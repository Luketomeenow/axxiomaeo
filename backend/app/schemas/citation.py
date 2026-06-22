from dataclasses import dataclass


@dataclass
class CitationResult:
    query: str
    is_cited: bool
    is_mentioned: bool = False
    is_url_cited: bool = False
    visibility_pct: float = 0.0
    sample_runs: int = 1
    competitor_cited: str | None = None
    citation_url: str | None = None
    platform: str = "google_ai"
    parent_query: str | None = None
    funnel_stage: str | None = None
