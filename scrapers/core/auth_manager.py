#!/usr/bin/env python3
"""
Authentication Manager for Multi-Platform Job Scraping

Handles authentication and session management for different platforms.
Each platform may have different auth requirements (cookies, API keys, etc.).
"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from playwright.async_api import BrowserContext

logger = logging.getLogger(__name__)


class AuthManager:
    """
    Manages authentication for different platforms.
    
    Supports:
    - Cookie-based sessions (LinkedIn)
    - API keys (Glassdoor)
    - No auth (Indeed)
    """
    
    def __init__(self, platform_name: str, config: Optional[Dict[str, Any]] = None):
        """
        Initialize auth manager for a platform.
        
        Args:
            platform_name: Name of the platform
            config: Platform-specific auth configuration
        """
        self.platform_name = platform_name
        self.config = config or {}
        self.session_file = self._get_session_file()
    
    def _get_session_file(self) -> Optional[Path]:
        """Get session file path for this platform."""
        session_filename = self.config.get('session_file')
        
        if not session_filename:
            # Default session file name
            session_filename = f"{self.platform_name}_session.json"
        
        # Store in AppData directory
        app_data_dir = Path.home() / "AppData" / "Local" / "JobScraper"
        app_data_dir.mkdir(parents=True, exist_ok=True)
        
        return app_data_dir / session_filename
    
    async def load_session(self, context: BrowserContext) -> bool:
        """
        Load session cookies into browser context.
        
        Args:
            context: Playwright browser context
            
        Returns:
            True if session loaded successfully
        """
        if not self.session_file or not self.session_file.exists():
            logger.info(f"No session file found for {self.platform_name}")
            return False
        
        try:
            with open(self.session_file, 'r') as f:
                session_data = json.load(f)
            
            if 'cookies' in session_data:
                await context.add_cookies(session_data['cookies'])
                logger.info(f"Loaded session for {self.platform_name}")
                return True
            else:
                logger.warning(f"No cookies in session file for {self.platform_name}")
                return False
                
        except Exception as e:
            logger.error(f"Error loading session for {self.platform_name}: {e}")
            return False
    
    async def save_session(self, context: BrowserContext) -> bool:
        """
        Save session cookies from browser context.
        
        Args:
            context: Playwright browser context
            
        Returns:
            True if session saved successfully
        """
        if not self.session_file:
            logger.warning(f"No session file configured for {self.platform_name}")
            return False
        
        try:
            cookies = await context.cookies()
            
            session_data = {
                'platform': self.platform_name,
                'cookies': cookies
            }
            
            with open(self.session_file, 'w') as f:
                json.dump(session_data, f, indent=2)
            
            logger.info(f"Saved session for {self.platform_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving session for {self.platform_name}: {e}")
            return False
    
    def get_api_key(self) -> Optional[str]:
        """
        Get API key for platforms that use API authentication.
        
        Returns:
            API key if configured
        """
        import os
        
        # Check config first
        api_key = self.config.get('api_key')
        if api_key:
            return api_key
        
        # Check environment variable
        env_var = self.config.get('api_key_env')
        if env_var:
            return os.getenv(env_var)
        
        return None
    
    def requires_auth(self) -> bool:
        """
        Check if this platform requires authentication.
        
        Returns:
            True if authentication is required
        """
        return self.config.get('requires_auth', False)
    
    def clear_session(self) -> bool:
        """
        Clear saved session.
        
        Returns:
            True if session was cleared
        """
        if self.session_file and self.session_file.exists():
            try:
                self.session_file.unlink()
                logger.info(f"Cleared session for {self.platform_name}")
                return True
            except Exception as e:
                logger.error(f"Error clearing session: {e}")
                return False
        return False
