#!/usr/bin/env python3
"""
Multi-Platform Company Details Scraper

Fetches jobs pending company information from Firebase and scrapes company details.
Works with all registered platforms that support company scraping (primarily LinkedIn).

Usage:
    python scrape_multi_platform_companies.py
    python scrape_multi_platform_companies.py --platform linkedin --limit 50
    python scrape_multi_platform_companies.py --concurrent 3
"""

import asyncio
import argparse
import logging
import sys
from typing import Optional
from playwright.async_api import async_playwright

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.firebase_manager import FirebaseManager
from scrapers.core.platform_registry import PlatformFactory
from scrapers.core.data_models import CompanyData
from firebase_admin import firestore

# Import platforms to register them
import scrapers.platforms.linkedin
import scrapers.platforms.indeed
import scrapers.platforms.glassdoor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.FileHandler('multi_platform_companies_scraper.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


class MultiPlatformCompanyScraper:
    """Scrapes company details from multiple platforms and updates Firebase."""
    
    def __init__(self, platform_filter: Optional[str] = None, concurrent: int = 2):
        """
        Initialize multi-platform company scraper.
        
        Args:
            platform_filter: Optional platform to filter
            concurrent: Number of concurrent scraping tasks
        """
        self.firebase_manager = FirebaseManager()
        self.platform_factory = PlatformFactory()
        self.platform_filter = platform_filter.lower() if platform_filter else None
        self.concurrent = concurrent
    
    async def scrape_company_detail(
        self,
        job: dict,
        scraper,
        context,
        semaphore: asyncio.Semaphore,
        platform: str
    ) -> Optional[CompanyData]:
        """
        Scrape company details for a single job.
        
        Args:
            job: Job document from Firebase
            scraper: Platform scraper instance
            context: Playwright browser context
            semaphore: Concurrency control
            platform: Platform name (e.g., 'linkedin')
            
        Returns:
            CompanyData if successful, None otherwise
        """
        async with semaphore:
            # Get company URL and name from job details
            # Try both camelCase and snake_case field names for compatibility
            company_url = job.get('companyUrl') or job.get('company_url')
            company_name = job.get('companyName') or job.get('company_name', 'Unknown')
            platform = job.get('platform', 'linkedin').lower()
            
            if not company_url:
                logger.warning(f"No company URL for {company_name}, skipping")
                return None
            
            # Create a new page for this task
            page = await context.new_page()
            
            try:
                logger.info(f"Scraping {platform} company: {company_name}")
                
                # Navigate to the company page
                await page.goto(company_url, timeout=30000)
                await asyncio.sleep(2)
                
                # For LinkedIn, check if login is still valid
                if platform == 'linkedin':
                    from linkedin_auth import check_page_requires_login
                    
                    if await check_page_requires_login(page):
                        logger.error(f"⚠ LinkedIn session expired while scraping company: {company_url}")
                        logger.error("⚠ Cannot continue scraping without valid login!")
                        logger.error("⚠ Please restart the scraper to re-authenticate.")
                        return None
                
                # Scrape company details
                company_data = await scraper.scrape_company_details(page, company_url)
                
                if company_data:
                    logger.info(f"✓ Successfully scraped company: {company_data.company_name}")
                    return company_data
                else:
                    logger.warning(f"⚠ No data extracted for company: {company_url}")
                    return None
                    
            except Exception as e:
                logger.error(f"✗ Error scraping company {company_url}: {e}")
                return None
            finally:
                # Always close the page
                await page.close()
    
    async def run(self, limit: Optional[int] = None):
        """
        Run the multi-platform company scraper.
        
        Args:
            limit: Maximum number of companies to scrape
        """
        logger.info("="*60)
        logger.info("Multi-Platform Company Details Scraper Started")
        if self.platform_filter:
            logger.info(f"Platform filter: {self.platform_filter}")
        logger.info(f"Concurrent tasks: {self.concurrent}")
        logger.info("="*60)
        
        # Get jobs pending company details from Firebase
        jobs = self.firebase_manager.get_jobs_pending_company(
            platform=self.platform_filter,
            limit=limit
        )
        
        if not jobs:
            logger.info("No jobs pending company details found")
            return
        
        logger.info(f"Found {len(jobs)} jobs pending company details")
        
        # Group by platform
        by_platform = {}
        for job in jobs:
            platform = job.get('platform', 'linkedin').lower()
            if platform not in by_platform:
                by_platform[platform] = []
            by_platform[platform].append(job)
        
        logger.info(f"Jobs by platform: {', '.join([f'{p}: {len(j)}' for p, j in by_platform.items()])}")
        
        total_scraped = 0
        total_failed = 0
        total_skipped = 0
        
        # Process each platform
        for platform, platform_jobs in by_platform.items():
            logger.info(f"\n{'='*60}")
            logger.info(f"Processing {len(platform_jobs)} companies from {platform}")
            logger.info(f"{'='*60}")
            
            # Get platform scraper
            scraper = self.platform_factory.create_scraper(platform)
            if not scraper:
                logger.error(f"Platform '{platform}' not available, skipping")
                total_failed += len(platform_jobs)
                continue
            
            # Check if platform supports company scraping
            if not scraper.supports_company_scraping():
                logger.warning(f"Platform '{platform}' does not support company scraping, skipping")
                total_skipped += len(platform_jobs)
                # Mark jobs as complete anyway
                for job in platform_jobs:
                    self.firebase_manager.update_job_status(job.get('id'), 'complete')
                continue
            
            async with async_playwright() as p:
                # Launch browser
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context()
                
                # For LinkedIn, load session first
                if platform == 'linkedin':
                    from linkedin_auth import load_session, wait_for_manual_login, is_logged_in
                    
                    # Try to load existing session
                    session_loaded = await load_session(context)
                    
                    if session_loaded:
                        # Verify session is still valid and has job search access
                        logger.info("Verifying LinkedIn session...")
                        if not await is_logged_in(context):
                            logger.warning("LinkedIn session expired or invalid. Please log in again.")
                            await browser.close()
                            
                            # Get new session
                            session_data = await wait_for_manual_login(headless=False)
                            if not session_data:
                                logger.error("LinkedIn login failed")
                                total_failed += len(platform_jobs)
                                continue
                            
                            # Relaunch with new session
                            browser = await p.chromium.launch(headless=True)
                            context = await browser.new_context()
                            await context.add_cookies(session_data['cookies'])
                            
                            # Verify the new session works
                            if not await is_logged_in(context):
                                logger.error("LinkedIn login verification failed after login")
                                total_failed += len(platform_jobs)
                                continue
                    else:
                        # No session file, need to log in
                        logger.info("No LinkedIn session found. Please log in.")
                        await browser.close()
                        
                        session_data = await wait_for_manual_login(headless=False)
                        if not session_data:
                            logger.error("LinkedIn login failed")
                            total_failed += len(platform_jobs)
                            continue
                        
                        # Relaunch with new session
                        browser = await p.chromium.launch(headless=True)
                        context = await browser.new_context()
                        await context.add_cookies(session_data['cookies'])
                        
                        # Verify the new session works
                        if not await is_logged_in(context):
                            logger.error("LinkedIn login verification failed after login")
                            total_failed += len(platform_jobs)
                            continue
                    
                    logger.info("✓ LinkedIn authenticated job search access verified")
                
                # Scrape companies with concurrency control
                # Each task will create its own page from the context
                semaphore = asyncio.Semaphore(self.concurrent)
                tasks = [
                    self.scrape_company_detail(job, scraper, context, semaphore, platform)
                    for job in platform_jobs
                ]
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Save results to Firebase
                for idx, (job, result) in enumerate(zip(platform_jobs, results)):
                    job_id = job.get('id')
                    company_url = job.get('companyUrl') or job.get('company_url')
                    
                    if isinstance(result, CompanyData):
                        # Embed company data into job details
                        update_data = {
                            'companyData': result.to_dict(),
                            'status': 'complete',
                            'updated_at': firestore.SERVER_TIMESTAMP
                        }
                        
                        try:
                            self.firebase_manager.job_details_ref.document(job_id).update(update_data)
                            total_scraped += 1
                            logger.info(f"[{idx+1}/{len(platform_jobs)}] ✓ Saved company data: {result.company_name}")
                        except Exception as e:
                            total_failed += 1
                            logger.error(f"[{idx+1}/{len(platform_jobs)}] ✗ Failed to update job with company data: {e}")
                    else:
                        # Mark job as complete anyway (company scraping is optional)
                        self.firebase_manager.update_job_status(job_id, 'complete')
                        total_failed += 1
                        logger.warning(f"[{idx+1}/{len(platform_jobs)}] ⚠ Failed to scrape company, marked job as complete")
                
                await browser.close()
        
        # Summary
        logger.info("\n" + "="*60)
        logger.info("Company Details Scraping Complete!")
        logger.info(f"Total Processed: {len(jobs)}")
        logger.info(f"Successfully Scraped: {total_scraped}")
        logger.info(f"Failed: {total_failed}")
        logger.info(f"Skipped (platform doesn't support): {total_skipped}")
        logger.info("="*60)


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Scrape company details from multiple platforms')
    parser.add_argument('--platform', type=str, help='Filter by platform (linkedin, indeed, glassdoor)')
    parser.add_argument('--limit', type=int, help='Max companies to scrape')
    parser.add_argument('--concurrent', type=int, default=2, help='Concurrent tasks (default: 2)')
    
    args = parser.parse_args()
    
    scraper = MultiPlatformCompanyScraper(
        platform_filter=args.platform,
        concurrent=args.concurrent
    )
    await scraper.run(limit=args.limit)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Scraper interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
