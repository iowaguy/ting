#!/usr/bin/env python3

"""A module for accessing the Ting API from the command line."""

import argparse
import logging
from os.path import realpath, dirname
import signal
import sys
from typing import Any, Dict, List

SCRIPT_DIR = dirname(realpath(__file__))

# This line is required so I can use the ting module
sys.path.append(SCRIPT_DIR + "/../")

# This has to be after I've added ting to the import path
from ting import ting  # pylint: disable=wrong-import-position

__LOGGER = logging.getLogger(__name__)


def __read_config_file(path: str) -> List[str]:
    with open(path) as file:
        __LOGGER.info("Read config file %s", path)
        lines = file.readlines()
    return lines


def __assemble_configuration_dict(path: str) -> Dict[str, Any]:
    config: Dict[str, Any] = {}
    for line in __read_config_file(path):
        pair = line.strip().split()

        try:
            config[pair[0]] = int(pair[1])
        except ValueError:
            config[pair[0]] = pair[1]
    if "InputFile" not in config:
        config["InputFile"] = None

    arg_overrides = [
        (args.dest_port, "DestinationPort"),
        (args.input_file, "InputFile"),
        (args.output_file, "ResultsDirectory"),
    ]

    for override in arg_overrides:
        if override[0] is not None:
            try:
                config[override[1]] = int(override[0])
            except ValueError:
                config[override[1]] = override[0]

    if args.relay1 and args.relay2:
        config["Pair"] = (args.relay1, args.relay2)
    else:
        config["Pair"] = None

    return config


if __name__ == "__main__":
    RESULT_DIRECTORY = "results"
    parser = argparse.ArgumentParser(  # pylint: disable=invalid-name
        prog="ting",
        description="Measure latency between either a pair of Tor relays\
                     (relay1,relay2), or a list of pairs, specified with\
                     the --input-file argument.",
    )
    parser.add_argument(
        "relay1",
        help="Tor relay identified by IP or Fingerprint",
        nargs="?",
        default=None,
    )
    parser.add_argument(
        "relay2",
        help="Tor relay identified by IP or Fingerprint",
        nargs="?",
        default=None,
    )
    parser.add_argument(
        "--output-file", help="store detailed results of run in JSON (default none)"
    )
    parser.add_argument("--dest-port", help="port of local echo server (default 16667)")
    parser.add_argument(
        "--num-samples",
        help="number of samples for each circuit (default 10)",
        type=int,
        default=1,
    )
    parser.add_argument(
        "--config-file",
        help="specify a file to read configuration options from (default ./tingrc)",
        default="tingrc",
    )
    parser.add_argument(
        "--input-file",
        help="""read list of relay pairs to measure from file, which contains
                one space-separated pair of fingerprints or ips per line 
                (default none)""",
    )
    parser.add_argument(
        "--log-level",
        choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
        default="INFO",
        help="The log level.",
    )
    args = parser.parse_args()  # pylint: disable=invalid-name

    logging.getLogger().setLevel(level=getattr(logging, args.log_level.upper()))

    configuration = __assemble_configuration_dict(  # pylint: disable=invalid-name
        args.config_file
    )

    def catch_sigint(sig: Any, frame: Any) -> None:  # pylint: disable=unused-argument
        """Catch SIGINT and exit with return code zero."""
        sys.exit(0)

    signal.signal(signal.SIGINT, catch_sigint)

    print(
        ting(
            [(args.relay1, args.relay2)],
            configuration["W"],
            configuration["Z"],
            num_samples=args.num_samples,
            **configuration,
        )
    )
