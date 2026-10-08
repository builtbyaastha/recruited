"""Query helpers shared by the API and CLI."""
from . import db
from .matching import resume as resume_mod
from .matching import scorer


def load_jobs(conn) -> list[dict]:
    rows = conn.execute(
        "SELECT j.*, c.name AS company, c.stage, c.domain FROM jobs j JOIN companies c ON c.id=j.company_id"
    ).fetchall()
    return [dict(r) for r in rows]


def load_signals(conn) -> dict[int, list[dict]]:
    out: dict[int, list[dict]] = {}
    for r in conn.execute("SELECT * FROM signals"):
        out.setdefault(r["company_id"], []).append(dict(r))
    return out


def match_resume(conn, text: str, **kw) -> dict:
    res = resume_mod.parse(text)
    matches = scorer.rank(res, load_jobs(conn), load_signals(conn), **kw)
    for m in matches:
        m["description"] = (m["description"] or "")[:400]
    return {"profile": {"skills": res.skills, "titles": res.titles, "years": res.years,
                        "seniority": res.seniority}, "matches": matches}


def recent_signals(conn, limit=50, type_=None) -> list[dict]:
    q = ("SELECT s.*, c.name AS company, c.domain FROM signals s JOIN companies c ON c.id=s.company_id "
         + ("WHERE s.type=? " if type_ else "") + "ORDER BY s.published_at DESC LIMIT ?")
    args = ([type_] if type_ else []) + [limit]
    return [dict(r) for r in conn.execute(q, args)]
