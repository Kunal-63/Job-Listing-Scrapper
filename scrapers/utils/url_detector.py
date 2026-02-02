#!/usr/bin/env python3
"""
URL Platform Detector

Auto-detects which platform a job URL belongs to based on domain.
"""

import re
from typing import Optional
from urllib.parse import urlparse


def detect_platform(url: str) -> Optional[str]:
    """
    Detect platform from job URL.
    
    Args:
        url: Job or search URL
        
    Returns:
        Platform name (lowercase) if detected, None otherwise
    """
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        # Remove www. prefix
        domain = re.sub(r'^www\.', '', domain)
        
        # Platform detection
        if 'linkedin.com' in domain:
            return 'linkedin'
        elif 'indeed.com' in domain:
            return 'indeed'
        elif 'glassdoor.com' in domain or 'glassdoor.co' in domain:
            return 'glassdoor'
        elif 'monster.com' in domain:
            return 'monster'
        elif 'ziprecruiter.com' in domain:
            return 'ziprecruiter'
        elif 'dice.com' in domain:
            return 'dice'
        elif 'careerbuilder.com' in domain:
            return 'careerbuilder'
        
        return None
        
    except Exception:
        return None


def is_job_url(url: str, platform: Optional[str] = None) -> bool:
    """
    Check if URL is a job posting URL.
    
    Args:
        url: URL to check
        platform: Optional platform name to check against
        
    Returns:
        True if URL appears to be a job posting
    """
    if platform is None:
        platform = detect_platform(url)
    
    if platform is None:
        return False
    
    url_lower = url.lower()
    
    # Platform-specific job URL patterns
    patterns = {
        'linkedin': r'/jobs/view/',
        'indeed': r'/viewjob|/rc/clk',
        'glassdoor': r'/job-listing/',
        'monster': r'/job-opening/',
        'ziprecruiter': r'/jobs/',
    }
    
    pattern = patterns.get(platform)
    if pattern:
        return bool(re.search(pattern, url_lower))
    
    return False


def is_search_url(url: str, platform: Optional[str] = None) -> bool:
    """
    Check if URL is a job search URL.
    
    Args:
        url: URL to check
        platform: Optional platform name to check against
        
    Returns:
        True if URL appears to be a job search page
    """
    if platform is None:
        platform = detect_platform(url)
    
    if platform is None:
        return False
    
    url_lower = url.lower()
    
    # Platform-specific search URL patterns
    patterns = {
        'linkedin': r'/jobs/search',
        'indeed': r'/jobs\?',
        'glassdoor': r'/job/jobs\.htm',
        'monster': r'/jobs/search',
        'ziprecruiter': r'/jobs-search',
    }
    
    pattern = patterns.get(platform)
    if pattern:
        return bool(re.search(pattern, url_lower))
    
    return False


def normalize_url(url: str) -> str:
    """
    Normalize URL by removing tracking parameters and fragments.
    
    Args:
        url: URL to normalize
        
    Returns:
        Normalized URL
    """
    try:
        parsed = urlparse(url)
        
        # Remove fragment
        url_without_fragment = url.split('#')[0]
        
        # Remove common tracking parameters
        tracking_params = [
            'utm_source', 'utm_medium', 'utm_campaign', 'utm_content',
            'utm_term', 'ref', 'refid', 'trackingid', 'trk'
        ]
        
        # For now, just return URL without fragment
        # Full query param filtering can be added if needed
        return url_without_fragment
        
    except Exception:
        return url
