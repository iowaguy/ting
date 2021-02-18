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
import urllib

import socks
from stem import (
    CircStatus,
    OperationFailed,
    InvalidRequest,
    InvalidArguments,
    CircuitExtensionFailed,
)
from stem.control import Controller, EventType
import stem.descriptor.remote
import ting.ting
from ting.logging import success, notify, failure
from ting.exceptions import NotReachableException, CircuitConnectionException

SOCKS_TYPE = socks.SOCKS5
SOCKS_HOST = "127.0.0.1"


class TingClient:
    def __init__(self, config, result_queue, flush_to_file):
        self.config = config
        self.controller_port = config["ControllerPort"]
        self.socks_port = config["SocksPort"]
        self.destination_port = config["DestinationPort"]
        self.num_samples = config["NumSamples"]
        self.num_repeats = config["NumRepeats"]
        self.source_addr = config["SourceAddr"]
        self.destination_addr = config["DestinationAddr"]
        self.socks_timeout = config["SocksTimeout"]
        self.max_circuit_builds = config["MaxCircuitBuildAttempts"]
        self.w_addr, self.w_fp = config["W"].split(",")
        self.z_addr, self.z_fp = config["Z"].split(",")
        self.result_queue = result_queue
        self.flush_to_file = flush_to_file
        self.parse_relay_list(config["RelayList"], int(config["RelayCacheTime"]))
        self.controller = self.initialize_controller()
        ting.logging.success(
            f"Controller initialized on port {self.controller_port}. \
                  Talking to Tor on port {self.socks_port}."
        )
        self.setup_job_queue(config["Pair"], config["InputFile"])
        if "ResultDirectory" in config:
            global RESULT_DIRECTORY
            RESULT_DIRECTORY = config["ResultDirectory"]
        self.recently_updated = False
        self.daily_pairs, self.daily_build_errors, self.daily_socks_errors = 0, 0, 0
        self.start_time = str(datetime.now())

    def initialize_controller(self):
        controller = Controller.from_port(port=self.controller_port)
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
        return controller

    # Tell socks to use tor as a proxy
    def setup_proxy(self):
        s = socks.socksocket()
        s.set_proxy(SOCKS_TYPE, SOCKS_HOST, self.socks_port)
        s.settimeout(self.socks_timeout)
        return s

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

    def parse_relay_list(self, relay_source, relay_cache_time):
        data = None
        if relay_source.lower() == "internet":
            if os.path.exists("./cache") and len(os.listdir("./cache")) > 0:
                most_recent_list = min(
                    glob.iglob("./cache/*.json"), key=os.path.getctime
                )
                most_recent_time = datetime.strptime(
                    most_recent_list, "./cache/relays-%y-%m-%d-%H.json"
                )
                hours_since_last = (datetime.now() - most_recent_time).seconds / 60 / 60
                if hours_since_last <= relay_cache_time:
                    ting.logging.log(
                        "Found list of relays in cache that is {0} hours old. Using that...".format(
                            hours_since_last
                        )
                    )
                    with open(most_recent_list) as f:
                        r = f.read()
                        data = json.loads(r)
            if not data:
                ting.logging.log(
                    "Downloading current list of relays.. (this may take a few seconds)"
                )
                data = json.load(
                    urllib.request.urlopen(
                        "https://onionoo.torproject.org/details?type=relay&running=true&fields=nickname,fingerprint,or_addresses"
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

    def setup_job_queue(self, pair, input_file):
        self.job_queue = queue.Queue()
        if pair:
            self.job_queue.put(pair)
            print("Ting mode selected : ({0},{1})".format(*pair))
        elif input_file:
            if input_file != "random":
                try:
                    with open(input_file) as f:
                        r = f.readlines()
                        for l in r:
                            self.job_queue.put(l.strip().split(" "))
                except IOError:
                    failure(
                        "Could not find specified input file {0}".format(input_file)
                    )
                except:
                    failure("Input file does not follow the specified format")
                print("Collect mode selected : input_file={0}".format(input_file))
            else:
                print("Random mode selected")

    def get_next_pair(self):
        if self.config["InputFile"] == "random":
            x, y = choice(self.relay_list.keys()), choice(self.relay_list.keys())

            while x == y:
                y = choice(self.relay_list.keys())
            return (x, y)
        else:

            try:
                return self.job_queue.get(True, 5)
            except queue.Empty:
                return False

    def generate_circuits(self, fps):
        xy_circ = [self.w_fp, fps[0], fps[1], self.z_fp]
        x_circ = [self.w_fp, fps[0], self.z_fp]
        y_circ = [self.w_fp, fps[1], self.z_fp]
        return ((xy_circ, "xy"), (x_circ, "x"), (y_circ, "y"))

    def try_daily_update(self):
        if datetime.now().hour == 0 or datetime.now().hour == 12:
            if not self.recently_updated:
                msg = "Yesterday I measured {0} pairs in total. There were {1} circuit build errors,\
                       and {2} circuit connection errors. The other {3} were successful! I have been\
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
                self.daily_pairs, self.daily_build_errors, self.daily_socks_errors = (
                    0,
                    0,
                    0,
                )
        else:
            self.recently_updated = False

    def build_circuits(self, circ):
        cid, last_exception, failures = None, None, 0

        while failures < self.max_circuit_builds:
            try:
                ting.logging.log("Building circuit...")
                cid = self.controller.new_circuit(circ, await_build=True)
                ting.logging.success("Circuit built successfully.")
                return cid

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
    def ting(self, name):
        arr, num_seen = [], 0
        msg, done = bytes("!c!", "utf-8"), bytes("!cX", "utf-8")

        try:
            print("\tTrying to connect..")
            self.tor_sock.connect((self.destination_addr, self.destination_port))
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
                "Failed to connect using the given circuit: ", name, str(e)
            )

    def run(self):

        consecutive_fails = 0

        for pair in iter(lambda: self.get_next_pair(), ""):
            if pair == False:
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
            pair_ips = (result["x"]["ip"], result["y"]["ip"])

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
                        start_build = time.time()
                        cid = self.build_circuits(circ)
                        self.curr_cid = cid
                        trial[name]["build_time"] = round(
                            (time.time() - start_build), 5
                        )

                        self.tor_sock = self.setup_proxy()

                        start_ting = time.time()
                        ting_results = self.ting(name)
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
                    "There have been 5 consecutive failures. The last pair attempted was "
                    + str(pair)
                )
                notify("Error", msg)
                consecutive_fails = 0

            self.result_queue.put(result, False)
            self.flush_to_file()
            self.try_daily_update()

        self._shutdown_socket()


    def _shutdown_socket(self):
        try:
            logging.debug("Shutting down Tor socket")
            self.tor_sock.shutdown(socket.SHUT_RDWR)
        except:
            pass
        self.tor_sock.close()
