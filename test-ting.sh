#!/bin/bash

CHUTNEY_PATH=${HOME}/chutney
CHUTNEY_BIN=${CHUTNEY_PATH}/chutney
CHUTNEY_REPO=https://git.torproject.org/chutney.git
NETWORK_SPECS=${CHUTNEY_PATH}/networks/basic
CHUTNEY_NODES=${CHUTNEY_PATH}/net/nodes
TING_CONFIG_FILE=tingrc

kill_all() {
  ps -ef | grep $1 | grep -v grep | awk '{print $2}' | xargs kill -9
}

kill_tor() {
  kill_all tor &> /dev/null
}

kill_echo_server() {
  kill_all echo_server &> /dev/null
}

configure_chutney() {
  pushd $HOME
  if [ ! -d "chutney" ]; then
    git clone ${CHUTNEY_REPO}
  else
    echo "Chutney is already available."
  fi
  popd
}

start() {
  # Configure torrc files
  ${CHUTNEY_BIN} configure ${NETWORK_SPECS}

  # Start nodes
  ${CHUTNEY_BIN} start ${NETWORK_SPECS}

  # Block until all nodes have bootstrapped
  ${CHUTNEY_BIN} wait_for_bootstrap ${NETWORK_SPECS}
}

ting() {
  local fingerprint_relay_w=$(cat ${CHUTNEY_NODES}/003r/fingerprint | awk '{print $2}')
  local fingerprint_relay_x=$(cat ${CHUTNEY_NODES}/004r/fingerprint | awk '{print $2}')
  local fingerprint_relay_y=$(cat ${CHUTNEY_NODES}/005r/fingerprint | awk '{print $2}')
  local fingerprint_relay_z=$(cat ${CHUTNEY_NODES}/006r/fingerprint | awk '{print $2}')
  # local fingerprint_client=$(cat ${CHUTNEY_NODES}/008c/fingerprint)

  local host=$(hostname -i | awk '{print $1}')

  # Generate default tingrc file
  cat <<EOF > ./${TING_CONFIG_FILE}
SocksPort 9050
ControllerPort 9051
SourceAddr $host
DestinationAddr $host
DestinationPort 16667
NumSamples 200
NumRepeats 1
RelayList test
RelayCacheTime 24
W ${host},${fingerprint_relay_w}
Z ${host},${fingerprint_relay_z}
# C ${host},${fingerprint_client}
SocksTimeout 60
MaxCircuitBuildAttempts 5
EOF

  grep DirAuthority ${CHUTNEY_PATH}/net/nodes/000a/torrc >> ./${TING_CONFIG_FILE}
  ./echo_server &

  ./ting ${fingerprint_relay_x} ${fingerprint_relay_y}

  kill_echo_server
}

stop() {
  # Stop tor nodes
  ${CHUTNEY_BIN} stop ${NETWORK_SPECS}
  kill_tor
}

status() {
  ${CHUTNEY_BIN} status ${NETWORK_SPECS}
}

usage() {
  echo "Usage: $0 [configure|start|ting|stop|status]" 1>&2
  exit 1
}

if [ $# == 0 ]; then
  usage
fi

while :; do
  PARAM=`echo $1 | awk -F= '{print $1}'`
  case "$PARAM" in
    configure)
      configure_chutney
      ;;
    start)
      start
      ;;
    status)
      status
      ;;
    ting)
      ting
      ;;
    stop)
      stop
      ;;
    *)
      echo "ERROR: unknown parameter \"$PARAM\""
      usage
      ;;
  esac
  shift
  exit 0
done
shift $((OPTIND-1))
