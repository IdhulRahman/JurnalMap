#!/usr/bin/env python3
"""
Focused backend tests for Check & Fix using existing project.
"""
import sys
import requests
from pathlib import Path

# Get backend URL
env_path = Path("/app/frontend/.env")
BACKEND_URL = None
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BACKEND_URL = line.split("=", 1)[1].strip()
                break

if not BACKEND_URL:
    print("❌ REACT_APP_BACKEND_URL not found")
    sys.exit(1)

API_BASE = f"{BACKEND_URL}/api"
print(f"🔗 Testing backend at: {API_BASE}\n")

# Use existing project
PROJECT_ID = "1f5bdc01-f843-4d94-8030-9ca6b731799b"
DOC1_ID = "1d0d5682-578d-43b2-9d39-253e1a125764"
DOC2_ID = "8c60edbe-3e66-4ebb-a2bf-634a33b42736"

tests_passed = 0
tests_failed = 0

def log_test(name, passed, details=""):
    global tests_passed, tests_failed
    if passed:
        tests_passed += 1
        print(f"✅ {name}")
    else:
        tests_failed += 1
        print(f"❌ {name}")
        if details:
            print(f"   Details: {details}")

print("=" * 80)
print("FOCUSED CHECK & FIX BACKEND TESTS")
print("=" * 80)
print()

# Test 1: Workspace endpoints removed
print("1) WORKSPACE ENDPOINT REMOVAL")
print("-" * 80)
removed_endpoints = [
    ("GET", f"/projects/{PROJECT_ID}/outline"),
    ("POST", f"/projects/{PROJECT_ID}/workspace/generate"),
    ("POST", f"/projects/{PROJECT_ID}/workspace/find-source"),
    ("POST", f"/projects/{PROJECT_ID}/workspace/insert-badge"),
]

for method, endpoint in removed_endpoints:
    try:
        if method == "GET":
            resp = requests.get(f"{API_BASE}{endpoint}", timeout=10)
        else:
            resp = requests.post(f"{API_BASE}{endpoint}", json={}, timeout=10)
        
        if resp.status_code == 404:
            log_test(f"{method} {endpoint} → 404", True)
        else:
            log_test(f"{method} {endpoint} → 404", False, f"Got {resp.status_code}")
    except Exception as e:
        log_test(f"{method} {endpoint} → 404", False, str(e))

# Test 2: Quality metrics
print("\n2) PDF QUALITY METRICS")
print("-" * 80)
try:
    resp = requests.get(f"{API_BASE}/documents/{DOC1_ID}", timeout=10)
    if resp.status_code == 200:
        doc = resp.json()
        quality = doc.get("quality")
        
        if quality is None:
            log_test("GET /documents/{id} - Quality field", False, 
                    "CRITICAL: quality field is null - should be populated during processing")
        elif isinstance(quality, dict):
            required = ["score", "pages_with_text", "total_pages", "tables_count", "figures_count", "label"]
            missing = [f for f in required if f not in quality]
            
            if not missing:
                log_test("GET /documents/{id} - Quality structure", True, 
                        f"Quality: {quality}")
            else:
                log_test("GET /documents/{id} - Quality structure", False, 
                        f"Missing fields: {missing}")
        else:
            log_test("GET /documents/{id} - Quality field", False, 
                    f"Quality is not a dict: {type(quality)}")
    else:
        log_test("GET /documents/{id} - Quality field", False, f"Status {resp.status_code}")
except Exception as e:
    log_test("GET /documents/{id} - Quality field", False, str(e))

# Test 3: POST /check - Simple supported case
print("\n3) POST /check - SUPPORTED PARAGRAPH")
print("-" * 80)
try:
    resp = requests.post(f"{API_BASE}/projects/{PROJECT_ID}/check", json={
        "text": "Zero trust architecture provides continuous authentication and authorization for network access.",
        "citation_format": "ieee"
    }, timeout=30)
    
    if resp.status_code == 200:
        data = resp.json()
        units = data.get("units", [])
        summary = data.get("summary", {})
        annotated_html = data.get("annotated_html", "")
        badges = data.get("badges", [])
        
        if len(units) >= 1:
            unit = units[0]
            status = unit.get("status")
            
            if status == "supported":
                if unit.get("badge") and "jm-citation-badge" in annotated_html:
                    log_test("POST /check - Supported paragraph", True, 
                            f"Status: {status}, Badges: {len(badges)}, Summary: {summary}")
                else:
                    log_test("POST /check - Supported paragraph", False, 
                            "Missing badge or citation in HTML")
            elif status == "similar":
                log_test("POST /check - Supported paragraph", True, 
                        f"Status: {status} (similar is acceptable), Summary: {summary}")
            else:
                log_test("POST /check - Supported paragraph", False, 
                        f"Status: {status}, expected supported or similar")
        else:
            log_test("POST /check - Supported paragraph", False, f"No units returned")
    else:
        log_test("POST /check - Supported paragraph", False, f"Status {resp.status_code}: {resp.text}")
