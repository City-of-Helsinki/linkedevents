#!/bin/bash

set -e


if [[ "$WAIT_FOR_IT_ADDRESS" ]]; then
    wait-for-it.sh $WAIT_FOR_IT_ADDRESS --timeout=30
fi


if [[ "$APPLY_MIGRATIONS" = "true" ]]; then
    echo "Applying database migrations..."
    ./manage.py migrate --noinput
    echo "Applying sync_translation_fields migrations..."
    ./manage.py sync_translation_fields --noinput
fi


if [[ "$CREATE_SUPERUSER" = "true" ]]; then
    ./manage.py create_admin_superuser
fi


if [[ "$DEV_SERVER" = "true" ]]; then
    ./manage.py runserver $RUNSERVER_ADDRESS
else
    uwsgi ./.prod/uwsgi_configuration.ini
fi
