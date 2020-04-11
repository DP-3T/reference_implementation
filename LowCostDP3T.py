#!/usr/bin/env python3
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

from Cryptodome.Util import Counter
from Cryptodome.Cipher import AES
import hashlib
import hmac
import secrets
import random
from datetime import datetime, timezone, timedelta

# Fixed global default broadcast key for ephID generation.
BROADCAST_KEY = "Broadcast key"

# Length of an epoch (in minutes).
EPOCH_LENGTH = 15

# Number of epochs per day.
NUM_EPOCHS_PER_DAY = 24*60//EPOCH_LENGTH

# Duration key and contact history is kept (in days).
RETENTION_PERIOD = 14

# Min number of observation seconds for a contact
CONTACT_THRESHOLD = 120


# Local key management and storage
##################################
class KeyStore:
	''' This class handles local key management (SKs and EphIDs).
		The set of previous SKs is kept in a local array (up to max length).
		The set of EphIDs for the current day is kept in another array.
	'''

	def __init__(self):
		self.SKt = [] 		# Current set of SKts
		self.ephIDs = [] 	# Daily set of ephIDs
		# Initial key is created from true random value
		self.SKt.insert(0, secrets.token_bytes(32))
		self.rotate_ephIDs()

	@staticmethod
	def get_SKt1(SK_t0):
		''' Updates a given SK_t to SK_t+1.

			This method creates the next key in the chain of SK_t's.
			This method is called either for the local rotation or when we
			recover the different SK_ts from an infected person.

			Arguments:
				SK(list): current SK_t (b"rand" * 32).

			Returns:
				b[]: The next SK (SK_t+1).
		'''
		SK_t1 = hashlib.sha256(SK_t0).digest()
		return SK_t1

	def rotate_SK(self):
		''' Create a new SK_t+1 based on SK_t.

			This method updates the current key and moves on to the next day.
			This method is called at midnight UTC.
		'''
		SK_t1 = KeyStore.get_SKt1(self.SKt[0])
		self.SKt.insert(0, SK_t1)
		# truncate list to max days
		while len(self.SKt) > RETENTION_PERIOD:
			self.SKt.pop()

	@staticmethod
	def create_ephIDs(SK):
		''' Create the set of beacons for the day based on a new SK_t.

			This method created the set of ephemeral IDs given an SK for
			day / broadcast_key.

			Arguments:
				SK(b[]): given SK (b"rand" * 32)

			Returns:
				[b[]]: Set of ephemeral IDs (ephIDs) for a single day.
		'''
		# Set up PRF with the SK and broadcast_key
		prf = hmac.new(SK, BROADCAST_KEY.encode(), hashlib.sha256).digest()
		# Start with a fresh counter each day and initialize AES in CTR mode
		prg = AES.new(prf, AES.MODE_CTR, counter = Counter.new(128, initial_value=0))
		ephIDs = []

		# Create the number of desired ephIDs by encrypting 0 bytes
		prg_data = prg.encrypt(b"\0" * 16 * NUM_EPOCHS_PER_DAY)
		for i in range(NUM_EPOCHS_PER_DAY):
			# split the prg data into individual ephIDs
			ephIDs.append(prg_data[i*16:i*16+16])
		return ephIDs

	def rotate_ephIDs(self):
		''' Generate the daily set of EphIDs.

			This method creates the set of ephIDs for the app to broadcast.
			We shuffle this set before returning it back to the app.
			This method updates the local set of ephIDs, epoch indexes into set.
			Executed once per day, at 0:00 UTC
		'''
		ephIDs = self.create_ephIDs(self.SKt[0])
		# TODO: random.shuffle is not cryptographically secure!
		#       The real app will use a cryptographic secure shuffle
		random.shuffle(ephIDs)
		self.ephIDs = ephIDs

	def get_epoch(self, now):
		''' Return the current epoch.
			now: time mapped to epoch
		'''
		offset = now.hour*60 + now.minute
		delta = 24*60 // NUM_EPOCHS_PER_DAY
		return offset//delta

	def get_current_ephID(self, now = None):
		''' Returns the current ephID
		'''
		if now is None:
			now = datetime.now(timezone.utc)
		return self.ephIDs[self.get_epoch(now)]


