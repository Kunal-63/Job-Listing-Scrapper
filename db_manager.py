#!/usr/bin/env python3
"""
MongoDB Database Manager for LinkedIn Job Scraper

Handles all database operations including:
- Job links storage and retrieval
- Job results storage
- Session management
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError   
import json

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages MongoDB connections and operations for job scraping."""
    
    def __init__(self, connection_string: str = "mongodb://localhost:27017/", database_name: str = "linkedin_scraper"):
        """
        Initialize database manager.
        
        Args:
            connection_string: MongoDB connection URI
            database_name: Name of the database to use
        """
        self.connection_string = connection_string
        self.database_name = database_name
        self.client: Optional[AsyncIOMotorClient] = None
        self.db = None
        
    async def connect(self) -> bool:
        """
        Connect to MongoDB.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            self.client = AsyncIOMotorClient(
                self.connection_string,
                serverSelectionTimeoutMS=5000
            )
            
            # Test connection
            await self.client.admin.command('ping')
            
            self.db = self.client[self.database_name]
            logger.info(f"Successfully connected to MongoDB: {self.database_name}")
            return True
            
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error connecting to MongoDB: {e}")
            return False
    
    async def disconnect(self):
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
            logger.info("Disconnected from MongoDB")
    
    async def test_connection(self) -> bool:
        """
        Test MongoDB connection.
        
        Returns:
            True if connection is active, False otherwise
        """
        try:
            if not self.client:
                return False
            await self.client.admin.command('ping')
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
    
    # Job Links Operations
    
    async def add_job_link(self, url: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Add a job link to the database.
        
        Args:
            url: Job URL to add
            metadata: Optional metadata about the job link
            
        Returns:
            True if added successfully, False otherwise
        """
        try:
            job_link = {
                "url": url,
                "status": "pending",  # pending, scraped, failed
                "added_at": datetime.utcnow(),
                "scraped_at": None,
                "metadata": metadata or {}
            }
            
            # Check if URL already exists
            existing = await self.db.job_links.find_one({"url": url})
            if existing:
                logger.info(f"Job link already exists: {url}")
                return True
            
            await self.db.job_links.insert_one(job_link)
            logger.info(f"Added job link: {url}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding job link: {e}")
            return False
    
    async def add_job_links_bulk(self, urls: List[str]) -> int:
        """
        Add multiple job links at once.
        
        Args:
            urls: List of job URLs to add
            
        Returns:
            Number of links added
        """
        added_count = 0
        for url in urls:
            if await self.add_job_link(url):
                added_count += 1
        return added_count
    
    async def get_pending_job_links(self, limit: Optional[int] = None) -> List[str]:
        """
        Get all pending job links.
        
        Args:
            limit: Maximum number of links to return
            
        Returns:
            List of pending job URLs
        """
        try:
            query = {} # Fetch all links regardless of status
            cursor = self.db.job_links.find(query)
            
            if limit:
                cursor = cursor.limit(limit)
            
            links = await cursor.to_list(length=None)
            urls = [link["url"] for link in links]
            
            logger.info(f"Retrieved {len(urls)} pending job links")
            return urls
            
        except Exception as e:
            logger.error(f"Error getting pending job links: {e}")
            return []
    
    async def get_all_job_links(self) -> List[Dict[str, Any]]:
        """
        Get all job links with their status.
        
        Returns:
            List of job link documents
        """
        try:
            links = await self.db.job_links.find().to_list(length=None)
            logger.info(f"Retrieved {len(links)} total job links")
            return links
        except Exception as e:
            logger.error(f"Error getting all job links: {e}")
            return []
    
    async def mark_job_link_scraped(self, url: str, success: bool = True):
        """
        Mark a job link as scraped.
        
        Args:
            url: Job URL
            success: Whether scraping was successful
        """
        try:
            status = "scraped" if success else "failed"
            await self.db.job_links.update_one(
                {"url": url},
                {
                    "$set": {
                        "status": status,
                        "scraped_at": datetime.utcnow()
                    }
                }
            )
            logger.info(f"Marked job link as {status}: {url}")
        except Exception as e:
            logger.error(f"Error marking job link: {e}")
    
    # Job Results Operations
    
    async def save_job_result(self, job_data: Dict[str, Any]) -> bool:
        """
        Save scraped job result to database.
        
        Args:
            job_data: Dictionary containing job information
            
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            # Add timestamp
            job_data["scraped_at"] = datetime.utcnow()
            
            # Check if job already exists (by URL)
            if "jobUrl" in job_data:
                existing = await self.db.job_scrapping_results.find_one({"jobUrl": job_data["jobUrl"]})
                if existing:
                    # Update existing record
                    await self.db.job_scrapping_results.update_one(
                        {"jobUrl": job_data["jobUrl"]},
                        {"$set": job_data}
                    )
                    logger.info(f"Updated job result: {job_data.get('jobTitle', 'Unknown')}")
                else:
                    # Insert new record
                    await self.db.job_scrapping_results.insert_one(job_data)
                    logger.info(f"Saved new job result: {job_data.get('jobTitle', 'Unknown')}")
                
                # Mark the job link as scraped
                if "jobUrl" in job_data:
                    await self.mark_job_link_scraped(job_data["jobUrl"], success=True)
                
                return True
            else:
                logger.warning("Job data missing jobUrl, cannot save")
                return False
                
        except Exception as e:
            logger.error(f"Error saving job result: {e}")
            return False
    
    async def save_job_results_bulk(self, jobs: List[Dict[str, Any]]) -> int:
        """
        Save multiple job results at once.
        
        Args:
            jobs: List of job data dictionaries
            
        Returns:
            Number of jobs saved
        """
        saved_count = 0
        for job in jobs:
            if await self.save_job_result(job):
                saved_count += 1
        return saved_count
    
    async def get_all_job_results(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get all scraped job results.
        
        Args:
            limit: Maximum number of results to return
            
        Returns:
            List of job result documents
        """
        try:
            cursor = self.db.job_scrapping_results.find().sort("scraped_at", -1)
            
            if limit:
                cursor = cursor.limit(limit)
            
            results = await cursor.to_list(length=None)
            logger.info(f"Retrieved {len(results)} job results")
            return results
            
        except Exception as e:
            logger.error(f"Error getting job results: {e}")
            return []
    
    async def get_job_stats(self) -> Dict[str, int]:
        """
        Get statistics about jobs in the database.
        
        Returns:
            Dictionary with job statistics
        """
        try:
            stats = {
                "total_links": await self.db.job_links.count_documents({}),
                "pending_links": await self.db.job_links.count_documents({"status": "pending"}),
                "scraped_links": await self.db.job_links.count_documents({"status": "scraped"}),
                "failed_links": await self.db.job_links.count_documents({"status": "failed"}),
                "total_results": await self.db.job_scrapping_results.count_documents({})
            }
            return stats
        except Exception as e:
            logger.error(f"Error getting job stats: {e}")
            return {
                "total_links": 0,
                "pending_links": 0,
                "scraped_links": 0,
                "failed_links": 0,
                "total_results": 0
            }
    
    async def clear_all_data(self):
        """Clear all data from the database (use with caution!)."""
        try:
            await self.db.job_links.delete_many({})
            await self.db.job_scrapping_results.delete_many({})
            logger.info("Cleared all data from database")
        except Exception as e:
            logger.error(f"Error clearing data: {e}")


# Helper function for testing
async def test_database():
    """Test database connection and operations."""
    db = DatabaseManager()
    
    print("Testing MongoDB connection...")
    if await db.connect():
        print("✓ Connected to MongoDB")
        
        # Test adding a job link
        test_url = "https://www.linkedin.com/jobs/view/test123/"
        await db.add_job_link(test_url, metadata={"test": True})
        print(f"✓ Added test job link")
        
        # Test getting pending links
        pending = await db.get_pending_job_links()
        print(f"✓ Found {len(pending)} pending job links")
        
        # Test stats
        stats = await db.get_job_stats()
        print(f"✓ Database stats: {stats}")
        
        await db.disconnect()
        print("✓ Disconnected from MongoDB")
    else:
        print("✗ Failed to connect to MongoDB")
        print("Make sure MongoDB is running on localhost:27017")


if __name__ == "__main__":
    # Run test
    asyncio.run(test_database())
