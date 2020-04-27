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

from datetime import datetime, timedelta, timezone
import pytest

import dp3t.protocols.lowcost as lowcost
import dp3t.protocols.unlinkable as unlinkable
import dp3t.config as config


@pytest.fixture(params=[lowcost.ContactTracer, unlinkable.ContactTracer])
def contact_tracer(request):
    return request.param


@pytest.fixture(params=[lowcost, unlinkable])
def protocol(request):
    return request.param


START_TIME = datetime(2020, 4, 25, 15, 17, tzinfo=timezone.utc)
EPHID = bytes.fromhex("66687aadf862bd776c8fc18b8e9f8e20")


############################
### TEST CONTACT TRACING ###
############################


def test_basic_contact_tracing_yesterday_ephid(contact_tracer):
    alice = contact_tracer(start_time=START_TIME)
    yesterday = START_TIME - timedelta(days=1)
    with pytest.raises(ValueError):
        alice.get_ephid_for_time(yesterday)


def test_basic_contact_tracing_tomorrow_ephid(contact_tracer):
    alice = contact_tracer(start_time=START_TIME)
    tomorrow = START_TIME + timedelta(days=1)
    with pytest.raises(ValueError):
        alice.get_ephid_for_time(tomorrow)


def test_basic_contact_tracing_late_observation(contact_tracer):
    alice = contact_tracer()
    observation_time = datetime.now() + timedelta(days=1)
    with pytest.raises(ValueError):
        alice.add_observation(EPHID, observation_time)


def test_basic_contact_tracing_unavailable_tracing_info(contact_tracer):
    alice = contact_tracer()

    # Requesting a past key that is not there
    with pytest.raises(ValueError):
        yesterday = datetime.now() - timedelta(days=1)
        alice.get_tracing_information(yesterday)

    # Requesting a future key that is not there
    with pytest.raises(ValueError):
        tomorrow = datetime.now() + timedelta(days=1, hours=1)
        dayafter = datetime.now() + timedelta(days=2, hours=1)
        alice.get_tracing_information(tomorrow, last_contagious_time=dayafter)


