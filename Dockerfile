FROM ubuntu:20.04

WORKDIR /root
ENV DOCKER_BUILD=1

COPY echo_server /root/
COPY libs/ /root/libs/
COPY tor/ /root/tor/
ADD tor/tor-0.4.4.6.tar.gz /root/tor/

COPY build.sh /root/
RUN ./build.sh

# COPY ting /root/
COPY configure.sh /root/
