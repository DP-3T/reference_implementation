#!/usr/bin/env python3

""" Simple example/demo of the low-cost DP-3T design

This demo simulates some interactions between two phones,
represented by the contact tracing modules, and then runs
contact tracing.
"""

__copyright__ = """
    Copyright 2020 EPFL

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.
"""
__license__ = "Apache 2.0"


from datetime import datetime, timedelta

from dp3t.protocols.lowcost import ContactTracer, TracingDataBatch, SECONDS_PER_BATCH


def report_broadcasted_ephids(name, app):
    """
    Convenience function to report some broadcasted EphIDs
    """
    ephids = [ephid.hex() for ephid in app.current_ephids]
    print("{} broadcasts [{}, {}, ...]".format(name, ephids[0], ephids[1]))


def report_day(epoch_time):
    """
    Convenience function to report start of the day
    """
    time = datetime.fromtimestamp(epoch_time)
    print("---- {} ({}) ----".format(time, epoch_time))


def process_single_day(alice, bob, interaction_time=None):
    """
    Convenience function, process and report on a single day
    """
    report_day(alice.start_of_today)
    report_broadcasted_ephids("Alice", alice)
    report_broadcasted_ephids("Bob", bob)

    if interaction_time:
        print("Alice and Bob interact:")
        ephid_bob = bob.get_ephid_for_time(interaction_time)
        alice.add_observation(ephid_bob, interaction_time)
        print("  Alice observes Bob's EphID {}".format(ephid_bob.hex()))

        ephid_alice = alice.get_ephid_for_time(interaction_time)
        bob.add_observation(ephid_alice, interaction_time)
        print("  Bob observes Alice's EphID {}".format(ephid_alice.hex()))
    else:
        print("Alice and Bob do not interact")

    # Advance to the next day
    alice.next_day()
    bob.next_day()
    print("")


def main():
    alice = ContactTracer()
    bob = ContactTracer()

    ### Interaction ###

    process_single_day(alice, bob)
    process_single_day(alice, bob)

    # Compute interaction time and process another day
    interaction_time = datetime.fromtimestamp(alice.start_of_today)
    interaction_time += timedelta(hours=10)
    process_single_day(alice, bob, interaction_time)

    print("... skipping 3 days ...\n")
    for _ in range(4):
        alice.next_day()
        bob.next_day()

    ### Diagnosis and reporting ###

    report_day(alice.start_of_today)
    print("Bob is diagnosed with SARS-CoV-2")
    bob_contagious_start = datetime.fromtimestamp(bob.start_of_today - 7 * 86400)
    print(
        "Doctor establishes that Bob started being contagious at {}".format(
            bob_contagious_start
        )
    )

    print("\n[Bob -> Server] Bob sends:")
    tracing_info_bob = bob.get_tracing_information(bob_contagious_start)
    bob_contagious_start_epoch, bob_contagious_key = tracing_info_bob
    print(" * his key on {}: {}".format(bob_contagious_start, bob_contagious_key.hex()))
    print(
        " * the corresponding start time in epoch-seconds: {}\n".format(
            bob_contagious_start_epoch
        )
    )

    ### Contact tracing ###

    print("[Server] Compiles download batch\n")
    release_time = bob.start_of_today + 4 * SECONDS_PER_BATCH
    batch = TracingDataBatch([tracing_info_bob], release_time=release_time)

    print("[Server -> Alice] Alice receives batch")
    print("  * Alice checks if she was in contact with an infected person")

    if alice.matches_with_batch(batch) > 0:
        print("  * CORRECT: Alice's phone concludes she is at risk")
    else:
        print("  * ERROR: Alice's phone does not conclude she is at risk")
        raise RuntimeError("Example code failed!")

    print("\n[Alice] Runs housekeeping to update her observation store")
    alice.housekeeping_after_batch(batch)


if __name__ == "__main__":
    main()
