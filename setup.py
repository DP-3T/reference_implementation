import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="dp3t-python-reference",
    version="0.0.1",
    author="EPFL",
    description="DP3T Python Reference Implementation",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/dp-3t/dp3t-python-reference",
    packages=setuptools.find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License"
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
    install_requires=["pycryptodomex", "scalable-cuckoo-filter"],
    extras_require={"dev": ["black", "flake8", "pre-commit"], "test": ["pytest"]},
)
