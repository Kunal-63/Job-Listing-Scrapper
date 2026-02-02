"""
Common scraping utilities for all platforms.

Provides reusable helper functions for web scraping tasks.
"""

import asyncio
import logging
from typing import Optional, Callable, Any
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)


async def scroll_to_bottom(page: Page, pause_time: float = 1.0, max_scrolls: int = 10) -> None:
    """
    Scroll to bottom of page with pauses.
    
    Args:
        page: Playwright page object
        pause_time: Time to pause between scrolls
        max_scrolls: Maximum number of scroll attempts
    """
    for _ in range(max_scrolls):
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(pause_time)


async def scroll_to_half(page: Page) -> None:
    """Scroll to middle of page."""
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")


async def click_see_more_buttons(page: Page, max_attempts: int = 10) -> int:
    """
    Click all 'Show more' / 'See more' buttons.
    
    Args:
        page: Playwright page object
        max_attempts: Maximum number of buttons to click
        
    Returns:
        Number of buttons clicked
    """
    clicked = 0
    selectors = [
        'button:has-text("Show more")',
        'button:has-text("See more")',
        'button:has-text("show all")',
        '.show-more-less-html__button'
    ]
    
    for _ in range(max_attempts):
        found = False
        for selector in selectors:
            try:
                button = page.locator(selector).first
                if await button.is_visible(timeout=1000):
                    await button.click()
                    clicked += 1
                    found = True
                    await asyncio.sleep(0.5)
                    break
            except:
                continue
        
        if not found:
            break
    
    return clicked


async def handle_modal_close(page: Page) -> bool:
    """
    Close any popup modals.
    
    Args:
        page: Playwright page object
        
    Returns:
        True if a modal was closed
    """
    close_selectors = [
        'button[aria-label="Dismiss"]',
        'button[aria-label="Close"]',
        '.artdeco-modal__dismiss',
        '[data-test-modal-close-btn]'
    ]
    
    for selector in close_selectors:
        try:
            button = page.locator(selector).first
            if await button.is_visible(timeout=1000):
                await button.click()
                await asyncio.sleep(0.3)
                return True
        except:
            continue
    
    return False


async def extract_text_safe(
    page: Page,
    selector: str,
    default: str = "",
    timeout: float = 2000
) -> str:
    """
    Safely extract text from element.
    
    Args:
        page: Playwright page object
        selector: CSS selector
        default: Default value if not found
        timeout: Timeout in milliseconds
        
    Returns:
        Extracted text or default
    """
    try:
        element = page.locator(selector).first
        text = await element.inner_text(timeout=timeout)
        return text.strip() if text else default
    except:
        return default


def retry_async(
    max_attempts: int = 3,
    backoff: float = 1.0,
    exceptions: tuple = (Exception,)
):
    """
    Decorator for retrying async functions.
    
    Args:
        max_attempts: Maximum number of attempts
        backoff: Backoff multiplier between attempts
        exceptions: Tuple of exceptions to catch
    """
    def decorator(func: Callable) -> Callable:
        async def wrapper(*args, **kwargs) -> Any:
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_attempts - 1:
                        raise
                    wait_time = backoff * (2 ** attempt)
                    logger.debug(f"Retry {attempt + 1}/{max_attempts} after {wait_time}s: {e}")
                    await asyncio.sleep(wait_time)
        return wrapper
    return decorator


async def is_logged_in(page: Page) -> bool:
    """
    Check if user is logged in to LinkedIn.
    
    Args:
        page: Playwright page object
        
    Returns:
        True if logged in
    """
    try:
        # Check for common logged-in indicators
        indicators = [
            '[data-control-name="nav.settings"]',
            '.global-nav__me',
            'button[aria-label*="View profile"]'
        ]
        
        for indicator in indicators:
            if await page.locator(indicator).count() > 0:
                return True
        
        # Check URL - if redirected to login page
        current_url = page.url
        if 'linkedin.com/login' in current_url or 'linkedin.com/uas/login' in current_url:
            return False
        
        return True
    except:
        return False


async def detect_rate_limit(page: Page) -> None:
    """
    Check for rate limiting indicators.
    
    Args:
        page: Playwright page object
        
    Raises:
        Exception: If rate limiting is detected
    """
    try:
        # Check for rate limit messages
        body_text = await page.inner_text('body', timeout=2000)
        rate_limit_indicators = [
            'too many requests',
            'rate limit',
            'try again later',
            'unusual activity'
        ]
        
        for indicator in rate_limit_indicators:
            if indicator in body_text.lower():
                raise Exception(f"Rate limit detected: {indicator}")
    except PlaywrightTimeoutError:
        pass


class ScrapingError(Exception):
    """Base exception for scraping errors."""
    pass


class AuthenticationError(ScrapingError):
    """Raised when authentication is required but not present."""
    pass


class RateLimitError(ScrapingError):
    """Raised when rate limiting is detected."""
    pass


class ProfileNotFoundError(ScrapingError):
    """Raised when a profile/page is not found."""
    pass
