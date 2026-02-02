@echo off
REM Continuous Job Scraper - Runs all 3 stages in a loop
REM Press Ctrl+C to stop

echo ============================================================
echo Multi-Platform Job Scraper - Continuous Mode
echo ============================================================
echo.
echo This will run continuously until you press Ctrl+C
echo.
echo Pipeline:
echo   1. Scrape job links
echo   2. Scrape job details  
echo   3. Scrape company details
echo   4. Wait 5 minutes
echo   5. Repeat
echo.
echo ============================================================
echo.

cd /d "%~dp0"
python scripts\run_multi_platform_scrapers.py --continuous

pause
