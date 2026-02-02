"""
Multi-platform job scraper package.

Provides a flexible architecture for scraping job listings from multiple platforms.
"""

from .core.base_scraper import (
    BasePlatformScraper,
    BaseJobSearchScraper,
    BaseJobDetailScraper,
    BaseCompanyDetailScraper
)
from .core.platform_registry import PlatformRegistry, PlatformFactory, register_platform
from .core.data_models import JobData, CompanyData, SearchConfig, ScraperResult
from .core.auth_manager import AuthManager

__all__ = [
    'BasePlatformScraper',
    'BaseJobSearchScraper',
    'BaseJobDetailScraper',
    'BaseCompanyDetailScraper',
    'PlatformRegistry',
    'PlatformFactory',
    'register_platform',
    'JobData',
    'CompanyData',
    'SearchConfig',
    'ScraperResult',
    'AuthManager'
]
