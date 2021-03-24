"""Provides a high-level interface to Ting that does not require knowledge
of internals."""

import logging
import threading
from typing import Tuple, List, Dict, Union

from ting.client import TingClient
from ting.utils import Fingerprint, IPAddress, RelayPair, TingLeg


def ting(
    measurement_targets: List[Tuple[Fingerprint, Fingerprint]],
    relay_w_fp: Fingerprint,
    relay_z_fp: Fingerprint,
    source_addr: IPAddress = "127.0.0.1",
    num_samples: int = 10,
    local_test: bool = False,
    **kwargs: Union[str, int],
) -> Dict[RelayPair, Dict[TingLeg, List[float]]]:
    """A high-level interface for Ting."""

    # problem with the following approach: zach will basically need to reimplement all this threading stuff; how can i hide it?
    # create Event(), e
    # start echo_server thread, passing it e
    # also pass e to client
    # during sample, client: starts timer, sends message, and waits for event
    # once event occurs, stop timer and record, then return


    # when echo server receives message, it flags event (e.set())

    ting_client = TingClient(relay_w_fp, relay_z_fp, source_addr, local_test, **kwargs)

    results: Dict[RelayPair, Dict[TingLeg, List[float]]] = dict()
    logging.info("Measure RTT between the following nodes: %s", measurement_targets)
    for relay1, relay2 in measurement_targets:
        results[(relay1, relay2)] = {TingLeg.X: [], TingLeg.Y: [], TingLeg.XY: []}
        circuit_templates = ting_client.generate_circuit_templates(relay1, relay2)
        for circuit_template in circuit_templates.all:
            with circuit_template as circuit:
                for _ in range(num_samples):
                    results[(relay1, relay2)][circuit_template.leg].append(
                        circuit.sample()
                    )

    return results
