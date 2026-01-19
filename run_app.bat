@echo off
cd /d "%~dp0"
if not exist "venv" (
    echo [ERROR] Environment not set up. Running setup first...
    call setup_remote.bat
)
start "" "venv\Scripts\pythonw.exe" main.py
