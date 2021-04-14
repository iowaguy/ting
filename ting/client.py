"""Ting client definition."""

from datetime import datetime
import glob
import json
import logging
import os
import os.path
from threading import Event, Thread
from typing import Any, ClassVar, Dict, TypeVar, Union
import urllib

from stem.control import Controller
import stem.descriptor.remote

from ting.circuit import TorCircuit, TingCircuit
from ting.echo_server import EchoServer
from ting.exceptions import ConnectionAlreadyExistsException
from ting.logging import failure
from ting.utils import Fingerprint, TingLeg, IPAddress, Port


Client = TypeVar("Client", bound="TingClient")

logger = logging.getLogger(__name__)


class TingClient:  # pylint: disable=too-few-public-methods, too-many-instance-attributes
    """A class for managing Ting operations."""

    __DEFAULT_CONTROLLER_PORT: ClassVar[Port] = 8008
    __DEFAULT_ECHO_SERVER_PORT: ClassVar[Port] = 16667
    __DEFAULT_ECHO_SERVER_IP: ClassVar[IPAddress] = "127.0.0.1"

    def __init__(
        self,
        relay_w_fp: Fingerprint,
        relay_z_fp: Fingerprint,
        local_ip: IPAddress,
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

    def __init_controller(self, controller_port: Port) -> Controller:

        controller = Controller.from_port(port=controller_port)
        if not controller:
            failure("Couldn't connect to Tor, Controller.from_port failed")
        if not controller.is_authenticated():
            controller.authenticate()
        controller.set_conf("__DisablePredictedCircuits", "1")
        controller.set_conf("__LeaveStreamsUnattached", "1")
        logger.info("Controller initialized on port %s.", controller_port)
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
