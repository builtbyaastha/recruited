import sqlite3
from pathlib import Path

from recruited import db, enrich, pipeline
from recruited.extract import parse_headline, seniority_of
from recruited.matching import resume as R
from recruited.matching import scorer
from recruited.sources import hn, rss, yc


def test_headline_funding():
    p = parse_headline("Acme AI raises $12M Series A to build agents")
    assert (p.type, p.company, p.amount, p.round) == ("funding", "Acme AI", "$12M", "Series A")


def test_headline_launch_and_noise():
    assert parse_headline("Foo launches new dashboard").type == "launch"
    assert parse_headline("Why the market is changing") is None
    assert parse_headline("Apple raises prices") is None  # no amount/round -> not funding


def test_hn_comment():
    c = {"id": 1, "created_at": "2026-10-01T00:00:00Z",
         "text": "Acme (YC S24) | Senior Backend Engineer | Remote (US) | Python, Postgres<p>We build things"}
    it = hn.parse_comment(c)
    assert it.company == "Acme" and it.job["remote"] and it.job["seniority"] == "senior"
    assert hn.parse_comment({"id": 2, "text": "just a rambling comment"}) is None


def test_rss_and_yc_parse():
    feed = """<rss version="2.0"><channel><item><title>Zed raises $5 million seed round</title>
    <link>https://x/1</link></item><item><title>Random essay</title><link>https://x/2</link></item></channel></rss>"""
    items = rss.parse_feed("techcrunch", feed)
    assert len(items) == 1 and items[0].amount == "$5M"
    y = yc.parse([{"name": "Foo", "website": "https://www.foo.io", "batch": "W26", "slug": "foo"}])
    assert y[0].domain == "foo.io"


def test_ats_parsers():
    gh = enrich.parse_greenhouse({"jobs": [{"title": "Eng", "absolute_url": "u", "location": {"name": "NYC"},
                                            "content": "&lt;p&gt;Hi&lt;/p&gt;"}]})
    assert gh[0]["description"] == "Hi"
    assert enrich.parse_lever([{"text": "T", "hostedUrl": "u", "categories": {"location": "SF"},
                                "descriptionPlain": "d", "createdAt": 1700000000000}])[0]["location"] == "SF"
    assert enrich.parse_ashby({"jobs": [{"title": "T", "jobUrl": "u", "location": "L"}]})[0]["url"] == "u"
    assert "acme" in enrich.slug_candidates("Acme Labs", "acme.io")


def test_resume_parse():
    r = R.parse("Senior Backend Engineer with 7 years of experience. Python, Postgres, Docker, AWS, ML.")
    assert {"python", "postgres", "docker", "aws"} <= set(r.skills)
    assert r.years == 7 and r.seniority == "senior" and "senior backend engineer" in r.titles


def _seed():
    conn = db.connect(Path(":memory:"))
    a = db.upsert_company(conn, "Acme")
    b = db.upsert_company(conn, "Bravo")
    db.add_signal(conn, a, "funding", "tc", "https://n/1", amount="$10M", round_="Series A")
    db.add_job(conn, a, "Senior Backend Engineer", "https://j/1", "Python Postgres Docker backend APIs",
               "Remote", True, "senior", "greenhouse")
    db.add_job(conn, b, "Marketing Manager", "https://j/2", "SEO content growth campaigns",
               "NYC", False, "lead", "lever")
    return conn


def test_dedupe_and_ranking():
    conn = _seed()
    assert not db.add_job(conn, 1, "Senior Backend Engineer", "https://j/1")  # duplicate url ignored
    assert db.upsert_company(conn, "ACME!") == 1  # name_key normalization
    from recruited import service
    out = service.match_resume(conn, "Senior backend engineer, 7 years. Python, Postgres, Docker, AWS " * 3)
    top = out["matches"][0]
    assert top["company"] == "Acme" and top["matched_skills"] and "raised $10M" in top["reason"]
    assert out["matches"][0]["score"] > out["matches"][1]["score"]


def test_filters():
    conn = _seed()
    from recruited import service
    txt = "Marketing growth SEO manager with 5 years experience in campaigns and content " * 2
    assert all(m["remote"] for m in service.match_resume(conn, txt, remote_only=True)["matches"])


def test_pipeline_store_item():
    conn = db.connect(Path(":memory:"))
    it = hn.parse_comment({"id": 9, "created_at": None,
                           "text": "Foo | ML Engineer | Remote | Python"})
    assert pipeline.store_item(conn, it)
    assert conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 1
    assert not pipeline.store_item(conn, it)  # idempotent


