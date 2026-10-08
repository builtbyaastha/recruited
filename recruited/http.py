import httpx

from . import config

_client: httpx.Client | None = None


def client() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(
            timeout=config.HTTP_TIMEOUT,
            headers={"User-Agent": config.USER_AGENT},
            follow_redirects=True,
        )
    return _client


def get_json(url: str, **kw):
    """GET a URL and return parsed JSON, or None on any failure."""
    try:
        r = client().get(url, **kw)
        if r.status_code != 200:
            return None
        return r.json()
    except (httpx.HTTPError, ValueError):
        return None


def get_text(url: str, **kw) -> str | None:
    try:
        r = client().get(url, **kw)
        return r.text if r.status_code == 200 else None
    except httpx.HTTPError:
        return None
