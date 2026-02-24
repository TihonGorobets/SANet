"""
logging_setup.py
Configures both a rotating file handler and a coloured stream handler.
Call :func:`configure_logging` once at application startup.
"""

import logging
import logging.handlers
from pathlib import Path

from .config import LOG_BACKUP_COUNT, LOG_FILE, LOG_MAX_BYTES


class _ColourFormatter(logging.Formatter):
    """ANSI-coloured log formatter for terminal output."""

    _COLOURS = {
        logging.DEBUG:    "\033[36m",   # cyan
        logging.INFO:     "\033[32m",   # green
        logging.WARNING:  "\033[33m",   # yellow
        logging.ERROR:    "\033[31m",   # red
        logging.CRITICAL: "\033[35m",   # magenta
    }
    _RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        colour = self._COLOURS.get(record.levelno, "")
        record.levelname = f"{colour}{record.levelname}{self._RESET}"
        return super().format(record)


def configure_logging(level: str = "INFO") -> None:
    """
    Set up root logger with:
    - A rotating file handler writing to :data:`~config.LOG_FILE`.
    - A coloured console handler.
    """
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    numeric_level = getattr(logging, level.upper(), logging.INFO)
    fmt           = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    date_fmt      = "%Y-%m-%d %H:%M:%S"

    root = logging.getLogger()
    root.setLevel(numeric_level)
    root.handlers.clear()

    # ── File handler ──────────────────────────────────────────────────────────
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(logging.Formatter(fmt, datefmt=date_fmt))
    root.addHandler(file_handler)

    # ── Console handler ───────────────────────────────────────────────────────
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(_ColourFormatter(fmt, datefmt=date_fmt))
    root.addHandler(console_handler)

    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("pdfminer").setLevel(logging.WARNING)
