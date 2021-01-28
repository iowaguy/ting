FROM ubuntu:20.04

WORKDIR /root

RUN apt-get update &&\
    apt-get install --yes \
            wget sudo gcc libevent-dev libssl-dev wget \
            zlib1g-dev make openssl python3 python3-pip

ARG TOR_VERSION=0.4.4.6
ENV TOR_VERSION=$TOR_VERSION
RUN wget https://dist.torproject.org/tor-$TOR_VERSION.tar.gz &&\
    tar -xzvf tor-$TOR_VERSION.tar.gz

RUN cd tor-$TOR_VERSION/ &&\
    ./configure &&\
    make -j8 &&\
    cd ..

EXPOSE 9001 9030 9051 9050
COPY scripts/docker-entrypoint.sh scripts/

ENTRYPOINT ["scripts/docker-entrypoint.sh"]
CMD ["relay"]
