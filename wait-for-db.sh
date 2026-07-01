#!/usr/bin/env bash
set -e

echo "⏳ Waiting for Postgres at $DB_HOST:$DB_PORT…"
until PGPASSWORD="$DB_PASSWORD" psql \
  -h "$DB_HOST" \
  -U "$DB_USER" \
  -d "$DB_NAME" \
  -c '\q' 2>/dev/null; do
  echo "Postgres is unavailable — sleeping"
  sleep 2
done

echo "✅ Postgres is up — running migrations"
poetry run python manage.py migrate --noinput

echo "🔄 Collecting static files…"
poetry run python manage.py collectstatic --noinput

# If a command was passed (via Docker CMD / compose `command:`), run it. Otherwise
# fall back to launching Gunicorn as the default.
if [ "$#" -gt 0 ]; then
  echo "🚀 Starting: $*"
  exec poetry run "$@"
else
  echo "🚀 Starting Gunicorn"
  exec poetry run gunicorn \
       --workers "${GUNICORN_WORKERS:-2}" \
       --bind 0.0.0.0:8000 \
       heroic_base.wsgi:application
fi
