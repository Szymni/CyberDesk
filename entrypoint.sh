#!/bin/sh
set -eu

# 1. Run structural migrations as the superuser/owner
export DB_USER="cyberdesk"
export DB_PASS="$ADMIN_DB_PASS"
python -m flask --app app init-db

if [ "${DEMO_MODE:-0}" = "1" ]; then
  python -m flask --app app seed-demo
fi

# 2. Swap to the restricted runtime user for web traffic
export DB_USER="cyberdesk_app"
export DB_PASS="$APP_DB_PASS"

exec "$@"
