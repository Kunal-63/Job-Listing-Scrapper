# LinkedIn Job Scraper - MongoDB Integration

## Overview
This application scrapes LinkedIn job postings and stores them in MongoDB with complete job and company details.

## Features
- ✅ Modern login interface
- ✅ Background scraping process
- ✅ MongoDB integration
- ✅ Complete job and company data extraction
- ✅ Automatic duplicate detection

## Data Structure

### Job Links Collection (`job_links`)
Stores job URLs to be scraped:
- `engineName`: Category/engine name
- `sourceName`: Source identifier
- `platform`: Platform name (e.g., "Linkedin Job")
- `url`: Job posting URL
- `status`: Scraping status (pending/scraped/failed)
- `created_at`: When the link was added
- `scraped_at`: When it was scraped

### Job Results Collection (`job_scrapping_results`)
Stores scraped job data with all required fields:
- `engineName`: Category/engine name
- `sourceName`: Source identifier
- `post_content`: Job description
- `time`: Posted date
- `title`: Job title
- `company_name`: Company name
- `company_url`: LinkedIn company URL
- `overview`: Company description
- `industry`: Company industry
- `company_size`: Number of employees
- `headquarters`: Company headquarters location
- `founded`: Year founded
- `website`: Company website
- `job_url`: Original job posting URL
- `location`: Job location
- `applicant_count`: Number of applicants
- `scraped_at`: Timestamp when scraped

## Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure MongoDB
Set your MongoDB connection string in `.env`:
```
MONGO_URI=mongodb://localhost:27017
MONGO_DB=jobs_db
```

Or use MongoDB Atlas:
```
MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/
MONGO_DB=jobs_db
```

### 3. Insert Job Links
First, add job links to MongoDB from your JSON file:
```bash
python insert_job_links.py job_links.json
```

## Usage

### Step 1: Run the Application
```bash
python main.py
```

### Step 2: Login to LinkedIn
1. Enter your work station name
2. Accept terms and conditions
3. Click "Connect your LinkedIn"
4. Complete LinkedIn login in the browser window
5. Wait for confirmation

### Step 3: Start Scraping
1. Click the "🚀 Start Scraping" button
2. The process will start in the background
3. You can close the GUI - scraping continues in background
4. View progress in Task Manager

### Background Process
The scraper runs independently and:
- Fetches pending job links from MongoDB
- Scrapes job details (title, description, location, etc.)
- Scrapes company details (industry, size, headquarters, etc.)
- Saves all data to MongoDB
- Updates job link status
- Logs everything to `scraper_background.log`

## Monitoring

### View Logs
```bash
# Real-time log monitoring
tail -f scraper_background.log

# On Windows
Get-Content scraper_background.log -Wait
```

### Check MongoDB
```python
from mongo_client import get_db, get_client

client = get_client()
db = get_db(client)

# Check job links
print("Total job links:", db.job_links.count_documents({}))
print("Pending:", db.job_links.count_documents({"status": "pending"}))
print("Scraped:", db.job_links.count_documents({"status": "scraped"}))

# Check results
print("Total results:", db.job_scrapping_results.count_documents({}))

# View latest result
latest = db.job_scrapping_results.find_one(sort=[("scraped_at", -1)])
print(latest)
```

## File Structure
```
JobScrapper/
├── main.py                     # Main GUI application
├── background_scraper.py       # Background scraping process
├── insert_job_links.py         # Script to insert job links
├── mongo_client.py             # MongoDB connection utilities
├── db_manager.py               # Database manager (async)
├── linkedin_session.json       # LinkedIn session (auto-generated)
├── scraper_background.log      # Background scraper logs
└── linkedin_scraper/           # Scraper modules
    ├── scrapers/
    │   ├── job.py             # Job scraper
    │   ├── company.py         # Company scraper
    │   └── job_search.py      # Search scraper
    └── ...
```

## Troubleshooting

### MongoDB Connection Issues
- Ensure MongoDB is running: `mongod --version`
- Check connection string in `.env`
- For Atlas, whitelist your IP address

### LinkedIn Session Expired
- Delete `linkedin_session.json`
- Run `main.py` again and re-login

### Background Process Not Starting
- Check if Python is in PATH
- Run manually: `python background_scraper.py`
- Check logs in `scraper_background.log`

### No Job Links Found
- Insert job links first: `python insert_job_links.py job_links.json`
- Check MongoDB: `db.job_links.find()`

## Advanced Usage

### Run Background Scraper Manually
```bash
python background_scraper.py
```

### Custom Scraping
Modify `background_scraper.py` to:
- Change concurrency settings
- Add retry logic
- Filter specific job types
- Add custom data fields

## Notes
- The scraper respects LinkedIn's rate limits
- All scraping runs in headless mode (no browser window)
- Session cookies are saved for reuse
- Duplicate job links are automatically skipped
- Failed jobs are marked and can be retried

## Support
For issues or questions, check the logs:
- GUI logs: Console output
- Background scraper: `scraper_background.log`
