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
    print("\n[1/5] Checking Prerequisites...")
    
    # Check for PyInstaller
    try:
        import PyInstaller
        print("[OK] PyInstaller is installed")
    except ImportError:
        print("\n[ERROR] PyInstaller not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # 2. Install Playwright browsers BEFORE building
    print("\n[2/5] Installing Playwright Browsers...")
    print("This will download Chromium to your system...")
    
    try:
        # Install browsers to default location
        subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
        print("[OK] Chromium installed successfully")
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Failed to install browsers: {e}")
        return
    
    # 3. Find Playwright browsers location
    print("\n[3/5] Locating Playwright Files...")
    
    # Get playwright package location
    import playwright
    playwright_dir = Path(playwright.__file__).parent
    
    # Find browser installation
    # Playwright installs to %USERPROFILE%\AppData\Local\ms-playwright on Windows
    if sys.platform == "win32":
        browsers_path = Path.home() / "AppData" / "Local" / "ms-playwright"
    else:
        browsers_path = Path.home() / ".cache" / "ms-playwright"
    
    if not browsers_path.exists():
        print(f"[ERROR] Browsers not found at {browsers_path}")
        print("Run 'playwright install chromium' manually first")
        return
    
    print(f"[OK] Browsers found at: {browsers_path}")
    
    # Find driver directory
    driver_dir = playwright_dir / "driver"
    if not driver_dir.exists():
        print(f"[ERROR] Driver directory not found at {driver_dir}")
        return
    
    print(f"[OK] Driver found at: {driver_dir}")
    
    # 4. Build PyInstaller command
    print("\n[4/5] Building Executable...")
    
    # Build the add-data strings for browsers
    # Note: We don't bundle linkedin_session.json - it's created in AppData at runtime
    add_data_parts = []
    
    # Add entire playwright driver directory
    add_data_parts.append(
        f"--add-data={driver_dir}{os.pathsep}playwright/driver"
    )
    
    # Add browser binaries (this will be large!)
    chromium_dir = browsers_path / "chromium-1140"  # Adjust version as needed
    if chromium_dir.exists():
        add_data_parts.append(
            f"--add-data={chromium_dir}{os.pathsep}ms-playwright/chromium-1140"
        )
        print(f"[OK] Adding Chromium from: {chromium_dir}")
    else:
        # Try to find any chromium folder
        chromium_folders = list(browsers_path.glob("chromium-*"))
        if chromium_folders:
            chromium_dir = chromium_folders[0]
            version = chromium_dir.name
            add_data_parts.append(
                f"--add-data={chromium_dir}{os.pathsep}ms-playwright/{version}"
            )
            print(f"[OK] Adding Chromium from: {chromium_dir}")
        else:
            print("[WARNING] Chromium directory not found - browsers may not work!")
    
    # Define build command
    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name=LinkedInScraper",
        *add_data_parts,
        "--hidden-import=playwright",
        "--hidden-import=playwright.sync_api",
        "--hidden-import=playwright._impl._driver",
        "--collect-all=playwright",
        "--collect-all=pymongo",
        "--hidden-import=bson",
        "--hidden-import=dotenv",
        "--hidden-import=pydantic",
        "--hidden-import=greenlet",
        # Exclude unnecessary files to reduce size
        "--exclude-module=matplotlib",
        "--exclude-module=numpy",
        "--exclude-module=pandas",
        "main.py"
    ]
    
    print(f"\nRunning PyInstaller...")
    print(f"Command: {' '.join(cmd[:5])}... (truncated)")
    
    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] PyInstaller failed: {e}")
        return
        
    # 5. Finalize   
    print("\n[5/5] Finalizing...")
    dist_path = Path("dist/LinkedInScraper")
    
    # Create a runtime config file
    config = {
        "playwright_bundled": True,
        "browser_path": "ms-playwright"
    }
    
    import json
    config_file = dist_path / "runtime_config.json"
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
    
    print("\n" + "="*80)
    print("BUILD SUCCESSFUL!")
    print("="*80)
    print(f"Application files created at: {dist_path.absolute()}")
    print(f"\nIMPORTANT: The bundled EXE is LARGE (~500MB) because it includes Chromium.")
    print("\nNext steps:")
    print("1. Test the EXE by running: dist\\LinkedInScraper\\LinkedInScraper.exe")
    print("2. If it works, create installer with Inno Setup:")
    print("   - Right-click 'setup.iss' and select 'Compile'")
    print("   - The final installer will be in the 'Output' folder")
    print("="*80)

if __name__ == "__main__":
    build_executable()