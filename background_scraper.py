#!/usr/bin/env python3
"""
Background scraper that runs independently.
Fetches job links from MongoDB and scrapes all required data.
"""

import asyncio
import logging
import sys
from datetime import datetime
from typing import List, Dict, Any
from playwright.async_api import async_playwright

from mongo_client import get_db, get_client
from linkedin_scraper.scrapers.job import JobScraper
from linkedin_scraper.scrapers.company import CompanyScraper
from linkedin_scraper.callbacks import SilentCallback

# Configure logging to file with UTF-8 encoding
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler('scraper_background.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


class BackgroundScraper:
    """Background scraper that processes job links from MongoDB."""
    
    def __init__(self):
        self.client = None
        self.db = None
        self.session_file = "linkedin_session.json"
    
    async def connect_db(self):
        """Connect to MongoDB."""
        try:
            self.client = get_client()
            self.db = get_db(self.client)
            logger.info("[OK] Connected to MongoDB")
            return True
        except Exception as e:
            logger.error(f"[ERROR] Failed to connect to MongoDB: {e}")
            return False
    
    def get_pending_job_links(self) -> List[Dict[str, Any]]:
        """Get all pending job links from MongoDB."""
        try:
            # Get ALL job links regardless of status (user request: scrap no matter what)
            job_links = list(self.db.job_links.find({}))
            
            logger.info(f"Found {len(job_links)} job links (processing all)")
            return job_links
        except Exception as e:
            logger.error(f"Error fetching job links: {e}")
            return []
    
    async def scrape_job_search_url(self, job_link: Dict[str, Any], browser_context) -> List[Dict[str, Any]]:
        """
        Scrape jobs from a search URL (handles job listing pages).
        Returns a list of scraped job results.
        
        Required fields for each result:
        - Engen Name (engineName)
        - Source Name (sourceName)
        - Post Content (job description)
        - Time (posted date)
        - Title (job title)
        - Company name
        - Company URL
        - Overview (company about)
        - Industry
        - Company Size
        - Headquarters
        - Founded
        - Website
        """
        url = job_link.get("url")
        engine_name = job_link.get("engineName", "Unknown")
        source_name = job_link.get("sourceName", "Job Posting")
        
        results = []
        
        try:
            logger.info(f"Scraping job search URL: {url}")
            
            # Create new page for this search
            page = await browser_context.new_page()
            
            try:
                # Use JobSearchScraper to handle search URLs
                from linkedin_scraper.scrapers.job_search import JobSearchScraper
                
                search_scraper = JobSearchScraper(page, SilentCallback())
                
                # Search and scrape jobs (this handles extracting individual jobs from search page)
                logger.info(f"Extracting jobs from search page...")
                jobs = await search_scraper.search(
                    search_url=url,
                    limit=25,  # Get up to 25 jobs per search URL
                    max_concurrent=3  # Parallel scraping
                )
                
                if not jobs:
                    logger.warning(f"No jobs found for search URL: {url}")
                    return results
                
                logger.info(f"Found {len(jobs)} jobs from search URL")
                
                # Convert each Job object to our required format
                for job in jobs:
                    result = {
                        "enegName": engine_name,
                        "sourceName": source_name,
                        "jobDescription": job.job_description or "",
                        "postedAt": job.posted_date or "",
                        "jobTitle": job.job_title or "",
                        "companyName": job.company or "",
                        "companyUrl": job.company_linkedin_url or "",
                        "companyOverview": job.company_about or "",
                        "companyIndustry": job.industry or "",
                        "companySize": job.company_size or "",
                        "companyHeadquarters": job.headquarters or "",
                        "companyFounded": job.founded or "",
                        "companyWebsite": job.company_website or "",
                        "postedDate": job.posted_date or "",
                        "postContent": job.job_description or "",
                        "jobUrl": job.linkedin_url or "",
                        "scraped_at": datetime.utcnow()
                    }
                    
                    results.append(result)
                    logger.info(f"[OK] Processed: {job.job_title}")
                
                logger.info(f"[OK] Successfully scraped {len(results)} jobs from search URL")
                return results
                
            finally:
                await page.close()
                
        except Exception as e:
            logger.error(f"Error scraping search URL {url}: {e}")
            return results
    
    async def save_result(self, result: Dict[str, Any], job_link_url: str):
        """Save scraped result to MongoDB."""
        try:
            # Insert into job_scrapping_results collection
            self.db.job_scrapping_results.insert_one(result)
            
            # Update job_links status to 'scraped'
            self.db.job_links.update_one(
                {"url": job_link_url},
                {
                    "$set": {
                        "status": "scraped",
                        "scraped_at": datetime.utcnow()
                    }
                }
            )
            
            logger.info(f"[OK] Saved result to MongoDB: {result.get('jobTitle', 'Unknown')}")
            return True
        except Exception as e:
            logger.error(f"Error saving result: {e}")
            # Mark as failed
            try:
                self.db.job_links.update_one(
                    {"url": job_link_url},
                    {
                        "$set": {
                            "status": "failed",
                            "error": str(e),
                            "failed_at": datetime.utcnow()
                        }
                    }
                )
            except:
                pass
            return False
    
    async def run(self):
        """Main scraping loop."""
        logger.info("="*60)
        logger.info("Background Scraper Started")
        logger.info("="*60)
        
        # Connect to MongoDB
        if not await self.connect_db():
            logger.error("Cannot proceed without MongoDB connection")
            return
        
        # Get pending job links
        job_links = self.get_pending_job_links()
        
        if not job_links:
            logger.info("No pending job links found. Exiting.")
            return
        
        logger.info(f"Starting to scrape {len(job_links)} jobs...")
        
        # Start browser
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            
            # Load session cookies
            try:
                import json
                with open(self.session_file, "r") as f:
                    session_data = json.load(f)
                    if "cookies" in session_data:
                        await context.add_cookies(session_data["cookies"])
                        logger.info("[OK] Loaded LinkedIn session")
            except Exception as e:
                logger.warning(f"Could not load session: {e}")
            
            # Process each job link (search URL)
            successful = 0
            failed = 0
            total_jobs_scraped = 0
            
            for idx, job_link in enumerate(job_links, 1):
                logger.info(f"\n[{idx}/{len(job_links)}] Processing search URL...")
                
                try:
                    # Scrape all jobs from this search URL
                    results = await self.scrape_job_search_url(job_link, context)
                    
                    if results:
                        # Save each job result
                        for result in results:
                            if await self.save_result(result, job_link.get("url")):
                                successful += 1
                                total_jobs_scraped += 1
                            else:
                                failed += 1
                        
                        logger.info(f"[OK] Saved {len(results)} jobs from this search URL")
                    else:
                        failed += 1
                        # Mark search URL as failed
                        try:
                            self.db.job_links.update_one(
                                {"url": job_link.get("url")},
                                {
                                    "$set": {
                                        "status": "failed",
                                        "failed_at": datetime.utcnow()
                                    }
                                }
                            )
                        except:
                            pass
                    
                    # Small delay between search URLs
                    await asyncio.sleep(3)
                    
                except Exception as e:
                    logger.error(f"Error processing search URL {idx}: {e}")
                    failed += 1
            
            await browser.close()
        
        # Summary
        logger.info("\n" + "="*60)
        logger.info("Scraping Complete!")
        logger.info(f"Search URLs Processed: {len(job_links)}")
        logger.info(f"Total Jobs Scraped: {total_jobs_scraped}")
        logger.info(f"Successful: {successful}")
        logger.info(f"Failed: {failed}")
        logger.info("="*60)
        
        # Close MongoDB connection
        if self.client:
            self.client.close()


async def main():
    """Main entry point."""
    scraper = BackgroundScraper()
    await scraper.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Scraper interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
