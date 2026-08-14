#!/bin/sh
set -e

echo "=== DeployOps Monitoring Backend Entrypoint ==="

PORT="${PORT:-8000}"

# Apply database migrations
echo "Applying database migrations..."
python manage.py migrate --noinput || echo "Database migration warning (check connection settings)"

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput --clear || echo "Collectstatic skipped/failed"

# Start Gunicorn WSGI Server
echo "Starting Gunicorn server on 0.0.0.0:${PORT}..."
exec gunicorn --bind "0.0.0.0:${PORT}" --workers 3 --timeout 120 config.wsgi:application
