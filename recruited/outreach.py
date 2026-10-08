"""Cold-outreach drafts for ONE user-selected job. Never batch; no email lookup.

Produces (a) the user's cold-email prompt filled in with context we already hold (job posting + recent
signals) so it can be pasted into any LLM with web search, (b) a deterministic draft email and LinkedIn note
that need no LLM, and (c) an optional rewrite by a local Ollama model if RECRUITED_OLLAMA_MODEL is set.
"""
import os
import re
from datetime import datetime, timedelta, timezone

import httpx
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from . import config
from .matching.resume import extract_skills

PROMPT = """I'm writing a cold email to {founder} at {company}, for a
{role} role. My goal is to get a reply or get redirected to the
right recruiter.

Do the following:

1. Search for the specific job posting for {role} at {company}
   (or the closest open role if the exact
   title isn't posted). Pull out the 2-3 things they say they actually
   need — skip generic mission-statement language.

2. Search for one recent, specific, and verifiable piece of news about
   {company} — a product launch, pricing change, funding round,
   market move, or strategic shift — published in the last 6 months.
   It needs to be something a Strategy & Ops person would actually
   notice and care about, not generic PR.

3. From my resume, pick ONE bullet point — the single most relevant
   one to the role and to the company's actual work. Not two, not three. One.

4. Write the email using this exact structure, using ONLY the job posting
   OR the news angle as the connective thread (whichever ties more
   directly to my chosen bullet point — don't use both):

   - Opening line: one sentence connecting [the job requirement / the
     news] directly to the one resume bullet — the connection must be
     specific and earned, not a generic "that's exactly the kind of
     work I do."
   - One sentence transition into the bullet itself, stated plainly.
   - One short paragraph: "I know a lot of talented people reach out to
     you directly, so I wanted to try anyway rather than go through the
     black box. Would it be possible to redirect me to the relevant
     recruiter for {role}? Resume attached."
   - Sign-off with my name and contact info.

Hard constraints:
- Total email under 120 words, excluding subject line and signature.
- No AI-sounding phrases: no "that's the kind of work I thrive on,"
  no "I believe {company} is looking for," no throat-clearing.
- Subject line: role title + "redirect to the right recruiter?"
- Flag, separately from the email, if the news fact needs verification
  before sending.

Here's my resume: {resume}
"""

REDIRECT = ("I know a lot of talented people reach out to you directly, so I wanted to try anyway rather "
            "than go through the black box. Would it be possible to redirect me to the relevant recruiter "
            "for {role}? Resume attached.")
_BULLET = re.compile(r"^\s*[-•*▪●◦·]\s*(.+)$")
_VERB = re.compile(r"^(led|built|launched|designed|created|reduced|increased|grew|managed|developed|"
                   r"implemented|automated|improved|owned|drove|shipped|scaled|cut|analy[sz]ed|ran|saved)\b", re.I)


def words(s: str) -> int:
    return len(s.split())


def candidate_bullets(resume: str) -> list[str]:
    out = []
    for line in resume.splitlines():
        m = _BULLET.match(line)
        text = (m.group(1) if m else line).strip()
        if 6 <= words(text) <= 45 and (m or _VERB.match(text)):
            out.append(text.rstrip("."))
    return out


def pick_bullet(resume: str, target: str) -> str | None:
    """Single bullet most similar to the target text; metrics (numbers) break near-ties."""
    bullets = candidate_bullets(resume)
    if not bullets:
        return None
    mat = TfidfVectorizer(stop_words="english", sublinear_tf=True).fit_transform([target] + bullets)
    sims = cosine_similarity(mat[0], mat[1:]).ravel()
    scored = [(s + (0.03 if re.search(r"\d", b) else 0), b) for s, b in zip(sims, bullets)]
    return max(scored)[1]


def _label(s: dict) -> str:
    """Signals can lack a title (e.g. EDGAR/seed data); fall back to a description of the event."""
    return s.get("title") or " ".join(x for x in (s["type"], s.get("round"), s.get("amount")) if x)


def fresh_news(signals: list[dict], days: int = 180) -> dict | None:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    ok = [s for s in signals if s["type"] in ("funding", "launch") and (s["published_at"] or "") >= cutoff]
    return max(ok, key=lambda s: s["published_at"]) if ok else None


def _needs(job_text: str, bullet: str) -> list[str]:
    """Things the posting asks for that the chosen bullet really covers (so the opening line is earned)."""
    mine = set(extract_skills(bullet))
    shared = [x for x in extract_skills(job_text) if x in mine]
    if shared:
        return shared[:3]
    stop = ENGLISH_STOP_WORDS | {"team", "work", "role", "experience", "years", "will", "across", "using"}
    btoks = {t for t in re.findall(r"[a-z]{4,}", bullet.lower()) if t not in stop}
    seen = []
    for t in re.findall(r"[a-z]{4,}", job_text.lower()):
        if t in btoks and t not in seen:
            seen.append(t)
    return seen[:2]


