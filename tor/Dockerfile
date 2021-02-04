FROM ubuntu:20.04

WORKDIR /root

RUN apt-get update &&\
    apt-get install --yes \
            wget sudo gcc libevent-dev libssl-dev wget \
            zlib1g-dev make openssl python3 python3-pip \
            net-tools autotools-dev automake git pwgen

ARG TOR_VERSION=tor-0.4.4.6
ENV TOR_VERSION=$TOR_VERSION

# RUN git clone https://git.torproject.org/tor.git &&\
#     cd tor/ &&\
#     git checkout $TOR_VERSION

RUN wget https://dist.torproject.org/$TOR_VERSION.tar.gz &&\
    tar -xzvf $TOR_VERSION.tar.gz
# ARG PATCH_FILE=changes-for-running-locally.patch
# COPY $PATCH_FILE tor/

RUN cd $TOR_VERSION &&\
#    git apply $PATCH_FILE &&\
    # ./autogen.sh &&\
    ./configure --disable-asciidoc --disable-dependency-tracking &&\
    make -j8 &&\
    cd ..

COPY scripts/docker-entrypoint.sh scripts/

ENTRYPOINT ["scripts/docker-entrypoint.sh"]
