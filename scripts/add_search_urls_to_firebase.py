import argparse
import json
import logging
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.firebase_manager import FirebaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def add_single_url(manager: FirebaseManager, url: str, name: str, platform: str = "linkedin", active: bool = True):
    """Add a single search URL to Firebase."""
    engine_name = platform.capitalize()
    
    if manager.add_search_url(url, engine_name, name, platform, active):
        logger.info(f"✓ Added: {name}")
        return True
    else:
        logger.error(f"✗ Failed to add: {name}")
        return False


def add_from_json(manager: FirebaseManager, json_file: str):
    """Add search URLs from a JSON file."""
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if not isinstance(data, list):
            data = [data]
        
        added = 0
        for item in data:
            url = item.get('url')
            source_name = item.get('sourceName', 'Unknown')
            engine_name = item.get('engineName', 'LinkedIn')
            platform = item.get('platform', 'linkedin').lower()
            active = item.get('active', True)
            
            if not url:
                logger.warning(f"Skipping item without URL: {item}")
                continue
            
            if manager.add_search_url(url, engine_name, source_name, platform, active):
                added += 1
                logger.info(f"✓ Added: {source_name}")
            else:
                logger.error(f"✗ Failed: {source_name}")
        
        logger.info(f"\nAdded {added}/{len(data)} search URLs")
        return added
        
    except Exception as e:
        logger.error(f"Error reading JSON file: {e}")
        return 0


def list_search_urls(manager: FirebaseManager, platform: str = None):
    """List all search URLs in Firebase."""
    search_urls = manager.get_search_urls(platform=platform, active_only=False)
    
    if not search_urls:
        print("\nNo search URLs found in Firebase.")
        return
    
    print(f"\nFound {len(search_urls)} search URLs:\n")
    print("="*80)
    
    for idx, url_config in enumerate(search_urls, 1):
        status = "✓ Active" if url_config.get('active', True) else "✗ Inactive"
        print(f"\n{idx}. {url_config.get('sourceName', 'Unknown')}")
        print(f"   Platform: {url_config.get('platform', 'unknown')}")
        print(f"   Status: {status}")
        print(f"   URL: {url_config.get('url', 'N/A')}")
    
    print("\n" + "="*80)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Add search URLs to Firebase')
    parser.add_argument('--url', type=str, help='Single search URL to add')
    parser.add_argument('--name', type=str, help='Name/description for the search URL')
    parser.add_argument('--platform', type=str, default='linkedin', help='Platform (default: linkedin)')
    parser.add_argument('--from-json', type=str, help='JSON file with search URLs')
    parser.add_argument('--list', action='store_true', help='List all search URLs in Firebase')
    parser.add_argument('--inactive', action='store_true', help='Mark URL as inactive')
    
    args = parser.parse_args()
    
    # Initialize Firebase manager
    try:
        manager = FirebaseManager()
        logger.info("Connected to Firebase")
    except Exception as e:
        logger.error(f"Failed to connect to Firebase: {e}")
        return
    
    # List search URLs
    if args.list:
        list_search_urls(manager, args.platform if args.platform != 'linkedin' else None)
        return
    
    # Add from JSON
    if args.from_json:
        json_path = Path(args.from_json)
        if not json_path.exists():
            logger.error(f"JSON file not found: {args.from_json}")
            return
        
        add_from_json(manager, args.from_json)
        return
    
    # Add single URL
    if args.url:
        if not args.name:
            logger.error("--name is required when adding a single URL")
            parser.print_help()
            return
        
        active = not args.inactive
        add_single_url(manager, args.url, args.name, args.platform, active)
        return
    
    # No action specified
    logger.error("No action specified. Use --url, --from-json, or --list")
    parser.print_help()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
