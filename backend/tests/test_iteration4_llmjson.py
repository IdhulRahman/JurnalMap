"""Iteration 4 retest — LLM JSON hardening + 502 mapping for /summarize.

Covers:
1) Unit tests on app.services.llm._try_parse_json (4 cases incl. LLMJSONError).
2) Endpoint test: monkeypatch app.services.llm.generate so the LLM emits invalid
   JSON, then POST /api/documents/{id}/summarize?model=gpt-5.4-mini and assert
   502 with detail containing 'malformed JSON' + the model id.
3) Happy-path retest: POST /summarize?model=gemini-3-flash-preview returns 200
   and updates model_used.
"""
from __future__ import annotations

import asyncio
import os
import sys
import time

import pytest
import requests
import fitz  # PyMuPDF
from dotenv import load_dotenv

# Make sure backend modules importable
sys.path.insert(0, "/app/backend")

from app.services import llm  # noqa: E402
from app.services.llm import LLMJSONError, _try_parse_json  # noqa: E402

load_dotenv("/app/frontend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"
API = f"{BASE_URL}/api"
S = requests.Session()


# ---------- 1) Unit tests on _try_parse_json ----------
class TestTryParseJson:
    def test_valid_json_returns_dict(self):
        out = _try_parse_json('{"a": 1, "b": "two"}')
        assert isinstance(out, dict)
        assert out == {"a": 1, "b": "two"}

    def test_json_in_markdown_fences_returns_dict(self):
        raw = '```json\n{"x": 42, "y": [1, 2, 3]}\n```'
        out = _try_parse_json(raw)
        assert isinstance(out, dict)
        assert out == {"x": 42, "y": [1, 2, 3]}

    def test_trailing_comma_is_repaired(self):
        raw = '{"a": 1, "b": 2,}'
        out = _try_parse_json(raw)
        assert isinstance(out, dict)
        assert out == {"a": 1, "b": 2}

    def test_non_json_raises_llmjsonerror(self):
        with pytest.raises(LLMJSONError):
            _try_parse_json("Sorry, I can't produce JSON")

    def test_llmjsonerror_is_not_jsondecodeerror(self):
        """LLMJSONError must be its own class (a ValueError), not JSONDecodeError."""
        import json as _json
        assert not issubclass(LLMJSONError, _json.JSONDecodeError)
        assert issubclass(LLMJSONError, ValueError)


# ---------- Helpers for endpoint tests ----------
def _make_sectioned_pdf(path: str, title: str = "TEST_iter4 paper") -> str:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), f"Title: {title}", fontsize=12)
    page.insert_text((50, 80),
        "Abstract: Short abstract about structured note-taking benefits among "
        "150 undergraduate students.", fontsize=9)
    page.insert_text((50, 140),
        "Objective: Test whether Cornell notes improve exam scores over free-form notes.",
        fontsize=9)
    page.insert_text((50, 200),
        "Methods: Randomised 150 students into Cornell (n=75) vs free-form (n=75).",
        fontsize=9)
    page.insert_text((50, 260),
        "Results: Cornell-note students scored on average 8.4 points higher (p<0.01).",
        fontsize=9)
    page.insert_text((50, 320),
        "Conclusion: Structured note-taking measurably improves learning outcomes.",
        fontsize=9)
    doc.save(path)
    doc.close()
    return path


def _wait_ready(doc_id: str, timeout: int = 120) -> dict:
    deadline = time.time() + timeout
    last = {}
    while time.time() < deadline:
        rr = S.get(f"{API}/documents/{doc_id}/status")
        if rr.status_code == 200:
            last = rr.json()
            if last.get("status") in ("ready", "failed"):
                return last
        time.sleep(3)
    return last


@pytest.fixture(scope="module")
def project_and_doc():
    r = S.post(f"{API}/projects", json={"name": "TEST_iter4_llmjson", "description": ""})
    assert r.status_code == 200, r.text
    pid = r.json()["id"]
    pdf = "/tmp/jm_iter4_sectioned.pdf"
    _make_sectioned_pdf(pdf)
    with open(pdf, "rb") as f:
        r2 = S.post(f"{API}/projects/{pid}/documents",
                    files={"file": ("sectioned.pdf", f, "application/pdf")})
    assert r2.status_code == 200, r2.text
    did = r2.json()["id"]
    final = _wait_ready(did)
    assert final.get("status") == "ready", f"doc failed: {final.get('error')}"
    yield {"project_id": pid, "document_id": did}
    S.delete(f"{API}/projects/{pid}")


# ---------- 2) Endpoint test: malformed JSON -> 502 ----------
# We can't monkeypatch the running supervisor backend process from this test
# process. Instead drive the FastAPI app in-process with TestClient so we can
# monkeypatch app.services.llm.generate before the call.
class TestSummarize502OnBadJSON:
    def test_endpoint_returns_502_when_llm_emits_non_json(self, project_and_doc, monkeypatch):
        # Import the *running* server module in-process. It uses the SAME mongo
        # so the seeded doc (uploaded via HTTP above) is visible.
        from server import app as fastapi_app
        from fastapi.testclient import TestClient

        async def fake_generate(*args, **kwargs):  # noqa: ANN001
            return "Sorry, I cannot produce JSON for this request."

        # Replace the lower-level generate. generate_json inside llm.py
        # references the module-level `generate`, so this monkeypatch is
        # picked up immediately.
        monkeypatch.setattr(llm, "generate", fake_generate)

        with TestClient(fastapi_app) as client:
            resp = client.post(
                f"/api/documents/{project_and_doc['document_id']}/summarize",
                params={"model": "gpt-5.4-mini"},
                json={},
            )
        assert resp.status_code == 502, (
            f"expected 502, got {resp.status_code}: {resp.text}"
        )
        body = resp.json()
        assert "detail" in body, body
        assert "malformed JSON" in body["detail"], body
        assert "gpt-5.4-mini" in body["detail"], body


# ---------- 3) Happy-path retest with gemini ----------
class TestSummarizeHappyPath:
    def test_resummarize_gemini_flash_returns_200(self, project_and_doc):
        did = project_and_doc["document_id"]
        before = S.get(f"{API}/documents/{did}/summary").json()
        before_claims = {c["id"] for c in (before.get("claims") or [])}

        r = S.post(
            f"{API}/documents/{did}/summarize",
            params={"model": "gemini-3-flash-preview"},
            json={},
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("model_used"), "model_used missing"
        # gemini-3-flash-preview must be reflected
        assert "gemini" in (d.get("model_used") or "").lower(), d.get("model_used")
        new_claims = {c["id"] for c in (d.get("claims") or [])}
        assert new_claims.isdisjoint(before_claims), \
            "claim ids should be regenerated on resummarize"
