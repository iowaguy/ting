"""A module of exceptions."""

from typing import List

from ting.utils import Fingerprint


class NotReachableException(Exception):
    """This error will be raised when a host is not reachable."""

    def __init__(self, msg: str, dest: str) -> None:
        super().__init__(msg)
        self.msg = msg
        self.dest = dest


class CircuitConnectionException(Exception):
    """This error will be raised when a circuit connection fails."""

    def __init__(self, msg: str, circuit: str, exc: Exception) -> None:
        super().__init__(msg)
        self.msg = msg
        self.circuit = circuit
        self.exc = exc


class TingException(Exception):
    """This error will be raised when a Ting specific exception occurs."""

    def __init__(self, msg: str, exc: Exception) -> None:
        super().__init__(msg)
        self.msg = msg
        self.exc = exc


class ConnectionAlreadyExistsException(Exception):
    """This error will be raised when a connection is attempted where one already exists."""

    def __init__(self, msg: str, exc: Exception) -> None:
        super().__init__(msg)
        self.msg = msg
        self.exc = exc


class TorShutdownException(Exception):
    """This error will be raised when Tor cannot shutdown properly."""

    def __init__(self, msg: str, exc: Exception) -> None:
        super().__init__(msg)
        self.msg = msg
        self.exc = exc
