"""A module for Tor circuit operations"""

import logging
import socket
import time
from threading import Event
from typing import Any, Callable, ClassVar, List, Tuple, TypeVar, Union

from stem import (
    OperationFailed,
    InvalidRequest,
    CircuitExtensionFailed,
)
from stem.control import Controller, EventType

import socks

from ting.exceptions import (
    CircuitConnectionException,
    ConnectionAlreadyExistsException,
    TorShutdownException,
)
from ting.logging import Color
import ting.timer_pb2
from ting.utils import Fingerprint, TingLeg, Port, IPAddress

TC = TypeVar("TC", bound="TorCircuit")


class TorCircuit:  # pylint: disable=too-many-instance-attributes
    """A class for building and interacting with Tor circuits."""

    __DEFAULT_MAX_BUILD_ATTEMPTS: ClassVar[int] = 5
    __DEFAULT_SOCKS_PORT: ClassVar[Port] = 9008
    __DEFAULT_SOCKS_TIMEOUT_SEC: ClassVar[Port] = 60
    __SOCKS_TYPE = socks.SOCKS5
    __SOCKS_HOST: ClassVar[IPAddress] = "127.0.0.1"

    def __init__(  # pylint: disable=too-many-arguments
        self,
        controller: Controller,
        relays: List[Fingerprint],
        leg: TingLeg,
        dest_ip: IPAddress,
        dest_port: Port,
        event: Event,
        **kwargs: Union[int, str],
    ) -> None:
        """
                :param controller This is a
        -        [stem controller][https://stem.torproject.org/api/control.html] object.
                :param relays This is a list of fingerprints of relays to connect to.
        """
        self.__logger = logging.getLogger(__name__)
        self.__relays = relays
        self.__ting_leg = leg
        self.__tor_sock: socket.socket = socket.socket()
        self.__circuit_id: int
        self.__dest_ip = dest_ip
        self.__dest_port = dest_port

        self.__max_circuit_build_attempts = int(
            kwargs.get("MaxCircuitBuildAttempts", self.__DEFAULT_MAX_BUILD_ATTEMPTS)
        )
        self.__socks_port = int(kwargs.get("SocksPort", self.__DEFAULT_SOCKS_PORT))
        self.__socks_timeout = int(
            kwargs.get("SocksTimeout", self.__DEFAULT_SOCKS_TIMEOUT_SEC)
        )
        self.__controller = controller
        self.__probe: Callable[[Any], Any]
        self.__build_time: float = 0.0
        self.__event = event

    def __exit__(self, exc_type: Exception, exc_value: str, exc_traceback: str) -> None:
        self.close()

    def __enter__(self: TC) -> TC:
        return self.build()

    def build(self: TC) -> TC:
        """Build the circuit.

        :return Time to build the circuit in milliseconds."""
        cid, failures = None, 0

        last_exception: Exception
        while failures < self.__max_circuit_build_attempts:
            try:
                self.__logger.info("Building circuit...")
                start_build = time.time()
                cid = self.__controller.new_circuit(self.relays, await_build=True)
                self.__circuit_id = cid
                end_build = time.time()
                self.__logger.info("Circuit built successfully.")

                self.__logger.info("Configuring event listener...")
                self.__configure_listeners(cid)
                self.__logger.info("Event listener setup is complete.")
                self.__logger.info("Setting up SOCKS proxy...")
                self.__tor_sock = self.__setup_proxy()
                self.__logger.info("SOCKS proxy setup complete.")

                self.__build_time = round(end_build - start_build, 5)
                self.__connect_to_dest(self.__dest_ip, self.__dest_port)
                return self

            except (InvalidRequest, CircuitExtensionFailed) as exc:
                failures += 1
                if "message" in vars(exc):
                    self.__logger.warning("%s", vars(exc)["message"])
                else:
                    self.__logger.warning("Failed to create circuit, reason unknown.")
                if self.__circuit_id is not None:
                    self.__controller.close_circuit(cid)
                last_exception = exc

        raise last_exception

    def __configure_listeners(self, circuit_id: int) -> None:
        # Attaches a specific circuit to the given stream (event)
        def attach_stream(event: EventType) -> None:
            try:
                self.__controller.attach_stream(event.id, circuit_id)
            except (OperationFailed, InvalidRequest) as exc:
                self.__logger.warning(
                    "Failed to attach stream to %s, unknown circuit."
                    "Closing stream...",
                    circuit_id,
                )
                self.__logger.info("\tResponse Code: %s ", str(exc.code))
                self.__logger.info("\tMessage: %s", str(exc.message))
                self.__controller.close_stream(event.id)

        # An event listener, called whenever StreamEvent status changes
        def probe_stream(event: EventType) -> None:
            if event.status == "DETACHED":
                if circuit_id:
                    self.__logger.warning(
                        "Stream Detached from circuit %s...", circuit_id
                    )
                else:
                    self.__logger.warning("Stream Detached from circuit...")
                self.__logger.info("\t%s", str(vars(event)))
            if event.status == "NEW" and event.purpose == "USER":
                attach_stream(event)

        self.__probe = probe_stream
        self.__controller.add_event_listener(
            probe_stream, EventType.STREAM  # pylint: disable=no-member
        )

    def __connect_to_dest(self, dest_ip: IPAddress, dest_port: Port) -> None:
        try:
            self.__logger.info("\tTrying to connect to endpoint..")

            self.__tor_sock.connect((dest_ip, dest_port))
            self.__logger.info(  # pylint: disable=logging-not-lazy
                Color.SUCCESS + "\tConnected to endpoint successfully!" + Color.END
            )
        except socket.error as exc:
            self.__logger.warning(
                "Failed to connect to the endpoint using the given circuit: %s"
                "\nClosing connection.",
                str(exc),
            )
            if self.__tor_sock:
                raise ConnectionAlreadyExistsException(
                    "This socket is already connected", exc
                ) from exc

            raise CircuitConnectionException(
                "Failed to connect using the given circuit: ", "", exc
            ) from exc

    # Tell socks to use tor as a proxy
    def __setup_proxy(self) -> socket.socket:
        sock = socks.socksocket()
        sock.set_proxy(self.__SOCKS_TYPE, self.__SOCKS_HOST, self.__socks_port)
        sock.settimeout(self.__socks_timeout)
        return sock

    def sample(self) -> Tuple[float, float]:
        """Take a Ting measurement on this circuit. Results in seconds.
        :param num_samples The number of measurements to take. Defaults to 1."""

        try:
            timer = ting.timer_pb2.Ting()
            timer.ptype = ting.timer_pb2.Ting.Packet.TING
            msg = timer.SerializeToString()
            start_time = time.time()
            self.__tor_sock.send(msg)
            self.__logger.debug("Sending %s", msg)

            timer.Clear()
            data = self.__tor_sock.recv(1024)
            stop_time = time.time()
            timer.ParseFromString(data)
            outgoing_time = timer.time_sec - start_time
            incoming_time = stop_time - timer.time_sec
            return (outgoing_time, incoming_time)
        except socket.error as exc:
            self.__logger.warning(
                "Failed to connect using the given circuit: %s" "\nClosing connection.",
                str(exc),
            )
            if self.__tor_sock:
                self.close()

            raise CircuitConnectionException(
                "Failed to connect using the given circuit: ", "", exc
            ) from exc

    def close(self) -> None:
        """Close the Tor socket."""
        try:
            timer = ting.timer_pb2.Ting()
            timer.ptype = ting.timer_pb2.Ting.Packet.CLOSE

            # Tell echo server that this connection is over
            self.__tor_sock.send(timer.SerializeToString())

            self.__logger.debug("Tearing down Tor circuit.")
            self.__controller.close_circuit(self.__circuit_id)
            self.__controller.remove_event_listener(self.__probe)
            self.__controller = None

            self.__logger.debug("Shutting down Tor socket")
            self.__tor_sock.shutdown(socket.SHUT_RDWR)
        except TorShutdownException:
            self.__logger.info(
                "There was an issue shutting down Tor, but it probably doesn't matter."
            )
        self.__tor_sock.close()

    @property
    def leg(self) -> TingLeg:
        """Getter method for the Ting circuit leg."""
        return self.__ting_leg

    @property
    def relays(self) -> List[Fingerprint]:
        """Getter method for the relays in the circuit."""
        return self.__relays

    @property
    def circuit_id(self) -> int:
        """Get the circuit ID. If circuit has not been built, returns None."""
        return self.__circuit_id

    @property
    def circuit_build_time(self) -> float:
        """Returns the time taken to build the circuit. None if circuit has not
        been built yet."""
        return self.__build_time


class TingCircuit:
    """Holds results for Tor circuit creation."""

    def __init__(self, x: TorCircuit, y: TorCircuit, xy: TorCircuit):
        self.__x_circ = x
        self.__y_circ = y
        self.__xy_circ = xy

    @property
    def x_circ(self) -> TorCircuit:
        """Getter method for circuit x."""
        return self.__x_circ

    @property
    def y_circ(self) -> TorCircuit:
        """Getter method for circuit y."""
        return self.__y_circ

    @property
    def xy_circ(self) -> TorCircuit:
        """Getter method for circuit xy."""
        return self.__xy_circ

    @property
    def all(self) -> Tuple[TorCircuit, TorCircuit, TorCircuit]:
        """Returns all legs of the Tor measurement."""
        return (self.__x_circ, self.__y_circ, self.__xy_circ)
