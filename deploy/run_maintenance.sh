#!/bin/bash

function run_all {
    next=0
    echo "Running all maintenance tasks in /maintenance/stage_*.sh"
    while [ -f /maintenance/stage_"$next".sh ]; do
        echo "Found stage_$next"
        /maintenance/stage_"$next".sh
        next=$((next+1))
    done
}


if [ "$1" = 'all' ]; then
    run_all
else
    echo -n "Running maintenance tasks "
    while test $# -gt 0
    do
        echo -n "$1"
        /maintenance/stage_"$1".sh
        shift
    done
fi
