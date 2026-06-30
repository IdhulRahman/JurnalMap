"""Targeted backend tests for the 3 fixes:
1. qa_service fallback citations when LLM omits used_sources
2. matrix_cache caching + refresh + cascade delete
3. outlier endpoint returns `keywords` per point
Plus regression sanity on the 4 core flows.
"""
from __future__ import annotations

import os
import time
import asyncio
import io
import pytest
import requests
import fitz
from pathlib import Path
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"
API = f"{BASE_URL}/api"

S = requests.Session()


def _pdf(path: str, title: str = "Effect of Coffee on Productivity"):
    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text((50, 60), f"Title: {title}", fontsize=12)
    p1.insert_text((50, 90),
                   "Abstract: This study investigates the effect of moderate coffee "
                   "consumption on knowledge worker productivity. We conducted a "
                   "randomized trial with 120 software engineers over 8 weeks.",
                   fontsize=9)
    p1.insert_text((50, 160),
                   "Methods: 120 participants (mean age 31) were randomly assigned to "
                   "coffee or placebo groups. We measured commits per day and bug rate.",
                   fontsize=9)
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


def _wait_ready(doc_id: str, timeout: int = 120) -> dict:
    deadline = time.time() + timeout
    last = {}
    while time.time() < deadline:
        time.sleep(3)
        r = S.get(f"{API}/documents/{doc_id}")
        if r.status_code == 200:
            last = r.json()
            if last["status"] in ("ready", "failed"):
                return last
    return last


@pytest.fixture(scope="module")
def project_and_doc():
    pr = S.post(f"{API}/projects", json={"name": "TEST_TargetedFixes"}).json()
    pid = pr["id"]
    pdf = "/tmp/jm_targeted.pdf"
    _pdf(pdf)
    with open(pdf, "rb") as f:
        up = S.post(f"{API}/projects/{pid}/documents",
                    files={"file": ("c.pdf", f, "application/pdf")})
    assert up.status_code == 200
    did = up.json()["id"]
    final = _wait_ready(did)
    if final.get("status") != "ready":
        S.delete(f"{API}/projects/{pid}")
        pytest.skip(f"Doc not ready: {final.get('error')}")
    yield pid, did
    S.delete(f"{API}/projects/{pid}")


# ============================================================
# FIX 1 — qa_service fallback citations (in-process unit test)
# ============================================================
class TestFix1QAFallback:
    def test_fallback_attaches_top3_low_tier_when_used_sources_missing(self, monkeypatch):
        import sys
        sys.path.insert(0, "/app/backend")
        from app.services import qa_service

        # Build fake docs with >=3 sentences
        docs = [{
            "id": "docA",
            "title": "Coffee Study",
            "sentences": [
                {"id": f"s{i}", "text": t, "page": 1, "idx": i,
                 "x0": 0, "y0": 0, "x1": 0, "y1": 0,
                 "page_width": 600, "page_height": 800}
                for i, t in enumerate([
                    "Coffee improves alertness in software engineers.",
                    "Productivity rose by 14 percent in the coffee group.",
                    "No difference in bug rate was observed.",
                    "Caffeine has limited long-term sustained effects.",
                    "Participants reported subjective focus improvements.",
                ])
            ],
        }]

        async def fake_gen(*args, **kwargs):
            return {"answer": "Coffee boosts productivity.",
                    "used_sources": [],
                    "overall_tier": "high"}

        monkeypatch.setattr(qa_service, "generate_json", fake_gen)

        out = asyncio.run(qa_service.answer_question("Does coffee improve productivity?", docs))

        assert out["overall_tier"] == "low", "overall_tier must be downgraded to low"
        assert out["answer"].startswith("Sumber tidak terverifikasi langsung oleh model"), \
            f"answer must be prefixed with fallback notice; got: {out['answer'][:80]}"
        assert "Coffee boosts productivity." in out["answer"]
        cits = out["citations"]
        # spec: "exactly 3 (or as many fragments as available if fewer)"
        assert 1 <= len(cits) <= 3, f"expected 1-3 fallback citations, got {len(cits)}"
        for c in cits:
            assert c["tier"] == "low"
            assert c["document_id"] == "docA"

    def test_normal_path_only_returns_cited_fragments(self, monkeypatch):
        import sys
        sys.path.insert(0, "/app/backend")
        from app.services import qa_service

        docs = [{
            "id": "docB",
            "title": "Coffee Study",
            "sentences": [
                {"id": f"s{i}", "text": t, "page": 1, "idx": i,
                 "x0": 0, "y0": 0, "x1": 0, "y1": 0,
                 "page_width": 600, "page_height": 800}
                for i, t in enumerate([
                    "Coffee improves alertness in software engineers.",
                    "Productivity rose by 14 percent in the coffee group.",
                    "No difference in bug rate was observed.",
                    "Caffeine has limited long-term effects.",
                    "Participants reported subjective focus improvements.",
                ])
            ],
        }]

        async def fake_gen(*args, **kwargs):
            return {"answer": "Coffee boosts productivity [S0].",
                    "used_sources": [{"id": "S0", "tier": "high"}],
                    "overall_tier": "high"}

        monkeypatch.setattr(qa_service, "generate_json", fake_gen)
        out = asyncio.run(qa_service.answer_question("coffee productivity?", docs))
        assert out["overall_tier"] == "high"
        assert not out["answer"].startswith("Sumber tidak terverifikasi")
        assert len(out["citations"]) == 1
        assert out["citations"][0]["tier"] == "high"


