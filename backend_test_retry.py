#!/usr/bin/env python3
"""
Retry upload and downstream tests for JurnalMap API.
"""
import requests
import time
import sys

BASE_URL = "https://8ae4e47a-c558-4ee8-a207-6fce7d1b5e4d.preview.emergentagent.com/api"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin"
DEMO_PDFS = [
    "/tmp/demo_pdfs/doc1.pdf",
    "/tmp/demo_pdfs/doc2.pdf",
    "/tmp/demo_pdfs/doc3.pdf",
]

test_results = []

def log_test(name: str, passed: bool, details: str = ""):
    status = "✅ PASS" if passed else "❌ FAIL"
    test_results.append({"name": name, "passed": passed, "details": details})
    print(f"{status}: {name}")
    if details:
        print(f"  Details: {details}")

def main():
    print("=" * 80)
    print("JurnalMap Backend Test - Upload Retry")
    print("=" * 80)
    print()
    
    # Login as admin
    try:
        resp = requests.post(
            f"{BASE_URL}/auth/login",
            json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
            timeout=10,
        )
        if resp.status_code != 200:
            print(f"❌ Failed to login as admin: {resp.status_code}")
            return 1
        admin_token = resp.json()["access_token"]
        print("✅ Logged in as admin")
    except Exception as e:
        print(f"❌ Exception during login: {e}")
        return 1
    
    # Create fresh project
    try:
        resp = requests.post(
            f"{BASE_URL}/projects",
            json={"name": "DemoProject2", "description": "Retry upload test"},
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10,
        )
        if resp.status_code != 200:
            print(f"❌ Failed to create project: {resp.status_code}")
            return 1
        proj_id = resp.json()["id"]
        log_test("Create DemoProject2", True, f"Created project {proj_id}")
    except Exception as e:
        log_test("Create DemoProject2", False, f"Exception: {e}")
        return 1
    
    # Upload 3 PDFs
    try:
        files = [
            ("files", ("doc1.pdf", open(DEMO_PDFS[0], "rb"), "application/pdf")),
            ("files", ("doc2.pdf", open(DEMO_PDFS[1], "rb"), "application/pdf")),
            ("files", ("doc3.pdf", open(DEMO_PDFS[2], "rb"), "application/pdf")),
        ]
        resp = requests.post(
            f"{BASE_URL}/projects/{proj_id}/documents",
            files=files,
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=60,
        )
        for _, (_, fh, _) in files:
            fh.close()
        
        if resp.status_code == 200:
            docs = resp.json()
            if len(docs) == 3:
                doc_ids = [d["id"] for d in docs]
                log_test("Upload 3 PDFs (retry)", True, f"Uploaded: {doc_ids}")
            else:
                log_test("Upload 3 PDFs (retry)", False, f"Expected 3 docs, got {len(docs)}")
                return 1
        else:
            log_test("Upload 3 PDFs (retry)", False, f"Status {resp.status_code}: {resp.text}")
            return 1
    except Exception as e:
        log_test("Upload 3 PDFs (retry)", False, f"Exception: {e}")
        return 1
    
    # Poll for ready (max 5 minutes)
    print("  Polling for documents to become ready (max 5 minutes)...")
    max_wait = 300
    poll_interval = 5
    elapsed = 0
    all_ready = False
    
    while elapsed < max_wait:
        try:
            resp = requests.get(
                f"{BASE_URL}/projects/{proj_id}/documents",
                headers={"Authorization": f"Bearer {admin_token}"},
                timeout=10,
            )
            if resp.status_code == 200:
                docs = resp.json()
                statuses = {d["id"]: d["status"] for d in docs}
                ready_count = sum(1 for s in statuses.values() if s == "ready")
                failed_count = sum(1 for s in statuses.values() if s == "failed")
                
                print(f"    [{elapsed}s] Ready: {ready_count}/3, Failed: {failed_count}/3")
                
                if failed_count > 0:
                    failed_docs = [d for d in docs if d["status"] == "failed"]
                    log_test("Document processing (retry)", False, f"Failed docs: {[d['filename'] + ': ' + d.get('error', 'No error')[:100] for d in failed_docs]}")
                    # Don't return yet, continue to test what we can
                    break
                
                if ready_count == 3:
                    all_ready = True
                    log_test("Document processing (retry - all ready)", True, f"All 3 documents ready")
                    break
        except Exception as e:
            print(f"    Polling error: {e}")
        
        time.sleep(poll_interval)
        elapsed += poll_interval
    
    if not all_ready and elapsed >= max_wait:
        log_test("Document processing (retry - timeout)", False, f"Timeout after {max_wait}s")
        return 1
    
    # Get final document list
    try:
        resp = requests.get(
            f"{BASE_URL}/projects/{proj_id}/documents",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10,
        )
        docs = resp.json()
        doc_ids = [d["id"] for d in docs if d["status"] == "ready"]
        print(f"\n  Ready documents: {len(doc_ids)}/3")
    except Exception as e:
        print(f"❌ Failed to get document list: {e}")
        return 1
    
    if len(doc_ids) == 0:
        print("❌ No documents ready, skipping downstream tests")
        return 1
    
    # Test downstream endpoints with available documents
    print("\n### Downstream Endpoints")
    
    # Test GET /documents/{id}/summary
    for doc_id in doc_ids:
        try:
            resp = requests.get(
                f"{BASE_URL}/documents/{doc_id}/summary",
                headers={"Authorization": f"Bearer {admin_token}"},
                timeout=10,
            )
            if resp.status_code == 200:
                body = resp.json()
                required_keys = ["title", "summary", "sections", "claims", "status"]
                if all(k in body for k in required_keys) and body["status"] == "ready":
                    log_test(f"GET /documents/{{id}}/summary (doc {doc_ids.index(doc_id)+1})", True, f"All keys present")
                else:
                    log_test(f"GET /documents/{{id}}/summary (doc {doc_ids.index(doc_id)+1})", False, f"Missing keys or wrong status")
            else:
                log_test(f"GET /documents/{{id}}/summary (doc {doc_ids.index(doc_id)+1})", False, f"Status {resp.status_code}")
        except Exception as e:
            log_test(f"GET /documents/{{id}}/summary (doc {doc_ids.index(doc_id)+1})", False, f"Exception: {e}")
    
    # Test GET /documents/{id}/status
    try:
        resp = requests.get(
            f"{BASE_URL}/documents/{doc_ids[0]}/status",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10,
        )
        if resp.status_code == 200:
            body = resp.json()
            if "summary" in body and body.get("status") == "ready":
                log_test("GET /documents/{id}/status", True, f"Has summary object")
            else:
                log_test("GET /documents/{id}/status", False, f"Missing summary or wrong status")
        else:
            log_test("GET /documents/{id}/status", False, f"Status {resp.status_code}")
    except Exception as e:
        log_test("GET /documents/{id}/status", False, f"Exception: {e}")
    
    # Test POST /claims/{claim_id}/evidence
    try:
        resp = requests.get(
            f"{BASE_URL}/documents/{doc_ids[0]}/summary",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10,
        )
        claims = resp.json().get("claims", [])
        if claims:
            claim_id = claims[0]["id"]
            resp = requests.post(
                f"{BASE_URL}/claims/{claim_id}/evidence",
                headers={"Authorization": f"Bearer {admin_token}"},
                timeout=30,
            )
            if resp.status_code == 200:
                body = resp.json()
                if "items" in body:
                    log_test("POST /claims/{claim_id}/evidence", True, f"Got items array (len={len(body['items'])})")
                else:
                    log_test("POST /claims/{claim_id}/evidence", False, f"Missing items")
            else:
                log_test("POST /claims/{claim_id}/evidence", False, f"Status {resp.status_code}")
        else:
            log_test("POST /claims/{claim_id}/evidence", False, f"No claims found")
    except Exception as e:
        log_test("POST /claims/{claim_id}/evidence", False, f"Exception: {e}")
    
    # Test POST /documents/{id}/section-evidence
    if len(doc_ids) >= 2:
        try:
            resp = requests.post(
                f"{BASE_URL}/documents/{doc_ids[1]}/section-evidence",
                json={"text": "blockchain trust management"},
                headers={"Authorization": f"Bearer {admin_token}"},
                timeout=30,
            )
            if resp.status_code == 200:
                body = resp.json()
                if "items" in body:
                    log_test("POST /documents/{id}/section-evidence", True, f"Got items array (len={len(body['items'])})")
                else:
                    log_test("POST /documents/{id}/section-evidence", False, f"Missing items")
            else:
                log_test("POST /documents/{id}/section-evidence", False, f"Status {resp.status_code}")
        except Exception as e:
            log_test("POST /documents/{id}/section-evidence", False, f"Exception: {e}")
    
    # Test GET /projects/{proj_id}/outliers
    try:
        resp = requests.get(
            f"{BASE_URL}/projects/{proj_id}/outliers",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=30,
        )
        if resp.status_code == 200:
            body = resp.json()
            if "points" in body and len(body["points"]) == len(doc_ids):
                log_test("GET /projects/{proj_id}/outliers", True, f"Got {len(body['points'])} points")
            else:
                log_test("GET /projects/{proj_id}/outliers", False, f"Expected {len(doc_ids)} points, got {len(body.get('points', []))}")
        else:
            log_test("GET /projects/{proj_id}/outliers", False, f"Status {resp.status_code}")
    except Exception as e:
        log_test("GET /projects/{proj_id}/outliers", False, f"Exception: {e}")
    
    # Test POST /projects/{proj_id}/matrix
    try:
        resp = requests.post(
            f"{BASE_URL}/projects/{proj_id}/matrix",
            json={},
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=60,
        )
        if resp.status_code == 200:
            body = resp.json()
            if "fields" in body and "rows" in body and len(body["rows"]) == len(doc_ids):
                log_test("POST /projects/{proj_id}/matrix", True, f"Got fields and {len(body['rows'])} rows")
            else:
                log_test("POST /projects/{proj_id}/matrix", False, f"Expected {len(doc_ids)} rows, got {len(body.get('rows', []))}")
        else:
            log_test("POST /projects/{proj_id}/matrix", False, f"Status {resp.status_code}")
    except Exception as e:
        log_test("POST /projects/{proj_id}/matrix", False, f"Exception: {e}")
    
    # Test POST /projects/{proj_id}/ask
    try:
        resp = requests.post(
            f"{BASE_URL}/projects/{proj_id}/ask",
            json={"question": "What methods are used for trust management?"},
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=60,
        )
        if resp.status_code == 200:
            body = resp.json()
            required_keys = ["answer", "citations", "overall_tier"]
            if all(k in body for k in required_keys):
                log_test("POST /projects/{proj_id}/ask", True, f"Got all required keys")
            else:
                log_test("POST /projects/{proj_id}/ask", False, f"Missing keys")
        else:
            log_test("POST /projects/{proj_id}/ask", False, f"Status {resp.status_code}")
    except Exception as e:
        log_test("POST /projects/{proj_id}/ask", False, f"Exception: {e}")
    
    # Test POST /projects/{proj_id}/check
    try:
        resp = requests.post(
            f"{BASE_URL}/projects/{proj_id}/check",
            json={"text": "Blockchain provides tamper-resistant trust in federated learning."},
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=60,
        )
        if resp.status_code == 200:
            body = resp.json()
            required_keys = ["units", "summary", "annotated_html", "badges", "references_used"]
            if all(k in body for k in required_keys):
                log_test("POST /projects/{proj_id}/check", True, f"Got all required keys")
            else:
                log_test("POST /projects/{proj_id}/check", False, f"Missing keys")
        else:
            log_test("POST /projects/{proj_id}/check", False, f"Status {resp.status_code}")
    except Exception as e:
        log_test("POST /projects/{proj_id}/check", False, f"Exception: {e}")
    
    # Cleanup
    try:
        resp = requests.delete(
            f"{BASE_URL}/projects/{proj_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10,
        )
        if resp.status_code == 200:
            log_test("DELETE DemoProject2", True, f"Deleted successfully")
        else:
            log_test("DELETE DemoProject2", False, f"Status {resp.status_code}")
    except Exception as e:
        log_test("DELETE DemoProject2", False, f"Exception: {e}")
    
    # Summary
    print("\n" + "=" * 80)
    print("Test Summary (Retry)")
    print("=" * 80)
    passed = sum(1 for r in test_results if r["passed"])
    failed = sum(1 for r in test_results if not r["passed"])
    total = len(test_results)
    
    print(f"Total: {total}, Passed: {passed}, Failed: {failed}")
    
    if failed > 0:
        print("\nFailed tests:")
        for r in test_results:
            if not r["passed"]:
                print(f"  ❌ {r['name']}")
                if r["details"]:
                    print(f"     {r['details'][:200]}")
    
    print("=" * 80)
    
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
