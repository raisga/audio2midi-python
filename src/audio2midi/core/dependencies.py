"""Install the app dependencies (Python packages and FFmpeg)."""

import logging
import platform
import shutil
import subprocess
import sys
from importlib import metadata

from audio2midi.constants import APP_NAME
from audio2midi.errors import Audio2MidiError

logger = logging.getLogger(__name__)

FFMPEG_HINTS = {
    "Linux": "sudo apt install ffmpeg | sudo pacman -S ffmpeg | sudo dnf install ffmpeg",
    "Darwin": "brew install ffmpeg",
    "Windows": "winget install ffmpeg",
}


def _run(command):
    logger.info("$ %s", " ".join(command))
    try:
        subprocess.run(command, check=True)
    except (OSError, subprocess.CalledProcessError) as error:
        raise Audio2MidiError(f"Command failed: {' '.join(command)}") from error


def runtime_requirements() -> list[str]:
    """The package's own runtime requirements, read from its installed metadata."""
    try:
        requirements = metadata.requires(APP_NAME) or []
    except metadata.PackageNotFoundError as error:
        raise Audio2MidiError(f"{APP_NAME} is not installed, run: pip install -e .") from error
    return [requirement for requirement in requirements if "extra ==" not in requirement]


def install_python_packages() -> None:
    """Install (or repair) the Python dependencies with pip."""
    _run([sys.executable, "-m", "pip", "install", *runtime_requirements()])


def ensure_ffmpeg() -> None:
    """Install FFmpeg with Homebrew on macOS, otherwise explain how to install it."""
    if shutil.which("ffmpeg"):
        logger.info("FFmpeg is already installed")
        return
    system = platform.system()
    if system == "Darwin" and shutil.which("brew"):
        _run(["brew", "install", "ffmpeg"])
        return
    hint = FFMPEG_HINTS.get(system, "https://ffmpeg.org/download.html")
    raise Audio2MidiError(f"FFmpeg is not installed, install it with: {hint}")


def install_dependencies() -> None:
    logger.info(">> Installing dependencies if needed... ⏳")
    install_python_packages()
    ensure_ffmpeg()
    logger.info(">> Dependencies installed ✅")
