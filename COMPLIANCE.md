# Data-source compliance

Rules enforced in code (`recruited/http.py`): one identifiable User-Agent with a contact, `robots.txt`
honoured for every host (unreachable robots.txt = skip), >=1s between requests to a host, one request per
feed per run, no logins, no CAPTCHA/anti-bot evasion, no headless-browser scraping.

We store only headlines, links and short snippets (never full copyrighted articles), and always link back.

| Source | Access method | Status |
|---|---|---|
| Greenhouse / Lever / Ashby | Documented public job-board APIs meant for embedding jobs | OK |
| Hacker News | Official Algolia HN Search API; content is public | OK, link back to the item |
| SEC EDGAR Form D | US government data; needs `RECRUITED_CONTACT`, <=10 req/s | OK |
| TechCrunch, VentureBeat, SiliconANGLE | Their public RSS feeds, headline + link only | OK for personal/non-commercial use; check each site's terms before commercial use |
| Product Hunt, EU-Startups | Public RSS feed | **Skipped automatically**: their robots.txt answers 403 to bots (checked Oct 2026). Resumes on its own if that changes |
| Y Combinator list | Third-party mirror of YC's directory | **Off by default** (`RECRUITED_ENABLE_YC=1`); verify YC's terms first |
| Crunchbase, Wellfound, LinkedIn | Terms prohibit scraping | **Not used** |

Operating notes: set `RECRUITED_CONTACT` to a real email. Never set `RECRUITED_IGNORE_ROBOTS` outside local tests.
If a site asks you to stop, remove its entry from `config.py`. This is engineering guidance, not legal advice.
