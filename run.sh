#!/bin/sh
set -eu

DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PYTHON="$DIR/.venv/bin/python"

if [ ! -x "$PYTHON" ]; then
    echo "Missing virtualenv. Run: python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt" >&2
    exit 1
fi

exec "$PYTHON" "$DIR/app.py"
