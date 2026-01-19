#!/usr/bin/env python3
"""
Quick test script to verify MongoDB connection and add sample job links.
Run this before using main.py to set up initial data.
"""

import asyncio
from db_manager import DatabaseManager


async def setup_database():
    """Set up database with sample job links."""
    print("=" * 60)
    print("LinkedIn Job Scraper - Database Setup")
    print("=" * 60)
    print()
    
    # Create database manager
    db = DatabaseManager()
    
    # Test connection
    print("📡 Testing MongoDB connection...")
    if await db.connect():
        print("✅ Connected to MongoDB successfully!")
        print()
    else:
        print("❌ Failed to connect to MongoDB")
        print("Make sure MongoDB is running on localhost:27017")
        print()
        print("To start MongoDB:")
        print("  - Windows: Start MongoDB service")
        print("  - Mac/Linux: mongod")
        return
    
    # Get current stats
    stats = await db.get_job_stats()
    print("📊 Current Database Statistics:")
    print(f"   Total job links: {stats['total_links']}")
    print(f"   Pending: {stats['pending_links']}")
    print(f"   Scraped: {stats['scraped_links']}")
    print(f"   Failed: {stats['failed_links']}")
    print(f"   Total results: {stats['total_results']}")
    print()
    
    # Ask if user wants to add sample links
    if stats['total_links'] == 0:
        print("📝 No job links found in database.")
        print("   Adding sample job links for testing...")
        print()
        
        # Sample LinkedIn job URLs (replace with real ones)
        sample_links = [
            "https://www.linkedin.com/jobs/search/?f_JT=F%2CP%2CC&f_TPR=r86400&f_WT=2&geoId=102713980&keywords=Product%20Designer&sortBy=DD",
            "https://www.linkedin.com/jobs/view/4099447907/",
            "https://www.linkedin.com/jobs/view/4099447908/",
            "https://www.linkedin.com/jobs/view/4099447909/",
            "https://www.linkedin.com/jobs/view/4099447910/",
        ]
        
        added = await db.add_job_links_bulk(sample_links)
        print(f"✅ Added {added} sample job links!")
        print()
        
        # Show updated stats
        stats = await db.get_job_stats()
        print("📊 Updated Statistics:")
        print(f"   Total job links: {stats['total_links']}")
        print(f"   Pending: {stats['pending_links']}")
        print()
    
    print("=" * 60)
    print("✅ Database setup complete!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("1. Run: python main.py")
    print("2. Log in to LinkedIn")
    print("3. Start scraping from the dashboard")
    print()
    
    await db.disconnect()


if __name__ == "__main__":
    asyncio.run(setup_database())
