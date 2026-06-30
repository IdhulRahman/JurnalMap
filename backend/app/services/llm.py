"""LLM adapter via emergentintegrations (Gemini 3 Flash by default).

Supports:
- Per-call provider / model / api_key overrides (so a user can plug in their
  own keys via /api/settings).
- Persona system-message prepending.
- JSON output parsing.
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
    """Pick the right API key. Fallback chain:
    user setting → EMERGENT_LLM_KEY.
    """
    if user_settings:
        if provider == "gemini" and user_settings.get("gemini_key"):
            return user_settings["gemini_key"]
        if provider == "openai" and user_settings.get("openai_key"):
            return user_settings["openai_key"]
        if provider == "anthropic" and user_settings.get("anthropic_key"):
            return user_settings["anthropic_key"]
    return emergent_key()


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
) -> str:
    chat = _new_chat(session_id, system, provider=provider, model=model, user_settings=user_settings)
    return await chat.send_message(UserMessage(text=user))


_JSON_BLOCK = re.compile(r"\{.*\}|\[.*\]", re.S)


async def generate_json(
    session_id: str,
    system: str,
    user: str,
    *,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    user_settings: Optional[dict] = None,
) -> Any:
    """Force the model to output JSON, parse and return."""
    sys = (
        system
        + "\n\nYou MUST respond with valid JSON only. No prose, no markdown fences."
    )
    raw = await generate(session_id, sys, user, provider=provider, model=model, user_settings=user_settings)
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except Exception:
        match = _JSON_BLOCK.search(raw)
        if match:
            return json.loads(match.group(0))
        raise


# ---- Persona handling ----
from app.models.schemas import PERSONAS  # noqa: E402


def persona_prefix(settings: Optional[dict]) -> str:
    """Build the persona system-message prefix from the user's settings."""
    if not settings:
        return ""
    pid = (settings.get("persona_id") or "akademisi_ketat").strip()
    if pid == "custom":
        custom = (settings.get("persona_custom") or "").strip()
        return custom + "\n\n" if custom else ""
    preset = PERSONAS.get(pid)
    if preset:
        return preset["prompt"] + "\n\n"
    return ""


def split_provider_model(model_id: str) -> tuple[str, str]:
    """Infer the provider from a model id string.

    Used when the frontend sends just a model id (e.g. "gpt-4o-mini").
    """
    m = model_id.lower()
    if m.startswith("gemini"):
        return "gemini", model_id
    if m.startswith("claude"):
        return "anthropic", model_id
    if m.startswith("gpt") or m.startswith("o1") or m.startswith("o3") or m.startswith("o4"):
        return "openai", model_id
    return default_provider(), model_id
