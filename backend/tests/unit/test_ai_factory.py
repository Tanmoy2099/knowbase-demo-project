import json
import pytest
from unittest.mock import MagicMock, patch
from app.ai.factory import get_provider
from app.ai.base import AIProvider
from app.ai.types import SummarizeContext, SummaryResult, TagResult, CollectionSuggestion, EnrichmentResult
from app.core.config import Config


def make_config(provider: str = "openai") -> Config:
    config = Config.for_testing()
    config.AI_PROVIDER = provider
    return config


def test_get_provider_returns_openai():
    from app.ai.providers.openai_provider import OpenAIProvider
    provider = get_provider(make_config("openai"))
    assert isinstance(provider, OpenAIProvider)


def test_get_provider_returns_mistral():
    from app.ai.providers.mistral_provider import MistralProvider
    provider = get_provider(make_config("mistral"))
    assert isinstance(provider, MistralProvider)


def test_get_provider_returns_ollama():
    from app.ai.providers.ollama_provider import OllamaProvider
    provider = get_provider(make_config("ollama"))
    assert isinstance(provider, OllamaProvider)


def test_get_provider_raises_for_unknown():
    with pytest.raises(ValueError, match="Unknown AI_PROVIDER"):
        get_provider(make_config("unknown_provider"))


def test_all_providers_implement_interface():
    for name in ["openai", "mistral", "ollama"]:
        provider = get_provider(make_config(name))
        assert isinstance(provider, AIProvider)
        assert hasattr(provider, "summarize")
        assert hasattr(provider, "extract_tags")
        assert hasattr(provider, "suggest_collection")
        assert hasattr(provider, "enrich")


def test_get_provider_case_sensitive():
    """Provider names are case-sensitive — 'OpenAI' is not valid."""
    with pytest.raises(ValueError):
        get_provider(make_config("OpenAI"))


@patch("app.ai.providers.openai_provider.OpenAI")
def test_openai_summarize(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="A great article about AI."))]
    )

    from app.ai.providers.openai_provider import OpenAIProvider
    provider = OpenAIProvider(make_config("openai"))
    result = provider.summarize("Some long content about AI.", SummarizeContext(content_type="link"))

    assert isinstance(result, SummaryResult)
    assert result.text == "A great article about AI."
    assert result.provider == "openai"
    assert result.model == "gpt-4o-mini"


@patch("app.ai.providers.openai_provider.OpenAI")
def test_openai_summarize_strips_whitespace(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="  Summary with spaces.  "))]
    )

    from app.ai.providers.openai_provider import OpenAIProvider
    provider = OpenAIProvider(make_config("openai"))
    result = provider.summarize("content", SummarizeContext(content_type="note"))

    assert result.text == "Summary with spaces."


@patch("app.ai.providers.openai_provider.OpenAI")
def test_openai_extract_tags_parses_json_array(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    tags_json = json.dumps([
        {"name": "Machine Learning", "slug": "machine-learning"},
        {"name": "Python", "slug": "python"},
    ])
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=tags_json))]
    )

    from app.ai.providers.openai_provider import OpenAIProvider
    provider = OpenAIProvider(make_config("openai"))
    tags = provider.extract_tags("Content about Python and ML.")

    assert len(tags) == 2
    assert all(isinstance(t, TagResult) for t in tags)
    assert tags[0].name == "Machine Learning"
    assert tags[0].slug == "machine-learning"


@patch("app.ai.providers.openai_provider.OpenAI")
def test_openai_extract_tags_parses_wrapped_object(mock_openai_cls):
    """Handles {"tags": [...]} wrapper format."""
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    tags_json = json.dumps({"tags": [{"name": "AI", "slug": "ai"}]})
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=tags_json))]
    )

    from app.ai.providers.openai_provider import OpenAIProvider
    provider = OpenAIProvider(make_config("openai"))
    tags = provider.extract_tags("Content about AI.")

    assert len(tags) == 1
    assert tags[0].name == "AI"
    assert tags[0].slug == "ai"


