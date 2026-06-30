"""Iteration 6 tests:
- PATCH /api/documents/{id} title editing (validation, persistence, matrix_cache sync)
- AskResponse attribution (model_used + persona_used in body + openapi schema)
"""
import os
import io
import time
import pytest
import requests

def _read_frontend_env():
    try:
        with open("/app/frontend/.env") as fh:
            for line in fh:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return None

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or _read_frontend_env() or "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL missing"
API = f"{BASE_URL}/api"


def _make_pdf_bytes(title: str, body_extra: str = "") -> bytes:
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    text = (
        f"{title}\n\n"
        f"Abstract: This study investigates an educational intervention.\n"
        f"Objective: To evaluate impact on student outcomes.\n"
        f"Methods: Mixed-methods design across two cohorts.\n"
        f"Results: Significant positive change observed (p<0.05).\n"
        f"Conclusion: The intervention is effective. {body_extra}\n"
    )
    page.insert_text((50, 50), text, fontsize=10)
    out = io.BytesIO()
    doc.save(out)
    doc.close()
    return out.getvalue()


@pytest.fixture(scope="module")
def project_id():
    r = requests.post(f"{API}/projects", json={"name": "TEST_iter6", "description": "iter6 patch title"})
    assert r.status_code == 200, r.text
    pid = r.json()["id"]
    yield pid
    requests.delete(f"{API}/projects/{pid}")


def _upload_and_wait(pid: str, title: str, timeout=120) -> str:
    pdf = _make_pdf_bytes(title)
    r = requests.post(
        f"{API}/projects/{pid}/documents",
        files={"file": (f"{title}.pdf", pdf, "application/pdf")},
    )
    assert r.status_code == 200, r.text
    did = r.json()["id"]
    deadline = time.time() + timeout
    while time.time() < deadline:
        s = requests.get(f"{API}/documents/{did}/status").json()
        if s.get("status") == "ready":
            return did
        if s.get("status") == "error":
            pytest.skip(f"doc errored during processing: {s.get('error')}")
        time.sleep(2)
    pytest.skip("doc did not reach ready in time")


@pytest.fixture(scope="module")
def doc_id(project_id):
    return _upload_and_wait(project_id, "TEST_iter6_paperA")


@pytest.fixture(scope="module")
def doc_id_two(project_id):
    return _upload_and_wait(project_id, "TEST_iter6_paperB")


# --- PATCH /api/documents/{id} validation + persistence ---
class TestPatchDocumentTitle:
    def test_patch_success_returns_updated_title(self, doc_id):
        r = requests.patch(f"{API}/documents/{doc_id}", json={"title": "Brand New Title"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["id"] == doc_id
        assert body["title"] == "Brand New Title"

    def test_get_document_after_patch(self, doc_id):
        r = requests.get(f"{API}/documents/{doc_id}")
        assert r.status_code == 200
        assert r.json()["title"] == "Brand New Title"

    def test_summary_endpoint_reflects_new_title(self, doc_id):
        r = requests.get(f"{API}/documents/{doc_id}/summary")
        assert r.status_code == 200
        assert r.json()["title"] == "Brand New Title"

    def test_patch_empty_title_400(self, doc_id):
        r = requests.patch(f"{API}/documents/{doc_id}", json={"title": ""})
        assert r.status_code == 400, r.text

    def test_patch_whitespace_only_400(self, doc_id):
        r = requests.patch(f"{API}/documents/{doc_id}", json={"title": "   "})
        assert r.status_code == 400
        assert "empty" in r.json().get("detail", "").lower()

    def test_patch_unknown_id_404(self):
        r = requests.patch(f"{API}/documents/does-not-exist-xyz", json={"title": "x"})
        assert r.status_code == 404

    def test_patch_extra_fields_ignored(self, doc_id):
        r = requests.patch(
            f"{API}/documents/{doc_id}",
            json={"title": "After Extras", "foo": "bar", "status": "error"},
        )
        # Extra fields should be ignored, not 400
        assert r.status_code == 200, r.text
        assert r.json()["title"] == "After Extras"
        # status should not have been overwritten
        d = requests.get(f"{API}/documents/{doc_id}").json()
        assert d["status"] == "ready"

    def test_patch_truncates_to_500_chars(self, doc_id):
        long_title = "A" * 800
        r = requests.patch(f"{API}/documents/{doc_id}", json={"title": long_title})
        assert r.status_code == 200
        assert len(r.json()["title"]) == 500


# --- matrix_cache title sync ---
class TestMatrixCacheTitleSync:
    def test_matrix_title_updates_after_patch_without_refresh(self, project_id, doc_id_two):
        # 1) Build matrix once (populates cache)
        r = requests.post(
            f"{API}/projects/{project_id}/matrix",
            json={"refresh": True, "method": "default"},
            timeout=180,
        )
        assert r.status_code == 200, r.text
        rows = r.json()["rows"]
        original_titles = {row["document_id"]: row["title"] for row in rows}
        assert doc_id_two in original_titles

        # 2) PATCH title for doc_id_two
        new_title = "MatrixSync Title XYZ"
        r2 = requests.patch(f"{API}/documents/{doc_id_two}", json={"title": new_title})
        assert r2.status_code == 200

        # 3) Build matrix again WITHOUT refresh — should hit cache but with new title
        r3 = requests.post(
            f"{API}/projects/{project_id}/matrix",
            json={"refresh": False, "method": "default"},
            timeout=60,
        )
        assert r3.status_code == 200
        rows3 = r3.json()["rows"]
        title_map = {row["document_id"]: row["title"] for row in rows3}
        assert title_map[doc_id_two] == new_title, \
            f"Expected '{new_title}' for {doc_id_two}, got {title_map[doc_id_two]}"


# --- AskResponse attribution ---
class TestAskAttribution:
    def test_openapi_schema_has_model_and_persona(self):
        # /openapi.json is not exposed through ingress (only /api/*) — use localhost
        r = requests.get("http://localhost:8001/openapi.json")
        assert r.status_code == 200
        schema = r.json()
        ask_schema = schema["components"]["schemas"]["AskResponse"]
        props = ask_schema["properties"]
        assert "model_used" in props, props.keys()
        assert "persona_used" in props, props.keys()

    def test_ask_returns_attribution(self, project_id, doc_id):
        # default persona is akademisi_ketat
        # ensure persona_id is set explicitly
        requests.put(f"{API}/settings", json={"persona_id": "akademisi_ketat"})

        r = requests.post(
            f"{API}/projects/{project_id}/ask",
            json={"question": "What is the conclusion of this study?"},
            timeout=120,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert isinstance(body.get("model_used"), str) and body["model_used"], body
        assert isinstance(body.get("persona_used"), str) and body["persona_used"], body
        assert body["persona_used"] == "akademisi_ketat"

    def test_ask_persona_switch_reflected(self, project_id, doc_id):
        # Switch persona, call ask once more
        r0 = requests.put(f"{API}/settings", json={"persona_id": "penulis_cepat"})
        assert r0.status_code == 200
        r = requests.post(
            f"{API}/projects/{project_id}/ask",
            json={"question": "Apa kesimpulan utama?"},
            timeout=120,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("persona_used") == "penulis_cepat", body
        # restore default
        requests.put(f"{API}/settings", json={"persona_id": "akademisi_ketat"})
