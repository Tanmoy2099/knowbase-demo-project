from dataclasses import dataclass
from typing import Optional


@dataclass
class SummarizeContext:
    content_type: str  # link|note|pdf|youtube
    title: Optional[str] = None


@dataclass
class SummaryResult:
    text: str
    model: str
    provider: str


@dataclass
class TagResult:
    name: str
    slug: str


@dataclass
class CollectionSuggestion:
    name: str
    slug: str
    description: str
    confidence: float
    is_new: bool


@dataclass
class EnrichmentResult:
    summary: SummaryResult
    tags: list[TagResult]
    collection: Optional[CollectionSuggestion]
