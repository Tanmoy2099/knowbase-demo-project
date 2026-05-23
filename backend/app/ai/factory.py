from .base import AIProvider
from .providers.openai_provider import OpenAIProvider
from .providers.mistral_provider import MistralProvider
from .providers.ollama_provider import OllamaProvider
import structlog

logger = structlog.get_logger()

_REGISTRY: dict[str, type[AIProvider]] = {
    "openai": OpenAIProvider,
    "mistral": MistralProvider,
    "ollama": OllamaProvider,
}


def get_provider(config) -> AIProvider:
    name = getattr(config, "AI_PROVIDER", None) or config.get("AI_PROVIDER", "openai")
    provider_cls = _REGISTRY.get(name)
    if not provider_cls:
        raise ValueError(
            f"Unknown AI_PROVIDER '{name}'. Valid options: {list(_REGISTRY.keys())}"
        )
    logger.info("AI provider selected", provider=name)
    return provider_cls(config)
