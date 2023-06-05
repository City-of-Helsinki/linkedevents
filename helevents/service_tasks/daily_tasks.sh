#!/bin/bash

echo ---------------------------------
echo "Starting daily import"
echo ---------------------------------

timeout --preserve-status -s INT 10m python manage.py event_import yso --all
if [ $? -ne 0 ]; then
    echo "YSO update signaled failure"
fi

timeout --preserve-status -s INT 15m python manage.py event_import harrastushaku --courses
if [ $? -ne 0 ]; then
    echo "Harrastushaku update signaled failure"
fi


timeout --preserve-status -s INT 20m python manage.py event_import osoite --places
if [ $? -ne 0 ]; then
    echo "PKS osoiteluettelo update signaled failure"
fi

echo "---------------------------------"
echo "Daily import finished"
echo "---------------------------------"
