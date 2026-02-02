#!/usr/bin/env python3
"""
Indeed Platform Scraper

Implements the BasePlatformScraper interface for Indeed job scraping.
Indeed typically doesn't require authentication for basic job scraping.
"""

import logging
import re
from typing import List, Optional, Dict, Any
from playwright.async_api import Page, BrowserContext

from ...core.base_scraper import BasePlatformScraper
from ...core.data_models import JobData, CompanyData, SearchConfig
from ...core.platform_registry import register_platform

logger = logging.getLogger(__name__)


@register_platform('indeed')
class IndeedScraper(BasePlatformScraper):
    """
    Indeed platform scraper implementation.
    
    Indeed is simpler than LinkedIn - no authentication required,
    and company pages are less detailed.
    """
    
    def __init__(self, platform_name: str = 'indeed', config: Optional[Dict[str, Any]] = None):
        """
        Initialize Indeed scraper.
        
        Args:
            platform_name: Platform name (should be 'indeed')
            config: Platform-specific configuration
        """
        super().__init__(platform_name, config)
    
    async def initialize_session(self, context: BrowserContext) -> bool:
        """
        Initialize Indeed session (no auth required).
        
        Args:
            context: Playwright browser context
            
        Returns:
            Always True (no auth needed)
        """
        logger.info("Indeed scraper initialized (no authentication required)")
        self.session_initialized = True
        return True
    
    async def search_jobs(
        self,
        page: Page,
        search_config: SearchConfig,
        limit: int = 25
    ) -> List[str]:
        """
        Search for jobs on Indeed and extract job URLs.
        
        Args:
            page: Playwright page object
            search_config: Search configuration with URL
            limit: Maximum number of job URLs to extract
            
        Returns:
            List of job URLs
        """
        try:
            logger.info(f"Searching Indeed jobs: {search_config.url}")
            
            # Navigate to search URL
            await page.goto(
                search_config.url,
                wait_until='domcontentloaded',
                timeout=30000
            )
            logger.info("Navigated to Indeed search page")
            
            # Wait for job listings
            try:
                await page.wait_for_selector(
                    '.job_seen_beacon, .jobsearch-ResultsList',
                    timeout=10000
                )
                logger.info("Job listings loaded")
            except Exception as e:
                logger.warning(f"Timeout waiting for job listings: {e}")
            
            # Extract job URLs
            job_urls = await self._extract_job_urls(page, limit)
            
            logger.info(f"Extracted {len(job_urls)} job URLs from Indeed")
            return job_urls
            
        except Exception as e:
            logger.error(f"Error searching Indeed jobs: {e}")
            return []
    
    async def _extract_job_urls(self, page: Page, limit: int) -> List[str]:
        """
        Extract job URLs from Indeed search results.
        
        Args:
            page: Playwright page object
            limit: Maximum number of URLs to extract
            
        Returns:
            List of job URLs
        """
        job_urls = []
        
        try:
            # Indeed job cards have various selectors
            job_cards = await page.locator('.job_seen_beacon, .jobsearch-ResultsList li').all()
            
            for card in job_cards[:limit]:
                try:
                    # Look for job link
                    link = card.locator('a[href*="/viewjob"], a[href*="/rc/clk"]').first
                    href = await link.get_attribute('href')
                    
                    if href:
                        # Make absolute URL
                        if href.startswith('/'):
                            href = f"https://www.indeed.com{href}"
                        elif not href.startswith('http'):
                            href = f"https://www.indeed.com/{href}"
                        
                        # Clean URL (remove tracking params)
                        if '?' in href:
                            href = href.split('?')[0]
                        
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
        Scrape detailed information from an Indeed job posting.
        
        Args:
            page: Playwright page object
            job_url: URL of the job posting
            
        Returns:
            JobData object if successful, None otherwise
        """
        try:
            logger.info(f"Scraping Indeed job: {job_url}")
            
            # Navigate to job page
            await page.goto(job_url, wait_until='domcontentloaded', timeout=30000)
            
            # Wait for job content
            try:
                await page.wait_for_selector('.jobsearch-JobComponent, #jobDescriptionText', timeout=10000)
            except:
                logger.warning("Job content not loaded")
            
            # Extract job details
            job_title = await self._extract_job_title(page)
            company_name = await self._extract_company_name(page)
            location = await self._extract_location(page)
            description = await self._extract_description(page)
            posted_date = await self._extract_posted_date(page)
            salary = await self._extract_salary(page)
            
            # Create JobData
            job_data = JobData(
                platform='indeed',
                job_title=job_title or '',
                job_description=description or '',
                job_url=job_url,
                company_name=company_name or '',
                company_url=None,  # Indeed doesn't have company LinkedIn URLs
                location=location or '',
                posted_date=posted_date or '',
                applicant_count=None,  # Indeed doesn't show applicant count
                engine_name='',  # Will be set by caller
                source_name='',  # Will be set by caller
                extra_data={
                    'salary': salary
                }
            )
            
            logger.info(f"Successfully scraped Indeed job: {job_data.job_title}")
            return job_data
            
        except Exception as e:
            logger.error(f"Error scraping Indeed job details: {e}")
            return None
    
    async def _extract_job_title(self, page: Page) -> Optional[str]:
        """Extract job title from Indeed page."""
        try:
            title_elem = page.locator('h1.jobsearch-JobInfoHeader-title, h1').first
            title = await title_elem.inner_text()
            return title.strip()
        except:
            return None
    
    async def _extract_company_name(self, page: Page) -> Optional[str]:
        """Extract company name from Indeed page."""
        try:
            company_elem = page.locator('[data-company-name], .jobsearch-InlineCompanyRating-companyHeader a, .jobsearch-CompanyInfoContainer a').first
            company = await company_elem.inner_text()
            return company.strip()
        except:
            return None
    
    async def _extract_location(self, page: Page) -> Optional[str]:
        """Extract location from Indeed page."""
        try:
            location_elem = page.locator('[data-testid="job-location"], .jobsearch-JobInfoHeader-subtitle div').first
            location = await location_elem.inner_text()
            return location.strip()
        except:
            return None
    
    async def _extract_description(self, page: Page) -> Optional[str]:
        """Extract job description from Indeed page."""
        try:
            desc_elem = page.locator('#jobDescriptionText, .jobsearch-jobDescriptionText').first
            description = await desc_elem.inner_text()
            return description.strip()
        except:
            return None
    
    async def _extract_posted_date(self, page: Page) -> Optional[str]:
        """Extract posted date from Indeed page."""
        try:
            # Look for "Posted X days ago" text
            text_elements = await page.locator('span, div').all()
            for elem in text_elements:
                text = await elem.inner_text()
                if 'posted' in text.lower() or 'ago' in text.lower():
                    match = re.search(r'(posted\s+)?(\d+\s+(?:minute|hour|day|week|month)s?\s+ago)', text, re.IGNORECASE)
                    if match:
                        return match.group(2).strip()
        except:
            pass
        return None
    
    async def _extract_salary(self, page: Page) -> Optional[str]:
        """Extract salary information from Indeed page."""
        try:
            salary_elem = page.locator('[data-testid="jobsearch-JobMetadataHeader-salary"], .jobsearch-JobMetadataHeader-item').first
            salary = await salary_elem.inner_text()
            if salary and ('$' in salary or 'year' in salary.lower() or 'hour' in salary.lower()):
                return salary.strip()
        except:
            pass
        return None
    
    async def scrape_company_details(
        self,
        page: Page,
        company_url: str
    ) -> Optional[CompanyData]:
        """
        Scrape company information from Indeed.
        
        Note: Indeed doesn't have rich company pages like LinkedIn,
        so this returns minimal information.
        
        Args:
            page: Playwright page object
            company_url: URL of the company page
            
        Returns:
            CompanyData object with basic info, or None
        """
        logger.info("Indeed has limited company information - skipping company scraping")
        return None
    
    def supports_company_scraping(self) -> bool:
        """Indeed has limited company information."""
        return False
    
    def get_rate_limit(self) -> float:
        """Get Indeed rate limit (2 requests per second by default)."""
        return self.config.get('rate_limit', 2.0)
    
    def requires_authentication(self) -> bool:
        """Indeed doesn't require authentication for basic scraping."""
        return False


logger.info("Indeed scraper registered with platform registry")
