
from typing import List, Optional, Dict, Any
import os
from pymongo import MongoClient, errors
from dotenv import load_dotenv


load_dotenv()


def get_mongo_uri() -> str:
    return os.environ.get("MONGO_URI", "mongodb://localhost:27017")


def get_db_name() -> str:
    return os.environ.get("MONGO_DB", "jobs_db")


def get_client() -> MongoClient:
    uri = get_mongo_uri()
    return MongoClient(uri)


def get_db(client: Optional[MongoClient] = None):
    if client is None:
        client = get_client()
    return client[get_db_name()]


def test_connection(uri: Optional[str] = None, timeout: float = 5.0):
    """Test a MongoDB connection string quickly.

    Returns (True, None) on success, or (False, error_message) on failure.
    """
    try:
        if uri is None:
            uri = get_mongo_uri()
        client = MongoClient(uri, serverSelectionTimeoutMS=int(timeout * 1000))
        # ping server
        client.admin.command('ping')
        return True, None
    except Exception as e:
        return False, str(e)


def set_mongo_uri(uri: str, persist: bool = False, env_path: str = '.env') -> None:
    """Set the MONGO_URI for the current process and optionally persist to a .env file.

    If `persist` is True the URI will be appended to `env_path` (simple append, not secure).
    """
    os.environ['MONGO_URI'] = uri
    if persist:
        try:
            with open(env_path, 'a', encoding='utf-8') as f:
                f.write(f"\nMONGO_URI={uri}\n")
        except Exception:
            # ignore file write errors
            pass


def create_collections_with_validators(db=None):
    """Create collections with optional JSON schema validators.

    If the collection already exists the function will leave it as-is.
    Validators are best-effort — some MongoDB servers may not support them.
    """
    if db is None:
        db = get_db()

    # job_links schema - Updated to match JSON structure
    job_links_validator = {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["engineName", "sourceName", "platform", "url"],
            "properties": {
                "engineName": {"bsonType": "string"},
                "sourceName": {"bsonType": "string"},
                "platform": {"bsonType": "string"},
                "url": {"bsonType": "string"},
                "status": {"bsonType": "string"},
                "created_at": {"bsonType": "date"},
                "scraped_at": {"bsonType": "date"}
            }
        }
    }

    # job_scrapping_results schema - Updated with all required fields
    job_results_validator = {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["enegName", "sourceName", "jobTitle", "companyName", "jobUrl"],
            "properties": {
                "enegName": {"bsonType": "string"},
                "sourceName": {"bsonType": "string"},
                "jobDescription": {"bsonType": "string"},
                "postedAt": {"bsonType": ["date", "string"]},
                "jobTitle": {"bsonType": "string"},
                "companyName": {"bsonType": "string"},
                "companyUrl": {"bsonType": "string"},
                "companyOverview": {"bsonType": "string"},
                "companyIndustry": {"bsonType": "string"},
                "companySize": {"bsonType": "string"},
                "companyHeadquarters": {"bsonType": "string"},
                "companyFounded": {"bsonType": "string"},
                "companyWebsite": {"bsonType": "string"},
                "postedDate": {"bsonType": ["date", "string"]},
                "postContent": {"bsonType": "string"},
                "jobUrl": {"bsonType": "string"},
                "location": {"bsonType": "string"},
                "applicant_count": {"bsonType": "string"},
                "scraped_at": {"bsonType": "date"}
            }
        }
    }

    # Create collections if they don't exist
    try:
        if "job_links" not in db.list_collection_names():
            db.create_collection("job_links", validator=job_links_validator)
    except errors.OperationFailure:
        # Ignore validator failures on older servers, create plain collection
        if "job_links" not in db.list_collection_names():
            db.create_collection("job_links")

    try:
        if "job_scrapping_results" not in db.list_collection_names():
            db.create_collection("job_scrapping_results", validator=job_results_validator)
    except errors.OperationFailure:
        if "job_scrapping_results" not in db.list_collection_names():
            db.create_collection("job_scrapping_results")

    # Add simple indexes
    try:
        db.job_links.create_index([("engineName", 1), ("sourceName", 1)])
        db.job_links.create_index([("url", 1)], unique=True)
        db.job_scrapping_results.create_index([("enegName", 1), ("sourceName", 1)])
        db.job_scrapping_results.create_index([("jobUrl", 1)])
    except Exception:
        pass


