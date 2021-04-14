#!/usr/bin/python3

"""A module for running an echo server."""

import logging
import select
import time

from socket import socket, AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR, timeout

import ting.timer_pb2
from ting.utils import IPAddress, Port

logger = logging.getLogger(__name__)


class EchoServer:
    """A simple echo server for Ting to contact."""

    __MESSAGE_SIZE = 3
    __TIMEOUT = 0.5

    def __init__(self, host: IPAddress = "0.0.0.0", port: Port = 16667) -> None:
        self.__host = host
        self.__port = port
        self.running = False

    def serve_one(self):
        logger.debug("Socket is ready to read")
        try:
            sock, address = self.echo_socket.accept()
        except timeout:
            return
        logger.info("Connection accepted from %s", str(address))
        with sock:
            while True:
                data = sock.recv(EchoServer.__MESSAGE_SIZE)
                timer = ting.timer_pb2.Ting()
                timer.ParseFromString(data)
                logger.debug("Data received: %s", timer)
                if not data or timer.ptype == ting.timer_pb2.Ting.Packet.CLOSE:
                    logger.debug("Client is closing connection.")
                    logger.info("Connection closed.")
                    break
                # If we're here, then the client is tinging us
                timer.Clear()
                timer.ptype = ting.timer_pb2.Ting.Packet.TING
                timer.time_sec = time.time()
                logger.debug("Echoing data: %s", data)
                sock.send(timer.SerializeToString())

    def serve(self) -> None:
        """Start the echo server."""
        while True:
            self.serve_one()

    def __enter__(self):
        sock = socket(AF_INET, SOCK_STREAM)
        sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        sock.settimeout(self.__TIMEOUT)
        sock.bind((self.__host, self.__port))

        backlog = 1
        sock.listen(backlog)
        logger.info("TCP echo server listening on port %i", self.__port)
        self.echo_socket = sock

        return self

    def __exit__(self, exc_type: Exception, exc_value: str, exc_traceback: str) -> None:
        self.echo_socket.close()
        self.echo_socket = None


if __name__ == "__main__":
    with EchoServer() as echo_server:
        echo_server.serve()
