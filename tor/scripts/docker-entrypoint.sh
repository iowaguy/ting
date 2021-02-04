#!/bin/bash

DATA_DIRECTORY=/etc/data
TOR_PATH=$TOR_VERSION
TOR=${TOR_PATH}/src/app/tor
ORPORT=9001

relay() {
  A="relay"
  DIRAUTH_NICKNAME=$(cat $DATA_DIRECTORY/dirauth/fingerprint | awk '{print $1}')
  DIRAUTH_FINGERPRINT=$(cat $DATA_DIRECTORY/dirauth/fingerprint | awk '{print $2}')
  DIRAUTH_IP=$(cat $DATA_DIRECTORY/dirauth/ip)
  ORPORT=9001
  mkdir -pv configs/ logs/ $DATA_DIRECTORY/$A $A
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
DataDirectory $DATA_DIRECTORY/$A
PidFile $A/tor.pid
Address $A
SocksPort 0
ControlPort 0
ControlSocket $(pwd)/$A/control_socket
ORPort $ORPORT
#DirPort auto
Nickname $A
DirAuthority $DIRAUTH_NICKNAME $DIRAUTH_IP:9030 $DIRAUTH_FINGERPRINT
TestingTorNetwork 1
Sandbox 1

EOF
}

dirauth() {
  ROLE="DIRAUTH"
  # Generate a random name
  TOR_NICKNAME=${ROLE}$(pwgen -0A 10)
  DIRPORT=9030
  CONTROL_PORT=9051

  mkdir -pv configs/ logs/ $DATA_DIRECTORY/$TOR_NICKNAME/keys $TOR_NICKNAME

  echo "password" > passwd
  sudo ${TOR_PATH}/src/tools/tor-gencert -v \
       -m 12 -a $(hostname -i):${DIRPORT} \
       --create-identity-key \
       -i $DATA_DIRECTORY/$TOR_NICKNAME/keys/authority_identity_key \
       -s $DATA_DIRECTORY/$TOR_NICKNAME/keys/authority_signing_key \
       -c $DATA_DIRECTORY/$TOR_NICKNAME/keys/authority_certificate \
       --passphrase-fd 0 < passwd
  wait

  ${TOR} --list-fingerprint --orport 1 \
    	   --dirserver "x 127.0.0.1:1 ffffffffffffffffffffffffffffffffffffffff" \
	       --datadirectory ${DATA_DIRECTORY}/${TOR_NICKNAME}

  # IP=127.0.0.1
  # hostname -i > $DATA_DIRECTORY/$TOR_NICKNAME/ip
  # chmod 700 $TOR_NICKNAME
  DIRAUTH_FINGERPRINT=$(grep "fingerprint" $DATA_DIRECTORY/$TOR_NICKNAME/keys/authority_certificate | awk -F " " '{print $2}')
  DIRAUTH_FINGERPRINT_RELAY=$(cat $DATA_DIRECTORY/$TOR_NICKNAME/fingerprint | awk -F " " '{print $2}')
  DIRAUTH_IP=$(grep "dir-address" $DATA_DIRECTORY/$TOR_NICKNAME/keys/* | awk -F " " '{print $2}')

  # generate by running tor --hash-password password
  TOR_CONTROL_PASSWD="16:C9C094CC959A441360CF9FDC98510A6D0489B96E06627783596DF54C32"


  cat <<EOF > ./configs/torrc
TestingTorNetwork 1

## Rapid Bootstrap Testing Options ##
# These typically launch a working minimal Tor network in 6s-10s
# These parameters make tor networks bootstrap fast,
# but can cause consensus instability and network unreliability
# (Some are also bad for security.)
AssumeReachable 1
PathsNeededToBuildCircuits 0.25
TestingDirAuthVoteExit *
TestingDirAuthVoteHSDir *
V3AuthNIntervalsValid 2

## Always On Testing Options ##
# We enable TestingDirAuthVoteGuard to avoid Guard stability requirements
TestingDirAuthVoteGuard *
# We set TestingMinExitFlagThreshold to 0 to avoid Exit bandwidth requirements
TestingMinExitFlagThreshold 0

## Options that we always want to test ##
Sandbox 1

# Private tor network configuration
RunAsDaemon 0
ConnLimit 60
ShutdownWaitLength 0
Log notice stdout
ProtocolWarnings 1
SafeLogging 0
DisableDebuggerAttachment 0

DirPortFrontPage ${TOR_PATH}/contrib/operator-tools/tor-exit-notice.html

Nickname $TOR_NICKNAME
DataDirectory $DATA_DIRECTORY/$TOR_NICKNAME
Address $(hostname -i)
ControlPort 0.0.0.0:$CONTROL_PORT
HashedControlPassword $TOR_CONTROL_PASSWD
AuthoritativeDirectory 1
V3AuthoritativeDirectory 1

TestingV3AuthInitialVotingInterval 300
TestingV3AuthInitialVoteDelay 5
V3AuthVoteDelay 5
TestingV3AuthInitialDistDelay 5
V3AuthDistDelay 5

OrPort $ORPORT
Dirport $DIRPORT
ExitPolicy accept *:*
DirAuthority $TOR_NICKNAME orport=$ORPORT no-v2 v3ident=$DIRAUTH_FINGERPRINT $DIRAUTH_IP $DIRAUTH_FINGERPRINT_RELAY

EOF
}

start_tor() {
  cat /root/configs/torrc
  exec ${TOR} -f /root/configs/torrc
  # ${TOR} -f /root/configs/torrc &
  # exec /bin/bash
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
