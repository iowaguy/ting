#!/bin/bash

TOR_VERSION=0.4.4.6

install_deps() {
  sudo apt-get update
  sudo apt-get install --yes \
       wget sudo gcc libevent-dev libssl-dev wget \
       zlib1g-dev make openssl python3 python3-pip
  pip3 install stem PySocks
}

setup() {
  mkdir tor/
  cd tor/
  wget https://dist.torproject.org/tor-0.4.4.6.tar.gz
  tar -xzvf tor-0.4.4.6.tar.gz
  cd ..

  # Setup dirs
  mkdir cache results
}

build_tor() {
  cd tor
  mkdir data logs pids configs

  pushd tor-${TOR_VERSION}/
  ./configure && make -j8
  popd
}

install_deps
setup
build_tor
