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


class TingLeg(Enum):
    X = "x"
    Y = "y"
    XY = "xy"
