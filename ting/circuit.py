"""A module for Tor circuit operations"""

from typing import List
from stem.control import Controller

from ting.logging import failure, notify, log, success
from ting.exceptions import CircuitConnectionException
from ting.utils import Fingerprint, TingLeg


class TorCircuit:
    """A class for building and interacting with Tor circuits."""

    def __init__(self, controller: Controller, relays: List[Fingerprint], leg: TingLeg):
        """:param controller This is a [stem controller][https://stem.torproject.org/api/control.html] object.
        :param relays This is a list of the """
        self.__controller = controller
        self.__relays = relays
        self.__ting_leg = leg

    def build(self):
        raise NotImplentedError("eventually")

    def sample(self):
        raise NotImplentedError("eventually")

    @property
    def leg(self):
        """Getter method for the Ting circuit leg."""
        return self.__ting_leg

    @property
    def relays(self):
        """Getter method for the relays in the circuit."""
        return self.__relays

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
