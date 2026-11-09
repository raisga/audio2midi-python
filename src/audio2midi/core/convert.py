"""Convert audio tracks to MIDI with Spotify's basic-pitch."""

import contextlib
import io
import warnings
from dataclasses import asdict, dataclass
from pathlib import Path

from audio2midi.constants import (
    DEFAULT_FRAME_THRESHOLD,
    DEFAULT_MIDI_TEMPO,
    DEFAULT_MINIMUM_NOTE_LENGTH,
    DEFAULT_ONSET_THRESHOLD,
)


@dataclass(frozen=True)
class MidiOptions:
    """Parameters forwarded to `basic_pitch.inference.predict`."""

    onset_threshold: float = DEFAULT_ONSET_THRESHOLD
    frame_threshold: float = DEFAULT_FRAME_THRESHOLD
    minimum_note_length: float = DEFAULT_MINIMUM_NOTE_LENGTH
    minimum_frequency: float | None = None
    maximum_frequency: float | None = None
    multiple_pitch_bends: bool = False
    melodia_trick: bool = True
    midi_tempo: float = DEFAULT_MIDI_TEMPO


class MidiConverter:
    """Loads the basic-pitch model once and reuses it for every track."""

    def __init__(self, options: MidiOptions | None = None):
        self.options = options or MidiOptions()
        self._model = None

    def _get_model(self):
        if self._model is None:
            from basic_pitch import FilenameSuffix, build_icassp_2022_model_path
            from basic_pitch.inference import Model

            # Always use the ONNX model: onnxruntime is maintained and numpy 2 compatible,
            # unlike tflite-runtime, which basic-pitch would pick by default on Linux.
            self._model = Model(build_icassp_2022_model_path(FilenameSuffix.onnx))
        return self._model

    def convert(self, audio_file: Path, midi_file: Path) -> Path:
        with warnings.catch_warnings():
            # resampy (a basic-pitch dependency) still imports the deprecated pkg_resources.
            warnings.filterwarnings("ignore", message="pkg_resources is deprecated", category=UserWarning)
            from basic_pitch.inference import predict

        # basic-pitch prints a line per file, progress is reported by our logger instead.
        with contextlib.redirect_stdout(io.StringIO()):
            _, midi_data, _ = predict(str(audio_file), self._get_model(), **asdict(self.options))
        midi_data.write(str(midi_file))
        return Path(midi_file)
