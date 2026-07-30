"""
app/utils/logger.py

Built-in logging configuration for Notification Agent.
"""

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)


def get_logger(name: str):
    return logging.getLogger(name)
