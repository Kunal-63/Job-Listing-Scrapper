#!/usr/bin/env python3
"""
Firebase Client for LinkedIn Job Scraper

Handles Firebase Admin SDK initialization and provides Firestore database instance.
"""

import os
import logging
from pathlib import Path
from typing import Optional
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Global Firebase app instance
_firebase_app: Optional[firebase_admin.App] = None
_firestore_db = None


def get_credentials_path() -> str:
    """
    Get Firebase credentials file path from environment or default location.
    
    Returns:
        Path to Firebase credentials JSON file
    """
    # Check environment variable first
    creds_path = os.getenv('FIREBASE_CREDENTIALS_PATH')
    
    if creds_path and Path(creds_path).exists():
        return creds_path
    
    # Check default location in project root (parent of db folder)
    default_path = Path(__file__).parent.parent / "firebase-credentials.json"
    if default_path.exists():
        return str(default_path)
    
    raise FileNotFoundError(
        "Firebase credentials file not found. Please set FIREBASE_CREDENTIALS_PATH "
        "environment variable or place firebase-credentials.json in project root."
    )


def initialize_firebase() -> firebase_admin.App:
    """
    Initialize Firebase Admin SDK.
    
    Returns:
        Firebase app instance
        
    Raises:
        FileNotFoundError: If credentials file not found
        ValueError: If Firebase initialization fails
    """
    global _firebase_app
    
    if _firebase_app is not None:
        logger.info("Firebase already initialized")
        return _firebase_app
    
    try:
        creds_path = get_credentials_path()
        logger.info(f"Initializing Firebase with credentials from: {creds_path}")
        
        cred = credentials.Certificate(creds_path)
        _firebase_app = firebase_admin.initialize_app(cred)
        
        logger.info("Firebase initialized successfully")
        return _firebase_app
        
    except Exception as e:
        logger.error(f"Failed to initialize Firebase: {e}")
        raise ValueError(f"Firebase initialization failed: {e}")


def get_firestore_db():
    """
    Get Firestore database instance.
    
    Returns:
        Firestore client instance
    """
    global _firestore_db
    
    if _firestore_db is None:
        # Initialize Firebase if not already done
        if _firebase_app is None:
            initialize_firebase()
        
        _firestore_db = firestore.client()
        logger.info("Firestore client created")
    
    return _firestore_db


def test_connection() -> bool:
    """
    Test Firebase connection by attempting to access Firestore.
    
    Returns:
        True if connection successful, False otherwise
    """
    try:
        db = get_firestore_db()
        
        # Try to access a collection (this will create it if it doesn't exist)
        test_ref = db.collection('_connection_test').document('test')
        test_ref.set({'timestamp': firestore.SERVER_TIMESTAMP})
        
        # Read it back
        doc = test_ref.get()
        
        # Clean up
        test_ref.delete()
        
        if doc.exists:
            logger.info("Firebase connection test successful")
            return True
        else:
            logger.warning("Firebase connection test failed: document not found")
            return False
            
    except Exception as e:
        logger.error(f"Firebase connection test failed: {e}")
        return False


def delete_firebase_app():
    """Delete Firebase app instance (useful for testing)."""
    global _firebase_app, _firestore_db
    
    if _firebase_app is not None:
        firebase_admin.delete_app(_firebase_app)
        _firebase_app = None
        _firestore_db = None
        logger.info("Firebase app deleted")


if __name__ == "__main__":
    # Test Firebase connection when run directly
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("Testing Firebase connection...")
    
    try:
        initialize_firebase()
        print("✓ Firebase initialized successfully")
        
        if test_connection():
            print("✓ Firebase connection test passed")
            print("\nFirebase is ready to use!")
        else:
            print("✗ Firebase connection test failed")
            
    except Exception as e:
        print(f"✗ Error: {e}")
        print("\nPlease ensure:")
        print("1. firebase-credentials.json exists in project root")
        print("2. The credentials file is valid")
        print("3. Firebase project is properly configured")
