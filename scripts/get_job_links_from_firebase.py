#!/usr/bin/env python3
"""
Fetch Job Links from Firebase

Retrieves job links from Firebase and displays or exports them.

Usage:
    python get_job_links_from_firebase.py
    python get_job_links_from_firebase.py --status pending
    python get_job_links_from_firebase.py --export output.json
"""

import argparse
import json
import logging
from typing import Optional, List, Dict, Any

from firebase_manager import FirebaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def get_job_links(status: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Get job links from Firebase.
    
    Args:
        status: Filter by status (pending, scraped, failed, or None for all)
        limit: Maximum number of links to retrieve
        
    Returns:
        List of job link documents
    """
    manager = FirebaseManager()
    
    try:
        if status:
            # Get links with specific status
            query = manager.job_links_ref.where('status', '==', status)
            if limit:
                query = query.limit(limit)
            docs = query.get()
        else:
            # Get all links
            query = manager.job_links_ref
            if limit:
                query = query.limit(limit)
            docs = query.get()
        
        links = []
        for doc in docs:
            data = doc.to_dict()
            data['id'] = doc.id
            links.append(data)
        
        return links
        
    except Exception as e:
        logger.error(f"Error fetching job links: {e}")
        return []


def display_job_links(links: List[Dict[str, Any]]):
    """Display job links in a readable format."""
    if not links:
        print("No job links found.")
        return
    
    print(f"\nFound {len(links)} job links:\n")
    print("="*80)
    
    for idx, link in enumerate(links, 1):
        print(f"\n{idx}. {link.get('sourceName', 'Unknown Source')}")
        print(f"   URL: {link.get('url')}")
        print(f"   Status: {link.get('status', 'unknown')}")
        print(f"   Engine: {link.get('engineName', 'Unknown')}")
        print(f"   Created: {link.get('created_at', 'Unknown')}")
        if link.get('error'):
            print(f"   Error: {link.get('error')}")
    
    print("\n" + "="*80)


def export_job_links(links: List[Dict[str, Any]], output_file: str):
    """Export job links to JSON file."""
    try:
        # Convert to serializable format
        export_data = []
        for link in links:
            export_data.append({
                'id': link.get('id'),
                'engineName': link.get('engineName'),
                'sourceName': link.get('sourceName'),
                'platform': link.get('platform'),
                'url': link.get('url'),
                'status': link.get('status'),
                'created_at': str(link.get('created_at')) if link.get('created_at') else None,
                'scraped_at': str(link.get('scraped_at')) if link.get('scraped_at') else None,
                'error': link.get('error')
            })
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ Exported {len(links)} job links to {output_file}")
        
    except Exception as e:
        logger.error(f"Error exporting job links: {e}")


def get_statistics():
    """Get and display Firebase statistics."""
    manager = FirebaseManager()
    stats = manager.get_statistics()
    
    print("\nFirebase Statistics:")
    print("="*80)
    print(f"Total Job Links: {stats.get('total_job_links', 0)}")
    print(f"  - Pending: {stats.get('pending_job_links', 0)}")
    print(f"  - Scraped: {stats.get('scraped_job_links', 0)}")
    print(f"Total Job Details: {stats.get('total_job_details', 0)}")
    print(f"  - Pending Company: {stats.get('pending_company_jobs', 0)}")
    print(f"  - Complete: {stats.get('complete_jobs', 0)}")
    print(f"Total Companies: {stats.get('total_companies', 0)}")
    print("="*80)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Get job links from Firebase')
    parser.add_argument('--status', type=str, choices=['pending', 'scraped', 'failed'], 
                       help='Filter by status')
    parser.add_argument('--limit', type=int, help='Maximum number of links to retrieve')
    parser.add_argument('--export', type=str, help='Export to JSON file')
    parser.add_argument('--stats', action='store_true', help='Show statistics only')
    
    args = parser.parse_args()
    
    if args.stats:
        get_statistics()
        return
    
    # Get job links
    logger.info("Fetching job links from Firebase...")
    links = get_job_links(args.status, args.limit)
    
    if args.export:
        export_job_links(links, args.export)
    else:
        display_job_links(links)
    
    # Show statistics
    get_statistics()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
