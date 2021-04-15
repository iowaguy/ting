#!/usr/bin/python3

"""A module for running an echo server."""

import logging
import time
import errno
import random

from socket import socket, AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR, timeout
from threading import Event, Thread
from contextlib import contextmanager
from typing import Optional

import ting.timer_pb2
from ting.utils import IPAddress, Port, Endpoint

logger = logging.getLogger(__name__)

_PORT_RANGE = range(16000, 17000)


class EchoServer:
    """A simple echo server for Ting to contact."""

    __MESSAGE_SIZE = 3
    __TIMEOUT = 0.5
    __DEFAULT_ENDPOINT = Endpoint(host=IPAddress("127.0.0.1"), port=Port(16667))

    def __init__(self, endpoint=__DEFAULT_ENDPOINT) -> None:
        self.endpoint = endpoint

    def serve_one(self):
        logger.debug("Socket is ready to read")
        try:
            sock, address = self.echo_socket.accept()
        except timeout:
            logger.debug("Socket timeout")
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

    def serve_with_shutdown(self, event: Event):
        while not event.is_set():
            self.serve_one()

    def serve(self) -> None:
        """Start the echo server."""
        while True:
            self.serve_one()

    def __enter__(self):
        sock = socket(AF_INET, SOCK_STREAM)
        sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        sock.settimeout(self.__TIMEOUT)
        sock.bind((self.endpoint.host, self.endpoint.port))

        backlog = 1
        sock.listen(backlog)
        logger.info("TCP echo server listening on port %i", self.endpoint.port)
        self.echo_socket = sock

        return self

    def __exit__(self, exc_type: Exception, exc_value: str, exc_traceback: str) -> None:
        self.echo_socket.close()
        self.echo_socket = None


@contextmanager
def _echo_server_background_inner(endpoint: Endpoint):
    shutdown = Event()
    with EchoServer(endpoint) as echo_server:
        try:
            thread = Thread(target=echo_server.serve_with_shutdown, args=(shutdown,))
            thread.start()
            yield echo_server.endpoint
        finally:
            shutdown.set()
            thread.join()


@contextmanager
def echo_server_background(host: IPAddress = "127.0.0.1"):
    while True:
        port = Port(random.randint(_PORT_RANGE.start, _PORT_RANGE.stop))
        endpoint = Endpoint(host, port)
        try:
            with _echo_server_background_inner(endpoint) as e:
                yield e
        except OSError as exc:
            if exc.errno == errno.EADDRINUSE:
                continue
            raise
        return


if __name__ == "__main__":
    with EchoServer() as echo_server:
        echo_server.serve()
