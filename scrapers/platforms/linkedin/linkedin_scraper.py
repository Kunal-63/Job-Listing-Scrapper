#!/usr/bin/env python3
"""
LinkedIn Platform Scraper

Implements the BasePlatformScraper interface for LinkedIn job scraping.
Wraps the existing LinkedIn scraper modules into the new multi-platform architecture.
"""

import logging
from typing import List, Optional, Dict, Any
from pathlib import Path
from playwright.async_api import Page, BrowserContext

from ...core.base_scraper import BasePlatformScraper
from ...core.data_models import JobData, CompanyData, SearchConfig
from ...core.auth_manager import AuthManager
from ...core.platform_registry import register_platform

# Import local LinkedIn scrapers
from .scrapers.job_search import JobSearchScraper
from .scrapers.job import JobScraper
from .scrapers.company import CompanyScraper
from .callbacks import SilentCallback

logger = logging.getLogger(__name__)


@register_platform('linkedin')
class LinkedInScraper(BasePlatformScraper):
    """
    LinkedIn platform scraper implementation.
    
    Wraps existing LinkedIn scraper modules to work with the new
    multi-platform architecture.
    """
    
    def __init__(self, platform_name: str = 'linkedin', config: Optional[Dict[str, Any]] = None):
        """
        Initialize LinkedIn scraper.
        
        Args:
            platform_name: Platform name (should be 'linkedin')
            config: Platform-specific configuration
        """
        super().__init__(platform_name, config)
        self.auth_manager = AuthManager(platform_name, config)
        self.callback = SilentCallback()
    
    async def initialize_session(self, context: BrowserContext) -> bool:
        """
        Initialize LinkedIn session by loading cookies.
        
        Args:
            context: Playwright browser context
            
        Returns:
            True if session loaded successfully
        """
        try:
            success = await self.auth_manager.load_session(context)
            self.session_initialized = success
            
            if success:
                logger.info("LinkedIn session initialized successfully")
            else:
                logger.warning("No LinkedIn session found - scraping may be limited")
            
            return success
            
        except Exception as e:
            logger.error(f"Error initializing LinkedIn session: {e}")
            return False
    
    async def search_jobs(
        self,
        page: Page,
        search_config: SearchConfig,
        limit: int = 25
    ) -> List[str]:
        """
        Search for jobs on LinkedIn and extract job URLs.
        
        Args:
            page: Playwright page object
            search_config: Search configuration with URL
            limit: Maximum number of job URLs to extract
            
        Returns:
            List of job URLs
        """
        try:
            logger.info(f"Searching LinkedIn jobs: {search_config.url}")
            
            # Create LinkedIn job search scraper
            scraper = JobSearchScraper(page, self.callback)
            
            # Navigate to search URL
            await page.goto(
                search_config.url,
                wait_until='domcontentloaded',
                timeout=30000
            )
            logger.info("Navigated to LinkedIn search page")
            
            # Wait for job listings
            try:
                await page.wait_for_selector(
                    'li[data-occludable-job-id]',
                    timeout=10000
                )
                logger.info("Job listings loaded")
            except Exception as e:
                logger.warning(f"Timeout waiting for job listings: {e}")
            
            # Extract job URLs using existing scraper
            job_urls = await scraper._extract_job_urls(limit)
            
            logger.info(f"Extracted {len(job_urls)} job URLs from LinkedIn")
            return job_urls
            
        except Exception as e:
            logger.error(f"Error searching LinkedIn jobs: {e}")
            return []
    
    async def scrape_job_details(self, page: Page, job_url: str) -> Optional[JobData]:
        """
        Scrape detailed information from a LinkedIn job posting.
        
        Args:
            page: Playwright page object
            job_url: URL of the job posting
            
        Returns:
            JobData object if successful, None otherwise
        """
        try:
            logger.info(f"Scraping LinkedIn job: {job_url}")
            
            # Create LinkedIn job scraper
            scraper = JobScraper(page, self.callback)
            
            # Scrape job using existing scraper
            job = await scraper.scrape(job_url)
            
            if not job:
                logger.warning("No job data extracted")
                return None
            
            # Convert to standardized JobData
            job_data = JobData(
                platform='linkedin',
                job_title=job.job_title or '',
                job_description=job.job_description or '',
                job_url=job.linkedin_url or job_url,
                company_name=job.company or '',
                company_url=job.company_linkedin_url,
                location=job.location or '',
                posted_date=job.posted_date or '',
                applicant_count=job.applicant_count,
                engine_name='',  # Will be set by caller
                source_name='',  # Will be set by caller
            )
            
            logger.info(f"Successfully scraped LinkedIn job: {job_data.job_title}")
            return job_data
            
        except Exception as e:
            logger.error(f"Error scraping LinkedIn job details: {e}")
            return None
    
    async def scrape_company_details(
        self,
        page: Page,
        company_url: str
    ) -> Optional[CompanyData]:
        """
        Scrape company information from LinkedIn company page.
        
        Args:
            page: Playwright page object
            company_url: URL of the company page
            
        Returns:
            CompanyData object if successful, None otherwise
        """
        try:
            logger.info(f"Scraping LinkedIn company: {company_url}")
            
            # Create LinkedIn company scraper
            scraper = CompanyScraper(page, self.callback)
            
            # Scrape company using existing scraper
            company = await scraper.scrape(company_url)
            
            if not company:
                logger.warning("No company data extracted")
                return None
            
            # Convert to standardized CompanyData
            company_data = CompanyData(
                platform='linkedin',
                company_name=company.name or '',
                company_url=company.linkedin_url or company_url,
                company_overview=company.about_us or '',
                company_industry=company.industry or '',
                company_size=company.company_size or '',
                company_headquarters=company.headquarters or '',
                company_founded=company.founded or '',
                company_website=company.website or '',
                extra_data={
                    'phone': company.phone,
                    'company_type': company.company_type,
                    'specialties': company.specialties,
                }
            )
            
            logger.info(f"Successfully scraped LinkedIn company: {company_data.company_name}")
            return company_data
            
        except Exception as e:
            logger.error(f"Error scraping LinkedIn company details: {e}")
            return None
    
    def supports_company_scraping(self) -> bool:
        """LinkedIn supports company detail scraping."""
        return True
    
    def get_rate_limit(self) -> float:
        """Get LinkedIn rate limit (1 request per second by default)."""
        return self.config.get('rate_limit', 1.0)
    
    def requires_authentication(self) -> bool:
        """LinkedIn requires authentication for full access."""
        return True


# The @register_platform decorator automatically registers this scraper
# when the module is imported
logger.info("LinkedIn scraper registered with platform registry")
