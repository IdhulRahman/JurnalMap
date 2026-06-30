"""Iteration 3 — Structured summary (P1), Settings, Persona, Model picker, Resummarize."""
import os
import time
import pytest
import requests
import fitz  # PyMuPDF
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL
API = f"{BASE_URL}/api"
S = requests.Session()


def _make_sectioned_pdf(path: str, title: str = "TEST_Sectioned Paper") -> str:
    """Single-page PDF with EXPLICITLY labelled Abstract/Objective/Methods/Results/Conclusion."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), f"Title: {title}", fontsize=12)
    page.insert_text((50, 80),
        "Abstract: We study the impact of structured note-taking on student learning outcomes "
        "across two semesters with 150 undergraduates in introductory psychology courses.",
        fontsize=9)
    page.insert_text((50, 140),
        "Objective: The primary objective is to determine whether Cornell-style notes improve "
        "exam scores compared to free-form notes among first-year students.",
        fontsize=9)
    page.insert_text((50, 200),
        "Methods: We randomly assigned 150 students to Cornell (n=75) or free-form (n=75) note-taking. "
        "Final exam scores and self-reported study time were measured at end of semester.",
        fontsize=9)
    page.insert_text((50, 280),
        "Results: Cornell-note students scored on average 8.4 points higher (p<0.01) and reported "
        "more efficient study sessions than free-form peers.",
        fontsize=9)
    page.insert_text((50, 340),
        "Conclusion: Structured note-taking provides a measurable benefit to learning outcomes and "
        "should be encouraged in introductory courses.",
        fontsize=9)
    doc.save(path)
    doc.close()
    return path


# ----- Fixtures -----
@pytest.fixture(scope="module")
def project_id():
    r = S.post(f"{API}/projects", json={"name": "TEST_iter3", "description": ""})
    assert r.status_code == 200, r.text
    pid = r.json()["id"]
    yield pid
    S.delete(f"{API}/projects/{pid}")


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
def ready_doc(project_id):
    pdf = "/tmp/jm_iter3_sectioned.pdf"
    _make_sectioned_pdf(pdf)
    with open(pdf, "rb") as f:
        r = S.post(f"{API}/projects/{project_id}/documents",
                   files={"file": ("sectioned.pdf", f, "application/pdf")})
    assert r.status_code == 200, r.text
    did = r.json()["id"]
    final = _wait_ready(did)
    assert final.get("status") == "ready", f"doc failed: {final.get('error')}"
    final["id"] = did
    return final


# ----- P1 BUG FIX: structured summary in /status and /summary -----
class TestStructuredSummary:
    def test_status_endpoint_returns_structured_summary(self, ready_doc):
        r = S.get(f"{API}/documents/{ready_doc['id']}/status")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ready"
        summary = data.get("summary")
        assert isinstance(summary, dict), f"summary must be dict, got {type(summary)}"
        for key in ("overview", "abstract", "objective", "method", "results", "conclusion"):
            assert key in summary, f"missing key {key} in summary"
            assert isinstance(summary[key], str), f"{key} not str"
            assert len(summary[key]) >= 10, f"{key} too short: {summary[key]!r}"

    def test_summary_endpoint_returns_sections_and_model(self, ready_doc):
        r = S.get(f"{API}/documents/{ready_doc['id']}/summary")
        assert r.status_code == 200
        data = r.json()
        sections = data.get("sections") or {}
        for key in ("abstract", "objective", "method", "results", "conclusion"):
            assert key in sections, f"missing section {key}"
            assert isinstance(sections[key], str) and len(sections[key]) >= 10
        assert data.get("model_used"), "model_used missing"


# ----- Settings GET/PUT -----
class TestSettings:
    def test_get_settings_defaults(self):
        r = S.get(f"{API}/settings")
        assert r.status_code == 200
        d = r.json()
        for k in ("theme", "persona_id", "default_model", "personas", "available_models",
                  "has_gemini_key", "has_openai_key", "has_anthropic_key",
                  "gemini_key_masked", "openai_key_masked", "anthropic_key_masked"):
            assert k in d, f"missing {k}"
        # personas: 3 + custom
        persona_ids = {p["id"] for p in d["personas"]}
        assert {"akademisi_ketat", "penjelasan_sederhana", "penulis_cepat", "custom"} <= persona_ids
        # available models include emergent defaults
        model_ids = {m["id"] for m in d["available_models"]}
        assert {"gemini-3-flash-preview", "gpt-5.4-mini", "claude-haiku-4-5"} <= model_ids

    def test_put_theme_persists(self):
        r = S.put(f"{API}/settings", json={"theme": "dark"})
        assert r.status_code == 200
        assert r.json()["theme"] == "dark"
        # Reset to light
        r2 = S.put(f"{API}/settings", json={"theme": "light"})
        assert r2.json()["theme"] == "light"

    def test_put_api_keys_set_and_clear(self):
        # Set all three
        r = S.put(f"{API}/settings", json={
            "gemini_key": "sk-test-gemini-12345678",
            "openai_key": "sk-test-openai-12345678",
            "anthropic_key": "sk-test-anth-12345678",
        })
        assert r.status_code == 200
        d = r.json()
        assert d["has_gemini_key"] and d["has_openai_key"] and d["has_anthropic_key"]
        assert "***" in d["gemini_key_masked"]
        # Clear gemini
        r2 = S.put(f"{API}/settings", json={"gemini_key": ""})
        d2 = r2.json()
        assert d2["has_gemini_key"] is False
        # cleanup all
        S.put(f"{API}/settings", json={"openai_key": "", "anthropic_key": ""})

    def test_put_default_model_persists(self):
        r = S.put(f"{API}/settings", json={"default_model": "gemini-2.5-pro"})
        assert r.status_code == 200
        assert r.json()["default_model"] == "gemini-2.5-pro"
        # GET again to verify persisted
        g = S.get(f"{API}/settings").json()
        assert g["default_model"] == "gemini-2.5-pro"
        # restore
        S.put(f"{API}/settings", json={"default_model": "gemini-3-flash-preview"})

    def test_persona_save_with_custom(self):
        r = S.put(f"{API}/settings", json={
            "persona_id": "custom",
            "persona_custom": "Ringkas seperti tweet 280 karakter.",
        })
        d = r.json()
        assert d["persona_id"] == "custom"
        # restore default
        S.put(f"{API}/settings", json={"persona_id": "akademisi_ketat", "persona_custom": ""})


# ----- Resummarize w/ model and persona override -----
class TestResummarize:
    def test_resummarize_with_different_model(self, ready_doc):
        # Get original
        original = S.get(f"{API}/documents/{ready_doc['id']}/summary").json()
        original_model = original.get("model_used")
        original_claim_ids = [c["id"] for c in (original.get("claims") or [])]
        # Use a different default model than original
        target = "gpt-5.4-mini" if original_model and "gpt" not in (original_model or "") else "claude-haiku-4-5"
        r = S.post(f"{API}/documents/{ready_doc['id']}/summarize",
                   params={"model": target}, json={})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("model_used"), "model_used missing"
        # claim ids should change (recreated)
        new_claim_ids = [c["id"] for c in (d.get("claims") or [])]
        assert set(new_claim_ids).isdisjoint(set(original_claim_ids)), \
            "claim ids should be regenerated"
        # Sections still populated
        sections = d.get("sections") or {}
        for k in ("abstract", "objective", "method", "results", "conclusion"):
            assert k in sections and len(sections[k]) >= 10

    def test_resummarize_with_persona_override_no_global_change(self, ready_doc):
        # Save current global persona
        before = S.get(f"{API}/settings").json()
        global_persona_before = before["persona_id"]
        # Override only for this call
        r = S.post(f"{API}/documents/{ready_doc['id']}/summarize",
                   json={"persona_id": "penjelasan_sederhana"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("persona_used") == "penjelasan_sederhana"
        # Verify global setting NOT changed
        after = S.get(f"{API}/settings").json()
        assert after["persona_id"] == global_persona_before, \
            "global persona_id should not change from one-off override"


# ----- Section evidence -----
class TestSectionEvidence:
    def test_section_evidence_returns_items(self, ready_doc):
        r = S.post(f"{API}/documents/{ready_doc['id']}/section-evidence",
                   json={"text": "Cornell-note students scored on average 8.4 points higher"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert "items" in d and isinstance(d["items"], list)
        assert len(d["items"]) >= 1, "expected at least one evidence sentence"
        first = d["items"][0]
        for k in ("page", "x0", "y0", "x1", "y1", "tier", "text"):
            assert k in first

    def test_section_evidence_empty_text_rejected(self, ready_doc):
        r = S.post(f"{API}/documents/{ready_doc['id']}/section-evidence",
                   json={"text": ""})
        assert r.status_code == 400
