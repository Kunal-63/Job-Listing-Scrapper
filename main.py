import asyncio
import logging
import sys
import os
import tkinter as tk
from tkinter import messagebox
import threading
import subprocess
from pathlib import Path

# Fix for Playwright in frozen app:
# PyInstaller's Playwright hook sets PLAYWRIGHT_BROWSERS_PATH to 0 (local).
# This causes it to look for browsers in the read-only Program Files directory.
# We unset this to allow Playwright to use the default User's AppData location.
if getattr(sys, 'frozen', False):
    import os
    # Force Playwright to look in the standard user directory (User/AppData/Local/ms-playwright)
    # This overrides PyInstaller's hook which forces it to look in the local _internal folder.
    user_profile = os.environ.get('USERPROFILE')
    if user_profile:
        # Standard location for Windows
        # We explicitly set this so both the runtime lookup and 'playwright install' 
        # use the same global writable location.
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(user_profile, 'AppData', 'Local', 'ms-playwright')
    elif "PLAYWRIGHT_BROWSERS_PATH" in os.environ:
        # Fallback: just remove the local override if we can't determine user profile
        del os.environ["PLAYWRIGHT_BROWSERS_PATH"]

from mongo_client import get_db, get_client
from linkedin_scraper import wait_for_manual_login
from linkedin_scraper.core.browser import BrowserManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)


