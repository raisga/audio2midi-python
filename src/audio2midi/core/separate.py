"""Split an audio file into instrument stems with demucs."""

import logging
from pathlib import Path

from audio2midi.errors import Audio2MidiError

logger = logging.getLogger(__name__)


def resolve_device(device: str) -> str:
    """Translate "auto" into the best available torch device."""
    if device != "auto":
        return device
    import torch

    return "cuda" if torch.cuda.is_available() else "cpu"


def load_separator(
    model_name: str,
    device: str = "cpu",
    shifts: int = 1,
    overlap: float = 0.25,
    jobs: int = 0,
    progress: bool = False,
):
    """Load (downloading on first use) a pretrained demucs model, wrapped in a `demucs.api.Separator`."""
    from demucs.api import LoadModelError, Separator
    from demucs.repo import ModelLoadingError

    logger.debug("Loading %s (device=%s, shifts=%d, overlap=%s, jobs=%d)", model_name, device, shifts, overlap, jobs)
    try:
        return Separator(
            model=model_name,
            device=device,
            shifts=shifts,
            overlap=overlap,
            jobs=jobs,
            progress=progress,
        )
    except (LoadModelError, ModelLoadingError) as error:
        raise Audio2MidiError(f"Could not load model '{model_name}': {error}") from error
    except (ImportError, SystemExit) as error:  # demucs exits instead of raising when diffq is missing
        hint = ", quantized models need: pip install diffq" if model_name.endswith("_q") else ""
        raise Audio2MidiError(f"Could not load model '{model_name}'{hint}") from error


def separate(separator, audio_file: Path) -> tuple[dict[str, "torch.Tensor"], int]:  # noqa: F821
    """Separate `audio_file` into stems.

    Returns:
        A mapping of stem name to a (channels, samples) tensor, and the sample rate.
    """
    from demucs.api import LoadAudioError

    try:
        _, stems = separator.separate_audio_file(Path(audio_file))
    except LoadAudioError as error:
        raise Audio2MidiError(f"Could not read audio file {audio_file}:\n{error}") from error
    return stems, separator.samplerate