def insert_job_link(engen_name: str, source_name: str, platform: str, urls: List[str], db=None) -> Any:
    """Insert a job_links document.

    Fields:
    - engen_name: str
    - source_name: str
    - platform: str
    - urls: list[str]
    """
    from datetime import datetime

    if db is None:
        db = get_db()

    doc = {
        "engen_name": engen_name,
        "source_name": source_name,
        "platform": platform,
        "urls": urls,
        "created_at": datetime.utcnow(),
    }

    return db.job_links.insert_one(doc)


def insert_job_result(
    enegName: str,
    sourceName: str,
    jobDescription: str,
    postedAt: Any,
    jobTitle: str,
    companyName: str,
    companyUrl: Optional[str] = None,
    companyOverview: Optional[str] = None,
    companyIndustry: Optional[str] = None,
    companySize: Optional[str] = None,
    companyHeadquarters: Optional[str] = None,
    companyFounded: Optional[str] = None,
    companyWebsite: Optional[str] = None,
    postedDate: Optional[Any] = None,
    postContent: Optional[str] = None,
    jobUrl: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
    db=None,
) -> Any:
    """Insert a job scraping result document.

    Required fields: `enegName`, `sourceName`, `jobDescription`, `postedAt`, `jobTitle`, `companyName`.
    """
    from datetime import datetime

    if db is None:
        db = get_db()

    doc = {
        "enegName": enegName,
        "sourceName": sourceName,
        "jobDescription": jobDescription,
        "postedAt": postedAt,
        "jobTitle": jobTitle,
        "companyName": companyName,
        "companyUrl": companyUrl,
        "companyOverview": companyOverview,
        "companyIndustry": companyIndustry,
        "companySize": companySize,
        "companyHeadquarters": companyHeadquarters,
        "companyFounded": companyFounded,
        "companyWebsite": companyWebsite,
        "postedDate": postedDate or postedAt,
        "postContent": postContent or jobDescription,
        "jobUrl": jobUrl,
        "scraped_at": datetime.utcnow(),
    }

    if extra:
        doc.update(extra)

    return db.job_scrapping_results.insert_one(doc)


def insert_job_link_from_json(
    engine_name: str,
    source_name: str,
    platform: str,
    url: str,
    db=None
) -> Any:
    """Insert a job link from JSON format (matches job_links.json structure).
    
    This function matches the exact JSON format:
    {
        "engineName": "...",
        "sourceName": "...",
        "platform": "...",
        "url": "..."
    }
    """
    from datetime import datetime

    if db is None:
        db = get_db()

    doc = {
        "engineName": engine_name,
        "sourceName": source_name,
        "platform": platform,
        "url": url,
        "created_at": datetime.utcnow(),
        "status": "pending"
    }

    return db.job_links.insert_one(doc)


if __name__ == "__main__":
    # Quick interactive demo when run directly. Use this to test Atlas connection.
    print("MongoDB helper - interactive setup")
    default_uri = os.environ.get('MONGO_URI', '')
    if default_uri:
        print("Current MONGO_URI found in environment (will test it)")
        ok, err = test_connection(default_uri)
        if ok:
            print("Connected successfully to current MONGO_URI")
            client = get_client()
            db = get_db(client)
            create_collections_with_validators(db)
            print("Collections ready in", get_db_name())
        else:
            print("Failed to connect using current MONGO_URI:", err)

    uri = input("Enter MongoDB connection string (Atlas) or press Enter to skip: ").strip()
    if uri:
        ok, err = test_connection(uri)
        if ok:
            print("Connection successful — using provided URI")
            set_mongo_uri(uri, persist=False)
            client = get_client()
            db = get_db(client)
            create_collections_with_validators(db)
            print("Collections ready in", get_db_name())
        else:
            print("Failed to connect:", err)
            print("No changes made. You can set MONGO_URI environment variable to your Atlas connection string and retry.")
    else:
        if not default_uri:
            print("No MONGO_URI provided; skipping database setup.")
