#!/bin/bash

if [ -n "$VIAM_RELOAD" ]; then
    ./reload.sh "$@"
else
    ./dist/main "$@"
fi
