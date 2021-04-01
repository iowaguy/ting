#!/usr/bin/python3

"""A module for running an echo server."""

import logging
import select
from socket import socket, AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR
from threading import Event
import time

from ting.utils import IPAddress, Port


class EchoServer:
    """A simple echo server for Ting to contact."""

    __MESSAGE_SIZE = 3
    __TIMEOUT = 0.5

    def __init__(
        self, event: Event, host: IPAddress = "0.0.0.0", port: Port = 16667
    ) -> None:
        self.__logger = logging.getLogger(__name__)
        self.echo_socket = self.__setup_socket(host, port)
        self.running = False
        self.__event = event


    def run(self) -> None:
        """Start the echo server."""
        self.running = True
        read_list = [self.echo_socket]
        while True:
            readable, _, _ = select.select(read_list, [], [], EchoServer.__TIMEOUT)
            self.__logger.debug("Socket is ready to read")
            for sock in readable:
                if sock is self.echo_socket:
                    client_socket, address = self.echo_socket.accept()
                    read_list.append(client_socket)
                    self.__logger.info("Connection accepted from %s", str(address))
                else:
                    data = sock.recv(EchoServer.__MESSAGE_SIZE)
                    self.__logger.debug("Data received: %s", data)
                    if not data or (str(bytes("!c", "utf-8") + data)) == "X":
                        self.__logger.debug("Client is closing connection.")
                        sock.close()
                        read_list.remove(sock)
                        self.__logger.info("Connection closed.")
                        continue

                    # If we're here, then the client is tinging us
                    self.__event.set()
                    self.__logger.debug("Echoing data: %s", data)
                    start_time = time.time()
                    sock.send(data)
                    self.__event.wait()
                    stop_time = time.time()
                    # TODO report stop_time - start_time to main thread

    def is_running(self) -> bool:
        """Return True if echo server is running locally."""
        return self.running

    def __setup_socket(self, host: IPAddress, port: Port) -> socket:
        sock = socket(AF_INET, SOCK_STREAM)
        sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        sock.bind((host, port))

        backlog = 1
        sock.listen(backlog)
        self.__logger.info("TCP echo server listening on port %i", port)
        return sock
