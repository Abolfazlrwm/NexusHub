"""Registry of available chat providers."""

from __future__ import annotations

from typing import Any, ClassVar

from ..exceptions import ConfigurationError
from .openai_compat import OpenAICompatProvider


class ProviderRegistry:
    """Named factory for chat providers.

    Keeps provider construction configurable at runtime: the platform layer
    will ask for a provider by name with per-agent settings, without the
    runtime importing platform code.
    """

    _factories: ClassVar[dict[str, type[OpenAICompatProvider]]] = {}

    @classmethod
    def register(cls, name: str, provider_cls: type[OpenAICompatProvider]) -> None:
        """Register a provider class under ``name``."""
        if name in cls._factories:
            raise ValueError(f"provider '{name}' is already registered")
        cls._factories[name] = provider_cls

    @classmethod
    def create(cls, name: str, **kwargs: Any) -> OpenAICompatProvider:
        """Instantiate the provider registered under ``name``."""
        try:
            factory = cls._factories[name]
        except KeyError:
            available = ", ".join(sorted(cls._factories)) or "none"
            raise ConfigurationError(
                f"unknown provider '{name}'; available: {available}"
            ) from None
        return factory(**kwargs)

    @classmethod
    def available(cls) -> list[str]:
        """Sorted names of all registered providers."""
        return sorted(cls._factories)


ProviderRegistry.register("openai", OpenAICompatProvider)
ProviderRegistry.register("openai-compat", OpenAICompatProvider)