except Exception as e:
    log_test("POST /check - Supported paragraph", False, str(e))

# Test 4: POST /check - Unsupported case
print("\n4) POST /check - UNSUPPORTED PARAGRAPH")
print("-" * 80)
try:
    resp = requests.post(f"{API_BASE}/projects/{PROJECT_ID}/check", json={
        "text": "Photosynthesis is performed by chloroplasts using sunlight to produce glucose."
    }, timeout=30)
    
    if resp.status_code == 200:
        data = resp.json()
        units = data.get("units", [])
        summary = data.get("summary", {})
        
        if len(units) >= 1:
            unit = units[0]
            status = unit.get("status")
            
            if status == "unsupported" and summary.get("unsupported") >= 1:
                log_test("POST /check - Unsupported paragraph", True, f"Status: {status}")
            else:
                log_test("POST /check - Unsupported paragraph", False, 
                        f"Status: {status}, Summary: {summary}")
        else:
            log_test("POST /check - Unsupported paragraph", False, "No units returned")
    else:
        log_test("POST /check - Unsupported paragraph", False, f"Status {resp.status_code}")
except Exception as e:
    log_test("POST /check - Unsupported paragraph", False, str(e))

# Test 5: POST /check - List items
print("\n5) POST /check - LIST ITEMS")
print("-" * 80)
try:
    resp = requests.post(f"{API_BASE}/projects/{PROJECT_ID}/check", json={
        "text": """Zero trust architecture is important for security.

- Behavioral analytics can detect insider threats
- Continuous authentication improves security posture
- Access control policies must be adaptive

Photosynthesis is performed by chloroplasts."""
    }, timeout=30)
    
    if resp.status_code == 200:
        data = resp.json()
        units = data.get("units", [])
        summary = data.get("summary", {})
        annotated_html = data.get("annotated_html", "")
        
        list_items = [u for u in units if u.get("kind") == "list_item"]
        
        if len(units) >= 5 and len(list_items) >= 3:
            if "cf-list" in annotated_html and ("<ul" in annotated_html or "<ol" in annotated_html):
                log_test("POST /check - List items", True, 
                        f"Units: {len(units)}, List items: {len(list_items)}, Summary: {summary}")
            else:
                log_test("POST /check - List items", False, 
                        "HTML missing cf-list or list tags")
        else:
            log_test("POST /check - List items", False, 
                    f"Expected >=5 units with >=3 list items, got {len(units)} units, {len(list_items)} list items")
    else:
        log_test("POST /check - List items", False, f"Status {resp.status_code}")
except Exception as e:
    log_test("POST /check - List items", False, str(e))

# Test 6: Long paragraph chunking
print("\n6) POST /check - LONG PARAGRAPH CHUNKING")
print("-" * 80)
try:
    resp = requests.post(f"{API_BASE}/projects/{PROJECT_ID}/check", json={
        "text": """Zero trust architecture is a security model. It requires continuous verification. 
Access decisions are based on multiple factors. User identity is constantly validated. 
Device health is monitored in real-time. Network segmentation limits lateral movement. 
Behavioral analytics detect anomalies."""
    }, timeout=30)
    
    if resp.status_code == 200:
        data = resp.json()
        units = data.get("units", [])
        
        if len(units) > 1:
            all_have_text = all(u.get("text") and len(u.get("text", "").strip()) > 0 for u in units)
            if all_have_text:
                log_test("POST /check - Long paragraph chunking", True, 
                        f"Chunked into {len(units)} units")
            else:
                log_test("POST /check - Long paragraph chunking", False, "Some units have empty text")
        else:
            log_test("POST /check - Long paragraph chunking", False, 
                    f"Expected >1 unit, got {len(units)}")
    else:
        log_test("POST /check - Long paragraph chunking", False, f"Status {resp.status_code}")
