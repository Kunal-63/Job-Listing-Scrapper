"""
Job search scraper for LinkedIn.

Searches for jobs on LinkedIn and extracts job details from detail and company pages.
"""
import logging
from typing import Optional, List
from urllib.parse import urlencode
from playwright.async_api import Page

from ..callbacks import ProgressCallback, SilentCallback
from ..models.job import Job
from .base import BaseScraper
from .job import JobScraper
from .company import CompanyScraper

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
        limit: int = 25,
        search_url: Optional[str] = None,
        max_concurrent: int = 5
    ) -> List[Job]:
        """
        Search for jobs on LinkedIn and scrape details from job and company pages with parallel processing.
        
        Args:
            keywords: Job search keywords (e.g., "software engineer")
            location: Job location (e.g., "San Francisco, CA")
            limit: Maximum number of jobs to scrape
            search_url: Full LinkedIn job search URL (overrides keywords and location)
            max_concurrent: Maximum number of concurrent scraping tasks (default: 5)
            
        Returns:
            List of Job objects with all details
        """
        import asyncio
        
        logger.info(f"Starting job search: keywords='{keywords}', location='{location}', search_url='{search_url}'")
        
        # Use provided search_url if available, otherwise build from keywords/location
        if search_url:
            url = search_url
            logger.info(f"Using provided search URL: {url}")
        else:
            url = self._build_search_url(keywords, location)
            logger.info(f"Built search URL: {url}")
        
        await self.callback.on_start("JobSearch", url)
        
        # Navigate to search results
        await self.navigate_and_wait(url)
        await self.callback.on_progress("Navigated to search results", 10)
        
        # Wait for job listings to load
        try:
            await self.page.wait_for_selector('li[data-occludable-job-id]', timeout=10000)
            logger.info("Job listings loaded")
        except Exception as e:
            logger.warning(f"Timeout waiting for listings: {e}")
        
        await self.wait_and_focus(0.5)
        await self.callback.on_progress("Loaded job listings", 20)
        
        # Extract job URLs from the search results list
        logger.info(f"Extracting up to {limit} job URLs...")
        job_urls = await self._extract_job_urls(limit)
        await self.callback.on_progress(f"Found {len(job_urls)} job URLs", 30)
        
        if not job_urls:
            logger.warning("No job URLs found!")
            return []
        
        # PARALLEL PROCESSING: Scrape jobs in batches
        logger.info(f"Starting parallel scraping of {len(job_urls)} jobs with max {max_concurrent} concurrent tasks")
        jobs = await self._scrape_jobs_parallel(job_urls, max_concurrent)
        
        await self.callback.on_progress(f"Scraped {len(jobs)} jobs, fetching company details...", 70)
        
        # PARALLEL PROCESSING: Scrape company details for all jobs
        logger.info(f"Starting parallel company scraping for {len(jobs)} jobs")
        jobs = await self._scrape_companies_parallel(jobs, max_concurrent)
        
        await self.callback.on_progress(f"Scraping complete: {len(jobs)} jobs", 100)
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
    
    async def _scrape_jobs_parallel(self, job_urls: List[str], max_concurrent: int) -> List[Job]:
        """
        Scrape multiple jobs in parallel with concurrency control.
        
        Args:
            job_urls: List of job URLs to scrape
            max_concurrent: Maximum number of concurrent tasks
            
        Returns:
            List of successfully scraped Job objects
        """
        import asyncio
        from playwright.async_api import async_playwright
        
        jobs = []
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def scrape_single_job(url: str, index: int) -> Optional[Job]:
            """Scrape a single job with semaphore control."""
            async with semaphore:
                try:
                    logger.info(f"[{index + 1}/{len(job_urls)}] Scraping job: {url}")
                    
                    # Create a new page for this job to enable parallel processing
                    async with async_playwright() as p:
                        browser = await p.chromium.launch(headless=True)
                        context = await browser.new_context()
                        
                        # Load session cookies if available
                        try:
                            import json
                            with open("linkedin_session.json", "r") as f:
                                session_data = json.load(f)
                                if "cookies" in session_data:
                                    await context.add_cookies(session_data["cookies"])
                        except:
                            pass
                        
                        page = await context.new_page()
                        job_scraper = JobScraper(page, SilentCallback())
                        
                        job = await job_scraper.scrape(url)
                        
                        await browser.close()
                        
                        if job:
                            logger.info(f"✓ [{index + 1}/{len(job_urls)}] {job.job_title}")
                            return job
                        else:
                            logger.warning(f"✗ [{index + 1}/{len(job_urls)}] Failed to scrape")
                            return None
                            
                except Exception as e:
                    logger.warning(f"✗ [{index + 1}/{len(job_urls)}] Error: {e}")
                    return None
        
        # Create tasks for all jobs
        tasks = [scrape_single_job(url, i) for i, url in enumerate(job_urls)]
        
        # Execute all tasks and gather results
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out None values and exceptions
        for result in results:
            if isinstance(result, Job):
                jobs.append(result)
        
        logger.info(f"Parallel job scraping complete: {len(jobs)}/{len(job_urls)} successful")
        return jobs
    
    async def _scrape_companies_parallel(self, jobs: List[Job], max_concurrent: int) -> List[Job]:
        """
        Scrape company details for multiple jobs in parallel.
        
        Args:
            jobs: List of Job objects to enrich with company data
            max_concurrent: Maximum number of concurrent tasks
            
        Returns:
            List of Job objects enriched with company details
        """
        import asyncio
        from playwright.async_api import async_playwright
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def scrape_single_company(job: Job, index: int) -> Job:
            """Scrape company details for a single job with semaphore control."""
            if not job.company_linkedin_url:
                return job
                
            async with semaphore:
                try:
                    logger.info(f"[{index + 1}/{len(jobs)}] Fetching company: {job.company}")
                    
                    # Create a new page for this company to enable parallel processing
                    async with async_playwright() as p:
                        browser = await p.chromium.launch(headless=True)
                        context = await browser.new_context()
                        
                        # Load session cookies if available
                        try:
                            import json
                            with open("linkedin_session.json", "r") as f:
                                session_data = json.load(f)
                                if "cookies" in session_data:
                                    await context.add_cookies(session_data["cookies"])
                        except:
                            pass
                        
                        page = await context.new_page()
                        company_scraper = CompanyScraper(page, SilentCallback())
                        
                        company = await company_scraper.scrape(job.company_linkedin_url)
                        
                        await browser.close()
                        
                        if company:
                            job.headquarters = company.headquarters
                            job.founded = company.founded
                            job.industry = company.industry
                            job.company_size = company.company_size
                            logger.info(f"✓ [{index + 1}/{len(jobs)}] Company details added")
                        
                except Exception as e:
                    logger.warning(f"✗ [{index + 1}/{len(jobs)}] Company error: {e}")
                
                return job
        
        # Create tasks for all companies
        tasks = [scrape_single_company(job, i) for i, job in enumerate(jobs)]
        
        # Execute all tasks and gather results
        enriched_jobs = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions
        valid_jobs = [job for job in enriched_jobs if isinstance(job, Job)]
        
        logger.info(f"Parallel company scraping complete: {len(valid_jobs)}/{len(jobs)} successful")
        return valid_jobs

    
    
    async def _scrape_jobs_from_list(self, limit: int) -> List[Job]:
        """
        Scrape job details by clicking each job item in the list (parallel processing).
        
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
            
            # Limit the items
            job_items = job_items[:limit]
            
            # Create tasks for parallel processing
            import asyncio
            tasks = []
            
            for idx, job_item in enumerate(job_items):
                try:
                    # Get job ID from data attribute
                    job_id = await job_item.get_attribute('data-occludable-job-id')
                    logger.debug(f"Processing job {idx + 1}: ID {job_id}")
                    
                    # Click on the job item
                    await job_item.click()
                    await self.wait_and_focus(0.2)
                    
                    # Extract job details
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
            
            # Fast extraction - no extra waits
            try:
                title = await self.page.locator('h1').first.inner_text()
                job_title = title.strip() if title else None
            except:
                pass
            
            try:
                company = await self.page.locator('a[href*="/company/"]').first.inner_text()
                company = company.strip() if company else None
            except:
                pass
            
            try:
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
                job_description = (desc.strip()[:500] + "...") if desc and len(desc) > 500 else desc.strip() if desc else None
            except:
                pass
            
            try:
                body_text = await self.page.locator('body').inner_text()
                for line in body_text.split('\n')[:100]:  # Only check first 100 lines
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
