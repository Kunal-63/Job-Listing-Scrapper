#!/usr/bin/env python3
"""
LinkedIn Job Scraper with Tkinter GUI

This application provides a graphical interface to:
1. Login to LinkedIn
2. Input a job listing URL
3. Scrape all jobs from the listing
4. Display the results in a user-friendly format
"""

import asyncio
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
from typing import List, Optional
import json
from datetime import datetime

from linkedin_scraper.core.browser import BrowserManager
from linkedin_scraper.scrapers.job_search import JobSearchScraper
from linkedin_scraper.scrapers.job import JobScraper


class LinkedInJobScraperGUI:
    """Tkinter GUI for LinkedIn Job Scraper"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("LinkedIn Job Scraper")
        self.root.geometry("1000x700")
        self.root.config(bg="#f5f5f5")
        
        # State variables
        self.browser = None
        self.is_logged_in = False
        self.scraped_jobs = []
        self.is_scraping = False
        
        # Configure styles
        self.setup_styles()
        
        # Create main notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create tabs
        self.login_frame = ttk.Frame(self.notebook)
        self.scraper_frame = ttk.Frame(self.notebook)
        self.results_frame = ttk.Frame(self.notebook)
        
        self.notebook.add(self.login_frame, text="Login")
        self.notebook.add(self.scraper_frame, text="Scrape Jobs")
        self.notebook.add(self.results_frame, text="Results")
        
        # Build UI
        self.build_login_ui()
        self.build_scraper_ui()
        self.build_results_ui()
    
    def setup_styles(self):
        """Configure ttk styles"""
        style = ttk.Style()
        style.theme_use('clam')
        
        style.configure('Header.TLabel', font=('Arial', 14, 'bold'), foreground='#1f497d')
        style.configure('Success.TLabel', foreground='green')
        style.configure('Error.TLabel', foreground='red')
        style.configure('Info.TLabel', foreground='#0073b1')
    
    def build_login_ui(self):
        """Build login tab UI"""
        # Main container
        main_container = ttk.Frame(self.login_frame, padding="20")
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # Header
        header = ttk.Label(main_container, text="LinkedIn Login", style='Header.TLabel')
        header.pack(pady=(0, 20))
        
        # Status frame
        status_frame = ttk.LabelFrame(main_container, text="Login Status", padding="15")
        status_frame.pack(fill=tk.X, pady=(0, 20))
        
        self.status_label = ttk.Label(status_frame, text="Not logged in", style='Error.TLabel')
        self.status_label.pack(anchor=tk.W)
        
        # Instructions
        instructions_frame = ttk.LabelFrame(main_container, text="Instructions", padding="15")
        instructions_frame.pack(fill=tk.X, pady=(0, 20))
        
        instructions = """
1. Click the "Start Login" button below
2. A browser window will open with LinkedIn login page
3. Log in to LinkedIn manually (you have 5 minutes)
4. Complete any 2FA or CAPTCHA challenges if prompted
5. Wait for your LinkedIn feed to load
6. The script will automatically detect successful login

