#!/usr/bin/env bash

CHUTNEY_BASE=${HOME}
CHUTNEY_PATH=${CHUTNEY_BASE}/chutney
CHUTNEY_BIN=${CHUTNEY_PATH}/chutney
CHUTNEY_REPO=https://git.torproject.org/chutney.git
NETWORK_SPECS=${CHUTNEY_PATH}/networks/basic
CHUTNEY_NODES=${CHUTNEY_PATH}/net/nodes
TING_CONFIG_FILE=tingrc
SCRIPTS=./scripts
TING_LOG_LEVEL=WARNING
TOR_DATA=${SCRIPTS}/data
TOR_DATA_W=${TOR_DATA}/w
TOR_DATA_Z=${TOR_DATA}/z

kill_all() {
  ps -ef | grep "$1" | grep -v grep | awk '{print $2}' | xargs kill -9
}

kill_tor() {
  kill_all "tor " &> /dev/null
}

kill_echo_server() {
  kill_all echo_server &> /dev/null
}

configure_chutney() {
  pushd $CHUTNEY_BASE
  if [ ! -d "chutney" ]; then
    git clone ${CHUTNEY_REPO}
  else
    echo "Chutney is already available."
  fi
  popd
}

bootstrap_test() {
  # Configure torrc files
  ${CHUTNEY_BIN} configure ${NETWORK_SPECS}

  # Start nodes
  ${CHUTNEY_BIN} start ${NETWORK_SPECS}

  # Block until all nodes have bootstrapped
  ${CHUTNEY_BIN} wait_for_bootstrap ${NETWORK_SPECS}
}

start_test() {
  local fingerprint_relay_w=$(cat ${CHUTNEY_NODES}/003r/fingerprint | awk '{print $2}')
  local fingerprint_relay_x=$(cat ${CHUTNEY_NODES}/004r/fingerprint | awk '{print $2}')
  local fingerprint_relay_y=$(cat ${CHUTNEY_NODES}/005r/fingerprint | awk '{print $2}')
  local fingerprint_relay_z=$(cat ${CHUTNEY_NODES}/006r/fingerprint | awk '{print $2}')
  # local fingerprint_client=$(cat ${CHUTNEY_NODES}/008c/fingerprint)

  local host=$(hostname -i | awk '{print $1}')

  # Generate default tingrc file
  cat <<EOF > ./${TING_CONFIG_FILE}
SocksPort 9008
ControllerPort 8008
SourceAddr $host
DestinationAddr $host
DestinationPort 16667
RelayList test
RelayCacheTime 24
W ${fingerprint_relay_w}
Z ${fingerprint_relay_z}
SocksTimeout 60
MaxCircuitBuildAttempts 5
EOF

  grep DirAuthority ${CHUTNEY_PATH}/net/nodes/000a/torrc >> ./${TING_CONFIG_FILE}
  ${SCRIPTS}/ting_runner.py --log-level ${TING_LOG_LEVEL} ${fingerprint_relay_x} ${fingerprint_relay_y}
}

stop_test() {
  # Stop tor nodes
  ${CHUTNEY_BIN} stop ${NETWORK_SPECS}
  kill_tor
}

status_test() {
  ${CHUTNEY_BIN} status ${NETWORK_SPECS}
}

usage() {
  echo "Usage: $0 [configure[_test]|bootstrap_test|start[_test]|stop[_test]|status_test]" 1>&2
  exit 1
}

configure() {
  local fingerprint_relay_w=$(cat ${TOR_DATA_W}/fingerprint | awk '{print $2}')
  local fingerprint_relay_z=$(cat ${TOR_DATA_Z}/fingerprint | awk '{print $2}')

  local host=$(curl icanhazip.com 2>/dev/null)

  # Generate default tingrc file
  cat <<EOF > ./${TING_CONFIG_FILE}
SocksPort 9008
ControllerPort 8008
SourceAddr $host
DestinationAddr $host
DestinationPort 16667
RelayList internet
RelayCacheTime 24
W ${fingerprint_relay_w}
Z ${fingerprint_relay_z}
SocksTimeout 60
MaxCircuitBuildAttempts 5
EOF
}

start() {
  local fingerprint_relay_x=$1
  local fingerprint_relay_y=$2

  ${SCRIPTS}/ting_runner.py --log-level ${TING_LOG_LEVEL} ${fingerprint_relay_x} ${fingerprint_relay_y}
}

stop() {
  kill_echo_server
  kill_tor
}

if [ $# == 0 ]; then
  usage
fi

while :; do
  PARAM=`echo $1 | awk -F= '{print $1}'`
  case "$PARAM" in
    configure_test)
      configure_chutney
      ;;
    bootstrap_test)
      bootstrap_test
      ;;
    status_test)
      status_test
      ;;
    start_test)
      start_test
      ;;
    stop_test)
      stop_test
      ;;
    configure)
      configure
      ;;
    start)
      if [ $# != 3 ]; then
        usage
        exit 1
      fi

      start $2 $3
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
