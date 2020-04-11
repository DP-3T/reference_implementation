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

import time
from datetime import datetime, timedelta

import LowCostDP3T

if __name__ == "__main__":

	# Mock time starts midnight on April 01.
	epotime = datetime.timestamp(datetime.strptime("2020-04-01", "%Y-%m-%d"))
	
	# We have three people: Alice, Bob, and Isidor
	alice = LowCostDP3T.MockApp()
	bob = LowCostDP3T.MockApp()
	isidor = LowCostDP3T.MockApp()

	# Run tests for the specified number of days
	for day in range(2):
		print("Day: Alice, Bob, and Isidor do not have contact.")
		epotime += 24*60*60
		alice.next_day()
		bob.next_day()
		isidor.next_day()

	for day in range(3):
		print("Day: Alice and Bob work in the same office, Isidor elsewhere.")
		for hour in range(8, 17):
			time = epotime + hour*60*60
			# We break each hour into epochs
			for epoch in range(60//LowCostDP3T.EPOCH_LENGTH):
				now = datetime.utcfromtimestamp(epotime)
				alice_ephID = alice.keystore.get_current_ephID(now)
				bob_ephID = bob.keystore.get_current_ephID(now)
				# Record two beacons in the same epoch, resulting in a contact
				alice.ctmgr.receive_scans([bob_ephID], now = now)
				bob.ctmgr.receive_scans([alice_ephID], now = now)
				now = now + timedelta(seconds=LowCostDP3T.CONTACT_THRESHOLD+1)
				alice.ctmgr.receive_scans([bob_ephID], now = now)
				bob.ctmgr.receive_scans([alice_ephID], now = now)
				# Process the received beacons
				alice.next_epoch()
				bob.next_epoch()
		# Tik Tok
		epotime += 24*60*60
		alice.next_day()
		bob.next_day()
		isidor.next_day()        

	print("Day: Bob and Isidor meet for dinner.")
	for hour in range(17, 20):
		for epoch in range(60//LowCostDP3T.EPOCH_LENGTH):
			now = datetime.utcfromtimestamp(epotime)
			bob_ephID = bob.keystore.get_current_ephID(now)
			isidor_ephID = isidor.keystore.get_current_ephID(now)
			# Record two beacons in the same epoch, resulting in a contact
			bob.ctmgr.receive_scans([isidor_ephID], now = now)
			isidor.ctmgr.receive_scans([bob_ephID], now = now)
			now = now + timedelta(seconds=LowCostDP3T.CONTACT_THRESHOLD+1)
			bob.ctmgr.receive_scans([isidor_ephID], now = now)
			isidor.ctmgr.receive_scans([bob_ephID], now = now)
			# Process the received beacons
			alice.next_epoch()
			bob.next_epoch()
			isidor.next_epoch()

	print("Isidor is tested positive.")
	infectious_date = datetime.utcfromtimestamp(epotime)
	infections_SK = isidor.keystore.SKt[0]

	# Tik Tok
	epotime += 24*60*60
	alice.next_day()
	bob.next_day()
	isidor.next_day()

	# Check infectiousness
	print("Check exposure of Alice and Bob.")
	print("Alice: (not positive)")
	alice.ctmgr.check_infected(infections_SK, infectious_date.strftime("%Y-%m-%d"), datetime.utcfromtimestamp(epotime))
	print("Bob: (at risk)")
	bob.ctmgr.check_infected(infections_SK, infectious_date.strftime("%Y-%m-%d"), datetime.utcfromtimestamp(epotime))
