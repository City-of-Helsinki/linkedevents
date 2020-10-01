#!/bin/bash
# Wait for database present as docker-compose is bringing it up in paraller
if [[ "$WAIT_FOR_IT_ADDRESS" ]]; then
    $HOME/deploy/wait-for-it.sh $WAIT_FOR_IT_ADDRESS --timeout=30
fi

./manage.py migrate

$HOME/deploy/init_application.sh

exec ./manage.py runserver 0:8000
