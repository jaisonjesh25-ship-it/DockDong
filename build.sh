#!/bin/bash
set -eu

DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$DIR"

echo "Creating virtual environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
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
