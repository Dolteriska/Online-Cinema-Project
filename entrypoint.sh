#!/bin/sh
set -e

echo "Waiting for postgres..."
until pg_isready -h db -p 5432 -U cinema; do
  sleep 1
done

alembic upgrade head

exec "$@"
