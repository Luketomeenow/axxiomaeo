from dataclasses import dataclass


@dataclass
class CitationResult:
    query: str
    is_cited: bool
    competitor_cited: str | None = None
    citation_url: str | None = None
    platform: str = "google_ai"
