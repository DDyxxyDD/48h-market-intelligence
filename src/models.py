"""Shared data models used across the pipeline."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(slots=True)
class Article:
    """A normalized news article and its briefing metadata."""

    title: str
    url: str
    source: str
    published_at: datetime
    summary: str = ""
    section: str = ""
    tickers: list[str] = field(default_factory=list)
    countries: list[str] = field(default_factory=list)
    relevance_score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("Article title cannot be empty")
        if not self.url.strip():
            raise ValueError("Article URL cannot be empty")
        if self.published_at.tzinfo is None:
            self.published_at = self.published_at.replace(tzinfo=timezone.utc)
        if not 0 <= self.relevance_score <= 10:
            raise ValueError("relevance_score must be between 0 and 10")

