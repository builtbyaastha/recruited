"""Funding / launch news via RSS (TechCrunch, VentureBeat, EU-Startups, Product Hunt...)."""
from datetime import datetime, timezone
from time import mktime

import feedparser

from .. import config
from ..extract import parse_headline
from .base import Item


def _published(entry) -> str | None:
    t = entry.get("published_parsed") or entry.get("updated_parsed")
    if not t:
        return None
    return datetime.fromtimestamp(mktime(t), tz=timezone.utc).isoformat(timespec="seconds")


def parse_feed(name: str, text: str) -> list[Item]:
    feed = feedparser.parse(text)
    items = []
    for e in feed.entries:
        title = e.get("title", "")
        link = e.get("link")
        if not link:
            continue
        if name == "producthunt":
            # Product Hunt titles are just the product name; the tagline is the summary.
            items.append(Item("launch", name, title.strip(), link, title=title,
                              description=e.get("summary", "")[:500], published_at=_published(e)))
            continue
        p = parse_headline(title)
        if p:
            items.append(Item(p.type, name, p.company, link, title=title, amount=p.amount,
                              round=p.round, published_at=_published(e)))
    return items


def fetch() -> list[Item]:
    from ..http import get_text
    out = []
    for name, url in config.RSS_FEEDS.items():
        text = get_text(url)
        if text:
            out.extend(parse_feed(name, text))
    return out
