#!/bin/sh
set -eu

python /app/dashboard/manage.py migrate --noinput
python /app/dashboard/manage.py collectstatic --noinput
python /app/dashboard/manage.py check

exec gunicorn dashboard.config.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers "${TOOL_SHED_DASHBOARD_WORKERS:-2}" \
  --threads "${TOOL_SHED_DASHBOARD_THREADS:-4}" \
  --access-logfile -
