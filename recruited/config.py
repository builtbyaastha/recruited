import os
from pathlib import Path

DB_PATH = Path(os.environ.get("RECRUITED_DB", "data/recruited.db"))
# SEC and others require a descriptive UA with a real contact. Set RECRUITED_CONTACT to your email.
CONTACT = os.environ.get("RECRUITED_CONTACT", "")
USER_AGENT = os.environ.get(
    "RECRUITED_UA", f"recruited-bot/0.1 (+https://github.com/builtbyaastha/recruited; {CONTACT})".replace("; )", ")"))
# Minimum seconds between requests to the same host (SEC allows 10 req/s; we stay far below).
MIN_DELAY = float(os.environ.get("RECRUITED_MIN_DELAY", "1.0"))
IGNORE_ROBOTS = os.environ.get("RECRUITED_IGNORE_ROBOTS") == "1"
HTTP_TIMEOUT = float(os.environ.get("RECRUITED_TIMEOUT", "20"))
# Max companies whose careers/ATS boards are probed per pipeline run.
ENRICH_LIMIT = int(os.environ.get("RECRUITED_ENRICH_LIMIT", "60"))
# Max age (days) of a signal to be considered "fresh" for ranking.
FRESH_DAYS = 45

RSS_FEEDS = {
    "techcrunch": "https://techcrunch.com/category/startups/feed/",
    "techcrunch-venture": "https://techcrunch.com/category/venture/feed/",
    "venturebeat": "https://venturebeat.com/category/business/feed/",
    "eu-startups": "https://www.eu-startups.com/feed/",
    "producthunt": "https://www.producthunt.com/feed",
    "siliconangle": "https://siliconangle.com/feed/",
}
# Sites whose robots.txt answers 401/403 are skipped automatically (see http.py). As of Oct 2026 that
# includes Product Hunt and EU-Startups; they stay listed so they resume if the site opens up.

# Documented, unauthenticated public APIs that exist for exactly this use. Their hosts may answer
# robots.txt with 401/403 because the whole host is an API; a robots.txt they do serve is still obeyed.
PUBLIC_API_HOSTS = {
    "boards-api.greenhouse.io",   # Greenhouse Job Board API
    "api.lever.co",               # Lever Postings API
    "api.ashbyhq.com",            # Ashby public job posting API
    "hn.algolia.com",             # Official HN Search API
}
# Opt-in only: this is a third-party mirror of YC's directory, so we don't enable it by default.
ENABLE_YC = os.environ.get("RECRUITED_ENABLE_YC") == "1"
YC_HIRING_URL = "https://yc-oss.github.io/api/companies/hiring.json"
EDGAR_FORM_D_ATOM = ("https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=D"
                     "&company=&dateb=&owner=include&start=0&count=100&output=atom")
