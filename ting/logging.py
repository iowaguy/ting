"""Logging functions used by Ting."""

import logging
import sys


class Color:  # pylint: disable=too-few-public-methods
    """Useful color codes."""

    HEADER = "\033[95m"
    BLUE = "\033[94m"
    SUCCESS = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    END = "\033[0m"


def failure(msg: str) -> None:
    """Log a critical failure and exit."""
    logging.critical(msg)
    sys.exit(-1)
