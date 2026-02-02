"""
LinkedIn Authentication Helper

Handles LinkedIn login and session management for the scraper.
"""

import asyncio
import logging
from pathlib import Path
from playwright.async_api import async_playwright, BrowserContext
import json

logger = logging.getLogger(__name__)

# Session file location (use parent directory's session file)
SESSION_FILE = Path(__file__).parent.parent / "linkedin_session.json"


async def is_logged_in(context: BrowserContext) -> bool:
    """
    Check if user is logged in to LinkedIn.
    
    Args:
        context: Playwright browser context
        
    Returns:
        True if logged in
    """
    try:
        page = await context.new_page()
        await page.goto("https://www.linkedin.com/feed/", timeout=10000)
        await asyncio.sleep(2)
        
        # Check for logged-in indicators
        current_url = page.url
        is_logged_in = 'linkedin.com/feed' in current_url or 'linkedin.com/mynetwork' in current_url
        
        await page.close()
        return is_logged_in
    except Exception as e:
        logger.debug(f"Login check failed: {e}")
        return False


async def wait_for_manual_login(headless: bool = False) -> dict:
    """
    Open browser and wait for user to manually log in to LinkedIn.
    
    Args:
        headless: Whether to run in headless mode (should be False for login)
        
    Returns:
        Dictionary with cookies
    """
    logger.info("="*60)
    logger.info("LinkedIn Login Required")
    logger.info("="*60)
    logger.info("Opening browser for LinkedIn login...")
    logger.info("Please log in to LinkedIn in the browser window.")
    logger.info("The script will continue automatically once you're logged in.")
    logger.info("="*60)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context()
        page = await context.new_page()
        
        # Navigate to LinkedIn login
        await page.goto("https://www.linkedin.com/login")
        
        logger.info("Waiting for you to log in...")
        
        # Wait for successful login (check every 3 seconds)
        max_wait = 300  # 5 minutes
        elapsed = 0
        
        while elapsed < max_wait:
            await asyncio.sleep(3)
            elapsed += 3
            
            current_url = page.url
            
            # Check if logged in successfully
            if 'linkedin.com/feed' in current_url or 'linkedin.com/mynetwork' in current_url:
                logger.info("✓ Login successful!")
                break
            
            if elapsed % 30 == 0:
                logger.info(f"Still waiting... ({elapsed}s elapsed)")
        
        if elapsed >= max_wait:
            logger.error("Login timeout. Please try again.")
            await browser.close()
            return None
        
        # Get cookies
        cookies = await context.cookies()
        
        # Save session
        session_data = {"cookies": cookies}
        with open(SESSION_FILE, 'w') as f:
            json.dump(session_data, f, indent=2)
        
        logger.info(f"✓ Session saved to {SESSION_FILE}")
        
        await browser.close()
        
        return session_data


async def load_session(context: BrowserContext) -> bool:
    """
    Load LinkedIn session from file.
    
    Args:
        context: Playwright browser context
        
    Returns:
        True if session loaded successfully
    """
    try:
        if not SESSION_FILE.exists():
            logger.warning(f"Session file not found: {SESSION_FILE}")
            return False
        
        with open(SESSION_FILE, 'r') as f:
            session_data = json.load(f)
        
        if 'cookies' in session_data:
            await context.add_cookies(session_data['cookies'])
            logger.info("✓ LinkedIn session loaded")
            return True
        
        return False
    except Exception as e:
        logger.error(f"Error loading session: {e}")
        return False


async def ensure_linkedin_login(context: BrowserContext = None) -> BrowserContext:
    """
    Ensure user is logged in to LinkedIn.
    Opens browser for manual login if needed.
    
    Args:
        context: Existing browser context (optional)
        
    Returns:
        Browser context with valid LinkedIn session
    """
    # If no context provided, create one
    if context is None:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
    
    # Try to load existing session
    session_loaded = await load_session(context)
    
    if session_loaded:
        # Verify session is still valid
        if await is_logged_in(context):
            logger.info("✓ Already logged in to LinkedIn")
            return context
        else:
            logger.warning("Existing session expired")
    
    # Need to log in
    logger.info("LinkedIn login required")
    session_data = await wait_for_manual_login(headless=False)
    
    if session_data:
        # Reload the session into the context
        await context.add_cookies(session_data['cookies'])
        logger.info("✓ Login complete and session saved")
        return context
    else:
        raise Exception("LinkedIn login failed or timed out")


if __name__ == "__main__":
    # Test the login flow
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    async def test():
        await ensure_linkedin_login()
    
    asyncio.run(test())
