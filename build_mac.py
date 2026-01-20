import os
import sys
import shutil
import subprocess
from pathlib import Path

def build_mac_app():
    """Build the standalone macOS .app and .dmg"""
    print("="*80)
    print("LINKEDIN SCRAPER - MAC BUILD SCRIPT")
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
    
    # Ensure Playwright browsers are installed (for local testing/building)
    # We won't bundle them, but good to have.
    subprocess.call([sys.executable, "-m", "playwright", "install", "chromium"])
    
    # 3. Build .app Bundle
    print("\n[3/4] Building .app Bundle...")
    
    # Define build command
    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--clean",
        "--windowed",  # Important for Mac .app
        "--name=LinkedInScraper",
        "--add-data=linkedin_session.json:.", # Colon separator for Mac
        "--collect-all=playwright",
        "--collect-all=pymongo",
        "--hidden-import=bson",
        "--hidden-import=dotenv",
        "--hidden-import=pydantic",
        "--icon=app_icon.icns", # Optional: You'll need an .icns file or remove this line
        "main.py"
    ]
    
    # Remove icon argument if file doesn't exist
    if not os.path.exists("app_icon.icns"):
        cmd = [x for x in cmd if not x.startswith("--icon")]

    print(f"Running: {' '.join(cmd)}")
    subprocess.check_call(cmd)
    
    # 4. Create DMG
    print("\n[4/4] Creating DMG Installer...")
    dist_path = Path("dist")
    app_path = dist_path / "LinkedInScraper.app"
    dmg_name = "LinkedInScraper.dmg"
    dmg_path = dist_path / dmg_name
    
    if dmg_path.exists():
        os.remove(dmg_path)

    # Use hdiutil to create DMG (standard macOS tool)
    # We creates a simple DMG containing the App and a link to Applications folder
    
    print("Creating temporary folder for DMG content...")
    dmg_source = dist_path / "dmg_source"
    if dmg_source.exists():
        shutil.rmtree(dmg_source)
    dmg_source.mkdir()
    
    # Copy .app to dmg source
    print("Copying .app to DMG folder...")
    shutil.copytree(app_path, dmg_source / "LinkedInScraper.app")
    
    # Create symlink to /Applications
    print("Creating Applications symlink...")
    os.symlink("/Applications", dmg_source / "Applications")
    
    print("Packing DMG...")
    subprocess.check_call([
        "hdiutil", "create",
        "-volname", "LinkedInScraper",
        "-srcfolder", str(dmg_source),
        "-ov",
        "-format", "UDZO",
        str(dmg_path)
    ])
    
    # ... (Keep previous code for DMG creation) ...
    
    # 5. Create PKG Installer (Wizard Style)
    print("\n[5/4] Creating PKG Installer (Windows-like Wizard)...")
    pkg_name = "LinkedInScraper_Setup.pkg"
    pkg_path = dist_path / pkg_name
    
    # Identify where to install on the user's mac
    install_location = "/Applications"
    
    # Build the package
    # This creates a standard macOS installer "wizard"
    subprocess.check_call([
        "pkgbuild",
        "--root", str(app_path.parent), # We need to point to folder containing .app
        "--component", str(app_path),
        "--install-location", install_location,
        str(pkg_path)
    ])
    
    print("\n" + "="*80)
    print("BUILD SUCCESSFUL!")
    print("="*80)
    print(f"1. DMG (Drag-and-Drop): {dmg_path.absolute()}")
    print(f"2. PKG (Setup Wizard):  {pkg_path.absolute()}")
    print("\nTransfer either file to your remote users.")
    print("The PKG file manages the installation automatically (like setup.exe).")

if __name__ == "__main__":
    if sys.platform != "darwin":
        print("ERROR: This script must be run on macOS.")
        print("You cannot build macOS apps from Windows.")
        print("Please copy this project to a Mac and run: python3 build_mac.py")
        sys.exit(1)
        
    build_mac_app()
