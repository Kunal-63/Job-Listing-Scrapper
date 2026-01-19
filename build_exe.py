
import os
import sys
import shutil
import subprocess
from pathlib import Path

def build_executable():
    """Build the standalone executable."""
    print("="*80)
    print("LINKEDIN SCRAPER - BUILD SCRIPT")
    print("="*80)
    
    # 1. Check Prerequisites
    print("\n[1/4] Checking Prerequisites...")
    
    # Check for PyInstaller
    try:
        import PyInstaller
        print("[OK] PyInstaller is installed")
    except ImportError:
        print("\n[ERROR] PyInstaller not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # 2. Prepare Resources
    print("\n[2/4] Preparing Resources...")
    
    # Ensure Playwright browsers are installed
    print("Checking Playwright browsers...")
    subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
    
    '''
    # Get Playwright browser path
    import playwright
    package_path = Path(playwright.__file__).parent
    browsers_path = package_path / "driver" / "package" / ".local-browsers"
    '''
    
    # 3. Create Spec File (or run PyInstaller directly)
    print("\n[3/4] Building Executable...")
    
    # Define build command
    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--clean",
        "--windowed",  # No console window
        "--name=LinkedInScraper",
        "--add-data=linkedin_session.json;.",  # Include session template if exists
        "--collect-all=playwright",
        "--collect-all=pymongo",
        "main.py"
    ]
    
    print(f"Running: {' '.join(cmd)}")
    subprocess.check_call(cmd)
    
    # 4. Finalize
    print("\n[4/4] Finalizing...")
    dist_path = Path("dist/LinkedInScraper")
    
    print("\n" + "="*80)
    print("BUILD SUCCESSFUL!")
    print("="*80)
    print(f"Application files created at: {dist_path.absolute()}")
    print("\nTo create the final SINGLE INSTALLER EXE:")
    print("1. Install Inno Setup (https://jrsoftware.org/isdl.php)")
    print("2. Right-click 'setup.iss' and select 'Compile'")
    print("3. The final 'JobScraperSetup.exe' will be in the 'Output' folder.")
    print("="*80)

if __name__ == "__main__":
    build_executable()
