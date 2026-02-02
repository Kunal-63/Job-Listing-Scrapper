#!/usr/bin/env python3
"""
Multi-Platform Job Scraper Orchestrator

Runs the complete multi-platform job scraping pipeline:
1. Scrape job links from search pages
2. Scrape job details from individual job postings
3. Scrape company details from company pages

Usage:
    # Single run (runs once and exits)
    python run_multi_platform_scrapers.py
    python run_multi_platform_scrapers.py --platform linkedin
    
    # Continuous mode (runs forever)
    python run_multi_platform_scrapers.py --continuous
    python run_multi_platform_scrapers.py --continuous --delay 600
    
    # Run specific stages only
    python run_multi_platform_scrapers.py --links-only
    python run_multi_platform_scrapers.py --details-only
    python run_multi_platform_scrapers.py --companies-only
    
    # Continuous mode for specific stage
    python run_multi_platform_scrapers.py --details-only --continuous
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.firebase_manager import FirebaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.FileHandler('multi_platform_orchestrator.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


async def run_links_scraper(platform: str = None, limit: int = 25):
    """Run job links scraper."""
    logger.info("\n" + "="*60)
    logger.info("STEP 1: Scraping Job Links")
    logger.info("="*60)
    
    from scrape_multi_platform_links import MultiPlatformLinkScraper
    import json
    
    # Load search configs
    config_file = Path('config/search_configs.json')
    if not config_file.exists():
        config_file = Path('job_links.json')
    
    if not config_file.exists():
        logger.error("No search configuration file found")
        return False
    
    with open(config_file, 'r') as f:
        search_configs = json.load(f)
    
    scraper = MultiPlatformLinkScraper(platform_filter=platform)
    await scraper.run(search_configs, limit)
    
    return True


async def run_details_scraper(platform: str = None, limit: int = None, concurrent: int = 3):
    """Run job details scraper."""
    logger.info("\n" + "="*60)
    logger.info("STEP 2: Scraping Job Details")
    logger.info("="*60)
    
    from scrape_multi_platform_details import MultiPlatformDetailScraper
    
    scraper = MultiPlatformDetailScraper(platform_filter=platform, concurrent=concurrent)
    await scraper.run(limit=limit)
    
    return True


async def run_companies_scraper(platform: str = None, limit: int = None, concurrent: int = 2):
    """Run company details scraper."""
    logger.info("\n" + "="*60)
    logger.info("STEP 3: Scraping Company Details")
    logger.info("="*60)
    
    from scrape_multi_platform_companies import MultiPlatformCompanyScraper
    
    scraper = MultiPlatformCompanyScraper(platform_filter=platform, concurrent=concurrent)
    await scraper.run(limit=limit)
    
    return True


def print_statistics(platform: str = None):
    """Print database statistics."""
    logger.info("\n" + "="*60)
    logger.info("Database Statistics")
    if platform:
        logger.info(f"Platform: {platform}")
    logger.info("="*60)
    
    firebase = FirebaseManager()
    stats = firebase.get_statistics(platform=platform)
    
    logger.info(f"Job Links:")
    logger.info(f"  Total: {stats.get('total_job_links', 0)}")
    logger.info(f"  Pending: {stats.get('pending_job_links', 0)}")
    logger.info(f"  Scraped: {stats.get('scraped_job_links', 0)}")
    logger.info(f"\nJob Details:")
    logger.info(f"  Total: {stats.get('total_job_details', 0)}")
    logger.info(f"  Pending Company: {stats.get('pending_company_jobs', 0)}")
    logger.info(f"  Complete: {stats.get('complete_jobs', 0)}")
    logger.info(f"\nCompanies:")
    logger.info(f"  Total: {stats.get('total_companies', 0)}")
    logger.info("="*60)


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Run multi-platform job scraping pipeline')
    parser.add_argument('--platform', type=str, help='Filter by platform (linkedin, indeed, glassdoor)')
    parser.add_argument('--links-only', action='store_true', help='Only scrape job links')
    parser.add_argument('--details-only', action='store_true', help='Only scrape job details')
    parser.add_argument('--companies-only', action='store_true', help='Only scrape company details')
    parser.add_argument('--links-limit', type=int, default=25, help='Max job links per search (default: 25)')
    parser.add_argument('--details-limit', type=int, help='Max job details to scrape')
    parser.add_argument('--companies-limit', type=int, help='Max companies to scrape')
    parser.add_argument('--concurrent', type=int, default=3, help='Concurrent tasks (default: 3)')
    parser.add_argument('--stats', action='store_true', help='Show statistics only')
    parser.add_argument('--continuous', action='store_true', help='Run continuously in a loop')
    parser.add_argument('--delay', type=int, default=300, help='Delay between cycles in seconds (default: 300)')
    
    args = parser.parse_args()
    
    # Show statistics if requested
    if args.stats:
        print_statistics(platform=args.platform)
        return
    
    logger.info("="*60)
    logger.info("Multi-Platform Job Scraper Orchestrator")
    if args.continuous:
        logger.info("MODE: Continuous (runs forever)")
        logger.info(f"Delay between cycles: {args.delay} seconds")
    else:
        logger.info("MODE: Single run")
    logger.info("="*60)
    
    # Print initial statistics
    print_statistics(platform=args.platform)
    
    cycle_count = 0
    
    while True:
        cycle_count += 1
        
        if args.continuous:
            logger.info(f"\n{'='*60}")
            logger.info(f"CYCLE {cycle_count} STARTED")
            logger.info(f"{'='*60}")
        
        try:
            # Run selected scrapers
            if args.links_only:
                await run_links_scraper(args.platform, args.links_limit)
            elif args.details_only:
                await run_details_scraper(args.platform, args.details_limit, args.concurrent)
            elif args.companies_only:
                await run_companies_scraper(args.platform, args.companies_limit, args.concurrent // 2)
            else:
                # Run full pipeline
                logger.info("\nRunning full scraping pipeline...")
                
                # Step 1: Scrape job links
                success = await run_links_scraper(args.platform, args.links_limit)
                if not success:
                    logger.error("Job links scraping failed, stopping pipeline")
                    if not args.continuous:
                        return
                    logger.info(f"Waiting {args.delay} seconds before retry...")
                    await asyncio.sleep(args.delay)
                    continue
                
                # Step 2: Scrape job details
                await run_details_scraper(args.platform, args.details_limit, args.concurrent)
                
                # Step 3: Scrape company details
                await run_companies_scraper(args.platform, args.companies_limit, args.concurrent // 2)
            
            # Print final statistics
            logger.info("\n" + "="*60)
            if args.continuous:
                logger.info(f"CYCLE {cycle_count} COMPLETE!")
            else:
                logger.info("Pipeline Complete!")
            logger.info("="*60)
            print_statistics(platform=args.platform)
            
            # If not continuous mode, exit after one run
            if not args.continuous:
                break
            
            # Wait before next cycle
            logger.info(f"\n{'='*60}")
            logger.info(f"Waiting {args.delay} seconds before next cycle...")
            logger.info(f"Press Ctrl+C to stop")
            logger.info(f"{'='*60}\n")
            await asyncio.sleep(args.delay)
            
        except Exception as e:
            logger.error(f"Pipeline error: {e}", exc_info=True)
            if not args.continuous:
                break
            logger.info(f"Error occurred, waiting {args.delay} seconds before retry...")
            await asyncio.sleep(args.delay)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\nPipeline interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
