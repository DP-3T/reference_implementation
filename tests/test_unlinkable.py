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

from datetime import datetime, timezone

from dp3t.protocols.unlinkable import (
    ephid_from_seed,
    epoch_from_time,
    hashed_observation_from_ephid,
    hashed_observation_from_seed,
)


SEED0 = bytes.fromhex(
    "0000000000000000000000000000000000000000000000000000000000000000"
)
SEED1 = bytes.fromhex(
    "eaa2054637009757b9988b28998209d253eede69345f835bb91b3b333108d229"
)

EPHID0 = bytes.fromhex("66687aadf862bd776c8fc18b8e9f8e20")
EPHID1 = bytes.fromhex("b7b1d06cd81686669aeea51e9f4723b5")

TIME0 = datetime(2020, 4, 10, hour=7, minute=15, tzinfo=timezone.utc)
TIME1 = datetime(2020, 4, 15, hour=14, minute=32, tzinfo=timezone.utc)

EPOCH0 = 1762781
EPOCH1 = 1763290

HASHED_OBSERVATION_EPHID1_TIME0 = bytes.fromhex(
    "93e8cffb4f828baf9e36b658ab8988b9afd39bec9f95b24930768157148adcc9"
)
HASHED_OBSERVATION_EPHID1_TIME1 = bytes.fromhex(
    "bc2667e5bc9d3ea33c0193f19884aefcb4879968f65250145c3c9bcb703ccb10"
)

##############################
### TEST UTILITY FUNCTIONS ###
##############################


def test_epoch_from_time():
    epoch0 = epoch_from_time(TIME0)
    assert epoch0 == EPOCH0

    epoch1 = epoch_from_time(TIME1)
    assert epoch1 == EPOCH1


##########################################
### TEST BASIC CRYPTOGRAPHIC FUNCTIONS ###
##########################################


def test_ephid_from_seed():
    ephid0 = ephid_from_seed(SEED0)
    assert ephid0 == EPHID0

    ephid1 = ephid_from_seed(SEED1)
    assert ephid1 == EPHID1


def test_hashed_observation_from_ephid():
    hashed_observation0 = hashed_observation_from_ephid(EPHID1, EPOCH0)
    assert hashed_observation0 == HASHED_OBSERVATION_EPHID1_TIME0

    hashed_observation1 = hashed_observation_from_ephid(EPHID1, EPOCH1)
    assert hashed_observation1 == HASHED_OBSERVATION_EPHID1_TIME1


def test_hashed_observation_from_seed():
    hashed_observation0 = hashed_observation_from_seed(SEED1, EPOCH0)
    assert hashed_observation0 == HASHED_OBSERVATION_EPHID1_TIME0

    hashed_observation1 = hashed_observation_from_seed(SEED1, EPOCH1)
    assert hashed_observation1 == HASHED_OBSERVATION_EPHID1_TIME1
