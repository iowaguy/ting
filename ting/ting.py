"""Provides a high-level interface to Ting that does not require knowledge
of internals."""

import logging
import time
from typing import Tuple, List, Dict, Union
from threading import Thread, Event

from ting.client import TingClient, init_controller
from ting.echo_server import echo_server_background
from ting.logging import failure
from ting.utils import Fingerprint, IPAddress, RelayPair, TingLeg


def ting(  # pylint: disable=too-many-arguments
    measurement_targets: List[Tuple[Fingerprint, Fingerprint]],
    relay_w_fp: Fingerprint,
    relay_z_fp: Fingerprint,
    source_addr: IPAddress = "127.0.0.1",
    num_samples: int = 10,
    **kwargs: Union[str, int],
) -> Dict[RelayPair, Dict[TingLeg, List[Tuple[float, float]]]]:
    """A high-level interface for Ting."""

    with echo_server_background() as echo_server:
        try:
            controller = init_controller(kwargs.pop("ControllerPort"))
        except ConnectionRefusedError:
            failure("Could not connect to controller.")
        ting_client = TingClient(
            relay_w_fp, relay_z_fp, source_addr, echo_server, controller, **kwargs
        )
        results: Dict[RelayPair, Dict[TingLeg, List[Tuple[float, float]]]] = dict()
        logging.info("Measure RTT between the following nodes: %s", measurement_targets)
        for relay1, relay2 in measurement_targets:
            results[(relay1, relay2)] = {l: [] for l in TingLeg}
            circuit_templates = ting_client.generate_circuit_templates(relay1, relay2)
            for circuit_template in circuit_templates:
                with circuit_template as circuit:
                    for _ in range(num_samples):
                        results[(relay1, relay2)][circuit_template.leg].append(
                            circuit.sample()
                        )

    return results
