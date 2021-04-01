#!/usr/bin/env bash

## install dependencies
sudo apt-get update -y

sudo apt-get install -y\
     cmake\
     gcc\
     g++\
     libc-dbg\
     libglib2.0-dev\
     libigraph-dev\
     make\
     automake\
     autoconf\
     python3\
     python3-pyelftools\
     xz-utils\
     autotools-dev\
     libevent-dev\
     libssl-dev\
     zlib1g\
     python3-numpy\
     python3-lxml\
     python3-matplotlib\
     python3-networkx\
     python3-scipy\
     python3-pip\
     dstat\
     git\
     htop\
     screen\
     emacs

pip3 install stem PySocks protobuf
