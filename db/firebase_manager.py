#!/usr/bin/env python3
"""
Firebase Database Manager for LinkedIn Job Scraper

Handles all database operations for job scraping with Firebase Firestore.
"""

import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from firebase_admin import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from .firebase_client import get_firestore_db

logger = logging.getLogger(__name__)


class FirebaseManager:
    """Manages Firebase Firestore operations for job scraping."""
    
    def __init__(self):
        """Initialize Firebase manager."""
        self.db = get_firestore_db()
        
        # Collection references
        self.job_links_ref = self.db.collection('job_links')
        self.job_details_ref = self.db.collection('job_details')
        self.company_details_ref = self.db.collection('company_details')
        self.search_urls_ref = self.db.collection('search_urls')  # New collection for search configurations
    
    # ==================== Search URLs Operations ====================
    
    def get_search_urls(self, platform: Optional[str] = None, active_only: bool = True) -> List[Dict[str, Any]]:
        """
        Get search URL configurations from Firebase.
        
        Args:
            platform: Optional platform filter (e.g., 'linkedin', 'indeed')
            active_only: If True, only return active search URLs
            
        Returns:
            List of search URL documents
        """
        try:
            query = self.search_urls_ref
            
            # Filter by active status
            if active_only:
                query = query.where(filter=FieldFilter('active', '==', True))
            
            # Filter by platform
            if platform:
                query = query.where(filter=FieldFilter('platform', '==', platform))
            
            docs = query.get()
            search_urls = []
            
            for doc in docs:
                data = doc.to_dict()
                data['id'] = doc.id
                search_urls.append(data)
            
            logger.info(f"Retrieved {len(search_urls)} search URLs from Firebase")
            return search_urls
            
        except Exception as e:
            logger.error(f"Error getting search URLs: {e}")
            return []
    
    def add_search_url(self, url: str, engine_name: str, source_name: str, platform: str = "linkedin", active: bool = True) -> bool:
        """
        Add a search URL configuration to Firebase.
        
        Args:
            url: Search URL
            engine_name: Engine name
            source_name: Source/search name
            platform: Platform name (default: linkedin)
            active: Whether this search URL is active
            
        Returns:
            True if added successfully
        """
        try:
            doc_data = {
                'url': url,
                'engineName': engine_name,
                'sourceName': source_name,
                'platform': platform,
                'active': active,
                'created_at': firestore.SERVER_TIMESTAMP
            }
            
            self.search_urls_ref.add(doc_data)
            logger.info(f"Added search URL: {source_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding search URL: {e}")
            return False

    # ==================== Job Links Operations ====================
    
    def add_job_link(self, engine_name: str, source_name: str, platform: str, url: str) -> bool:
        """
        Add a job link to Firebase.
        
        Args:
            engine_name: Name of the scraping engine
            source_name: Source/search name
            platform: Platform name (e.g., "LinkedIn")
            url: Job URL
            
        Returns:
            True if added successfully, False otherwise
        """
        try:
            # Check if URL already exists
            existing = self.job_links_ref.where(filter=FieldFilter('url', '==', url)).limit(1).get()
            
            if len(list(existing)) > 0:
                logger.info(f"Job link already exists: {url}")
                return True
            
            # Add new job link
            doc_data = {
                'engineName': engine_name,
                'sourceName': source_name,
                'platform': platform,
                'url': url,
                'status': 'pending',
                'created_at': firestore.SERVER_TIMESTAMP,
                'scraped_at': None,
                'error': None
            }
            
            self.job_links_ref.add(doc_data)
            logger.info(f"Added job link: {url}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding job link: {e}")
            return False
    
    def add_job_links_bulk(self, links: List[Dict[str, str]]) -> int:
        """
        Add multiple job links at once using batch operations.
        
        Args:
            links: List of dicts with keys: engineName, sourceName, platform, url
            
        Returns:
            Number of links added
        """
        added_count = 0
        batch = self.db.batch()
        batch_size = 0
        max_batch_size = 500  # Firestore limit
        
        try:
            for link in links:
                # Check if exists
                existing = self.job_links_ref.where(filter=FieldFilter('url', '==', link['url'])).limit(1).get()
                if len(list(existing)) > 0:
                    continue
                
                # Add to batch
                doc_ref = self.job_links_ref.document()
                doc_data = {
                    'engineName': link.get('engineName', 'LinkedIn'),
                    'sourceName': link.get('sourceName', 'Job Search'),
                    'platform': link.get('platform', 'LinkedIn'),
                    'url': link['url'],
                    'status': 'pending',
                    'created_at': firestore.SERVER_TIMESTAMP,
                    'scraped_at': None,
                    'error': None
                }
                
                batch.set(doc_ref, doc_data)
                batch_size += 1
                added_count += 1
                
                # Commit batch if it reaches max size
                if batch_size >= max_batch_size:
                    batch.commit()
                    batch = self.db.batch()
                    batch_size = 0
            
            # Commit remaining items
            if batch_size > 0:
                batch.commit()
            
            logger.info(f"Added {added_count} job links in bulk")
            return added_count
            
        except Exception as e:
            logger.error(f"Error adding job links in bulk: {e}")
            return added_count
    
    def get_pending_job_links(self, platform: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get pending job links from Firebase.
        
        Args:
            platform: Optional platform filter (e.g., 'linkedin', 'indeed')
            limit: Maximum number of links to return
            
        Returns:
            List of job link documents
        """
        try:
            query = self.job_links_ref.where(filter=FieldFilter('status', '==', 'pending'))
            
            # Add platform filter if specified
            if platform:
                query = query.where(filter=FieldFilter('platform', '==', platform))
            
            if limit:
                query = query.limit(limit)
            
            docs = query.get()
            links = []
            
            for doc in docs:
                data = doc.to_dict()
                data['id'] = doc.id
                links.append(data)
            
            platform_str = f" for platform '{platform}'" if platform else ""
            logger.info(f"Retrieved {len(links)} pending job links{platform_str}")
            return links
            
        except Exception as e:
            logger.error(f"Error getting pending job links: {e}")
            return []
    
    def update_job_link_status(self, doc_id: str, status: str, error: Optional[str] = None):
        """
        Update job link status.
        
        Args:
            doc_id: Document ID
            status: New status (scraped, failed, etc.)
            error: Optional error message
        """
        try:
            update_data = {
                'status': status,
                'scraped_at': firestore.SERVER_TIMESTAMP
            }
            
            if error:
                update_data['error'] = error
            
            self.job_links_ref.document(doc_id).update(update_data)
            logger.info(f"Updated job link status to {status}")
            
        except Exception as e:
            logger.error(f"Error updating job link status: {e}")
    
    # ==================== Job Details Operations ====================
    
    def job_details_exist(self, job_url: str) -> bool:
        """
        Check if job details already exist for a given URL.
        Returns True if job details exist and status is not 'pending'.
        
        Args:
            job_url: Job URL to check
            
        Returns:
            True if job details exist (status != 'pending'), False otherwise
        """
        try:
            existing = self.job_details_ref.where('jobUrl', '==', job_url).limit(1).get()
            existing_docs = list(existing)
            
            if len(existing_docs) == 0:
                return False
            
            # Check if the job has been scraped (not in pending status)
            job_data = existing_docs[0].to_dict()
            status = job_data.get('status', '')
            
            # Only skip if status is not 'pending' (could be 'pending_company' or 'complete')
            return status != 'pending'
            
        except Exception as e:
            logger.error(f"Error checking if job details exist: {e}")
            return False
    
    def save_job_details(self, job_data: Dict[str, Any]) -> Optional[str]:
        """
        Save job details to Firebase.
        
        Args:
            job_data: Dictionary containing job information
            
        Returns:
            Document ID if saved successfully, None otherwise
        """
        try:
            # Check if job already exists by URL
            job_url = job_data.get('jobUrl')
            if job_url:
                existing = self.job_details_ref.where('jobUrl', '==', job_url).limit(1).get()
                existing_docs = list(existing)
                
                if existing_docs:
                    # Update existing
                    doc_id = existing_docs[0].id
                    job_data['updated_at'] = firestore.SERVER_TIMESTAMP
                    self.job_details_ref.document(doc_id).update(job_data)
                    logger.info(f"Updated job details: {job_data.get('jobTitle', 'Unknown')}")
                    return doc_id
            
            # Add new job details
            job_data['scraped_at'] = firestore.SERVER_TIMESTAMP
            job_data['updated_at'] = firestore.SERVER_TIMESTAMP
            
            # Status should be set by the caller (pending_company or complete)
            # Don't override it here
            
            doc_ref = self.job_details_ref.add(job_data)
            logger.info(f"Saved job details: {job_data.get('jobTitle', 'Unknown')}")
            return doc_ref[1].id
            
        except Exception as e:
            logger.error(f"Error saving job details: {e}")
            return None
    
    def get_jobs_pending_company(self, platform: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get jobs that need company details.
        
        Args:
            platform: Optional platform filter
            limit: Maximum number of jobs to return
            
        Returns:
            List of job documents
        """
        try:
            query = self.job_details_ref.where('status', '==', 'pending_company')
            
            # Add platform filter if specified
            if platform:
                query = query.where('platform', '==', platform)
            
            if limit:
                query = query.limit(limit)
            
            docs = query.get()
            jobs = []
            
            for doc in docs:
                data = doc.to_dict()
                data['id'] = doc.id
                jobs.append(data)
            
            platform_str = f" for platform '{platform}'" if platform else ""
            logger.info(f"Retrieved {len(jobs)} jobs pending company details{platform_str}")
            return jobs
            
        except Exception as e:
            logger.error(f"Error getting jobs pending company: {e}")
            return []
    
    def update_job_with_company_details(self, job_id: str, company_data: Dict[str, Any]):
        """
        Update job with company details.
        
        Args:
            job_id: Job document ID
            company_data: Company information to add
        """
        try:
            update_data = {
                'companyOverview': company_data.get('companyOverview', ''),
                'companyIndustry': company_data.get('companyIndustry', ''),
                'companySize': company_data.get('companySize', ''),
                'companyHeadquarters': company_data.get('companyHeadquarters', ''),
                'companyFounded': company_data.get('companyFounded', ''),
                'companyWebsite': company_data.get('companyWebsite', ''),
                'status': 'complete',
                'updated_at': firestore.SERVER_TIMESTAMP
            }
            
            self.job_details_ref.document(job_id).update(update_data)
            logger.info(f"Updated job with company details")
            
        except Exception as e:
            logger.error(f"Error updating job with company details: {e}")
    
    def update_job_link_status(self, link_id: str, status: str, error: Optional[str] = None):
        """
        Update job link status.
        
        Args:
            link_id: Job link document ID
            status: New status ('pending', 'scraped', 'failed')
            error: Optional error message
        """
        try:
            update_data = {
                'status': status,
                'updated_at': firestore.SERVER_TIMESTAMP
            }
            
            if status == 'scraped':
                update_data['scraped_at'] = firestore.SERVER_TIMESTAMP
            elif status == 'failed' and error:
                update_data['error'] = error
                update_data['failed_at'] = firestore.SERVER_TIMESTAMP
            
            self.job_links_ref.document(link_id).update(update_data)
            logger.debug(f"Updated job link status to: {status}")
            
        except Exception as e:
            logger.error(f"Error updating job link status: {e}")
    
    def update_job_status(self, job_id: str, status: str):
        """
        Update job status.
        
        Args:
            job_id: Job document ID
            status: New status ('pending_company', 'complete')
        """
        try:
            update_data = {
                'status': status,
                'updated_at': firestore.SERVER_TIMESTAMP
            }
            
            self.job_details_ref.document(job_id).update(update_data)
            logger.debug(f"Updated job status to: {status}")
            
        except Exception as e:
            logger.error(f"Error updating job status: {e}")
    
    def update_job_with_company(self, job_id: str, company_data: Dict[str, Any]):
        """
        Update job with company details and mark as complete.
        
        Args:
            job_id: Job document ID
            company_data: Company information to add
        """
        try:
            update_data = {
                'company_overview': company_data.get('company_overview', ''),
                'company_industry': company_data.get('company_industry', ''),
                'company_size': company_data.get('company_size', ''),
                'company_headquarters': company_data.get('company_headquarters', ''),
                'company_founded': company_data.get('company_founded', ''),
                'company_website': company_data.get('company_website', ''),
                'status': 'complete',
                'updated_at': firestore.SERVER_TIMESTAMP
            }
            
            self.job_details_ref.document(job_id).update(update_data)
            logger.info(f"Updated job with company details and marked as complete")
            
        except Exception as e:
            logger.error(f"Error updating job with company: {e}")
    
    # ==================== Company Details Operations ====================
    
    def get_company_details(self, company_url: str) -> Optional[Dict[str, Any]]:
        """
        Get cached company details by URL.
        
        Args:
            company_url: Company LinkedIn URL
            
        Returns:
            Company data if found, None otherwise
        """
        try:
            docs = self.company_details_ref.where('companyUrl', '==', company_url).limit(1).get()
            docs_list = list(docs)
            
            if docs_list:
                data = docs_list[0].to_dict()
                data['id'] = docs_list[0].id
                logger.info(f"Found cached company details for {company_url}")
                return data
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting company details: {e}")
            return None
    
    def save_company_details(self, company_data: Dict[str, Any]) -> Optional[str]:
        """
        Save company details to Firebase.
        
        Args:
            company_data: Company information
            
        Returns:
            Document ID if saved successfully, None otherwise
        """
        try:
            company_url = company_data.get('companyUrl')
            if not company_url:
                logger.warning("Cannot save company without URL")
                return None
            
            # Check if exists
            existing = self.get_company_details(company_url)
            
            if existing:
                # Update existing
                doc_id = existing['id']
                company_data['updated_at'] = firestore.SERVER_TIMESTAMP
                self.company_details_ref.document(doc_id).update(company_data)
                logger.info(f"Updated company details: {company_data.get('companyName', 'Unknown')}")
                return doc_id
            
            # Add new
            company_data['scraped_at'] = firestore.SERVER_TIMESTAMP
            doc_ref = self.company_details_ref.add(company_data)
            logger.info(f"Saved company details: {company_data.get('companyName', 'Unknown')}")
            return doc_ref[1].id
            
        except Exception as e:
            logger.error(f"Error saving company details: {e}")
            return None
    
    # ==================== Statistics ====================
    
    def get_statistics(self, platform: Optional[str] = None) -> Dict[str, int]:
        """
        Get database statistics.
        
        Args:
            platform: Optional platform filter
        
        Returns:
            Dictionary with counts
        """
        try:
            # Build queries with optional platform filter
            if platform:
                stats = {
                    'total_job_links': len(list(self.job_links_ref.where(filter=FieldFilter('platform', '==', platform)).get())),
                    'pending_job_links': len(list(self.job_links_ref.where(filter=FieldFilter('status', '==', 'pending')).where(filter=FieldFilter('platform', '==', platform)).get())),
                    'scraped_job_links': len(list(self.job_links_ref.where(filter=FieldFilter('status', '==', 'scraped')).where(filter=FieldFilter('platform', '==', platform)).get())),
                    'total_job_details': len(list(self.job_details_ref.where(filter=FieldFilter('platform', '==', platform)).get())),
                    'pending_company_jobs': len(list(self.job_details_ref.where(filter=FieldFilter('status', '==', 'pending_company')).where(filter=FieldFilter('platform', '==', platform)).get())),
                    'complete_jobs': len(list(self.job_details_ref.where(filter=FieldFilter('status', '==', 'complete')).where(filter=FieldFilter('platform', '==', platform)).get())),
                    'total_companies': len(list(self.company_details_ref.where(filter=FieldFilter('platform', '==', platform)).get()))
                }
            else:
                stats = {
                    'total_job_links': len(list(self.job_links_ref.get())),
                    'pending_job_links': len(list(self.job_links_ref.where(filter=FieldFilter('status', '==', 'pending')).get())),
                    'scraped_job_links': len(list(self.job_links_ref.where(filter=FieldFilter('status', '==', 'scraped')).get())),
                    'total_job_details': len(list(self.job_details_ref.get())),
                    'pending_company_jobs': len(list(self.job_details_ref.where(filter=FieldFilter('status', '==', 'pending_company')).get())),
                    'complete_jobs': len(list(self.job_details_ref.where(filter=FieldFilter('status', '==', 'complete')).get())),
                    'total_companies': len(list(self.company_details_ref.get()))
                }
            return stats
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {}


if __name__ == "__main__":
    # Test Firebase manager
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("Testing Firebase Manager...")
    
    try:
        manager = FirebaseManager()
        print("✓ Firebase Manager initialized")
        
        # Test adding a job link
        test_url = "https://www.linkedin.com/jobs/view/test123/"
        manager.add_job_link("LinkedIn", "Test Search", "LinkedIn", test_url)
        print("✓ Added test job link")
        
        # Get statistics
        stats = manager.get_statistics()
        print(f"✓ Database stats: {stats}")
        
        print("\nFirebase Manager is ready to use!")
        
    except Exception as e:
        print(f"✗ Error: {e}")