def first_name(full: str) -> str:
    return (full.strip().split() or ["there"])[0]


def _lower_first(s: str) -> str:
    return s[0].lower() + s[1:] if s and not s[:2].isupper() else s


def draft(job: dict, signals: list[dict], resume: str, founder: str, sender: str, contact: str) -> dict:
    company, role = job["company"], job["title"]
    job_text = f"{job['title']} {job['description'] or ''}"
    news = fresh_news(signals)
    bullet = pick_bullet(resume, job_text + (" " + _label(news) if news else ""))
    flags = []
    if not bullet:
        return {"error": "Couldn't find a resume bullet. Use lines starting with '-' or an action verb."}

    needs = _needs(job_text, bullet)
    job_sim = pick_sim(bullet, job_text)
    news_sim = pick_sim(bullet, _label(news)) if news else -1
    if news and news_sim > job_sim:
        angle = "news"
        amount = f" {news['amount']}" if news.get("amount") else ""
        what = "raise" if news["type"] == "funding" else "launch"
        opening = f"{company}'s recent{amount} {what} will put pressure on exactly the area this project covered."
        flags.append(f"VERIFY before sending: \"{_label(news)}\" ({news['source']}, "
                     f"{(news['published_at'] or '')[:10]}) {news['url']}")
    else:
        angle = "job"
        opening = (f"The {role} posting centres on {_join(needs)}, and that is where my recent work has been."
                   if needs else f"The {role} posting at {company} describes work close to one project of mine.")
        flags.append(f"Confirm the role is still open: {job['url']}")

    bullet_s = _shorten(bullet, 32)
    body = "\n\n".join([
        f"Hi {first_name(founder)},",
        f"{opening} Specifically: {_lower_first(bullet_s)}.",
        REDIRECT.format(role=role),
    ])
    sig = f"{sender}\n{contact}".strip()
    email = f"Subject: {role} redirect to the right recruiter?\n\n{body}\n\n{sig}"
    flags.append(f"Body is {words(body)} words (limit 120)." if words(body) <= 120
                 else f"Body is {words(body)} words: trim it, limit is 120.")
    return {"angle": angle, "bullet": bullet, "email": email, "linkedin": linkedin(role, company, founder, bullet, sender),
            "flags": flags}


def pick_sim(a: str, b: str) -> float:
    m = TfidfVectorizer(stop_words="english").fit_transform([a, b])
    return float(cosine_similarity(m[0], m[1])[0, 0])


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _shorten(s: str, n: int) -> str:
    w = s.split()
    return s if len(w) <= n else " ".join(w[:n]).rstrip(",;") + "…"


def linkedin(role: str, company: str, founder: str, bullet: str, sender: str) -> str:
    """Connection note, kept under LinkedIn's 300-character limit."""
    tail = f" Could you point me to the right recruiter for {role}? Happy to send my resume. — {sender}"
    head = f"Hi {first_name(founder)}, I'm interested in {role} at {company}. "
    room = 300 - len(head) - len(tail) - 2
    b = bullet
    if len(b) > room:
        b = b[:max(0, room - 1)].rsplit(" ", 1)[0] + "…"
    return (head + (b + "." if room > 20 else "") + tail)[:300]


def build_prompt(job: dict, signals: list[dict], resume: str, founder: str) -> str:
    p = PROMPT.format(founder=founder or "[FOUNDER NAME]", company=job["company"], role=job["title"], resume=resume.strip())
    news = [f"- {s['type']}: {_label(s)} ({s['source']}, {(s['published_at'] or '')[:10]}) {s['url']}"
            for s in signals[:5]]
    ctx = (f"\nContext already collected (unverified, check it yourself):\n- Job posting: {job['url']}\n"
           f"{(job['description'] or '')[:1200]}\n" + ("\n".join(news) if news else ""))
    return p + ctx


def ollama_refine(prompt: str) -> str | None:
    """Optional local LLM pass. Returns None if no model configured or Ollama is unreachable."""
    model = os.environ.get("RECRUITED_OLLAMA_MODEL")
    if not model:
        return None
    try:
        r = httpx.post(os.environ.get("OLLAMA_URL", "http://localhost:11434") + "/api/generate",
                       json={"model": model, "prompt": prompt, "stream": False}, timeout=120)
        r.raise_for_status()
        return r.json().get("response")
    except (httpx.HTTPError, ValueError):
        return None
