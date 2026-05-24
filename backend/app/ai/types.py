from dataclasses import dataclass
from typing import Optional


@dataclass
class SummarizeContext:
    content_type: str              # link|note|pdf|youtube
    title: Optional[str] = None
    extra_context: Optional[str] = None      # user-supplied extra context
    user_instructions: Optional[str] = None  # user-supplied AI instructions


@dataclass
class SummaryResult:
    text: str
    model: str
    provider: str


@dataclass
class TitleResult:
    title: str


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
    suggested_title: Optional[TitleResult] = None
