class NotReachableException(Exception):
    def __init__(self, msg, func, dest):
        self.msg = msg
        self.func = func
        self.dest = dest


class CircuitConnectionException(Exception):
    def __init__(self, msg, circuit, exc):
        self.msg = msg
        self.circuit = circuit
        self.exc = exc


class TingException(Exception):
    def __init__(self, msg, exc):
        self.msg = msg
        self.exc = exc


class ConnectionAlreadyExistsException(Exception):
    def __init__(self, msg, exc):
        self.msg = msg
        self.exc = exc

class TorShutdownException(Exception):
    def __init__(self, msg, exc):
        self.msg = msg
        self.exc = exc
    
