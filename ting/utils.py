"""A series of utility functions and classes for Ting."""

from enum import Enum
from typing import Tuple

Fingerprint = str
"""A Tor fingerprint"""

IPAddress = str
"""An IP address"""

Port = int
"""A port number"""

RelayPair = Tuple[Fingerprint, Fingerprint]
"""A pair of Tor relays"""


class TingLeg(Enum):
    """One of X, Y, or XY. The three circuits that are measured for each pair of relays."""

    X = "x"
    Y = "y"
    XY = "xy"


class TorRelayType(Enum):
    """The position of the relay in the circuit."""

    GUARD = 0
    MIDDLE = 1
    EXIT = 2
