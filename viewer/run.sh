#!/usr/bin/env sh
# Run script for mqtt_event_pricure app.py
# Exports environment variables with sensible defaults, prints the effective config,
# then runs the application.
#
# Usage:
#   MQTT_BROKER_HOST=broker.local MQTT_USERNAME=user ./run.sh
#
# The script honors any variables already set in the environment; otherwise it sets defaults.

set -eu

# Defaults (can be overridden by environment)
MQTT_BROKER_HOST="${MQTT_BROKER_HOST:-localhost}"
MQTT_BROKER_PORT="${MQTT_BROKER_PORT:-1883}"
MQTT_USERNAME="${MQTT_USERNAME:-}"
MQTT_PASSWORD="${MQTT_PASSWORD:-}"
MQTT_TOPIC="${MQTT_TOPIC:-frigate/+/+/snapshot}"

HTTP_HOST="${HTTP_HOST:-0.0.0.0}"
HTTP_PORT="${HTTP_PORT:-8080}"
LOG_LEVEL=DEBUG
IMAGE_REFRESH_MS="${IMAGE_REFRESH_MS:-2000}"

# Export for the Python app to read
export MQTT_BROKER_HOST MQTT_BROKER_PORT MQTT_USERNAME MQTT_PASSWORD MQTT_TOPIC
export HTTP_HOST HTTP_PORT IMAGE_REFRESH_MS

# Helper to mask sensitive values when printing
_mask() {
  case "$1" in
    "") printf "(empty)";;
    *) printf "****";;
  esac
}

# Print effective configuration
printf "\n[run.sh] Starting mqtt_event_pricure\n"
printf "[run.sh] Configuration:\n"
printf "  MQTT_BROKER_HOST = %s\n" "$MQTT_BROKER_HOST"
printf "  MQTT_BROKER_PORT = %s\n" "$MQTT_BROKER_PORT"
printf "  MQTT_USERNAME    = %s\n" "${MQTT_USERNAME:-(empty)}"
printf "  MQTT_PASSWORD    = %s\n" "$(_mask "$MQTT_PASSWORD")"
printf "  MQTT_TOPIC       = %s\n" "$MQTT_TOPIC"
printf "  HTTP_HOST        = %s\n" "$HTTP_HOST"
printf "  HTTP_PORT        = %s\n" "$HTTP_PORT"
printf "  IMAGE_REFRESH_MS = %s\n" "$IMAGE_REFRESH_MS"
printf "\n"

# Choose python executable (prefer python3)
if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  printf "[run.sh] ERROR: No python interpreter found in PATH. Please install Python 3.\n" >&2
  exit 2
fi

# Show the command and execute (use exec so PID 1 is the python process when used in containers)
printf "[run.sh] Executing: %s app.py\n\n" "$PY"
exec "$PY" app.py
