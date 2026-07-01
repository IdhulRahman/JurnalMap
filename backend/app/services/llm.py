"""LLM adapter — supports Google Gemini, OpenAI, Anthropic (via native SDKs),
and OpenAI-compatible local endpoints (Ollama / vLLM / LM Studio).

API keys come exclusively from the user's Settings stored in the database.
There is no server-level cloud API key; admins only configure the local LLM.

Key resolution chain:
  1. User's per-provider key from Settings (gemini_key / openai_key / anthropic_key)
  2. For local provider: endpoint + model from user Settings (overridden by admin env if LOCAL_LLM_ENABLED)
  3. ValueError raised if no valid key / endpoint is available.

Resilient JSON parsing with LLMJSONError as the single recoverable boundary.
"""
from __future__ import annotations

import json
import os
import re
import uuid
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def default_provider() -> str:
    return os.environ.get("LLM_PROVIDER", "gemini")


def default_model() -> str:
    return os.environ.get("LLM_MODEL", "gemini-2.0-flash")


def resolve_key(provider: str, user_settings: Optional[dict] = None) -> str:
    """Return the API key for the given provider from user settings.

    Raises ValueError if no key is found (no fallback to any server-side key).
    """
    if user_settings:
        if provider == "gemini" and user_settings.get("gemini_key"):
            return user_settings["gemini_key"]
        if provider == "openai" and user_settings.get("openai_key"):
            return user_settings["openai_key"]
        if provider == "anthropic" and user_settings.get("anthropic_key"):
            return user_settings["anthropic_key"]
        if provider == "local":
            return user_settings.get("local_api_key", "ollama")
    raise ValueError(
        f"No API key configured for provider '{provider}'. "
        "Please add your API key in Settings → API Keys."
    )


def _is_local(provider: str, user_settings: Optional[dict]) -> bool:
    return provider == "local" and bool(user_settings and user_settings.get("local_endpoint"))


# ---------------------------------------------------------------------------
# Provider-specific generate functions
# ---------------------------------------------------------------------------

async def _gemini_generate(
    api_key: str,
    model: str,
    system: str,
    user: str,
    *,
    want_json: bool = False,
) -> str:
    """Generate via Google Gemini using the google-genai SDK."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    config_kwargs: dict[str, Any] = {"temperature": 0.2}
    if want_json:
        config_kwargs["response_mime_type"] = "application/json"

    response = await client.aio.models.generate_content(
        model=model,
        contents=user,
        config=types.GenerateContentConfig(
            system_instruction=system,
            **config_kwargs,
        ),
    )
    return (response.text or "").strip()


async def _openai_generate(
    api_key: str,
    model: str,
    system: str,
    user: str,
    *,
    endpoint: Optional[str] = None,
    want_json: bool = False,
) -> str:
    """Generate via OpenAI SDK (also handles Ollama / vLLM / LM Studio)."""
    from openai import AsyncOpenAI

    kwargs_client: dict[str, Any] = {"api_key": api_key or "ollama"}
    if endpoint:
        kwargs_client["base_url"] = endpoint.rstrip("/")

    client = AsyncOpenAI(**kwargs_client)
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
    }
    if want_json:
        kwargs["response_format"] = {"type": "json_object"}
    resp = await client.chat.completions.create(**kwargs)
    return (resp.choices[0].message.content or "").strip()


async def _anthropic_generate(
    api_key: str,
    model: str,
    system: str,
    user: str,
    *,
    want_json: bool = False,
) -> str:
    """Generate via Anthropic SDK (Claude models)."""
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=api_key)
    system_prompt = system
    if want_json:
        system_prompt += "\n\nYou MUST respond with valid JSON only. No prose, no markdown."

    message = await client.messages.create(
        model=model,
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": user}],
    )
    return (message.content[0].text or "").strip()


# ---------------------------------------------------------------------------
# Unified generate interface
# ---------------------------------------------------------------------------

async def generate(
    session_id: str,
    system: str,
    user: str,
    *,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    user_settings: Optional[dict] = None,
    want_json: bool = False,
) -> str:
    """Route to the correct provider adapter and return raw text."""
    prov = provider or default_provider()
    mdl = model or default_model()

    if _is_local(prov, user_settings):
        return await _openai_generate(
            api_key=user_settings.get("local_api_key", "ollama"),
            model=mdl or user_settings.get("local_model", "llama3.1:8b"),
            system=system,
            user=user,
            endpoint=user_settings["local_endpoint"],
            want_json=want_json,
        )

    api_key = resolve_key(prov, user_settings)

    if prov == "gemini":
        return await _gemini_generate(api_key, mdl, system, user, want_json=want_json)
    if prov == "openai":
        return await _openai_generate(api_key, mdl, system, user, want_json=want_json)
    if prov == "anthropic":
        return await _anthropic_generate(api_key, mdl, system, user, want_json=want_json)

    raise ValueError(f"Unknown provider '{prov}'. Supported: gemini, openai, anthropic, local.")


# ---------------------------------------------------------------------------
# JSON generation with resilient parsing
# ---------------------------------------------------------------------------

_JSON_BLOCK = re.compile(r"\{.*\}|\[.*\]", re.S)


class LLMJSONError(ValueError):
    """Raised when the LLM returns text that we cannot recover as valid JSON."""


def _try_parse_json(raw: str) -> Any:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    match = _JSON_BLOCK.search(raw)
    if match:
        block = match.group(0)
        try:
            return json.loads(block)
        except json.JSONDecodeError:
            repaired = re.sub(r",(\s*[}\]])", r"\1", block)
            try:
                return json.loads(repaired)
            except json.JSONDecodeError:
                pass
    raise LLMJSONError(
        "LLM returned text that could not be parsed as JSON. "
        "Try another model or simplify the request."
    )


async def generate_json(
    session_id: str,
    system: str,
    user: str,
    *,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    user_settings: Optional[dict] = None,
) -> Any:
    sys = (
        system
        + "\n\nYou MUST respond with valid JSON only. No prose, no markdown fences, "
        + "no trailing commas, no comments."
    )
    raw = await generate(
        session_id, sys, user,
        provider=provider, model=model, user_settings=user_settings,
        want_json=True,
    )
    return _try_parse_json(raw)


# ---------------------------------------------------------------------------
# Persona handling
# ---------------------------------------------------------------------------
from app.models.schemas import PERSONAS  # noqa: E402


_LANG_INSTRUCTION = {
    "en": "Always respond in English.",
    "id": "Always respond in Bahasa Indonesia (formal academic register).",
}


def persona_prefix(settings: Optional[dict]) -> str:
    """Build the persona + language system-message prefix from the user's settings."""
    parts: list[str] = []
    if settings:
        pid = (settings.get("persona_id") or "akademisi_ketat").strip()
        if pid == "custom":
            custom = (settings.get("persona_custom") or "").strip()
            if custom:
                parts.append(custom)
        else:
            preset = PERSONAS.get(pid)
            if preset:
                parts.append(preset["prompt"])
        lang = (settings.get("output_language") or "en").lower()
        if lang in _LANG_INSTRUCTION:
            parts.append(_LANG_INSTRUCTION[lang])
    return ("\n\n".join(parts) + "\n\n") if parts else ""


