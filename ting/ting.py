import logging
from ting.exceptions import TingException
from ting.client import TingClient

def ting(measurement_targets, source_addr=None, max_circuit_build_attempts=5,
         num_samples=10, relay_w_fp=None, relay_z_fp=None, relay_list="test",
         start_echo_server=False):

    # all "local" config goes in TingClient
    ting_client = TingClient(relay_w_fp, relay_z_fp, source_addr, dest_port, relay_list)
    results = {}
    for relay1, relay2 in measurement_targets:
        with ting_client.circuit(relay1, relay2,
                                 max_attempts=max_circuit_build_attempts) \
                                 as ting_circuit:
            results[(relay1, relay2)] = []
            for _ in range(num_samples):
                try:
                    measurement = ting_circuit.measure()
                except TingException as e:
                    logging.error("Ting has run into a problem:", str(e))

                results[(relay1, relay2)].append(measurement)
                
    return results
