# Recruited

Free, open-source startup job matcher. Every day it collects signals that a startup just
**raised, launched, or started hiring**, pulls their open jobs, and ranks them against your resume.
No paid services: SQLite, public RSS/JSON endpoints, and local TF-IDF (or local embeddings).

## Quick start
```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python -m recruited run                     # ingest + enrich (daily job)
python -m recruited match resume.pdf --remote-only
uvicorn recruited.api:app --reload          # web UI at http://localhost:8000
pytest
```

## Pipeline
`sources/` (HN "Who is hiring", SEC EDGAR Form D, RSS funding/launch news, Product Hunt; YC opt-in)
-> `extract.py` (headline -> company, amount, round) -> SQLite
-> `enrich.py` (guess Greenhouse/Lever/Ashby board, pull jobs from public JSON APIs)
-> `matching/` (resume parse, TF-IDF cosine + skills + title + funding momentum + seniority).

Add a source: create `sources/foo.py` with `fetch() -> list[Item]` and register it in `sources/__init__.py`.

## Options
- `RECRUITED_EMBEDDER=st` + `pip install sentence-transformers`: use a local embedding model.
- `RECRUITED_DB`, `RECRUITED_ENRICH_LIMIT`: DB path, companies probed per run.
- `.github/workflows/daily.yml` runs the pipeline daily on GitHub Actions (free).

## Digest
`python -m recruited digest resume.pdf` prints new matches from the last 24h; add `--to you@x.com` and set
`SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD` (any free SMTP, e.g. Gmail app password or Brevo) to email it.

## Compliance
Set `RECRUITED_CONTACT=you@example.com` (required for SEC EDGAR). All requests honour robots.txt and are rate
limited. See [COMPLIANCE.md](COMPLIANCE.md) for per-source terms.

## Notes
- Crunchbase, Wellfound and LinkedIn are intentionally not scraped (ToS). Funding news, YC and ATS boards cover the same signal.
- Respect each site's robots.txt/ToS. Resumes are processed in memory and never stored.
- Ideas next: user accounts, Postgres+pgvector.
