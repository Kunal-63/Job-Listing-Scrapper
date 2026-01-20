@echo off
setlocal
cd /d "%~dp0"

echo ===================================================
echo      LINKEDIN SCRAPER - FIRST TIME SETUP
echo ===================================================

REM 1. Check for Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Python not found. Downloading Python 3.11...
    
    REM Download Python installer using PowerShell
    powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile 'python_installer.exe'"
    
    echo [INFO] Installing Python (Admin required)...
    echo Please accept the User Account Control prompt.
    
    REM Install Python silently, adding to PATH
    python_installer.exe /quiet PrependPath=1 Include_test=0
    
    REM Clean up
    del python_installer.exe
    
    REM Refresh environment vars (hacky way for batch)
    set PATH=%PATH%;C:\Program Files\Python311\Scripts;C:\Program Files\Python311
)

REM Verify Python again
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python installation failed or PATH not updated.
    echo Please restart your computer and run this script again.
    pause
    exit /b 1
)

REM 2. Create Virtual Environment
if not exist "venv" (
    echo [INFO] Creating virtual environment...
    python -m venv venv
)

REM 3. Install Dependencies
echo [INFO] Installing requirements...
call venv\Scripts\activate.bat
pip install -r requirements.txt

REM 4. Install Playwright Browsers
echo [INFO] Installing browsers...
call venv\Scripts\activate.bat
call venv\Scripts\python.exe -m playwright install

echo.
echo [SUCCESS] Setup complete!
echo You can now launch the application using "Run App" shortcut.
pause
