#!/bin/bash

echo ---------------------------------
echo "Starting daily import"
echo ---------------------------------

timeout --preserve-status -s INT 30m python manage.py event_import yso --all --disable-indexing
if [ $? -ne 0 ]; then
    echo "YSO update signaled failure"
fi

timeout --preserve-status -s INT 60m python manage.py event_import harrastushaku --places --disable-indexing
if [ $? -ne 0 ]; then
    echo "Harrastushaku places update signaled failure"
fi

timeout --preserve-status -s INT 60m python manage.py event_import harrastushaku --courses --disable-indexing
if [ $? -ne 0 ]; then
    echo "Harrastushaku courses update signaled failure"
fi


timeout --preserve-status -s INT 60m python manage.py event_import osoite --places --disable-indexing
if [ $? -ne 0 ]; then
    echo "PKS osoiteluettelo update signaled failure"
fi

timeout --preserve-status -s INT 60m python manage.py pseudonymize_past_signups
if [ $? -ne 0 ]; then
    echo "Pseudonymization failure"
fi

echo "---------------------------------"
echo "Daily import finished"
echo "---------------------------------"
