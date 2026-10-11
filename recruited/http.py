"""Polite HTTP layer: identifies itself, honours robots.txt, rate-limits per host.

Every fetch in the project goes through here, so compliance is enforced in one place.
"""
import logging
import time
import urllib.robotparser
from urllib.parse import urlparse

import httpx

from . import config

log = logging.getLogger("recruited.http")

_client: httpx.Client | None = None
_robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
_last_hit: dict[str, float] = {}


def client() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(timeout=config.HTTP_TIMEOUT, headers={"User-Agent": config.USER_AGENT},
                               follow_redirects=True)
    return _client


def _robots_for(origin: str):
    """Parse robots.txt once per host, reading any doubt as "keep out".

    200 -> obey its rules. 404/410 (no robots.txt) -> no restrictions. 401/403 -> the site is refusing
    bots, so stay out, unless the host is a documented public API (config.PUBLIC_API_HOSTS) whose API
    root simply rejects unauthenticated paths. 429/5xx/unreachable -> stay out this run.
    """
    if origin in _robots:
        return _robots[origin]
    rp = urllib.robotparser.RobotFileParser()
    host = urlparse(origin).netloc
    try:
        r = client().get(f"{origin}/robots.txt")
        code = r.status_code
        if code == 200:
            rp.parse(r.text.splitlines())
        elif code in (404, 410) or (code in (401, 403) and host in config.PUBLIC_API_HOSTS):
            rp.parse([])
        else:
            log.info("robots.txt at %s returned %s; not fetching from this host", host, code)
            rp = None
    except httpx.HTTPError:
        rp = None
    _robots[origin] = rp
    return rp


def allowed(url: str) -> bool:
    if config.IGNORE_ROBOTS:  # escape hatch for local testing only; never set in CI
        return True
    u = urlparse(url)
    rp = _robots_for(f"{u.scheme}://{u.netloc}")
    return bool(rp and rp.can_fetch(config.USER_AGENT, url))


def _throttle(host: str):
    wait = config.MIN_DELAY - (time.monotonic() - _last_hit.get(host, 0))
    if wait > 0:
        time.sleep(wait)
    _last_hit[host] = time.monotonic()


def _get(url: str, **kw) -> httpx.Response | None:
    if not allowed(url):
        log.info("skipped (robots.txt): %s", url)
        return None
    _throttle(urlparse(url).netloc)
    try:
        r = client().get(url, **kw)
    except httpx.HTTPError as e:
        log.info("fetch failed: %s (%s)", url, type(e).__name__)
        return None
    if r.status_code != 200:
        log.debug("HTTP %s: %s", r.status_code, url)
        return None
    return r


def get_json(url: str, **kw):
    r = _get(url, **kw)
    try:
        return r.json() if r is not None else None
    except ValueError:
        return None


def get_text(url: str, **kw) -> str | None:
    r = _get(url, **kw)
    return r.text if r is not None else None
