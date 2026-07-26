"""
app/utils/logger.py

Purpose
-------
One place to configure logging so every module gets consistent,
timestamped, leveled output instead of ad-hoc print()s.

Responsibilities
----------------
- `get_logger(name)` returns a configured logger. Call it as
  `logger = get_logger(__name__)` at the top of every module.

Dependencies
------------
Python stdlib logging only.
"""

import logging
import sys

from app.config.settings import get_settings

_CONFIGURED = False


def _configure_root() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    settings = get_settings()
    root = logging.getLogger()
    root.setLevel(settings.LOG_LEVEL)

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    root.handlers = [handler]
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    _configure_root()
    return logging.getLogger(name)