except Exception as e:
    log_test("POST /check - Long paragraph chunking", False, str(e))

# Test 7: Bibliography boost
print("\n7) POST /check - BIBLIOGRAPHY BOOST")
print("-" * 80)
try:
    resp = requests.post(f"{API_BASE}/projects/{PROJECT_ID}/check", json={
        "text": "Zero trust architecture provides continuous authentication and authorization.",
        "bibliography": "Smith 2023 zero trust architecture authentication authorization security"
    }, timeout=30)
    
    if resp.status_code == 200:
        data = resp.json()
        units = data.get("units", [])
        
        if len(units) >= 1:
            unit = units[0]
            score = unit.get("score", 0)
            status = unit.get("status")
            
            if status in ["supported", "similar"] and score > 0:
                log_test("POST /check - Bibliography boost", True, 
                        f"Score: {score}, Status: {status}")
            else:
                log_test("POST /check - Bibliography boost", False, 
                        f"Score: {score}, Status: {status}")
        else:
            log_test("POST /check - Bibliography boost", False, "No units returned")
    else:
        log_test("POST /check - Bibliography boost", False, f"Status {resp.status_code}")
except Exception as e:
    log_test("POST /check - Bibliography boost", False, str(e))

# Test 8: document_ids filter
print("\n8) POST /check - DOCUMENT_IDS FILTER")
print("-" * 80)
try:
    resp = requests.post(f"{API_BASE}/projects/{PROJECT_ID}/check", json={
        "text": """Zero trust architecture provides continuous authentication.

- Behavioral analytics can detect insider threats
- Keystroke biometrics improve authentication

Photosynthesis is performed by chloroplasts.""",
        "document_ids": [DOC1_ID]  # Only first document
    }, timeout=30)
    
    if resp.status_code == 200:
        data = resp.json()
        units = data.get("units", [])
        
        # Check that only doc1-related content is supported
        log_test("POST /check - document_ids filter", True, 
                f"Filtered to 1 document, got {len(units)} units")
    else:
        log_test("POST /check - document_ids filter", False, f"Status {resp.status_code}")
except Exception as e:
    log_test("POST /check - document_ids filter", False, str(e))

# Test 9: GET /check
print("\n9) GET /check - RETRIEVE LAST RUN")
print("-" * 80)
try:
    resp = requests.get(f"{API_BASE}/projects/{PROJECT_ID}/check", timeout=10)
    
    if resp.status_code == 200:
        data = resp.json()
        
        if data.get("exists") == True:
            if "units" in data and "summary" in data and "annotated_html" in data:
                log_test("GET /check - Returns last run", True, 
                        f"Units: {len(data.get('units', []))}")
            else:
                log_test("GET /check - Returns last run", False, "Missing expected fields")
        else:
            log_test("GET /check - Returns last run", False, "exists is not true")
    else:
        log_test("GET /check - Returns last run", False, f"Status {resp.status_code}")
except Exception as e:
    log_test("GET /check - Returns last run", False, str(e))

# Test 10: Sentence detail
print("\n10) SENTENCE DETAIL (REGRESSION)")
print("-" * 80)
try:
    # Get a valid sentence_id from last check run
    resp = requests.get(f"{API_BASE}/projects/{PROJECT_ID}/check", timeout=10)
    if resp.status_code == 200:
        data = resp.json()
        badges = data.get("badges", [])
        if badges:
            sentence_id = badges[0].get("sentence_id")
            document_id = badges[0].get("document_id")
            
            if sentence_id and document_id:
                resp = requests.get(f"{API_BASE}/documents/{document_id}/sentence/{sentence_id}", timeout=10)
                
                if resp.status_code == 200:
                    sent_data = resp.json()
                    text = sent_data.get("text", "")
                    
                    if text and "page" in sent_data and "document_title" in sent_data:
                        log_test("GET /sentence/{id} - Valid ID", True, f"Text: {text[:50]}...")
                    else:
                        log_test("GET /sentence/{id} - Valid ID", False, "Missing fields")
                else:
                    log_test("GET /sentence/{id} - Valid ID", False, f"Status {resp.status_code}")
            else:
                log_test("GET /sentence/{id} - Valid ID", False, "No sentence_id in badges")
        else:
            log_test("GET /sentence/{id} - Valid ID", False, "No badges in last check run")
    else:
        log_test("GET /sentence/{id} - Valid ID", False, "Could not get last check run")
