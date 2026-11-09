"""Constants and default values shared across the app."""

from audio2midi import __version__

APP_NAME = "audio2midi"
VERSION = __version__

# Operations
OP_MINI = "op_mini"
OP_FULL = "op_full"
OP_EXTRA = "op_extra"
OPERATIONS = (OP_MINI, OP_FULL, OP_EXTRA)

# Demucs pretrained models
HTDEMUCS = "htdemucs"
HTDEMUCS_FT = "htdemucs_ft"
HTDEMUCS_6S = "htdemucs_6s"
MODELS = (
    HTDEMUCS,
    HTDEMUCS_FT,
    HTDEMUCS_6S,
    "hdemucs_mmi",
    "mdx",
    "mdx_extra",
    "mdx_q",
    "mdx_extra_q",
)

# Instrument tracks (stems), in the order demucs models produce them
INSTRUMENTS_TRACKS = ("drums", "bass", "other", "vocals")
SIX_STEMS_TRACKS = INSTRUMENTS_TRACKS + ("guitar", "piano")
ALL_TRACKS = SIX_STEMS_TRACKS
MODEL_TRACKS = {model: INSTRUMENTS_TRACKS for model in MODELS}
MODEL_TRACKS[HTDEMUCS_6S] = SIX_STEMS_TRACKS

# Output naming
COMPLEMENT_PREFIX = "no_"  # e.g. "no_vocals": everything except the vocals
COMBINATION_SEPARATOR = "_"  # e.g. "bass_drums": bass and drums mixed together
MIDI_EXTENSION = "mid"
LOG_FILE_NAME = f"{APP_NAME}.log"

# Audio output formats
AUDIO_FORMATS = ("mp3", "wav", "flac")
DEVICES = ("auto", "cpu", "cuda", "mps")

# FFmpeg VBR quality used when compressing mp3 files (0 = best, 9 = smallest)
COMPRESS_MP3_QUALITY = 0

# Default values
DEFAULT_VERBOSE_MODE = False
DEFAULT_COMPRESS_MODE = False
DEFAULT_OUTPUT_DIR = "output"
DEFAULT_MODEL_NAME = HTDEMUCS_FT
DEFAULT_SELECTED_OP = OP_MINI
DEFAULT_AUDIO_FORMAT = "mp3"
DEFAULT_MP3_BITRATE = 320
DEFAULT_DEVICE = "auto"
DEFAULT_SHIFTS = 1
DEFAULT_OVERLAP = 0.25

# basic-pitch defaults
DEFAULT_ONSET_THRESHOLD = 0.5
DEFAULT_FRAME_THRESHOLD = 0.3
DEFAULT_MINIMUM_NOTE_LENGTH = 127.70  # milliseconds
DEFAULT_MIDI_TEMPO = 120.0
