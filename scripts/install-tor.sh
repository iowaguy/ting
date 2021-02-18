#!/bin/bash -e

TOR_VERSION=tor-0.4.4.7

git clone https://gitlab.torproject.org/tpo/core/tor.git
cd tor/
git checkout ${TOR_VERSION}

sh autogen.sh
./configure --disable-asciidoc
make -j$(nproc)
sudo make install
