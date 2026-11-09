"""Console and file logging setup."""

import logging
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

ROOT_LOGGER = "audio2midi"


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Configure the app logger: INFO messages in verbose mode, warnings and errors otherwise."""
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
    return logger


@contextmanager
def log_to_file(log_file: Path) -> Iterator[None]:
    """Also record everything logged inside the block, with timestamps, to `log_file`."""
    log_file = Path(log_file)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(log_file, encoding="utf-8")
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    logger = logging.getLogger(ROOT_LOGGER)
    logger.addHandler(handler)
    try:
        yield
    finally:
        logger.removeHandler(handler)
        handler.close()
