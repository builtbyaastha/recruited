"""Rank jobs against a resume.

score = 0.55 * semantic + 0.20 * skill overlap + 0.10 * title match
      + 0.10 * company momentum + 0.05 * seniority fit

`semantic` is TF-IDF cosine by default (zero downloads, runs anywhere). If
`sentence-transformers` is installed and RECRUITED_EMBEDDER=st, a local
embedding model is used instead.
"""
import os
import re
from datetime import datetime, timezone

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .. import config
from ..extract import seniority_of
from .resume import Resume, extract_skills

LEVELS = ["intern", "junior", "mid", "senior", "lead", "executive"]
SIGNAL_WEIGHT = {"funding": 1.0, "launch": 0.8, "hiring": 0.6}
W = dict(semantic=0.55, skills=0.20, title=0.10, momentum=0.10, seniority=0.05)


def semantic_scores(query: str, docs: list[str]) -> np.ndarray:
    if not docs:
        return np.array([])
    if os.environ.get("RECRUITED_EMBEDDER") == "st":
        from sentence_transformers import SentenceTransformer
        m = SentenceTransformer(os.environ.get("RECRUITED_ST_MODEL", "BAAI/bge-small-en-v1.5"))
        emb = m.encode([query] + docs, normalize_embeddings=True)
        return emb[1:] @ emb[0]
    vec = TfidfVectorizer(stop_words="english", sublinear_tf=True, ngram_range=(1, 2), min_df=1)
    mat = vec.fit_transform([query] + docs)
    return cosine_similarity(mat[0], mat[1:]).ravel()


def _days_ago(iso: str | None) -> float:
    if not iso:
        return 9999
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 86400)
    except ValueError:
        return 9999


def momentum(signals: list[dict]) -> float:
    best = 0.0
    for s in signals:
        age = _days_ago(s["published_at"])
        if age <= config.FRESH_DAYS:
            best = max(best, SIGNAL_WEIGHT.get(s["type"], 0.5) * (1 - age / (config.FRESH_DAYS * 1.5)))
    return best


def seniority_fit(want: str, have: str | None) -> float:
    if not have or have not in LEVELS or want not in LEVELS:
        return 0.5
    return max(0.0, 1 - abs(LEVELS.index(want) - LEVELS.index(have)) / 3)


def skill_overlap(mine: set, theirs: set) -> float:
    """Share of the job's skills I have, but a job naming only one or two skills can't score a full
    match off a single keyword (floor of 5 in the denominator)."""
    return len(mine & theirs) / max(len(theirs), 5) if theirs else 0.0


_GENERIC_TITLE = {"engineer", "developer", "senior", "sr", "sr.", "junior", "jr", "lead", "staff",
                  "principal", "manager", "i", "ii", "iii", "-", "and", "of"}


def title_match(resume_titles: list[str], job_title: str) -> float:
    """Fraction of the distinctive words in my best title (e.g. "backend", "data") found in the job title."""
    job = set(re.findall(r"[a-z+#.]+", job_title.lower()))
    best = 0.0
    for t in resume_titles:
        words = set(t.split()) - _GENERIC_TITLE
        if words:
            best = max(best, len(words & job) / len(words))
    return best


def rank(resume: Resume, jobs: list[dict], signals_by_company: dict[int, list[dict]],
         location: str = "", remote_only: bool = False, limit: int = 25) -> list[dict]:
    if location:
        loc = location.lower()
        jobs = [j for j in jobs if j["remote"] or loc in (j["location"] or "").lower()]
    if remote_only:
        jobs = [j for j in jobs if j["remote"]]
    if not jobs:
        return []
    sem = semantic_scores(resume.text, [f"{j['title']} {j['title']} {j['description'] or ''}" for j in jobs])
    rskills = set(resume.skills)
    results = []
    for j, s in zip(jobs, sem):
        jskills = set(extract_skills(f"{j['title']} {j['description'] or ''}"))
        matched = sorted(rskills & jskills)
        title_hit = title_match(resume.titles, j["title"])
        mom = momentum(signals_by_company.get(j["company_id"], []))
        sen = seniority_fit(resume.seniority, seniority_of(j["title"]))  # from title, so rule fixes apply to old rows
        score = (W["semantic"] * float(s) + W["skills"] * skill_overlap(rskills, jskills)
                 + W["title"] * title_hit + W["momentum"] * mom + W["seniority"] * sen)
        results.append(dict(j, score=round(score, 4), matched_skills=matched, momentum=round(mom, 2),
                            reason=_reason(matched, mom, signals_by_company.get(j["company_id"], []), sen)))
    results.sort(key=lambda r: r["score"], reverse=True)
    # The same role is often posted several times (one per location); keep the best-scoring copy.
    seen, unique = set(), []
    for r in results:
        key = (r["company_id"], r["title"].strip().lower())
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique[:limit]


def _reason(matched, mom, signals, sen) -> str:
    bits = []
    if matched:
        bits.append("Skills in common: " + ", ".join(matched[:6]))
    fresh = [s for s in signals if _days_ago(s["published_at"]) <= config.FRESH_DAYS]
    if fresh:
        s = max(fresh, key=lambda x: SIGNAL_WEIGHT.get(x["type"], 0))
        detail = {"funding": f"raised {s['amount'] or 'funding'}" + (f" ({s['round']})" if s["round"] else ""),
                  "launch": "just launched", "hiring": "is actively hiring"}[s["type"]]
        bits.append(f"Company {detail}")
    if sen >= 0.99:
        bits.append("seniority fits")
    return "; ".join(bits) or "Semantic match with your resume"
