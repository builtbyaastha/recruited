"""SEC EDGAR Form D filings: the earliest official signal that a private company is raising.

Public-domain government data. SEC requires a descriptive User-Agent with contact info
(set RECRUITED_CONTACT) and <=10 requests/second; we make a single request per run.
"""
import re
from datetime import datetime, timezone

import feedparser

from .. import config
from .base import Item

# Atom titles look like: "D - Acme Robotics, Inc. (0001234567) (Filer)"
_TITLE = re.compile(r"^D(?:/A)?\s*-\s*(?P<name>.+?)\s*\(\d{6,10}\)")
_SUFFIX = re.compile(r",?\s+(inc\.?|llc|l\.l\.c\.|corp\.?|corporation|ltd\.?|lp|l\.p\.)$", re.I)
# Funds/SPVs file Form D too; they aren't hiring startups.
_NOT_STARTUP = re.compile(r"\b(fund|capital|partners|holdings|trust|spv|series\s+\w+\s+a?\s*llc|"
                          r"real estate|realty|properties|investors?|lp|l\.p\.|ventures)\b", re.I)


def parse(text: str) -> list[Item]:
    items = []
    for e in feedparser.parse(text).entries:
        m = _TITLE.match(e.get("title", ""))
        if not m or not e.get("link"):
            continue
        name = _SUFFIX.sub("", m.group("name")).strip()
        if not name or _NOT_STARTUP.search(name):
            continue
        t = e.get("updated_parsed") or e.get("published_parsed")
        when = datetime(*t[:6], tzinfo=timezone.utc).isoformat(timespec="seconds") if t else None
        items.append(Item("funding", "sec-edgar", name, e["link"], title=f"{name} filed Form D (SEC)",
                          round="Form D", published_at=when))
    return items


def fetch() -> list[Item]:
    from ..http import get_text
    if not config.CONTACT and not config.USER_AGENT.count("@"):
        return []  # SEC blocks anonymous bots; skip rather than send a non-compliant request
    text = get_text(config.EDGAR_FORM_D_ATOM)
    return parse(text) if text else []