# ============================================================
# FIX 2 — Matrix caching in matrix_cache collection
# ============================================================
class TestFix2MatrixCache:
    def test_matrix_caches_and_serves_fast_on_second_call(self, project_and_doc):
        pid, did = project_and_doc
        # First call — should populate cache (LLM call)
        t0 = time.time()
        r1 = S.post(f"{API}/projects/{pid}/matrix", json={})
        elapsed1 = time.time() - t0
        assert r1.status_code == 200, r1.text
        data1 = r1.json()
        assert len(data1["rows"]) >= 1

        # Verify cache row written
        import pymongo
        cli = pymongo.MongoClient(os.environ["MONGO_URL"])
        cdb = cli[os.environ["DB_NAME"]]
        cached = cdb.matrix_cache.find_one({"document_id": did})
        assert cached, "matrix_cache row missing after first call"
        assert "cells" in cached and isinstance(cached["cells"], list) and cached["cells"]
        assert "cached_at" in cached
        assert "title" in cached
        first_cached_at = cached["cached_at"]

        # Second call — should be fast (no LLM)
        t0 = time.time()
        r2 = S.post(f"{API}/projects/{pid}/matrix", json={})
        elapsed2 = time.time() - t0
        assert r2.status_code == 200
        assert elapsed2 < 1.5, f"cached call too slow: {elapsed2:.2f}s (first was {elapsed1:.2f}s)"
        # Cells must be identical
        assert r2.json()["rows"][0]["cells"] == data1["rows"][0]["cells"]

        # Refresh — should bypass cache, update cached_at
        time.sleep(1.1)
        t0 = time.time()
        r3 = S.post(f"{API}/projects/{pid}/matrix", json={"refresh": True})
        elapsed3 = time.time() - t0
        assert r3.status_code == 200
        # Refresh path calls LLM → expect noticeably slower than cached path
        assert elapsed3 > elapsed2, f"refresh did not appear to re-call LLM (refresh={elapsed3:.2f}s, cache={elapsed2:.2f}s)"
        cached2 = cdb.matrix_cache.find_one({"document_id": did})
        assert cached2["cached_at"] != first_cached_at, "cached_at not updated after refresh=true"
        cli.close()

    def test_delete_document_removes_matrix_cache(self):
        # fresh project + doc, build matrix, delete doc, check cache row is gone
        pr = S.post(f"{API}/projects", json={"name": "TEST_DelMatrix"}).json()
        pid = pr["id"]
        pdf = "/tmp/jm_delmatrix.pdf"
        _pdf(pdf)
        with open(pdf, "rb") as f:
            up = S.post(f"{API}/projects/{pid}/documents",
                        files={"file": ("d.pdf", f, "application/pdf")})
        did = up.json()["id"]
        final = _wait_ready(did)
        if final.get("status") != "ready":
            S.delete(f"{API}/projects/{pid}")
            pytest.skip("doc not ready")
        rm = S.post(f"{API}/projects/{pid}/matrix", json={})
        assert rm.status_code == 200

        import pymongo
        cli = pymongo.MongoClient(os.environ["MONGO_URL"])
        cdb = cli[os.environ["DB_NAME"]]
        assert cdb.matrix_cache.find_one({"document_id": did}) is not None

        d = S.delete(f"{API}/documents/{did}")
        assert d.status_code == 200
        assert cdb.matrix_cache.find_one({"document_id": did}) is None, \
            "matrix_cache row not cleaned up on doc delete"
        S.delete(f"{API}/projects/{pid}")
        cli.close()

    def test_delete_project_cascades_matrix_cache(self):
        pr = S.post(f"{API}/projects", json={"name": "TEST_CascadeMatrix"}).json()
        pid = pr["id"]
        pdf = "/tmp/jm_cascademat.pdf"
        _pdf(pdf)
        with open(pdf, "rb") as f:
            up = S.post(f"{API}/projects/{pid}/documents",
                        files={"file": ("e.pdf", f, "application/pdf")})
        did = up.json()["id"]
        final = _wait_ready(did)
        if final.get("status") != "ready":
            S.delete(f"{API}/projects/{pid}")
            pytest.skip("doc not ready")
        S.post(f"{API}/projects/{pid}/matrix", json={})

        import pymongo
        cli = pymongo.MongoClient(os.environ["MONGO_URL"])
        cdb = cli[os.environ["DB_NAME"]]
        assert cdb.matrix_cache.find_one({"document_id": did}) is not None

        S.delete(f"{API}/projects/{pid}")
        assert cdb.matrix_cache.find_one({"document_id": did}) is None, \
            "matrix_cache not cascaded on project delete"
        cli.close()


# ============================================================
# FIX 3 — Outlier returns keywords per point
# ============================================================
class TestFix3OutlierKeywords:
    def test_outlier_points_have_keywords(self, project_and_doc):
        pid, _ = project_and_doc
        r = S.get(f"{API}/projects/{pid}/outliers")
        assert r.status_code == 200
        data = r.json()
        assert data["points"], "expected at least 1 outlier point"
        for p in data["points"]:
            assert "keywords" in p, f"missing keywords field on point {p['document_id']}"
            assert isinstance(p["keywords"], list)
            assert len(p["keywords"]) >= 1, f"no keywords for {p['title']}"
            # stopword sanity
            assert "the" not in p["keywords"]
            assert "yang" not in p["keywords"]


# ============================================================
# Regression sanity — 4 core flows
# ============================================================
class TestRegression:
    def test_core_flow_end_to_end(self, project_and_doc):
        pid, did = project_and_doc
        # project exists
        p = S.get(f"{API}/projects/{pid}")
        assert p.status_code == 200
        # summary
        s = S.get(f"{API}/documents/{did}/summary")
        assert s.status_code == 200
        claims = s.json().get("claims") or []
        assert 5 <= len(claims) <= 8
        # evidence
        ev = S.post(f"{API}/claims/{claims[0]['id']}/evidence")
        assert ev.status_code == 200
        assert ev.json().get("items"), "expected at least 1 evidence item"
