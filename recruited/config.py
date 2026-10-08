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
    "siliconangle": "https://siliconangle.com/category/startups/feed/",
}
# Opt-in only: this is a third-party mirror of YC's directory, so we don't enable it by default.
ENABLE_YC = os.environ.get("RECRUITED_ENABLE_YC") == "1"
YC_HIRING_URL = "https://yc-oss.github.io/api/companies/hiring.json"
EDGAR_FORM_D_ATOM = ("https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=D"
                     "&company=&dateb=&owner=include&start=0&count=100&output=atom")
