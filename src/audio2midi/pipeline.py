"""Audio -> stems -> variations -> audio files (+ MIDI files) pipeline."""

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from audio2midi.constants import (
    DEFAULT_AUDIO_FORMAT,
    DEFAULT_DEVICE,
    DEFAULT_MODEL_NAME,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_OVERLAP,
    DEFAULT_SELECTED_OP,
    DEFAULT_SHIFTS,
    LOG_FILE_NAME,
    MIDI_EXTENSION,
)
from audio2midi.core import audio_io, compress, separate
from audio2midi.core.convert import MidiConverter, MidiOptions
from audio2midi.core.variations import build_variations
from audio2midi.errors import Audio2MidiError
from audio2midi.utils.logger import add_file_handler

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PipelineConfig:
    input_file: Path
    output_dir: Path = Path(DEFAULT_OUTPUT_DIR)
    model_name: str = DEFAULT_MODEL_NAME
    operation: str = DEFAULT_SELECTED_OP
    tracks: Sequence[str] | None = None  # None selects every track of the model
    audio_format: str = DEFAULT_AUDIO_FORMAT
    compress: bool = False
    midi: bool = True
    midi_options: MidiOptions = field(default_factory=MidiOptions)
    device: str = DEFAULT_DEVICE
    shifts: int = DEFAULT_SHIFTS
    overlap: float = DEFAULT_OVERLAP
    jobs: int = 0
    log: bool = False
    verbose: bool = False

    @property
    def track_dir(self) -> Path:
        """Where results go: <outdir>/<audio file name>/<operation>."""
        return Path(self.output_dir) / Path(self.input_file).stem / self.operation


@dataclass
class PipelineResult:
    output_dir: Path
    audio_files: list[Path] = field(default_factory=list)
    midi_files: list[Path] = field(default_factory=list)


def _select_tracks(available: Sequence[str], requested: Sequence[str] | None, model_name: str) -> list[str]:
    if not requested:
        return list(available)
    missing = [track for track in requested if track not in available]
    if missing:
        raise Audio2MidiError(
            f"Model '{model_name}' cannot extract {', '.join(missing)} "
            f"(available: {', '.join(available)})"
        )
    # Keep the model's stem order so outputs are deterministic.
    return [track for track in available if track in requested]


def run_pipeline(config: PipelineConfig) -> PipelineResult:
    track_dir = config.track_dir
    track_dir.mkdir(parents=True, exist_ok=True)
    if config.log:
        add_file_handler(track_dir / LOG_FILE_NAME)

    logger.info("- Input file: %s", config.input_file)
    logger.info("- Output directory: %s", config.output_dir)
    logger.info("- Model name: %s", config.model_name)
    logger.info("- Selected operation: %s", config.operation)
    logger.info("- Tracks: %s", ", ".join(config.tracks) if config.tracks else "all")
    logger.info(">> Starting split audio file operations... 🚀")

    separator = separate.load_separator(
        config.model_name,
        device=separate.resolve_device(config.device),
        shifts=config.shifts,
        overlap=config.overlap,
        jobs=config.jobs,
        progress=config.verbose,
    )
    tracks = _select_tracks(separator.model.sources, config.tracks, config.model_name)
    stems, samplerate = separate.separate(separator, Path(config.input_file))

    result = PipelineResult(output_dir=track_dir)
    variations = build_variations(stems, tracks, config.operation)
    logger.info("> Using %s operation, exporting %d tracks", config.operation, len(variations))
    for name, wav in variations.items():
        path = track_dir / f"{name}.{config.audio_format}"
        audio_io.save_audio(wav, path, samplerate)
        logger.info("  - %s", path)
        result.audio_files.append(path)

    if config.midi:
        logger.info(">> Converting audio to MIDI... ⏳")
        converter = MidiConverter(config.midi_options)
        for audio_file in result.audio_files:
            midi_file = audio_file.with_suffix(f".{MIDI_EXTENSION}")
            converter.convert(audio_file, midi_file)
            logger.info("  - %s", midi_file)
            result.midi_files.append(midi_file)

    if config.compress:
        logger.info(">> Compressing audio files... 🗜️")
        for audio_file in result.audio_files:
            compress.compress_mp3(audio_file)

    logger.info(">> Done! ✅")
    return result
