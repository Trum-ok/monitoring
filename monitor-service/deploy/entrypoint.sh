#!/bin/sh
set -e

mkdir -p /app/data

if [ -n "$MONITOR_DB_PATH" ]; then
  export MONITOR_DB_PATH
fi

alembic upgrade head
exec uvicorn main:app --host 0.0.0.0 --port 8000
