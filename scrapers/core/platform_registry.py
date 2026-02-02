#!/usr/bin/env python3
"""
Platform Registry and Factory System

Manages registration and creation of platform-specific scrapers.
Provides a centralized way to get the appropriate scraper for each platform.
"""

import logging
from typing import Dict, Type, Optional, List
from pathlib import Path

from .base_scraper import BasePlatformScraper

logger = logging.getLogger(__name__)


class PlatformRegistry:
    """
    Singleton registry for all platform scrapers.
    
    Platforms register themselves on import, and can be retrieved by name.
    """
    
    _instance: Optional['PlatformRegistry'] = None
    _platforms: Dict[str, Type[BasePlatformScraper]] = {}
    
    def __new__(cls):
        """Ensure singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def register_platform(
        self,
        name: str,
        scraper_class: Type[BasePlatformScraper]
    ) -> None:
        """
        Register a platform scraper.
        
        Args:
            name: Platform name (e.g., 'linkedin', 'indeed')
            scraper_class: Scraper class that implements BasePlatformScraper
        """
        if not issubclass(scraper_class, BasePlatformScraper):
            raise TypeError(
                f"{scraper_class.__name__} must inherit from BasePlatformScraper"
            )
        
        name = name.lower()
        if name in self._platforms:
            logger.warning(f"Platform '{name}' already registered, overwriting")
        
        self._platforms[name] = scraper_class
        logger.info(f"Registered platform: {name}")
    
    def get_platform_class(self, name: str) -> Optional[Type[BasePlatformScraper]]:
        """
        Get platform scraper class by name.
        
        Args:
            name: Platform name
            
        Returns:
            Scraper class if found, None otherwise
        """
        name = name.lower()
        return self._platforms.get(name)
    
    def is_registered(self, name: str) -> bool:
        """
        Check if a platform is registered.
        
        Args:
            name: Platform name
            
        Returns:
            True if platform is registered
        """
        return name.lower() in self._platforms
    
    def list_platforms(self) -> List[str]:
        """
        Get list of all registered platforms.
        
        Returns:
            List of platform names
        """
        return sorted(self._platforms.keys())
    
    def unregister_platform(self, name: str) -> bool:
        """
        Unregister a platform.
        
        Args:
            name: Platform name
            
        Returns:
            True if platform was unregistered
        """
        name = name.lower()
        if name in self._platforms:
            del self._platforms[name]
            logger.info(f"Unregistered platform: {name}")
            return True
        return False
    
    def clear(self) -> None:
        """Clear all registered platforms (useful for testing)."""
        self._platforms.clear()
        logger.info("Cleared all registered platforms")


class PlatformFactory:
    """
    Factory for creating platform scraper instances.
    
    Uses the PlatformRegistry to get the appropriate scraper class
    and creates instances with the provided configuration.
    """
    
    def __init__(self):
        """Initialize platform factory."""
        self.registry = PlatformRegistry()
    
    def create_scraper(
        self,
        platform_name: str,
        config: Optional[Dict] = None
    ) -> Optional[BasePlatformScraper]:
        """
        Create a platform scraper instance.
        
        Args:
            platform_name: Name of the platform
            config: Platform-specific configuration
            
        Returns:
            Scraper instance if platform is registered, None otherwise
        """
        platform_name = platform_name.lower()
        scraper_class = self.registry.get_platform_class(platform_name)
        
        if scraper_class is None:
            logger.error(f"Platform '{platform_name}' not registered")
            logger.info(f"Available platforms: {self.registry.list_platforms()}")
            return None
        
        try:
            scraper = scraper_class(platform_name, config)
            logger.info(f"Created scraper for platform: {platform_name}")
            return scraper
        except Exception as e:
            logger.error(f"Error creating scraper for {platform_name}: {e}")
            return None
    
    def get_available_platforms(self) -> List[str]:
        """
        Get list of available platforms.
        
        Returns:
            List of platform names
        """
        return self.registry.list_platforms()
    
    def is_platform_available(self, platform_name: str) -> bool:
        """
        Check if a platform is available.
        
        Args:
            platform_name: Platform name
            
        Returns:
            True if platform is available
        """
        return self.registry.is_registered(platform_name)


def auto_discover_platforms(platforms_dir: Optional[Path] = None) -> int:
    """
    Auto-discover and import all platform modules.
    
    Scans the platforms directory and imports all platform modules,
    which should register themselves with the PlatformRegistry.
    
    Args:
        platforms_dir: Path to platforms directory (optional)
        
    Returns:
        Number of platforms discovered
    """
    if platforms_dir is None:
        # Default to scrapers/platforms directory
        platforms_dir = Path(__file__).parent.parent / "platforms"
    
    if not platforms_dir.exists():
        logger.warning(f"Platforms directory not found: {platforms_dir}")
        return 0
    
    discovered = 0
    
    # Import each platform module
    for platform_path in platforms_dir.iterdir():
        if not platform_path.is_dir():
            continue
        
        if platform_path.name.startswith('_'):
            continue
        
        platform_name = platform_path.name
        
        try:
            # Try to import the platform module
            module_name = f"scrapers.platforms.{platform_name}"
            __import__(module_name)
            discovered += 1
            logger.info(f"Discovered platform: {platform_name}")
        except ImportError as e:
            logger.warning(f"Could not import platform {platform_name}: {e}")
        except Exception as e:
            logger.error(f"Error loading platform {platform_name}: {e}")
    
    logger.info(f"Auto-discovered {discovered} platforms")
    return discovered


# Convenience function to register a platform
def register_platform(name: str):
    """
    Decorator to register a platform scraper.
    
    Usage:
        @register_platform('linkedin')
        class LinkedInScraper(BasePlatformScraper):
            ...
    
    Args:
        name: Platform name
    """
    def decorator(cls: Type[BasePlatformScraper]):
        PlatformRegistry().register_platform(name, cls)
        return cls
    return decorator