class LinkedInScraperApp:
    """Main application with MongoDB integration and modern UI."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Plugs - LinkedIn Job Scraper")
        self.root.geometry("500x650")
        self.root.config(bg="#f8f9fa")
        
        # State variables
        self.is_logged_in = False
        self.work_station_name = tk.StringVar()
        self.terms_accepted = tk.BooleanVar(value=False)
        
        # Current screen
        self.current_screen = None
        
        # Show login screen
        self.show_login_screen()
    
    def clear_screen(self):
        """Clear current screen."""
        if self.current_screen:
            self.current_screen.destroy()
    
    def show_login_screen(self):
        """Show modern login screen."""
        self.clear_screen()
        
        # Main container
        self.current_screen = tk.Frame(self.root, bg="#f8f9fa")
        self.current_screen.pack(fill=tk.BOTH, expand=True, padx=40, pady=40)
        
        # Header - "Plugs"
        header = tk.Label(
            self.current_screen,
            text="Plugs",
            font=("Arial", 48, "bold"),
            bg="#f8f9fa",
            fg="#000000"
        )
        header.pack(pady=(20, 10))
        
        # Subtitle
        subtitle_text = "Setup your profile to see how we\nconnect you with high-intent buyers\nready to take action."
        subtitle = tk.Label(
            self.current_screen,
            text=subtitle_text,
            font=("Arial", 13),
            bg="#f8f9fa",
            fg="#4a5568",
            justify=tk.CENTER
        )
        subtitle.pack(pady=(0, 30))
        
        # Work station name input
        input_frame = tk.Frame(self.current_screen, bg="#f8f9fa")
        input_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.work_station_entry = tk.Entry(
            input_frame,
            textvariable=self.work_station_name,
            font=("Arial", 12),
            bg="#ffffff",
            fg="#000000",
            relief=tk.SOLID,
            borderwidth=1,
            highlightthickness=2,
            highlightbackground="#e2e8f0",
            highlightcolor="#0073b1"
        )
        self.work_station_entry.pack(fill=tk.X, ipady=10, ipadx=10)
        self.work_station_entry.insert(0, "Choose your work station name")
        self.work_station_entry.bind("<FocusIn>", self._on_entry_focus_in)
        self.work_station_entry.bind("<FocusOut>", self._on_entry_focus_out)
        self.work_station_entry.config(fg="#9ca3af")
        
        # Terms and conditions checkbox
        terms_frame = tk.Frame(self.current_screen, bg="#f8f9fa")
        terms_frame.pack(fill=tk.X, pady=(0, 20))
        
        terms_check = tk.Checkbutton(
            terms_frame,
            text="I agree with terms and conditions of use",
            variable=self.terms_accepted,
            font=("Arial", 10),
            bg="#f8f9fa",
            fg="#4a5568",
            activebackground="#f8f9fa",
            selectcolor="#ffffff",
            relief=tk.FLAT
        )
        terms_check.pack(anchor=tk.W)
        
        # Connect LinkedIn button
        self.connect_button = tk.Button(
            self.current_screen,
            text="🔗 Connect your LinkedIn",
            font=("Arial", 13, "bold"),
            bg="#000000",
            fg="#ffffff",
            activebackground="#1a1a1a",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            cursor="hand2",
            command=self.start_linkedin_login,
            padx=20,
            pady=15
        )
        self.connect_button.pack(fill=tk.X, pady=(0, 15))
        
        # Footer text
        footer_text = "We track recruitment for you on daily bases and our agent provide\nyour best fit Ideal profile linkedin contact"
        footer = tk.Label(
            self.current_screen,
            text=footer_text,
            font=("Arial", 9),
            bg="#f8f9fa",
            fg="#9ca3af",
            justify=tk.CENTER
        )
        footer.pack(pady=(10, 0))
    
    def _on_entry_focus_in(self, event):
        """Handle entry focus in."""
        if self.work_station_entry.get() == "Choose your work station name":
            self.work_station_entry.delete(0, tk.END)
            self.work_station_entry.config(fg="#000000")
    
    def _on_entry_focus_out(self, event):
        """Handle entry focus out."""
        if not self.work_station_entry.get():
            self.work_station_entry.insert(0, "Choose your work station name")
            self.work_station_entry.config(fg="#9ca3af")
    
    def start_linkedin_login(self):
        """Start LinkedIn login process."""
        # Validate inputs
        work_station = self.work_station_name.get()
        if not work_station or work_station == "Choose your work station name":
            messagebox.showerror("Error", "Please enter your work station name")
            return
        
        if not self.terms_accepted.get():
            messagebox.showerror("Error", "Please accept the terms and conditions")
            return
        
        # Disable button
        self.connect_button.config(state=tk.DISABLED, text="Connecting...")
        
        # Start login in background thread
        threading.Thread(target=self._run_login, daemon=True).start()
    
    def _run_login(self):
        """Run LinkedIn login process."""
        try:
            asyncio.run(self._login_async())
        except Exception as e:
            logger.error(f"Login failed: {e}")
            messagebox.showerror("Login Error", f"Login failed: {str(e)}")
            self.connect_button.config(state=tk.NORMAL, text="🔗 Connect your LinkedIn")
    
    async def _login_async(self):
        """Async LinkedIn login process."""
        try:
            logger.info("Starting LinkedIn login...")
            
            async with BrowserManager(headless=False, disable_javascript=False) as browser:
                logger.info("Navigating to LinkedIn login page...")
                await browser.page.goto("https://www.linkedin.com/login")
                
                logger.info("Waiting for manual login (5 minutes timeout)...")
                await wait_for_manual_login(browser.page, timeout=300000)
                
                # Save session
                logger.info("Saving session...")
                await browser.save_session("linkedin_session.json")
                
                self.is_logged_in = True
                logger.info("Login successful!")
                
                # Switch to dashboard
                self.root.after(0, self.show_dashboard)
        
        except Exception as e:
            logger.error(f"Login error: {e}")
            raise
    
    def show_dashboard(self):
        """Show main dashboard after successful login with Start Scraping button."""
        self.clear_screen()
        
        # Main container
        self.current_screen = tk.Frame(self.root, bg="#f8f9fa")
        self.current_screen.pack(fill=tk.BOTH, expand=True, padx=40, pady=40)
        
        # Keep window size
        self.root.geometry("500x400")
        
        # Header
        header = tk.Label(
            self.current_screen,
            text="LinkedIn Scraper",
            font=("Arial", 32, "bold"),
            bg="#f8f9fa",
            fg="#000000"
        )
        header.pack(pady=(40, 20))
        
        # Status message
        status = tk.Label(
            self.current_screen,
            text="✓ Successfully connected to LinkedIn",
            font=("Arial", 12),
            bg="#f8f9fa",
            fg="#10b981"
        )
        status.pack(pady=(0, 40))
        
        # Start Scraping Button - Large and prominent
        self.scrape_button = tk.Button(
            self.current_screen,
            text="🚀 Start Scraping",
            font=("Arial", 16, "bold"),
            bg="#0073b1",
            fg="#ffffff",
            activebackground="#005582",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            cursor="hand2",
            command=self.start_background_scraping,
            padx=40,
            pady=20
        )
        self.scrape_button.pack(pady=20)
        
        # Info text
        info_text = "Click to start scraping job links from MongoDB\nThe process will run in the background"
        info = tk.Label(
            self.current_screen,
            text=info_text,
            font=("Arial", 10),
            bg="#f8f9fa",
            fg="#6b7280",
            justify=tk.CENTER
        )
        info.pack(pady=(10, 0))
    
    def start_background_scraping(self):
        """Start scraping process in background."""
        # Disable button
        self.scrape_button.config(state=tk.DISABLED, text="⏳ Starting...")
        
        # Show confirmation
        result = messagebox.showinfo(
            "Scraping Started",
            "The scraping process has been started in the background.\n\n"
            "You can view the process in Task Manager.\n"
            "Check 'scraper_background.log' for progress.\n\n"
            "The application window will now close."
        )
        
        # Start background process
        threading.Thread(target=self._start_background_process, daemon=True).start()
        
        # Give it a moment to start, then close the window
        self.root.after(2000, self._close_application)
    
    def _close_application(self):
        """Close the application window."""
        logger.info("Closing application window - background scraper is running")
        self.root.quit()
        self.root.destroy()
    

    def _start_background_process(self):
        """Start the actual background scraping process."""
        try:
            # Determine how to launch the scraper
            if getattr(sys, 'frozen', False):
                # Running as compiled exe - call self with flag
                executable = sys.executable
                args = [executable, "--scraper"]
            else:
                # Running as script
                executable = sys.executable
                script_path = Path(__file__).parent / "main.py"
                args = [executable, str(script_path), "--scraper"]
            
            # Start as a detached background process
            if sys.platform == "win32":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                
                subprocess.Popen(
                    args,
                    creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
                    startupinfo=startupinfo,
                    close_fds=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            else:
                subprocess.Popen(
                    args,
                    start_new_session=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            
            logger.info("Background scraper process started successfully")
            
        except Exception as e:
            logger.error(f"Error starting background process: {e}")
            messagebox.showerror("Error", f"Failed to start background process: {str(e)}")


def ensure_playwright(force=False):
    """Ensure Playwright browsers are installed."""
    try:
        from playwright.sync_api import sync_playwright
        logger.info("Checking Playwright browsers...")
        
        needed = force
        if not needed:
            # Try to launch browser to verify installation
            try:
                with sync_playwright() as p:
                    p.chromium.launch(headless=True).close()
                    logger.info("Playwright browsers verified.")
            except Exception:
                needed = True
            
        if needed:
            logger.info("Browsers not found (or forced). Installing...")
            if not force: # Only show GUI message if not forced (installer handles UX)
                messagebox.showinfo("First Time Setup", "Installing browser components...\nThis may take a few minutes. Please wait.")
            
            if getattr(sys, 'frozen', False):
                # In frozen app, attempt to use internal CLI
                try:
                    # We need to monkeypatch sys.argv for the internal main function
                    old_argv = sys.argv
                    sys.argv = ["playwright", "install", "chromium"]
                    
                    from playwright.__main__ import main as pw_main
                    try:
                        pw_main()
                    except SystemExit as e:
                        # SystemExit is expected after install completes
                        if e.code != 0:
                            logger.warning(f"Playwright install exited with code {e.code} (may still have succeeded)")
                    finally:
                        sys.argv = old_argv
                        
                except Exception as e:
                    logger.warning(f"Playwright install attempt: {e} (browsers may still be available)")
                    # Don't show error - browsers might be pre-bundled or installed already
            else:
                # In script mode, use subprocess
                result = subprocess.run(
                    [sys.executable, "-m", "playwright", "install", "chromium"],
                    capture_output=True,
                    text=True
                )
                if result.returncode != 0:
                    logger.warning(f"Playwright install returned code {result.returncode}: {result.stderr}")
                    # Don't raise - browser might still be installed
                else:
                    logger.info("Browsers installed successfully")
                
            logger.info("Browser installation completed.")
            
    except Exception as e:
        logger.warning(f"Playwright setup check: {e} (will attempt to continue)")
        # Don't fail here - browsers might be already installed or available



def main():
    """Main entry point."""
    # Check for CLI flags
    if len(sys.argv) > 1:
        if sys.argv[1] == "--scraper":
            # Run background scraper
            import background_scraper
            asyncio.run(background_scraper.main())
            return
        elif sys.argv[1] == "--install-browsers":
            # Just install browsers and exit
            ensure_playwright(force=True)
            return

    # Normal GUI mode
    # from local_db import ensure_db_running
    
    # Try to start local MongoDB
    # ensure_db_running()
    
    # Ensure Playwright browsers are installed (check only)
    ensure_playwright(force=False)
    
    root = tk.Tk()
    app = LinkedInScraperApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

