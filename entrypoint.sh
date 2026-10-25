#!/bin/sh
set -eu
python -m flask --app app init-db
if [ "${DEMO_MODE:-0}" = "1" ]; then
  python -m flask --app app seed-demo
fi
exec "$@"
