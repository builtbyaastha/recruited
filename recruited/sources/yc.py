"""Y Combinator companies that are currently hiring (community mirror of the YC directory)."""
from urllib.parse import urlparse

from .. import config
from .base import Item


def parse(data: list[dict]) -> list[Item]:
    items = []
    for c in data or []:
        name, url = c.get("name"), c.get("url") or c.get("website")
        if not name:
            continue
        domain = urlparse(c["website"]).netloc.removeprefix("www.") if c.get("website") else None
        batch = c.get("batch", "")
        items.append(Item(
            "hiring", "yc", name, c.get("url") or f"https://www.ycombinator.com/companies/{c.get('slug', name)}",
            title=f"{name} ({batch}) is hiring", domain=domain,
            description=c.get("one_liner") or c.get("long_description"),
            round=f"YC {batch}" if batch else None,
        ))
    return items


def fetch() -> list[Item]:
    from ..http import get_json
    return parse(get_json(config.YC_HIRING_URL))
