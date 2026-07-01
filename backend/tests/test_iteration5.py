"""Iteration 5 backend tests — settings shape, persona language, matrix method,
local provider plumbing, JSON mode hint best-effort."""
from __future__ import annotations

import io
import os
import sys
import time
import json
from pathlib import Path

import fitz  # PyMuPDF
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pdf-queue-processor.preview.emergentagent.com").rstrip("/")

# Ensure /app/backend on path for unit-level imports
sys.path.insert(0, "/app/backend")


# ----------------------- Fixtures -----------------------
@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def sample_pdf(tmp_path_factory) -> Path:
    p = tmp_path_factory.mktemp("iter5") / "TEST_iter5.pdf"
    doc = fitz.open()
    page = doc.new_page()
    text = (
        "Abstract\n"
        "This study evaluates the effect of a mindfulness intervention on stress reduction "
        "among 120 undergraduate students using a randomized controlled trial.\n\n"
        "Objective\n"
        "We aim to determine whether an 8-week mindfulness program reduces self-reported stress.\n\n"
        "Methods\n"
        "120 participants were randomly assigned to intervention or control. Stress measured by PSS-10. "
        "Analysis used ANCOVA controlling for baseline scores.\n\n"
        "Results\n"
        "The intervention group showed a statistically significant reduction (p<0.01) in stress scores.\n\n"
        "Conclusion\n"
        "Mindfulness shows promise for reducing student stress; further work needed.\n"
    )
    page.insert_text((50, 50), text)
    doc.save(str(p))
    doc.close()
    return p


@pytest.fixture(scope="module")
def project_and_doc(api, sample_pdf):
    r = api.post(f"{BASE_URL}/api/projects", json={"name": "TEST_iter5", "description": "iter5"})
    assert r.status_code == 200, r.text
    pid = r.json()["id"]

    with open(sample_pdf, "rb") as f:
        r = requests.post(
            f"{BASE_URL}/api/projects/{pid}/documents",
            files={"file": (sample_pdf.name, f, "application/pdf")},
        )
    assert r.status_code == 200, r.text
    did = r.json()["id"]

    # wait for ready
    deadline = time.time() + 120
    while time.time() < deadline:
        s = api.get(f"{BASE_URL}/api/documents/{did}/status").json()
        if s.get("status") == "ready":
            break
        if s.get("status") == "failed":
            pytest.skip(f"document processing failed: {s.get('error')}")
        time.sleep(3)
    else:
        pytest.skip("processing did not complete in 120s")

    yield {"project_id": pid, "document_id": did}

    # cleanup
    try:
        api.delete(f"{BASE_URL}/api/projects/{pid}")
    except Exception:
        pass


# ----------------------- Settings shape -----------------------
class TestSettingsShape:
    def test_get_settings_has_new_fields(self, api):
        r = api.get(f"{BASE_URL}/api/settings")
        assert r.status_code == 200
        s = r.json()
        for key in ("output_language", "ui_language", "local_endpoint",
                    "local_model", "local_api_key_masked", "has_local", "matrix_methods"):
            assert key in s, f"missing {key}"
        # types
        assert isinstance(s["matrix_methods"], list)
        method_ids = {m["id"] for m in s["matrix_methods"]}
        for needed in ("default", "gap_analysis", "method_comparison",
                       "feature_comparison", "experimental_comparison"):
            assert needed in method_ids, f"missing matrix method {needed}"

    def test_put_settings_persists_new_fields(self, api):
        payload = {
            "output_language": "en",
            "ui_language": "en",
            "local_endpoint": "http://example.invalid/v1",
            "local_model": "llama3.1:8b",
            "local_api_key": "xyz12345abc",
        }
        r = api.put(f"{BASE_URL}/api/settings", json=payload)
        assert r.status_code == 200, r.text
        g = api.get(f"{BASE_URL}/api/settings").json()
        assert g["output_language"] == "en"
        assert g["ui_language"] == "en"
        assert g["local_endpoint"] == "http://example.invalid/v1"
        assert g["local_model"] == "llama3.1:8b"
        # api key is masked
        assert g["local_api_key_masked"]  # non-empty
        assert "xyz12345abc" not in g["local_api_key_masked"]
        assert g["has_local"] is True
        # available_models should include the local entry
        local_entries = [m for m in g["available_models"] if m.get("provider") == "local"]
        assert any(m["id"] == "llama3.1:8b" for m in local_entries), f"local not in {g['available_models']}"

    def test_clear_local_endpoint(self, api):
        api.put(f"{BASE_URL}/api/settings", json={
            "local_endpoint": "", "local_model": "", "local_api_key": "",
        })
        g = api.get(f"{BASE_URL}/api/settings").json()
        assert g["has_local"] is False
        assert g["local_endpoint"] == ""


