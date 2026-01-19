@echo off
echo ===================================================
echo   LINKEDIN SCRAPER - ONE CLICK BUILDER
echo ===================================================
echo.

REM 1. Run the Python build script
echo [1/2] Running Python Build Script...
python build_exe.py
if %errorlevel% neq 0 (
    echo [ERROR] Python build failed!
    pause
    exit /b %errorlevel%
)

REM 2. Check for Inno Setup Compiler
echo.
echo [2/2] Packing into Installer...
set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"

if exist "%ISCC%" (
    "%ISCC%" setup.iss
    if %errorlevel% neq 0 (
        echo [ERROR] Inno Setup compilation failed!
        pause
        exit /b %errorlevel%
    )
    echo.
    echo ===================================================
    echo   SUCCESS! Installer created in "Output" folder.
    echo ===================================================
    echo You can now send "JobScraperSetup.exe" to the user.
) else (
    echo.
    echo [WARNING] Inno Setup Compiler not found at:
    echo "%ISCC%"
    echo.
    echo To finish:
    echo 1. Install Inno Setup from https://jrsoftware.org/isdl.php
    echo 2. Right-click "setup.iss" and select "Compile"
)

pause
