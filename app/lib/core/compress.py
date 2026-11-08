"""Compress mp3 files with FFmpeg (VBR re-encode, metadata stripped)."""

import os
import shutil
import subprocess
from pathlib import Path

from lib.constants import COMPRESS_MP3_QUALITY
from lib.errors import Audio2MidiError


def compress_mp3(path: Path, quality: int = COMPRESS_MP3_QUALITY) -> Path:
    """Re-encode `path` in place as a variable bitrate mp3."""
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise Audio2MidiError("FFmpeg is required to compress files, run with --install")
    path = Path(path)
    tmp_path = path.with_name(f".{path.stem}.compressed{path.suffix}")
    command = [
        ffmpeg, "-hide_banner", "-loglevel", "error",
        "-i", str(path),
        "-codec:a", "libmp3lame", "-qscale:a", str(quality),
        "-map_metadata", "-1", "-id3v2_version", "3",
        "-y", str(tmp_path),
    ]  # fmt: skip
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as error:
        tmp_path.unlink(missing_ok=True)
        raise Audio2MidiError(f"FFmpeg failed to compress {path}: {error.stderr.strip()}") from error
    os.replace(tmp_path, path)
    return path
