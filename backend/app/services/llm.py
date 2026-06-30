"""LLM adapter — supports emergentintegrations (Gemini/OpenAI/Anthropic via Emergent
universal key) AND OpenAI-compatible endpoints (Ollama / vLLM / LM Studio) when
the user provides a local_endpoint in Settings.

Resilient JSON parsing with LLMJSONError as a single recoverable boundary.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Optional

from emergentintegrations.llm.chat import LlmChat, UserMessage


def emergent_key() -> str:
    return os.environ.get("EMERGENT_LLM_KEY", "")


def default_provider() -> str:
    return os.environ.get("LLM_PROVIDER", "gemini")


def default_model() -> str:
    return os.environ.get("LLM_MODEL", "gemini-3-flash-preview")


def resolve_key(provider: str, user_settings: Optional[dict] = None) -> str:
    """Pick the right API key. Fallback chain: user setting → EMERGENT_LLM_KEY."""
    if user_settings:
        if provider == "gemini" and user_settings.get("gemini_key"):
            return user_settings["gemini_key"]
        if provider == "openai" and user_settings.get("openai_key"):
            return user_settings["openai_key"]
        if provider == "anthropic" and user_settings.get("anthropic_key"):
            return user_settings["anthropic_key"]
        if provider == "local" and user_settings.get("local_api_key"):
            return user_settings["local_api_key"]
    return emergent_key()


def _is_local(provider: str, user_settings: Optional[dict]) -> bool:
    return provider == "local" and bool(user_settings and user_settings.get("local_endpoint"))


# --- OpenAI-compatible client (lazy-imported) ---
async def _local_generate(
    endpoint: str,
    api_key: str,
    model: str,
    system: str,
    user: str,
    *,
    want_json: bool = False,
) -> str:
    """Use the OpenAI SDK against a custom base_url. Supports Ollama / vLLM / LM Studio."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=api_key or "ollama", base_url=endpoint.rstrip("/"))
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


def _new_chat(
    session_id: str,
    system_message: str,
    *,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    user_settings: Optional[dict] = None,
) -> LlmChat:
    prov = provider or default_provider()
    mdl = model or default_model()
    api_key = resolve_key(prov, user_settings)
    return LlmChat(
        api_key=api_key,
        session_id=session_id,
        system_message=system_message,
    ).with_model(prov, mdl)


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
    if _is_local(provider or "", user_settings):
        return await _local_generate(
            endpoint=user_settings["local_endpoint"],
            api_key=user_settings.get("local_api_key", "ollama"),
            model=model or user_settings.get("local_model", "llama3.1:8b"),
            system=system,
            user=user,
            want_json=want_json,
        )
    chat = _new_chat(session_id, system, provider=provider, model=model, user_settings=user_settings)
    # Best-effort JSON-mode hint for providers via emergent — fall back to system prompt only.
    try:
        if want_json and hasattr(chat, "with_response_format"):
            chat = chat.with_response_format({"type": "json_object"})
    except Exception:
        pass
    return await chat.send_message(UserMessage(text=user))


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


# ---- Persona handling ----
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
