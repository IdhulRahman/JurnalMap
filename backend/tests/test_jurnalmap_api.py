"""End-to-end backend tests for JurnalMap. Uses public REACT_APP_BACKEND_URL."""
import os
import time
import io
import pytest
import requests
import fitz  # PyMuPDF
from pathlib import Path
from dotenv import load_dotenv

# Load /app/frontend/.env to get REACT_APP_BACKEND_URL
load_dotenv("/app/frontend/.env")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"
API = f"{BASE_URL}/api"

SESSION = requests.Session()
SESSION.headers.update({"Accept": "application/json"})


# ---- helpers ----
def _make_pdf(path: str, title: str = "Effect of Coffee on Productivity", n_pages: int = 2) -> str:
    """Tiny scientific-style PDF for processing."""
    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text((50, 60), f"Title: {title}", fontsize=12)
    p1.insert_text((50, 90),
                   "Abstract: This study investigates the effect of moderate coffee "
                   "consumption on knowledge worker productivity. We conducted a "
                   "randomized trial with 120 software engineers over 8 weeks.",
                   fontsize=9)
    p1.insert_text((50, 160),
                   "Introduction: Coffee is widely consumed in workplaces. Prior work "
                   "suggests caffeine boosts short term alertness but evidence on "
                   "sustained output is mixed.",
                   fontsize=9)
    p1.insert_text((50, 230),
                   "Methods: 120 participants (mean age 31) were randomly assigned to "
                   "coffee or placebo groups. We measured commits per day and bug rate.",
                   fontsize=9)
    if n_pages >= 2:
        p2 = doc.new_page()
        p2.insert_text((50, 60),
                       "Results: The coffee group produced 14% more commits "
                       "(p<0.01) with no significant difference in bug rate.",
                       fontsize=9)
        p2.insert_text((50, 130),
                       "Discussion: Findings suggest moderate caffeine intake may "
                       "increase output without harming code quality.",
                       fontsize=9)
        p2.insert_text((50, 200),
                       "Limitations: Single-site, short duration, self-reported "
                       "consumption. Generalizability is limited.",
                       fontsize=9)
    doc.save(path)
    doc.close()
    return path


@pytest.fixture(scope="session")
def project_id():
    r = SESSION.post(f"{API}/projects",
                     json={"name": "TEST_Pytest_Project", "description": "auto"})
    assert r.status_code == 200, r.text
    pid = r.json()["id"]
    yield pid
    # teardown
    SESSION.delete(f"{API}/projects/{pid}")


@pytest.fixture(scope="session")
def uploaded_doc(project_id):
    pdf = "/tmp/jurnalmap_test.pdf"
    _make_pdf(pdf, "Effect of Coffee on Productivity", n_pages=2)
    with open(pdf, "rb") as f:
        r = SESSION.post(
            f"{API}/projects/{project_id}/documents",
            files={"file": ("coffee.pdf", f, "application/pdf")},
        )
    assert r.status_code == 200, r.text
    meta = r.json()
    assert meta["status"] == "processing"
    # poll until ready / failed (LLM call can take ~30s)
    deadline = time.time() + 90
    last = meta
    while time.time() < deadline:
        time.sleep(3)
        rr = SESSION.get(f"{API}/documents/{meta['id']}")
        if rr.status_code == 200:
            last = rr.json()
            if last["status"] in ("ready", "failed"):
                break
    return last


# ---- Health ----
def test_health():
    r = SESSION.get(f"{API}/")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


# ---- Projects CRUD ----
class TestProjects:
    def test_create_and_list_project(self):
        r = SESSION.post(f"{API}/projects",
                         json={"name": "TEST_proj_crud", "description": "x"})
        assert r.status_code == 200
        data = r.json()
        assert data["name"] == "TEST_proj_crud"
        assert "id" in data
        pid = data["id"]

        # list
        lr = SESSION.get(f"{API}/projects")
        assert lr.status_code == 200
        ids = [p["id"] for p in lr.json()]
        assert pid in ids

        # delete
        dr = SESSION.delete(f"{API}/projects/{pid}")
        assert dr.status_code == 200
        assert dr.json().get("deleted") is True

        # confirm gone
        gr = SESSION.get(f"{API}/projects/{pid}")
        assert gr.status_code == 404

    def test_cascade_delete_documents(self):
        # create project + upload doc, then delete project, verify doc gone
        pr = SESSION.post(f"{API}/projects", json={"name": "TEST_cascade"}).json()
        pid = pr["id"]
        pdf = "/tmp/jm_cascade.pdf"
        _make_pdf(pdf)
        with open(pdf, "rb") as f:
            up = SESSION.post(f"{API}/projects/{pid}/documents",
                              files={"file": ("c.pdf", f, "application/pdf")})
        assert up.status_code == 200
        did = up.json()["id"]
        SESSION.delete(f"{API}/projects/{pid}")
        # doc should also be 404
        gd = SESSION.get(f"{API}/documents/{did}")
        assert gd.status_code == 404


