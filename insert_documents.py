
import json
import os
from pathlib import Path
from mongo_client import insert_job_link_from_json, get_client, get_db

def main():
    # Path to the JSON file
    json_file_path = Path(__file__).parent / "job_links.json"
    
    if not json_file_path.exists():
        print(f"Error: {json_file_path} not found.")
        return

    print(f"Reading from {json_file_path}...")
    
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            job_links = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        return

    if not isinstance(job_links, list):
        print("Error: JSON content must be a list of objects.")
        return

    print(f"Found {len(job_links)} job links to insert.")
    
    # Get database connection
    try:
        client = get_client()
        db = get_db(client)
        print("Connected to MongoDB.")
    except Exception as e:
        print(f"Error connecting to MongoDB: {e}")
        print("Make sure you have set the MONGO_URI environment variable or have a local MongoDB instance running.")
        return

    inserted_count = 0
    skipped_count = 0
    error_count = 0

    for link in job_links:
        try:
            # Extract fields
            engine_name = link.get("engineName")
            source_name = link.get("sourceName")
            platform = link.get("platform")
            url = link.get("url")

            if not all([engine_name, source_name, platform, url]):
                print(f"Skipping incomplete record: {link}")
                skipped_count += 1
                continue

            # Check for existing URL to avoid duplicates (optional but good practice)
            # The mongo_client.py schema sets a unique index on 'url', so duplicate inserts might fail or we should check first.
            # insert_job_link_from_json does a direct insert. If there's a unique index, it might raise DuplicateKeyError.
            
            try:
                insert_job_link_from_json(
                    engine_name=engine_name, 
                    source_name=source_name, 
                    platform=platform, 
                    url=url, 
                    db=db
                )
                inserted_count += 1
                if inserted_count % 10 == 0:
                    print(f"Inserted {inserted_count} docs...")
            except Exception as e:
                # Likely a duplicate key error if unique index exists
                if "E11000 duplicate key error" in str(e):
                    # print(f"Duplicate URL found: {url}")
                    skipped_count += 1
                else:
                    print(f"Error inserting {url}: {e}")
                    error_count += 1

        except Exception as e:
            print(f"Unexpected error processing link: {e}")
            error_count += 1

    print("-" * 30)
    print("Insertion Summary:")
    print(f"Total processed: {len(job_links)}")
    print(f"Successfully inserted: {inserted_count}")
    print(f"Skipped (likely duplicates): {skipped_count}")
    print(f"Errors: {error_count}")
    print("-" * 30)

if __name__ == "__main__":
    main()
