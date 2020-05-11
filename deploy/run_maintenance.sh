#!/bin/bash

function run_all {
    echo "Running all maintenance tasks in /maintenance/stage_*.sh"
    for TASK_SCRIPT in /maintenance/stage_*.sh; do
        echo "Found $TASK_SCRIPT, running"
        $TASK_SCRIPT
        next=$((next+1))
    done
    echo "All found maintenance tasks were run"
}

if ! ls /maintenance/stage_*.sh &> /dev/null; then
    echo "No stage_*.sh maintenance scripts found in /maintenance"
    echo "Either build such scripts into the image or mount them there."
    echo "Exiting now"
    exit 1
fi

if [ "$1" = 'all' ]; then
    run_all
else
    echo -n 'Running maintenance tasks '
    while test $# -gt 0
    do
        echo -n "$1"
        /maintenance/stage_"$1".sh
        shift
    done
    echo .
    echo 'Specified maintenance tasks run'
fi
