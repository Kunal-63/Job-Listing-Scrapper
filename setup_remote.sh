#!/bin/bash

# Setup script for macOS/Linux

echo "==================================================="
echo "     LINKEDIN SCRAPER - FIRST TIME SETUP"
echo "==================================================="

# 1. Check for Python
if ! command -v python3 &> /dev/null
then
    echo "[ERROR] Python 3 could not be found."
    echo "Please install Python 3 from https://www.python.org/downloads/"
    exit 1
fi

echo "[INFO] Using Python: $(which python3)"

# 2. Create Virtual Environment
if [ ! -d "venv" ]; then
    echo "[INFO] Creating virtual environment..."
    python3 -m venv venv
fi

# 3. Install Dependencies
echo "[INFO] Installing requirements..."
source venv/bin/activate
pip install -r requirements.txt

# 4. Install Playwright Browsers
echo "[INFO] Installing Playwright browsers..."
playwright install chromium

echo ""
echo "[SUCCESS] Setup complete!"
echo "You can now run the app using ./run_app.sh"