# ---- Documents upload + processing ----
class TestDocuments:
    def test_upload_processes_async(self, project_id):
        # upload should return immediately with status=processing
        pdf = "/tmp/jm_async.pdf"
        _make_pdf(pdf)
        t0 = time.time()
        with open(pdf, "rb") as f:
            r = SESSION.post(f"{API}/projects/{project_id}/documents",
                             files={"file": ("a.pdf", f, "application/pdf")})
        elapsed = time.time() - t0
        assert r.status_code == 200, r.text
        meta = r.json()
        assert meta["status"] == "processing"
        # request must not block on the LLM (allow some PDF write overhead)
        assert elapsed < 10, f"upload returned slowly: {elapsed:.1f}s"

    def test_reject_non_pdf(self, project_id):
        r = SESSION.post(f"{API}/projects/{project_id}/documents",
                         files={"file": ("a.txt", io.BytesIO(b"hi"), "text/plain")})
        assert r.status_code == 400

    def test_doc_reaches_ready(self, uploaded_doc):
        # If processing failed, surface the error explicitly
        assert uploaded_doc["status"] == "ready", (
            f"document failed: {uploaded_doc.get('error') or uploaded_doc}"
        )
        assert uploaded_doc.get("page_count", 0) >= 1

    def test_serve_pdf(self, uploaded_doc):
        r = SESSION.get(f"{API}/documents/{uploaded_doc['id']}/pdf")
        assert r.status_code == 200
        assert "application/pdf" in r.headers.get("content-type", "")
        assert r.content[:4] == b"%PDF"

    def test_summary_endpoint(self, uploaded_doc):
        if uploaded_doc["status"] != "ready":
            pytest.skip(f"doc not ready: {uploaded_doc.get('error')}")
        r = SESSION.get(f"{API}/documents/{uploaded_doc['id']}/summary")
        assert r.status_code == 200
        data = r.json()
        assert "title" in data
        assert isinstance(data.get("summary"), str)
        claims = data.get("claims") or []
        assert 5 <= len(claims) <= 8, f"expected 5-8 claims, got {len(claims)}"
        cats = {c["category"] for c in claims}
        assert cats.issubset({"objective", "method", "finding", "limitation"}), cats


# ---- Evidence ----
class TestEvidence:
    def test_evidence_for_claim(self, uploaded_doc):
        if uploaded_doc["status"] != "ready":
            pytest.skip("doc not ready")
        s = SESSION.get(f"{API}/documents/{uploaded_doc['id']}/summary").json()
        claims = s["claims"]
        assert claims, "no claims to test evidence on"
        cid = claims[0]["id"]
        r = SESSION.post(f"{API}/claims/{cid}/evidence")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["claim_id"] == cid
        items = data.get("items") or []
        assert items, "expected at least one evidence item"
        first = items[0]
        for k in ("page", "x0", "y0", "x1", "y1", "tier", "rationale"):
            assert k in first
        assert first["tier"] in ("high", "medium", "low")


# ---- Outliers ----
class TestOutliers:
    def test_outliers_single_doc(self, project_id, uploaded_doc):
        if uploaded_doc["status"] != "ready":
            pytest.skip("doc not ready")
        r = SESSION.get(f"{API}/projects/{project_id}/outliers")
        assert r.status_code == 200
        data = r.json()
        # Could be 1+ docs (test session uploads multiple)
        assert "points" in data and "summary" in data
        assert len(data["points"]) >= 1

    def test_outliers_two_docs(self, project_id):
        # add a second distinct doc
        pdf = "/tmp/jm_outlier2.pdf"
        _make_pdf(pdf, title="Bridge Truss Fatigue Study", n_pages=2)
        with open(pdf, "rb") as f:
            up = SESSION.post(f"{API}/projects/{project_id}/documents",
                              files={"file": ("b.pdf", f, "application/pdf")})
        assert up.status_code == 200
        did = up.json()["id"]
        # wait for ready
        deadline = time.time() + 90
        while time.time() < deadline:
            time.sleep(3)
            d = SESSION.get(f"{API}/documents/{did}").json()
            if d["status"] in ("ready", "failed"):
                break
        if d["status"] != "ready":
            pytest.skip(f"second doc not ready: {d.get('error')}")
        r = SESSION.get(f"{API}/projects/{project_id}/outliers")
        data = r.json()
        assert len(data["points"]) >= 2
        for p in data["points"]:
            assert 0.0 <= p["x"] <= 1.0
            assert 0.0 <= p["y"] <= 1.0


# ---- Matrix ----
class TestMatrix:
    def test_matrix(self, project_id, uploaded_doc):
        if uploaded_doc["status"] != "ready":
            pytest.skip("doc not ready")
        r = SESSION.post(f"{API}/projects/{project_id}/matrix", json={})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["fields"] == ["objective", "method", "sample",
                                  "key_finding", "limitation"]
        assert len(data["rows"]) >= 1
        row = data["rows"][0]
        assert {c["field"] for c in row["cells"]} >= set(data["fields"])


# ---- Ask ----
class TestAsk:
    def test_ask_returns_answer_and_tier(self, project_id, uploaded_doc):
        if uploaded_doc["status"] != "ready":
            pytest.skip("doc not ready")
        r = SESSION.post(f"{API}/projects/{project_id}/ask",
                         json={"question": "What was the effect of coffee on productivity?"})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["overall_tier"] in ("high", "medium", "low")
        assert isinstance(data["answer"], str) and data["answer"]
        assert isinstance(data["citations"], list)

    def test_ask_empty_question_rejected(self, project_id):
        r = SESSION.post(f"{API}/projects/{project_id}/ask", json={"question": "   "})
        assert r.status_code == 400