The session will be saved to linkedin_session.json for future use.
        """
        
        instructions_label = ttk.Label(instructions_frame, text=instructions.strip(), justify=tk.LEFT)
        instructions_label.pack(anchor=tk.W)
        
        # Button frame
        button_frame = ttk.Frame(main_container)
        button_frame.pack(fill=tk.X, pady=20)
        
        self.login_button = ttk.Button(
            button_frame,
            text="Start Login",
            command=self.start_login
        )
        self.login_button.pack(side=tk.LEFT, padx=5)
        
        self.logout_button = ttk.Button(
            button_frame,
            text="Clear Session",
            command=self.clear_session,
            state=tk.DISABLED
        )
        self.logout_button.pack(side=tk.LEFT, padx=5)
        
        # Progress frame
        progress_frame = ttk.LabelFrame(main_container, text="Progress", padding="15")
        progress_frame.pack(fill=tk.X, pady=(0, 20))
        
        self.progress_text = scrolledtext.ScrolledText(
            progress_frame,
            height=10,
            width=60,
            state=tk.DISABLED
        )
        self.progress_text.pack(fill=tk.BOTH, expand=True)
    
    def build_scraper_ui(self):
        """Build scraper tab UI"""
        main_container = ttk.Frame(self.scraper_frame, padding="20")
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # Header
        header = ttk.Label(main_container, text="Job Search Scraper", style='Header.TLabel')
        header.pack(pady=(0, 20))
        
        # URL input frame
        url_frame = ttk.LabelFrame(main_container, text="Job Listing URL", padding="15")
        url_frame.pack(fill=tk.X, pady=(0, 20))
        
        ttk.Label(url_frame, text="Enter LinkedIn Job Search URL:").pack(anchor=tk.W, pady=(0, 5))
        
        self.url_input = ttk.Entry(url_frame, width=70)
        self.url_input.pack(fill=tk.X, pady=(0, 10))
        self.url_input.insert(0, "https://www.linkedin.com/jobs/search/?keywords=software%20engineer&location=")
        
        # Instructions
        ttk.Label(
            url_frame,
            text="Example: https://www.linkedin.com/jobs/search/?keywords=python&location=San%20Francisco",
            foreground="gray"
        ).pack(anchor=tk.W)
        
        # Options frame
        options_frame = ttk.LabelFrame(main_container, text="Scraping Options", padding="15")
        options_frame.pack(fill=tk.X, pady=(0, 20))
        
        ttk.Label(options_frame, text="Max jobs to scrape:").pack(anchor=tk.W, pady=(0, 5))
        
        self.max_jobs_var = tk.StringVar(value="25")
        max_jobs_spin = ttk.Spinbox(
            options_frame,
            from_=1,
            to=100,
            textvariable=self.max_jobs_var,
            width=10
        )
        max_jobs_spin.pack(anchor=tk.W)
        
        # Button frame
        button_frame = ttk.Frame(main_container)
        button_frame.pack(fill=tk.X, pady=20)
        
        self.scrape_button = ttk.Button(
            button_frame,
            text="Start Scraping",
            command=self.start_scraping,
            state=tk.DISABLED
        )
        self.scrape_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(
            button_frame,
            text="Stop Scraping",
            command=self.stop_scraping,
            state=tk.DISABLED
        )
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        # Progress frame
        progress_frame = ttk.LabelFrame(main_container, text="Scraping Progress", padding="15")
        progress_frame.pack(fill=tk.BOTH, expand=True)
        
        self.scraper_progress_text = scrolledtext.ScrolledText(
            progress_frame,
            height=15,
            width=60,
            state=tk.DISABLED
        )
        self.scraper_progress_text.pack(fill=tk.BOTH, expand=True)
    
    def build_results_ui(self):
        """Build results tab UI"""
        main_container = ttk.Frame(self.results_frame, padding="20")
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # Header
        header = ttk.Label(main_container, text="Scraped Jobs", style='Header.TLabel')
        header.pack(pady=(0, 20))
        
        # Button frame
        button_frame = ttk.Frame(main_container)
        button_frame.pack(fill=tk.X, pady=(0, 20))
        
        ttk.Button(
            button_frame,
            text="Export to JSON",
            command=self.export_to_json
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            button_frame,
            text="Clear Results",
            command=self.clear_results
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(button_frame, text="Total jobs: 0").pack(side=tk.LEFT, padx=20)
        self.jobs_count_label = ttk.Label(button_frame, text="0", foreground="green", font=('Arial', 12, 'bold'))
        self.jobs_count_label.pack(side=tk.LEFT)
        
        # Results display
        results_frame = ttk.LabelFrame(main_container, text="Job Details", padding="15")
        results_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create Treeview
        columns = ("Title", "Company", "Location", "Posted", "Applicants")
        self.results_tree = ttk.Treeview(results_frame, columns=columns, height=20)
        self.results_tree.column("#0", width=0, stretch=tk.NO)
        self.results_tree.column("Title", anchor=tk.W, width=250)
        self.results_tree.column("Company", anchor=tk.W, width=150)
        self.results_tree.column("Location", anchor=tk.W, width=150)
        self.results_tree.column("Posted", anchor=tk.W, width=100)
        self.results_tree.column("Applicants", anchor=tk.W, width=100)
        
        self.results_tree.heading("#0", text="", anchor=tk.W)
        self.results_tree.heading("Title", text="Job Title", anchor=tk.W)
        self.results_tree.heading("Company", text="Company", anchor=tk.W)
        self.results_tree.heading("Location", text="Location", anchor=tk.W)
        self.results_tree.heading("Posted", text="Posted", anchor=tk.W)
        self.results_tree.heading("Applicants", text="Applicants", anchor=tk.W)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.results_tree.yview)
        self.results_tree.configure(yscroll=scrollbar.set)
        
        self.results_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind double click to show details
        self.results_tree.bind("<Double-1>", self.show_job_details)
    
    def log_progress(self, message: str, tab: str = "login"):
        """Log progress message to appropriate tab"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}\n"
        
        if tab == "login":
            text_widget = self.progress_text
        else:
            text_widget = self.scraper_progress_text
        
        text_widget.config(state=tk.NORMAL)
        text_widget.insert(tk.END, log_message)
        text_widget.see(tk.END)
        text_widget.config(state=tk.DISABLED)
    
    def start_login(self):
        """Start login process in a separate thread"""
        self.login_button.config(state=tk.DISABLED)
        thread = threading.Thread(target=self._run_login, daemon=True)
        thread.start()
    
    def _run_login(self):
        """Run login process (async)"""
        try:
            asyncio.run(self._login_async())
        except Exception as e:
            self.log_progress(f"❌ Login failed: {str(e)}")
            messagebox.showerror("Login Error", f"Login failed: {str(e)}")
            self.login_button.config(state=tk.NORMAL)
    
    async def _login_async(self):
        """Async login process"""
        try:
            self.log_progress("🔄 Starting browser...")
            
            async with BrowserManager(headless=False) as browser:
                self.browser = browser
                
                self.log_progress("📱 Navigating to LinkedIn login page...")
                await browser.page.goto("https://www.linkedin.com/login")
                
                self.log_progress("🔐 Please log in to LinkedIn in the browser window...")
                self.log_progress("⏳ Waiting for login (5 minutes timeout)...")
                
                # Wait for manual login
                from linkedin_scraper import wait_for_manual_login
                await wait_for_manual_login(browser.page, timeout=300000)
                
                # Save session
                self.log_progress("💾 Saving session to linkedin_session.json...")
                await browser.save_session("linkedin_session.json")
                
                self.log_progress("✅ Login successful!")
                self.is_logged_in = True
                self.status_label.config(text="✓ Logged in", style='Success.TLabel')
                self.login_button.config(state=tk.DISABLED)
                self.logout_button.config(state=tk.NORMAL)
                self.scrape_button.config(state=tk.NORMAL)
                
                messagebox.showinfo("Success", "Login successful! You can now scrape jobs.")
        
        except Exception as e:
            self.log_progress(f"❌ Error: {str(e)}")
            self.login_button.config(state=tk.NORMAL)
            raise
    
    def clear_session(self):
        """Clear the session"""
        self.is_logged_in = False
        self.browser = None
        self.status_label.config(text="Not logged in", style='Error.TLabel')
        self.login_button.config(state=tk.NORMAL)
        self.logout_button.config(state=tk.DISABLED)
        self.scrape_button.config(state=tk.DISABLED)
        self.log_progress("Session cleared")
    
    def start_scraping(self):
        """Start scraping process"""
        url = self.url_input.get().strip()
        
        if not url:
            messagebox.showerror("Error", "Please enter a job listing URL")
            return
        
        if not self.is_logged_in:
            messagebox.showerror("Error", "Please login first")
            return
        
        self.is_scraping = True
        self.scrape_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.scraper_progress_text.config(state=tk.NORMAL)
        self.scraper_progress_text.delete(1.0, tk.END)
        self.scraper_progress_text.config(state=tk.DISABLED)
        
        thread = threading.Thread(target=self._run_scraping, daemon=True)
        thread.start()
    
    def _run_scraping(self):
        """Run scraping process (async)"""
        try:
            asyncio.run(self._scrape_async())
        except Exception as e:
            self.log_progress(f"❌ Scraping failed: {str(e)}", tab="scraper")
            messagebox.showerror("Scraping Error", f"Scraping failed: {str(e)}")
            self._reset_scraping_buttons()
    
    async def _scrape_async(self):
        """Async scraping process"""
        try:
            url = self.url_input.get().strip()
            max_jobs = int(self.max_jobs_var.get())
            
            self.log_progress(f"📄 Loading job listing: {url}", tab="scraper")
            
            async with BrowserManager(headless=True) as browser:
                await browser.load_session("linkedin_session.json")
                self.log_progress("✓ Session loaded", tab="scraper")
                
                # Search for jobs and scrape details directly from list view
                search_scraper = JobSearchScraper(browser.page)
                self.log_progress(f"🔍 Searching for jobs (max: {max_jobs})...", tab="scraper")
                
                # This now returns Job objects directly instead of URLs
                self.scraped_jobs = await search_scraper.search(limit=max_jobs)
                
                self.log_progress(f"✓ Scraped {len(self.scraped_jobs)} jobs successfully", tab="scraper")
                
                for i, job in enumerate(self.scraped_jobs, 1):
                    if not self.is_scraping:
                        self.log_progress("⏹ Scraping stopped by user", tab="scraper")
                        break
                    # Only log every 2nd job to save time
                    if i % 2 == 0 or i == 1:
                        self.log_progress(f"[{i}/{len(self.scraped_jobs)}] ✓ {job.job_title[:40]}", tab="scraper")
                
                self.log_progress(f"\n✅ Scraping complete! Total jobs: {len(self.scraped_jobs)}", tab="scraper")
                self._display_results()
                messagebox.showinfo("Success", f"Scraped {len(self.scraped_jobs)} jobs successfully!")
        
        except Exception as e:
            self.log_progress(f"❌ Error: {str(e)}", tab="scraper")
            raise
        
        finally:
            self._reset_scraping_buttons()
    
    def stop_scraping(self):
        """Stop the scraping process"""
        self.is_scraping = False
        self.stop_button.config(state=tk.DISABLED)
        self.log_progress("⏹ Stopping scraping...", tab="scraper")
    
    def _reset_scraping_buttons(self):
        """Reset scraping buttons to normal state"""
        self.is_scraping = False
        self.scrape_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
    
    def _display_results(self):
        """Display scraped jobs in results tab"""
        # Clear existing items
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        
        # Add new items
        for job in self.scraped_jobs:
            self.results_tree.insert(
                "",
                tk.END,
                values=(
                    job.job_title or "N/A",
                    job.company or "N/A",
                    job.location or "N/A",
                    job.posted_date or "N/A",
                    job.applicant_count or "N/A"
                )
            )
        
        # Update count
        self.jobs_count_label.config(text=str(len(self.scraped_jobs)))
    
    def show_job_details(self, event):
        """Show detailed information for selected job"""
        selection = self.results_tree.selection()
        if not selection:
            return
        
        index = list(self.results_tree.get_children()).index(selection[0])
        job = self.scraped_jobs[index]
        
        # Create detail window
        detail_window = tk.Toplevel(self.root)
        detail_window.title(f"Job Details: {job.job_title}")
        detail_window.geometry("800x600")
        
        # Create text widget
        text_widget = scrolledtext.ScrolledText(detail_window, wrap=tk.WORD)
        text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        text_widget.config(state=tk.NORMAL)
        
        # Format job details
        details = f"""
JOB TITLE: {job.job_title}
COMPANY: {job.company}
COMPANY URL: {job.company_linkedin_url}
LOCATION: {job.location}
POSTED DATE: {job.posted_date}
APPLICANT COUNT: {job.applicant_count}
JOB URL: {job.linkedin_url}

{'='*80}
DESCRIPTION:
{'='*80}

{job.job_description or 'No description available'}
        """
        
        text_widget.insert(tk.END, details.strip())
        text_widget.config(state=tk.DISABLED)
    
    def export_to_json(self):
        """Export results to JSON file"""
        if not self.scraped_jobs:
            messagebox.showwarning("No Data", "No jobs to export. Please scrape first.")
            return
        
        filename = f"jobs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        try:
            data = []
            for job in self.scraped_jobs:
                data.append({
                    "job_title": job.job_title,
                    "company": job.company,
                    "company_url": job.company_linkedin_url,
                    "location": job.location,
                    "posted_date": job.posted_date,
                    "applicant_count": job.applicant_count,
                    "job_url": job.linkedin_url,
                    "description": job.job_description
                })
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            messagebox.showinfo("Success", f"Data exported to {filename}")
            self.log_progress(f"📁 Exported data to {filename}", tab="scraper")
        
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export: {str(e)}")
    
    def clear_results(self):
        """Clear all results"""
        self.scraped_jobs = []
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        self.jobs_count_label.config(text="0")
        self.log_progress("Results cleared", tab="scraper")


def main():
    """Main entry point"""
    root = tk.Tk()
    app = LinkedInJobScraperGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
