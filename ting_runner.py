#!/usr/bin/python3

import argparse
import contextlib
import logging

import ting.echo_server
import ting.ting


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
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
        help="number of samples for each circuit (default 200)",
        type=int,
    )
    parser.add_argument(
        "--num-repeats",
        help="number of times to measure each pair (default 1)",
        type=int,
    )
    parser.add_argument(
        "--config-file",
        help="specify a file to read configuration options from (default ./tingrc)",
        default="tingrc",
    )
    parser.add_argument(
        "--input-file",
        help="read list of relay pairs to measure from file, which contains\
                                              one space-separated pair of fingerprints or ips per line (default none)",
    )
    parser.add_argument(
        "--log-level",
        choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
        default="INFO",
        help="The log level.",
    )
    args = parser.parse_args()

    logger = logging.getLogger()
    logger.setLevel(level=getattr(logging, args.log_level.upper()))

    with ting.echo_server.echo_server():
        ting.ting.main(args)
