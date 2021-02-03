FROM ubuntu:20.04

WORKDIR /root

RUN apt-get update &&\
    apt-get install --yes \
            wget sudo gcc libevent-dev libssl-dev wget \
            zlib1g-dev make openssl python3 python3-pip \
            net-tools autotools-dev automake git

ARG TOR_VERSION=tor-0.4.4.6
ENV TOR_VERSION=$TOR_VERSION

RUN git clone https://git.torproject.org/tor.git &&\
    cd tor/ &&\
    git checkout $TOR_VERSION

COPY allow-internal-ips.patch tor/

RUN cd tor/ &&\
    git apply allow-internal-ips.patch &&\
    ./autogen.sh &&\
    ./configure --disable-asciidoc --disable-dependency-tracking &&\
    make -j8 &&\
    cd ..

COPY scripts/docker-entrypoint.sh scripts/

ENTRYPOINT ["scripts/docker-entrypoint.sh"]
