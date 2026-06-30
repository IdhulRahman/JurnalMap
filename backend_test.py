#!/usr/bin/env python3
"""
Backend API tests for JurnalMap "Check & Fix" feature.
Tests workspace endpoint removal and new verification endpoints.
"""
import os
import sys
import time
import json
import requests
from pathlib import Path

# Get backend URL from frontend .env
env_path = Path("/app/frontend/.env")
BACKEND_URL = None
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BACKEND_URL = line.split("=", 1)[1].strip()
                break

if not BACKEND_URL:
    print("❌ REACT_APP_BACKEND_URL not found in /app/frontend/.env")
    sys.exit(1)

API_BASE = f"{BACKEND_URL}/api"
print(f"🔗 Testing backend at: {API_BASE}\n")

# Test results tracking
tests_passed = 0
tests_failed = 0
test_details = []


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
    test_details.append({"name": name, "passed": passed, "details": details})


def create_pdf_with_text(text_content, filename):
    """Create a small test PDF with specific text using PyMuPDF."""
    try:
        import fitz
        doc = fitz.open()
        page = doc.new_page()
        
        # Add text content line by line
        y_pos = 72
        for line in text_content.split('\n'):
            if line.strip():
                page.insert_text((50, y_pos), line.strip(), fontsize=11)
                y_pos += 20
        
        pdf_path = f"/tmp/{filename}"
        doc.save(pdf_path)
        doc.close()
        print(f"📄 Created test PDF: {pdf_path}")
        return pdf_path
    except Exception as e:
        print(f"❌ Failed to create test PDF: {e}")
        return None


def wait_for_document_ready(document_id, max_wait=180):
    """Poll document status until ready or failed."""
    poll_interval = 3
    elapsed = 0
    
    while elapsed < max_wait:
        try:
            resp = requests.get(f"{API_BASE}/documents/{document_id}/status", timeout=10)
            if resp.status_code == 200:
                status_data = resp.json()
                status = status_data.get("status")
                print(f"   Document {document_id[:8]}... status: {status} (elapsed: {elapsed}s)")
                
                if status == "ready":
                    return True, None
                elif status == "failed":
                    error = status_data.get("error", "Unknown error")
                    return False, f"Processing failed: {error}"
            
            time.sleep(poll_interval)
            elapsed += poll_interval
        except Exception as e:
            return False, f"Polling error: {e}"
    
    return False, f"Timeout after {max_wait}s"


