#!/bin/bash

# Get our public ip address
MY_PUBLIC_IP=$(wget http://ipinfo.io/ip -qO -)
TOR_VERSION=0.4.4.6

cd tor

# Generate torrc files
cat <<EOF > ./configs/torrc-auth
AuthoritativeDirectory 1
V3AuthoritativeDirectory 1
DirAllowPrivateAddresses 1
ContactInfo auth${hostname}@dontemail.me
ExitPolicy reject *:*
Log notice file $PWD/logs/auth.log
RunAsDaemon 1
AssumeReachable 1
TestingTorNetwork 1
DirPort localhost:9030
ExtendAllowPrivateAddresses 1
EOF

# Generate torrc files
cat <<EOF > ./configs/torrc-client
TestingTorNetwork 1

AvoidDiskWrites 1
ControlPort 9051
CookieAuthentication 1
CircuitBuildTimeout 10
LearnCircuitBuildTimeout 0
DataDirectory $PWD/data/client

ORPort 9000
DirReqStatistics 0
UseMicrodescriptors 0
ExitPolicy reject *:*
Log notice file $PWD/logs/client.log
SocksPort 9050
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
SocksPort 9150
ExitPolicyRejectPrivate 0
Exitpolicy reject *:*
RunAsDaemon 1
PublishServerDescriptor 1
EOF

cat <<EOF > ./configs/torrc-x
AvoidDiskWrites 1
ControlPort 9251
CookieAuthentication 1
LearnCircuitBuildTimeout 0
DataDirectory $PWD/data/x
ORPort 9002
DirReqStatistics 0
UseMicroDescriptors 0
DownloadExtraInfo 1
Log notice file $PWD/logs/x.log
SocksPort 9250
ExitPolicyRejectPrivate 0
Exitpolicy reject *:*
RunAsDaemon 1
PublishServerDescriptor 1
EOF

cat <<EOF > ./configs/torrc-y
AvoidDiskWrites 1
ControlPort 9351
CookieAuthentication 1
LearnCircuitBuildTimeout 0
DataDirectory $PWD/data/y
ORPort 9003
DirReqStatistics 0
UseMicroDescriptors 0
DownloadExtraInfo 1
Log notice file $PWD/logs/y.log
SocksPort 9350
ExitPolicyRejectPrivate 0
Exitpolicy reject *:*
RunAsDaemon 1
PublishServerDescriptor 1
EOF

cat <<EOF > ./configs/torrc-z
AvoidDiskWrites 1
ControlPort 9451
CookieAuthentication 1
LearnCircuitBuildTimeout 0
DataDirectory $PWD/data/z
ORPort 9004
DirReqStatistics 0
UseMicroDescriptors 0
DownloadExtraInfo 1
Log notice file $PWD/logs/z.log
SocksPort 9450
ExitPolicyRejectPrivate 0
Exitpolicy accept $MY_PUBLIC_IP:16667, reject *:*
RunAsDaemon 1
PublishServerDescriptor 1
EOF

# make data dirs for w, z and client
mkdir data/w data/x data/y data/z data/client data/auth

# Start Tor
tor-${TOR_VERSION}/src/app/tor -f configs/torrc-auth
tor-${TOR_VERSION}/src/app/tor -f configs/torrc-client
tor-${TOR_VERSION}/src/app/tor -f configs/torrc-w
tor-${TOR_VERSION}/src/app/tor -f configs/torrc-x
tor-${TOR_VERSION}/src/app/tor -f configs/torrc-y
tor-${TOR_VERSION}/src/app/tor -f configs/torrc-z


cd ..

# Give them some time to start up
sleep 5

# Determine the fingerprint of W and Z
export FP_W=$(cat ./tor/data/w/fingerprint | cut -f2 -d" ")
export FP_X=$(cat ./tor/data/x/fingerprint | cut -f2 -d" ")
export FP_Y=$(cat ./tor/data/y/fingerprint | cut -f2 -d" ")
export FP_Z=$(cat ./tor/data/z/fingerprint | cut -f2 -d" ")
export FP_C=$(cat ./tor/data/client/fingerprint | cut -f2 -d" ")


############
### TING ###
############

# Generate default tingrc file
cat <<EOF > ./tingrc
SocksPort 9050
ControllerPort 9051
SourceAddr $MY_PUBLIC_IP
DestinationAddr $MY_PUBLIC_IP
DestinationPort 16667
NumSamples 200
NumRepeats 1
RelayList internet
RelayCacheTime 24
W $MY_PUBLIC_IP,$FP_W
X $MY_PUBLIC_IP,$FP_X
Y $MY_PUBLIC_IP,$FP_Y
Z $MY_PUBLIC_IP,$FP_Z
C $MY_PUBLIC_IP,$FP_C
SocksTimeout 60
MaxCircuitBuildAttempts 5
EOF

nohup ./echo_server &
