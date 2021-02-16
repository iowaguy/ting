import logging

EMAIL_ADDR = None  # set this to your email address to get email notifications


class Color:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    SUCCESS = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    END = "\033[0m"


def success(msg):
    print(msg, flush=True)


def warning(msg):
    logging.warning(msg)


def failure(msg):
    logging.critical(msg)
    sys.exit(-1)


def log(msg):
    logging.info(msg)


def notify(type, msg):
    if EMAIL_ADDR:
        os.system(
            "echo '{0}' | mailx -s 'Ting {1}' '{2}'".format(msg, type, EMAIL_ADDR)
        )
