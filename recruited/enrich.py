"""Find a company's public ATS job board (Greenhouse / Lever / Ashby) and pull its jobs.

These are official public JSON endpoints, so no HTML scraping is needed.
"""
import html
import re
from datetime import datetime, timezone

from . import config, db
from .extract import is_remote, seniority_of

TAG_RE = re.compile(r"<[^>]+>")


def _clean(h: str | None) -> str:
    return re.sub(r"\s+", " ", html.unescape(TAG_RE.sub(" ", html.unescape(h or "")))).strip()[:4000]


def slug_candidates(name: str, domain: str | None) -> list[str]:
    cands = []
    if domain:
        cands.append(domain.split(".")[0].lower())
    base = re.sub(r"\b(inc|labs?|ai|hq|technologies|io)\b\.?", "", name.lower()).strip()
    cands += [re.sub(r"[^a-z0-9]", "", name.lower()),
              re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-"),
              re.sub(r"[^a-z0-9]", "", base)]
    seen, out = set(), []
    for c in cands:
        if c and len(c) > 1 and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def _ms_to_iso(ms) -> str | None:
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).isoformat(timespec="seconds")
    except (TypeError, ValueError):
        return None


def parse_greenhouse(data: dict) -> list[dict]:
    jobs = []
    for j in (data or {}).get("jobs", []):
        loc = (j.get("location") or {}).get("name", "")
        jobs.append(dict(title=j["title"], url=j["absolute_url"], location=loc,
                         description=_clean(j.get("content")), posted_at=j.get("updated_at")))
    return jobs


def parse_lever(data) -> list[dict]:
    jobs = []
    for j in data if isinstance(data, list) else []:
        jobs.append(dict(title=j["text"], url=j["hostedUrl"],
                         location=(j.get("categories") or {}).get("location", "") or "",
                         description=_clean(j.get("descriptionPlain") or j.get("description")),
                         posted_at=_ms_to_iso(j.get("createdAt"))))
    return jobs


def parse_ashby(data: dict) -> list[dict]:
    jobs = []
    for j in (data or {}).get("jobs", []):
        jobs.append(dict(title=j["title"], url=j.get("jobUrl") or j.get("applyUrl"),
                         location=j.get("location", "") or "",
                         description=_clean(j.get("descriptionPlain") or j.get("descriptionHtml")),
                         posted_at=j.get("publishedAt")))
    return [j for j in jobs if j["url"]]


ATS = {
    "greenhouse": ("https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true", parse_greenhouse),
    "lever": ("https://api.lever.co/v0/postings/{slug}?mode=json", parse_lever),
    "ashby": ("https://api.ashbyhq.com/posting-api/job-board/{slug}", parse_ashby),
}


def fetch_jobs(ats: str, slug: str) -> list[dict]:
    from .http import get_json
    url, parser = ATS[ats]
    return parser(get_json(url.format(slug=slug)))


def discover(name: str, domain: str | None) -> tuple[str, str, list[dict]] | None:
    for slug in slug_candidates(name, domain):
        for ats in ATS:
            jobs = fetch_jobs(ats, slug)
            if jobs:
                return ats, slug, jobs
    return None


def store_jobs(conn, company_id: int, ats: str, jobs: list[dict]) -> int:
    n = 0
    for j in jobs:
        n += db.add_job(conn, company_id, j["title"], j["url"], j["description"], j["location"],
                        is_remote(j["location"], j["title"]), seniority_of(j["title"]), ats, j["posted_at"])
    return n


def enrich_companies(conn, limit: int | None = None) -> int:
    """Probe ATS boards for companies we haven't checked yet, freshest signals first."""
    limit = limit or config.ENRICH_LIMIT
    rows = conn.execute(
        "SELECT * FROM companies WHERE ats_checked_at IS NULL "
        "ORDER BY last_signal_at DESC LIMIT ?", (limit,)).fetchall()
    added = 0
    for c in rows:
        found = discover(c["name"], c["domain"])
        if found:
            ats, slug, jobs = found
            conn.execute("UPDATE companies SET ats_type=?, ats_slug=? WHERE id=?", (ats, slug, c["id"]))
            added += store_jobs(conn, c["id"], ats, jobs)
        conn.execute("UPDATE companies SET ats_checked_at=? WHERE id=?", (db.now(), c["id"]))
        conn.commit()
    return added
