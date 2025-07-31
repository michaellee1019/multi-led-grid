#!/usr/bin/env bash

# bash safe mode. look at `set --help` to see what these are doing
set -euxo pipefail 

cd $(dirname $0)
MODULE_DIR=$(dirname $0)
VIRTUAL_ENV=$MODULE_DIR/.venv
PYTHON=$VIRTUAL_ENV/bin/python

if [ "$VIAM_RELOAD" = "reinstall" ]; then
    ./setup.sh
fi

# Be sure to use `exec` so that termination signals reach the python process,
# or handle forwarding termination signals manually
exec $PYTHON src/main.py $@