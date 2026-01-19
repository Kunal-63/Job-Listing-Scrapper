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
        
        linkedin_url = linkedin_url.rstrip('/')
        if linkedin_url.endswith('/life'):
            linkedin_url = linkedin_url[:-5]
            logger.info(f"Cleaned company URL: {linkedin_url}")
        
        await self.callback.on_start("company", linkedin_url)
        
        await self.navigate_and_wait(linkedin_url, wait_until='domcontentloaded', timeout=45000)
        await self.callback.on_progress("Navigated to company page", 10)
        
        await self.check_rate_limit()
        
        name = await self._get_name()
        await self.callback.on_progress(f"Got company name: {name}", 20)
        
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
            # Look for the first <p> tag in the Overview section
            sections = await self.page.locator('section').all()
            logger.debug(f"Found {len(sections)} sections")
            
            for section in sections:
                # Check if this section contains "Overview" heading
                try:
                    h2_text = await section.locator('h2').first.inner_text()
                    logger.debug(f"Found section heading: {h2_text}")
                    
                    if 'overview' in h2_text.lower() or 'about' in h2_text.lower():
                        # Found the right section, get the first <p> tag
                        paragraphs = await section.locator('p').all()
                        if paragraphs:
                            about = await paragraphs[0].inner_text()
                            about = about.strip() if about else None
                            logger.info(f"Extracted about text: {about[:100] if about else 'None'}...")
                            return about
                except Exception as e:
                    logger.debug(f"Error checking section: {e}")
                    continue
            
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
            
            for dl_idx, dl in enumerate(dl_elements):
                try:
                    # Get all direct children (dt and dd) from this dl
                    all_children = await dl.locator(':scope > *').all()
                    
                    logger.debug(f"DL {dl_idx}: Found {len(all_children)} direct children")
                    
                    current_label = None
                    
                    for child in all_children:
                        tag_name = await child.evaluate("el => el.tagName.toLowerCase()")
                        
                        if tag_name == 'dt':
                            # New label - extract from h3 if present
                            h3_elem = child.locator('h3')
                            if await h3_elem.count() > 0:
                                current_label = await h3_elem.first.inner_text()
                            else:
                                current_label = await child.inner_text()
                            
                            current_label = current_label.strip().lower() if current_label else ""
                            logger.debug(f"Found label: {current_label}")
                        
                        elif tag_name == 'dd' and current_label:
                            # This dd belongs to the current_label
                            value = await child.inner_text()
                            value = value.strip() if value else None
                            
                            if not value or '70 associated members' in value or 'linkedin members' in value.lower():
                                # Skip empty values and "associated members" rows
                                logger.debug(f"Skipping dd value: {value[:50] if value else 'empty'}")
                                continue
                            
                            logger.debug(f"Found: {current_label} = {value[:50]}")
                            
                            # For website, extract href from link if present
                            if 'website' in current_label or 'url' in current_label:
                                link = child.locator('a')
                                if await link.count() > 0:
                                    href = await link.first.get_attribute('href')
                                    if href and not href.startswith('tel:'):
                                        overview['website'] = href
                                        logger.debug(f"Found website link: {href}")
                                else:
                                    overview['website'] = value
                            
                            # For phone, extract href from link if present
                            elif 'phone' in current_label:
                                link = child.locator('a')
                                if await link.count() > 0:
                                    href = await link.first.get_attribute('href')
                                    if href and href.startswith('tel:'):
                                        # Extract phone number from tel: link
                                        phone = href.replace('tel:', '')
                                        overview['phone'] = phone
                                        logger.debug(f"Found phone: {phone}")
                                else:
                                    overview['phone'] = value
                            
                            # Map other fields
                            elif 'headquarters' in current_label or 'location' in current_label or 'address' in current_label:
                                overview['headquarters'] = value
                                
                            elif 'founded' in current_label or 'year' in current_label:
                                overview['founded'] = value
                                
                            elif 'industry' in current_label or 'industries' in current_label:
                                overview['industry'] = value
                                
                            elif 'company type' in current_label or ('type' in current_label and 'company' in current_label):
                                overview['company_type'] = value
                                
                            elif 'company size' in current_label or 'size' in current_label or 'employee' in current_label:
                                overview['company_size'] = value
                                
                            elif 'specialt' in current_label or 'expertise' in current_label:
                                overview['specialties'] = value
                    
                except Exception as e:
                    logger.debug(f"Error processing dl {dl_idx}: {e}")
                    continue
            
            # Log extracted values
            extracted = {k: v for k, v in overview.items() if v}
            logger.info(f"Extracted company overview: {extracted}")
            
        except Exception as e:
            logger.debug(f"Error extracting company overview: {e}")
        
        return overview
