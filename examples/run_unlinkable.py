#!/usr/bin/env python3

""" Simple example/demo of the unlinkable DP-3T design

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


from datetime import timedelta

from dp3t.protocols.unlinkable import ContactTracer, TracingDataBatch


def report_broadcasted_ephids(name, app):
    """
    Convenience function to report some broadcasted EphIDs
    """
    reporting_time = app.start_of_today + timedelta(hours=10)
    ephid = app.get_ephid_for_time(reporting_time)
    print("At {}: {} broadcasts {}".format(reporting_time.time(), name, ephid.hex()))


def report_day(time):
    """
    Convenience function to report start of the day
    """
    print("---- {} ----".format(time))


def process_single_day(alice, bob, interaction_time=None):
    """
    Convenience function, process and report on a single day
    """
    report_day(alice.today)
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

    interaction_time = alice.start_of_today + timedelta(hours=10)
    bob_contagious_start = bob.start_of_today
    process_single_day(alice, bob, interaction_time)

    print("... skipping 3 days ...\n")
    for _ in range(4):
        alice.next_day()
        bob.next_day()

    ### Diagnosis and reporting ###

    report_day(alice.today)
    print("Bob is diagnosed with SARS-CoV-2")
    print(
        "Doctor establishes that Bob started being contagious at {}".format(
            bob_contagious_start
        )
    )
    print("And that Bob was contagious for 3 days")
    bob_contagious_end = bob_contagious_start + timedelta(days=3)

    print("\n[Bob -> Server] Bob sends:")
    tracing_info_bob = bob.get_tracing_information(
        bob_contagious_start, bob_contagious_end
    )
    print(
        " * his seeds for the time period {} to {}".format(
            bob_contagious_start, bob_contagious_end
        )
    )
    print(" * and the corresponding epochs\n")

    ### Contact tracing ###

    print("[Server] Compiles download batch by:")
    print("  * Computing hashed observations given the seeds")
    print("  * Inserts these into a cuckoo filter\n")
    batch = TracingDataBatch([tracing_info_bob])

    print("[Server -> Alice] Alice receives batch")
    print("  * Alice checks if she was in contact with an infected person")

    if alice.matches_with_batch(batch) > 0:
        print("  * CORRECT: Alice's phone concludes she is at risk")
    else:
        print("  * ERROR: Alice's phone does not conclude she is at risk")
        raise RuntimeError("Example code failed!")


if __name__ == "__main__":
    main()
