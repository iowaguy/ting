#!/bin/bash

apt-get update
apt-get install --yes wget sudo gcc libevent-dev libssl-dev zlib1g-dev make openssl python
wget https://bootstrap.pypa.io/get-pip.py
python get-pip.py
pip install stem

if [[ "x${DOCKER_BUILD}" != "x1" ]]; then
  cd tor/
  tar -zxvf tor-0.4.4.6.tar.gz
  cd ..
fi

# Setup dirs
mkdir cache results

###########
### TOR ###
###########

cd tor

mkdir data logs pids configs

tar -zxvf tor-0.4.4.6.tar.gz
cd tor-0.4.4.6/
./configure && make
cd ..
