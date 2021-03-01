"""Logging functions used by Ting."""

import logging
import os
import sys

EMAIL_ADDR = None  # set this to your email address to get email notifications


class Color:
    """Useful color codes."""

    HEADER = "\033[95m"
    BLUE = "\033[94m"
    SUCCESS = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    END = "\033[0m"


def success(msg):
    logging.info(msg, flush=True)


def warning(msg):
    logging.warning(msg)


def failure(msg):
    """Log a critical failure and exit."""
    logging.critical(msg)
    sys.exit(-1)


def log(msg):
    logging.info(msg)


def debug(msg):
    logging.debug(msg)


def notify(msg_type, msg):
    """Send email alert."""
    if EMAIL_ADDR:
        os.system(
            "echo '{0}' | mailx -s 'Ting {1}' '{2}'".format(msg, msg_type, EMAIL_ADDR)
        )
