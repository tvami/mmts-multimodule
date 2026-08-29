# HGCal GTB-SCA Software

## uhal

Both python and c++ versions need uhal installed:

visit https://gitlab.cern.ch/hgcal-daq-sw/ipbus-software  (branch: asteen/UIO-hgcal-dev) for installation instructions.

## Python version:

For the python version, you should only need uhal installed. Then you can run
```bash
source env.sh
```
From this directory and import the gbtsca into python as demonstrated in gbtsca_bus_test.py. 

## C++ version:

## Pre-requisites:

- some libraries:
```bash
yum install epel-release
yum update
yum install cmake zeromq zeromq-devel cppzmq-devel libyaml libyaml-devel yaml-cpp yaml-cpp-devel boost boost-devel
```

### Basic installation of gbtsca-sw on the zynq:
```bash
git clone ssh://git@gitlab.cern.ch:7999/hgcal-daq-sw/gbt-sca-sw.git
cd gbt-sca-sw
mkdir build
cd build
cmake ../
make install
cd ../
source env.sh
```

## Some examples

- Test GBT-SCA connection using c++ directly:
```bash
./bin/gbtsca_test
```
- Test python version:
```bash
python3 gbtsca_bus_test.py
```
Should print out the device ID of the sca you point it to.
