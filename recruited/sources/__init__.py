from . import hn, rss, yc
from .base import Item

ALL = {"hn": hn.fetch, "rss": rss.fetch, "yc": yc.fetch}

__all__ = ["ALL", "Item"]
