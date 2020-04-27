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

import dp3t.config as config
from dp3t.protocols.lowcost import (
    day_start_from_time,
    next_day_key,
    generate_ephids_for_day,
    batch_start_from_time,
    ContactTracer,
    TracingDataBatch,
    SECONDS_PER_BATCH,
)

START_TIME = datetime(2020, 4, 25, 15, 17, tzinfo=timezone.utc)
START_TIME_DAY_START_IN_EPOCHS = 1587772800

EPHID1 = bytes.fromhex("66687aadf862bd776c8fc18b8e9f8e20")
EPHID2 = bytes.fromhex("b7b1d06cd81686669aeea51e9f4723b5")

KEY0 = bytes.fromhex("0000000000000000000000000000000000000000000000000000000000000000")
KEY1 = bytes.fromhex("66687aadf862bd776c8fc18b8e9f8e20089714856ee233b3902a591d0d5f2925")
KEY2 = bytes.fromhex("2b32db6c2c0a6235fb1397e8225ea85e0f0e6e8c7b126d0016ccbde0e667151e")


EPHIDS_KEY1 = [
    bytes.fromhex("04cab76af57ca373de1d52689fae06c1"),
    bytes.fromhex("ab7747084efb743a6aa1b19bab2f0ca3"),
    bytes.fromhex("f417c16279d7f718465f958e17466550"),
]

##############################
### TEST UTILITY FUNCTIONS ###
##############################


def test_day_start_from_time():
    day_start = day_start_from_time(START_TIME)
    assert day_start % config.SECONDS_PER_DAY == 0
    assert day_start_from_time(START_TIME) == START_TIME_DAY_START_IN_EPOCHS


def test_batch_start_from_time():
    batch_start = batch_start_from_time(START_TIME)
    assert batch_start % SECONDS_PER_BATCH == 0


##########################################
### TEST BASIC CRYPTOGRAPHIC FUNCTIONS ###
##########################################


def test_next_day_key():
    key0 = KEY0
    key1 = next_day_key(key0)
    assert key1 == KEY1

    key2 = next_day_key(key1)
    assert key2 == KEY2


def test_generate_ephids_for_day():
    key = KEY1

    # Test correct order when not shuffling
    ephids = generate_ephids_for_day(key, shuffle=False)
    for idx, ephid in enumerate(EPHIDS_KEY1):
        assert ephids[idx] == ephid

    # Test values are still present when shuffling
    ephids = generate_ephids_for_day(key, shuffle=True)
    for ephid in EPHIDS_KEY1:
        assert ephid in ephids


##########################
### TEST TRACING BATCH ###
##########################


def test_tracing_batch_init():
    batch = TracingDataBatch([])

    # Approximate test for default release time
    assert datetime.now().timestamp() - batch.release_time < SECONDS_PER_BATCH + 60


def test_tracing_batch_non_aligned_release_time():
    # Don't accept release time that does not align to batch boundary
    release_time = int(START_TIME.timestamp())
    with pytest.raises(ValueError):
        TracingDataBatch([], release_time=release_time)


def test_tracing_batch_aligned_release_time():
    # With an aligned release time we shouldn't get an error
    ts_start = int(START_TIME.timestamp())
    release_time = (ts_start // SECONDS_PER_BATCH) * SECONDS_PER_BATCH
    TracingDataBatch([], release_time=release_time)


####################################
### TEST INTERNAL DATASTRUCTURES ###
####################################


def test_deleting_old_keys():
    ct = ContactTracer(start_time=START_TIME)
    ct.next_day()
    ct.next_day()

    assert len(ct.past_keys) > 0

    old_day_key = ct.current_day_key
    old_ephids = set(ct.current_ephids)

    # Get with side-effects: deleting old keys
    ct.get_tracing_information(START_TIME)

    # Should delete all old keys
    assert len(ct.past_keys) == 0

    # Should pick a new day key
    assert ct.current_day_key != old_day_key

    # And all EphIDs should have been regenerated
    assert len(set(ct.current_ephids).intersection(old_ephids)) == 0


def test_contact_tracing_retention():
    ct = ContactTracer(start_time=START_TIME)
    t1 = START_TIME + timedelta(minutes=20)
    t2 = START_TIME + timedelta(hours=6)
    ct.add_observation(EPHID1, t1)
    ct.add_observation(EPHID2, t2)
    recorded_times = ct.observations.keys()

    for _ in range(config.RETENTION_PERIOD + 1):
        ct.next_day()

    for time in recorded_times:
        assert time not in ct.observations


def test_observation_granularity():
    ct = ContactTracer(start_time=START_TIME)
    t1 = START_TIME + timedelta(minutes=20)
    t2 = START_TIME + timedelta(hours=6)
    ct.add_observation(EPHID1, t1)
    ct.add_observation(EPHID2, t2)

    # Verify that internal representation has batch granularity
    for time in ct.observations:
        assert time % SECONDS_PER_BATCH == 0


def test_observation_granularity_after_update():
    ct = ContactTracer(start_time=START_TIME)
    t1 = START_TIME + timedelta(minutes=20)
    t2 = START_TIME + timedelta(hours=6)
    t3 = START_TIME + timedelta(days=1, hours=6)
    ct.add_observation(EPHID1, t1)
    ct.add_observation(EPHID2, t2)
    ct.next_day()
    ct.add_observation(EPHID2, t3)

    t4 = int((START_TIME + timedelta(days=1, hours=10)).timestamp())
    release_time = (t4 // SECONDS_PER_BATCH) * SECONDS_PER_BATCH
    batch = TracingDataBatch([], release_time=release_time)
    ct.housekeeping_after_batch(batch)

    # All observations should now be at day granularity
    for time in ct.observations:
        assert time % config.SECONDS_PER_DAY == 0
