"""
Company scraper for LinkedIn.

Extracts company information from LinkedIn company pages.
"""
import logging
import sys
from typing import Optional
from playwright.async_api import Page

from ..models.company import Company
from ..core.exceptions import ProfileNotFoundError
from ..callbacks import ProgressCallback, SilentCallback
from .base import BaseScraper

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


class CompanyScraper(BaseScraper):
    """
    Scraper for LinkedIn company pages.
    
    Example:
        async with BrowserManager() as browser:
            scraper = CompanyScraper(browser.page)
            company = await scraper.scrape("https://www.linkedin.com/company/microsoft/")
            print(company.to_json())
    """
    
    def __init__(self, page: Page, callback: Optional[ProgressCallback] = None):
        """
        Initialize company scraper.
        
        Args:
            page: Playwright page object
            callback: Optional progress callback
        """
        super().__init__(page, callback or SilentCallback())
    
    async def scrape(self, linkedin_url: str) -> Company:
        """
        Scrape a LinkedIn company page.
        
        Args:
            linkedin_url: URL of the LinkedIn company page
            
        Returns:
            Company object with scraped data
            
        Raises:
            ProfileNotFoundError: If company page not found
        """
        logger.info(f"Starting company scraping: {linkedin_url}")
        await self.callback.on_start("company", linkedin_url)
        
        # Navigate to company page with increased timeout to handle slow pages
        await self.navigate_and_wait(linkedin_url, wait_until='domcontentloaded', timeout=45000)
        await self.callback.on_progress("Navigated to company page", 10)
        
        await self.check_rate_limit()
        
        name = await self._get_name()
        await self.callback.on_progress(f"Got company name: {name}", 20)
        
        # Navigate to About section to get detailed company information
        about_section_url = linkedin_url.rstrip('/') + '/about/'
        logger.info(f"Navigating to About section: {about_section_url}")
        await self.navigate_and_wait(about_section_url, wait_until='domcontentloaded', timeout=45000)
        await self.callback.on_progress("Navigated to About section", 30)
        
        await self.wait_and_focus(1.0)
        
        about_us = await self._get_about()
        await self.callback.on_progress("Got about section", 40)
        
        overview = await self._get_overview()
        await self.callback.on_progress("Got overview details", 60)
        
        company = Company(
            linkedin_url=linkedin_url,
            name=name,
            about_us=about_us,
            **overview
        )
        
        await self.callback.on_progress("Scraping complete", 100)
        await self.callback.on_complete("company", company)
        
        logger.info(f"Successfully scraped company: {name}")
        return company
    
    async def _get_name(self) -> str:
        """Extract company name."""
        try:
            # Try main heading
            name_elem = self.page.locator('h1').first
            name = await name_elem.inner_text()
            return name.strip()
        except Exception as e:
            logger.warning(f"Error getting company name: {e}")
            return "Unknown Company"
    
    async def _get_about(self) -> Optional[str]:
        """Extract about/description section."""
        try:
            # Look for "About us" section
            sections = await self.page.locator('section').all()
            
            for section in sections:
                section_text = await section.inner_text()
                if 'About us' in section_text[:50]:
                    paragraphs = await section.locator('p').all()
                    if paragraphs:
                        about = await paragraphs[0].inner_text()
                        return about.strip()
            
            return None
        except Exception as e:
            logger.debug(f"Error getting about section: {e}")
            return None
    
    async def _get_overview(self) -> dict:
        """
        Extract company overview details from About section (website, industry, size, etc.).
        
        Returns dict with: website, phone, headquarters, founded, industry,
        company_type, company_size, specialties
        """
        overview = {
            "website": None,
            "phone": None,
            "headquarters": None,
            "founded": None,
            "industry": None,
            "company_type": None,
            "company_size": None,
            "specialties": None
        }
        
        try:
            # Parse dt/dd structure from About section
            logger.debug("Extracting company details from dt/dd structure...")
            
            dl_elements = await self.page.locator('dl').all()
            logger.debug(f"Found {len(dl_elements)} dl elements")
            
            for dl in dl_elements:
                dt_elements = await dl.locator('dt').all()
                
                for i, dt in enumerate(dt_elements):
                    try:
                        # Get the label from dt
                        label_text = await dt.inner_text()
                        label = label_text.strip().lower()
                        
                        # Get the corresponding dd value
                        # The dd immediately follows the dt in the dl
                        dds = await dl.locator('dd').all()
                        
                        if i < len(dds):
                            dd = dds[i]
                            value = await dd.inner_text()
                            value = value.strip() if value else None
                            
                            logger.debug(f"Found: {label} = {value}")
                            
                            # Map to overview fields
                            if 'website' in label or 'url' in label:
                                # Check if there's a link in the dd
                                link = await dd.locator('a').first.get_attribute('href')
                                if link:
                                    overview['website'] = link
                                else:
                                    overview['website'] = value
                                    
                            elif 'phone' in label:
                                overview['phone'] = value
                                
                            elif 'headquarters' in label or 'location' in label or 'address' in label:
                                overview['headquarters'] = value
                                
                            elif 'founded' in label or 'year' in label:
                                overview['founded'] = value
                                
                            elif 'industry' in label or 'industries' in label:
                                overview['industry'] = value
                                
                            elif 'company type' in label or 'type' in label:
                                if 'type' not in label or 'company' in label:
                                    overview['company_type'] = value
                                    
                            elif 'company size' in label or 'size' in label or 'employee' in label:
                                overview['company_size'] = value
                                
                            elif 'specialt' in label or 'expertise' in label:
                                overview['specialties'] = value
                    
                    except Exception as e:
                        logger.debug(f"Error parsing dt/dd pair {i}: {e}")
                        continue
            
            logger.info(f"Extracted overview: {[f'{k}={v}' for k,v in overview.items() if v]}")
            
        except Exception as e:
            logger.debug(f"Error extracting company overview: {e}")
        
        return overview
