from dataclasses import dataclass, field


@dataclass
class Item:
    """Normalized output of every source plugin."""
    kind: str                    # funding | launch | hiring
    source: str
    company: str
    url: str
    title: str = ""
    domain: str | None = None
    description: str | None = None
    amount: str | None = None
    round: str | None = None
    published_at: str | None = None
    # Present only when the source itself yields a job (e.g. HN "Who is hiring").
    job: dict | None = field(default=None)
