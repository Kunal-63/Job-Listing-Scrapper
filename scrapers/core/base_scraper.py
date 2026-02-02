#!/usr/bin/env python3
"""
Abstract Base Classes for Multi-Platform Job Scraping

Defines the interface that all platform-specific scrapers must implement.
This ensures consistency across LinkedIn, Indeed, Glassdoor, and other platforms.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from playwright.async_api import Page, BrowserContext

from .data_models import JobData, CompanyData, SearchConfig, ScraperResult


class BasePlatformScraper(ABC):
    """
    Abstract base class for platform-specific scrapers.
    
    Each platform (LinkedIn, Indeed, Glassdoor, etc.) should implement this interface.
    """
    
    def __init__(self, platform_name: str, config: Optional[Dict[str, Any]] = None):
        """
        Initialize platform scraper.
        
        Args:
            platform_name: Name of the platform (e.g., 'linkedin', 'indeed')
            config: Platform-specific configuration
        """
        self.platform_name = platform_name
        self.config = config or {}
        self.session_initialized = False
    
    @abstractmethod
    async def initialize_session(self, context: BrowserContext) -> bool:
        """
        Initialize session/authentication for the platform.
        
        Args:
            context: Playwright browser context
            
        Returns:
            True if session initialized successfully
        """
        pass
    
    @abstractmethod
    async def search_jobs(
        self,
        page: Page,
        search_config: SearchConfig,
        limit: int = 25
    ) -> List[str]:
        """
        Search for jobs and extract job URLs.
        
        Args:
            page: Playwright page object
            search_config: Search configuration
            limit: Maximum number of job URLs to extract
            
        Returns:
            List of job URLs
        """
        pass
    
    @abstractmethod
    async def scrape_job_details(self, page: Page, job_url: str) -> Optional[JobData]:
        """
        Scrape detailed information from a job posting.
        
        Args:
            page: Playwright page object
            job_url: URL of the job posting
            
        Returns:
            JobData object if successful, None otherwise
        """
        pass
    
    @abstractmethod
    async def scrape_company_details(
        self,
        page: Page,
        company_url: str
    ) -> Optional[CompanyData]:
        """
        Scrape company information.
        
        Args:
            page: Playwright page object
            company_url: URL of the company page
            
        Returns:
            CompanyData object if successful, None otherwise
        """
        pass
    
    def supports_company_scraping(self) -> bool:
        """
        Check if this platform supports company detail scraping.
        
        Returns:
            True if company scraping is supported
        """
        return True
    
    def get_rate_limit(self) -> float:
        """
        Get rate limit for this platform (requests per second).
        
        Returns:
            Rate limit value
        """
        return self.config.get('rate_limit', 1.0)
    
    def requires_authentication(self) -> bool:
        """
        Check if this platform requires authentication.
        
        Returns:
            True if authentication is required
        """
        return self.config.get('requires_auth', False)


class BaseJobSearchScraper(ABC):
    """
    Abstract base class for job search scrapers.
    
    Handles extracting job URLs from search result pages.
    """
    
    def __init__(self, page: Page, platform_name: str):
        """
        Initialize job search scraper.
        
        Args:
            page: Playwright page object
            platform_name: Name of the platform
        """
        self.page = page
        self.platform_name = platform_name
    
    @abstractmethod
    async def extract_job_urls(self, limit: int = 25) -> List[str]:
        """
        Extract job URLs from the current search page.
        
        Args:
            limit: Maximum number of URLs to extract
            
        Returns:
            List of job URLs
        """
        pass
    
    @abstractmethod
    async def scroll_to_load_more(self) -> bool:
        """
        Scroll the page to load more job listings.
        
        Returns:
            True if more content was loaded
        """
        pass
    
    @abstractmethod
    async def get_total_results_count(self) -> Optional[int]:
        """
        Get the total number of search results.
        
        Returns:
            Total count if available, None otherwise
        """
        pass


class BaseJobDetailScraper(ABC):
    """
    Abstract base class for job detail scrapers.
    
    Handles extracting detailed information from individual job postings.
    """
    
    def __init__(self, page: Page, platform_name: str):
        """
        Initialize job detail scraper.
        
        Args:
            page: Playwright page object
            platform_name: Name of the platform
        """
        self.page = page
        self.platform_name = platform_name
    
    @abstractmethod
    async def extract_job_title(self) -> str:
        """Extract job title."""
        pass
    
    @abstractmethod
    async def extract_job_description(self) -> str:
        """Extract job description."""
        pass
    
    @abstractmethod
    async def extract_company_name(self) -> str:
        """Extract company name."""
        pass
    
    @abstractmethod
    async def extract_company_url(self) -> Optional[str]:
        """Extract company URL."""
        pass
    
    @abstractmethod
    async def extract_location(self) -> str:
        """Extract job location."""
        pass
    
    @abstractmethod
    async def extract_posted_date(self) -> str:
        """Extract posted date."""
        pass
    
    async def extract_applicant_count(self) -> Optional[str]:
        """
        Extract applicant count (optional, not all platforms have this).
        
        Returns:
            Applicant count if available
        """
        return None
    
    async def extract_salary(self) -> Optional[str]:
        """
        Extract salary information (optional).
        
        Returns:
            Salary info if available
        """
        return None


class BaseCompanyDetailScraper(ABC):
    """
    Abstract base class for company detail scrapers.
    
    Handles extracting company information from company pages.
    """
    
    def __init__(self, page: Page, platform_name: str):
        """
        Initialize company detail scraper.
        
        Args:
            page: Playwright page object
            platform_name: Name of the platform
        """
        self.page = page
        self.platform_name = platform_name
    
    @abstractmethod
    async def extract_company_name(self) -> str:
        """Extract company name."""
        pass
    
    @abstractmethod
    async def extract_company_overview(self) -> str:
        """Extract company overview/description."""
        pass
    
    async def extract_company_industry(self) -> str:
        """Extract company industry."""
        return ""
    
    async def extract_company_size(self) -> str:
        """Extract company size."""
        return ""
    
    async def extract_company_headquarters(self) -> str:
        """Extract company headquarters location."""
        return ""
    
    async def extract_company_founded(self) -> str:
        """Extract year company was founded."""
        return ""
    
    async def extract_company_website(self) -> str:
        """Extract company website URL."""
        return ""