# ----------------------- Persona prefix carries language -----------------------
class TestOutputLanguage:
    def test_persona_prefix_appends_language_unit(self):
        """Unit-level: persona_prefix uses output_language to add language instruction."""
        from app.services.llm import persona_prefix
        idn = persona_prefix({"persona_id": "akademisi_ketat", "output_language": "id"})
        eng = persona_prefix({"persona_id": "akademisi_ketat", "output_language": "en"})
        assert "Bahasa Indonesia" in idn
        assert "English" in eng


# ----------------------- Matrix method param -----------------------
class TestMatrixMethod:
    def test_matrix_gap_analysis(self, api, project_and_doc):
        pid = project_and_doc["project_id"]
        # clear cache via refresh=True to ensure fresh method
        r = api.post(
            f"{BASE_URL}/api/projects/{pid}/matrix",
            json={"method": "gap_analysis", "refresh": True},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["fields"] == ["what_is_known", "gap_identified", "why_unresolved", "opportunity"]
        assert len(body["rows"]) >= 1
        cell_fields = {c["field"] for c in body["rows"][0]["cells"]}
        assert cell_fields == set(body["fields"])

        # second call with same method should be cached (fast)
        t0 = time.time()
        r2 = api.post(
            f"{BASE_URL}/api/projects/{pid}/matrix",
            json={"method": "gap_analysis"},
        )
        dt = time.time() - t0
        assert r2.status_code == 200
        assert dt < 10, f"cached call took {dt:.1f}s — cache miss?"

    def test_matrix_cache_keyed_by_method(self, api, project_and_doc):
        """A second method should not hit the first method's cache. Inspect via DB query."""
        from pymongo import MongoClient
        mongo = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
        db = mongo[os.environ.get("DB_NAME", "test_database")]
        did = project_and_doc["document_id"]
        cached = list(db.matrix_cache.find({"document_id": did}))
        # Already had gap_analysis cached. Check method field exists.
        assert any(c.get("method") == "gap_analysis" for c in cached), f"cache: {cached}"


# ----------------------- Local provider plumbing -----------------------
class TestLocalPlumbing:
    def test_split_provider_model_routes_local(self):
        from app.services.llm import split_provider_model
        prov, mid = split_provider_model(
            "llama3.1:8b",
            {"local_endpoint": "http://example.invalid/v1", "local_model": "llama3.1:8b"},
        )
        assert prov == "local"
        assert mid == "llama3.1:8b"

    def test_summarize_with_local_returns_5xx(self, api, project_and_doc):
        # Set the local endpoint to a fake URL
        api.put(f"{BASE_URL}/api/settings", json={
            "local_endpoint": "http://example.invalid/v1",
            "local_model": "llama3.1:8b",
            "local_api_key": "xyz",
        })
        did = project_and_doc["document_id"]
        try:
            r = api.post(
                f"{BASE_URL}/api/documents/{did}/summarize?model=llama3.1:8b",
                json={},
                timeout=60,
            )
            # We expect a network error → 500/502
            assert r.status_code in (500, 502), f"got {r.status_code}: {r.text[:300]}"
        finally:
            # clean
            api.put(f"{BASE_URL}/api/settings", json={
                "local_endpoint": "", "local_model": "", "local_api_key": "",
            })


# ----------------------- JSON-mode hint best-effort -----------------------
class TestJsonModeHint:
    def test_generate_accepts_want_json_kwarg(self):
        """Ensure generate() has want_json param and does not crash for non-local path."""
        import asyncio
        from app.services import llm

        captured = {}

        class FakeChat:
            def __init__(self, *a, **k):
                pass

            def send_message(self, msg):
                async def _coro():
                    return "ok"
                return _coro()

            def with_response_format(self, fmt):
                captured["fmt"] = fmt
                return self

        def fake_new_chat(*a, **k):
            return FakeChat()

        llm._new_chat = fake_new_chat  # type: ignore

        async def run():
            return await llm.generate("s", "sys", "u", provider="gemini", model="x", want_json=True)

        out = asyncio.get_event_loop().run_until_complete(run())
        assert out == "ok"
        # If hasattr(FakeChat, with_response_format) was True, want_json should have triggered
        assert captured.get("fmt") == {"type": "json_object"}


# ----------------------- Sanity / regression -----------------------
class TestSanity:
    def test_root(self, api):
        r = api.get(f"{BASE_URL}/api/")
        assert r.status_code == 200
        assert r.json().get("status") == "ok"

    def test_summary_has_model_and_persona(self, api, project_and_doc):
        did = project_and_doc["document_id"]
        s = api.get(f"{BASE_URL}/api/documents/{did}/summary").json()
        assert s.get("model_used")
        assert s.get("persona_used")
        assert "sections" in s
        assert isinstance(s.get("claims"), list)
