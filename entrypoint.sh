#!/usr/bin/env bash
set -euo pipefail

# Apply database migrations
python manage.py migrate --noinput

# Collect static files (safe to run again in container runtime for CI parity)
python manage.py collectstatic --noinput --verbosity 0

# Start Gunicorn
exec gunicorn base.wsgi:application \
    --bind 0.0.0.0:${PORT:-8000} \
    --workers ${WEB_CONCURRENCY:-3} \
    --threads ${GUNICORN_THREADS:-3} \
    --timeout 120
