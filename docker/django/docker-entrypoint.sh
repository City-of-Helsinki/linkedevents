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
    echo "Create language objects..."
    ./manage.py create_languages
fi


if [[ "$CREATE_SUPERUSER" = "true" ]]; then
    ./manage.py create_admin_superuser
fi

if [[ -n "$INSTALL_TEMPLATE" ]]; then
    ./manage.py install_templates "${INSTALL_TEMPLATE}"
fi

if [[ "$COMPILE_TRANSLATIONS" = "true" ]]; then
    echo "Compile translations..."
    django-admin compilemessages
fi

# Allow running arbitrary commands instead of the servers
if [[ -n "$@" ]]; then
    "$@"
elif [[ "$DEV_SERVER" = "true" ]]; then
    exec python -Wd ./manage.py runserver_plus 0.0.0.0:8000
else
    exec uwsgi \
         --ini .prod/uwsgi_configuration.ini \
         --processes ${UWSGI_PROCESSES-2} \
         --threads ${UWSGI_THREADS-2} \
         --stats /tmp/statsock \
         -m
fi
