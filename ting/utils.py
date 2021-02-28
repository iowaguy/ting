"""A series of utility functions and classes for Ting."""

from enum import Enum

Fingerprint = str
"""A Tor fingerprint"""

IPAddress = str
"""An IP address"""

Port = int
"""A port number"""


class TingLeg(Enum):
    X = "x"
    Y = "y"
    XY = "xy"
