#!/usr/bin/env python3
"""
Multi-Platform Job Link Scraper

Extracts job URLs from multiple job platforms (LinkedIn, Indeed, Glassdoor, etc.)
and stores them in Firebase. Fetches search URLs from Firebase search_urls collection.

Usage:
    python scrape_multi_platform_links.py
    python scrape_multi_platform_links.py --platform linkedin --limit 50
"""

import asyncio
import argparse
import logging
import sys
import json
from pathlib import Path
from typing import List, Dict, Optional
from playwright.async_api import async_playwright

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.firebase_manager import FirebaseManager
from scrapers.core.platform_registry import PlatformFactory
from scrapers.core.data_models import SearchConfig
from scrapers.utils.url_detector import detect_platform

# Import platforms to register them
import scrapers.platforms.linkedin
# import scrapers.platforms.indeed  # Disabled - using LinkedIn only
# import scrapers.platforms.glassdoor  # Disabled - using LinkedIn only

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.FileHandler('multi_platform_links_scraper.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


class MultiPlatformLinkScraper:
    """Scrapes job URLs from multiple platforms and stores in Firebase."""
    
    def __init__(self, platform_filter: Optional[str] = None):
        """
        Initialize multi-platform link scraper.
        
        Args:
            platform_filter: Optional platform to filter (e.g., 'linkedin', 'indeed')
        """
        self.firebase_manager = FirebaseManager()
        self.platform_factory = PlatformFactory()
        self.platform_filter = platform_filter.lower() if platform_filter else None
        self.browser = None
        self.context = None
        self.playwright = None
    
    async def initialize_browser(self):
        """Initialize browser and context once for all searches."""
        if self.browser is not None:
            return  # Already initialized
        
        from playwright.async_api import async_playwright
        
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)
        self.context = await self.browser.new_context()
        
        # For LinkedIn, handle login once
        if self.platform_filter == 'linkedin':
            from linkedin_auth import load_session, wait_for_manual_login, is_logged_in
            
            # Try to load existing session
            session_loaded = await load_session(self.context)
            
            if session_loaded:
                # Verify session is still valid and has job search access
                logger.info("Verifying LinkedIn session...")
                if not await is_logged_in(self.context):
                    logger.warning("LinkedIn session expired or invalid. Please log in again.")
                    await self.cleanup()
                    
                    # Get new session
                    session_data = await wait_for_manual_login(headless=False)
                    if not session_data:
                        raise Exception("LinkedIn login failed")
                    
                    # Reinitialize with new session
                    self.playwright = await async_playwright().start()
                    self.browser = await self.playwright.chromium.launch(headless=True)
                    self.context = await self.browser.new_context()
                    await self.context.add_cookies(session_data['cookies'])
                    
                    # Verify the new session works
                    if not await is_logged_in(self.context):
                        raise Exception("LinkedIn login verification failed after login")
            else:
                # No session file, need to log in
                logger.info("No LinkedIn session found. Please log in.")
                await self.cleanup()
                
                session_data = await wait_for_manual_login(headless=False)
                if not session_data:
                    raise Exception("LinkedIn login failed")
                
                # Initialize with new session
                self.playwright = await async_playwright().start()
                self.browser = await self.playwright.chromium.launch(headless=True)
                self.context = await self.browser.new_context()
                await self.context.add_cookies(session_data['cookies'])
                
                # Verify the new session works
                if not await is_logged_in(self.context):
                    raise Exception("LinkedIn login verification failed after login")
            
            logger.info("✓ LinkedIn browser session initialized and authenticated job search access verified")
    
    async def refresh_session(self):
        """Refresh and save the current session to prevent expiration."""
        if self.context and self.platform_filter == 'linkedin':
            try:
                import json
                from linkedin_auth import SESSION_FILE
                
                # Get current cookies
                cookies = await self.context.cookies()
                session_data = {"cookies": cookies}
                
                # Save to file
                with open(SESSION_FILE, 'w') as f:
                    json.dump(session_data, f, indent=2)
                
                logger.debug("✓ LinkedIn session refreshed and saved")
            except Exception as e:
                logger.warning(f"Failed to refresh session: {e}")
    
    async def cleanup(self):
        """Clean up browser resources."""
        # Save session one last time before cleanup
        await self.refresh_session()
        
        if self.browser:
            await self.browser.close()
            self.browser = None
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None
        self.context = None
    
    async def scrape_search_url(
        self,
        search_config: SearchConfig,
        limit: int = 25
    ) -> List[str]:
        """
        Scrape job URLs from a search page.
        
        Args:
            search_config: Search configuration
            limit: Maximum number of job URLs to extract
            
        Returns:
            List of job URLs
        """
        platform = search_config.platform.lower()
        job_urls = []
        
        try:
            logger.info(f"Starting {platform} search: {search_config.url}")
            
            # Get platform scraper
            scraper = self.platform_factory.create_scraper(platform)
            if not scraper:
                logger.error(f"Platform '{platform}' not available")
                return []
            
            # Ensure browser is initialized
            await self.initialize_browser()
            
            # Create a new page for this search (reusing the same context)
            page = await self.context.new_page()
            
            try:
                # For LinkedIn, check if login is still valid before scraping
                if platform == 'linkedin':
                    from linkedin_auth import check_page_requires_login, wait_for_manual_login
                    
                    # Navigate to the search URL first
                    await page.goto(search_config.url, timeout=30000)
                    await asyncio.sleep(2)
                    
                    # Check if we need to re-login
                    if await check_page_requires_login(page):
                        logger.error("⚠ LinkedIn session expired during scraping!")
                        logger.info("Requesting fresh login...")
                        
                        # Close current page and browser
                        await page.close()
                        await self.cleanup()
                        
                        # Get new session
                        session_data = await wait_for_manual_login(headless=False)
                        if not session_data:
                            raise Exception("LinkedIn login failed - cannot continue scraping")
                        
                        # Reinitialize browser with new session
                        await self.initialize_browser()
                        
                        # Create a new page with the fresh session
                        page = await self.context.new_page()
                        logger.info("✓ Re-authenticated successfully, continuing scraping...")
                
                # Search for jobs
                job_urls = await scraper.search_jobs(page, search_config, limit)
            finally:
                # Close the page (but keep the context/browser alive)
                await page.close()
            
            logger.info(f"Extracted {len(job_urls)} job URLs from {platform}")
            return job_urls
            
        except Exception as e:
            logger.error(f"Error scraping {platform} search URL: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    
    async def run(
        self,
        search_configs: List[Dict],
        limit_per_search: int = 25
    ):
        """
        Run the multi-platform link scraper.
        
        Args:
            search_configs: List of search configurations
            limit_per_search: Maximum job URLs to extract per search
        """
        logger.info("="*60)
        logger.info("Multi-Platform Job Link Scraper Started")
        logger.info(f"Number of search configs: {len(search_configs)}")
        logger.info(f"Limit per search: {limit_per_search}")
        if self.platform_filter:
            logger.info(f"Platform filter: {self.platform_filter}")
        logger.info("="*60)
        
        # Show available platforms
        available_platforms = self.platform_factory.get_available_platforms()
        logger.info(f"Available platforms: {', '.join(available_platforms)}")
        
        total_urls_found = 0
        total_urls_saved = 0
        
        try:
            # Initialize browser once for all searches
            await self.initialize_browser()
            
            for idx, search_dict in enumerate(search_configs, 1):
                # Convert to SearchConfig
                search_config = SearchConfig.from_dict(search_dict)
                
                # Check if enabled
                if not search_config.enabled:
                    logger.info(f"[{idx}/{len(search_configs)}] Skipping disabled search: {search_config.platform}")
                    continue
                
                # Apply platform filter
                if self.platform_filter and search_config.platform.lower() != self.platform_filter:
                    logger.info(f"[{idx}/{len(search_configs)}] Skipping {search_config.platform} (filter: {self.platform_filter})")
                    continue
                
                logger.info(f"\n[{idx}/{len(search_configs)}] Processing: {search_config.platform} - {search_config.source_name}")
                
                # Scrape job URLs
                job_urls = await self.scrape_search_url(search_config, limit_per_search)
                
                total_urls_found += len(job_urls)
                
                # Save to Firebase
                if job_urls:
                    logger.info(f"Saving {len(job_urls)} job URLs to Firebase...")
                    
                    links_data = [
                        {
                            'engineName': search_config.engine_name,
                            'sourceName': search_config.source_name,
                            'platform': search_config.platform,
                            'url': url
                        }
                        for url in job_urls
                    ]
                    
                    saved_count = self.firebase_manager.add_job_links_bulk(links_data)
                    total_urls_saved += saved_count
                    logger.info(f"Saved {saved_count} new job URLs")
                
                # Refresh session periodically (every 5 searches)
                if idx % 5 == 0:
                    await self.refresh_session()
                
                # Small delay between searches
                if idx < len(search_configs):
                    await asyncio.sleep(2)
        
        finally:
            # Clean up browser resources
            await self.cleanup()
        
        # Summary
        logger.info("\n" + "="*60)
        logger.info("Multi-Platform Link Scraping Complete!")
        logger.info(f"Search Configs Processed: {len([c for c in search_configs if c.get('enabled', True)])}")
        logger.info(f"Total URLs Found: {total_urls_found}")
        logger.info(f"New URLs Saved: {total_urls_saved}")
        logger.info("="*60)


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Scrape job links from multiple platforms')
    parser.add_argument('--platform', type=str, help='Filter by platform (linkedin, indeed, glassdoor)')
    parser.add_argument('--limit', type=int, default=25, help='Max job URLs per search (default: 25)')
    
    args = parser.parse_args()
    
    # Initialize Firebase manager
    firebase_manager = FirebaseManager()
    
    # Fetch from Firebase
    platform_filter = args.platform.lower() if args.platform else None
    logger.info(f"Fetching search URLs from Firebase...")
    if platform_filter:
        logger.info(f"Platform filter: {platform_filter}")
    
    firebase_search_urls = firebase_manager.get_search_urls(platform=platform_filter, active_only=True)
    
    if not firebase_search_urls:
        logger.error("No search URLs found in Firebase!")
        logger.error("Add search URLs using: python add_search_urls_to_firebase.py")
        return
    
    # Convert Firebase documents to search config format
    logger.info(f"Found {len(firebase_search_urls)} search URLs in Firebase")
    search_configs = [
        {
            'url': item.get('url'),
            'engineName': item.get('engineName', 'LinkedIn'),
            'sourceName': item.get('sourceName', 'Job Search'),
            'platform': item.get('platform', 'linkedin'),
            'enabled': item.get('active', True)
        }
        for item in firebase_search_urls
    ]
    
    # Auto-detect and normalize platform names
    for config in search_configs:
        platform_value = config.get('platform', '')
        
        # Normalize platform name
        if platform_value:
            # Convert to lowercase and extract base platform name
            platform_lower = platform_value.lower()
            
            if 'linkedin' in platform_lower:
                config['platform'] = 'linkedin'
            elif 'indeed' in platform_lower:
                config['platform'] = 'indeed'
            elif 'glassdoor' in platform_lower:
                config['platform'] = 'glassdoor'
            else:
                # Try URL detection
                detected = detect_platform(config['url'])
                if detected:
                    config['platform'] = detected
                    logger.info(f"Auto-detected platform '{detected}' for URL: {config['url']}")
                else:
                    config['platform'] = 'linkedin'  # Default fallback
                    logger.warning(f"Could not detect platform, defaulting to 'linkedin'")
        else:
            # No platform specified, try to detect from URL
            detected = detect_platform(config['url'])
            if detected:
                config['platform'] = detected
                logger.info(f"Auto-detected platform '{detected}' for URL: {config['url']}")
            else:
                config['platform'] = 'linkedin'  # Default fallback
                logger.warning(f"Could not detect platform for URL: {config['url']}, defaulting to 'linkedin'")
    
    logger.info(f"Processing {len(search_configs)} search configurations")
    
    # Run scraper
    scraper = MultiPlatformLinkScraper(platform_filter=args.platform)
    await scraper.run(search_configs, args.limit)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Scraper interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
