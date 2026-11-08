"""Split an audio file into instrument stems with demucs."""

import logging
from pathlib import Path
from typing import Dict, Tuple

from lib.errors import Audio2MidiError

logger = logging.getLogger(__name__)


def resolve_device(device: str) -> str:
    """Translate "auto" into the best available torch device."""
    if device != "auto":
        return device
    import torch

    return "cuda" if torch.cuda.is_available() else "cpu"


def load_model(model_name: str):
    """Load (downloading on first use) a pretrained demucs model."""
    from demucs.pretrained import ModelLoadingError, get_model

    try:
        model = get_model(model_name)
    except ModelLoadingError as error:
        raise Audio2MidiError(f"Could not load model '{model_name}': {error}") from error
    model.eval()
    return model


def separate(
    model,
    audio_file: Path,
    device: str = "cpu",
    shifts: int = 1,
    overlap: float = 0.25,
    jobs: int = 0,
    progress: bool = False,
) -> Tuple[Dict[str, "torch.Tensor"], int]:  # noqa: F821
    """Separate `audio_file` into stems.

    Returns:
        A mapping of stem name to a (channels, samples) tensor, and the sample rate.
    """
    import torch
    from demucs.apply import apply_model
    from demucs.separate import load_track

    try:
        wav = load_track(Path(audio_file), model.audio_channels, model.samplerate)
    except SystemExit as error:  # demucs exits instead of raising on unreadable files
        raise Audio2MidiError(f"Could not read audio file: {audio_file}") from error

    # Normalize like `demucs.separate` does, guarding against silent input.
    ref = wav.mean(0)
    mean, std = ref.mean(), ref.std().clamp(min=1e-8)
    wav = (wav - mean) / std
    logger.debug("Running %s on %s (device=%s, shifts=%d)", type(model).__name__, audio_file, device, shifts)
    with torch.no_grad():
        sources = apply_model(
            model,
            wav[None],
            device=device,
            shifts=shifts,
            split=True,
            overlap=overlap,
            progress=progress,
            num_workers=jobs,
        )[0]
    sources = sources * std + mean
    return dict(zip(model.sources, sources)), model.samplerate
