#!/usr/bin/env python3

""" Produces test vectors for the lowcost DP-3T design """

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

from dp3t.protocols.lowcost import next_day_key, generate_ephids_for_day

KEY0 = bytes.fromhex("0000000000000000000000000000000000000000000000000000000000000000")


def main():
    print("## Test vectors of keys and generated EphIDs ##")
    print("   WARNING: shuffling is disabled to obtain stable test vectors")
    print("            implementations should broadcast the EphIDS in random order.\n")
    key = KEY0
    for i in range(3):
        print("  * Key: SK_[t + {}] = {}".format(i, key.hex()))
        ephids = generate_ephids_for_day(key, shuffle=False)
        for j in [0, 1, 2, 95]:
            print("    - ephid[{}] = {}".format(j, ephids[j].hex()))
        key = next_day_key(key)


if __name__ == "__main__":
    main()
