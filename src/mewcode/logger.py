"""Logging configuration for MewCode"""

import logging
import os
from pathlib import Path

def setup_logging(log_file: str = None, console_output: bool = False):
    """Setup logging configuration"""
    # Create logs directory
    log_dir = Path.home() / ".mewcode" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    # Default log file
    if log_file is None:
        log_file = log_dir / "mewcode.log"

    # Configure logging
    handlers = [logging.FileHandler(log_file, encoding='utf-8')]

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
