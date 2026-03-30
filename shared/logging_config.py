"""
Shared logging configuration for all services.

Usage in any service:
    from shared.logging_config import get_logger
    logger = get_logger("agent_system_a.supervisor")

Produces structured, human-readable logs like:
    2026-03-26 14:23:01 | INFO     | agent_system_a.supervisor | Routing query to property_analyst
    2026-03-26 14:23:01 | ERROR    | agent_system_b.pipeline   | Comp evaluation failed | error=JSONDecodeError

Logs go to:
    - Console (colored, for dev)
    - Rotating file: logs/<service>.log (for persistence)
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler

# Log directory — project root /logs/
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# Format: timestamp | level | module | message
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-40s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Log level from env (default INFO)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


class ColorFormatter(logging.Formatter):
    """Adds ANSI colors to console output for readability."""
    COLORS = {
        "DEBUG": "\033[36m",     # cyan
        "INFO": "\033[32m",      # green
        "WARNING": "\033[33m",   # yellow
        "ERROR": "\033[31m",     # red
        "CRITICAL": "\033[1;31m",  # bold red
    }
    RESET = "\033[0m"

    def format(self, record):
        color = self.COLORS.get(record.levelname, "")
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


def get_logger(name: str, log_file: str = None) -> logging.Logger:
    """Create a configured logger.

    Args:
        name: Logger name, typically "service.module" (e.g., "agent_system_a.supervisor")
        log_file: Optional filename override. Defaults to the top-level service name.

    Returns:
        Configured logging.Logger instance.
    """
    logger = logging.getLogger(name)

    # Avoid adding handlers multiple times if get_logger is called again
    if logger.handlers:
        return logger

    logger.setLevel(LOG_LEVEL)
    logger.propagate = False  # Don't bubble up to root logger

    # --- Console handler (colored) ---
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(LOG_LEVEL)
    console.setFormatter(ColorFormatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    logger.addHandler(console)

    # --- File handler (rotating, 5MB max, 3 backups) ---
    if log_file is None:
        # Extract service name: "agent_system_a.supervisor" → "agent_system_a"
        log_file = name.split(".")[0] + ".log"

    file_path = os.path.join(LOG_DIR, log_file)
    file_handler = RotatingFileHandler(
        file_path,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(LOG_LEVEL)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    logger.addHandler(file_handler)

    return logger
