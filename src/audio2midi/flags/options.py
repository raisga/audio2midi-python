"""Click options for the audio2midi command."""

from pathlib import Path

import click

from audio2midi.constants import (
    ALL_TRACKS,
    AUDIO_FORMATS,
    DEFAULT_AUDIO_FORMAT,
    DEFAULT_DEVICE,
    DEFAULT_FRAME_THRESHOLD,
    DEFAULT_MIDI_TEMPO,
    DEFAULT_MINIMUM_NOTE_LENGTH,
    DEFAULT_MODEL_NAME,
    DEFAULT_ONSET_THRESHOLD,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_OVERLAP,
    DEFAULT_SELECTED_OP,
    DEFAULT_SHIFTS,
    DEVICES,
    MODELS,
    OPERATIONS,
)


def _parse_tracks(ctx, param, values):
    """Accept both `-t bass -t drums` and `-t bass,drums`."""
    tracks = []
    for value in values:
        for track in value.split(","):
            track = track.strip().lower()
            if not track:
                continue
            if track not in ALL_TRACKS:
                raise click.BadParameter(f"'{track}' is not one of {', '.join(ALL_TRACKS)}", ctx, param)
            if track not in tracks:
                tracks.append(track)
    return tuple(tracks)


def _apply(options):
    def decorator(f):
        for option in reversed(options):
            f = option(f)
        return f

    return decorator


general_options = _apply([
    click.option("-v", "--verbose", is_flag=True, help="Enable verbose mode, show progress and details."),
    click.option("-i", "--install", is_flag=True, help="Install dependencies (Python packages and FFmpeg)."),
    click.option("-l", "--log", is_flag=True, help="Save a log file in the output directory."),
])  # fmt: skip

separation_options = _apply([
    click.option(
        "-f", "--file", "input_file",
        type=click.Path(exists=True, dir_okay=False, path_type=Path),
        help="Input audio file to process (mp3, wav, flac or any FFmpeg supported format).",
    ),
    click.option(
        "-o", "--outdir", "output_dir", default=DEFAULT_OUTPUT_DIR, show_default=True,
        type=click.Path(file_okay=False, path_type=Path), help="Output directory.",
    ),
    click.option(
        "-m", "--model", "model_name", default=DEFAULT_MODEL_NAME, show_default=True,
        type=click.Choice(MODELS), help="Demucs model, use htdemucs_6s for guitar and piano tracks.",
    ),
    click.option(
        "-s", "--select", "operation", default=DEFAULT_SELECTED_OP, show_default=True,
        type=click.Choice(OPERATIONS),
        help="Operation: op_mini (tracks), op_full (+ no_<track> complements), op_extra (+ track pairs).",
    ),
    click.option(
        "-t", "--tracks", multiple=True, callback=_parse_tracks, metavar="TRACK[,TRACK...]",
        help=f"Tracks to extract, repeatable or comma separated: {', '.join(ALL_TRACKS)} [default: all]",
    ),
    click.option(
        "-F", "--format", "audio_format", default=DEFAULT_AUDIO_FORMAT, show_default=True,
        type=click.Choice(AUDIO_FORMATS), help="Audio format of the extracted tracks.",
    ),
    click.option("-c", "--compress", is_flag=True, help="Compress the extracted mp3 tracks (VBR) with FFmpeg."),
    click.option(
        "-d", "--device", default=DEFAULT_DEVICE, show_default=True,
        type=click.Choice(DEVICES), help="Torch device used for the separation.",
    ),
    click.option(
        "--shifts", default=DEFAULT_SHIFTS, show_default=True, type=click.IntRange(min=1),
        help="Random shifts for equivariant stabilization, higher is better but slower.",
    ),
    click.option(
        "--overlap", default=DEFAULT_OVERLAP, show_default=True, type=click.FloatRange(0, 1, max_open=True),
        help="Overlap between separation windows.",
    ),
    click.option(
        "-j", "--jobs", default=0, show_default=True, type=click.IntRange(min=0),
        help="Number of parallel separation jobs (more memory).",
    ),
])  # fmt: skip

midi_options = _apply([
    click.option("--midi/--no-midi", default=True, show_default=True, help="Convert the extracted tracks to MIDI."),
    click.option(
        "--onset-threshold", default=DEFAULT_ONSET_THRESHOLD, show_default=True, type=click.FloatRange(0, 1),
        help="basic-pitch: minimum energy required for an onset to be considered present.",
    ),
    click.option(
        "--frame-threshold", default=DEFAULT_FRAME_THRESHOLD, show_default=True, type=click.FloatRange(0, 1),
        help="basic-pitch: minimum energy requirement for a frame to be considered present.",
    ),
    click.option(
        "--min-note-length", default=DEFAULT_MINIMUM_NOTE_LENGTH, show_default=True,
        type=click.FloatRange(min=0), help="basic-pitch: minimum allowed note length, in milliseconds.",
    ),
    click.option("--min-frequency", type=click.FloatRange(min=0), help="basic-pitch: minimum note frequency (Hz)."),
    click.option("--max-frequency", type=click.FloatRange(min=0), help="basic-pitch: maximum note frequency (Hz)."),
    click.option("--multiple-pitch-bends", is_flag=True, help="basic-pitch: allow overlapping notes to pitch bend."),
    click.option("--melodia/--no-melodia", default=True, show_default=True, help="basic-pitch: apply melodia trick."),
    click.option(
        "--midi-tempo", default=DEFAULT_MIDI_TEMPO, show_default=True, type=click.FloatRange(min=0, min_open=True),
        help="Tempo (BPM) written to the MIDI files.",
    ),
])  # fmt: skip
