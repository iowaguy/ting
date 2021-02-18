#!/usr/bin/python3

"""A module for running an echo server."""

import logging
import select
import socket

class EchoServer():
    """A simple echo server for Ting to contact."""

    __MESSAGE_SIZE = 3
    __TIMEOUT = 0.5

    def __init__(self, host="0.0.0.0", port=16667):
        self.echo_socket = self.__setup_socket(host, port)
        self.running = False

    def run(self):
        """Start the echo server."""
        self.running = True
        read_list = [self.echo_socket]
        while True:
            readable, _, _ = select.select(read_list, [], [], EchoServer.__TIMEOUT)
            logging.debug("Socket is ready to read")
            for sock in readable:
                if sock is self.echo_socket:
                    client_socket, address = self.echo_socket.accept()
                    read_list.append(client_socket)
                    logging.info("Connection accepted from %s", str(address))
                else:
                    data = sock.recv(EchoServer.__MESSAGE_SIZE)
                    logging.debug("data recieved=%s", data)
                    while data and (str(bytes("!c", "utf-8") + data)) != "X":
                        logging.debug("Echoing data: %s", data)
                        sock.send(data)
                        data = sock.recv(EchoServer.__MESSAGE_SIZE)
                    sock.close()
                    read_list.remove(sock)
                    logging.info("Connection closed.")

    def is_running(self):
        """Return True if echo server is running locally."""
        return self.running
                    
    @classmethod
    def __setup_socket(cls, host, port):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))

        backlog = 1
        sock.listen(backlog)
        logging.info("TCP echo server listening on port %i", port)
        return sock
