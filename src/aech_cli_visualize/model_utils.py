"""Model string parsing utilities for pydantic-ai.

Supports @key=value syntax for model configuration:
- OpenAI Responses API: @reasoning_effort=none|minimal|low|medium|high
- Anthropic: @thinking=true|false|<budget_tokens>

Example: anthropic:claude-sonnet-4-20250514@thinking=true
"""

from typing import Any


def parse_model_string(model_string: str) -> tuple[str, dict[str, Any]]:
    """Parse model string with optional settings.

    Examples:
        "openai:gpt-4o" -> ("openai:gpt-4o", {})
        "openai-responses:o3@reasoning_effort=low" -> ("openai-responses:o3", {"reasoning_effort": "low"})
        "anthropic:claude-sonnet-4@thinking=true" -> ("anthropic:claude-sonnet-4", {"thinking": True})

    Returns:
        Tuple of (model_name, settings_dict)
    """
    if "@" not in model_string:
        return model_string, {}

    parts = model_string.split("@")
    model_name = parts[0]
    settings: dict[str, Any] = {}

    for part in parts[1:]:
        if "=" in part:
            key, value = part.split("=", 1)
            # Parse value types
            if value.lower() == "true":
                settings[key] = True
            elif value.lower() == "false":
                settings[key] = False
            elif value.isdigit():
                settings[key] = int(value)
            else:
                settings[key] = value

    return model_name, settings


def get_model_settings(model_string: str):
    """Get pydantic-ai model_settings from parsed model string.

    Returns appropriate ModelSettings subclass based on provider, or None
    if no settings are needed.
    """
    model_name, settings = parse_model_string(model_string)

    if not settings:
        return None

    if model_name.startswith("openai-responses:"):
        from pydantic_ai.models.openai import OpenAIResponsesModelSettings

        kwargs: dict[str, Any] = {}
        if "reasoning_effort" in settings:
            kwargs["openai_reasoning_effort"] = settings["reasoning_effort"]
        if "reasoning_summary" in settings:
            kwargs["openai_reasoning_summary"] = settings["reasoning_summary"]

        return OpenAIResponsesModelSettings(**kwargs) if kwargs else None

    elif model_name.startswith("anthropic:"):
        from pydantic_ai.models.anthropic import AnthropicModelSettings

        kwargs = {}
        if "thinking" in settings:
            thinking_val = settings["thinking"]
            if thinking_val is True:
                kwargs["anthropic_thinking"] = {"type": "enabled", "budget_tokens": 10000}
            elif isinstance(thinking_val, int) and thinking_val > 0:
                kwargs["anthropic_thinking"] = {"type": "enabled", "budget_tokens": thinking_val}

        return AnthropicModelSettings(**kwargs) if kwargs else None

    return None


def build_pydantic_ai_model(model_string: str, *, api_key: str | None = None):
    """Build a pydantic-ai model, preserving provider-prefixed model strings."""
    model_name, _ = parse_model_string(model_string)

    if model_name.startswith("openai-responses:"):
        from pydantic_ai.models.openai import OpenAIResponsesModel

        raw_model = model_name.split(":", 1)[1]
        if api_key:
            from pydantic_ai.providers.openai import OpenAIProvider

            return OpenAIResponsesModel(raw_model, provider=OpenAIProvider(api_key=api_key))
        return model_name

    if ":" not in model_name:
        from pydantic_ai.models.openai import OpenAIResponsesModel

        if api_key:
            from pydantic_ai.providers.openai import OpenAIProvider

            return OpenAIResponsesModel(model_name, provider=OpenAIProvider(api_key=api_key))
        return f"openai-responses:{model_name}"

    return model_name
