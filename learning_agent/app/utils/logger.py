"""
app/utils/logger.py

Standard Python logging configuration for Learning Agent.
"""

import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)


def get_logger(name: str):
    return logging.getLogger(name)