# Handle and manage contacts
############################
class ContactManager:
	''' Keep track of contacts and manage measurements
	'''

	def __init__(self):
		self.observations = {}	# Observations of the current epoch
		self.contacts = [{}]	# Array of daily contact sets

	# Remote beacon management
	##########################
	def receive_scans(self, beacons = None, now = None):
		''' Receive a set of new BLE beacons and process them.

			Add the current received information to the observations for the
			current epoch.

			Arguments:
				beacons([]): list of received beacons.
				now(datetime): current time, override for mock testing.
		'''
		if beacons is None:
			beacons = []

		if now is None:
			now = datetime.now(timezone.utc)

		timestamp = (now.hour*60 + now.minute)*60 + now.second
		for beacon in beacons:
			self.add_observation(beacon, timestamp)


	# Contact management and proximity logger
	#########################################
	def add_observation(self, beacon, timestamp):
		''' Adds a new contact observation to the current epoch.

			Arguments:
				beacon(b[]): observed beacon.
				timestamp(int): offset to beginning of UTC 0:00 in seconds.
		'''
		if beacon in self.observations:
			self.observations[beacon].append(timestamp)
		else:
			self.observations[beacon] = [timestamp]

	def rotate_contacts(self):
		''' Move to the next day for contacts.

			Create a new empty set of contacts, update and truncate history.
		'''
		self.contacts.insert(0, {})
		# truncate history
		while len(self.contacts) > RETENTION_PERIOD:
			self.contacts.pop()

	def process_epoch(self):
		''' Process observations/epoch, add to contact set if >threshold.

			Iterate through all observations and identify which observations
			are above a threshold, i.e., turn the set of observations into a
			set of minimal contacts. This process aggregates multiple
			observations into a contact of a given duration. As a side effect,
			this process drops timing information (i.e., when the contact
			happened and only stores how long the contact lasted).
		'''
		for beacon in self.observations:
			# TODO: as of now, we subtract the last observation from the first
			#       and use this as overall timestamp. The real app will use a
			#       elaborate way to identify a contact, e.g., by averaging and
			#       adding some statistical modeling across all timestamps.
			if len(self.observations[beacon]) >= 2:
				duration = self.observations[beacon][-1] - self.observations[beacon][0]
				if duration > CONTACT_THRESHOLD:
					self.contacts[0][beacon] = duration
		self.observations = {}


	# Update infected and local risk scoring
	########################################
	def check_infected(self, inf_SK0, date, now = None):
		''' Checks if our database was exposed to an infected SK starting on date.

			NOTE: this implementation uses the date of the SK_t to reduce the
			number of comparisons. The backend needs to store <SK, date> tuples.

			Check if we recorded a contact with a given SK0 across in our
			database of contact records. This implementation assumes we are
			given a date of infection and checks on a per-day basis.

			Arguments
				infSK0(b[]): SK_t of infected
				date(str): date of SK_t (i.e., the t in the form 2020-04-23).
				now(datetime): current date for mock testing.
		'''
		if now is None:
			now = datetime.now(timezone.utc)
		infect_date = datetime.strptime(date, "%Y-%m-%d")
		days_infected = (now-infect_date).days
		inf_SK = inf_SK0
		for day in range(days_infected, -1, -1):
			# Create infected EphIDs and rotate infected SK
			infected_ephIDs = KeyStore.create_ephIDs(inf_SK)
			inf_SK = KeyStore.get_SKt1(inf_SK)

			# Do we have observations that day?
			if len(self.contacts)<=day or len(self.contacts[day]) == 0:
				continue

			# Go through all infected EphIDs and check if we have a hit
			for inf_ephID in infected_ephIDs:
				# Hash check of infected beacon in set of daily contacts
				if inf_ephID in self.contacts[day]:
					duration = self.contacts[day][inf_ephID]
					print("At risk, observed {} on day -{} for {}".format(inf_ephID.hex(), day, duration))


# Mock Application that ties contact manager and keystore together
##################################################################
class MockApp:
	def __init__(self):
		''' Initialize the simple mock app, create an SK/ephIDs.
		'''
		self.keystore = KeyStore()
		self.ctmgr = ContactManager()

	def next_day(self):
		# Rotate keys daily
		# ASSERT(This function is executed at 0:00 UTC)
		self.keystore.rotate_SK()
		self.keystore.rotate_ephIDs()
		self.ctmgr.rotate_contacts()

	def next_epoch(self):
		self.ctmgr.process_epoch()