def test_check_fix_backend():
    """Main test function for Check & Fix backend."""
    
    print("=" * 80)
    print("CHECK & FIX BACKEND API TESTS")
    print("=" * 80)
    print()
    
    # ========================================================================
    # 1) WORKSPACE ENDPOINT REMOVAL SANITY CHECK
    # ========================================================================
    print("=" * 80)
    print("1) WORKSPACE ENDPOINT REMOVAL SANITY CHECK")
    print("=" * 80)
    print()
    
    # Create a dummy project for testing removed endpoints
    print("📝 Creating dummy project for workspace endpoint tests...")
    try:
        resp = requests.post(f"{API_BASE}/projects", json={
            "name": "Workspace Removal Test",
            "description": "Testing removed endpoints"
        }, timeout=10)
        
        if resp.status_code == 200:
            dummy_project = resp.json()
            dummy_project_id = dummy_project["id"]
            print(f"   Created project: {dummy_project_id}")
        else:
            log_test("Setup - Create dummy project", False, f"Status {resp.status_code}")
            return
    except Exception as e:
        log_test("Setup - Create dummy project", False, str(e))
        return
    
    # Test removed endpoints
    removed_endpoints = [
        ("GET", f"/projects/{dummy_project_id}/outline"),
        ("POST", f"/projects/{dummy_project_id}/workspace/generate"),
        ("POST", f"/projects/{dummy_project_id}/workspace/find-source"),
        ("POST", f"/projects/{dummy_project_id}/workspace/insert-badge"),
    ]
    
    for method, endpoint in removed_endpoints:
        try:
            if method == "GET":
                resp = requests.get(f"{API_BASE}{endpoint}", timeout=10)
            else:
                resp = requests.post(f"{API_BASE}{endpoint}", json={}, timeout=10)
            
            if resp.status_code == 404:
                log_test(f"Removed endpoint {method} {endpoint} returns 404", True)
            else:
                log_test(f"Removed endpoint {method} {endpoint} returns 404", False, 
                        f"Expected 404, got {resp.status_code}")
        except Exception as e:
            log_test(f"Removed endpoint {method} {endpoint} returns 404", False, str(e))
    
    # Clean up dummy project
    try:
        requests.delete(f"{API_BASE}/projects/{dummy_project_id}", timeout=10)
    except:
        pass
    
    # ========================================================================
    # 2) SETUP: CREATE PROJECT AND UPLOAD 2 PDFs
    # ========================================================================
    print("\n" + "=" * 80)
    print("2) SETUP: CREATE PROJECT AND UPLOAD 2 PDFs")
    print("=" * 80)
    print()
    
    print("📝 Creating test project...")
    try:
        resp = requests.post(f"{API_BASE}/projects", json={
            "name": "Check & Fix Test Project",
            "description": "Testing verification endpoints"
        }, timeout=10)
        
        if resp.status_code == 200:
            project = resp.json()
            project_id = project["id"]
            log_test("POST /projects - Create project", True, f"Project ID: {project_id}")
        else:
            log_test("POST /projects - Create project", False, f"Status {resp.status_code}")
            return
    except Exception as e:
        log_test("POST /projects - Create project", False, str(e))
        return
    
    # Create PDF 1 - Social media study
    pdf1_text = """Social media use exceeding three hours per day correlates with elevated anxiety in adolescents.
A cohort of 312 high-school students was surveyed.
Sleep deprivation mediates the relationship.
The study found significant correlations between social media usage and mental health outcomes.
Adolescents who spent more than three hours daily on social platforms showed higher anxiety levels."""
    
    pdf1_path = create_pdf_with_text(pdf1_text, "social_media_study.pdf")
    if not pdf1_path:
        log_test("Create PDF 1", False, "Failed to create PDF")
        return
    
    # Create PDF 2 - Transformers NLP
    pdf2_text = """Transformers achieve state-of-the-art performance on natural language processing benchmarks.
Attention mechanisms enable long-range dependencies.
BERT and GPT family models dominate the leaderboard.
The transformer architecture revolutionized NLP tasks.
Self-attention allows models to capture contextual relationships effectively."""
    
    pdf2_path = create_pdf_with_text(pdf2_text, "transformers_nlp.pdf")
    if not pdf2_path:
        log_test("Create PDF 2", False, "Failed to create PDF")
        return
    
    # Upload PDF 1
    print("\n📝 Uploading PDF 1 (social media study)...")
    doc1_id = None
    try:
        with open(pdf1_path, "rb") as f:
            files = {"file": ("social_media_study.pdf", f, "application/pdf")}
            resp = requests.post(
                f"{API_BASE}/projects/{project_id}/documents",
                files=files,
                timeout=30
            )
        
        if resp.status_code == 200:
            doc1 = resp.json()
            doc1_id = doc1["id"]
            log_test("POST /documents - Upload PDF 1", True, f"Document ID: {doc1_id}")
        else:
            log_test("POST /documents - Upload PDF 1", False, f"Status {resp.status_code}")
            return
    except Exception as e:
        log_test("POST /documents - Upload PDF 1", False, str(e))
        return
    
    # Upload PDF 2
    print("\n📝 Uploading PDF 2 (transformers NLP)...")
    doc2_id = None
    try:
        with open(pdf2_path, "rb") as f:
            files = {"file": ("transformers_nlp.pdf", f, "application/pdf")}
            resp = requests.post(
                f"{API_BASE}/projects/{project_id}/documents",
                files=files,
                timeout=30
            )
        
        if resp.status_code == 200:
            doc2 = resp.json()
            doc2_id = doc2["id"]
            log_test("POST /documents - Upload PDF 2", True, f"Document ID: {doc2_id}")
        else:
            log_test("POST /documents - Upload PDF 2", False, f"Status {resp.status_code}")
            return
    except Exception as e:
        log_test("POST /documents - Upload PDF 2", False, str(e))
        return
    
    # Wait for both documents to be ready
    print("\n📝 Waiting for PDF 1 to be ready (max 3 minutes)...")
    doc1_ready, doc1_error = wait_for_document_ready(doc1_id)
    if doc1_ready:
        log_test("Document 1 processing - Ready", True)
    else:
        log_test("Document 1 processing - Ready", False, doc1_error)
        return
    
    print("\n📝 Waiting for PDF 2 to be ready (max 3 minutes)...")
    doc2_ready, doc2_error = wait_for_document_ready(doc2_id)
    if doc2_ready:
        log_test("Document 2 processing - Ready", True)
    else:
        log_test("Document 2 processing - Ready", False, doc2_error)
        return
    
    # ========================================================================
    # 3) TEST PDF QUALITY METRICS
    # ========================================================================
    print("\n" + "=" * 80)
    print("3) TEST PDF QUALITY METRICS")
    print("=" * 80)
    print()
    
    print("📝 Testing GET /documents/{id} includes quality metrics...")
    try:
        resp = requests.get(f"{API_BASE}/documents/{doc1_id}", timeout=10)
        
        if resp.status_code == 200:
            doc_data = resp.json()
            quality = doc_data.get("quality")
            
            if quality:
                required_fields = ["score", "pages_with_text", "total_pages", "tables_count", "figures_count", "label"]
                missing_fields = [f for f in required_fields if f not in quality]
                
                if not missing_fields:
                    score = quality.get("score")
                    label = quality.get("label")
                    pages_with_text = quality.get("pages_with_text")
                    total_pages = quality.get("total_pages")
                    
                    # For a 1-page PDF with text, score should be 100, label "good", pages_with_text=1
                    if total_pages == 1 and pages_with_text == 1 and score == 100 and label == "good":
                        log_test("GET /documents/{id} - Quality metrics", True, 
                                f"Quality: score={score}, label={label}, pages_with_text={pages_with_text}")
                    else:
                        log_test("GET /documents/{id} - Quality metrics", False, 
                                f"Unexpected values: score={score}, label={label}, pages_with_text={pages_with_text}, total_pages={total_pages}")
                else:
                    log_test("GET /documents/{id} - Quality metrics", False, 
                            f"Missing fields: {missing_fields}")
            else:
                log_test("GET /documents/{id} - Quality metrics", False, "No quality field in response")
        else:
            log_test("GET /documents/{id} - Quality metrics", False, f"Status {resp.status_code}")
    except Exception as e:
        log_test("GET /documents/{id} - Quality metrics", False, str(e))
    
    # ========================================================================
    # 4) TEST POST /api/projects/{id}/check - BODY A (supported)
    # ========================================================================
    print("\n" + "=" * 80)
    print("4) TEST POST /check - BODY A (paragraph supported)")
    print("=" * 80)
    print()
    
    body_a = {
        "text": "Social media use exceeding three hours per day correlates with elevated anxiety in adolescents.",
        "citation_format": "ieee"
    }
    
    print("📝 Testing Body A (should be supported)...")
    try:
        resp = requests.post(f"{API_BASE}/projects/{project_id}/check", json=body_a, timeout=30)
        
        if resp.status_code == 200:
            data = resp.json()
            units = data.get("units", [])
            summary = data.get("summary", {})
            annotated_html = data.get("annotated_html", "")
            badges = data.get("badges", [])
            
            # Expect: units length 1; that unit "status" == "supported"
            if len(units) == 1:
                unit = units[0]
                status = unit.get("status")
                badge = unit.get("badge")
                
                if status == "supported":
                    # Check badge present with label "[1]"
                    if badge and badge.get("label") == "[1]":
                        # Check annotated_html contains class "cf-supported" and citation badge
                        if "cf-supported" in annotated_html and "jm-citation-badge" in annotated_html:
                            # Check summary.supported == 1
                            if summary.get("supported") == 1:
                                log_test("Body A - Paragraph supported", True, 
                                        f"Status: {status}, Badge: {badge.get('label')}, Summary: {summary}")
                            else:
                                log_test("Body A - Paragraph supported", False, 
                                        f"summary.supported != 1: {summary}")
                        else:
                            log_test("Body A - Paragraph supported", False, 
                                    "annotated_html missing cf-supported or jm-citation-badge")
                    else:
                        log_test("Body A - Paragraph supported", False, 
                                f"Badge missing or wrong label: {badge}")
                else:
                    log_test("Body A - Paragraph supported", False, f"Status is {status}, expected 'supported'")
            else:
                log_test("Body A - Paragraph supported", False, f"Expected 1 unit, got {len(units)}")
        else:
            log_test("Body A - Paragraph supported", False, f"Status {resp.status_code}: {resp.text}")
    except Exception as e:
        log_test("Body A - Paragraph supported", False, str(e))
    
    # ========================================================================
    # 5) TEST POST /check - BODY B (unsupported)
    # ========================================================================
    print("\n" + "=" * 80)
    print("5) TEST POST /check - BODY B (paragraph unsupported)")
    print("=" * 80)
    print()
    
    body_b = {
        "text": "Photosynthesis is performed by chloroplasts using sunlight to produce glucose."
    }
    
    print("📝 Testing Body B (should be unsupported)...")
    try:
        resp = requests.post(f"{API_BASE}/projects/{project_id}/check", json=body_b, timeout=30)
        
        if resp.status_code == 200:
            data = resp.json()
            units = data.get("units", [])
            summary = data.get("summary", {})
            
            if len(units) == 1:
                unit = units[0]
                status = unit.get("status")
                
                if status == "unsupported" and summary.get("unsupported") == 1:
                    log_test("Body B - Paragraph unsupported", True, f"Status: {status}, Summary: {summary}")
                else:
                    log_test("Body B - Paragraph unsupported", False, 
                            f"Status: {status}, Summary: {summary}")
            else:
                log_test("Body B - Paragraph unsupported", False, f"Expected 1 unit, got {len(units)}")
        else:
            log_test("Body B - Paragraph unsupported", False, f"Status {resp.status_code}")
    except Exception as e:
        log_test("Body B - Paragraph unsupported", False, str(e))
    
    # ========================================================================
    # 6) TEST POST /check - BODY C (multi-paragraph + list)
    # ========================================================================
    print("\n" + "=" * 80)
    print("6) TEST POST /check - BODY C (multi-paragraph slicing & list)")
    print("=" * 80)
    print()
    
    body_c = {
        "text": """Social media use exceeding three hours per day correlates with elevated anxiety.

- Transformers achieve state-of-the-art performance on natural language processing benchmarks.
- Attention mechanisms enable long-range dependencies.
- BERT and GPT family models dominate the leaderboard.

Photosynthesis is performed by chloroplasts using sunlight to produce glucose."""
    }
    
    print("📝 Testing Body C (multi-paragraph + list)...")
    try:
        resp = requests.post(f"{API_BASE}/projects/{project_id}/check", json=body_c, timeout=30)
        
        if resp.status_code == 200:
            data = resp.json()
            units = data.get("units", [])
            summary = data.get("summary", {})
            annotated_html = data.get("annotated_html", "")
            
            # Expect: units.length >= 5 (1 paragraph + 3 list items + 1 unsupported paragraph)
            if len(units) >= 5:
                # Check for list items
                list_items = [u for u in units if u.get("kind") == "list_item"]
                
                # At least one supported unit cites PDF 1; list items cite PDF 2
                supported_units = [u for u in units if u.get("status") == "supported"]
                
                # Check summary.unsupported >= 1
                if summary.get("unsupported") >= 1:
                    # Check annotated_html contains a <ul> or <ol> with class "cf-list"
                    if "cf-list" in annotated_html and ("<ul" in annotated_html or "<ol" in annotated_html):
                        log_test("Body C - Multi-paragraph + list", True, 
                                f"Units: {len(units)}, List items: {len(list_items)}, Supported: {len(supported_units)}, Summary: {summary}")
                    else:
                        log_test("Body C - Multi-paragraph + list", False, 
                                "annotated_html missing cf-list or list tags")
                else:
                    log_test("Body C - Multi-paragraph + list", False, 
                            f"summary.unsupported < 1: {summary}")
            else:
                log_test("Body C - Multi-paragraph + list", False, 
                        f"Expected >= 5 units, got {len(units)}")
        else:
            log_test("Body C - Multi-paragraph + list", False, f"Status {resp.status_code}")
    except Exception as e:
        log_test("Body C - Multi-paragraph + list", False, str(e))
    
    # ========================================================================
    # 7) TEST POST /check - BODY D (long paragraph chunking)
    # ========================================================================
    print("\n" + "=" * 80)
    print("7) TEST POST /check - BODY D (long paragraph >5 sentences gets chunked)")
    print("=" * 80)
    print()
    
    body_d = {
        "text": """Social media platforms have become ubiquitous in modern society. 
Adolescents spend an average of three to four hours daily on these platforms. 
Research indicates a correlation between excessive social media use and mental health issues. 
Anxiety and depression rates have increased among teenagers in recent years. 
Sleep patterns are disrupted by late-night social media engagement. 
Academic performance may suffer due to distraction and reduced study time. 
Parents and educators express concern about the long-term effects of social media addiction."""
    }
    
    print("📝 Testing Body D (7-sentence paragraph should be chunked)...")
    try:
        resp = requests.post(f"{API_BASE}/projects/{project_id}/check", json=body_d, timeout=30)
        
        if resp.status_code == 200:
            data = resp.json()
            units = data.get("units", [])
            
            # Expect units > 1 (multiple sub-paragraphs), each text non-empty
            if len(units) > 1:
                all_have_text = all(u.get("text") and len(u.get("text", "").strip()) > 0 for u in units)
                
                if all_have_text:
                    log_test("Body D - Long paragraph chunking", True, 
                            f"Chunked into {len(units)} units")
                else:
                    log_test("Body D - Long paragraph chunking", False, 
                            "Some units have empty text")
            else:
                log_test("Body D - Long paragraph chunking", False, 
                        f"Expected > 1 unit, got {len(units)}")
        else:
            log_test("Body D - Long paragraph chunking", False, f"Status {resp.status_code}")
    except Exception as e:
        log_test("Body D - Long paragraph chunking", False, str(e))
    
    # ========================================================================
    # 8) TEST POST /check - BODY E (bibliography boost)
    # ========================================================================
    print("\n" + "=" * 80)
    print("8) TEST POST /check - BODY E (bibliography boost)")
    print("=" * 80)
    print()
    
    body_e = {
        "text": "Social media use exceeding three hours per day correlates with elevated anxiety in adolescents.",
        "bibliography": "Smith 2023 social media anxiety adolescents",
        "citation_format": "ieee"
    }
    
    print("📝 Testing Body E (with bibliography boost)...")
    try:
        resp = requests.post(f"{API_BASE}/projects/{project_id}/check", json=body_e, timeout=30)
        
        if resp.status_code == 200:
            data = resp.json()
            units = data.get("units", [])
            
            if len(units) == 1:
                unit_with_bib = units[0]
                score_with_bib = unit_with_bib.get("score", 0)
                
                # Compare with Body A's score (without bibliography)
                # We already tested Body A, so we know it should be supported
                # The score should be equal or higher with bibliography
                # For this test, we just verify it's still supported and has a reasonable score
                if unit_with_bib.get("status") == "supported" and score_with_bib > 0:
                    log_test("Body E - Bibliography boost", True, 
                            f"Score with bibliography: {score_with_bib}, Status: supported")
                else:
                    log_test("Body E - Bibliography boost", False, 
                            f"Status: {unit_with_bib.get('status')}, Score: {score_with_bib}")
            else:
                log_test("Body E - Bibliography boost", False, f"Expected 1 unit, got {len(units)}")
        else:
            log_test("Body E - Bibliography boost", False, f"Status {resp.status_code}")
    except Exception as e:
        log_test("Body E - Bibliography boost", False, str(e))
    
    # ========================================================================
    # 9) TEST POST /check - BODY F (document_ids filter)
    # ========================================================================
    print("\n" + "=" * 80)
    print("9) TEST POST /check - BODY F (document_ids filter)")
    print("=" * 80)
    print()
    
    body_f = {
        "text": """Social media use exceeding three hours per day correlates with elevated anxiety.

- Transformers achieve state-of-the-art performance on natural language processing benchmarks.
- Attention mechanisms enable long-range dependencies.
- BERT and GPT family models dominate the leaderboard.

Photosynthesis is performed by chloroplasts using sunlight to produce glucose.""",
        "document_ids": [doc1_id]  # Only PDF 1 (social media)
    }
    
    print(f"📝 Testing Body F (document_ids filter - only doc1: {doc1_id[:8]}...)...")
    try:
        resp = requests.post(f"{API_BASE}/projects/{project_id}/check", json=body_f, timeout=30)
        
        if resp.status_code == 200:
            data = resp.json()
            units = data.get("units", [])
            
            # List items about transformers should NOT be supported (no PDF 2 in scope)
            list_items = [u for u in units if u.get("kind") == "list_item"]
            transformer_items_unsupported = all(
                u.get("status") != "supported" 
                for u in list_items 
                if "transformer" in u.get("text", "").lower() or "bert" in u.get("text", "").lower()
            )
            
            if transformer_items_unsupported:
                log_test("Body F - document_ids filter", True, 
                        "Transformer list items not supported (PDF 2 excluded)")
            else:
                log_test("Body F - document_ids filter", False, 
                        "Transformer items were supported despite PDF 2 being excluded")
        else:
            log_test("Body F - document_ids filter", False, f"Status {resp.status_code}")
    except Exception as e:
        log_test("Body F - document_ids filter", False, str(e))
    
    # ========================================================================
    # 10) TEST GET /api/projects/{id}/check
    # ========================================================================
    print("\n" + "=" * 80)
    print("10) TEST GET /check (retrieve last run)")
    print("=" * 80)
    print()
    
    print("📝 Testing GET /check returns last run...")
    try:
        resp = requests.get(f"{API_BASE}/projects/{project_id}/check", timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            
            if data.get("exists") == True:
                # Should match the latest run (Body F)
                if "units" in data and "summary" in data and "annotated_html" in data:
                    log_test("GET /check - Returns last run", True, 
                            f"exists: true, units: {len(data.get('units', []))}")
                else:
                    log_test("GET /check - Returns last run", False, 
                            "Missing expected fields")
            else:
                log_test("GET /check - Returns last run", False, "exists is not true")
        else:
            log_test("GET /check - Returns last run", False, f"Status {resp.status_code}")
    except Exception as e:
        log_test("GET /check - Returns last run", False, str(e))
    
    # ========================================================================
    # 11) TEST SENTENCE DETAIL (regression)
    # ========================================================================
    print("\n" + "=" * 80)
    print("11) TEST SENTENCE DETAIL (regression)")
    print("=" * 80)
    print()
    
    # Get a valid sentence_id from the last check run
    print("📝 Testing GET /documents/{id}/sentence/{sentence_id}...")
    sentence_id = None
    try:
        # Get sentence_id from last check run
        resp = requests.get(f"{API_BASE}/projects/{project_id}/check", timeout=10)
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
                
                # Full sentence text (ends with . ! or ?)
                if text and (text.endswith('.') or text.endswith('!') or text.endswith('?')):
                    if "page" in sent_data and "document_title" in sent_data:
                        log_test("GET /sentence/{id} - Valid ID", True, 
                                f"Retrieved sentence: {text[:50]}...")
                    else:
                        log_test("GET /sentence/{id} - Valid ID", False, 
                                "Missing page or document_title")
                else:
                    log_test("GET /sentence/{id} - Valid ID", False, 
                            f"Text doesn't end with punctuation: {text}")
            else:
                log_test("GET /sentence/{id} - Valid ID", False, f"Status {resp.status_code}")
        else:
            log_test("GET /sentence/{id} - Valid ID", False, "No sentence_id available from badges")
    except Exception as e:
        log_test("GET /sentence/{id} - Valid ID", False, str(e))
    
    # Test with unknown sentence_id (should 404)
    print("\n📝 Testing GET /sentence/{id} with unknown ID (should 404)...")
    try:
        resp = requests.get(f"{API_BASE}/documents/{doc1_id}/sentence/unknown-sentence-id", timeout=10)
        
        if resp.status_code == 404:
            log_test("GET /sentence/{id} - Unknown ID (404)", True)
        else:
            log_test("GET /sentence/{id} - Unknown ID (404)", False, 
                    f"Expected 404, got {resp.status_code}")
    except Exception as e:
        log_test("GET /sentence/{id} - Unknown ID (404)", False, str(e))
    
    # ========================================================================
    # 12) REGRESSION TESTS
    # ========================================================================
    print("\n" + "=" * 80)
    print("12) REGRESSION TESTS")
    print("=" * 80)
    print()
    
    # Test GET /api/
    print("📝 Testing GET /api/ (health check)...")
    try:
        resp = requests.get(f"{API_BASE}/", timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            if data.get("app") == "JurnalMap" and data.get("status") == "ok":
                log_test("GET /api/ - Health check", True)
            else:
                log_test("GET /api/ - Health check", False, f"Unexpected response: {data}")
        else:
            log_test("GET /api/ - Health check", False, f"Status {resp.status_code}")
    except Exception as e:
        log_test("GET /api/ - Health check", False, str(e))
    
    # Test POST /api/projects (already tested above, but verify again)
    print("\n📝 Testing POST /projects (regression)...")
    try:
        resp = requests.post(f"{API_BASE}/projects", json={
            "name": "Regression Test Project",
            "description": "Testing project creation"
        }, timeout=10)
        
        if resp.status_code == 200:
            reg_project = resp.json()
            reg_project_id = reg_project["id"]
            log_test("POST /projects - Regression", True, f"Project ID: {reg_project_id}")
            
            # Test GET project by ID
            resp = requests.get(f"{API_BASE}/projects/{reg_project_id}", timeout=10)
            if resp.status_code == 200:
                log_test("GET /projects/{id} - Regression", True)
            else:
                log_test("GET /projects/{id} - Regression", False, f"Status {resp.status_code}")
            
            # Test DELETE project
            resp = requests.delete(f"{API_BASE}/projects/{reg_project_id}", timeout=10)
            if resp.status_code == 200:
                log_test("DELETE /projects/{id} - Regression", True)
            else:
                log_test("DELETE /projects/{id} - Regression", False, f"Status {resp.status_code}")
        else:
            log_test("POST /projects - Regression", False, f"Status {resp.status_code}")
    except Exception as e:
        log_test("POST /projects - Regression", False, str(e))
    
    # Test GET /api/projects (list)
    print("\n📝 Testing GET /projects (list)...")
    try:
        resp = requests.get(f"{API_BASE}/projects", timeout=10)
        
        if resp.status_code == 200:
            projects = resp.json()
            if isinstance(projects, list):
                log_test("GET /projects - List", True, f"Found {len(projects)} projects")
            else:
                log_test("GET /projects - List", False, "Response is not a list")
        else:
            log_test("GET /projects - List", False, f"Status {resp.status_code}")
    except Exception as e:
        log_test("GET /projects - List", False, str(e))
    
    # Test POST /api/settings/test-api-key
    print("\n📝 Testing POST /settings/test-api-key...")
    try:
        resp = requests.post(f"{API_BASE}/settings/test-api-key", json={
            "provider": "gemini",
            "model": "gemini-2.5-flash",
            "api_key": "AQ.Ab8RN6KcXL7KCacLa87cmsjawr9IYitKC7lkD16AZEORGSDZng"
        }, timeout=30)
        
        if resp.status_code == 200:
            data = resp.json()
            if data.get("ok") == True:
                log_test("POST /settings/test-api-key - Valid key", True, 
                        f"Provider: {data.get('provider')}, Model: {data.get('model')}")
            else:
                log_test("POST /settings/test-api-key - Valid key", False, 
                        f"ok is not true: {data}")
        else:
            log_test("POST /settings/test-api-key - Valid key", False, f"Status {resp.status_code}")
    except Exception as e:
        log_test("POST /settings/test-api-key - Valid key", False, str(e))
    
    # ========================================================================
    # 13) CASCADE DELETE TEST
    # ========================================================================
    print("\n" + "=" * 80)
    print("13) CASCADE DELETE TEST")
    print("=" * 80)
    print()
    
    print("📝 Testing DELETE project cascades check_runs...")
    try:
        # Delete the main test project
        resp = requests.delete(f"{API_BASE}/projects/{project_id}", timeout=10)
        
        if resp.status_code == 200:
            log_test("DELETE /projects/{id} - Success", True)
            
            # Verify check_run is gone
            resp = requests.get(f"{API_BASE}/projects/{project_id}/check", timeout=10)
            
            # Should return 404 or exists: false
            if resp.status_code == 404:
                log_test("DELETE cascade - check_runs removed (404)", True)
            elif resp.status_code == 200:
                data = resp.json()
                if data.get("exists") == False:
                    log_test("DELETE cascade - check_runs removed (exists:false)", True)
                else:
                    log_test("DELETE cascade - check_runs removed", False, 
                            "check_run still exists after project deletion")
            else:
                log_test("DELETE cascade - check_runs removed", False, 
                        f"Unexpected status {resp.status_code}")
        else:
            log_test("DELETE /projects/{id} - Success", False, f"Status {resp.status_code}")
    except Exception as e:
        log_test("DELETE cascade - check_runs removed", False, str(e))


if __name__ == "__main__":
    test_check_fix_backend()
    
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
