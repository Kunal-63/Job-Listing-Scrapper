"""Utility modules for the job scraper."""

from .url_detector import detect_platform, is_job_url, is_search_url, normalize_url
from .rate_limiter import RateLimiter, PlatformRateLimiter, get_global_rate_limiter
from .scraping_helpers import (
    scroll_to_bottom,
    scroll_to_half,
    click_see_more_buttons,
    handle_modal_close,
    extract_text_safe,
    retry_async,
    is_logged_in,
    detect_rate_limit,
    ScrapingError,
    AuthenticationError,
    RateLimitError,
    ProfileNotFoundError
)

__all__ = [
    'detect_platform',
    'is_job_url',
    'is_search_url',
    'normalize_url',
    'RateLimiter',
    'PlatformRateLimiter',
    'get_global_rate_limiter',
    'scroll_to_bottom',
    'scroll_to_half',
    'click_see_more_buttons',
    'handle_modal_close',
    'extract_text_safe',
    'retry_async',
    'is_logged_in',
    'detect_rate_limit',
    'ScrapingError',
    'AuthenticationError',
    'RateLimitError',
    'ProfileNotFoundError'
]
