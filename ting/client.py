"""Ting client definition."""

import logging
from threading import Thread, Event
from typing import ClassVar, TypeVar, Union

from stem.control import Controller

from ting.circuit import TorCircuit, TingCircuit
from ting.echo_server import EchoServer
from ting.exceptions import ConnectionAlreadyExistsException
from ting.logging import failure
from ting.utils import Fingerprint, TingLeg, IPAddress, Port, Endpoint


Client = TypeVar("Client", bound="TingClient")

logger = logging.getLogger(__name__)


class TingClient:  # pylint: disable=too-few-public-methods, too-many-instance-attributes
    """A class for managing Ting operations."""

    __DEFAULT_CONTROLLER_PORT: ClassVar[Port] = 8008

    def __init__(
        self,
        relay_w_fp: Fingerprint,
        relay_z_fp: Fingerprint,
        local_ip: IPAddress,
        echo_server: Endpoint,
        **kwargs: Union[int, str],
    ) -> None:
        self.__kwargs = kwargs
        self.echo_server = echo_server

        self.source_addr = local_ip

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
                self.echo_server,
                **self.__kwargs,
            ),
            TorCircuit(
                self.__controller,
                y_circ,
                TingLeg.Y,
                self.echo_server,
                **self.__kwargs,
            ),
            TorCircuit(
                self.__controller,
                xy_circ,
                TingLeg.XY,
                self.echo_server,
                **self.__kwargs,
            ),
        )
