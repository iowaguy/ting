"""Ting client definition."""

from datetime import datetime
import glob
import json
import os
import os.path
from threading import Event, Thread
from typing import Any, ClassVar, Dict, TypeVar, Union
import urllib

from stem.control import Controller
import stem.descriptor.remote

import ting
from ting.circuit import TorCircuit, TingCircuit
from ting.echo_server import EchoServer
from ting.exceptions import ConnectionAlreadyExistsException
from ting.logging import failure, success
from ting.utils import Fingerprint, TingLeg, IPAddress, Port


Client = TypeVar("Client", bound="TingClient")


class TingClient:  # pylint: disable=too-few-public-methods, too-many-instance-attributes
    """A class for managing Ting operations."""

    __DEFAULT_CONTROLLER_PORT: ClassVar[Port] = 8008
    __DEFAULT_ECHO_SERVER_PORT: ClassVar[Port] = 16667
    __DEFAULT_ECHO_SERVER_IP: ClassVar[IPAddress] = "127.0.0.1"
    __DEFAULT_RELAY_CACHE_TIME: ClassVar[int] = 24  # hours

    def __init__(
        self,
        relay_w_fp: Fingerprint,
        relay_z_fp: Fingerprint,
        local_ip: IPAddress,
        local_test: bool = False,
        **kwargs: Union[int, str],
    ) -> None:
        self.__kwargs = kwargs
        self.destination_port = int(
            kwargs.get("DestinationPort", self.__DEFAULT_ECHO_SERVER_PORT)
        )

        self.source_addr = local_ip
        self.destination_addr = str(
            kwargs.get("DestinationAddr", self.__DEFAULT_ECHO_SERVER_IP)
        )

        self.w_fp = relay_w_fp
        self.z_fp = relay_z_fp
        relay_cache_time = int(
            kwargs.get("RelayCacheTime", self.__DEFAULT_RELAY_CACHE_TIME)
        )

        self.__parse_relay_list(local_test, relay_cache_time)

        self.relay_list: Dict[IPAddress, Fingerprint]
        self.fp_to_ip: Dict[Fingerprint, IPAddress]
        controller_port = int(
            kwargs.get("ControllerPort", self.__DEFAULT_CONTROLLER_PORT)
        )

        try:
            self.__controller = self.__init_controller(controller_port)
        except ConnectionRefusedError:
            failure(
                "Could not download consensus. Do this machine have a"
                "public, static IP?"
            )

        self.__measurement_event = Event()
        self.__echo_server_thread = Thread(
            target=self.__start_echo_server,
            args=(self.__measurement_event,),
            daemon=True,
        )

    def __exit__(self, exc_type: Exception, exc_value: str, exc_traceback: str) -> None:
        self.__measurement_event.set()
        self.__echo_server_thread.join()

    def __enter__(self: Client) -> Client:
        self.__echo_server_thread.start()
        return self

    @classmethod
    def __start_echo_server(cls, event: Event) -> None:
        echo_server = EchoServer(event)
        if echo_server.is_running():
            raise ConnectionAlreadyExistsException("EchoServer already exists")
        echo_server.run()

    @classmethod
    def __init_controller(cls, controller_port: Port) -> Controller:

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
                self.__measurement_event,
                **self.__kwargs,
            ),
            TorCircuit(
                self.__controller,
                y_circ,
                TingLeg.Y,
                self.destination_addr,
                self.destination_port,
                self.__measurement_event,
                **self.__kwargs,
            ),
            TorCircuit(
                self.__controller,
                xy_circ,
                TingLeg.XY,
                self.destination_addr,
                self.destination_port,
                self.__measurement_event,
                **self.__kwargs,
            ),
        )

    def __download_dummy_consensus(self) -> None:
        self.relay_list = {}
        self.fp_to_ip = {}
        for descriptor in stem.descriptor.remote.get_consensus(
            endpoints=(stem.ORPort("127.0.0.1", 5000),)
        ):
            self.fp_to_ip[
                descriptor.fingerprint.encode("ascii", "ignore")
            ] = "127.0.0.1"

    def __load_consensus(self, data: Dict[str, Any]) -> None:
        self.relay_list = {}
        self.fp_to_ip = {}
        for relay in data["relays"]:
            if "or_addresses" in relay:
                ip_address = relay["or_addresses"][0].split(":")[0]
                self.relay_list[ip_address] = relay["fingerprint"].encode(
                    "ascii", "ignore"
                )
                self.fp_to_ip[
                    relay["fingerprint"].encode("ascii", "ignore")
                ] = ip_address

    @classmethod
    def __seconds_to_hours(cls, seconds: int) -> float:
        return seconds / 3600

    def __parse_relay_list(
        self, test_relays: bool = False, relay_cache_time: int = 24
    ) -> None:
        data = None
        if not test_relays:
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
                    with open(most_recent_list) as file:
                        contents = file.read()
                        data = json.loads(contents)
            if not data:
                ting.logging.log(
                    "Downloading current list of relays.. (this may take a \
                     few seconds)"
                )
                data = json.load(
                    urllib.request.urlopen(  # type: ignore
                        "https://onionoo.torproject.org/details?type=relay&"
                        "running=true&fields=nickname,fingerprint,or_addresses"
                    )
                )
                new_cache_file = datetime.now().strftime(
                    "./cache/relays-%y-%m-%d-%H.json"
                )
                if not os.path.exists("./cache"):
                    os.mkdir("./cache")
                with open(new_cache_file, "w") as file:
                    file.write(json.dumps(data))
            self.__load_consensus(data)
        elif test_relays:
            self.__download_dummy_consensus()

        ting.logging.success(
            "There are {0} currently running Tor nodes.".format(len(self.fp_to_ip))
        )
