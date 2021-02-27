from datetime import datetime
import json
import logging
import signal
import sys
from ting.client import TingClient
from ting.logging import failure, log


RESULT_DIRECTORY = "results"


def get_current_log():
    return RESULT_DIRECTORY + "/" + str(datetime.now()).split()[0] + ".json"


def main(args):

    logging.basicConfig(level=getattr(logging, args.log_level.upper()))
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
    if not "InputFile" in config:
        config["InputFile"] = None

    arg_overrides = [
        (args.num_repeats, "NumRepeats"),
        (args.num_samples, "NumSamples"),
        (args.dest_port, "DestinationPort"),
        (args.input_file, "InputFile"),
        (args.output_file, "ResultsDirectory"),
    ]

    for override in arg_overrides:
        if not override[0] is None:
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

    client = TingClient(
        config["W"],
        config["Z"],
        config["SourceAddr"],
        config["DestinationPort"],
        **config
    )
    client.generate_circuit_templates(
        "873610A50D6AC4A7D2BA0A0D5BEDFDB039C66A15",
        "C70CDB4796D64EA085B014A5A20B7DE159EF2111",
    )
    client.run()
