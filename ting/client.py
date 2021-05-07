"""Ting client definition."""

import logging
import textwrap
from threading import Thread, Event
from typing import ClassVar, TypeVar, Union, Optional

from stem.control import Controller

from ting.circuit import TorCircuit, TingCircuit
from ting.echo_server import EchoServer
from ting.exceptions import ConnectionAlreadyExistsException
from ting.logging import failure
from ting.utils import Fingerprint, TingLeg, IPAddress, Port, Endpoint


Client = TypeVar("Client", bound="TingClient")

logger = logging.getLogger(__name__)

_DEFAULT_CONTROLLER_PORT = 8008


def init_controller(controller_port: Optional[Port] = None) -> Controller:
    if not controller_port:
        controller_port = _DEFAULT_CONTROLLER_PORT
    controller = Controller.from_port(port=controller_port)
    if not controller:
        failure("Couldn't connect to Tor, Controller.from_port failed")
    if not controller.is_authenticated():
        controller.authenticate()
    controller.set_conf("__DisablePredictedCircuits", "1")
    controller.set_conf("__LeaveStreamsUnattached", "1")
    logger.info("Controller initialized on port %s.", controller_port)
    return controller


class TingClient:  # pylint: disable=too-few-public-methods, too-many-instance-attributes
    """A class for managing Ting operations."""

    def __init__(
        self,
        relay_w_fp: Fingerprint,
        relay_z_fp: Fingerprint,
        echo_server: Endpoint,
        controller: Controller,
        **kwargs: Union[int, str],
    ) -> None:
        self.__kwargs = kwargs
        self.echo_server = echo_server
        self.w_fp = relay_w_fp
        self.z_fp = relay_z_fp
        self.__controller = controller

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

    def __str__(self) -> str:
        return textwrap.dedent(
            f"""\
           TingClient(
               w_fp={self.w_fp},
               z_fp={self.z_fp},
               echo_server={self.echo_server},
           )"""
        )
