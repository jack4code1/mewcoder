"""Logging configuration for MewCode"""

import logging
import os
from pathlib import Path

def setup_logging(log_file: str = None, console_output: bool = False):
    """Setup logging configuration"""
    handlers: list[logging.Handler] = []

    try:
        # Create logs directory. Tests/sandboxes can override this with a
        # writable path; if the user directory is unavailable, logging falls
        # back to a NullHandler instead of preventing imports.
        log_dir = Path(
            os.getenv("MEWCODE_LOG_DIR", str(Path.home() / ".mewcode" / "logs"))
        ).expanduser()
        log_dir.mkdir(parents=True, exist_ok=True)

        # Default log file
        if log_file is None:
            log_file = log_dir / "mewcode.log"

        handlers.append(logging.FileHandler(log_file, encoding='utf-8'))
    except OSError:
        handlers.append(logging.NullHandler())

    # Only add console handler if explicitly requested
    if console_output:
        handlers.append(logging.StreamHandler())

    logging.basicConfig(
        level=logging.WARNING,  # 只记录警告和错误
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers
    )

    return logging.getLogger("mewcode")

# Create logger instance - 默认不输出到控制台
logger = setup_logging(console_output=False)
