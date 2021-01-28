#!/bin/bash

relay() {
  mkdir configs/
  cat <<EOF > ./configs/torrc
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
}

dirauth() {
  A="dirauth"
  ip=127.0.0.1
  orport=9001
  dirport=9030
  mkdir -pv configs/ logs/ $A
  chmod 700 $A
  cat <<EOF > ./configs/torrc
Log notice stdout
ShutdownWaitLength 2
ExitPolicy reject *:*
CookieAuthentication 1
ContactInfo tortest (at) weintraub (dot) xyz
LogTimeGranularity 1
SafeLogging 0
DataDirectory $A
PidFile $A/tor.pid
Address $ip
SocksPort 0
ControlPort 0
ControlSocket $(pwd)/$A/control_socket
ORPort $ip:$orport
DirPort $ip:$dirport
Nickname test
# AuthoritativeDirectory 1
# V3AuthoritativeDirectory 1
DirAllowPrivateAddresses 1
EOF
}

start_tor() {
  exec tor-${TOR_VERSION}/src/app/tor -f configs/torrc
}

while [ "$1" != "" ]; do
  PARAM=$1
  # VALUE=`echo $1 | awk -F= '{print $2}'`
  case "$PARAM" in
    relay)
      relay
      ;;
    dirauth)
      dirauth
      ;;
    *)
      echo "ERROR: unknown parameter \"$PARAM\""
      exit 1
      ;;
  esac
  shift
done
shift $((OPTIND-1))

start_tor
