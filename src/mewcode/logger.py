"""Logging configuration for MewCode."""

import logging
import os
from pathlib import Path


def setup_logging(log_file: str = None, console_output: bool = False):
    """Set up logging configuration."""
    handlers: list[logging.Handler] = []

    try:
        log_dir = Path(
            os.getenv("MEWCODE_LOG_DIR", str(Path.home() / ".mewcode" / "logs"))
        ).expanduser()
        log_dir.mkdir(parents=True, exist_ok=True)

        if log_file is None:
            log_file = log_dir / "mewcode.log"

        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    except OSError:
        handlers.append(logging.NullHandler())

    if console_output:
        handlers.append(logging.StreamHandler())

    level_name = os.getenv("MEWCODE_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers,
    )

    return logging.getLogger("mewcode")


logger = setup_logging(console_output=False)
