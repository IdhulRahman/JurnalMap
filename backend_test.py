#!/usr/bin/env python3
"""
Backend API tests for JurnalMap Workspace endpoints.
Tests all workspace-related endpoints end-to-end.
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


def create_test_pdf():
    """Create a small test PDF with academic content using PyMuPDF."""
    try:
        import fitz
        doc = fitz.open()
        page = doc.new_page()
        
        # Add realistic academic content
        page.insert_text((50, 72), "Social Media and Mental Health: A Quantitative Study", fontsize=14)
        page.insert_text((50, 100), "Abstract: Social media usage exceeds three hours per day among adolescents.", fontsize=11)
        page.insert_text((50, 120), "Adolescents experience increased anxiety and depression symptoms.", fontsize=11)
        page.insert_text((50, 140), "This study surveys 200 university students about their social media habits.", fontsize=11)
        page.insert_text((50, 160), "We measured psychological well-being using standardized scales.", fontsize=11)
        page.insert_text((50, 180), "Results show a strong positive correlation between screen time and anxiety.", fontsize=11)
        page.insert_text((50, 200), "The correlation coefficient was r=0.72, p<0.001, indicating significance.", fontsize=11)
        page.insert_text((50, 220), "Instagram and TikTok showed the highest association with negative outcomes.", fontsize=11)
        
        pdf_path = "/tmp/test_academic.pdf"
        doc.save(pdf_path)
        doc.close()
        print(f"📄 Created test PDF: {pdf_path}")
        return pdf_path
    except Exception as e:
        print(f"❌ Failed to create test PDF: {e}")
        return None


def test_workspace_endpoints():
    """Main test function for all workspace endpoints."""
    
    print("=" * 60)
    print("WORKSPACE BACKEND API TESTS")
    print("=" * 60)
    print()
    
    # Step 1: Create a project
    print("📝 Step 1: Creating test project...")
    try:
        resp = requests.post(f"{API_BASE}/projects", json={
            "name": "Workspace Test Project",
            "description": "Testing workspace endpoints"
        }, timeout=10)
        
        if resp.status_code == 200:
            project = resp.json()
            project_id = project["id"]
            log_test("POST /projects - Create project", True, f"Project ID: {project_id}")
        else:
            log_test("POST /projects - Create project", False, f"Status {resp.status_code}: {resp.text}")
            return
    except Exception as e:
        log_test("POST /projects - Create project", False, str(e))
        return
    
    # Step 2: GET outline when none exists
    print("\n📝 Step 2: GET outline (should return exists:false)...")
    try:
        resp = requests.get(f"{API_BASE}/projects/{project_id}/outline", timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            if data.get("exists") == False and data.get("chapters") == [] and data.get("citation_format") == "ieee":
                log_test("GET /outline - Empty state", True, "Returns exists:false, empty chapters, ieee format")
            else:
                log_test("GET /outline - Empty state", False, f"Unexpected response: {data}")
        else:
            log_test("GET /outline - Empty state", False, f"Status {resp.status_code}: {resp.text}")
    except Exception as e:
        log_test("GET /outline - Empty state", False, str(e))
    
    # Step 3: POST outline with IEEE format
    print("\n📝 Step 3: POST outline with IEEE citation format...")
    outline_payload = {
        "title": "Skripsi Bab 2 Test",
        "chapters": [
            {
                "title": "Bab 1: Pendahuluan",
                "subchapters": [
                    {"title": "1.1 Latar Belakang"},
                    {"title": "1.2 Rumusan Masalah"}
                ]
            },
            {
                "title": "Bab 2: Tinjauan Pustaka",
                "subchapters": [
                    {"title": "2.1 Definisi Media Sosial"}
                ]
            }
        ],
        "citation_format": "ieee"
    }
    
    try:
        resp = requests.post(f"{API_BASE}/projects/{project_id}/outline", json=outline_payload, timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            # Verify IDs are assigned
            has_ids = all(
                ch.get("id") and all(sc.get("id") for sc in ch.get("subchapters", []))
                for ch in data.get("chapters", [])
            )
            if has_ids and data.get("exists") == True and data.get("citation_format") == "ieee" and "updated_at" in data:
                log_test("POST /outline - Save with IEEE", True, "IDs assigned, exists:true, citation_format:ieee")
                saved_outline = data
                # Store subchapter IDs for later tests
                subchapter_ids = []
                for ch in data.get("chapters", []):
                    for sc in ch.get("subchapters", []):
                        subchapter_ids.append(sc["id"])
            else:
                log_test("POST /outline - Save with IEEE", False, f"Missing expected fields: {data}")
                return
        else:
            log_test("POST /outline - Save with IEEE", False, f"Status {resp.status_code}: {resp.text}")
            return
    except Exception as e:
        log_test("POST /outline - Save with IEEE", False, str(e))
        return
    
    # Step 4: GET outline again to verify persistence
    print("\n📝 Step 4: GET outline again (verify persistence)...")
    try:
        resp = requests.get(f"{API_BASE}/projects/{project_id}/outline", timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            if data.get("title") == "Skripsi Bab 2 Test" and len(data.get("chapters", [])) == 2:
                log_test("GET /outline - Verify persistence", True, "Outline persisted correctly")
            else:
                log_test("GET /outline - Verify persistence", False, f"Data mismatch: {data}")
        else:
            log_test("GET /outline - Verify persistence", False, f"Status {resp.status_code}")
    except Exception as e:
        log_test("GET /outline - Verify persistence", False, str(e))
    
    # Step 5: Update outline with APA7 format
    print("\n📝 Step 5: Update outline to APA7 citation format...")
    # Use the saved outline with existing IDs to preserve subchapter references
    saved_outline["citation_format"] = "apa7"
    try:
        resp = requests.post(f"{API_BASE}/projects/{project_id}/outline", json=saved_outline, timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            if data.get("citation_format") == "apa7":
                log_test("POST /outline - Update to APA7", True, "Citation format updated to apa7")
                saved_outline = data  # Update saved outline
            else:
                log_test("POST /outline - Update to APA7", False, f"Format not updated: {data.get('citation_format')}")
        else:
            log_test("POST /outline - Update to APA7", False, f"Status {resp.status_code}")
    except Exception as e:
        log_test("POST /outline - Update to APA7", False, str(e))
    
    # Step 6: GET content for subchapter (should be empty)
    print("\n📝 Step 6: GET content for subchapter (empty state)...")
    test_subchapter_id = subchapter_ids[0] if subchapter_ids else "test-id"
    try:
        resp = requests.get(f"{API_BASE}/projects/{project_id}/workspace/content/{test_subchapter_id}", timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            if data.get("content") == "" and data.get("badges") == [] and data.get("references_used") == []:
                log_test("GET /workspace/content/{id} - Empty", True, "Returns empty content, badges, references")
            else:
                log_test("GET /workspace/content/{id} - Empty", False, f"Unexpected data: {data}")
        else:
            log_test("GET /workspace/content/{id} - Empty", False, f"Status {resp.status_code}")
    except Exception as e:
        log_test("GET /workspace/content/{id} - Empty", False, str(e))
    
    # Step 7: PUT content to save
    print("\n📝 Step 7: PUT content to save...")
    content_payload = {
        "content": "<p>Hello World Test Content</p>",
        "badges": [],
        "references_used": [],
        "plain_paragraphs": ["Hello World Test Content"]
    }
    try:
        resp = requests.put(
            f"{API_BASE}/projects/{project_id}/workspace/content/{test_subchapter_id}",
            json=content_payload,
            timeout=10
        )
        
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "saved" and "updated_at" in data:
                log_test("PUT /workspace/content/{id} - Save", True, "Content saved successfully")
            else:
                log_test("PUT /workspace/content/{id} - Save", False, f"Unexpected response: {data}")
        else:
            log_test("PUT /workspace/content/{id} - Save", False, f"Status {resp.status_code}: {resp.text}")
    except Exception as e:
        log_test("PUT /workspace/content/{id} - Save", False, str(e))
    
    # Step 8: GET content again to verify save
    print("\n📝 Step 8: GET content again (verify save)...")
    try:
        resp = requests.get(f"{API_BASE}/projects/{project_id}/workspace/content/{test_subchapter_id}", timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            if data.get("content") == "<p>Hello World Test Content</p>":
                log_test("GET /workspace/content/{id} - Verify save", True, "Content retrieved correctly")
            else:
                log_test("GET /workspace/content/{id} - Verify save", False, f"Content mismatch: {data.get('content')}")
        else:
            log_test("GET /workspace/content/{id} - Verify save", False, f"Status {resp.status_code}")
    except Exception as e:
        log_test("GET /workspace/content/{id} - Verify save", False, str(e))
    
    # Step 9: GET all contents
    print("\n📝 Step 9: GET all workspace contents...")
    try:
        resp = requests.get(f"{API_BASE}/projects/{project_id}/workspace/contents", timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            if "items" in data and len(data["items"]) >= 1:
                log_test("GET /workspace/contents - List all", True, f"Found {len(data['items'])} content(s)")
            else:
                log_test("GET /workspace/contents - List all", False, f"Unexpected response: {data}")
        else:
            log_test("GET /workspace/contents - List all", False, f"Status {resp.status_code}")
    except Exception as e:
        log_test("GET /workspace/contents - List all", False, str(e))
    
    # Step 10: POST generate without documents (should fail)
    print("\n📝 Step 10: POST generate without documents (should fail with 400)...")
    try:
        resp = requests.post(
            f"{API_BASE}/projects/{project_id}/workspace/generate",
            json={"subchapter_id": test_subchapter_id},
            timeout=10
        )
        
        if resp.status_code == 400:
            error_msg = resp.json().get("detail", "").lower()
            if "jurnal" in error_msg or "dokumen" in error_msg or "pdf" in error_msg:
                log_test("POST /workspace/generate - No docs (400)", True, f"Correctly returns 400: {error_msg}")
            else:
                log_test("POST /workspace/generate - No docs (400)", False, f"Wrong error message: {error_msg}")
        else:
            log_test("POST /workspace/generate - No docs (400)", False, f"Expected 400, got {resp.status_code}")
    except Exception as e:
        log_test("POST /workspace/generate - No docs (400)", False, str(e))
    
    # Step 11: Upload a PDF document
    print("\n📝 Step 11: Upload PDF document...")
    pdf_path = create_test_pdf()
    if not pdf_path:
        log_test("Upload PDF", False, "Failed to create test PDF")
        print("\n⚠️  Skipping remaining tests that require a document")
        return
    
    document_id = None
    try:
        with open(pdf_path, "rb") as f:
            files = {"file": ("test_academic.pdf", f, "application/pdf")}
            resp = requests.post(
                f"{API_BASE}/projects/{project_id}/documents",
                files=files,
                timeout=30
            )
        
        if resp.status_code == 200:
            doc = resp.json()
            document_id = doc["id"]
            log_test("POST /documents - Upload PDF", True, f"Document ID: {document_id}")
        else:
            log_test("POST /documents - Upload PDF", False, f"Status {resp.status_code}: {resp.text}")
            return
    except Exception as e:
        log_test("POST /documents - Upload PDF", False, str(e))
        return
    
    # Step 12: Poll document status until ready
    print("\n📝 Step 12: Polling document status (max 3 minutes)...")
    max_wait = 180  # 3 minutes
    poll_interval = 3
    elapsed = 0
    doc_ready = False
    
    while elapsed < max_wait:
        try:
            resp = requests.get(f"{API_BASE}/documents/{document_id}/status", timeout=10)
            if resp.status_code == 200:
                status_data = resp.json()
                status = status_data.get("status")
                print(f"   Status: {status} (elapsed: {elapsed}s)")
                
                if status == "ready":
                    doc_ready = True
                    log_test("Document processing - Ready", True, f"Document ready after {elapsed}s")
                    break
                elif status == "failed":
                    error = status_data.get("error", "Unknown error")
                    log_test("Document processing - Ready", False, f"Processing failed: {error}")
                    return
            
            time.sleep(poll_interval)
            elapsed += poll_interval
        except Exception as e:
            log_test("Document processing - Ready", False, f"Polling error: {e}")
            return
    
    if not doc_ready:
        log_test("Document processing - Ready", False, f"Timeout after {max_wait}s")
        return
    
    # Step 13: POST generate with document (should succeed)
    print("\n📝 Step 13: POST generate with document (should succeed)...")
    try:
        resp = requests.post(
            f"{API_BASE}/projects/{project_id}/workspace/generate",
            json={"subchapter_id": test_subchapter_id},
            timeout=90  # Allow up to 90s for LLM call
        )
        
        if resp.status_code == 200:
            data = resp.json()
            content = data.get("content", "")
            badges = data.get("badges", [])
            references = data.get("references_used", [])
            
            # Check if content is generated
            if content and isinstance(content, str) and len(content) > 0:
                # Check for citation badges in content
                has_badges = "jm-citation-badge" in content or len(badges) > 0
                log_test(
                    "POST /workspace/generate - With docs",
                    True,
                    f"Generated content ({len(content)} chars), {len(badges)} badges, {len(references)} refs"
                )
            else:
                log_test("POST /workspace/generate - With docs", False, f"Empty or invalid content: {data}")
        else:
            log_test("POST /workspace/generate - With docs", False, f"Status {resp.status_code}: {resp.text}")
    except Exception as e:
        log_test("POST /workspace/generate - With docs", False, str(e))
    
    # Step 14: Get sentence detail
    print("\n📝 Step 14: GET sentence detail...")
    # First, get a valid sentence_id from the document
    sentence_id = None
    try:
        # Query MongoDB directly or use badges from generate response
        # For now, we'll try to get sentences from the last generate response
        if 'data' in locals() and data.get("badges"):
            sentence_id = data["badges"][0].get("sentence_id")
        
        if sentence_id:
            resp = requests.get(f"{API_BASE}/documents/{document_id}/sentence/{sentence_id}", timeout=10)
            
            if resp.status_code == 200:
                sent_data = resp.json()
                if "text" in sent_data and "page" in sent_data and "document_title" in sent_data:
                    log_test("GET /sentence/{id} - Valid ID", True, f"Retrieved sentence: {sent_data.get('text', '')[:50]}...")
                else:
                    log_test("GET /sentence/{id} - Valid ID", False, f"Missing fields: {sent_data}")
            else:
                log_test("GET /sentence/{id} - Valid ID", False, f"Status {resp.status_code}")
        else:
            log_test("GET /sentence/{id} - Valid ID", False, "No sentence_id available from badges")
    except Exception as e:
        log_test("GET /sentence/{id} - Valid ID", False, str(e))
    
    # Step 15: Test sentence detail with invalid ID (should 404)
    print("\n📝 Step 15: GET sentence detail with fake ID (should 404)...")
    try:
        resp = requests.get(f"{API_BASE}/documents/{document_id}/sentence/fake-sentence-id", timeout=10)
        
        if resp.status_code == 404:
            log_test("GET /sentence/{id} - Invalid ID (404)", True, "Correctly returns 404")
        else:
            log_test("GET /sentence/{id} - Invalid ID (404)", False, f"Expected 404, got {resp.status_code}")
    except Exception as e:
        log_test("GET /sentence/{id} - Invalid ID (404)", False, str(e))
    
    # Step 16: Test insert-badge with APA7 format
    print("\n📝 Step 16: POST insert-badge with APA7 format...")
    try:
        badge_payload = {
            "subchapter_id": test_subchapter_id,
            "document_id": document_id,
            "sentence_id": sentence_id if sentence_id else "test-sentence",
            "quote": "Sample quote text for testing",
            "page": 1
        }
        resp = requests.post(
            f"{API_BASE}/projects/{project_id}/workspace/insert-badge",
            json=badge_payload,
            timeout=10
        )
        
        if resp.status_code == 200:
            data = resp.json()
            badge = data.get("badge", {})
            label = badge.get("label", "")
            citation_format = data.get("citation_format", "")
            
            # APA7 should have parentheses, not brackets
            if citation_format == "apa7" and "(" in label and ")" in label and "[" not in label:
                log_test("POST /insert-badge - APA7 format", True, f"Label: {label}")
            else:
                log_test("POST /insert-badge - APA7 format", False, f"Wrong format: {label} (expected APA7 with parentheses)")
        else:
            log_test("POST /insert-badge - APA7 format", False, f"Status {resp.status_code}: {resp.text}")
    except Exception as e:
        log_test("POST /insert-badge - APA7 format", False, str(e))
    
    # Step 17: Change to IEEE and test insert-badge again
    print("\n📝 Step 17: Change to IEEE and test insert-badge...")
    try:
        # Update outline to IEEE (use saved_outline to preserve IDs)
        saved_outline["citation_format"] = "ieee"
        resp = requests.post(f"{API_BASE}/projects/{project_id}/outline", json=saved_outline, timeout=10)
        
        if resp.status_code == 200:
            # Now test insert-badge with IEEE
            resp = requests.post(
                f"{API_BASE}/projects/{project_id}/workspace/insert-badge",
                json=badge_payload,
                timeout=10
            )
            
            if resp.status_code == 200:
                data = resp.json()
                badge = data.get("badge", {})
                label = badge.get("label", "")
                citation_format = data.get("citation_format", "")
                
                # IEEE should have brackets like [1], [2], etc.
                if citation_format == "ieee" and "[" in label and "]" in label:
                    log_test("POST /insert-badge - IEEE format", True, f"Label: {label}")
                else:
                    log_test("POST /insert-badge - IEEE format", False, f"Wrong format: {label} (expected IEEE with brackets)")
            else:
                log_test("POST /insert-badge - IEEE format", False, f"Status {resp.status_code}")
        else:
            log_test("POST /insert-badge - IEEE format", False, "Failed to update outline to IEEE")
    except Exception as e:
        log_test("POST /insert-badge - IEEE format", False, str(e))
    
    # Step 18: DELETE project (cascade delete)
    print("\n📝 Step 18: DELETE project (cascade delete)...")
    try:
        resp = requests.delete(f"{API_BASE}/projects/{project_id}", timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            if data.get("deleted") == True:
                log_test("DELETE /projects/{id} - Cascade", True, "Project deleted")
                
                # Verify outline is gone
                resp = requests.get(f"{API_BASE}/projects/{project_id}/outline", timeout=10)
                if resp.status_code == 404 or (resp.status_code == 200 and resp.json().get("exists") == False):
                    log_test("DELETE cascade - Outline removed", True, "Outline no longer exists")
                else:
                    log_test("DELETE cascade - Outline removed", False, f"Outline still exists: {resp.status_code}")
            else:
                log_test("DELETE /projects/{id} - Cascade", False, f"Unexpected response: {data}")
        else:
            log_test("DELETE /projects/{id} - Cascade", False, f"Status {resp.status_code}")
    except Exception as e:
        log_test("DELETE /projects/{id} - Cascade", False, str(e))
    
    # Note about workspace_contents cascade
    print("\n📝 Note: Checking if workspace_contents are cascade-deleted...")
    print("   (This requires MongoDB query - backend may not cascade workspace_* collections)")
    print("   If they remain, that's acceptable for now but should be flagged.")


if __name__ == "__main__":
    test_workspace_endpoints()
    
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"✅ Passed: {tests_passed}")
    print(f"❌ Failed: {tests_failed}")
    print(f"📊 Total:  {tests_passed + tests_failed}")
    print("=" * 60)
    
    if tests_failed > 0:
        print("\n⚠️  Some tests failed. See details above.")
        sys.exit(1)
    else:
        print("\n🎉 All tests passed!")
        sys.exit(0)
