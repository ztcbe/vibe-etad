"""LLM adapter for zvibe — uses ADK's LiteLlm with litellm for provider flexibility.

Replaces the custom VngCloudLlm adapter. LiteLlm handles all translation
between ADK's genai types and provider-native formats (OpenAI, Anthropic, etc.).

Each agent can use a different model via per-agent env vars
(fallback to global LLM_* if not set).
"""
from google.adk.models.lite_llm import LiteLlm


def build_llm(
    model: str | None = None,
    api_key: str | None = None,
    api_base: str | None = None,
    max_tokens: int | None = None,
) -> LiteLlm:
    """Build a LiteLlm instance with explicit parameters.

    Args:
        model: Model name (e.g. "google/gemma-4-31b-it").
        api_key: API key for the provider.
        api_base: Base URL for the provider API.
        max_tokens: Max tokens for the model context window.

    Returns:
        Configured LiteLlm instance.
    """
    return LiteLlm(
        model=f"openai/{model}",
        api_key=api_key,
        api_base=api_base,
        max_tokens=max_tokens,
    )
