# Multi-Platform Job Scraper

A flexible, extensible job scraping system that supports multiple job platforms (LinkedIn, Indeed, Glassdoor, etc.).

## Quick Start

### 1. Install Dependencies
```bash
pip install firebase_admin playwright pyyaml
playwright install chromium
```

### 2. Configure Firebase
Set up your Firebase credentials in `firebase_credentials.json` or set the `FIREBASE_CREDENTIALS` environment variable.

### 3. Configure Platforms
Edit `config/platforms.yaml` to enable/disable platforms and set rate limits.

Edit `config/search_configs.json` to add your job search URLs.

### 4. Run the Scraper

**Full Pipeline:**
```bash
python scripts/run_multi_platform_scrapers.py
```

**Individual Steps:**
```bash
# Step 1: Scrape job links
python scripts/scrape_multi_platform_links.py --limit 25

# Step 2: Scrape job details
python scripts/scrape_multi_platform_details.py --concurrent 3

# Step 3: Scrape company details
python scripts/scrape_multi_platform_companies.py --concurrent 2
```

**Platform-Specific:**
```bash
# Scrape only LinkedIn
python scripts/run_multi_platform_scrapers.py --platform linkedin

# Scrape only Indeed
python scripts/run_multi_platform_scrapers.py --platform indeed
```

## Project Structure

```
JobScrapper/
├── db/                          # Database layer
│   ├── firebase_manager.py      # Firebase operations
│   └── firebase_client.py       # Firebase initialization
├── scrapers/                    # Scraper modules
│   ├── core/                    # Core architecture
│   │   ├── base_scraper.py      # Abstract base classes
│   │   ├── platform_registry.py # Platform registry & factory
│   │   ├── data_models.py       # Unified data models
│   │   └── auth_manager.py      # Authentication
│   ├── platforms/               # Platform implementations
│   │   ├── linkedin/            # LinkedIn scraper
│   │   ├── indeed/              # Indeed scraper
│   │   └── glassdoor/           # Glassdoor scraper
│   └── utils/                   # Utilities
│       ├── url_detector.py      # Platform detection
│       └── rate_limiter.py      # Rate limiting
├── scripts/                     # Scraper scripts
│   ├── scrape_multi_platform_links.py     # Job link scraper
│   ├── scrape_multi_platform_details.py   # Job details scraper
│   ├── scrape_multi_platform_companies.py # Company scraper
│   └── run_multi_platform_scrapers.py     # Orchestrator
└── config/                      # Configuration
    ├── platforms.yaml           # Platform settings
    └── search_configs.json      # Search URLs
```

## Supported Platforms

- ✅ **LinkedIn** - Full support (job search, details, company info)
- ✅ **Indeed** - Job search and details (no company pages)
- ✅ **Glassdoor** - Job search and details (company scraping WIP)

## Adding New Platforms

1. Create a new file in `scrapers/platforms/{platform_name}/`
2. Implement `BasePlatformScraper` interface
3. Use `@register_platform('platform_name')` decorator
4. Add configuration to `config/platforms.yaml`

## Database Schema

### Collections

- **job_links** - Job URLs from search pages
- **job_details** - Detailed job information
- **company_details** - Company information

### Fields

All documents include a `platform` field to identify the source platform.

## Features

- 🔄 **Multi-Platform** - Easily add new job platforms
- 🚀 **Concurrent Scraping** - Parallel processing for speed
- 🔐 **Authentication** - Platform-specific auth handling
- ⏱️ **Rate Limiting** - Respect platform limits
- 📊 **Statistics** - Track scraping progress
- 🔍 **Auto-Detection** - Detect platform from URLs

## License

MIT
