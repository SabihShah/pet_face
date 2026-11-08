#!/usr/bin/env bash
# Start the whole pet_face software stack (no ROS) from one terminal.
#
#   ./run.sh               start everything, stream all logs; Ctrl+C stops everything
#   ./run.sh --no-tail     start everything, don't stream logs (still Ctrl+C to stop)
#   ./run.sh stop          stop a running stack (e.g. from another terminal)
#
# Settings (environment variables):
#   WHISPER_MODEL=small.en     voice_module --model
#   CAM=1                      camera_module --cam  (1 = integrated camera, 0 = Iriun)
#   CAMERA_ARGS=""             extra camera flags, e.g. "--no-preview --no-hands"
#   VOICE_ARGS=""              extra voice flags, e.g. "--wake-th 0.5"
#   MIC_VOLUME=0.15            mic input volume set via wpctl; MIC_VOLUME= (empty) to skip
#
# Logs: logs/<module>.log   (follow one with: tail -f logs/voice.log)

set -u
cd "$(dirname "$(readlink -f "$0")")"

LOG_DIR=logs
PID_FILE="$LOG_DIR/pids"
PY=.venv/bin/python
WHISPER_MODEL=${WHISPER_MODEL:-small.en}
CAM=${CAM:-1}
CAMERA_ARGS=${CAMERA_ARGS:-}
VOICE_ARGS=${VOICE_ARGS:-}
MIC_VOLUME=${MIC_VOLUME-0.15}
PORTS="5005 5006 5007 5008"

# name | command (started in this order; brain/speak first so app/voice can reach them)
MODULES=(
  "brain|src/brain_module.py"
  "speak|src/speak_module.py"
  "app|src/app.py"
  "camera|src/camera_module.py --cam $CAM $CAMERA_ARGS"
  "voice|src/voice_module.py --model $WHISPER_MODEL $VOICE_ARGS"
)

stop_all() {
  [ -f "$PID_FILE" ] || { echo "Nothing to stop (no $PID_FILE)."; return 0; }
  echo "Stopping pet_face..."
  local entries pid name
  mapfile -t entries < "$PID_FILE"      # read once: the watcher may delete the file meanwhile
  rm -f "$PID_FILE"
  for e in "${entries[@]}"; do
    read -r pid name <<< "$e"
    kill "$pid" 2>/dev/null && echo "  stopped $name ($pid)"
  done
  sleep 1
  for e in "${entries[@]}"; do
    read -r pid name <<< "$e"
    kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null && echo "  force-killed $name ($pid)"
  done
}

if [ "${1:-}" = "stop" ]; then
  stop_all
  exit 0
fi
TAIL=1
[ "${1:-}" = "--no-tail" ] && TAIL=0

# --- Pre-flight checks -------------------------------------------------------
[ -x "$PY" ] || { echo "ERROR: $PY not found. Create the venv first."; exit 1; }

busy=$(ss -ulpn 2>/dev/null | grep -E "127.0.0.1:($(echo $PORTS | tr ' ' '|')) " || true)
if [ -n "$busy" ]; then
  echo "ERROR: pet_face ports already in use (is the stack already running?):"
  echo "$busy"
  echo "Stop it first: ./run.sh stop   (or kill the PIDs shown above)"
  exit 1
fi

if ! curl -s --max-time 2 http://127.0.0.1:11434/api/tags >/dev/null; then
  echo "WARNING: Ollama is not reachable on :11434. brain_module needs it:"
  echo "         sudo systemctl start ollama   (or run: ollama serve)"
fi

if [ -n "$MIC_VOLUME" ] && command -v wpctl >/dev/null; then
  wpctl set-volume @DEFAULT_AUDIO_SOURCE@ "$MIC_VOLUME" && echo "Mic input volume set to $MIC_VOLUME"
fi

# --- Start -------------------------------------------------------------------
# Strip ROS from the environment: [FACE] processes must not see ROS Python paths.
unset PYTHONPATH AMENT_PREFIX_PATH ROS_DISTRO ROS_VERSION ROS_PYTHON_VERSION \
      ROS_AUTOMATIC_DISCOVERY_RANGE ROS_DOMAIN_ID COLCON_PREFIX_PATH CMAKE_PREFIX_PATH

mkdir -p "$LOG_DIR"
: > "$PID_FILE"
trap 'echo; stop_all; exit 0' INT TERM

for m in "${MODULES[@]}"; do
  name=${m%%|*}
  cmd=${m#*|}
  log="$LOG_DIR/$name.log"
  echo "=== $(date '+%F %T') starting: $cmd" > "$log"
  # shellcheck disable=SC2086
  $PY -u $cmd >> "$log" 2>&1 &
  echo "$! $name" >> "$PID_FILE"
  printf '  %-7s pid %-7s log %s\n' "$name" "$!" "$log"
  [ "$name" = "voice" ] && echo "  (voice calibrates the noise floor for 1 s: stay quiet)"
  sleep 1
done

echo
echo "All modules started. Say 'alexa' to talk. Ctrl+C stops everything."
echo

# --- Watch -------------------------------------------------------------------
if [ "$TAIL" = 1 ]; then
  tail -n +1 -F "$LOG_DIR"/{brain,speak,app,camera,voice}.log &
  TAIL_PID=$!
  trap 'kill $TAIL_PID 2>/dev/null; echo; stop_all; exit 0' INT TERM
fi

# Report any module that dies; exit when all are gone.
declare -A reported=()
while true; do
  # stopped from another terminal (./run.sh stop removed the pid file)
  if [ ! -f "$PID_FILE" ]; then
    [ "$TAIL" = 1 ] && kill "$TAIL_PID" 2>/dev/null
    echo "Stack stopped."
    exit 0
  fi
  alive=0
  while read -r pid name; do
    if kill -0 "$pid" 2>/dev/null; then
      alive=$((alive + 1))
    elif [ -z "${reported[$name]:-}" ]; then
      reported[$name]=1
      echo ">>> $name (pid $pid) EXITED. Last lines of $LOG_DIR/$name.log:"
      tail -n 5 "$LOG_DIR/$name.log" | sed 's/^/    /'
    fi
  done < "$PID_FILE"
  if [ "$alive" -eq 0 ]; then
    echo "All modules have exited."
    [ "$TAIL" = 1 ] && kill "$TAIL_PID" 2>/dev/null
    rm -f "$PID_FILE"
    exit 1
  fi
  sleep 2
done
