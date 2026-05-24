from abc import ABC, abstractmethod
from .types import SummarizeContext, SummaryResult, TagResult, CollectionSuggestion, EnrichmentResult, TitleResult


class AIProvider(ABC):
    @abstractmethod
    def summarize(self, content: str, context: SummarizeContext) -> SummaryResult: ...

    @abstractmethod
    def extract_tags(self, content: str) -> list[TagResult]: ...

    @abstractmethod
    def suggest_collection(self, content: str, existing_collections: list[str]) -> CollectionSuggestion | None: ...

    @abstractmethod
    def suggest_title(self, content: str, content_type: str) -> TitleResult: ...

    def enrich(
        self,
        content: str,
        context: SummarizeContext,
        existing_collections: list[str],
    ) -> EnrichmentResult:
        summary = self.summarize(content, context)
        tags = self.extract_tags(content)
        collection = self.suggest_collection(content, existing_collections)
        title = self.suggest_title(content, context.content_type)
        return EnrichmentResult(
            summary=summary,
            tags=tags,
            collection=collection,
            suggested_title=title,
        )
