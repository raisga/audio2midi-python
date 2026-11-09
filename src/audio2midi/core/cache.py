"""On-disk cache of separated stems, so re-running a file skips the slow separation.

Every stem of a separation is stored, whatever tracks were selected, as 24-bit FLAC: lossless
enough that outputs built from cached stems match a fresh separation. Model output can exceed
[-1, 1], so each stem is scaled into range and its scale factor saved in the entry's manifest.

Entries are keyed by the input file *content* (renaming or moving a file keeps its entry) and by
every setting that changes the separation. The least recently used entries are evicted once the
cache grows past its size limit.
"""

import hashlib
import json
import logging
import os
import platform
import re
import shutil
import time
from collections.abc import Mapping
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path

from audio2midi.constants import APP_NAME

logger = logging.getLogger(__name__)

CACHE_DIR_ENV = "AUDIO2MIDI_CACHE_DIR"
CACHE_SIZE_ENV = "AUDIO2MIDI_CACHE_SIZE"
DEFAULT_CACHE_SIZE = "2GB"
CACHE_FORMAT_VERSION = 1  # bump when the entry layout changes, invalidating old entries
MANIFEST = "manifest.json"
STEMS_DIR = "stems"
TMP_MARKER = ".tmp-"
STALE_TMP_SECONDS = 3600  # leftovers of interrupted writes older than this are removed
MAX_PCM_LEVEL = 0.99

