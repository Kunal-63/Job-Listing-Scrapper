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
        
        # Wait for job listings to load with longer timeout and multiple selectors
        try:
            await self.page.wait_for_selector('li.scaffold-layout__list-item[data-occludable-job-id], li[data-occludable-job-id]', timeout=20000)
            logger.info("Job listings loaded")
        except Exception as e:
            logger.warning(f"Timeout waiting for results list, trying alternative selector: {e}")
            await self.page.wait_for_selector('.job-card-container', timeout=15000)
        
        await self.wait_and_focus(2)
        
        # Scroll to load more results
        await self.scroll_page_to_bottom(pause_time=1.5, max_scrolls=3)
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
                    await self.wait_and_focus(1.5)
                    
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
        Extract job details from the right-side details panel.
        
        Args:
            job_id: Optional job ID for reference
            
        Returns:
            Job object with extracted details, or None if extraction fails
        """
        try:
            # Job title - usually in h1 or main heading
            job_title = None
            try:
                title_elem = self.page.locator('.jobs-details__main-content h1, .show-more-less-html__markup h2').first
                job_title = await title_elem.inner_text()
                job_title = job_title.strip() if job_title else None
            except:
                pass
            
            # Company name
            company = None
            try:
                company_elem = self.page.locator('.job-details-jobs-unified-top-card__company-name, a[href*="/company/"]').first
                company = await company_elem.inner_text()
                company = company.strip() if company else None
            except:
                pass
            
            # Company URL
            company_url = None
            try:
                company_links = await self.page.locator('a[href*="/company/"]').all()
                for link in company_links:
                    href = await link.get_attribute('href')
                    if href and '/company/' in href:
                        company_url = href.split('?')[0] if '?' in href else href
                        break
            except:
                pass
            
            # Location
            location = None
            try:
                # Look for location in various possible selectors
                location_elem = self.page.locator('.job-details-jobs-unified-top-card__bullet, .base-text--italic').first
                location = await location_elem.inner_text()
                location = location.strip() if location else None
            except:
                pass
            
            # Posted date
            posted_date = None
            try:
                time_elem = self.page.locator('time').first
                posted_date = await time_elem.inner_text()
                posted_date = posted_date.strip() if posted_date else None
            except:
                pass
            
            # Applicant count
            applicant_count = None
            try:
                spans = await self.page.locator('span').all()
                for span in spans:
                    text = await span.inner_text()
                    if 'applicant' in text.lower():
                        applicant_count = text.strip()
                        break
            except:
                pass
            
            # Job description - get all text from description area
            job_description = None
            try:
                desc_elem = self.page.locator('.show-more-less-html__markup').first
                job_description = await desc_elem.inner_text()
                job_description = job_description.strip() if job_description else None
            except:
                try:
                    # Fallback: get from article
                    article = self.page.locator('article').first
                    job_description = await article.inner_text()
                    job_description = job_description.strip() if job_description else None
                except:
                    pass
            
            # Generate job URL (if we have job ID)
            linkedin_url = None
            if job_id:
                linkedin_url = f"https://www.linkedin.com/jobs/view/{job_id}/"
            
            # Create and return Job object
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
            logger.error(f"Error extracting job from details panel: {e}")
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
