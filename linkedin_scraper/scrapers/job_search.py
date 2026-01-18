"""
Job search scraper for LinkedIn.

Searches for jobs on LinkedIn and extracts job details from the list view.
"""
import logging
from typing import Optional, List
from urllib.parse import urlencode
from playwright.async_api import Page

from ..callbacks import ProgressCallback, SilentCallback
from ..models.job import Job
from .base import BaseScraper

logger = logging.getLogger(__name__)


class JobSearchScraper(BaseScraper):
    """
    Scraper for LinkedIn job search results.
    
    Example:
        async with BrowserManager() as browser:
            scraper = JobSearchScraper(browser.page)
            job_urls = await scraper.search(
                keywords="software engineer",
                location="San Francisco",
                limit=10
            )
    """
    
    def __init__(self, page: Page, callback: Optional[ProgressCallback] = None):
        """
        Initialize job search scraper.
        
        Args:
            page: Playwright page object
            callback: Optional progress callback
        """
        super().__init__(page, callback or SilentCallback())
    
    async def search(
        self,
        keywords: Optional[str] = None,
        location: Optional[str] = None,
        limit: int = 25
    ) -> List[Job]:
        """
        Search for jobs on LinkedIn and scrape details from list view.
        
        Args:
            keywords: Job search keywords (e.g., "software engineer")
            location: Job location (e.g., "San Francisco, CA")
            limit: Maximum number of jobs to scrape
            
        Returns:
            List of Job objects with all details
        """
        logger.info(f"Starting job search: keywords='{keywords}', location='{location}'")
        
        # Build search URL
        search_url = self._build_search_url(keywords, location)
        await self.callback.on_start("JobSearch", search_url)
        
        # Navigate to search results
        await self.navigate_and_wait(search_url)
        await self.callback.on_progress("Navigated to search results", 20)
        
        # Wait for job listings to load - aggressive optimization
        try:
            await self.page.wait_for_selector('li[data-occludable-job-id]', timeout=8000)
            logger.info("Job listings loaded")
        except Exception as e:
            logger.warning(f"Timeout: {e}")
        
        await self.wait_and_focus(0.2)
        
        # Minimal scroll
        await self.scroll_page_to_bottom(pause_time=0.1, max_scrolls=1)
        await self.callback.on_progress("Loaded job listings", 50)
        
        # Extract job details by clicking each item
        jobs = await self._scrape_jobs_from_list(limit)
        await self.callback.on_progress(f"Found {len(jobs)} jobs", 90)
        
        await self.callback.on_progress("Search complete", 100)
        await self.callback.on_complete("JobSearch", jobs)
        
        logger.info(f"Job search complete: found {len(jobs)} jobs")
        return jobs
    
    def _build_search_url(
        self,
        keywords: Optional[str] = None,
        location: Optional[str] = None
    ) -> str:
        """Build LinkedIn job search URL with parameters."""
        base_url = "https://www.linkedin.com/jobs/search/"
        
        params = {}
        if keywords:
            params['keywords'] = keywords
        if location:
            params['location'] = location
        
        if params:
            return f"{base_url}?{urlencode(params)}"
        return base_url
    
    
    async def _scrape_jobs_from_list(self, limit: int) -> List[Job]:
        """
        Scrape job details by clicking each job item in the list.
        
        Args:
            limit: Maximum number of jobs to scrape
            
        Returns:
            List of Job objects with all details
        """
        jobs = []
        
        try:
            # Find all job items in the list
            job_items = await self.page.locator('li[data-occludable-job-id]').all()
            logger.info(f"Found {len(job_items)} job items in list")
            
            for idx, job_item in enumerate(job_items):
                if len(jobs) >= limit:
                    break
                
                try:
                    # Get job ID from data attribute
                    job_id = await job_item.get_attribute('data-occludable-job-id')
                    logger.debug(f"Processing job {idx + 1}: ID {job_id}")
                    
                    # Click on the job item to load details in right panel
                    await job_item.click()
                    await self.wait_and_focus(0.3)
                    
                    # Extract job details from the right panel
                    job = await self._extract_job_from_details_panel(job_id)
                    
                    if job:
                        jobs.append(job)
                        logger.info(f"Successfully scraped: {job.job_title} at {job.company}")
                    
                except Exception as e:
                    logger.warning(f"Error processing job item {idx + 1}: {e}")
                    continue
            
            logger.info(f"Successfully scraped {len(jobs)} job details from list")
        
        except Exception as e:
            logger.error(f"Error scraping jobs from list: {e}")
        
        return jobs
    
    async def _extract_job_from_details_panel(self, job_id: Optional[str] = None) -> Optional[Job]:
        """
        Extract job details from the right-side details panel (ultra-fast).
        
        Args:
            job_id: Optional job ID for reference
            
        Returns:
            Job object with extracted details, or None if extraction fails
        """
        try:
            job_title = None
            company = None
            company_url = None
            location = None
            posted_date = None
            applicant_count = None
            job_description = None
            
            # Aggressive parallel extraction - no error handling delays
            try:
                title = await self.page.locator('h1').first.inner_text()
                job_title = title.strip() if title else None
            except:
                pass
            
            try:
                company = await self.page.locator('a[href*="/company/"]').first.inner_text()
                company = company.strip() if company else None
                company_url = await self.page.locator('a[href*="/company/"]').first.get_attribute('href')
                if company_url and '?' in company_url:
                    company_url = company_url.split('?')[0]
            except:
                pass
            
            try:
                loc = await self.page.locator('.job-details-jobs-unified-top-card__bullet').first.inner_text()
                location = loc.strip() if loc else None
            except:
                pass
            
            try:
                date = await self.page.locator('time').first.inner_text()
                posted_date = date.strip() if date else None
            except:
                pass
            
            try:
                desc = await self.page.locator('.show-more-less-html__markup').first.inner_text()
                job_description = desc.strip() if desc else None
            except:
                pass
            
            try:
                body = await self.page.locator('body').inner_text()
                for line in body.split('\n'):
                    if 'applicant' in line.lower():
                        applicant_count = line.strip()
                        break
            except:
                pass
            
            linkedin_url = f"https://www.linkedin.com/jobs/view/{job_id}/" if job_id else None
            
            job = Job(
                linkedin_url=linkedin_url,
                job_title=job_title,
                company=company,
                company_linkedin_url=company_url,
                location=location,
                posted_date=posted_date,
                applicant_count=applicant_count,
                job_description=job_description
            )
            
            return job
        
        except Exception as e:
            logger.error(f"Error extracting job: {e}")
            return None
    
    async def _extract_job_urls(self, limit: int) -> List[str]:
        """
        Extract job URLs from search results (legacy method).
        
        Args:
            limit: Maximum number of URLs to extract
            
        Returns:
            List of job posting URLs
        """
        job_urls = []
        
        try:
            # Method 1: Try to find job links by job ID (from data attribute)
            job_items = await self.page.locator('li[data-occludable-job-id]').all()
            logger.info(f"Found {len(job_items)} job items")
            
            seen_urls = set()
            for job_item in job_items:
                if len(job_urls) >= limit:
                    break
                
                try:
                    # Find the job title link within this item - updated selector
                    job_link = job_item.locator('a.job-card-list__title--link, a.job-card-container__link').first
                    href = await job_link.get_attribute('href')
                    
                    if href and '/jobs/view/' in href:
                        # Clean URL (remove query params)
                        clean_url = href.split('?')[0] if '?' in href else href
                        
                        # Ensure full URL
                        if not clean_url.startswith('http'):
                            clean_url = f"https://www.linkedin.com{clean_url}"
                        
                        # Avoid duplicates
                        if clean_url not in seen_urls:
                            job_urls.append(clean_url)
                            seen_urls.add(clean_url)
                            logger.debug(f"Extracted job URL: {clean_url}")
                except Exception as e:
                    logger.debug(f"Error extracting job from item: {e}")
                    continue
            
            # Method 2: Fallback - find all job view links if Method 1 didn't work
            if len(job_urls) == 0:
                logger.info("Method 1 failed, trying fallback method...")
                job_links = await self.page.locator('a[href*="/jobs/view/"]').all()
                
                for link in job_links:
                    if len(job_urls) >= limit:
                        break
                    
                    try:
                        href = await link.get_attribute('href')
                        if href and '/jobs/view/' in href:
                            # Clean URL (remove query params)
                            clean_url = href.split('?')[0] if '?' in href else href
                            
                            # Ensure full URL
                            if not clean_url.startswith('http'):
                                clean_url = f"https://www.linkedin.com{clean_url}"
                            
                            # Avoid duplicates
                            if clean_url not in seen_urls:
                                job_urls.append(clean_url)
                                seen_urls.add(clean_url)
                    except Exception as e:
                        logger.debug(f"Error extracting job URL: {e}")
                        continue
        
        except Exception as e:
            logger.warning(f"Error extracting job URLs: {e}")
        
        logger.info(f"Successfully extracted {len(job_urls)} unique job URLs")
        return job_urls
