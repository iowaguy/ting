#!/bin/bash

TOR_VERSION=0.4.4.6

install_deps() {
  apt-get update
  apt-get install --yes \
          wget sudo gcc libevent-dev libssl-dev \
          zlib1g-dev make openssl python3 python3-pip
  pip3 install stem PySocks
}

setup() {
  if [[ "x${DOCKER_BUILD}" != "x1" ]]; then
    cd tor/
    tar -zxvf tor-0.4.4.6.tar.gz
    cd ..
  fi

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
