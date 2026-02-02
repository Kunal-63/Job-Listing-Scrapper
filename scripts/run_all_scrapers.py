#!/usr/bin/env python3
"""
Run All Scrapers - Complete Pipeline

Runs all three scraping scripts in sequence for a complete workflow.

Usage:
    python run_all_scrapers.py
    python run_all_scrapers.py --job-limit 50 --company-limit 30
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.FileHandler('complete_scraper.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


async def run_job_link_scraper(limit: int = 25):
    """Run job link scraper."""
    logger.info("="*60)
    logger.info("STEP 1: Scraping Job Links")
    logger.info("="*60)
    
    from scrape_job_links import JobLinkScraper
    import json
    
    # Load search URLs from config
    config_file = Path(__file__).parent / "job_links.json"
    if not config_file.exists():
        config_file = Path(__file__).parent / "search_urls_example.json"
    
    if config_file.exists():
        with open(config_file, 'r') as f:
            search_urls = json.load(f)
            if not isinstance(search_urls, list):
                search_urls = [search_urls]
    else:
        logger.error("No search URL configuration found!")
        return False
    
    scraper = JobLinkScraper()
    await scraper.run(search_urls, limit)
    return True


async def run_job_detail_scraper(limit: int = None, concurrent: int = 5):
    """Run job detail scraper."""
    logger.info("\n" + "="*60)
    logger.info("STEP 2: Scraping Job Details")
    logger.info("="*60)
    
    from scrape_job_details import JobDetailScraper
    
    scraper = JobDetailScraper()
    await scraper.run(limit, concurrent)
    return True


async def run_company_detail_scraper(limit: int = None, concurrent: int = 3):
    """Run company detail scraper."""
    logger.info("\n" + "="*60)
    logger.info("STEP 3: Scraping Company Details")
    logger.info("="*60)
    
    from scrape_company_details import CompanyDetailScraper
    
    scraper = CompanyDetailScraper()
    await scraper.run(limit, concurrent)
    return True


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Run complete scraping pipeline')
    parser.add_argument('--link-limit', type=int, default=25, help='Max job links per search (default: 25)')
    parser.add_argument('--job-limit', type=int, help='Max jobs to scrape (default: all pending)')
    parser.add_argument('--company-limit', type=int, help='Max companies to scrape (default: all pending)')
    parser.add_argument('--job-concurrent', type=int, default=5, help='Concurrent job scraping tasks (default: 5)')
    parser.add_argument('--company-concurrent', type=int, default=3, help='Concurrent company scraping tasks (default: 3)')
    
    args = parser.parse_args()
    
    logger.info("="*60)
    logger.info("COMPLETE SCRAPING PIPELINE STARTED")
    logger.info("="*60)
    
    try:
        # Step 1: Scrape job links
        if not await run_job_link_scraper(args.link_limit):
            logger.error("Job link scraping failed, stopping pipeline")
            return
        
        # Small delay
        await asyncio.sleep(3)
        
        # Step 2: Scrape job details
        if not await run_job_detail_scraper(args.job_limit, args.job_concurrent):
            logger.error("Job detail scraping failed, stopping pipeline")
            return
        
        # Small delay
        await asyncio.sleep(3)
        
        # Step 3: Scrape company details
        if not await run_company_detail_scraper(args.company_limit, args.company_concurrent):
            logger.error("Company detail scraping failed")
            return
        
        logger.info("\n" + "="*60)
        logger.info("COMPLETE PIPELINE FINISHED SUCCESSFULLY!")
        logger.info("="*60)
        
        # Show final statistics
        from firebase_manager import FirebaseManager
        manager = FirebaseManager()
        stats = manager.get_statistics()
        
        logger.info("\nFinal Statistics:")
        logger.info(f"  Total Job Links: {stats.get('total_job_links', 0)}")
        logger.info(f"  Total Job Details: {stats.get('total_job_details', 0)}")
        logger.info(f"  Complete Jobs: {stats.get('complete_jobs', 0)}")
        logger.info(f"  Total Companies: {stats.get('total_companies', 0)}")
        
    except Exception as e:
        logger.error(f"Pipeline error: {e}", exc_info=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Pipeline interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
