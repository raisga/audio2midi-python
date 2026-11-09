"""Audio -> stems -> variations -> audio files (+ MIDI files) pipeline."""

import logging
from collections.abc import Callable, Sequence
from contextlib import nullcontext
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
    MODEL_TRACKS,
)
from audio2midi.core import audio_io, compress, separate
from audio2midi.core.cache import DEFAULT_CACHE_SIZE, StemCache, parse_size
from audio2midi.core.convert import MidiConverter, MidiOptions
from audio2midi.core.variations import build_variations
from audio2midi.errors import Audio2MidiError, ModelLoadError
from audio2midi.utils.logger import log_to_file

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PipelineConfig:
    """Settings shared by every processed file."""

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
    cache_dir: Path | None = None  # None disables the stems cache
    cache_max_size: int = parse_size(DEFAULT_CACHE_SIZE)

    def track_dir(self, input_file: Path) -> Path:
        """Where results go: <outdir>/<audio file name>/<operation>."""
        return Path(self.output_dir) / Path(input_file).stem / self.operation


@dataclass
class PipelineResult:
    input_file: Path
    output_dir: Path
    audio_files: list[Path] = field(default_factory=list)
    midi_files: list[Path] = field(default_factory=list)
    cached: bool = False  # stems came from the cache, the separation was skipped


@dataclass
class FileFailure:
    input_file: Path
    error: str


@dataclass
class BatchResult:
    results: list[PipelineResult] = field(default_factory=list)
    failures: list[FileFailure] = field(default_factory=list)


OnResult = Callable[[int, int, PipelineResult | FileFailure], None]


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


def _describe(error: Exception) -> str:
    if isinstance(error, Audio2MidiError):
        return str(error)
    return f"{type(error).__name__}: {error}" if str(error) else type(error).__name__


class Pipeline:
    """Processes audio files, loading the separation and MIDI models once for all of them.

    The separation model is only loaded when a file's stems are not cached.
    """

    def __init__(self, config: PipelineConfig):
        self.config = config
        self._separator = None
        self._converter = MidiConverter(config.midi_options) if config.midi else None
        self._cache = StemCache(config.cache_dir, config.cache_max_size) if config.cache_dir else None

    def load(self) -> None:
        """Load the separation model, raising `ModelLoadError` on failure."""
        if self._separator is not None:
            return
        config = self.config
        logger.info("> Loading model %s...", config.model_name)
        self._separator = separate.load_separator(
            config.model_name,
            device=separate.resolve_device(config.device),
            shifts=config.shifts,
            overlap=config.overlap,
            jobs=config.jobs,
            progress=config.verbose,
        )

    def _stems(self, input_file: Path) -> tuple[dict, int, bool]:
        """Stems of `input_file`, from the cache when possible: (stems, sample rate, cached)."""
        config = self.config
        key = None
        if self._cache is not None:
            key = self._cache.key(input_file, config.model_name, config.shifts, config.overlap)
            hit = self._cache.load(key)
            if hit is not None:
                logger.info("> Using cached stems from %s", self._cache.entries_dir)
                return separate.from_arrays(hit.stems), hit.samplerate, True
        self.load()
        stems, samplerate = separate.separate(self._separator, input_file)
        if self._cache is not None and self._cache.store(key, separate.to_arrays(stems), samplerate, input_file.name):
            logger.info("> Cached stems in %s", self._cache.entries_dir)
        return stems, samplerate, False

    def process(self, input_file: Path) -> PipelineResult:
        config = self.config
        track_dir = config.track_dir(input_file)
        track_dir.mkdir(parents=True, exist_ok=True)
        with log_to_file(track_dir / LOG_FILE_NAME) if config.log else nullcontext():
            try:
                return self._process(Path(input_file), track_dir)
            except Exception:
                logger.debug("Failed to process %s", input_file, exc_info=True)
                raise

    def _process(self, input_file: Path, track_dir: Path) -> PipelineResult:
        config = self.config
        logger.info("- Input file: %s", input_file)
        logger.info("- Output directory: %s", track_dir)
        logger.info("- Model name: %s", config.model_name)
        logger.info("- Selected operation: %s", config.operation)
        logger.info(">> Starting split audio file operations... 🚀")
        stems, samplerate, cached = self._stems(input_file)
        tracks = _select_tracks(list(stems), config.tracks, config.model_name)
        logger.info("- Tracks: %s", ", ".join(tracks))

        result = PipelineResult(input_file=input_file, output_dir=track_dir, cached=cached)
        variations = build_variations(stems, tracks, config.operation)
        logger.info("> Using %s operation, exporting %d tracks", config.operation, len(variations))
        for name, wav in variations.items():
            path = track_dir / f"{name}.{config.audio_format}"
            audio_io.save_audio(wav, path, samplerate)
            logger.info("  - %s", path)
            result.audio_files.append(path)

        if self._converter is not None:
            logger.info(">> Converting audio to MIDI... ⏳")
            for audio_file in result.audio_files:
                midi_file = audio_file.with_suffix(f".{MIDI_EXTENSION}")
                self._converter.convert(audio_file, midi_file)
                logger.info("  - %s", midi_file)
                result.midi_files.append(midi_file)

        if config.compress:
            logger.info(">> Compressing audio files... 🗜️")
            for audio_file in result.audio_files:
                compress.compress_mp3(audio_file)

        logger.info(">> Done! ✅")
        return result


def run_pipeline(config: PipelineConfig, input_files: Sequence[Path], on_result: OnResult | None = None) -> BatchResult:
    """Process every file. A failing file is recorded and the next one is processed.

    Args:
        on_result: Called with (index, total, result or failure) after each file, starting at 1.

    Raises:
        Audio2MidiError: When the tracks or the model are invalid, which would fail every file.
    """
    _select_tracks(MODEL_TRACKS.get(config.model_name, ()), config.tracks, config.model_name)
    pipeline = Pipeline(config)
    batch = BatchResult()
    total = len(input_files)
    for index, input_file in enumerate(input_files, start=1):
        if total > 1:
            logger.info(">> [%d/%d] %s", index, total, input_file)
        try:
            outcome = pipeline.process(input_file)
            batch.results.append(outcome)
        except ModelLoadError:
            raise
        except Exception as error:  # noqa: BLE001 - one bad file must not stop the batch
            outcome = FileFailure(input_file=Path(input_file), error=_describe(error))
            batch.failures.append(outcome)
        if on_result is not None:
            on_result(index, total, outcome)
    return batch
