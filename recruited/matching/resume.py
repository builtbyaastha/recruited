import io
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from ..extract import SENIOR_PATTERNS

_YEARS = re.compile(r"(\d{1,2})\s*\+?\s*(?:years?|yrs?)\b", re.I)
_TITLE = re.compile(
    r"\b((?:senior|sr\.?|junior|jr\.?|staff|principal|lead)?\s*"
    r"(?:software|backend|back-end|frontend|front-end|full[- ]?stack|data|machine learning|ml|ai|devops|"
    r"product|mobile|ios|android|security|cloud|platform|research|qa|design|growth|marketing|sales)\s*"
    r"(?:engineer|developer|scientist|analyst|manager|designer|architect|researcher))\b", re.I)


@dataclass
class Resume:
    text: str
    skills: list[str] = field(default_factory=list)
    titles: list[str] = field(default_factory=list)
    years: int = 0
    seniority: str = "mid"


@lru_cache(maxsize=1)
def skill_vocab() -> list[str]:
    path = Path(__file__).resolve().parent.parent / "skills.txt"
    return [s.strip().lower() for s in path.read_text().splitlines() if s.strip()]


def extract_skills(text: str) -> list[str]:
    low = text.lower()
    found = []
    for s in skill_vocab():
        if re.search(rf"(?<![a-z0-9+#.]){re.escape(s)}(?![a-z0-9+#])", low):
            found.append(s)
    return found


def read_text(data: bytes, filename: str = "") -> str:
    if filename.lower().endswith(".pdf") or data[:5] == b"%PDF-":
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        return "\n".join((p.extract_text() or "") for p in reader.pages)
    return data.decode("utf-8", errors="ignore")


def seniority_from_years(years: int) -> str:
    if years < 1:
        return "junior"
    if years < 3:
        return "junior" if years < 2 else "mid"
    if years < 6:
        return "mid"
    if years < 10:
        return "senior"
    return "lead"


def parse(text: str) -> Resume:
    years = max((int(y) for y in _YEARS.findall(text) if int(y) < 45), default=0)
    titles = list(dict.fromkeys(t.strip().lower() for t in _TITLE.findall(text)))[:5]
    seniority = seniority_from_years(years)
    for label, rx in SENIOR_PATTERNS:
        if label in ("senior", "lead", "executive") and any(rx.search(t) for t in titles):
            seniority = label if years == 0 else seniority
    return Resume(text=text, skills=extract_skills(text), titles=titles, years=years, seniority=seniority)
