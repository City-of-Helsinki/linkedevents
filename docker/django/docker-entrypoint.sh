#!/bin/bash

set -e


if [[ "$DATABASE_URL" ]]; then
    wait-for-it.sh --host=postgres --port=5432 --strict --timeout=10
fi


if [[ "$APPLY_MIGRATIONS" = "1" ]]; then
    echo "Applying database migrations..."
    ./manage.py migrate --noinput
fi


# Start server
if [[ ! -z "$@" ]]; then
    "$@"
elif [[ "$DEV_SERVER" = "1" ]]; then
    python ./manage.py runserver 0.0.0.0:8000
else
    uwsgi --wsgi-file linkedevents/wsgi.py
fi
