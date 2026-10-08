"""Hacker News "Ask HN: Who is hiring?" -- the best free stream of startup jobs."""
import html
import re

from ..extract import is_remote, seniority_of
from .base import Item

ALGOLIA = "https://hn.algolia.com/api/v1"
TAG_RE = re.compile(r"<[^>]+>")


def _text(h: str) -> str:
    h = re.sub(r"<p>|<br\s*/?>", "\n", h or "")
    return html.unescape(TAG_RE.sub("", h)).strip()


def parse_comment(c: dict) -> Item | None:
    """Parse one top-level hiring comment: 'Company | Role | Location | Remote ...'."""
    if not c.get("text"):
        return None
    text = _text(c["text"])
    first = text.split("\n", 1)[0]
    parts = [p.strip() for p in first.split("|")]
    if len(parts) < 3 or len(parts[0]) > 60:
        return None
    company = re.sub(r"\(.*?\)", "", parts[0]).strip()
    if not company:
        return None
    rest = parts[1:]
    role = next((p for p in rest if re.search(r"engineer|developer|designer|manager|scientist|"
                                              r"analyst|sales|marketing|founder|cto|intern|devops|"
                                              r"product|research|ops|support|recruit", p, re.I)), rest[0])
    location = next((p for p in rest if p != role and re.search(r"remote|onsite|hybrid|[A-Z][a-z]+,? ?[A-Z]{2}\b|"
                                                                r"london|berlin|new york|sf|san francisco|nyc|"
                                                                r"europe|usa|us\b|canada|india", p, re.I)), "")
    url = f"https://news.ycombinator.com/item?id={c['id']}"
    return Item(
        "hiring", "hn", company, url, title=first[:200],
        published_at=c.get("created_at"),
        job={"title": role[:150], "description": text[:4000], "location": location[:100],
             "remote": is_remote(first), "seniority": seniority_of(role), "url": url},
    )


def fetch(max_threads: int = 1) -> list[Item]:
    from ..http import get_json
    found = get_json(f"{ALGOLIA}/search_by_date?tags=story,author_whoishiring&hitsPerPage=10")
    items: list[Item] = []
    threads = [h for h in (found or {}).get("hits", []) if "who is hiring" in h.get("title", "").lower()]
    for t in threads[:max_threads]:
        thread = get_json(f"{ALGOLIA}/items/{t['objectID']}")
        for c in (thread or {}).get("children", []):
            it = parse_comment(c)
            if it:
                items.append(it)
    return items
