#!/usr/bin/env python3
"""
Multi-Platform Job Details Scraper

Fetches pending job links from Firebase and scrapes detailed job information
for each job posting. Works with all registered platforms (LinkedIn, Indeed, Glassdoor).

Usage:
    python scrape_multi_platform_details.py
    python scrape_multi_platform_details.py --platform linkedin --limit 50
    python scrape_multi_platform_details.py --concurrent 5
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
from scrapers.core.data_models import JobData
from scrapers.utils.url_detector import detect_platform

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
        logging.FileHandler('multi_platform_details_scraper.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


class MultiPlatformDetailScraper:
    """Scrapes job details from multiple platforms and updates Firebase."""
    
    def __init__(self, platform_filter: Optional[str] = None, concurrent: int = 3):
        """
        Initialize multi-platform detail scraper.
        
        Args:
            platform_filter: Optional platform to filter
            concurrent: Number of concurrent scraping tasks
        """
        self.firebase_manager = FirebaseManager()
        self.platform_factory = PlatformFactory()
        self.platform_filter = platform_filter.lower() if platform_filter else None
        self.concurrent = concurrent
    
    async def scrape_job_detail(
        self,
        job_link: dict,
        scraper,
        context,
        semaphore: asyncio.Semaphore
    ) -> bool:
        """
        Scrape details for a single job and save to Firebase immediately.
        
        Args:
            job_link: Job link document from Firebase
            scraper: Platform scraper instance
            context: Playwright browser context
            semaphore: Concurrency control
            
        Returns:
            True if successful, False otherwise
        """
        async with semaphore:
            job_url = job_link.get('url')
            job_link_id = job_link.get('id')
            platform = job_link.get('platform', 'linkedin').lower()
            
            # Check if job details already exist (skip if already scraped)
            if self.firebase_manager.job_details_exist(job_url):
                logger.info(f"⊘ Skipping (job details exist): {job_url}")
                # Update job link status to scraped if not already
                self.firebase_manager.update_job_link_status(
                    job_link_id,
                    'scraped'
                )
                return True
            
            try:
                logger.info(f"Scraping {platform} job: {job_url}")
                
                # Create a new page for this task
                page = await context.new_page()
                
                try:
                    # Scrape job details only (no company data)
                    job_data = await scraper.scrape_job_details(page, job_url)
                    
                    if job_data:
                        # Add metadata from job_link
                        job_data.engine_name = job_link.get('engineName', '')
                        job_data.source_name = job_link.get('sourceName', '')
                        
                        # Convert to dict for saving
                        job_dict = job_data.to_dict()
                        
                        # Set status based on whether company URL exists
                        if job_data.company_url:
                            job_dict['status'] = 'pending_company'
                            logger.info(f"  → Company URL found, will scrape company details later")
                        else:
                            job_dict['status'] = 'complete'
                            logger.info(f"  → No company URL, marking as complete")
                        
                        # Save to Firebase immediately
                        job_doc_id = self.firebase_manager.save_job_details(job_dict)
                        
                        if job_doc_id:
                            # Update job link status
                            self.firebase_manager.update_job_link_status(
                                job_link_id,
                                'scraped'
                            )
                            logger.info(f"✓ Saved: {job_data.job_title}")
                            return True
                        else:
                            logger.error(f"✗ Failed to save to Firebase: {job_data.job_title}")
                            return False
                    else:
                        # Mark as failed
                        self.firebase_manager.update_job_link_status(
                            job_link_id,
                            'failed',
                            error="No data extracted"
                        )
                        logger.warning(f"✗ No data extracted for: {job_url}")
                        return False
                finally:
                    # Always close the page
                    await page.close()
                    
            except Exception as e:
                # Mark as failed
                self.firebase_manager.update_job_link_status(
                    job_link_id,
                    'failed',
                    error=str(e)
                )
                logger.error(f"✗ Error scraping job {job_url}: {e}")
                return False
    
    async def run(self, limit: Optional[int] = None):
        """
        Run the multi-platform detail scraper.
        
        Args:
            limit: Maximum number of jobs to scrape
        """
        logger.info("="*60)
        logger.info("Multi-Platform Job Details Scraper Started")
        if self.platform_filter:
            logger.info(f"Platform filter: {self.platform_filter}")
        logger.info(f"Concurrent tasks: {self.concurrent}")
        logger.info("="*60)
        
        # Get pending job links from Firebase
        job_links = self.firebase_manager.get_pending_job_links(
            platform=self.platform_filter,
            limit=limit
        )
        
        if not job_links:
            logger.info("No pending job links found")
            return
        
        logger.info(f"Found {len(job_links)} pending job links")
        
        # Group by platform
        by_platform = {}
        for job_link in job_links:
            platform = job_link.get('platform', 'linkedin').lower()
            if platform not in by_platform:
                by_platform[platform] = []
            by_platform[platform].append(job_link)
        
        logger.info(f"Jobs by platform: {', '.join([f'{p}: {len(jobs)}' for p, jobs in by_platform.items()])}")
        
        total_scraped = 0
        total_failed = 0
        
        # Process each platform
        for platform, platform_jobs in by_platform.items():
            logger.info(f"\n{'='*60}")
            logger.info(f"Processing {len(platform_jobs)} jobs from {platform}")
            logger.info(f"{'='*60}")
            
            # Get platform scraper
            scraper = self.platform_factory.create_scraper(platform)
            if not scraper:
                logger.error(f"Platform '{platform}' not available, skipping")
                total_failed += len(platform_jobs)
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
                        # Verify session is still valid
                        if not await is_logged_in(context):
                            logger.warning("LinkedIn session expired. Please log in again.")
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
                
                
                # Scrape jobs with concurrency control
                # Each task will create its own page from the context
                semaphore = asyncio.Semaphore(self.concurrent)
                tasks = [
                    self.scrape_job_detail(job_link, scraper, context, semaphore)
                    for job_link in platform_jobs
                ]
                
                # Wait for all tasks to complete
                # Results are already saved to Firebase by each task
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Count successes and failures
                for result in results:
                    if isinstance(result, bool):
                        if result:
                            total_scraped += 1
                        else:
                            total_failed += 1
                    elif isinstance(result, Exception):
                        total_failed += 1
                        logger.error(f"Task exception: {result}")
                    else:
                        total_failed += 1
                
                await browser.close()
        
        # Summary
        logger.info("\n" + "="*60)
        logger.info("Job Details Scraping Complete!")
        logger.info(f"Total Processed: {len(job_links)}")
        logger.info(f"Successfully Scraped: {total_scraped}")
        logger.info(f"Failed: {total_failed}")
        logger.info("="*60)


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Scrape job details from multiple platforms')
    parser.add_argument('--platform', type=str, help='Filter by platform (linkedin, indeed, glassdoor)')
    parser.add_argument('--limit', type=int, help='Max jobs to scrape')
    parser.add_argument('--concurrent', type=int, default=3, help='Concurrent tasks (default: 3)')
    
    args = parser.parse_args()
    
    scraper = MultiPlatformDetailScraper(
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