def split_provider_model(model_id: str, user_settings: Optional[dict] = None) -> tuple[str, str]:
    """Infer the provider from a model id string. If the model matches the
    user's configured `local_model`, route via the local OpenAI-compatible path.
    """
    if (
        user_settings
        and user_settings.get("local_endpoint")
        and user_settings.get("local_model")
        and model_id == user_settings.get("local_model")
    ):
        return "local", model_id
    m = model_id.lower()
    if m.startswith("gemini"):
        return "gemini", model_id
    if m.startswith("claude"):
        return "anthropic", model_id
    if m.startswith("gpt") or m.startswith("o1") or m.startswith("o3") or m.startswith("o4"):
        return "openai", model_id
    return default_provider(), model_id


async def list_available_models(provider: str, api_key: str) -> list[dict]:
    """Dynamically list text-generation models supported by the provider key.

    If the call fails or the provider does not support listing (e.g. Anthropic),
    returns a list of default standard models.
    """
    if not api_key:
        return []

    prov = provider.lower().strip()

    if prov == "gemini":
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            models = []
            for m in client.models.list():
                if (
                    m.supported_generation_methods and
                    "generateContent" in m.supported_generation_methods and
                    (m.name.startswith("models/gemini") or m.name.startswith("models/gemma"))
                ):
                    model_id = m.name.replace("models/", "")
                    label = model_id.replace("-", " ").title()
                    models.append({"id": model_id, "provider": "gemini", "label": label})
            if models:
                # Sort models so newest/most common come first
                models.sort(key=lambda x: x["id"], reverse=True)
                return models
        except Exception:
            pass
        return [
            {"id": "gemini-2.5-flash", "provider": "gemini", "label": "Gemini 2.5 Flash"},
            {"id": "gemini-2.5-pro", "provider": "gemini", "label": "Gemini 2.5 Pro"},
            {"id": "gemini-1.5-flash", "provider": "gemini", "label": "Gemini 1.5 Flash"},
            {"id": "gemini-1.5-pro", "provider": "gemini", "label": "Gemini 1.5 Pro"},
        ]

    if prov == "openai":
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=api_key)
            res = await client.models.list()
            models = []
            for m in res.data:
                if m.id.startswith(("gpt-4", "gpt-3.5", "o1", "o3")):
                    label = m.id.replace("-", " ").title()
                    models.append({"id": m.id, "provider": "openai", "label": label})
            if models:
                models.sort(key=lambda x: x["id"])
                return models
        except Exception:
            pass
        return [
            {"id": "gpt-4o-mini", "provider": "openai", "label": "GPT-4o Mini"},
            {"id": "gpt-4o", "provider": "openai", "label": "GPT-4o"},
            {"id": "o1-mini", "provider": "openai", "label": "O1 Mini"},
            {"id": "o3-mini", "provider": "openai", "label": "O3 Mini"},
        ]

    if prov == "anthropic":
        return [
            {"id": "claude-3-5-haiku-latest", "provider": "anthropic", "label": "Claude 3.5 Haiku"},
            {"id": "claude-3-5-sonnet-latest", "provider": "anthropic", "label": "Claude 3.5 Sonnet"},
            {"id": "claude-3-opus-latest", "provider": "anthropic", "label": "Claude 3 Opus"},
        ]

    return []

