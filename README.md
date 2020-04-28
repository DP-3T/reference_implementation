# Cryptographic Reference Implementation of DP3T designs

The full set of documents for DP3T is at <https://github.com/DP-3T/documents>.
Please refer to the technical documents and whitepapers for the descriptions
of the implementation.

*This repository implements both proximity tracing designs from the
white-paper.* In both designs, smartphones broadcast ephemeral Bluetooth
identifiers (`EphID`s), and store the identifiers received from other devices.
The designs differ in how they generate these `EphID`s and how they do proximity
tracing:

 * *Low-cost design*. In this design, `EphID`s are generated from a rotating
   seed `SKt` for efficiency. When an app owner is diagnosed with SARS-CoV-2,
   their app uploads the corresponding seed `SKt`. Other apps use this seed to
   regenerate the ephemeral Bluetooth identifiers, and check if they have seen
   an identifier corresponding to an infected person.
 * *Unlinkable design*. In this design, `EphID`s are generated independently
   from random seeds. When an app owner is diagnosed with SARS-CoV-2, their app
   uploads the corresponding seeds for each `EphID` broadcast in a compact
   representation. Other apps use this compact representation to check if they
   have seen an identifier corresponding to an infected person.
 
*Difference with respect to the Android/iOS SDKs and backend implementations.*
The DP-3T project has also published
[Android](https://github.com/DP-3T/dp3t-sdk-android) and
[iOS](https://github.com/DP-3T/dp3t-sdk-ios) implementations and a [backend
SDK](https://github.com/DP-3T/dp3t-sdk-backend) for use in production apps and
backends. This reference implementation serves to provide a simple
implementation that complements the white paper. We try to avoid differences
between this Python reference implementations and the other implementations, but
small differences are unavoidable due to the speed at which this project
progresses.

*Example implementations of App and Backend.* We plan to soon extend this
repository with example implementations of the App and Backend server. The App
implementation will show how smartphones interact with the backend server's API
to upload tracing information, to retrieve tracing information, and to do
contact tracing.

## The code

This reference implementation is deliberately simple. It aims to provide a clear
and simple implementation of the cryptographic concepts from the whitepaper and
to show how these tie together.

The package `dp3t.config` contains global configuration parameters shared
between all designs. The package `dp3t.protocols` contains the reference
implementations `lowcost` and `unlinkable` for the low-cost and unlinkable
designs. These files follow a similar structure:

 1. They introduce design-specific parameters such as the length of a batch.
 2. They define utility functions to convert time to internal representations
 2. They define simple cryptographic functions used to generate seeds and `EphIDs`
 3. The class `TracingDataBatch` represents the information downloaded from the
    server. Both designs use the same interface for this class.
 3. The class `ContactTracer` ties these functions together and sketches the
    core contact tracing functionality that would be used by a smartphone
    contact tracing app. The class takes care of rotating keys (`next_day`),
    generating `EphID`s to broadcast, to output `EphID` given a specific time
    (`get_ephid_for_time`), to process an observation (`add_obseration`), to
    output tracing information (`get_tracing_information`), and to process a
    batch of tracing information to determine the number of contacts with
    infected people (`matches_with_batch`). Both designs use the same interface
    for this class
    
This code deliberately does _not_ implement any interactions with (simulated)
Bluetooth devices or backend services.
    
## Installing the reference implementation

You'll need to install the project. For example as follows:

```bash
python3 -m venv venv
source venv/bin/activate
pip3 install -e .
```

## Running the example

After installing the project you can run the examples:

```bash
examples/run_lowcost.py
examples/run_unlinkable.py
```

## Obtaining test vectors

After installing the project you can obtain test vectors by running:

```bash
utils/testvectors_lowcost.py
utils/testvectors_unlinkable.py
```

## Development

For development, you should install the development and test dependencies:

```bash
pip install -e ".[dev,test]"
```

You should also install the proper pre-commit-hooks so that the files stay
formatted:

```bash
pip install pre-commit
pre-commit install
```

### Running the tests

To run the tests, simply call

```bash
pytest
```

If you just installed the test dependencies, you may need to reload the `venv`
(`deactivate` followed by `source venv/bin/ativate`) to ensure that the paths
are picked up correctly.

## License

This code is licensed under the Apache 2.0 license, as found in the LICENSE
file.