def test_api_roundtrip(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from recruited import api, config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    with db.session() as c:
        pipeline.store_item(c, hn.parse_comment({"id": 3, "created_at": None,
                            "text": "Foo | Backend Engineer | Remote | Python Postgres"}))
    cl = TestClient(api.app)
    r = cl.post("/api/match", data={"text": "Backend engineer with 4 years of Python and Postgres experience. " * 2})
    assert r.status_code == 200 and r.json()["matches"][0]["company"] == "Foo"
    assert cl.post("/api/match", data={"text": "short"}).status_code == 400
    assert cl.get("/").status_code == 200


def test_edgar_parse_filters_funds():
    from recruited.sources import edgar
    feed = """<feed xmlns="http://www.w3.org/2005/Atom">
    <entry><title>D - Acme Robotics, Inc. (0001234567) (Filer)</title><link href="https://sec/1"/><updated>2026-10-01T10:00:00-04:00</updated></entry>
    <entry><title>D - Blue Oak Real Estate Fund LP (0001234568) (Filer)</title><link href="https://sec/2"/></entry>
    </feed>"""
    items = edgar.parse(feed)
    assert [i.company for i in items] == ["Acme Robotics"] and items[0].round == "Form D"


def test_robots_enforced(monkeypatch):
    from recruited import http
    http._robots.clear()
    class R:  # fake response
        def __init__(s, code, text=""): s.status_code, s.text = code, text
    robots = {"blocked.test": R(200, "User-agent: *\nDisallow: /private"), "norobots.test": R(404),
              "forbidden.test": R(403), "api.ashbyhq.com": R(401), "ratelimited.test": R(429)}
    class C:
        def get(s, url, **kw):
            if url.endswith("/robots.txt"):
                return robots[url.split("/")[2]]
            return R(200, "ok")
    monkeypatch.setattr(http, "client", lambda: C())
    monkeypatch.setattr(http.config, "MIN_DELAY", 0)
    assert http.get_text("https://blocked.test/private/x") is None
    assert http.get_text("https://blocked.test/public") == "ok"
    assert http.get_text("https://norobots.test/anything") == "ok"    # no robots.txt -> allowed
    assert http.get_text("https://forbidden.test/feed") is None       # 403 robots -> stay out
    assert http.get_text("https://ratelimited.test/feed") is None     # 429 robots -> stay out
    assert http.get_text("https://api.ashbyhq.com/posting-api/job-board/x") == "ok"  # documented API


def test_robots_unreachable_means_no(monkeypatch):
    import httpx
    from recruited import http
    http._robots.clear()
    class C:
        def get(s, url, **kw): raise httpx.ConnectError("down")
    monkeypatch.setattr(http, "client", lambda: C())
    assert http.get_text("https://down.test/x") is None


def test_digest_builds():
    from recruited import digest
    conn = _seed()
    conn.execute("UPDATE jobs SET posted_at=?", (db.now(),))
    subj, body = digest.build(conn, "Senior backend engineer, 7 years. Python Postgres Docker AWS " * 3)
    assert "Acme" in body and subj.startswith("Recruited")


RESUME = """Jane Doe
- Reduced onboarding time 40% by automating Postgres data pipelines in Python
- Organised the office holiday party for 30 people
- Led a team of 4 to launch pricing experiments across 3 markets
"""


def test_outreach_picks_one_bullet_and_stays_short():
    from recruited import outreach
    conn = _seed()
    job = dict(conn.execute("SELECT j.*, c.name AS company FROM jobs j JOIN companies c ON c.id=j.company_id "
                            "WHERE j.id=1").fetchone())
    sigs = [dict(r) for r in conn.execute("SELECT * FROM signals")]
    d = outreach.draft(job, sigs, RESUME, "Sam Lee", "Jane Doe", "jane@x.com")
    assert "Postgres" in d["bullet"] and d["email"].count("Postgres") <= 1
    assert d["email"].startswith("Subject: Senior Backend Engineer redirect to the right recruiter?")
    body = d["email"].split("\n\n", 1)[1].rsplit("\n\n", 1)[0]
    assert outreach.words(body) < 120 and len(d["linkedin"]) <= 300
    assert d["flags"] and "Hi Sam," in d["email"]
    assert "redirect me to the relevant recruiter" in d["email"]


def test_outreach_prompt_filled_and_no_bullets_error():
    from recruited import outreach
    conn = _seed()
    job = dict(conn.execute("SELECT j.*, c.name AS company FROM jobs j JOIN companies c ON c.id=j.company_id "
                            "WHERE j.id=1").fetchone())
    p = outreach.build_prompt(job, [], RESUME, "Sam Lee")
    assert "cold email to Sam Lee at Acme" in p and "[FOUNDER NAME]" not in p and "Here's my resume: Jane" in p
    assert "error" in outreach.draft(job, [], "no bullets here at all just prose", "S", "J", "")


def test_outreach_api_single_job_only(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from recruited import api, config
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "o.db")
    with db.session() as c:
        pipeline.store_item(c, hn.parse_comment({"id": 3, "created_at": None,
                            "text": "Foo | Backend Engineer | Remote | Python Postgres"}))
    cl = TestClient(api.app)
    form = {"job_id": 1, "resume_text": RESUME, "founder": "Sam", "sender": "Jane", "contact": "j@x.com"}
    r = cl.post("/api/outreach", data=form)
    assert r.status_code == 200 and "Subject:" in r.json()["email"] and "prompt" in r.json()
    assert cl.post("/api/outreach", data={**form, "job_id": 99}).status_code == 404
    assert cl.post("/api/outreach", data={"job_ids": "1,2", "resume_text": RESUME, "sender": "J"}).status_code == 422


def test_ollama_optional(monkeypatch):
    from recruited import outreach
    monkeypatch.delenv("RECRUITED_OLLAMA_MODEL", raising=False)
    assert outreach.ollama_refine("x") is None
