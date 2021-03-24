"""A module for Tor circuit operations"""

import logging
import socket
import time
from typing import Any, Callable, ClassVar, List, Tuple, TypeVar

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
from ting.logging import log, success, warning, Color
from ting.utils import Fingerprint, TingLeg, Port, IPAddress

T = TypeVar('T', bound='TorCircuit')

class TorCircuit:
    """A class for building and interacting with Tor circuits."""

    __DEFAULT_MAX_BUILD_ATTEMPTS: ClassVar[int] = 5
    __DEFAULT_SOCKS_PORT: ClassVar[Port] = 9008
    __DEFAULT_SOCKS_TIMEOUT_SEC: ClassVar[Port] = 60
    __SOCKS_TYPE = socks.SOCKS5
    __SOCKS_HOST: ClassVar[IPAddress] = "127.0.0.1"

    def __init__(
        self,
        controller: Controller,
        relays: List[Fingerprint],
        leg: TingLeg,
        dest_ip: IPAddress,
        dest_port: Port,
        **kwargs: int,
    ) -> None:
        """
        :param controller This is a
-        [stem controller][https://stem.torproject.org/api/control.html] object.
        :param relays This is a list of fingerprints of relays to connect to.
        """
        self.__relays = relays
        self.__ting_leg = leg
        self.__tor_sock: socket.socket = socket.socket()
        self.__circuit_id = None
        self.__dest_ip = dest_ip
        self.__dest_port = dest_port

        self.__max_circuit_build_attempts = kwargs.get(
            "MaxCircuitBuildAttempts", self.__DEFAULT_MAX_BUILD_ATTEMPTS
        )
        self.__socks_port = kwargs.get("SocksPort", self.__DEFAULT_SOCKS_PORT)
        self.__socks_timeout = kwargs.get(
            "SocksTimeout", self.__DEFAULT_SOCKS_TIMEOUT_SEC
        )
        self.__controller = controller
        self.__probe: Callable[[Any], Any] = None
        self.__build_time: float = 0.0

    def __exit__(self, exc_type: Exception, exc_value: str, exc_traceback: str) -> None:
        self.close()

    def __enter__(self) -> T:
        return self.build()

    def build(self) -> T:
        """Build the circuit.

        :return Time to build the circuit in milliseconds."""
        cid, last_exception, failures = None, None, 0

        while failures < self.__max_circuit_build_attempts:
            try:
                log("Building circuit...")
                start_build = time.time()
                cid = self.__controller.new_circuit(self.relays, await_build=True)
                self.__circuit_id = cid
                end_build = time.time()
                success("Circuit built successfully.")

                log("Configuring event listener...")
                self.__configure_listeners(cid)
                log("Event listener setup is complete.")
                log("Setting up SOCKS proxy...")
                self.__tor_sock = self.__setup_proxy()
                log("SOCKS proxy setup complete.")

                self.__build_time = round(end_build - start_build, 5)
                self.__connect_to_dest(self.__dest_ip, self.__dest_port)
                return self

            except (InvalidRequest, CircuitExtensionFailed) as exc:
                failures += 1
                if "message" in vars(exc):
                    warning("{0}".format(vars(exc)["message"]))
                else:
                    warning("Failed to create circuit, reason unknown.")
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
                warning(
                    f"Failed to attach stream to {circuit_id}, unknown circuit."
                    "Closing stream..."
                )
                log("\tResponse Code: %s " % str(exc.code))
                log("\tMessage: %s" % str(exc.message))
                self.__controller.close_stream(event.id)

        # An event listener, called whenever StreamEvent status changes
        def probe_stream(event: EventType) -> None:
            if event.status == "DETACHED":
                if circuit_id:
                    warning(f"Stream Detached from circuit {circuit_id}...")
                else:
                    warning("Stream Detached from circuit...")
                log("\t" + str(vars(event)))
            if event.status == "NEW" and event.purpose == "USER":
                attach_stream(event)

        self.__probe = probe_stream
        self.__controller.add_event_listener(probe_stream, EventType.STREAM)

    def __connect_to_dest(self, dest_ip: IPAddress, dest_port: Port) -> None:
        try:
            log("\tTrying to connect to endpoint..")

            self.__tor_sock.connect((dest_ip, dest_port))
            log(Color.SUCCESS + "\tConnected to endpoint successfully!" + Color.END)
        except socket.error as exc:
            warning(
                "Failed to connect to the endpoint using the given circuit: "
                + str(exc)
                + "\nClosing connection."
            )
            if self.__tor_sock:
                raise ConnectionAlreadyExistsException(
                    "This socket is already connected", exc
                )

            raise CircuitConnectionException(
                "Failed to connect using the given circuit: ", "", exc
            )

    # Tell socks to use tor as a proxy
    def __setup_proxy(self) -> socket.socket:
        sock = socks.socksocket()
        sock.set_proxy(self.__SOCKS_TYPE, self.__SOCKS_HOST, self.__socks_port)
        sock.settimeout(self.__socks_timeout)
        return sock

    def sample(self, num_samples=1) -> float:
        """Take a Ting measurement on this circuit. Results in seconds.
        :param num_samples The number of measurements to take. Defaults to 1."""
        arr, num_seen = [], 0

        try:
            while num_seen < num_samples:
                logging.debug("Tinging. Sample %d", num_seen + 1)
                start_time = time.time()
                self.__tor_sock.send(bytes("!c!", "utf-8"))
                self.__tor_sock.recv(1024)
                end_time = time.time()
                arr.append((end_time - start_time))
                num_seen += 1
                # time.sleep(1)

            logging.debug("Ending ting after %d sample(s)", num_seen)

            if len(arr) == 1:
                return arr[0]

            return arr

        except socket.error as exc:
            warning(
                "Failed to connect using the given circuit: "
                + str(exc)
                + "\nClosing connection."
            )
            if self.__tor_sock:
                self.close()

            raise CircuitConnectionException(
                "Failed to connect using the given circuit: ", "", str(exc)
            )

    def close(self):
        """Close the Tor socket."""
        try:
            # Tell echo server that this connection is over
            self.__tor_sock.send(bytes("!cX", "utf-8"))

            logging.debug("Tearing down Tor circuit.")
            self.__controller.close_circuit(self.__circuit_id)
            self.__controller.remove_event_listener(self.__probe)
            self.__controller = None

            logging.debug("Shutting down Tor socket")
            self.__tor_sock.shutdown(socket.SHUT_RDWR)
        except TorShutdownException:
            log("There was an issue shutting down Tor, but it probably doesn't matter.")
        self.__tor_sock.close()

    @property
    def leg(self):
        """Getter method for the Ting circuit leg."""
        return self.__ting_leg

    @property
    def relays(self):
        """Getter method for the relays in the circuit."""
        return self.__relays

    @property
    def circuit_id(self):
        """Get the circuit ID. If circuit has not been built, returns None."""
        return self.__circuit_id

    @property
    def circuit_build_time(self):
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
    def all(self) -> Tuple[TorCircuit]:
        """Returns all legs of the Tor measurement."""
        return (self.__x_circ, self.__y_circ, self.__xy_circ)
