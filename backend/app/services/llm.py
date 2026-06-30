"""LLM adapter via emergentintegrations (Gemini 3 Flash by default)."""
from __future__ import annotations

import json
import os
import re
from typing import Any

from emergentintegrations.llm.chat import LlmChat, UserMessage


def _cfg():
    return (
        os.environ.get("EMERGENT_LLM_KEY", ""),
        os.environ.get("LLM_PROVIDER", "gemini"),
        os.environ.get("LLM_MODEL", "gemini-3-flash-preview"),
    )


def _new_chat(session_id: str, system_message: str) -> LlmChat:
    api_key, provider, model = _cfg()
    return LlmChat(
        api_key=api_key,
        session_id=session_id,
        system_message=system_message,
    ).with_model(provider, model)


async def generate(session_id: str, system: str, user: str) -> str:
    chat = _new_chat(session_id, system)
    return await chat.send_message(UserMessage(text=user))


_JSON_BLOCK = re.compile(r"\{.*\}|\[.*\]", re.S)


async def generate_json(session_id: str, system: str, user: str) -> Any:
    """Force the model to output JSON, parse and return."""
    sys = (
        system
        + "\n\nYou MUST respond with valid JSON only. No prose, no markdown fences."
    )
    raw = await generate(session_id, sys, user)
    raw = raw.strip()
    # strip code fences if any
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
