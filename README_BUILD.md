# How to Build the Installer

Follow these steps to create the single-file setup EXE for the LinkedIn Scraper.

## 1. Build the Application
1.  Open a terminal in the project folder.
2.  Run the build script:
    ```bash
    python build_exe.py
    ```
3.  This will:
    *   Install PyInstaller (if missing).
    *   Install Playwright browsers.
    *   Compile the application into `dist/LinkedInScraper`.

## 2. Create the Installer
1.  Download and install **Inno Setup** from [jrsoftware.org](https://jrsoftware.org/isdl.php).
2.  Right-click `setup.iss` and choose **Compile**.
   (Or use the `BUILD_INSTALLER.bat` script).

## 3. Done!
*   The final installer file `JobScraperSetup.exe` will be in the `Output` folder.
*   **Note**: This version does NOT include MongoDB. The user must have MongoDB installed or the application must be configured to point to a cloud database (Atlas).
