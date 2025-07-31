#!/bin/sh
cd `dirname $0`

if [ -n "$VIAM_RELOAD" ]; then
    mkdir -p dist
    rm -f dist/archive.tar.gz
    tar czf dist/archive.tar.gz requirements.txt src/* meta.json setup.sh reload.sh run.sh
else
    # Create a virtual environment to run our code
    VENV_NAME=".venv"
    PYTHON="$VENV_NAME/bin/python"

    if ! $PYTHON -m pip install pyinstaller -Uqq; then
        exit 1
    fi

    $PYTHON -m PyInstaller --onefile --hidden-import="googleapiclient" src/main.py
    mkdir -p dist
    tar -czvf dist/archive.tar.gz ./dist/main run.sh
fi




