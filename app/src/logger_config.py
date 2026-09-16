"""Runtime logging configuration for the complete pipeline."""

from __future__ import annotations

import logging
from pathlib import Path


def configure_logging(path: Path) -> logging.Logger:
    """Create a fresh UTF-8 file logger for one pipeline execution."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("dcf_pipeline")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    handler = logging.FileHandler(destination, mode="w", encoding="utf-8")
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
    logger.addHandler(handler)
    return logger

