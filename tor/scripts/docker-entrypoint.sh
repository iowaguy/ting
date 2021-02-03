#!/bin/bash

orport=9001
tmp_dir=$XDG_RUNTIME_DIR
data_directory=/etc/data
tor_version=tor

relay() {
  A="relay"
  dirauth_nickname=$(cat $data_directory/dirauth/fingerprint | awk '{print $1}')
  dirauth_fingerprint=$(cat $data_directory/dirauth/fingerprint | awk '{print $2}')
  dirauth_ip=$(cat $data_directory/dirauth/ip)
  mkdir -pv configs/ logs/ $data_directory/$A $A
  chmod 700 $A
  cat <<EOF > ./configs/torrc
Log notice stdout
ShutdownWaitLength 2
# ExitRelay 1
IPv6Exit 1
ExitPolicy reject *:*
CookieAuthentication 1
ContactInfo tortest (AT) weintraub (DOT) xyz
LogTimeGranularity 1
SafeLogging 0
DataDirectory $data_directory/$A
PidFile $A/tor.pid
Address $A
SocksPort 0
ControlPort 0
ControlSocket $(pwd)/$A/control_socket
ORPort $orport
#DirPort auto
Nickname $A
DirAuthority $dirauth_nickname $dirauth_ip:9030 $dirauth_fingerprint
TestingTorNetwork 1

# AvoidDiskWrites 1
# ControlPort 9051
# CookieAuthentication 1
# LearnCircuitBuildTimeout 0
# DataDirectory $PWD/data/w
# ORPort $orport
# DirReqStatistics 0
# UseMicroDescriptors 0
# DownloadExtraInfo 1
# Log notice file $PWD/logs/w.log
# SocksPort 9150
# ExitPolicyRejectPrivate 0
# Exitpolicy reject *:*
# RunAsDaemon 1
# PublishServerDescriptor 1
EOF
}

dirauth() {
  A="dirauth"
  ip=127.0.0.1
  dirport=9030
  mkdir -pv configs/ logs/ $data_directory/$A $A
  hostname -i > $data_directory/$A/ip
  chmod 700 $A
  cat <<EOF > ./configs/torrc
AuthoritativeDirectory 1
V3AuthoritativeDirectory 1
AssumeReachable 1
Log notice stdout
# Log notice file $data_directory/$A.log
ShutdownWaitLength 2
ExitPolicy reject *:*
# CookieAuthentication 1
ContactInfo tortest (AT) weintraub (DOT) xyz
LogTimeGranularity 1
SafeLogging 0
DataDirectory $data_directory/$A
PidFile /root/$A/tor.pid
Address $(hostname -i)
SocksPort 0
ControlPort 0
ControlSocket $(pwd)/$A/control_socket
ORPort 0.0.0.0:$orport
DirPort 0.0.0.0:$dirport
Nickname TestDirAuth
DirAllowPrivateAddresses 1
# RunAsDaemon 0
# DirPortFrontPage ${TOR_VERSION}/contrib/operator-tools/tor-exit-notice.html
# Sandbox 1
EOF

  echo "very secret password\n" > passwd
  sudo ${tor_version}/src/tools/tor-gencert -v --create-identity-key -i $data_directory/$A/keys/authority_identity_key -s $data_directory/$A/keys/authority_signing_key -c $data_directory/$A/keys/authority_certificate --passphrase-fd 0 < passwd
  wait
}

start_tor() {
  exec ${tor_version}/src/app/tor -f /root/configs/torrc
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
