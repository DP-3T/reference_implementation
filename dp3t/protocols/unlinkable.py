"""
Reference implementation of the unlinkable DP3T design
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

import hashlib
import secrets
import datetime

from cuckoo.filter import CuckooFilter

from dp3t.config import RETENTION_PERIOD, EPOCH_LENGTH, NUM_EPOCHS_PER_DAY, LENGTH_EPHID


#################################
### GLOBAL PROTOCOL CONSTANTS ###
#################################

#: FPR for CuckooFilter
CUCKOO_FPR = 2 ** -42


#########################
### UTILITY FUNCTIONS ###
#########################


def epoch_from_time(time):
    """Compute the epoch number given a time

    Computes the number of epochs since the UNIX Epoch and uses that as a counter.

    Args:
        time (:obj:`datetime`): A date-time instance
    """
    return int(time.timestamp() // (EPOCH_LENGTH * 60))


#########################################
### BASIC CRYPTOGRAPHIC FUNCTIONALITY ###
#########################################


def generate_new_seed():
    """Return a fresh random seed"""
    return secrets.token_bytes(32)


def ephid_from_seed(seed):
    """Compute the EphID given a seed

    Args:
        seed (byte array): A 32-byte seed
    """
    raw_bytes = hashlib.sha256(seed).digest()
    return raw_bytes[:LENGTH_EPHID]


def hashed_observation_from_ephid(ephid, epoch):
    """Compute the hashed observation for a given epoch

    Computes SHA256(EphID || i) where i is the given epoch. Encoding is as
    follows:

      * First 16 bytes are the EphID
      * Next 4 bytes are the epoch number in BigEndian order

    Args:
        ephid (byte array): The observed EphID
        time (:obj:`datetime`): Time of observation
    """
    epoch_bytes = epoch.to_bytes(4, "big")
    result = hashlib.sha256(ephid + epoch_bytes).digest()
    return result


def hashed_observation_from_seed(seed, epoch):
    """Compute the hashed observation given a seed and epoch

    See :func:`hashed_observation_from_ephid`

    Args:
        ephid (byte array): The observed EphID
        epoch (:obj:`datetime.datetime`): Time epoch of observation
    """
    ephid = ephid_from_seed(seed)
    return hashed_observation_from_ephid(ephid, epoch)


#############################################################
### TYING CRYPTO FUNCTIONS TOGETHER FOR TRACING/RECORDING ###
#############################################################


class TracingDataBatch:
    """
    Simple representation of a batch of keys that is downloaded from
    the backend server to the phone at regular intervals.

    Contrary to the low-cost design, the release time is not needed to prevent
    replay attacks.

    *Example only.* This data structure uses a simple Python cuckoo filter to
    hold the hashed observations. We did not thoroughly check this library.
    Final implementations must at the very least use a portable and
    well-specified version of such a cuckoo filter.
    """

    def __init__(self, tracing_seeds, release_time=None):
        """Create a published batch of tracing keys

        Args:
            tracing_seeds ([(reported_epochs, seeds)]): A list of reported epochs/seeds
                per infected user
            release_time (optional): Release time of this batch
        """

        # Compute size of filter and ensure we have enough capacity
        nr_items = sum([len(epochs) for (epochs, _) in tracing_seeds])
        capacity = int(nr_items * 1.2)

        self.infected_observations = CuckooFilter(capacity, error_rate=CUCKOO_FPR)
        for (epochs, seeds) in tracing_seeds:
            for (epoch, seed) in zip(epochs, seeds):
                self.infected_observations.insert(
                    hashed_observation_from_seed(seed, epoch)
                )

        self.release_time = release_time


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
     * All internal times are epoch counters, starting from the start of UNIX
       epoch (see :func:`epoch_from_time`)

    All external facing interfaces use datetime.datetime objects.
    """

    def __init__(self, start_time=None):
        """Create an new App object and initialize

        Args:
            start_time (:obj:`datetime.datetime`, optional): Start of the first day
                The default value is the start of the current day.
        """

        # Store seeds and EphIDs per epoch
        self.seeds_per_epoch = {}
        self.ephids_per_epoch = {}

        # For each day, a list of observed hashed EphIDs
        self.observations_per_day = {}

        if start_time is None:
            start_time = datetime.datetime.now()
            start_time = start_time.replace(hour=0, minute=0, second=0, microsecond=0)

        self.start_of_today = start_time

        self._create_new_day_ephids()

    @property
    def today(self):
        """The current day (datetime.date)"""
        return self.start_of_today.date()

    def _create_new_day_ephids(self):
        """Compute a new set of seeds and ephids for a new day"""

        # Generate fresh seeds and store them
        seeds = [generate_new_seed() for _ in range(NUM_EPOCHS_PER_DAY)]
        ephids = [ephid_from_seed(seed) for seed in seeds]

        # Convert to epoch numbers
        first_epoch = epoch_from_time(self.start_of_today)

        # Store seeds and compute EphIDs
        for relative_epoch in range(0, NUM_EPOCHS_PER_DAY):
            self.seeds_per_epoch[first_epoch + relative_epoch] = seeds[relative_epoch]
            self.ephids_per_epoch[first_epoch + relative_epoch] = ephids[relative_epoch]

    def next_day(self):
        """Setup seeds and EphIDs for the next day, and do housekeeping"""

        # Update current day
        self.start_of_today = self.start_of_today + datetime.timedelta(days=1)

        # Generate new EphIDs for new day
        self._create_new_day_ephids()

        # Remove old observations
        last_retained_day = self.today - datetime.timedelta(days=RETENTION_PERIOD)
        old_days = [day for day in self.observations_per_day if day < last_retained_day]
        for day in old_days:
            del self.observations_per_day[day]

        # Remove old seeds and ephids
        days_back = datetime.timedelta(days=RETENTION_PERIOD)
        last_valid_time = self.start_of_today - days_back
        last_retained_epoch = epoch_from_time(last_valid_time)

        old_epochs = [
            epoch for epoch in self.seeds_per_epoch if epoch < last_retained_epoch
        ]
        for epoch in old_epochs:
            del self.seeds_per_epoch[epoch]
            del self.ephids_per_epoch[epoch]

    def get_ephid_for_time(self, time):
        """Return the EphID corresponding to the requested time

        Args:
            time (:obj:`datetime.datetime`): The requested time

        Raises:
            ValueError: If the requested ephid is unavailable
        """
        # Convert to epoch number
        epoch = epoch_from_time(time)

        if epoch not in self.ephids_per_epoch:
            raise ValueError("EphID not available, did you call next_day()?")

        return self.ephids_per_epoch[epoch]

    def add_observation(self, ephid, time):
        """Add ephID to list of observations. Time must correspond to the current day

        Args:
            ephID (byte array): the observed ephID
            time (:obj:`datatime.datetime`): time of observation

        Raises:
            ValueError: If time does not correspond to the current day
        """

        if self.today not in self.observations_per_day:
            self.observations_per_day[self.today] = []

        if not time.date() == self.today:
            raise ValueError("Observation must correspond to current day")

        epoch = epoch_from_time(time)
        hashed_observation = hashed_observation_from_ephid(ephid, epoch)
        self.observations_per_day[self.today].append(hashed_observation)

    def get_tracing_seeds_for_epochs(self, reported_epochs):
        """Return the seeds corresponding to the requested epochs

        Args:
            reported_epochs: The requested epochs for contagion reporting

        Raises:
            ValueError: If a requested epoch is unavailable
        """
        seeds = []
        try:
            seeds = [self.seeds_per_epoch[epoch] for epoch in reported_epochs]
        except KeyError:
            raise ValueError("A requested epoch is not available")

        return seeds

    def get_tracing_information(self, first_contagious_time, last_contagious_time=None):
        """Return the seeds corresponding to the requested time range

        *Warning:* This function should not be used to retrieve tracing
        information for future epochs to limit the amount of linking
        information available to the server. Unfortunately, this class does not
        have a notion of the exact time, so it is up to the caller to verify
        this constraint.

        Args:
            first_contagious_time (:obj:`datetime.datetime`): The time from which we
                 should start tracing
            last_contagious_time (:obj:`datatime.datatime`, optional): The last time
                 for tracing. Default value: the beginning of the current day.

        Returns:
            epochs: the epochs
            seeds: the corresponding seeds

        Raises:
            ValueError: If the requested key is unavailable or if
                last_contagious_time is before first_contagious_time
        """

        if last_contagious_time is None:
            last_contagious_time = self.start_of_today

        if last_contagious_time < first_contagious_time:
            raise ValueError(
                "Last_contagious_time should be after first_contagious_time"
            )

        start_epoch = epoch_from_time(first_contagious_time)
        end_epoch = epoch_from_time(last_contagious_time)
        reported_epochs = range(start_epoch, end_epoch + 1)

        return reported_epochs, self.get_tracing_seeds_for_epochs(reported_epochs)

    def matches_with_batch(self, batch):
        """Check for contact with infected person given a published filter

        Args:
            infected_observations: A (compact) representation of hashed
                observations belonging to infected persons

        Returns:
            int: How many EphIDs of infected persons we saw
        """

        seen_infected_ephids = 0

        for (_, hashed_observations) in self.observations_per_day.items():
            for hashed_observation in hashed_observations:
                if hashed_observation in batch.infected_observations:
                    seen_infected_ephids += 1

        return seen_infected_ephids