_SIZE_UNITS = {"": 1, "B": 1, "K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}


def default_cache_dir() -> Path:
    """$AUDIO2MIDI_CACHE_DIR, otherwise the platform's user cache folder."""
    override = os.environ.get(CACHE_DIR_ENV)
    if override:
        return Path(override).expanduser()
    system = platform.system()
    if system == "Darwin":
        base = Path.home() / "Library" / "Caches"
    elif system == "Windows":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return base / APP_NAME


def parse_size(text: str) -> int:
    """Parse sizes like "500MB", "2GB", "1.5G" or "0" into bytes (binary units)."""
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([KMGT]?)(?:I?B)?\s*", text.upper())
    if not match:
        raise ValueError(f"invalid size '{text}', use a value like 500MB or 2GB")
    number, unit = match.groups()
    return int(float(number) * _SIZE_UNITS[unit])


def configured_max_size() -> int:
    """$AUDIO2MIDI_CACHE_SIZE in bytes, or the default limit."""
    return parse_size(os.environ.get(CACHE_SIZE_ENV) or DEFAULT_CACHE_SIZE)


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _demucs_version() -> str:
    try:
        return metadata.version("demucs")
    except metadata.PackageNotFoundError:
        return "unknown"


def _dir_size(path: Path) -> int:
    return sum(file.stat().st_size for file in path.rglob("*") if file.is_file())


@dataclass(frozen=True)
class CachedStems:
    stems: dict  # stem name -> (channels, samples) float32 numpy array
    samplerate: int


class StemCache:
    """Stems cache rooted at `root` (entries live in `root/stems`)."""

    def __init__(self, root: Path, max_size: int):
        self.root = Path(root)
        self.entries_dir = self.root / STEMS_DIR
        self.max_size = max_size

    def key(self, audio_file: Path, model_name: str, shifts: int, overlap: float) -> str:
        """Identify a separation by the input content and every setting that changes the stems."""
        settings = {
            "format": CACHE_FORMAT_VERSION,
            "demucs": _demucs_version(),
            "input": _file_digest(Path(audio_file)),
            "model": model_name,
            "shifts": shifts,
            "overlap": overlap,
        }
        return hashlib.sha256(json.dumps(settings, sort_keys=True).encode()).hexdigest()

    def _entry_dir(self, key: str) -> Path:
        return self.entries_dir / key[:2] / key

    def load(self, key: str) -> CachedStems | None:
        """Return the cached stems, or None on a miss. A broken entry is removed and is a miss."""
        entry = self._entry_dir(key)
        manifest_path = entry / MANIFEST
        if not manifest_path.is_file():
            return None
        try:
            import numpy
            import soundfile

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            stems = {}
            for stem in manifest["stems"]:
                audio, samplerate = soundfile.read(str(entry / stem["file"]), dtype="float32", always_2d=True)
                if samplerate != manifest["samplerate"]:
                    raise ValueError(f"{stem['file']} has a sample rate of {samplerate}")
                stems[stem["name"]] = numpy.ascontiguousarray(audio.T) * numpy.float32(stem["scale"])
            os.utime(manifest_path)  # mark as recently used for eviction
            return CachedStems(stems=stems, samplerate=manifest["samplerate"])
        except Exception as error:  # noqa: BLE001 - a broken cache entry must never fail a run
            logger.warning("Ignoring broken cache entry %s: %s", entry, error)
            shutil.rmtree(entry, ignore_errors=True)
            return None

    def store(self, key: str, stems: Mapping[str, "numpy.ndarray"], samplerate: int, source: str = "") -> bool:  # noqa: F821
        """Save stems ((channels, samples) arrays). Returns False, with a warning, if it fails."""
        entry = self._entry_dir(key)
        tmp = entry.with_name(f"{entry.name}{TMP_MARKER}{os.getpid()}")
        try:
            import numpy
            import soundfile

            shutil.rmtree(tmp, ignore_errors=True)
            tmp.mkdir(parents=True)
            manifest = {"format": CACHE_FORMAT_VERSION, "samplerate": samplerate, "source": source, "stems": []}
            for name, audio in stems.items():
                audio = numpy.asarray(audio, dtype=numpy.float32)
                peak = float(numpy.abs(audio).max()) if audio.size else 0.0
                scale = peak / MAX_PCM_LEVEL if peak > MAX_PCM_LEVEL else 1.0
                file_name = f"{name}.flac"
                soundfile.write(str(tmp / file_name), (audio / scale).T, samplerate, subtype="PCM_24")
                manifest["stems"].append({"name": name, "file": file_name, "scale": scale})
            (tmp / MANIFEST).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            if entry.exists() and not (entry / MANIFEST).is_file():  # leftover without a manifest
                shutil.rmtree(entry)
            try:
                os.rename(tmp, entry)
            except OSError:
                if not (entry / MANIFEST).is_file():  # not just another process storing it first
                    raise
                shutil.rmtree(tmp, ignore_errors=True)
        except Exception as error:  # noqa: BLE001 - caching is an optimization, never fail a run
            logger.warning("Could not cache stems in %s: %s", self.entries_dir, error)
            shutil.rmtree(tmp, ignore_errors=True)
            return False
        self.evict(keep=key)
        return True

    def evict(self, keep: str | None = None) -> None:
        """Delete least recently used entries until the cache fits in `max_size`."""
        if not self.entries_dir.is_dir():
            return
        entries = []
        now = time.time()
        for path in self.entries_dir.glob("*/*"):
            if TMP_MARKER in path.name:
                if now - path.stat().st_mtime > STALE_TMP_SECONDS:
                    shutil.rmtree(path, ignore_errors=True)
                continue
            manifest = path / MANIFEST
            last_used = manifest.stat().st_mtime if manifest.is_file() else 0.0
            entries.append((last_used, path))
        total = sum(_dir_size(path) for _, path in entries)
        for _, path in sorted(entries, key=lambda item: item[0]):
            if total <= self.max_size:
                break
            if path.name == keep:
                continue
            size = _dir_size(path)
            shutil.rmtree(path, ignore_errors=True)
            total -= size
            logger.debug("Evicted cache entry %s (%d bytes)", path.name, size)

    def size(self) -> int:
        return _dir_size(self.entries_dir) if self.entries_dir.is_dir() else 0

    def clear(self) -> int:
        """Delete every entry, returning the number of bytes freed."""
        freed = self.size()
        shutil.rmtree(self.entries_dir, ignore_errors=True)
        return freed
