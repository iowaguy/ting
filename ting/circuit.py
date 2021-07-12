"""A module for Tor circuit operations"""

import contextlib
import datetime
import logging
import socket
import time
import textwrap
from typing import (
    Any,
    Callable,
    ClassVar,
    List,
    Tuple,
    TypeVar,
    Union,
    Optional,
    Iterator,
)

import stem
from stem import OperationFailed, InvalidRequest, CircuitExtensionFailed, StreamStatus
from stem.control import Controller, EventType
from stem.response.events import StreamEvent

import socks

from ting.exceptions import (
    CircuitConnectionException,
    ConnectionAlreadyExistsException,
    TorShutdownException,
)
from ting.logging import Color
import ting.timer_pb2
from ting.utils import Fingerprint, TingLeg, Port, IPAddress, Endpoint

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
        dest: Endpoint,
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
        self.__circuit_id: Optional[int] = None
        self.__dest = dest

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

    @contextlib.contextmanager
    def build(self) -> Any:
        """Build the circuit."""
        cid, failures = None, 0

        last_exception: Exception
        while failures < self.__max_circuit_build_attempts:
            if failures > 0:
                time.sleep(1)
            try:
                self.__logger.info("Building circuit...")
                start_build = time.time()
                self.__controller.set_conf("__LeaveStreamsUnattached", "1")
                cid = self.__controller.new_circuit(self.relays, await_build=True)
                self.__circuit_id = cid
                end_build = time.time()
                self.__build_time = round(end_build - start_build, 5)
                self.__logger.info("Circuit built successfully.")

                self.__logger.info("Configuring event listener...")
                self.__configure_listeners(cid)
                self.__logger.info("Event listener setup is complete.")
                self.__logger.info("Setting up SOCKS proxy...")
                with self.__setup_proxy() as tor_sock:
                    self.__logger.info("SOCKS proxy setup complete.")
                    self.__connect_to_dest(tor_sock)
                    yield lambda: self.sample(tor_sock)

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
        def attach_stream(event: StreamEvent) -> None:
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
        def probe_stream(event: StreamEvent) -> None:
            if event.target_port != self.__dest.port:
                # Not our stream; not our problem.
                return
            if event.status == StreamStatus.DETACHED and event.circ_id == circuit_id:
                self.__logger.warning("Stream Detached from circuit %s...", circuit_id)
                self.__logger.info("\t%s", str(vars(event)))
                return
            if event.status == "NEW" and event.purpose == "USER":
                self.__logger.info("Found our stream; attaching!")
                attach_stream(event)

        self.__probe = probe_stream
        self.__controller.add_event_listener(
            probe_stream, EventType.STREAM  # pylint: disable=no-member
        )

    def __connect_to_dest(self, tor_sock: socket.socket) -> None:
        try:
            self.__logger.info("\tTrying to connect to endpoint..")

            tor_sock.connect((self.__dest.host, self.__dest.port))
            self.__logger.info(  # pylint: disable=logging-not-lazy
                Color.SUCCESS + "\tConnected to endpoint successfully!" + Color.END
            )
        except socket.error as exc:
            self.__logger.exception(
                "Failed to connect to the endpoint using the given circuit."
                "\nClosing connection.",
            )
            raise CircuitConnectionException(
                "Failed to connect using the given circuit: ", "", exc
            ) from exc

    # Tell socks to use tor as a proxy
    def __setup_proxy(self) -> socket.socket:
        sock = socks.socksocket()
        # random password makes Tor give us a new "stream"
        password = str(hash(self)) + str(hash(datetime.datetime.now()))
        sock.set_proxy(
            self.__SOCKS_TYPE,
            self.__SOCKS_HOST,
            self.__socks_port,
            username="user",
            password=password,
        )
        sock.settimeout(self.__socks_timeout)
        return sock

    def sample(self, tor_sock: socket.socket) -> Tuple[float, float]:
        """Take a Ting measurement on this circuit. Results in seconds.
        :param num_samples The number of measurements to take. Defaults to 1."""

        try:
            timer = ting.timer_pb2.Ting()
            timer.ptype = ting.timer_pb2.Ting.Packet.TING
            msg = timer.SerializeToString()
            start_time = time.time()
            tor_sock.send(msg)
            self.__logger.debug("Sending %s", msg)

            timer.Clear()
            data = tor_sock.recv(1024)
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

            raise CircuitConnectionException(
                "Failed to connect using the given circuit: ", "", exc
            ) from exc

    def close(self, tor_sock: socket.socket) -> None:
        """Close the Tor socket."""
        try:
            timer = ting.timer_pb2.Ting()
            timer.ptype = ting.timer_pb2.Ting.Packet.CLOSE

            # Tell echo server that this connection is over
            tor_sock.send(timer.SerializeToString())

            self.__logger.debug("Tearing down Tor circuit.")
            try:
                self.__controller.close_circuit(self.__circuit_id)
            finally:
                self.__controller.remove_event_listener(self.__probe)
            self.__controller = None
        except TorShutdownException:
            self.__logger.info(
                "There was an issue shutting down Tor, but it probably doesn't matter."
            )

    @property
    def leg(self) -> TingLeg:
        """Getter method for the Ting circuit leg."""
        return self.__ting_leg

    @property
    def relays(self) -> List[Fingerprint]:
        """Getter method for the relays in the circuit."""
        return self.__relays

    @property
    def circuit_id(self) -> Optional[int]:
        """Get the circuit ID. If circuit has not been built, returns None."""
        return self.__circuit_id

    @property
    def circuit_build_time(self) -> float:
        """Returns the time taken to build the circuit. None if circuit has not
        been built yet."""
        return self.__build_time

    def __str__(self) -> str:
        return f"TorCircuit(relays={self.__relays}, leg={self.__ting_leg}, dest={self.__dest})"


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

    def __iter__(self) -> Iterator[TorCircuit]:
        """Returns all legs of the Tor measurement."""
        return iter((self.__x_circ, self.__y_circ, self.__xy_circ))

    def __str__(self) -> str:
        return textwrap.dedent(
            f"""\
          TingCircuit(
              x ={self.__x_circ},
              y ={self.__y_circ},
              xy={self.__xy_circ}"
          )"""
        )
