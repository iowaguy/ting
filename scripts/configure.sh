#!/bin/bash

# Get our public ip address
MY_PUBLIC_IP=$(wget http://ipinfo.io/ip -qO -)

cd tor

# Generate torrc files
cat <<EOF > ./configs/torrc-client
AvoidDiskWrites 1
ControlPort 9051
CookieAuthentication 1

CircuitBuildTimeout 10
LearnCircuitBuildTimeout 0
DataDirectory $PWD/data/client
DirPort 9030
ORPort 9500
DirReqStatistics 0
UseMicrodescriptors 0
ExitPolicy reject *:*
Log notice file $PWD/logs/client.log
SocksListenAddress 127.0.0.1
SocksPort 9050
WarnUnsafeSocks 0
PublishServerDescriptor 0
RunAsDaemon 1
EOF

cat <<EOF > ./configs/torrc-w
AvoidDiskWrites 1
ControlPort 9151
CookieAuthentication 1

LearnCircuitBuildTimeout 0
DataDirectory $PWD/data/w
ORPort 9001
DirReqStatistics 0
UseMicroDescriptors 0
DownloadExtraInfo 1
Log notice file $PWD/logs/w.log
SocksListenAddress 127.0.0.1
SocksPort 9150
WarnUnsafeSocks 0
ExitPolicyRejectPrivate 0
Exitpolicy accept $MY_PUBLIC_IP:16667,reject *:*
RunAsDaemon 1
PublishServerDescriptor 1
EOF

cat <<EOF > ./configs/torrc-z
AvoidDiskWrites 1
ControlPort 9251
CookieAuthentication 1
LearnCircuitBuildTimeout 0

DataDirectory $PWD/data/z
ORPort 9002
DirReqStatistics 0
UseMicroDescriptors 0
DownloadExtraInfo 1
Log notice file $PWD/logs/z.log
SocksListenAddress 127.0.0.1
SocksPort 9250
WarnUnsafeSocks 0
ExitPolicyRejectPrivate 0
Exitpolicy accept $MY_PUBLIC_IP:16667, reject *:*
RunAsDaemon 1
PublishServerDescriptor 1
EOF

# make data dirs for w, z and client
mkdir data/w data/z data/client

# Start Tor
tor-0.4.4.6/src/app/tor -f configs/torrc-client
# tor-0.4.4.6/src/app/tor -f configs/torrc-w
# tor-0.4.4.6/src/app/tor -f configs/torrc-z

cd ..

# Give them some time to start up
sleep 5

# Determine the fingerprint of W and Z
# FP_W=$(cat ./tor/data/w/fingerprint | cut -f2 -d" ")
# FP_Z=$(cat ./tor/data/z/fingerprint | cut -f2 -d" ")
FP_C=$(cat ./tor/data/client/fingerprint | cut -f2 -d" ")


############
### TING ###
############

# Generate default tingrc file
# cat <<EOF > ./tingrc
# SocksPort 9050
# ControllerPort 9051
# SourceAddr $MY_PUBLIC_IP
# DestinationAddr $MY_PUBLIC_IP
# DestinationPort 16667
# NumSamples 200
# NumRepeats 1
# W $MY_PUBLIC_IP,$FP_W
# Z $MY_PUBLIC_IP,$FP_Z
# C $MY_PUBLIC_IP,$FP_C
# EOF

# Generate default tingrc file
cat <<EOF > ./tingrc
SocksPort 9050
ControllerPort 9051
SourceAddr $MY_PUBLIC_IP
DestinationAddr $MY_PUBLIC_IP
DestinationPort 16667
NumSamples 200
NumRepeats 1
W moria.csail.mit.edu,9695DFC35FFEB861329B9F1AB04C46397020CE31
Z 46.165.245.154,749EF4A434DFD00DAB31E93DE86233FB916D31E3
C $MY_PUBLIC_IP,$FP_C
EOF


nohup ./echo_server &
