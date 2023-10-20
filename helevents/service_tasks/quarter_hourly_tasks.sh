#!/bin/bash

echo ---------------------------------
echo "Starting quarter hourly tasks"
echo ---------------------------------

timeout --preserve-status -s INT 30m python manage.py send_audit_logs_to_elasticsearch
if [ $? -ne 0 ]; then
    echo "Sending audit log entries to Elasticsearch failed"
fi

echo "---------------------------------"
echo "Quarter hourly tasks finished"
echo "---------------------------------"
