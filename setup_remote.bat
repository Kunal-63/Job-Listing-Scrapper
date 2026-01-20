@echo off
setlocal
cd /d "%~dp0"

echo ===================================================
echo      LINKEDIN SCRAPER - FIRST TIME SETUP
echo ===================================================
echo.
echo [INFO] Installing Playwright browsers (Chromium)...
echo This is a one-time setup and may take 2-5 minutes.
echo.
echo A window will open showing the installation progress.
echo Please wait for the installation to complete.
echo.

REM Don't set PLAYWRIGHT_BROWSERS_PATH - let it use default AppData location
set PLAYWRIGHT_BROWSERS_PATH=

REM Run browser installation via the EXE with UI
start "" /wait "LinkedInScraper.exe" --install-browsers

if %ERRORLEVEL% EQU 0 (
    echo.
    echo [SUCCESS] Browser installation completed successfully!
    echo You can now run LinkedInScraper.exe normally.
    echo.
) else (
    echo.
    echo [WARNING] Installation may have encountered issues.
    echo Check the log file at:
    echo %LOCALAPPDATA%\LinkedInScraper\playwright_install.log
    echo.
)

pause