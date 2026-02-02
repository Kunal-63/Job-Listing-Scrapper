#!/usr/bin/env python3
"""
Glassdoor Platform Scraper

Implements the BasePlatformScraper interface for Glassdoor job scraping.
Glassdoor has rich company information including reviews and ratings.
"""

import logging
import re
from typing import List, Optional, Dict, Any
from playwright.async_api import Page, BrowserContext

from ...core.base_scraper import BasePlatformScraper
from ...core.data_models import JobData, CompanyData, SearchConfig
from ...core.auth_manager import AuthManager
from ...core.platform_registry import register_platform

logger = logging.getLogger(__name__)


@register_platform('glassdoor')
class GlassdoorScraper(BasePlatformScraper):
    """
    Glassdoor platform scraper implementation.
    
    Glassdoor provides rich company information including ratings,
    reviews, and salary data.
    """
    
    def __init__(self, platform_name: str = 'glassdoor', config: Optional[Dict[str, Any]] = None):
        """
        Initialize Glassdoor scraper.
        
        Args:
            platform_name: Platform name (should be 'glassdoor')
            config: Platform-specific configuration
        """
        super().__init__(platform_name, config)
        self.auth_manager = AuthManager(platform_name, config)
    
    async def initialize_session(self, context: BrowserContext) -> bool:
        """
        Initialize Glassdoor session.
        
        Args:
            context: Playwright browser context
            
        Returns:
            True if session initialized successfully
        """
        try:
            # Try to load session cookies
            success = await self.auth_manager.load_session(context)
            self.session_initialized = success
            
            if success:
                logger.info("Glassdoor session initialized successfully")
            else:
                logger.warning("No Glassdoor session found - some features may be limited")
            
            return success
            
        except Exception as e:
            logger.error(f"Error initializing Glassdoor session: {e}")
            return False
    
    async def search_jobs(
        self,
        page: Page,
        search_config: SearchConfig,
        limit: int = 25
    ) -> List[str]:
        """
        Search for jobs on Glassdoor and extract job URLs.
        
        Args:
            page: Playwright page object
            search_config: Search configuration with URL
            limit: Maximum number of job URLs to extract
            
        Returns:
            List of job URLs
        """
        try:
            logger.info(f"Searching Glassdoor jobs: {search_config.url}")
            
            # Navigate to search URL
            await page.goto(
                search_config.url,
                wait_until='domcontentloaded',
                timeout=30000
            )
            logger.info("Navigated to Glassdoor search page")
            
            # Wait for job listings
            try:
                await page.wait_for_selector(
                    '[data-test="job-listing"], .react-job-listing',
                    timeout=10000
                )
                logger.info("Job listings loaded")
            except Exception as e:
                logger.warning(f"Timeout waiting for job listings: {e}")
            
            # Extract job URLs
            job_urls = await self._extract_job_urls(page, limit)
            
            logger.info(f"Extracted {len(job_urls)} job URLs from Glassdoor")
            return job_urls
            
        except Exception as e:
            logger.error(f"Error searching Glassdoor jobs: {e}")
            return []
    
    async def _extract_job_urls(self, page: Page, limit: int) -> List[str]:
        """Extract job URLs from Glassdoor search results."""
        job_urls = []
        
        try:
            # Glassdoor job cards
            job_cards = await page.locator('[data-test="job-listing"], .react-job-listing').all()
            
            for card in job_cards[:limit]:
                try:
                    # Look for job link
                    link = card.locator('a[href*="/job-listing/"]').first
                    href = await link.get_attribute('href')
                    
                    if href:
                        # Make absolute URL
                        if href.startswith('/'):
                            href = f"https://www.glassdoor.com{href}"
                        elif not href.startswith('http'):
                            href = f"https://www.glassdoor.com/{href}"
                        
                        if href not in job_urls:
                            job_urls.append(href)
                            
                            if len(job_urls) >= limit:
                                break
                                
                except Exception as e:
                    logger.debug(f"Error extracting job URL from card: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"Error extracting job URLs: {e}")
        
        return job_urls
    
    async def scrape_job_details(self, page: Page, job_url: str) -> Optional[JobData]:
        """
        Scrape detailed information from a Glassdoor job posting.
        
        Args:
            page: Playwright page object
            job_url: URL of the job posting
            
        Returns:
            JobData object if successful, None otherwise
        """
        try:
            logger.info(f"Scraping Glassdoor job: {job_url}")
            
            # Navigate to job page
            await page.goto(job_url, wait_until='domcontentloaded', timeout=30000)
            
            # Wait for job content
            try:
                await page.wait_for_selector('[data-test="job-title"], .JobDetails_jobTitle', timeout=10000)
            except:
                logger.warning("Job content not loaded")
            
            # Extract job details
            job_title = await self._extract_job_title(page)
            company_name = await self._extract_company_name(page)
            location = await self._extract_location(page)
            description = await self._extract_description(page)
            posted_date = await self._extract_posted_date(page)
            salary = await self._extract_salary(page)
            company_rating = await self._extract_company_rating(page)
            
            # Create JobData
            job_data = JobData(
                platform='glassdoor',
                job_title=job_title or '',
                job_description=description or '',
                job_url=job_url,
                company_name=company_name or '',
                company_url=None,  # Can be extracted if needed
                location=location or '',
                posted_date=posted_date or '',
                applicant_count=None,
                engine_name='',  # Will be set by caller
                source_name='',  # Will be set by caller
                extra_data={
                    'salary': salary,
                    'company_rating': company_rating
                }
            )
            
            logger.info(f"Successfully scraped Glassdoor job: {job_data.job_title}")
            return job_data
            
        except Exception as e:
            logger.error(f"Error scraping Glassdoor job details: {e}")
            return None
    
    async def _extract_job_title(self, page: Page) -> Optional[str]:
        """Extract job title."""
        try:
            title_elem = page.locator('[data-test="job-title"], .JobDetails_jobTitle, h1').first
            title = await title_elem.inner_text()
            return title.strip()
        except:
            return None
    
    async def _extract_company_name(self, page: Page) -> Optional[str]:
        """Extract company name."""
        try:
            company_elem = page.locator('[data-test="employer-name"], .EmployerProfile_employerName').first
            company = await company_elem.inner_text()
            return company.strip()
        except:
            return None
    
    async def _extract_location(self, page: Page) -> Optional[str]:
        """Extract location."""
        try:
            location_elem = page.locator('[data-test="location"], .JobDetails_location').first
            location = await location_elem.inner_text()
            return location.strip()
        except:
            return None
    
    async def _extract_description(self, page: Page) -> Optional[str]:
        """Extract job description."""
        try:
            desc_elem = page.locator('[data-test="job-description"], .JobDetails_jobDescription').first
            description = await desc_elem.inner_text()
            return description.strip()
        except:
            return None
    
    async def _extract_posted_date(self, page: Page) -> Optional[str]:
        """Extract posted date."""
        try:
            text_elements = await page.locator('span, div').all()
            for elem in text_elements:
                text = await elem.inner_text()
                if 'ago' in text.lower():
                    match = re.search(r'(\d+[+]?\s+(?:minute|hour|day|week|month)s?\s+ago)', text, re.IGNORECASE)
                    if match:
                        return match.group(1).strip()
        except:
            pass
        return None
    
    async def _extract_salary(self, page: Page) -> Optional[str]:
        """Extract salary information."""
        try:
            salary_elem = page.locator('[data-test="salary"], .JobDetails_salary').first
            salary = await salary_elem.inner_text()
            if salary and ('$' in salary or 'K' in salary):
                return salary.strip()
        except:
            pass
        return None
    
    async def _extract_company_rating(self, page: Page) -> Optional[str]:
        """Extract company rating."""
        try:
            rating_elem = page.locator('[data-test="rating"], .EmployerProfile_ratingNum').first
            rating = await rating_elem.inner_text()
            return rating.strip()
        except:
            return None
    
    async def scrape_company_details(
        self,
        page: Page,
        company_url: str
    ) -> Optional[CompanyData]:
        """
        Scrape company information from Glassdoor.
        
        Glassdoor has rich company pages with reviews and ratings.
        
        Args:
            page: Playwright page object
            company_url: URL of the company page
            
        Returns:
            CompanyData object if successful, None otherwise
        """
        logger.info(f"Glassdoor company scraping not fully implemented yet: {company_url}")
        # TODO: Implement Glassdoor company scraping
        # Glassdoor has rich company data including reviews, ratings, salaries
        return None
    
    def supports_company_scraping(self) -> bool:
        """Glassdoor supports company scraping (but not fully implemented yet)."""
        return False  # Set to True when implemented
    
    def get_rate_limit(self) -> float:
        """Get Glassdoor rate limit (0.5 requests per second - more conservative)."""
        return self.config.get('rate_limit', 0.5)
    
    def requires_authentication(self) -> bool:
        """Glassdoor may require authentication for full access."""
        return self.config.get('requires_auth', False)


logger.info("Glassdoor scraper registered with platform registry")
