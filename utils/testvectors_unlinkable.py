#!/usr/bin/env python3

""" Produces test vectors for the unlinkable DP-3T design """

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
)


SEED0 = "0000000000000000000000000000000000000000000000000000000000000000"
SEED1 = "eaa2054637009757b9988b28998209d253eede69345f835bb91b3b333108d229"


TIME0 = datetime(2020, 4, 10, hour=7, minute=15, tzinfo=timezone.utc)
TIME1 = datetime(2020, 4, 15, hour=14, minute=32, tzinfo=timezone.utc)
TIME2 = datetime(2020, 4, 16, hour=14, minute=32, tzinfo=timezone.utc)


def main():
    print("## Test vectors computing EphID given a seed ##")
    for seed_str in [SEED0, SEED1]:
        seed = bytes.fromhex(seed_str)
        ephid = ephid_from_seed(seed)

        print(" - Seed:", seed.hex())
        print(" - EphID:", ephid.hex())
        print()

    print("\n## Test vectors computing epoch number ##")
    for time in [TIME0, TIME1, TIME2]:
        print(" - Time:", time.isoformat(" "))
        print(" - Epoch Number:", epoch_from_time(time))
        print()

    print("\n## Test vector hashed observed EphIDs ##")
    ephid = ephid_from_seed(bytes.fromhex(SEED1))
    for time in [TIME0, TIME1, TIME2]:
        epoch = epoch_from_time(time)
        print(" - EphID:", ephid.hex())
        print(" - Time:", time.isoformat(" "))
        print(" - Epoch:", epoch)
        print(
            " - Hashed observation:", hashed_observation_from_ephid(ephid, epoch).hex()
        )
        print()


if __name__ == "__main__":
    main()
