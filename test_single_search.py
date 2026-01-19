#!/usr/bin/env python3
"""
Test script to scrape a single job search URL and display results.
This helps debug what data is being fetched.
"""

import asyncio
import json
from datetime import datetime
from playwright.async_api import async_playwright

from linkedin_scraper.scrapers.job_search import JobSearchScraper
from linkedin_scraper.callbacks import SilentCallback


async def test_single_search_url():
    """Test scraping a single search URL."""
    
    # Test URL - you can change this to any search URL from your database
    test_url = "https://www.linkedin.com/jobs/search/?f_JT=F%2CP%2CC&f_TPR=r86400&f_WT=2&geoId=102713980&keywords=Product%20Designer&sortBy=DD"
    
    print("="*80)
    print("LinkedIn Job Search Test")
    print("="*80)
    print(f"\nTest URL: {test_url}")
    print(f"Starting at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    try:
        async with async_playwright() as p:
            # Launch browser
            print("Launching browser...")
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            
            # Load session
            print("Loading LinkedIn session...")
            try:
                with open("linkedin_session.json", "r") as f:
                    session_data = json.load(f)
                    if "cookies" in session_data:
                        await context.add_cookies(session_data["cookies"])
                        print("[OK] Session loaded")
            except Exception as e:
                print(f"[WARNING] Could not load session: {e}")
            
            # Create page
            page = await context.new_page()
            
            # Create scraper
            print("\nCreating JobSearchScraper...")
            scraper = JobSearchScraper(page, SilentCallback())
            
            # Scrape jobs
            print(f"\nScraping jobs from search URL...")
            print("Settings: limit=5, max_concurrent=2")
            print("-"*80)
            
            jobs = await scraper.search(
                search_url=test_url,
                limit=5,  # Only get 5 jobs for testing
                max_concurrent=2  # Lower concurrency for testing
            )
            
            print("-"*80)
            print(f"\n[RESULT] Found {len(jobs)} jobs\n")
            
            # Display results
            if jobs:
                for i, job in enumerate(jobs, 1):
                    print("="*80)
                    print(f"JOB #{i}")
                    print("="*80)
                    print(f"Title:           {job.job_title or 'N/A'}")
                    print(f"Company:         {job.company or 'N/A'}")
                    print(f"Company URL:     {job.company_linkedin_url or 'N/A'}")
                    print(f"Location:        {job.location or 'N/A'}")
                    print(f"Posted:          {job.posted_date or 'N/A'}")
                    print(f"Applicants:      {job.applicant_count or 'N/A'}")
                    print(f"Job URL:         {job.linkedin_url or 'N/A'}")
                    print(f"\nCompany Details:")
                    print(f"  Industry:      {job.industry or 'N/A'}")
                    print(f"  Size:          {job.company_size or 'N/A'}")
                    print(f"  Headquarters:  {job.headquarters or 'N/A'}")
                    print(f"  Founded:       {job.founded or 'N/A'}")
                    print(f"  Website:       {job.company_website or 'N/A'}")
                    print(f"\nCompany Overview:")
                    overview = job.company_about or "N/A"
                    print(f"  {overview[:200]}..." if len(overview) > 200 else f"  {overview}")
                    print(f"\nJob Description Preview:")
                    desc = job.job_description or "N/A"
                    print(f"  {desc[:200]}..." if len(desc) > 200 else f"  {desc}")
                    print()
                
                # Export to JSON for inspection
                export_data = []
                for job in jobs:
                    export_data.append({
                        "title": job.job_title,
                        "company": job.company,
                        "company_url": job.company_linkedin_url,
                        "location": job.location,
                        "posted_date": job.posted_date,
                        "applicant_count": job.applicant_count,
                        "job_url": job.linkedin_url,
                        "industry": job.industry,
                        "company_size": job.company_size,
                        "headquarters": job.headquarters,
                        "founded": job.founded,
                        "description": job.job_description
                    })
                
                filename = f"test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=2, ensure_ascii=False)
                
                print("="*80)
                print(f"[OK] Results exported to: {filename}")
                print("="*80)
            else:
                print("[WARNING] No jobs found!")
                print("\nPossible reasons:")
                print("  1. LinkedIn session expired - run main.py to re-login")
                print("  2. Search URL has no results")
                print("  3. LinkedIn changed their HTML structure")
                print("  4. Rate limiting - wait a few minutes and try again")
            
            await browser.close()
            
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\nFinished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    print("\n" + "="*80)
    print("SINGLE SEARCH URL TEST")
    print("="*80)
    print("\nThis script will:")
    print("  1. Load your LinkedIn session")
    print("  2. Scrape 5 jobs from a test search URL")
    print("  3. Display all data fetched")
    print("  4. Export results to JSON file")
    print("\nPress Ctrl+C to cancel\n")
    
    try:
        asyncio.run(test_single_search_url())
    except KeyboardInterrupt:
        print("\n\nTest cancelled by user")
    except Exception as e:
        print(f"\n\nFatal error: {e}")
