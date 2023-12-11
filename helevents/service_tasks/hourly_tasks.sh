#!/bin/bash

echo ---------------------------------
echo "Starting hourly tasks"
echo ---------------------------------

timeout --preserve-status -s INT 10m python manage.py event_import tprek --places --disable-indexing
if [ $? -ne 0 ]; then
    echo "tprek importer signaled failure"
fi

echo "--- Starting kulke importer ---"

timeout --preserve-status -s INT 30m python manage.py event_import kulke --keywords --disable-indexing
if [ $? -ne 0 ]; then
    echo "kulke importer keyword import signaled failure"
fi

timeout --preserve-status -s INT 30m python manage.py event_import kulke --events --disable-indexing
if [ $? -ne 0 ]; then
    echo "kulke importer event import signaled failure"
fi

echo "--- Starting lippupiste importer ---"

timeout --preserve-status -s INT 45m python manage.py event_import lippupiste --events --disable-indexing
if [ $? -ne 0 ]; then
    echo "lippupiste importer signaled failure"
fi

echo "--- Starting helmet importer ---"

timeout --preserve-status -s INT 75m python manage.py event_import helmet --events --disable-indexing
if [ $? -ne 0 ]; then
    echo "helmet importer signaled failure"
fi

echo "--- Starting espoo importer ---"

timeout --preserve-status -s INT 30m python manage.py event_import espoo --events --disable-indexing
if [ $? -ne 0 ]; then
    echo "espoo importer signaled failure"
fi


echo "--- Updating local event cache ---"

nice python manage.py populate_local_event_cache
if [ $? -ne 0 ]; then
    echo "populate local event cache signaled failure"
fi

echo "--- Starting keyword and place n_events update ---"

nice python manage.py update_n_events
if [ $? -ne 0 ]; then
    echo "keyword and place n_events update signaled failure"
fi

echo "--- Updating has_upcoming_events flags ---"

nice python manage.py update_has_upcoming_events
if [ $? -ne 0 ]; then
    echo "update_has_upcoming_events update signaled failure"
fi

echo "--- Starting haystack index update ---"

nice python manage.py update_index -m 75
if [ $? -ne 0 ]; then
    echo "haystack index update signaled failure"
fi

echo "---------------------------------"
echo "Hourly import finished"
echo "---------------------------------"