@patch("app.ai.providers.openai_provider.OpenAI")
def test_openai_extract_tags_handles_malformed_json(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="not valid json at all"))]
    )

    from app.ai.providers.openai_provider import OpenAIProvider
    provider = OpenAIProvider(make_config("openai"))
    tags = provider.extract_tags("Content")

    # Should return empty list, not raise
    assert tags == []


@patch("app.ai.providers.openai_provider.OpenAI")
def test_openai_extract_tags_caps_at_eight(mock_openai_cls):
    """extract_tags returns at most 8 tags."""
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    many_tags = [{"name": f"Tag{i}", "slug": f"tag-{i}"} for i in range(15)]
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=json.dumps(many_tags)))]
    )

    from app.ai.providers.openai_provider import OpenAIProvider
    provider = OpenAIProvider(make_config("openai"))
    tags = provider.extract_tags("Long content with many topics.")

    assert len(tags) <= 8


@patch("app.ai.providers.openai_provider.OpenAI")
def test_openai_suggest_collection_returns_none_for_null(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="null"))]
    )

    from app.ai.providers.openai_provider import OpenAIProvider
    provider = OpenAIProvider(make_config("openai"))
    result = provider.suggest_collection("Some content", [])

    assert result is None


@patch("app.ai.providers.openai_provider.OpenAI")
def test_openai_suggest_collection_returns_suggestion(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    suggestion_json = json.dumps({
        "name": "AI Research",
        "slug": "ai-research",
        "description": "Articles about AI research.",
        "confidence": 0.9,
        "is_new": True,
    })
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=suggestion_json))]
    )

    from app.ai.providers.openai_provider import OpenAIProvider
    provider = OpenAIProvider(make_config("openai"))
    result = provider.suggest_collection("Content about artificial intelligence research.", [])

    assert isinstance(result, CollectionSuggestion)
    assert result.name == "AI Research"
    assert result.slug == "ai-research"
    assert result.confidence == 0.9
    assert result.is_new is True


@patch("app.ai.providers.openai_provider.OpenAI")
def test_openai_suggest_collection_handles_malformed_json(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="{bad json}"))]
    )

    from app.ai.providers.openai_provider import OpenAIProvider
    provider = OpenAIProvider(make_config("openai"))
    result = provider.suggest_collection("Content", [])

    assert result is None


@patch("app.ai.providers.openai_provider.OpenAI")
def test_enrich_calls_all_three_methods(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client

    responses = [
        "Summary text here.",
        json.dumps([{"name": "AI", "slug": "ai"}]),
        json.dumps({
            "name": "AI Research",
            "slug": "ai-research",
            "description": "AI topics",
            "confidence": 0.9,
            "is_new": True,
        }),
    ]
    mock_client.chat.completions.create.side_effect = [
        MagicMock(choices=[MagicMock(message=MagicMock(content=r))]) for r in responses
    ]

    from app.ai.providers.openai_provider import OpenAIProvider
    provider = OpenAIProvider(make_config("openai"))
    result = provider.enrich("Some content", SummarizeContext(content_type="link"), [])

    assert isinstance(result, EnrichmentResult)
    assert result.summary.text == "Summary text here."
    assert len(result.tags) == 1
    assert result.collection is not None
    assert result.collection.name == "AI Research"


@patch("app.ai.providers.openai_provider.OpenAI")
def test_enrich_handles_no_collection_suggestion(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client

    responses = [
        "Summary text.",
        json.dumps([{"name": "Python", "slug": "python"}]),
        "null",
    ]
    mock_client.chat.completions.create.side_effect = [
        MagicMock(choices=[MagicMock(message=MagicMock(content=r))]) for r in responses
    ]

    from app.ai.providers.openai_provider import OpenAIProvider
    provider = OpenAIProvider(make_config("openai"))
    result = provider.enrich("Some content", SummarizeContext(content_type="note"), [])

    assert isinstance(result, EnrichmentResult)
    assert result.collection is None
    assert result.summary.text == "Summary text."
    assert len(result.tags) == 1
