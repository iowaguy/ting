#!/usr/bin/python3

"""A module for running an echo server."""

from contextlib import contextmanager
import logging
import socket
from ting.stoppable_thread import StoppableThread

# from ting.exceptions import MissingParameterException

__MESSAGE_SIZE = 1

# def __read_port_from_tingrc(tingrc_path='./tingrc'):
#     with open(tingrc_path) as tingrc_file:
#         params = tingrc_file.readlines()
#     for param in params:
#         if "DestinationPort" in param:
#             return int(param.strip().split(" ")[1])
#     raise MissingParameterException(
#         "The tingrc must include a DestinationPort for the echo server."
#     )

def __setup_socket(host, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host,port))

    backlog = 1
    sock.listen(backlog)
    logging.info("TCP echo server listening on port %i", port)
    return sock


def start_echo_server(host='0.0.0.0', port=16667):
    """Start the echo server."""
    sock = __setup_socket(host, port)

    while True:
        try:
            client, address = sock.accept()
            logging.info("Connection accepted from %s", str(address))
            data = client.recv(__MESSAGE_SIZE)
            while data and (str(bytes('!c', 'utf-8') + data)) != 'X':
                client.send(data)
                data = client.recv(__MESSAGE_SIZE)
            client.close()
            logging.info("Connection closed.")
        except socket.error as socket_error:
            logging.error("Socket Error: %s", str(socket_error))

@contextmanager
def echo_server():
    """A context managed echo server."""
    echo_server_thread = StoppableThread(target=start_echo_server)
    echo_server_thread.start()
    try:
        yield
    finally:
        echo_server_thread.stop()
        echo_server_thread.join()
