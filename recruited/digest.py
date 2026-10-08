"""Daily email digest: new jobs from the last day, ranked against a resume. Stdlib SMTP, no paid service."""
import os
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from . import service
from .matching import resume as resume_mod
from .matching import scorer


def new_jobs(conn, hours: int = 24) -> list[dict]:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat(timespec="seconds")
    # Jobs have no created-at of their own, so use rowid recency via company signals + posted_at.
    jobs = service.load_jobs(conn)
    return [j for j in jobs if (j["posted_at"] or "") >= cutoff]


def build(conn, resume_text: str, hours: int = 24, limit: int = 10) -> tuple[str, str] | None:
    res = resume_mod.parse(resume_text)
    jobs = new_jobs(conn, hours)
    ranked = scorer.rank(res, jobs, service.load_signals(conn), limit=limit)
    if not ranked:
        return None
    lines = [f"{len(ranked)} new startup roles matched to your resume:\n"]
    for i, m in enumerate(ranked, 1):
        lines.append(f"{i}. {m['title']} @ {m['company']}  [{m['score'] * 100:.0f}]\n   {m['reason']}\n   {m['url']}\n")
    lines.append("You are receiving this because you ran the digest yourself. Nothing is stored about your resume.")
    return f"Recruited: {len(ranked)} new matches", "\n".join(lines)


def send(subject: str, body: str, to: str):
    host = os.environ.get("SMTP_HOST")
    if not host:
        raise RuntimeError("Set SMTP_HOST (and SMTP_USER/SMTP_PASSWORD/SMTP_FROM) to send mail")
    msg = EmailMessage()
    msg["Subject"], msg["To"] = subject, to
    msg["From"] = os.environ.get("SMTP_FROM", os.environ.get("SMTP_USER", "recruited@localhost"))
    msg.set_content(body)
    with smtplib.SMTP(host, int(os.environ.get("SMTP_PORT", "587"))) as s:
        s.starttls()
        if os.environ.get("SMTP_USER"):
            s.login(os.environ["SMTP_USER"], os.environ.get("SMTP_PASSWORD", ""))
        s.send_message(msg)
