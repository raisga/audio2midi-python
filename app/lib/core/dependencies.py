"""Install the app dependencies (Python packages and FFmpeg)."""

import logging
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from lib.errors import Audio2MidiError

logger = logging.getLogger(__name__)

REQUIREMENTS_FILE = Path(__file__).resolve().parents[3] / "requirements.txt"

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


def install_python_packages(requirements: Path = REQUIREMENTS_FILE) -> None:
    _run([sys.executable, "-m", "pip", "install", "-r", str(requirements)])


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
