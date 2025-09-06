#!/bin/bash
set -e

echo "=== Starting entrypoint.sh ==="

# Multiple possible directories
mkdir -p /app/static
mkdir -p /app/staticfiles/drf_spectacular_sidecar/swagger-ui-dist
mkdir -p /tmp/staticfiles/drf_spectacular_sidecar/swagger-ui-dist

echo "Extracting Spectacular static files..."
python extract_spectacular_static.py

echo "Collecting static files..."
python manage.py collectstatic --noinput

# Make files accessible in all locations
cp -r /app/staticfiles/drf_spectacular_sidecar/swagger-ui-dist/* /tmp/staticfiles/drf_spectacular_sidecar/swagger-ui-dist/ || echo "Copy failed, continuing anyway"

# Debug info
echo "Contents of staticfiles directories:"
find /app/staticfiles -type f | grep swagger
find /tmp/staticfiles -type f | grep swagger 2>/dev/null || echo "No files in /tmp/staticfiles"

# Make directories readable
chmod -R 755 /app/staticfiles
chmod -R 755 /tmp/staticfiles 2>/dev/null || echo "Chmod failed on /tmp/staticfiles, continuing anyway"

exec gunicorn base.wsgi:application --log-level debug --workers 2 --timeout 120 --access-logfile - --error-logfile - --bind 0.0.0.0:$PORT