def test_contact_tracing_single_observation(protocol):
    alice = protocol.ContactTracer(start_time=START_TIME)
    bob = protocol.ContactTracer(start_time=START_TIME)

    # A single interaction between Alice and Bob
    interaction_time = START_TIME + timedelta(minutes=20)
    ephid_alice = alice.get_ephid_for_time(interaction_time)
    ephid_bob = bob.get_ephid_for_time(interaction_time)
    alice.add_observation(ephid_bob, interaction_time)
    bob.add_observation(ephid_alice, interaction_time)

    # Advance 4 days
    for _ in range(4):
        alice.next_day()
        bob.next_day()

    # Bob infected, get tracing keys
    tracing_info_bob = bob.get_tracing_information(START_TIME)

    # Pack into a batch, set release time to 4 days from start
    release_time = (int(START_TIME.timestamp()) // 86400 + 4) * 86400
    batch = protocol.TracingDataBatch([tracing_info_bob], release_time=release_time)

    # Alice should have one interaction with Bob
    assert alice.matches_with_batch(batch) == 1


def test_contact_tracing_multiple_observations(protocol):
    alice = protocol.ContactTracer(start_time=START_TIME)
    bob = protocol.ContactTracer(start_time=START_TIME)

    # Several interactions between Alice and Bob
    interaction_times = [
        START_TIME + timedelta(minutes=mins) for mins in [20, 100, 240]
    ]
    for interaction_time in interaction_times:
        ephid_alice = alice.get_ephid_for_time(interaction_time)
        ephid_bob = bob.get_ephid_for_time(interaction_time)
        alice.add_observation(ephid_bob, interaction_time)
        bob.add_observation(ephid_alice, interaction_time)

    # Advance 4 days
    for _ in range(4):
        alice.next_day()
        bob.next_day()

    # Bob infected, get tracing keys
    tracing_info_bob = bob.get_tracing_information(START_TIME)

    # Pack into a batch
    release_time = (int(START_TIME.timestamp()) // 86400 + 4) * 86400
    batch = protocol.TracingDataBatch([tracing_info_bob], release_time=release_time)

    # Alice should have three interactions with Bob
    assert alice.matches_with_batch(batch) == 3


def test_contact_tracing_contact_before_contagious(protocol):
    alice = protocol.ContactTracer(start_time=START_TIME)
    bob = protocol.ContactTracer(start_time=START_TIME)

    # A single interaction between Alice and Bob
    interaction_time = START_TIME + timedelta(minutes=20)
    ephid_alice = alice.get_ephid_for_time(interaction_time)
    ephid_bob = bob.get_ephid_for_time(interaction_time)
    alice.add_observation(ephid_bob, interaction_time)
    bob.add_observation(ephid_alice, interaction_time)

    # Advance 4 days
    for _ in range(4):
        alice.next_day()
        bob.next_day()

    # Bob infected, get tracing keys, day after Alice and Bob met
    start_of_being_contagious = START_TIME + timedelta(days=1)
    tracing_info_bob = bob.get_tracing_information(start_of_being_contagious)

    # Pack into a batch
    release_time = (int(START_TIME.timestamp()) // 86400 + 4) * 86400
    batch = protocol.TracingDataBatch([tracing_info_bob], release_time=release_time)

    # Alice should have zero contagious interactions with Bob
    assert alice.matches_with_batch(batch) == 0


def test_contact_tracing_no_replay_after_release(protocol):
    alice = protocol.ContactTracer(start_time=START_TIME)
    bob = protocol.ContactTracer(start_time=START_TIME)

    # Bob transmits an EphID
    transmit_time = START_TIME + timedelta(minutes=20)
    ephid_bob = bob.get_ephid_for_time(transmit_time)

    # Bob infected, get tracing keys
    start_of_being_contagious = START_TIME
    tracing_info_bob = bob.get_tracing_information(start_of_being_contagious)

    # Compute release time and create a batch
    release_time = (
        int(transmit_time.timestamp()) // lowcost.SECONDS_PER_BATCH + 1
    ) * lowcost.SECONDS_PER_BATCH
    batch = protocol.TracingDataBatch([tracing_info_bob], release_time=release_time)

    # Bob's EphID is replayed to Alice after the release time
    receive_time = datetime.fromtimestamp(release_time) + timedelta(minutes=7)
    alice.add_observation(ephid_bob, receive_time)

    # Alice should ignore the replay of Bob's EphId and register 0 interactions
    assert alice.matches_with_batch(batch) == 0


def test_contact_tracing_no_contact_outside_retention_window(protocol):
    alice = protocol.ContactTracer(start_time=START_TIME)
    bob = protocol.ContactTracer(start_time=START_TIME)

    alice.next_day()
    bob.next_day()

    # A single interaction between Alice and Bob
    interaction_time = START_TIME + timedelta(days=1, minutes=20)
    ephid_alice = alice.get_ephid_for_time(interaction_time)
    ephid_bob = bob.get_ephid_for_time(interaction_time)
    alice.add_observation(ephid_bob, interaction_time)
    bob.add_observation(ephid_alice, interaction_time)

    # Gather tracing information for today from Bob now
    start_of_today = interaction_time.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_today = start_of_today + timedelta(days=1)
    tracing_info_bob = bob.get_tracing_information(
        start_of_today, last_contagious_time=end_of_today
    )

    # Verify that Alice detects the interaction now
    release_time = int(end_of_today.timestamp())
    batch = protocol.TracingDataBatch([tracing_info_bob], release_time=release_time)
    assert alice.matches_with_batch(batch) == 1

    # Advance beyond the retention time
    for _ in range(config.RETENTION_PERIOD + 1):
        alice.next_day()
        bob.next_day()

    # Verify that Alice does not detect the interaction because it is too old
    end_of_retention = end_of_today + timedelta(days=config.RETENTION_PERIOD + 1)
    release_time = int(end_of_retention.timestamp())
    batch = protocol.TracingDataBatch([tracing_info_bob], release_time=release_time)
    assert alice.matches_with_batch(batch) == 0
