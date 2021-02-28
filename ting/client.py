from datetime import datetime
import glob
import json
import os
import os.path
import queue
import time
from typing import ClassVar
import urllib

import socks
from stem.control import Controller
import stem.descriptor.remote
import ting.ting
from ting.circuit import TorCircuit, TingCircuit
from ting.logging import failure, notify, success
from ting.utils import Fingerprint, TingLeg, IPAddress, Port


class TingClient:
    """A class for managing Ting operations."""

    __DEFAULT_CONTROLLER_PORT: ClassVar[Port] = 8008

    def __init__(
        self,
        relay_w_fp: Fingerprint,
        relay_z_fp: Fingerprint,
        local_ip: IPAddress,
        dest_port: Port,
        **kwargs,
    ):
        self.__kwargs = kwargs
        self.destination_port = dest_port
        self.num_samples = kwargs["NumSamples"]
        self.num_repeats = kwargs["NumRepeats"]
        self.source_addr = local_ip
        self.destination_addr = kwargs["DestinationAddr"]
        self.socks_timeout = kwargs["SocksTimeout"]
        self.max_circuit_builds = kwargs["MaxCircuitBuildAttempts"]
        self.w_fp = relay_w_fp
        self.z_fp = relay_z_fp
        self.__parse_relay_list(kwargs["RelayList"], int(kwargs["RelayCacheTime"]))

        self.__setup_job_queue(kwargs["Pair"], kwargs["InputFile"])
        if "ResultDirectory" in kwargs:
            global RESULT_DIRECTORY
            RESULT_DIRECTORY = kwargs["ResultDirectory"]
        self.recently_updated = False
        self.start_time = str(datetime.now())
        self.relay_list = {}
        self.fp_to_ip = {}
        controller_port = kwargs.get("ControllerPort", self.__DEFAULT_CONTROLLER_PORT)
        self.__controller = self.__init_controller(controller_port)

    @classmethod
    def __init_controller(cls, controller_port):
        controller = Controller.from_port(port=controller_port)
        if not controller:
            failure("Couldn't connect to Tor, Controller.from_port failed")
        if not controller.is_authenticated():
            controller.authenticate()
        controller.set_conf("__DisablePredictedCircuits", "1")
        controller.set_conf("__LeaveStreamsUnattached", "1")
        success(f"Controller initialized on port {controller_port}.")
        return controller

    def generate_circuit_templates(
        self, relay1: Fingerprint, relay2: Fingerprint
    ) -> TingCircuit:
        """Generates a TingCircuit which includes each of the three TorCircuits to measure.
        :param relay1 The fingerprint of the first relay to measure.
        :param relay2 The fingerprint of the second relay to measure.

        :return An object holding the three unbuilt circuits.
        """

        x_circ = [self.w_fp, relay1, self.z_fp]
        y_circ = [self.w_fp, relay2, self.z_fp]
        xy_circ = [self.w_fp, relay1, relay2, self.z_fp]

        return TingCircuit(
            TorCircuit(
                self.__controller,
                x_circ,
                TingLeg.X,
                self.destination_addr,
                self.destination_port,
                **self.__kwargs,
            ),
            TorCircuit(
                self.__controller,
                y_circ,
                TingLeg.Y,
                self.destination_addr,
                self.destination_port,
                **self.__kwargs,
            ),
            TorCircuit(
                self.__controller,
                xy_circ,
                TingLeg.XY,
                self.destination_addr,
                self.destination_port,
                **self.__kwargs,
            ),
        )

    def __download_dummy_consensus(self):
        try:
            self.relay_list = {}
            self.fp_to_ip = {}
            for descriptor in stem.descriptor.remote.get_consensus(
                endpoints=(stem.ORPort("127.0.0.1", 5000),)
            ):
                self.fp_to_ip[
                    descriptor.fingerprint.encode("ascii", "ignore")
                ] = "127.0.0.1"
        except Exception as exc:
            print("Unable to retrieve the consensus: %s" % exc)

    def __load_consensus(self, data):
        self.relay_list = {}
        self.fp_to_ip = {}
        for relay in data["relays"]:
            if "or_addresses" in relay:
                ip = relay["or_addresses"][0].split(":")[0]
                self.relay_list[ip] = relay["fingerprint"].encode("ascii", "ignore")
                self.fp_to_ip[relay["fingerprint"].encode("ascii", "ignore")] = ip

    @classmethod
    def __seconds_to_hours(cls, seconds: int) -> float:
        return seconds / 60 / 60

    def __parse_relay_list(self, relay_source, relay_cache_time):
        data = None
        if relay_source.lower() == "internet":
            if os.path.exists("./cache") and len(os.listdir("./cache")) > 0:
                most_recent_list = min(
                    glob.iglob("./cache/*.json"), key=os.path.getctime
                )
                most_recent_time = datetime.strptime(
                    most_recent_list, "./cache/relays-%y-%m-%d-%H.json"
                )
                hours_since_last = self.__seconds_to_hours(
                    (datetime.now() - most_recent_time).seconds
                )
                if hours_since_last <= relay_cache_time:
                    ting.logging.log(
                        "Found list of relays in cache that is "
                        f"{hours_since_last} hours old. Using that..."
                    )
                    with open(most_recent_list) as f:
                        r = f.read()
                        data = json.loads(r)
            if not data:
                ting.logging.log(
                    "Downloading current list of relays.. (this may take a \
                     few seconds)"
                )
                data = json.load(
                    urllib.request.urlopen(
                        "https://onionoo.torproject.org/details?type=relay&\
                         running=true&fields=nickname,fingerprint,or_addresses"
                    )
                )
                new_cache_file = datetime.now().strftime(
                    "./cache/relays-%y-%m-%d-%H.json"
                )
                if not os.path.exists("./cache"):
                    os.mkdir("./cache")
                with open(new_cache_file, "w") as f:
                    f.write(json.dumps(data))
            self.__load_consensus(data)
        elif relay_source.lower() == "test":
            self.__download_dummy_consensus()
        else:
            with open(relay_source) as f:
                r = f.read()
                data = json.loads(r)
                self.__load_consensus(data)

        ting.logging.success(
            "There are {0} currently running Tor nodes.".format(len(self.fp_to_ip))
        )

    def __setup_job_queue(self, pair, input_file):
        self.job_queue = queue.Queue()
        if pair:
            self.job_queue.put(pair)
            print("Ting mode selected : ({0},{1})".format(*pair))
        elif input_file:
            if input_file != "random":
                try:
                    with open(input_file) as f:
                        lines = f.readlines()
                        for config in lines:
                            self.job_queue.put(config.strip().split(" "))
                except IOError:
                    failure(
                        "Could not find specified input file {0}".format(input_file)
                    )
                except Exception:
                    failure("Input file does not follow the specified format")
                print("Collect mode selected : input_file={0}".format(input_file))
            else:
                print("Random mode selected")

    def __get_next_pair(self):
        try:
            return self.job_queue.get(True, 5)
        except queue.Empty:
            return False

    def run(self):

        consecutive_fails = 0

        for pair in iter(lambda: self.__get_next_pair(), ""):
            if pair is False:
                break

            x, y = pair
            result = {}
            result["x"], result["y"] = {}, {}
            print(x)
            print(y)
            if "." in x:
                result["x"]["ip"] = x
                result["x"]["fp"] = self.relay_list[x]
            else:
                result["x"]["fp"] = x
                if x in self.fp_to_ip.keys():
                    result["x"]["ip"] = self.fp_to_ip[x]
                else:
                    result["x"]["ip"] = "0.0.0.0"
            if "." in y:
                result["y"]["ip"] = y
                result["y"]["fp"] = self.relay_list[y]
            else:
                result["y"]["fp"] = y
                if y in self.fp_to_ip.keys():
                    result["y"]["ip"] = self.fp_to_ip[y]
                else:
                    result["y"]["ip"] = "0.0.0.0"
            print(result)

            result["time_start"] = str(datetime.now()).split()[1]
            result["trials"] = []

            ting.logging.log("Measuring new pair: {0}->{1}".format(x, y))

            try:
                for i in range(self.num_repeats):
                    ting.logging.log("Iteration %d" % (i + 1))

                    trial = {}
                    trial["start_time"] = str(datetime.now())
                    circs = self.generate_circuit_templates(
                        result["x"]["fp"], result["y"]["fp"]
                    )

                    for c in circs.all:
                        name = c.leg.value
                        trial[name] = {}
                        ting.logging.log("Tinging " + name)
                        # import pdb; pdb.set_trace()
                        build_time = c.build()
                        trial[name]["build_time"] = build_time

                        start_ting = time.time()
                        ting_results = c.sample(num_samples=1)
                        c.close()
                        trial[name]["ting_time"] = round((time.time() - start_ting), 5)
                        trial[name]["measurements"] = ting_results
                        ting.logging.log(
                            "Ting complete, min for this circuit: %fms"
                            % min(ting_results)
                        )

                    trial["rtt"] = (
                        min(trial["xy"]["measurements"])
                        - (min(trial["x"]["measurements"]) / 2)
                        - (min(trial["y"]["measurements"]) / 2)
                    )
                    ting.logging.success(
                        "Predicted RTT between {0}->{1}: {2}ms".format(
                            x, y, trial["rtt"]
                        )
                    )

                    consecutive_fails = 0

            except Exception as err:
                consecutive_fails += 1
                result["error"] = {}
                result["error"]["type"] = err.__class__.__name__
                result["error"]["details"] = str(err)
                ting.logging.warning(
                    "{0}: {1}".format(err.__class__.__name__, str(err))
                )
                ting.logging.log("Cooling down for five seconds...")
                time.sleep(5)

            if consecutive_fails >= 5:
                msg = f"There have been 5 consecutive failures. The last pair \
                      attempted was {pair}"
                notify("Error", msg)
                consecutive_fails = 0
