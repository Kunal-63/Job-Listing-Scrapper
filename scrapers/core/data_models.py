#!/usr/bin/env python3
"""
Unified Data Models for Multi-Platform Job Scraping

Provides standardized data structures that work across all job platforms
(LinkedIn, Indeed, Glassdoor, etc.). Platform-specific fields are stored
in the extra_data dictionary.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List
from datetime import datetime


@dataclass
class JobData:
    """
    Standardized job information across all platforms.
    
    Attributes:
        platform: Platform name (linkedin, indeed, glassdoor, etc.)
        job_title: Job title/position
        job_description: Full job description
        job_url: URL to the job posting
        company_name: Company name
        company_url: URL to company page (if available)
        location: Job location
        posted_date: When the job was posted
        applicant_count: Number of applicants (if available)
        engine_name: Category/engine name for organization
        source_name: Source identifier
        extra_data: Platform-specific additional fields
    """
    platform: str
    job_title: str
    job_description: str
    job_url: str
    company_name: str
    location: str
    posted_date: str
    engine_name: str = ""
    source_name: str = ""
    company_url: Optional[str] = None
    applicant_count: Optional[str] = None
    company_data: Optional[Dict[str, Any]] = None  # Embedded company information
    extra_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        data = asdict(self)
        # Flatten extra_data into main dict for backward compatibility
        if self.extra_data:
            extra = data.pop('extra_data')
            data.update(extra)
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'JobData':
        """Create JobData from dictionary."""
        # Extract known fields
        known_fields = {
            'platform', 'job_title', 'job_description', 'job_url',
            'company_name', 'location', 'posted_date', 'engine_name',
            'source_name', 'company_url', 'applicant_count', 'company_data'
        }
        
        job_data = {k: v for k, v in data.items() if k in known_fields}
        extra_data = {k: v for k, v in data.items() if k not in known_fields}
        
        if extra_data:
            job_data['extra_data'] = extra_data
        
        return cls(**job_data)


@dataclass
class CompanyData:
    """
    Standardized company information across all platforms.
    
    Attributes:
        platform: Platform name
        company_name: Company name
        company_url: URL to company page
        company_overview: Company description/about
        company_industry: Industry/sector
        company_size: Number of employees
        company_headquarters: HQ location
        company_founded: Year founded
        company_website: Company website URL
        extra_data: Platform-specific fields (e.g., Glassdoor ratings)
    """
    platform: str
    company_name: str
    company_url: str
    company_overview: str = ""
    company_industry: str = ""
    company_size: str = ""
    company_headquarters: str = ""
    company_founded: str = ""
    company_website: str = ""
    extra_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        data = asdict(self)
        # Flatten extra_data
        if self.extra_data:
            extra = data.pop('extra_data')
            data.update(extra)
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CompanyData':
        """Create CompanyData from dictionary."""
        known_fields = {
            'platform', 'company_name', 'company_url', 'company_overview',
            'company_industry', 'company_size', 'company_headquarters',
            'company_founded', 'company_website'
        }
        
        company_data = {k: v for k, v in data.items() if k in known_fields}
        extra_data = {k: v for k, v in data.items() if k not in known_fields}
        
        if extra_data:
            company_data['extra_data'] = extra_data
        
        return cls(**company_data)


@dataclass
class SearchConfig:
    """
    Platform-agnostic search configuration.
    
    Attributes:
        platform: Platform to search on
        url: Search URL
        engine_name: Category/engine name
        source_name: Source identifier
        enabled: Whether this search is enabled
        max_results: Maximum results to fetch (optional)
        extra_params: Platform-specific search parameters
    """
    platform: str
    url: str
    engine_name: str = ""
    source_name: str = ""
    enabled: bool = True
    max_results: Optional[int] = None
    extra_params: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SearchConfig':
        """Create SearchConfig from dictionary (handles both camelCase and snake_case)."""
        # Convert camelCase to snake_case for backward compatibility
        converted = {}
        field_mapping = {
            'engineName': 'engine_name',
            'sourceName': 'source_name',
            'platform': 'platform',
            'url': 'url',
            'enabled': 'enabled'
        }
        
        for key, value in data.items():
            # Use mapping if available, otherwise use the key as-is
            new_key = field_mapping.get(key, key)
            converted[new_key] = value
        
        return cls(**converted)


@dataclass
class ScraperResult:
    """
    Result from a scraping operation.
    
    Attributes:
        success: Whether the operation succeeded
        data: The scraped data (JobData, CompanyData, or list of URLs)
        error: Error message if failed
        platform: Platform name
        url: URL that was scraped
    """
    success: bool
    platform: str
    url: str
    data: Any = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            'success': self.success,
            'platform': self.platform,
            'url': self.url,
            'error': self.error
        }
        
        if self.data is not None:
            if hasattr(self.data, 'to_dict'):
                result['data'] = self.data.to_dict()
            else:
                result['data'] = self.data
        
        return result
