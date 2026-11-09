"""Resolve the files and folders given on the command line into a list of audio files."""

from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

from audio2midi.errors import Audio2MidiError

# Extensions picked up when scanning folders. Files given explicitly are always accepted:
# demucs falls back to FFmpeg, which reads almost any format.
AUDIO_EXTENSIONS = frozenset({
    ".aac", ".aif", ".aiff", ".alac", ".flac", ".m4a", ".mp3", ".oga", ".ogg", ".opus", ".wav", ".wma",
})  # fmt: skip


def _is_within(path: Path, directory: Path) -> bool:
    try:
        path.relative_to(directory)
    except ValueError:
        return False
    return True


def _scan_directory(directory: Path, recursive: bool, exclude: Path | None) -> list[Path]:
    pattern = "**/*" if recursive else "*"
    found = []
    for path in sorted(directory.glob(pattern)):
        relative_parts = path.relative_to(directory).parts
        if any(part.startswith(".") for part in relative_parts):  # hidden files, macOS "._" forks
            continue
        if not path.is_file() or path.suffix.lower() not in AUDIO_EXTENSIONS:
            continue
        if exclude is not None and _is_within(path.resolve(), exclude):  # previous results
            continue
        found.append(path)
    return found


def collect_input_files(
    paths: Iterable[Path], recursive: bool = False, output_dir: Path | None = None
) -> list[Path]:
    """Expand folders into the audio files they contain, keeping order and dropping duplicates.

    Args:
        paths: Files and folders, in the order they were given.
        recursive: Also scan the subfolders of folders.
        output_dir: Skipped while scanning, so earlier results are not processed again.
    """
    exclude = Path(output_dir).resolve() if output_dir is not None else None
    files, seen = [], set()
    for path in map(Path, paths):
        if path.is_dir():
            candidates = _scan_directory(path, recursive, exclude)
            if not candidates:
                raise Audio2MidiError(f"No audio files found in {path}")
        else:
            candidates = [path]
        for candidate in candidates:
            key = candidate.resolve()
            if key not in seen:
                seen.add(key)
                files.append(candidate)
    return files


def find_output_conflicts(files: Iterable[Path]) -> dict[str, list[Path]]:
    """Inputs sharing a file name stem, which would write to the same output folder."""
    by_stem = defaultdict(list)
    for path in files:
        by_stem[Path(path).stem].append(Path(path))
    return {stem: paths for stem, paths in by_stem.items() if len(paths) > 1}
