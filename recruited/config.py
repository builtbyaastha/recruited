import os
from pathlib import Path

DB_PATH = Path(os.environ.get("RECRUITED_DB", "data/recruited.db"))
USER_AGENT = os.environ.get("RECRUITED_UA", "recruited-bot/0.1 (+https://github.com/builtbyaastha/recruited)")
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
YC_HIRING_URL = "https://yc-oss.github.io/api/companies/hiring.json"
