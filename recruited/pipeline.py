"""Daily pipeline: ingest -> store -> enrich."""
import logging

from . import db, enrich
from .sources import ALL, Item

log = logging.getLogger("recruited")


def store_item(conn, it: Item) -> bool:
    cid = db.upsert_company(conn, it.company, it.domain, it.description)
    new = db.add_signal(conn, cid, it.kind, it.source, it.url, it.title, it.amount, it.round, it.published_at)
    if it.job:
        j = it.job
        db.add_job(conn, cid, j["title"], j["url"], j["description"], j["location"],
                   j["remote"], j["seniority"], it.source, it.published_at)
    return new


def run(only: list[str] | None = None, do_enrich: bool = True, conn=None) -> dict:
    stats = {"signals": 0, "jobs_from_ats": 0}
    own = conn is None
    ctx = db.session() if own else None
    conn = ctx.__enter__() if own else conn
    try:
        for name, fetch in ALL.items():
            if only and name not in only:
                continue
            try:
                items = fetch()
            except Exception as e:  # one broken source must never kill the run
                log.warning("source %s failed: %s", name, e)
                continue
            new = sum(store_item(conn, it) for it in items)
            conn.commit()
            stats[name] = {"fetched": len(items), "new": new}
            stats["signals"] += new
            log.info("%s: %d items, %d new", name, len(items), new)
        if do_enrich:
            stats["jobs_from_ats"] = enrich.enrich_companies(conn)
    finally:
        if own:
            ctx.__exit__(None, None, None)
    return stats