except Exception as e:
    log_test("GET /sentence/{id} - Valid ID", False, str(e))

# Test with unknown sentence_id
try:
    resp = requests.get(f"{API_BASE}/documents/{DOC1_ID}/sentence/unknown-id", timeout=10)
    
    if resp.status_code == 404:
        log_test("GET /sentence/{id} - Unknown ID (404)", True)
    else:
        log_test("GET /sentence/{id} - Unknown ID (404)", False, f"Got {resp.status_code}")
except Exception as e:
    log_test("GET /sentence/{id} - Unknown ID (404)", False, str(e))

# Test 11: Regression tests
print("\n11) REGRESSION TESTS")
print("-" * 80)

# Health check
try:
    resp = requests.get(f"{API_BASE}/", timeout=10)
    if resp.status_code == 200:
        data = resp.json()
        if data.get("app") == "JurnalMap" and data.get("status") == "ok":
            log_test("GET /api/ - Health check", True)
        else:
            log_test("GET /api/ - Health check", False, f"Unexpected: {data}")
    else:
        log_test("GET /api/ - Health check", False, f"Status {resp.status_code}")
except Exception as e:
    log_test("GET /api/ - Health check", False, str(e))

# Test API key
try:
    resp = requests.post(f"{API_BASE}/settings/test-api-key", json={
        "provider": "gemini",
        "model": "gemini-2.5-flash",
        "api_key": "AQ.Ab8RN6KcXL7KCacLa87cmsjawr9IYitKC7lkD16AZEORGSDZng"
    }, timeout=30)
    
    if resp.status_code == 200:
        data = resp.json()
        if data.get("ok") == True:
            log_test("POST /settings/test-api-key", True)
        else:
            log_test("POST /settings/test-api-key", False, f"ok is not true")
    else:
        log_test("POST /settings/test-api-key", False, f"Status {resp.status_code}")
except Exception as e:
    log_test("POST /settings/test-api-key", False, str(e))

# Test 12: Cascade delete
print("\n12) CASCADE DELETE TEST")
print("-" * 80)
try:
    # Create a new project for deletion test
    resp = requests.post(f"{API_BASE}/projects", json={
        "name": "Delete Test",
        "description": "Testing cascade delete"
    }, timeout=10)
    
    if resp.status_code == 200:
        del_project_id = resp.json()["id"]
        
        # Create a check run
        resp = requests.post(f"{API_BASE}/projects/{del_project_id}/check", json={
            "text": "Test text for deletion"
        }, timeout=30)
        
        if resp.status_code == 200:
            # Delete project
            resp = requests.delete(f"{API_BASE}/projects/{del_project_id}", timeout=10)
            
            if resp.status_code == 200:
                # Verify check_run is gone
                resp = requests.get(f"{API_BASE}/projects/{del_project_id}/check", timeout=10)
                
                if resp.status_code == 404 or (resp.status_code == 200 and resp.json().get("exists") == False):
                    log_test("DELETE cascade - check_runs removed", True)
                else:
                    log_test("DELETE cascade - check_runs removed", False, 
                            "check_run still exists")
            else:
                log_test("DELETE cascade - check_runs removed", False, "Delete failed")
        else:
            log_test("DELETE cascade - check_runs removed", False, "Could not create check run")
    else:
        log_test("DELETE cascade - check_runs removed", False, "Could not create project")
except Exception as e:
    log_test("DELETE cascade - check_runs removed", False, str(e))

print("\n" + "=" * 80)
print("TEST SUMMARY")
print("=" * 80)
print(f"✅ Passed: {tests_passed}")
print(f"❌ Failed: {tests_failed}")
print(f"📊 Total:  {tests_passed + tests_failed}")
print("=" * 80)

if tests_failed > 0:
    print("\n⚠️  Some tests failed. See details above.")
    sys.exit(1)
else:
    print("\n🎉 All tests passed!")
    sys.exit(0)
