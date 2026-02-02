#!/usr/bin/env python3
"""
Rate Limiter for Platform-Specific Request Throttling

Ensures we don't exceed rate limits for different job platforms.
"""

import asyncio
import time
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Rate limiter for controlling request frequency.
    
    Uses token bucket algorithm to allow bursts while maintaining
    average rate limit.
    """
    
    def __init__(self, requests_per_second: float = 1.0, burst_size: Optional[int] = None):
        """
        Initialize rate limiter.
        
        Args:
            requests_per_second: Maximum requests per second
            burst_size: Maximum burst size (default: 2x rate)
        """
        self.rate = requests_per_second
        self.burst_size = burst_size or int(requests_per_second * 2)
        self.tokens = self.burst_size
        self.last_update = time.time()
        self.lock = asyncio.Lock()
    
    async def acquire(self) -> None:
        """
        Acquire permission to make a request.
        
        Blocks until a token is available.
        """
        async with self.lock:
            while self.tokens < 1:
                # Calculate time to wait for next token
                now = time.time()
                time_passed = now - self.last_update
                self.tokens = min(
                    self.burst_size,
                    self.tokens + time_passed * self.rate
                )
                self.last_update = now
                
                if self.tokens < 1:
                    wait_time = (1 - self.tokens) / self.rate
                    logger.debug(f"Rate limit reached, waiting {wait_time:.2f}s")
                    await asyncio.sleep(wait_time)
            
            # Consume a token
            self.tokens -= 1
    
    async def wait(self) -> None:
        """Alias for acquire() for backward compatibility."""
        await self.acquire()


class PlatformRateLimiter:
    """
    Manages rate limiters for multiple platforms.
    
    Each platform can have its own rate limit configuration.
    """
    
    def __init__(self):
        """Initialize platform rate limiter."""
        self.limiters: Dict[str, RateLimiter] = {}
    
    def set_rate_limit(
        self,
        platform: str,
        requests_per_second: float,
        burst_size: Optional[int] = None
    ) -> None:
        """
        Set rate limit for a platform.
        
        Args:
            platform: Platform name
            requests_per_second: Maximum requests per second
            burst_size: Maximum burst size
        """
        self.limiters[platform] = RateLimiter(requests_per_second, burst_size)
        logger.info(
            f"Set rate limit for {platform}: {requests_per_second} req/s"
        )
    
    def get_limiter(self, platform: str) -> Optional[RateLimiter]:
        """
        Get rate limiter for a platform.
        
        Args:
            platform: Platform name
            
        Returns:
            RateLimiter if configured, None otherwise
        """
        return self.limiters.get(platform.lower())
    
    async def acquire(self, platform: str) -> None:
        """
        Acquire permission to make a request for a platform.
        
        Args:
            platform: Platform name
        """
        limiter = self.get_limiter(platform)
        if limiter:
            await limiter.acquire()
    
    async def wait(self, platform: str) -> None:
        """
        Wait for rate limit (alias for acquire).
        
        Args:
            platform: Platform name
        """
        await self.acquire(platform)


# Global platform rate limiter instance
_global_rate_limiter: Optional[PlatformRateLimiter] = None


def get_global_rate_limiter() -> PlatformRateLimiter:
    """
    Get global platform rate limiter instance.
    
    Returns:
        Global PlatformRateLimiter instance
    """
    global _global_rate_limiter
    
    if _global_rate_limiter is None:
        _global_rate_limiter = PlatformRateLimiter()
        
        # Set default rate limits
        _global_rate_limiter.set_rate_limit('linkedin', 1.0)  # 1 req/s
        _global_rate_limiter.set_rate_limit('indeed', 2.0)    # 2 req/s
        _global_rate_limiter.set_rate_limit('glassdoor', 0.5) # 0.5 req/s
    
    return _global_rate_limiter
