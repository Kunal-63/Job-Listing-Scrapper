"""
Database Layer for Multi-Platform Job Scraper

Handles Firebase Firestore operations.
"""

from .firebase_manager import FirebaseManager
from .firebase_client import get_firestore_db, initialize_firebase

__all__ = ['FirebaseManager', 'get_firestore_db', 'initialize_firebase']
