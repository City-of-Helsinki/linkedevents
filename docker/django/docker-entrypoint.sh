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

if [[ -n "$INSTALL_TEMPLATE" ]]; then
    ./manage.py install_templates "${INSTALL_TEMPLATE}"
fi

# Start server
if [[ -n "$@" ]]; then
    "$@"
elif [[ "$DEV_SERVER" = "true" ]]; then
    python -Wd ./manage.py runserver_plus 0.0.0.0:8000
else
    uwsgi \
    --ini .prod/uwsgi_configuration.ini \
    --processes ${UWSGI_PROCESSES-2} \
    --threads ${UWSGI_THREADS-2}
fi
