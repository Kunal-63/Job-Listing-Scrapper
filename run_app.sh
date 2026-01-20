#!/bin/bash

# Run script for macOS/Linux

# Get directory of this script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "[ERROR] Environment not set up. Running setup first..."
    ./setup_remote.sh
fi

# Activate and run
source venv/bin/activate
python3 main.py
