from datetime import datetime
import glob
import json
import logging
import os
import os.path
import queue
from random import choice
import socket
import time
from typing import List
import urllib

import socks
from stem import (
    OperationFailed,
    InvalidRequest,
    CircuitExtensionFailed,
)
from stem.control import Controller, EventType
import stem.descriptor.remote
import ting.ting
from ting.logging import failure, notify, log
from ting.exceptions import CircuitConnectionException


class TingClient:
    """A class for managing Ting operations."""
    __SOCKS_TYPE = socks.SOCKS5
    __SOCKS_HOST = "127.0.0.1"

    # def generate_circuit_templates(self, relay1, relay2) -> List[TorCircuit]:
    #     """Generates a list of unbuilt TorCircuit objects."""
    #     raise NotImplentedError("not yet..")

    def __init__(self, relay_w_fp, relay_z_fp, local_ip, dest_port, **kwargs):
        self.socks_port = kwargs["SocksPort"]
        self.destination_port = dest_port
        self.num_samples = kwargs["NumSamples"]
        self.num_repeats = kwargs["NumRepeats"]
        self.source_addr = local_ip
        self.destination_addr = kwargs["DestinationAddr"]
        self.socks_timeout = kwargs["SocksTimeout"]
        self.max_circuit_builds = kwargs["MaxCircuitBuildAttempts"]
        self.w_fp = relay_w_fp
        self.z_fp = relay_z_fp
        self.__parse_relay_list(kwargs["RelayList"],
                                int(kwargs["RelayCacheTime"]))
        self.controller = self.__initialize_controller(kwargs["ControllerPort"])
        self.__setup_job_queue(kwargs["Pair"], kwargs["InputFile"])
        if "ResultDirectory" in kwargs:
            global RESULT_DIRECTORY
            RESULT_DIRECTORY = kwargs["ResultDirectory"]
        self.recently_updated = False
        self.daily_pairs = 0
        self.daily_build_errors = 0
        self.daily_socks_errors = 0
        self.start_time = str(datetime.now())
        self.relay_list = {}
        self.fp_to_ip = {}

    def __initialize_controller(self, controller_port):
        controller = Controller.from_port(port=controller_port)
        if not controller:
            failure("Couldn't connect to Tor, Controller.from_port failed")
        if not controller.is_authenticated():
            controller.authenticate()
        controller.set_conf("__DisablePredictedCircuits", "1")
        controller.set_conf("__LeaveStreamsUnattached", "1")

        # Attaches a specific circuit to the given stream (event)
        def attach_stream(event):
            try:
                self.controller.attach_stream(event.id, self.curr_cid)
            except (OperationFailed, InvalidRequest) as e:
                ting.logging.warning(
                    "Failed to attach stream to %s, unknown circuit.\
                         Closing stream..."
                    % self.curr_cid
                )
                print("\tResponse Code: %s " % str(e.code))
                print("\tMessage: %s" % str(e.message))
                self.controller.close_stream(event.id)

        # An event listener, called whenever StreamEvent status changes
        def probe_stream(event):
            if event.status == "DETACHED":
                if hasattr(self, "curr_cid"):
                    ting.logging.warning(
                        f"Stream Detached from circuit {self.curr_cid}..."
                    )
                else:
                    ting.logging.warning("Stream Detached from circuit...")
                print("\t" + str(vars(event)))
            if event.status == "NEW" and event.purpose == "USER":
                attach_stream(event)

        controller.add_event_listener(probe_stream, EventType.STREAM)
        ting.logging.success(
            f"Controller initialized on port {controller_port}. Talking "
            "to Tor on port {self.socks_port}."
        )
        return controller

    # Tell socks to use tor as a proxy
    def __setup_proxy(self):
        sock = socks.socksocket()
        sock.set_proxy(self.__SOCKS_TYPE, self.__SOCKS_HOST, self.socks_port)
        sock.settimeout(self.socks_timeout)
        return sock

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
                self.relay_list[ip] = relay["fingerprint"].encode("ascii",
                                                                  "ignore")
                self.fp_to_ip[relay["fingerprint"].encode("ascii",
                                                          "ignore")] = ip

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
                        "Found list of relays in cache that is {0} hours old. \
                         Using that...".format(
                            hours_since_last
                        )
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
            "There are {0} currently running Tor nodes.".format(
                len(self.fp_to_ip)
            )
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
                        "Could not find specified input file {0}".format(
                            input_file
                        )
                    )
                except Exception:
                    failure("Input file does not follow the specified format")
                print("Collect mode selected : input_file={0}".format(
                    input_file
                ))
            else:
                print("Random mode selected")

    def __get_next_pair(self):
        try:
            return self.job_queue.get(True, 5)
        except queue.Empty:
            return False

    def generate_circuits(self, fingerprints: List[str]):
        """Generate the three circuits of interest for a ting measurement. \
           *fingerprints* is a pair of fingerprints of relays to measure."""
        xy_circ = [self.w_fp, fingerprints[0], fingerprints[1], self.z_fp]
        x_circ = [self.w_fp, fingerprints[0], self.z_fp]
        y_circ = [self.w_fp, fingerprints[1], self.z_fp]
        return ((xy_circ, "xy"), (x_circ, "x"), (y_circ, "y"))

    def __try_daily_update(self):
        if datetime.now().hour == 0 or datetime.now().hour == 12:
            if not self.recently_updated:
                msg = "Yesterday I measured {0} pairs in total. There were {1}\
                       circuit build errors, and {2} circuit connection \
                       errors. The other {3} were successful! I have been \
                       running since {4}.".format(
                    self.daily_pairs,
                    self.daily_build_errors,
                    self.daily_socks_errors,
                    (
                        self.daily_pairs
                        - self.daily_build_errors
                        - self.daily_socks_errors
                    ),
                    self.start_time,
                )
                notify("Daily Update", msg)
                self.recently_updated = True
                self.daily_pairs = 0
                self.daily_build_errors = 0
                self.daily_socks_errors = 0
        else:
            self.recently_updated = False

    def build_circuit(self, circuit: List[str]):
        """Build a Tor circuit. *circuit* is a list of fingerprints from which a Tor circuit will be built."""
        cid, last_exception, failures = None, None, 0

        while failures < self.max_circuit_builds:
            try:
                ting.logging.log("Building circuit...")
                start_build = time.time()
                cid = self.controller.new_circuit(circuit, await_build=True)
                end_build = time.time()
                self.curr_cid = cid
                ting.logging.success("Circuit built successfully.")

                log("Setting up SOCKS proxy...")
                self.tor_sock = self.__setup_proxy()
                log("SOCKS proxy setup complete.")
                
                return cid, round(end_build - start_build, 5)

            except (InvalidRequest, CircuitExtensionFailed) as exc:
                failures += 1
                if "message" in vars(exc):
                    ting.logging.warning("{0}".format(vars(exc)["message"]))
                else:
                    ting.logging.warning(
                        "Circuit failed to be created, reason unknown."
                    )
                if cid is not None:
                    self.controller.close_circuit(cid)
                last_exception = exc

        self.daily_build_errors += 1
        raise last_exception

    # Ping over Tor
    # Return array of times measured
    def ting(self):
        arr, num_seen = [], 0
        msg, done = bytes("!c!", "utf-8"), bytes("!cX", "utf-8")

        try:
            print("\tTrying to connect..")
            self.tor_sock.connect(
                (self.destination_addr, self.destination_port)
            )
            print(
                ting.logging.Color.SUCCESS
                + "\tConnected successfully!"
                + ting.logging.Color.END
            )

            while num_seen < self.num_samples:
                start_time = time.time()
                logging.debug("Tinging. Sample #%s", num_seen+1)
                self.tor_sock.send(msg)
                self.tor_sock.recv(1024)
                end_time = time.time()
                arr.append((end_time - start_time))
                num_seen += 1
                # time.sleep(1)

            logging.debug("Ending ting after %s sample(s)", num_seen)
            self.tor_sock.send(done)
            self._shutdown_socket()

            return [round((x * 1000), 5) for x in arr]

        except socket.error as e:
            ting.logging.warning(
                "Failed to connect using the given circuit: "
                + str(e)
                + "\nClosing connection."
            )
            if self.tor_sock:
                self._shutdown_socket()

            self.daily_socks_errors += 1
            raise CircuitConnectionException(
                "Failed to connect using the given circuit: ", "", str(e)
            )

    def run(self):

        consecutive_fails = 0

        for pair in iter(lambda: self.__get_next_pair(), ""):
            if pair is False:
                break
            self.daily_pairs += 1
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
            pair_fps = (result["x"]["fp"], result["y"]["fp"])

            result["time_start"] = str(datetime.now()).split()[1]
            result["trials"] = []

            ting.logging.log("Measuring new pair: {0}->{1}".format(x, y))

            try:
                for i in range(self.num_repeats):
                    ting.logging.log("Iteration %d" % (i + 1))

                    trial = {}
                    trial["start_time"] = str(datetime.now())
                    circs = self.generate_circuits(pair_fps)

                    for (circ, name) in circs:
                        trial[name] = {}
                        ting.logging.log("Tinging " + name)
                        cid, build_time = self.build_circuit(circ)
                        trial[name]["build_time"] = build_time

                        start_ting = time.time()
                        ting_results = self.ting()
                        trial[name]["ting_time"] = round(
                            (time.time() - start_ting),
                            5
                        )
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
                    result["trials"].append(trial)
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
                msg = (
                    f"There have been 5 consecutive failures. The last pair \
                      attempted was {pair}"
                )
                notify("Error", msg)
                consecutive_fails = 0

            self.__try_daily_update()

        self._shutdown_socket()


    def _shutdown_socket(self):
        try:
            logging.debug("Shutting down Tor socket")
            self.tor_sock.shutdown(socket.SHUT_RDWR)
        except Exception:
            log("There was an issue shutting down Tor, but it probably doesn't matter.")
        self.tor_sock.close()
