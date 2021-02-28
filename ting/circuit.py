"""A module for Tor circuit operations"""

import logging
import socket
import time
from typing import List, ClassVar

import socks
from stem import (
    OperationFailed,
    InvalidRequest,
    CircuitExtensionFailed,
)
from stem.control import Controller

from ting.logging import log, success, warning
from ting.utils import Fingerprint, TingLeg, Port, IPAddress


class TorCircuit:
    """A class for building and interacting with Tor circuits."""
    __DEFAULT_MAX_BUILD_ATTEMPTS: ClassVar[int] = 5
    __DEFAULT_SOCKS_PORT: ClassVar[Port] = 9008
    __DEFAULT_SOCKS_TIMEOUT_SEC: ClassVar[Port] = 60
    __SOCKS_TYPE = socks.SOCKS5
    __SOCKS_HOST: ClassVar[IPAddress] = "127.0.0.1"

    def __init__(self, controller: Controller, relays: List[Fingerprint],
                 leg: TingLeg, **kwargs):
        """:param controller This is a
        [stem controller][https://stem.torproject.org/api/control.html] object.
        :param relays This is a list of the """
        self.__controller = controller
        self.__relays = relays
        self.__ting_leg = leg
        self.__tor_sock = None
        self.__circuit_id = None

        self.__max_circuit_build_attempts = kwargs.get(
            "max_circuit_build_attempts", self.__DEFAULT_MAX_BUILD_ATTEMPTS
        )
        self.__socks_port = kwargs.get(
            "SocksPort", self.__DEFAULT_SOCKS_PORT
        )
        self.__socks_timeout = kwargs.get(
            "SocksTimeout", self.__DEFAULT_SOCKS_TIMEOUT_SEC
        )
        
    def build(self):
        """Build the circuit.

        :return Time to build the circuit"""
        cid, last_exception, failures = None, None, 0

        while failures < self.__max_circuit_build_attempts:
            try:
                log("Building circuit...")
                start_build = time.time()
                self.__circuit_id = self.__controller.new_circuit(self.relays, await_build=True)
                end_build = time.time()
                success("Circuit built successfully.")

                log("Setting up SOCKS proxy...")
                self.__tor_sock = self.__setup_proxy()
                log("SOCKS proxy setup complete.")

                return round(end_build - start_build, 5)

            except (InvalidRequest, CircuitExtensionFailed) as exc:
                failures += 1
                if "message" in vars(exc):
                    warning("{0}".format(vars(exc)["message"]))
                else:
                    warning(
                        "Circuit failed to be created, reason unknown."
                    )
                if cid is not None:
                    self.__controller.close_circuit(cid)
                last_exception = exc

        raise last_exception
        

    # Tell socks to use tor as a proxy
    def __setup_proxy(self):
        sock = socks.socksocket()
        sock.set_proxy(self.__SOCKS_TYPE, self.__SOCKS_HOST, self.__socks_port)
        sock.settimeout(self.__socks_timeout)
        return sock

    def sample(self):
        """Take a Ting measurement on this circuit."""
        raise NotImplementedError("eventually")


    def close(self):
        """Close the Tor socket."""
        # TODO bring down circuit
        try:
            logging.debug("Shutting down Tor socket")
            self.__tor_sock.shutdown(socket.SHUT_RDWR)
        except Exception:
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
    def id(self):
        """Get the circuit ID. If circuit has not been built, returns None."""
        return self.__circuit_id


class TingCircuit:
    """Holds results for Tor circuit creation."""

    def __init__(self, x: TorCircuit, y: TorCircuit, xy: TorCircuit):
        self.__x_circ = x
        self.__y_circ = y
        self.__xy_circ = xy

    @property
    def x_circ(self):
        """Getter method for circuit x."""
        return self.__x_circ

    @property
    def y_circ(self):
        """Getter method for circuit y."""
        return self.__y_circ

    @property
    def xy_circ(self):
        """Getter method for circuit xy."""
        return self.__xy_circ

    @property
    def all(self):
        """Returns all legs of the Tor measurement."""
        return [self.__x_circ, self.__y_circ, self.__xy_circ]
