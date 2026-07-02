#!/bin/bash
set -eu

DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$DIR"

SYSTEM_PYTHON="/usr/bin/python3"

echo "Creating virtual environment with system Python ($SYSTEM_PYTHON)..."
# Always use the macOS system Python to avoid Anaconda/Homebrew incompatibilities
# with py2app bundling (pyobjc + Python 3.13 causes NSAutoreleasePool import crash)
if [ -d ".venv" ]; then
    VENV_PYTHON=$(.venv/bin/python --version 2>&1 | awk '{print $2}')
    SYSTEM_VERSION=$($SYSTEM_PYTHON --version 2>&1 | awk '{print $2}')
    if [ "$VENV_PYTHON" != "$SYSTEM_VERSION" ]; then
        echo "Existing .venv uses Python $VENV_PYTHON, need $SYSTEM_VERSION. Recreating..."
        rm -rf .venv
    fi
fi
if [ ! -d ".venv" ]; then
    $SYSTEM_PYTHON -m venv .venv
fi
source .venv/bin/activate

echo "Installing dependencies..."
pip install -r requirements.txt
pip install py2app

echo "Building the application bundle..."
# Clean previous builds
rm -rf build dist

python setup.py py2app

echo "Creating DMG..."
# Remove old DMG if it exists
rm -f dockdong.dmg

# Simple DMG creation using hdiutil
hdiutil create -volname "dockdong" -srcfolder dist/dockdong.app -ov -format UDZO "dockdong.dmg"

echo "Done! You can find the app in dist/ and the DMG as dockdong.dmg"
