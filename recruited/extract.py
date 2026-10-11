"""Rule-based extraction of company / event details from news headlines.

Deliberately dependency-free. Swap in a local LLM (Ollama) behind the same
`parse_headline` interface for better recall.
"""
import re
from dataclasses import dataclass

AMOUNT_RE = re.compile(r"\$\s?(\d+(?:\.\d+)?)\s?(k|m|mn|million|b|bn|billion)\b", re.I)
ROUND_RE = re.compile(
    r"\b(pre-?seed|seed|series\s+[a-f]\b|angel|bridge|growth round|venture round)", re.I
)
FUNDING_VERBS = r"(?:raises?|raised|secures?|secured|lands?|closes?|closed|bags?|snags?|nabs?|gets?|scores?|banks?|picks? up|bags)"
LAUNCH_VERBS = r"(?:launch(?:es|ed)?|unveils?|introduces?|debuts?|releases?|ships?|announces?)"

_FUNDING_NAME = re.compile(rf"^(?P<name>[A-Z0-9][^,:;|]{{1,60}}?)\s+{FUNDING_VERBS}\b")
_LAUNCH_NAME = re.compile(rf"^(?P<name>[A-Z0-9][^,:;|]{{1,60}}?)\s+{LAUNCH_VERBS}\b")
# "Startup X, backed by ..., raises" -> handled by cutting at the first comma in name group.
_TRAILING = re.compile(r"\s+(?:startup|ai startup|the|a)$", re.I)
# "Warehouse robot maker Ultra Robotics" -> "Ultra Robotics"
_DESCRIPTOR = re.compile(r"^.*?\b(?:maker|creator|developer|startup|provider|platform|company|firm|"
                         r"unicorn|giant|specialist|operator|owner|builder|vendor|app)\s+(?=[A-Z0-9])")


@dataclass
class Parsed:
    type: str            # funding | launch
    company: str
    amount: str | None = None
    round: str | None = None


def _amount(text: str) -> str | None:
    m = AMOUNT_RE.search(text)
    if not m:
        return None
    unit = m.group(2).lower()
    unit = {"million": "M", "mn": "M", "m": "M", "billion": "B", "bn": "B", "b": "B", "k": "K"}[unit]
    return f"${m.group(1)}{unit}"


def _round(text: str) -> str | None:
    m = ROUND_RE.search(text)
    if not m:
        return None
    r = re.sub(r"\s+", " ", m.group(1).strip()).title().replace("Pre-Seed", "Pre-Seed")
    return r.replace("Preseed", "Pre-Seed")


def _clean(name: str) -> str:
    name = _TRAILING.sub("", name.strip())
    name = _DESCRIPTOR.sub("", name)
    return name.strip(" -–—\"'")


def parse_headline(title: str) -> Parsed | None:
    """Return a Parsed event for funding/launch headlines, else None."""
    title = title.strip()
    amt, rnd = _amount(title), _round(title)
    m = _FUNDING_NAME.match(title)
    if m and (amt or rnd):
        name = _clean(m.group("name"))
        if name and len(name.split()) <= 6:
            return Parsed("funding", name, amt, rnd)
    m = _LAUNCH_NAME.match(title)
    if m:
        name = _clean(m.group("name"))
        if name and len(name.split()) <= 4:
            return Parsed("launch", name)
    return None


REMOTE_RE = re.compile(r"\bremote\b", re.I)
SENIOR_PATTERNS = [
    ("intern", re.compile(r"\bintern(ship)?\b", re.I)),
    ("executive", re.compile(r"\b(chief|cto|ceo|vp|vice president|head of)\b", re.I)),
    ("lead", re.compile(r"\b(staff|principal|lead|manager|director)\b", re.I)),
    ("senior", re.compile(r"\b(senior|sr\.?)\b", re.I)),
    ("junior", re.compile(r"\b(junior|jr\.?|entry|new grad|graduate|associate)\b", re.I)),
]


def seniority_of(title: str) -> str:
    for label, rx in SENIOR_PATTERNS:
        if rx.search(title):
            return label
    return "mid"


def is_remote(*texts: str) -> bool:
    return any(t and REMOTE_RE.search(t) for t in texts)
