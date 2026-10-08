import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS companies (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  name_key TEXT NOT NULL UNIQUE,
  domain TEXT,
  description TEXT,
  stage TEXT,
  ats_type TEXT,
  ats_slug TEXT,
  ats_checked_at TEXT,
  last_signal_at TEXT
);
CREATE TABLE IF NOT EXISTS signals (
  id INTEGER PRIMARY KEY,
  company_id INTEGER NOT NULL REFERENCES companies(id),
  type TEXT NOT NULL,            -- funding | launch | hiring
  source TEXT NOT NULL,
  url TEXT NOT NULL UNIQUE,
  title TEXT,
  amount TEXT,
  round TEXT,
  published_at TEXT
);
CREATE TABLE IF NOT EXISTS jobs (
  id INTEGER PRIMARY KEY,
  company_id INTEGER NOT NULL REFERENCES companies(id),
  title TEXT NOT NULL,
  description TEXT,
  location TEXT,
  remote INTEGER DEFAULT 0,
  seniority TEXT,
  url TEXT NOT NULL UNIQUE,
  source TEXT,
  posted_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_signals_company ON signals(company_id);
CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company_id);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def name_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def connect(path=None) -> sqlite3.Connection:
    path = path or config.DB_PATH
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


@contextmanager
def session(path=None):
    conn = connect(path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def upsert_company(conn, name: str, domain: str | None = None, description: str | None = None) -> int:
    key = name_key(name)
    row = conn.execute("SELECT id, domain, description FROM companies WHERE name_key=?", (key,)).fetchone()
    if row:
        conn.execute(
            "UPDATE companies SET domain=COALESCE(domain, ?), description=COALESCE(description, ?) WHERE id=?",
            (domain, description, row["id"]),
        )
        return row["id"]
    cur = conn.execute(
        "INSERT INTO companies(name, name_key, domain, description) VALUES (?,?,?,?)",
        (name.strip(), key, domain, description),
    )
    return cur.lastrowid


def add_signal(conn, company_id, type_, source, url, title=None, amount=None, round_=None, published_at=None) -> bool:
    published_at = published_at or now()
    cur = conn.execute(
        "INSERT OR IGNORE INTO signals(company_id,type,source,url,title,amount,round,published_at) VALUES (?,?,?,?,?,?,?,?)",
        (company_id, type_, source, url, title, amount, round_, published_at),
    )
    if cur.rowcount:
        conn.execute(
            "UPDATE companies SET last_signal_at=MAX(COALESCE(last_signal_at,''), ?), "
            "stage=COALESCE(?, stage) WHERE id=?",
            (published_at, round_, company_id),
        )
    return bool(cur.rowcount)


def add_job(conn, company_id, title, url, description="", location="", remote=False,
            seniority=None, source=None, posted_at=None) -> bool:
    cur = conn.execute(
        "INSERT OR IGNORE INTO jobs(company_id,title,description,location,remote,seniority,url,source,posted_at) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (company_id, title, description, location, int(remote), seniority, url, source, posted_at or now()),
    )
    return bool(cur.rowcount)
