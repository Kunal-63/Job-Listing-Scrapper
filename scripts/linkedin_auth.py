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


async def check_page_requires_login(page) -> bool:
    """
    Check if the current page indicates that login is required.
    This is useful for detecting session expiration during scraping.
    
    Args:
        page: Playwright page object
        
    Returns:
        True if login is required, False if still authenticated
    """
    try:
        current_url = page.url
        
        # Check if we're on a login page
        if 'linkedin.com/login' in current_url or 'linkedin.com/uas/login' in current_url:
            logger.warning("⚠ Detected redirect to login page - session expired")
            return True
        
        # Check if we're on an authwall page
        if 'authwall' in current_url.lower():
            logger.warning("⚠ Detected authwall - session expired")
            return True
        
        # Check for login form on the page
        login_form_selectors = [
            'form[action*="login"]',
            'input[name="session_key"]',
            'input[name="session_password"]',
            '#username',
            '#password'
        ]
        
        for selector in login_form_selectors:
            count = await page.locator(selector).count()
            if count > 0:
                logger.warning(f"⚠ Detected login form on page - session expired")
                return True
        
        # Check for "Sign in" text that appears when not logged in
        sign_in_text = await page.locator('text="Sign in"').count()
        if sign_in_text > 2:  # More than 2 instances likely means we're logged out
            logger.warning("⚠ Detected multiple 'Sign in' prompts - session may have expired")
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"Error checking if login required: {e}")
        return False


async def is_logged_in(context: BrowserContext) -> bool:
    """
    Check if user is logged in to LinkedIn by verifying job search access.
    
    Args:
        context: Playwright browser context
        
    Returns:
        True if logged in and can access job search
    """
    try:
        page = await context.new_page()
        
        # Try to access a job search page (requires login for full results)
        logger.debug("Verifying LinkedIn login status...")
        await page.goto("https://www.linkedin.com/jobs/search/?keywords=software", timeout=15000)
        await asyncio.sleep(3)
        
        current_url = page.url
        
        # Check if we're redirected to login page
        if 'linkedin.com/login' in current_url or 'linkedin.com/uas/login' in current_url:
            logger.warning("Redirected to login page - not logged in")
            await page.close()
            return False
        
        # Check for authenticated job search indicators
        try:
            # Look for elements that indicate we're logged in
            # 1. Check for various navigation patterns (LinkedIn changes their structure)
            nav_selectors = [
                'nav.global-nav',
                'nav[aria-label="Primary Navigation"]',
                'header.global-nav',
                'div.global-nav',
                'nav.scaffold-layout__nav',
                '[data-test-global-nav]'
            ]
            
            has_nav = False
            for selector in nav_selectors:
                count = await page.locator(selector).count()
                if count > 0:
                    has_nav = True
                    logger.debug(f"Found navigation with selector: {selector}")
                    break
            
            # 2. Check for job listings (authenticated view)
            has_jobs = await page.locator('li[data-occludable-job-id]').count() > 0
            
            # 3. Check we're not on a checkpoint/verification page
            is_checkpoint = 'checkpoint' in current_url.lower()
            
            # 4. Additional check: look for profile/user menu elements
            has_user_menu = False
            user_menu_selectors = [
                'button[aria-label*="View Profile"]',
                'img.global-nav__me-photo',
                '[data-control-name="nav.settings_signout"]',
                'a[href*="/mynetwork/"]'
            ]
            for selector in user_menu_selectors:
                count = await page.locator(selector).count()
                if count > 0:
                    has_user_menu = True
                    logger.debug(f"Found user menu with selector: {selector}")
                    break
            
            # More flexible verification:
            # - Must have jobs visible
            # - Must not be on checkpoint
            # - Should have either nav OR user menu (LinkedIn structure varies)
            if has_jobs and not is_checkpoint and (has_nav or has_user_menu):
                logger.info("✓ LinkedIn login verified - authenticated job search access confirmed")
                await page.close()
                return True
            elif has_jobs and not is_checkpoint:
                # Jobs are visible and not on checkpoint - likely logged in
                logger.info("✓ LinkedIn login verified - job listings accessible (relaxed check)")
                await page.close()
                return True
            else:
                logger.warning(f"Login check failed - nav:{has_nav}, jobs:{has_jobs}, user_menu:{has_user_menu}, checkpoint:{is_checkpoint}")
                await page.close()
                return False
                
        except Exception as e:
            logger.warning(f"Could not verify login elements: {e}")
            await page.close()
            return False
            
    except Exception as e:
        logger.error(f"Login check failed: {e}")
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
