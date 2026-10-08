from .. import config
from . import edgar, hn, rss, yc
from .base import Item

ALL = {"hn": hn.fetch, "rss": rss.fetch, "edgar": edgar.fetch}
if config.ENABLE_YC:
    ALL["yc"] = yc.fetch

__all__ = ["ALL", "Item"]
