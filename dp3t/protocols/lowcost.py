"""
Reference implementation of the low-cost DP3T design
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

import datetime
import hashlib
import hmac
import secrets
import random

from Cryptodome.Util import Counter
from Cryptodome.Cipher import AES

from dp3t.config import (
    EPOCH_LENGTH,
    RETENTION_PERIOD,
    NUM_EPOCHS_PER_DAY,
    LENGTH_EPHID,
    SECONDS_PER_DAY,
)


#################################
### GLOBAL PROTOCOL CONSTANTS ###
#################################

#: Constant string "broadcast key" for domain seperation
BROADCAST_KEY = "broadcast key".encode("ascii")

#: Length of a batch (2 hours)
SECONDS_PER_BATCH = 2 * 60 * 60


#########################
### UTILITY FUNCTIONS ###
#########################


def day_start_from_time(time):
    """Return the first Unix epoch second of the day corresponding to time

    Args:
        datetime (obj:datetime.datetime): A datetime

    Returns:
        The first Unix epoch second on that day
    """
    return (int(time.timestamp()) // SECONDS_PER_DAY) * SECONDS_PER_DAY


def batch_start_from_time(time):
    """Return the first Unix epoch second of the batch corresponding to time

    Args:
        datetime (obj:datetime.datetime): A datetime

    Returns:
        The first Unix epoch second on that day
    """
    return (int(time.timestamp()) // SECONDS_PER_BATCH) * SECONDS_PER_BATCH


def secure_shuffle(items):
    """Perform a cryptographically secure shuffling of the given items

    Args:
        items (obj:list): A list of items to be shuffled

    Returns:
        Nothing. Items are shuffled in place
    """
    random.shuffle(items, secrets.SystemRandom().random)


#########################################
### BASIC CRYPTOGRAPHIC FUNCTIONALITY ###
#########################################


def generate_new_day_key():
    """Returns a fresh random key"""
    return secrets.token_bytes(32)


def next_day_key(current_day_key):
    """Computes key of the next day given current key

    Args:
        key (byte array): A 32-byte key

    Returns:
        byte array: The next 32-byte key
    """
    return hashlib.sha256(current_day_key).digest()


def generate_ephids_for_day(current_day_key, shuffle=True):
    """Generates the list of EphIDs for the current day

    Args:
        key (byte array): A 32-byte key
        shuffle (bool, optional): Whether to shuffle the list of EphIDs. Default: True.
            Should only be set to False when testing or when generating test vectors

    Returns:
        list of byte arrays: The list of EphIDs for the day
    """

    # Compute key for stream cipher based on current_day_key
    stream_key = hmac.new(current_day_key, BROADCAST_KEY, hashlib.sha256).digest()

    # Start with a fresh counter each day and initialize AES in CTR mode
    counter = Counter.new(128, initial_value=0)
    prg = AES.new(stream_key, AES.MODE_CTR, counter=counter)

    # Create the number of desired ephIDs by drawing from AES in CTR mode
    # operating a s a stream cipher. To get the raw output, we ask the library
    # to "encrypt" an all-zero message of sufficient length.
    prg_output_bytes = prg.encrypt(bytes(LENGTH_EPHID * NUM_EPOCHS_PER_DAY))

    ephids = [
        prg_output_bytes[idx : idx + LENGTH_EPHID]
        for idx in range(0, len(prg_output_bytes), LENGTH_EPHID)
    ]

    # Shuffle the resulting ephids
    if shuffle:
        secure_shuffle(ephids)

    return ephids


#############################################################
### TYING CRYPTO FUNCTIONS TOGETHER FOR TRACING/RECORDING ###
#############################################################


class TracingDataBatch:
    """
    Simple representation of a batch of keys that is downloaded from
    the backend server to the phone at regular intervals.
    """

    def __init__(self, time_key_pairs, release_time=None):
        """Create a published batch of tracing keys

        Args:
            time_key_pairs ([(time, byte array)]): List of tracing keys of
                infected people and the corresponding start times.
            release_time (int, optional): Release time in seconds since UNIX Epoch
                when missing, defaults to current time

        Raises:
            ValueError: if the release_time is not aligned to a batch boundary
        """
        if release_time is None:
            release_time = batch_start_from_time(datetime.datetime.now())

        if release_time % SECONDS_PER_BATCH != 0:
            raise ValueError("Release time must be batch-aligned")

        self.release_time = release_time
        self.time_key_pairs = time_key_pairs


class ContactTracer:
    """Simple reference implementation of the contact tracer.

    This class shows how the contact tracing part of a smartphone app would
    operate.

    *Simplification* This class simplifies recording of observations and
    computing the final risk score. Observations are represented by the
    corresponding EphID, and we omit proximity metrics such as duration and
    signal strength. Similarly, the risk scoring mechanism is simple. It only
    outputs the number of unique infected EphIDs that have been observed.

    Actual implementations will probably take into account extra information
    from the Bluetooth backend to do better distance measurements, and
    subsequently use this information to do a better risk computation.

    A note on internal data representation:
     * All internal times are in seconds since UNIX epoch
     * The start of each day is aligned with a day-boundary (i.e., multiples of
       86400 seconds)
     * Batches are aligned at batch boundaries (e.g., multiples of SECONDS_PER_BATCH)

    All external facing interfaces use datetime.datetime objects instead.
    """

    @staticmethod
    def _reconstruct_ephids(key, start_time, end_time):
        """Regenerate all EphIDs given start and end times

        Args:
            key (byte array): A 32-byte key
            start_time (int): In seconds since UNIX epoch (expect to be day aligned)
            end_time (int): In seconds since UNIX epoch (does not have to be day aligned)

        Returns:
            dictionary: For each day, start_date <= day <= end_date, a list of EphIDs
        """
        day = start_time

        ephids_per_day = {}
        while day <= end_time:
            ephids_per_day[day] = generate_ephids_for_day(key)

            key = next_day_key(key)
            day += SECONDS_PER_DAY

        return ephids_per_day

    def __init__(self, start_time=None):
        """Initialize a new contact tracer

        Args:
            start_time (:obj:`datetime.datetime`, optional): The current time
                The default value is the current time.
        """
        self.past_keys = []

        # For each day, a list of observed EphIDs
        self.observations = {}

        if start_time is None:
            start_time = datetime.datetime.now()
        self.start_of_today = day_start_from_time(start_time)

        # Generate initial day key
        self.current_day_key = generate_new_day_key()

        # Generate new batch of EphIDs
        self.current_ephids = generate_ephids_for_day(self.current_day_key)

    def next_day(self):
        """Setup keys and EphIDs for the next day, and do housekeeping"""

        # Keep a list of the past RETENTION_PERIOD keys
        self.past_keys.insert(0, self.current_day_key)
        self.past_keys = self.past_keys[:RETENTION_PERIOD]

        # Update the day key
        self.current_day_key = next_day_key(self.current_day_key)

        # Generate new batch of EphIDs
        self.current_ephids = generate_ephids_for_day(self.current_day_key)

        # Update current day
        self.start_of_today = self.start_of_today + SECONDS_PER_DAY

        # Remove old observations
        last_retained = self.start_of_today - RETENTION_PERIOD * SECONDS_PER_DAY
        delete_times = [time for time in self.observations if time < last_retained]
        for time in delete_times:
            del self.observations[time]

    def get_ephid_for_time(self, time):
        """Return the EphID corresponding to the requested time

        Args:
            time (:obj:`datetime.datetime`): The requested time

        Raises:
            ValueError: If the requested ephid is unavailable
        """
        # Check if we are on the current day
        day_start = day_start_from_time(time)
        if day_start != self.start_of_today:
            raise ValueError("Requested EphID not availavle. Did you call next_day()?")

        # Compute the corresponding epoch within the day
        epoch = (int(time.timestamp()) - day_start) // (EPOCH_LENGTH * 60)

        return self.current_ephids[epoch]

    def add_observation(self, ephid, time):
        """Add ephID to list of observations. Time must correspond to the current day

        Initially observations are stored with a receive time that has batch
        granularity. This enables us to verify whether an observation occurred
        before or after the corresponding key was released. The latter should
        be ignored. Once a :obj:`TracingDataBatch` with release time
        `release_time` has been processed, observations before `release_time`
        can be updated to have day granularity. See
        :func:`housekeeping_after_batch`.

        Args:
            ephID (byte array): the observed ephID
            time (:obj:`datatime.datetime`): time of observation

        Raises:
            ValueError: If time does not correspond to the current day
        """

        batch_start = batch_start_from_time(time)

        end_of_today = self.start_of_today + SECONDS_PER_DAY
        if not self.start_of_today <= batch_start < end_of_today:
            raise ValueError("Observation must correspond to current day")

        if batch_start not in self.observations:
            self.observations[batch_start] = []
        self.observations[batch_start].append(ephid)

        # Shuffle observations to hide receive order
        secure_shuffle(self.observations[batch_start])

    def get_tracing_information(
        self,
        first_contagious_time,
        last_contagious_time=None,
        reset_key_after_release=True,
    ):
        """Return the day key corresponding to first_contageous_time

        *Warning*: While this function accepts the optional
         `last_contagious_time` parameter, report a range is not supported by
         this protocol, and the value will be ignored.

        Args:
            first_contagious_time (:obj:`datetime.datetime`): The time from which we
                 should start tracing
            last_contagious_time (:obj:`datetime.datetime`, optional): This value is
                 IGNORED. It is here to present a compatible interface
            reset_key_after_release (:obj:`datetime.datetime`, optional):
                 Whether to pick a new key. Default is True to preserve privacy of
                 future beacons.

        Returns:
            (start_contagious_day, key)

        Raises:
            ValueError: If the requested key is unavailable
        """

        start_contagious_day = day_start_from_time(first_contagious_time)
        tracing_key = None

        nr_days_back = (self.start_of_today - start_contagious_day) // SECONDS_PER_DAY

        if nr_days_back > len(self.past_keys) or nr_days_back < 0:
            raise ValueError("The requested tracing key is not available")

        if nr_days_back == 0:
            tracing_key = self.current_day_key
        else:
            tracing_key = self.past_keys[nr_days_back - 1]

        ## Reset current day's key to a new value and regenerate EphIDs
        if reset_key_after_release:
            # Pick a new seed
            self.current_day_key = generate_new_day_key()

            # Generate new batch of EphIDs
            self.current_ephids = generate_ephids_for_day(self.current_day_key)

            # Destroy history, as it will no longer be valid
            self.past_keys = []

        return start_contagious_day, tracing_key

    def matches_with_key(self, key, start_time, release_time):
        """Count #contacts with infected person given person's day key

        Args:
            key (byte array): A 32-byte key of an infected person
            start_time (int): The first day (in UNIX epoch seconds) on which this key is valid
            release_time (int): The publication time of the key

        Returns:
            int: How many epochs we saw EphIDs of the infected person
        """

        ephids_per_day = self._reconstruct_ephids(key, start_time, release_time)

        nr_encounters = 0

        for time in self.observations:
            # Ignore observations on or after publication time of the key
            if time >= release_time:
                continue

            # Get start of the day corresponding to the time
            day = (time // SECONDS_PER_DAY) * SECONDS_PER_DAY

            # Skip if we don't have corresponding observations
            if day not in ephids_per_day:
                continue

            for ephid in ephids_per_day[day]:
                if ephid in self.observations[time]:
                    nr_encounters += 1

        return nr_encounters

    def matches_with_batch(self, batch):
        """Count #contacts with each infected person in batch

        Args:
            batch (`obj`:TracingDataBatch): A batch of tracing keys

        Returns:
            int: How many EphIDs of infected persons we saw
        """

        seen_infected_ephids = 0
        release_time = batch.release_time

        for (start_time, key) in batch.time_key_pairs:
            seen_infected_ephids += self.matches_with_key(key, start_time, release_time)

        return seen_infected_ephids

    def housekeeping_after_batch(self, batch):
        """Update stored observations after processing batch.

        This function *must* be run after processing each batch.

        Assumption: batches will be processed in order of release.

        This method updates the stored observations that have been observed
        before the release of the latest batch to now have day granularity. See
        also :func:`add_observation`
        """

        update_list = {}

        # Gather observations we should update
        for time in self.observations:
            if time < batch.release_time and time % SECONDS_PER_DAY != 0:
                update_list[time] = self.observations[time]

        # Delete these observations
        for time in update_list:
            del self.observations[time]

        # Reinsert gathered observations with day-granularity
        for (time, observations) in update_list.items():
            day_time = (time // SECONDS_PER_DAY) * SECONDS_PER_DAY

            if day_time not in self.observations:
                self.observations[day_time] = []

            self.observations[day_time].extend(observations)

            # Reshuffle to make sure we do not store ordering data
            secure_shuffle(self.observations[day_time])
