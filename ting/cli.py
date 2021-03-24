from datetime import datetime
import logging
import signal
import sys
from ting import ting
from ting.client import TingClient
from ting.logging import failure, log


RESULT_DIRECTORY = "results"


def ting_from_configuration(args):
    try:
        f = open(args.config_file)
    except IOError:
        failure("Couldn't find a tingrc config file. Try running ./configure.sh")
    log("Read config file " + args.config_file)
    r = f.readlines()
    f.close()

    config = {}
    for l in r:
        pair = l.strip().split()

        try:
            config[pair[0]] = int(pair[1])
        except ValueError:
            config[pair[0]] = pair[1]
    if "InputFile" not in config:
        config["InputFile"] = None

    arg_overrides = [
        (args.num_repeats, "NumRepeats"),
        (args.num_samples, "NumSamples"),
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

    ########## CONFIG END ##########

    def catch_sigint(signal, frame):
        sys.exit(0)

    signal.signal(
        signal.SIGINT, catch_sigint
    )  # Still write output even if process killed

    local_test = config["RelayList"] == "test"
    results = ting(
        [(args.relay1, args.relay2)],
        config["W"],
        config["Z"],
        config["SourceAddr"],
        num_samples=10,
        local_test=local_test,
    )
    print(results)
