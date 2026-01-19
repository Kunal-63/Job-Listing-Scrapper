"""
Job search scraper for LinkedIn.

Searches for jobs on LinkedIn and extracts job details from detail and company pages.
"""
import asyncio
import logging
import re
import sys
from typing import Optional, List
from urllib.parse import urlencode
from playwright.async_api import Page

from ..callbacks import ProgressCallback, SilentCallback
from ..models.job import Job
from .base import BaseScraper
from .job import JobScraper
from .company import CompanyScraper

# Configure logging with console handler
logger = logging.getLogger(__name__)

# Only configure if not already configured
if not logger.handlers:
    logger.setLevel(logging.INFO)
    
    # Create console handler with formatting
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(console_handler)
    logger.propagate = False


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
        max_concurrent: int = 3
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
        logger.info(f"Starting job search: keywords='{keywords}', location='{location}', search_url='{search_url}'")
        
        if search_url:
            url = search_url
            logger.info(f"Using provided search URL: {url}")
        else:
            url = self._build_search_url(keywords, location)
            logger.info(f"Built search URL: {url}")
        
        await self.callback.on_start("JobSearch", url)
        
        await self.navigate_and_wait(url, wait_until='domcontentloaded', timeout=30000)
        await self.callback.on_progress("Navigated to search results", 10)
        
        try:
            await self.page.wait_for_selector('li[data-occludable-job-id]', timeout=5000)
            logger.info("Job listings loaded")
        except Exception as e:
            logger.warning(f"Timeout waiting for listings (trying anyway): {e}")
        
        await self.wait_and_focus(0.3)
        await self.callback.on_progress("Loaded job listings", 20)
        
        logger.info(f"Extracting up to {limit} job URLs...")
        job_urls = await self._extract_job_urls(limit)
        await self.callback.on_progress(f"Found {len(job_urls)} job URLs", 30)
        
        if not job_urls:
            logger.warning("No job URLs found!")
            return []
        
        logger.info(f"Starting parallel scraping of {len(job_urls)} jobs with max {max_concurrent} concurrent tasks")
        jobs = await self._scrape_jobs_parallel(job_urls, max_concurrent)
        
        await self.callback.on_progress(f"Scraped {len(jobs)} jobs, fetching company details...", 70)
        
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
        
        async def scrape_single_job(url: str, index: int, max_retries: int = 2) -> Optional[Job]:
            """Scrape a single job with retry logic."""
            async with semaphore:
                for attempt in range(max_retries + 1):
                    try:
                        if attempt > 0:
                            logger.info(f"[{index + 1}/{len(job_urls)}] Retry {attempt}/{max_retries}: {url}")
                        else:
                            logger.info(f"[{index + 1}/{len(job_urls)}] Scraping job: {url}")
                        
                        async with async_playwright() as p:
                            browser = await p.chromium.launch(headless=True)
                            context = await browser.new_context()
                            
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
                                logger.info(f"[{index + 1}/{len(job_urls)}] {job.job_title}")
                                return job
                            else:
                                if attempt < max_retries:
                                    logger.warning(f"[{index + 1}/{len(job_urls)}] Failed, will retry...")
                                    await asyncio.sleep(1)
                                    continue
                                else:
                                    logger.warning(f"[{index + 1}/{len(job_urls)}] Failed after {max_retries} retries")
                                    return None
                                
                    except Exception as e:
                        error_msg = str(e)
                        if attempt < max_retries:
                            logger.warning(f"[{index + 1}/{len(job_urls)}] Error (will retry): {error_msg[:100]}")
                            await asyncio.sleep(2)
                            continue
                        else:
                            logger.warning(f"[{index + 1}/{len(job_urls)}] Error after {max_retries} retries: {error_msg[:100]}")
                            return None
                
                return None
        
        tasks = [scrape_single_job(url, i) for i, url in enumerate(job_urls)]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Job):
                jobs.append(result)
        
        logger.info(f"Parallel job scraping complete: {len(jobs)}/{len(job_urls)} successful")
        return jobs
    
    async def _scrape_companies_parallel(self, jobs: List[Job], max_concurrent: int) -> List[Job]:
        """
        Scrape company details for multiple jobs in parallel.
        IMPORTANT: Jobs are ALWAYS returned, even if company scraping fails.
        
        Args:
            jobs: List of Job objects to enrich with company data
            max_concurrent: Maximum number of concurrent tasks
            
        Returns:
            List of Job objects (all jobs, with or without company details)
        """
        import asyncio
        from playwright.async_api import async_playwright
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def scrape_single_company(job: Job, index: int, max_retries: int = 1) -> Job:
            """Scrape company details for a single job with retry logic. Always returns the job."""
            if not job.company_linkedin_url:
                logger.info(f"[{index + 1}/{len(jobs)}] No company URL for {job.company}, skipping company scrape")
                return job
                
            async with semaphore:
                for attempt in range(max_retries + 1):
                    try:
                        if attempt > 0:
                            logger.info(f"[{index + 1}/{len(jobs)}] Retry {attempt}/{max_retries} for company: {job.company}")
                        else:
                            logger.info(f"[{index + 1}/{len(jobs)}] Fetching company: {job.company}")
                        
                        async with async_playwright() as p:
                            browser = await p.chromium.launch(headless=True)
                            context = await browser.new_context()
                            
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
                                logger.info(f"[{index + 1}/{len(jobs)}] Company details added")
                                return job  # Success, return enriched job
                            else:
                                if attempt < max_retries:
                                    logger.warning(f"[{index + 1}/{len(jobs)}] Company scrape failed, will retry...")
                                    await asyncio.sleep(1)
                                    continue
                                else:
                                    logger.warning(f"[{index + 1}/{len(jobs)}] Company scrape failed, keeping job without company details")
                                    return job  # Return job without company details
                        
                    except Exception as e:
                        error_msg = str(e)
                        if attempt < max_retries:
                            logger.warning(f"[{index + 1}/{len(jobs)}] Company error (will retry): {error_msg[:100]}")
                            await asyncio.sleep(2)
                            continue
                        else:
                            logger.warning(f"{index + 1}/{len(jobs)}] Company error, keeping job without company details: {error_msg[:100]}")
                            return job  # Return job without company details
                
                return job  # Fallback: always return the job
        
        tasks = [scrape_single_company(job, i) for i, job in enumerate(jobs)]
        
        enriched_jobs = await asyncio.gather(*tasks, return_exceptions=True)
        
        final_jobs = []
        for i, result in enumerate(enriched_jobs):
            if isinstance(result, Job):
                final_jobs.append(result)
            elif isinstance(result, Exception):
                logger.error(f"Unexpected exception for company {i+1}, keeping job anyway: {result}")
                if i < len(jobs):
                    final_jobs.append(jobs[i])
        
        logger.info(f"Parallel company scraping complete: {len(final_jobs)}/{len(jobs)} jobs returned")
        return final_jobs

    
    
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
            job_items = await self.page.locator('li[data-occludable-job-id]').all()
            logger.info(f"Found {len(job_items)} job items in list")
            
            job_items = job_items[:limit]
            
            import asyncio
            tasks = []
            
            for idx, job_item in enumerate(job_items):
                try:
                    job_id = await job_item.get_attribute('data-occludable-job-id')
                    logger.debug(f"Processing job {idx + 1}: ID {job_id}")
                    
                    await job_item.click()
                    await self.wait_and_focus(0.2)
                    
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

                if company_url:
                    company_url = company_url.split('?')[0].rstrip('/')
                    
                    # Remove /life suffix from company URLs
                    if company_url.endswith('/life'):
                        company_url = company_url[:-5]
                    
                    logger.debug(f"Cleaned company URL: {company_url}")
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
        Extract job URLs from search results with optimized scrolling.
        
        Args:
            limit: Maximum number of URLs to extract
            
        Returns:
            List of job posting URLs
        """
        job_urls = []
        seen_urls = set()
        
        try:
            logger.info(f"Fast extraction: Getting {limit} job URLs...")
            
            # Wait extra long for initial content to fully render with links
            logger.info("Waiting for all visible job items to fully render with links...")
            await asyncio.sleep(5.0)
            
            job_items = await self.page.locator('li[data-occludable-job-id]').all()
            logger.info(f"Found {len(job_items)} jobs initially visible")
            
            # Trigger rendering by scrolling slightly within the container
            try:
                await self.page.evaluate('''() => {
                    const jobItems = document.querySelectorAll('li[data-occludable-job-id]');
                    if (jobItems.length > 0) {
                        let container = jobItems[0].closest('ul');
                        if (!container) {
                            const selectors = ['div.jobs-search-results-list', 'div[class*="scaffold-layout__list"]'];
                            for (const sel of selectors) {
                                container = document.querySelector(sel);
                                if (container) break;
                            }
                        }
                        if (container && (container.scrollHeight > container.clientHeight)) {
                            container.scrollBy({ top: 100, behavior: 'auto' });
                            setTimeout(() => container.scrollBy({ top: -100, behavior: 'auto' }), 200);
                        }
                    }
                }''')
                await asyncio.sleep(1.5)
            except:
                pass
            
            try:
                urls_js = await self.page.evaluate('''() => {
                    const items = document.querySelectorAll('li[data-occludable-job-id]');
                    const urls = [];
                    items.forEach(item => {
                        const link = item.querySelector('a[href*="/jobs/view/"]');
                        if (link && link.href) {
                            const cleanUrl = link.href.split('?')[0];
                            urls.push(cleanUrl);
                        }
                    });
                    return urls;
                }''')
                
                for url in urls_js:
                    if url not in seen_urls and len(job_urls) < limit:
                        job_urls.append(url)
                        seen_urls.add(url)
                
                logger.info(f"Extracted {len(job_urls)} URLs from visible items")
            except Exception as e:
                logger.debug(f"JS extraction failed, using fallback: {e}")
            
            if len(job_urls) < limit:
                logger.info(f"Need {limit - len(job_urls)} more URLs, scrolling the job list container...")
                logger.info("Waiting for lazy-loaded content to appear...")
                
                await asyncio.sleep(2.0)
                
                max_scrolls = 50 
                no_new_urls_count = 0
                previous_url_count = len(job_urls)
                
                for scroll_attempt in range(max_scrolls):
                    if len(job_urls) >= limit:
                        logger.info(f"Reached target: {len(job_urls)}/{limit} URLs")
                        break
                    
                    try:
                        scroll_result = await self.page.evaluate('''() => {
                            // Try multiple selectors to find the job list container
                            let container = null;
                            
                            // Strategy 1: Find UL containing job items
                            const jobItems = document.querySelectorAll('li[data-occludable-job-id]');
                            if (jobItems.length > 0) {
                                container = jobItems[0].closest('ul');
                            }
                            
                            // Strategy 2: Find scrollable parent of the UL
                            if (container) {
                                let el = container;
                                while (el && el !== document.body) {
                                    const style = window.getComputedStyle(el);
                                    if (style.overflowY === 'auto' || style.overflowY === 'scroll') {
                                        container = el;
                                        break;
                                    }
                                    el = el.parentElement;
                                }
                            }
                            
                            // Strategy 3: Try common class patterns if still not found
                            if (!container || container.tagName === 'UL') {
                                const selectors = [
                                    'div.jobs-search-results-list',
                                    'div[class*="scaffold-layout__list"]',
                                    'div.scaffold-layout__list-container'
                                ];
                                
                                for (const selector of selectors) {
                                    const elem = document.querySelector(selector);
                                    if (elem) {
                                        container = elem;
                                        break;
                                    }
                                }
                            }
                            
                            if (container) {
                                // Scroll the container incrementally
                                const scrollHeight = container.scrollHeight;
                                const currentScroll = container.scrollTop;
                                const clientHeight = container.clientHeight;
                                
                                // Scroll by 1 viewport at a time for better loading
                                container.scrollBy({ top: clientHeight, behavior: 'auto' });
                                
                                const newScroll = container.scrollTop;
                                const scrolled = newScroll > currentScroll;
                                
                                // More conservative: only consider end if we haven't scrolled at all
                                const nearBottom = (newScroll + clientHeight + 300) >= scrollHeight;
                                
                                return {
                                    success: true,
                                    scrolled: scrolled,
                                    scrollTop: newScroll,
                                    scrollHeight: scrollHeight,
                                    clientHeight: clientHeight,
                                    nearBottom: nearBottom,
                                    selector: container.tagName + '.' + Array.from(container.classList).slice(0, 2).join('.')
                                };
                            }
                            
                            return { success: false, error: 'Container not found' };
                        }''')
                        
                        if scroll_result.get('success'):
                            if scroll_attempt == 0:
                                logger.info(f"Found scrollable container: {scroll_result.get('selector', 'unknown')}")
                            
                            scrolled = scroll_result.get('scrolled', False)
                            nearBottom = scroll_result.get('nearBottom', False)
                            
                            if not scrolled:
                                logger.debug("Could not scroll further")
                        else:
                            logger.warning(f"Could not find job list container: {scroll_result.get('error')}")
                        
                        logger.debug(f"Scroll {scroll_attempt + 1}: Waiting for page to load new content...")
                        await asyncio.sleep(4.0)
                        
                    except Exception as e:
                        logger.debug(f"Scroll error: {e}")
                    
                    try:
                        new_urls = await self.page.evaluate('''() => {
                            const items = document.querySelectorAll('li[data-occludable-job-id]');
                            const urls = [];
                            items.forEach(item => {
                                const link = item.querySelector('a[href*="/jobs/view/"]');
                                if (link && link.href) {
                                    const cleanUrl = link.href.split('?')[0];
                                    urls.push(cleanUrl);
                                }
                            });
                            return urls;
                        }''')
                        
                        for url in new_urls:
                            if url not in seen_urls and len(job_urls) < limit:
                                job_urls.append(url)
                                seen_urls.add(url)
                        
                        if len(job_urls) == previous_url_count:
                            no_new_urls_count += 1
                            logger.debug(f"No new URLs (count: {no_new_urls_count}), current: {len(job_urls)}/{limit}")
                            if no_new_urls_count >= max_scrolls:
                                logger.info(f"No new URLs after {no_new_urls_count} consecutive scrolls, stopping")
                                break
                        else:
                            no_new_urls_count = 0
                            previous_url_count = len(job_urls)
                            logger.info(f"Progress: {len(job_urls)}/{limit} URLs extracted (scroll {scroll_attempt + 1})")
                        
                    except Exception as e:
                        logger.debug(f"URL extraction error: {e}")
                        break
            
            logger.info(f"Successfully extracted {len(job_urls)} unique job URLs")
        
        except Exception as e:
            logger.warning(f"Error extracting job URLs: {e}")
        
        return job_urls
