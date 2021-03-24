"""Provides a high-level interface to Ting that does not require knowledge
of internals."""

import logging
from typing import Tuple, List, Dict

from ting.client import TingClient
from ting.utils import Fingerprint, RelayPair


def ting(
    measurement_targets: List[Tuple[Fingerprint, Fingerprint]],
    relay_w_fp,
    relay_z_fp,
    source_addr=None,
    num_samples=10,
    local_test=False,
    **kwargs,
) -> Dict[RelayPair, Dict[str, List[float]]]:
    """A high-level interface for Ting."""
    ting_client = TingClient(relay_w_fp, relay_z_fp, source_addr, local_test, **kwargs)

    results: Dict[RelayPair, Dict[str, List[float]]] = dict()
    logging.info("Measure RTT between the following nodes: %s", measurement_targets)
    for relay1, relay2 in measurement_targets:
        results[(relay1, relay2)] = {"x": [], "y": [], "xy": []}
        circuit_templates = ting_client.generate_circuit_templates(relay1, relay2)
        for circuit_template in circuit_templates.all:
            # circuit_results: Dict[str, List[float]] = {circuit_template.leg.value: []}
            with circuit_template as circuit:
                for _ in range(num_samples):
                    results[(relay1, relay2)][circuit_template.leg.value].append(
                        circuit.sample()
                    )

    return results
