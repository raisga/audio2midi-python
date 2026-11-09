class Audio2MidiError(Exception):
    """An expected failure that should be reported to the user without a traceback."""


class ModelLoadError(Audio2MidiError):
    """The separation model cannot be loaded: every file would fail, so a batch stops."""
