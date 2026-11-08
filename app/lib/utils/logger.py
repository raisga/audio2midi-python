"""Console and file logging setup."""

import logging
import sys
from pathlib import Path
from typing import Optional

ROOT_LOGGER = "lib"


def setup_logging(verbose: bool = False, log_file: Optional[Path] = None) -> logging.Logger:
    """Configure the app logger.

    Console shows INFO messages in verbose mode, warnings and errors otherwise.
    The optional log file always records everything, with timestamps.
    """
    # Third-party libraries (basic-pitch) log noise on the root logger, which would otherwise
    # trigger logging's implicit stderr configuration.
    root = logging.getLogger()
    if not root.handlers:
        root.addHandler(logging.NullHandler())

    logger = logging.getLogger(ROOT_LOGGER)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO if verbose else logging.WARNING)
    console.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(console)

    if log_file is not None:
        add_file_handler(log_file)
    return logger


def add_file_handler(log_file: Path) -> None:
    log_file = Path(log_file)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(log_file, encoding="utf-8")
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    logging.getLogger(ROOT_LOGGER).addHandler(handler)
