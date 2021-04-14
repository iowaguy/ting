#!/usr/bin/python3

"""A module for running an echo server."""

import logging
import select
from socket import socket, AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR
from threading import Event
import time

import ting.timer_pb2
from ting.utils import IPAddress, Port

logger = logging.getLogger(__name__)


class EchoServer:
    """A simple echo server for Ting to contact."""

    __MESSAGE_SIZE = 3
    __TIMEOUT = 0.5

    def __init__(
        self, event: Event, host: IPAddress = "0.0.0.0", port: Port = 16667
    ) -> None:
        self.echo_socket = self.__setup_socket(host, port)
        self.running = False
        self.__event = event

    def run(self) -> None:
        """Start the echo server."""
        self.running = True
        read_list = [self.echo_socket]
        while True:
            if self.__event.is_set():
                return
            readable, _, _ = select.select(read_list, [], [], EchoServer.__TIMEOUT)
            logger.debug("Socket is ready to read")
            for sock in readable:
                if sock is self.echo_socket:
                    client_socket, address = self.echo_socket.accept()
                    read_list.append(client_socket)
                    logger.info("Connection accepted from %s", str(address))
                else:
                    data = sock.recv(EchoServer.__MESSAGE_SIZE)
                    timer = ting.timer_pb2.Ting()
                    timer.ParseFromString(data)
                    logger.debug("Data received: %s", timer)
                    if not data or timer.ptype == ting.timer_pb2.Ting.Packet.CLOSE:
                        logger.debug("Client is closing connection.")
                        sock.close()
                        read_list.remove(sock)
                        logger.info("Connection closed.")
                        continue

                    # If we're here, then the client is tinging us
                    timer.Clear()
                    timer.ptype = ting.timer_pb2.Ting.Packet.TING
                    timer.time_sec = time.time()
                    logger.debug("Echoing data: %s", data)
                    sock.send(timer.SerializeToString())

    def is_running(self) -> bool:
        """Return True if echo server is running locally."""
        return self.running

    def __setup_socket(self, host: IPAddress, port: Port) -> socket:
        sock = socket(AF_INET, SOCK_STREAM)
        sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        sock.bind((host, port))

        backlog = 1
        sock.listen(backlog)
        logger.info("TCP echo server listening on port %i", port)
        return sock


if __name__ == "__main__":
    echo_server = EchoServer()
    if not echo_server.is_running():
        echo_server.run()
