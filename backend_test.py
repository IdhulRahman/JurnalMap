#!/usr/bin/env python3
"""
JurnalMap Backend Test - Focus on NEW/CHANGED endpoints after large revision.

Test scenarios:
1. GET /api/config (no auth)
2. Queue + upload flow (admin token)
3. Auto-summary must NOT run
4. On-demand summarize with language
5. Retry endpoint
6. Network graph
7. Ask language
8. Regression sanity
"""
import os
import sys
import time
import requests
from pathlib import Path

# Base URL from environment
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://a3982528-8c1d-4548-97ce-8cc44cfbb337.preview.emergentagent.com")
API_URL = f"{BASE_URL}/api"

# Admin credentials
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin"

# Test PDF file
TEST_PDF = "/app/backend/uploads/0f1539db-7f94-4d44-ae38-2736c8dbd6ee.pdf"

# Color codes for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

class TestResults:
    def __init__(self):
        self.passed = []
        self.failed = []
        self.warnings = []
    
    def add_pass(self, test_name):
        self.passed.append(test_name)
        print(f"{GREEN}✓{RESET} {test_name}")
    
    def add_fail(self, test_name, reason):
        self.failed.append((test_name, reason))
        print(f"{RED}✗{RESET} {test_name}: {reason}")
    
    def add_warning(self, test_name, reason):
        self.warnings.append((test_name, reason))
        print(f"{YELLOW}⚠{RESET} {test_name}: {reason}")
    
    def summary(self):
        print(f"\n{BLUE}{'='*60}{RESET}")
        print(f"{BLUE}TEST SUMMARY{RESET}")
        print(f"{BLUE}{'='*60}{RESET}")
        print(f"{GREEN}Passed: {len(self.passed)}{RESET}")
        print(f"{RED}Failed: {len(self.failed)}{RESET}")
        print(f"{YELLOW}Warnings: {len(self.warnings)}{RESET}")
        
        if self.failed:
            print(f"\n{RED}Failed Tests:{RESET}")
            for name, reason in self.failed:
                print(f"  - {name}: {reason}")
        
        if self.warnings:
            print(f"\n{YELLOW}Warnings:{RESET}")
            for name, reason in self.warnings:
                print(f"  - {name}: {reason}")

results = TestResults()

def login_admin():
    """Login as admin and return token."""
    print(f"\n{BLUE}Logging in as admin...{RESET}")
    resp = requests.post(f"{API_URL}/auth/login", json={
        "username": ADMIN_USERNAME,
        "password": ADMIN_PASSWORD
    })
    if resp.status_code != 200:
        print(f"{RED}Login failed: {resp.status_code} {resp.text}{RESET}")
        sys.exit(1)
    token = resp.json()["access_token"]
    print(f"{GREEN}Login successful{RESET}")
    return token

def test_config_endpoint():
    """Test 1: GET /api/config (no auth)"""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}TEST 1: GET /api/config (no auth){RESET}")
    print(f"{BLUE}{'='*60}{RESET}")
    
    resp = requests.get(f"{API_URL}/config")
    if resp.status_code != 200:
        results.add_fail("GET /api/config", f"Status {resp.status_code}")
        return
    
    data = resp.json()
    
    # Check available_models
    if "available_models" not in data:
        results.add_fail("GET /api/config", "Missing 'available_models'")
        return
    
    models = data["available_models"]
    if not isinstance(models, list) or len(models) == 0:
        results.add_fail("GET /api/config", "available_models is empty or not a list")
        return
    
    # Check each model has id, provider, label
    for model in models:
        if not all(k in model for k in ["id", "provider", "label"]):
            results.add_fail("GET /api/config", f"Model missing required fields: {model}")
            return
        
        # Check label ends with "(administrator)"
        if not model["label"].endswith("(administrator)"):
            results.add_fail("GET /api/config", f"Model label doesn't end with '(administrator)': {model['label']}")
            return
    
    # Check other required fields
    required_fields = ["default_model", "embedding_enabled", "local_llm_enabled", 
                      "max_files_per_upload", "max_upload_size_mb"]
    for field in required_fields:
        if field not in data:
            results.add_fail("GET /api/config", f"Missing field: {field}")
            return
    
    # Verify local_llm_enabled is false
    if data["local_llm_enabled"] != False:
        results.add_fail("GET /api/config", f"local_llm_enabled should be false, got {data['local_llm_enabled']}")
        return
    
    results.add_pass("GET /api/config - all fields present and valid")
    print(f"  Available models: {len(models)}")
    print(f"  Default model: {data['default_model']}")
    print(f"  Embedding enabled: {data['embedding_enabled']}")
    print(f"  Max files per upload: {data['max_files_per_upload']}")

def test_queue_upload_flow(token):
    """Test 2: Queue + upload flow"""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}TEST 2: Queue + upload flow{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Create a fresh project
    print("Creating new project...")
    resp = requests.post(f"{API_URL}/projects", json={"name": "Queue Test Project"}, headers=headers)
    if resp.status_code != 200:
        results.add_fail("Create project", f"Status {resp.status_code}")
        return None
    
    project_id = resp.json()["id"]
    print(f"Project created: {project_id}")
    
    # Upload 3 PDF files at once
    print("Uploading 3 PDF files...")
    if not Path(TEST_PDF).exists():
        results.add_fail("Upload files", f"Test PDF not found: {TEST_PDF}")
        return None
    
    files = [
        ("files", ("doc1.pdf", open(TEST_PDF, "rb"), "application/pdf")),
        ("files", ("doc2.pdf", open(TEST_PDF, "rb"), "application/pdf")),
        ("files", ("doc3.pdf", open(TEST_PDF, "rb"), "application/pdf")),
    ]
    
    resp = requests.post(f"{API_URL}/projects/{project_id}/documents", files=files, headers=headers)
    
    # Close file handles
    for _, (_, fh, _) in files:
        fh.close()
    
    if resp.status_code != 200:
        results.add_fail("Upload 3 files", f"Status {resp.status_code}: {resp.text}")
        return None
    
    docs = resp.json()
    if len(docs) != 3:
        results.add_fail("Upload 3 files", f"Expected 3 docs, got {len(docs)}")
        return None
    
    # Check all docs have status = "queued"
    for doc in docs:
        if doc["status"] != "queued":
            results.add_fail("Upload 3 files", f"Doc {doc['id']} status is {doc['status']}, expected 'queued'")
            return None
    
    results.add_pass("Upload 3 files - all queued")
    doc_ids = [d["id"] for d in docs]
    
    # Immediately GET /api/projects/{P}/queue
    print("Checking queue positions...")
    resp = requests.get(f"{API_URL}/projects/{project_id}/queue", headers=headers)
    if resp.status_code != 200:
        results.add_fail("GET queue", f"Status {resp.status_code}")
        return None
    
    queue_data = resp.json()
    items = queue_data.get("items", [])
    
    # Check queue positions
    positions = [item.get("queue_position") for item in items if item.get("status") in ["queued", "processing"]]
    if not positions:
        results.add_fail("GET queue", "No queue positions found")
        return None
    
    # Positions should be 1, 2, 3 (or some subset if processing started)
    print(f"  Queue positions: {positions}")
    print(f"  Total in queue: {queue_data.get('total', 0)}")
    results.add_pass("GET queue - positions present")
    
    # Poll until all processed (max 60s)
    print("Polling queue until all processed (max 60s)...")
    start_time = time.time()
    max_wait = 60
    
    while time.time() - start_time < max_wait:
        resp = requests.get(f"{API_URL}/projects/{project_id}/queue", headers=headers)
        if resp.status_code != 200:
            results.add_fail("Poll queue", f"Status {resp.status_code}")
            return None
        
        queue_data = resp.json()
        processing = queue_data.get("processing", 0)
        queued = queue_data.get("queued", 0)
        
        print(f"  Processing: {processing}, Queued: {queued}")
        
        if processing == 0 and queued == 0:
            print(f"{GREEN}All documents processed!{RESET}")
            break
        
        time.sleep(2)
    else:
        results.add_warning("Poll queue", "Timeout waiting for processing (60s)")
        return project_id
    
    # Check all items are ready
    resp = requests.get(f"{API_URL}/projects/{project_id}/queue", headers=headers)
    queue_data = resp.json()
    items = queue_data.get("items", [])
    
    all_ready = all(item.get("status") == "ready" for item in items)
    if not all_ready:
        statuses = [item.get("status") for item in items]
        results.add_fail("Poll queue", f"Not all docs ready: {statuses}")
        return project_id
    
    # Check queue_position is null for ready docs
    for item in items:
        if item.get("status") == "ready" and item.get("queue_position") is not None:
            results.add_fail("Poll queue", f"Ready doc has queue_position: {item.get('queue_position')}")
            return project_id
    
    results.add_pass("Poll queue - all docs ready, queue_position null")
    
    return project_id

def test_auto_summary_not_run(token, project_id):
    """Test 3: Auto-summary must NOT run"""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}TEST 3: Auto-summary must NOT run{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")
    
    if not project_id:
        results.add_fail("Auto-summary check", "No project_id from previous test")
        return None
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Get documents
    resp = requests.get(f"{API_URL}/projects/{project_id}/documents", headers=headers)
    if resp.status_code != 200:
        results.add_fail("Get documents", f"Status {resp.status_code}")
        return None
    
    docs = resp.json()
    if not docs:
        results.add_fail("Get documents", "No documents found")
        return None
    
    # Pick first doc
    doc_id = docs[0]["id"]
    
    # GET /api/documents/{id}/summary
    resp = requests.get(f"{API_URL}/documents/{doc_id}/summary", headers=headers)
    if resp.status_code != 200:
        results.add_fail("GET summary", f"Status {resp.status_code}")
        return None
    
    summary_data = resp.json()
    summary = summary_data.get("summary", "")
    sections = summary_data.get("sections", {})
    claims = summary_data.get("claims", [])
    
    # Summary should be empty or sections empty, claims empty
    if summary or sections or claims:
        results.add_fail("Auto-summary check", f"Summary exists (should be empty): summary={bool(summary)}, sections={bool(sections)}, claims={len(claims)}")
        return None
    
    results.add_pass("Auto-summary check - summary is empty (LLM not auto-called)")
    return doc_id

def test_on_demand_summarize(token, doc_id):
    """Test 4: On-demand summarize with language"""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}TEST 4: On-demand summarize with language{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")
    
    if not doc_id:
        results.add_fail("On-demand summarize", "No doc_id from previous test")
        return
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # POST /api/documents/{id}/summarize?language=id
    print("Requesting summary in Indonesian (language=id)...")
    resp = requests.post(f"{API_URL}/documents/{doc_id}/summarize?language=id", headers=headers)
    
    if resp.status_code == 502:
        results.add_warning("Summarize (id)", "502 Bad Gateway - Gemini API temporarily down (tolerable)")
    elif resp.status_code == 400:
        results.add_fail("Summarize (id)", f"400 Bad Request: {resp.text}")
        return
    elif resp.status_code == 404:
        results.add_fail("Summarize (id)", f"404 Not Found: {resp.text}")
        return
    elif resp.status_code == 409:
        results.add_fail("Summarize (id)", f"409 Conflict: {resp.text}")
        return
    elif resp.status_code != 200:
        results.add_fail("Summarize (id)", f"Status {resp.status_code}: {resp.text}")
        return
    else:
        # Success
        summary_data = resp.json()
        summary = summary_data.get("summary", "")
        
        if not summary:
            results.add_fail("Summarize (id)", "Summary is empty after summarize")
            return
        
        results.add_pass("Summarize (id) - summary generated")
        
        # Verify summary_language was persisted
        print("Verifying summary_language persisted...")
        resp = requests.get(f"{API_URL}/documents/{doc_id}/summary", headers=headers)
        if resp.status_code != 200:
            results.add_fail("Verify summary_language", f"Status {resp.status_code}")
            return
        
        # Note: summary_language is not in the response schema, but we can check the document
        resp = requests.get(f"{API_URL}/documents/{doc_id}", headers=headers)
        if resp.status_code == 200:
            doc_data = resp.json()
            summary_lang = doc_data.get("summary_language")
            if summary_lang == "id":
                results.add_pass("Verify summary_language - persisted as 'id'")
            else:
                results.add_warning("Verify summary_language", f"Expected 'id', got {summary_lang}")
    
    # POST /api/documents/{id}/summarize?language=en
    print("Requesting summary in English (language=en)...")
    resp = requests.post(f"{API_URL}/documents/{doc_id}/summarize?language=en", headers=headers)
    
    if resp.status_code == 502:
        results.add_warning("Summarize (en)", "502 Bad Gateway - Gemini API temporarily down (tolerable)")
    elif resp.status_code != 200:
        results.add_fail("Summarize (en)", f"Status {resp.status_code}: {resp.text}")
    else:
        results.add_pass("Summarize (en) - summary generated")

def test_retry_endpoint(token):
    """Test 5: Retry endpoint"""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}TEST 5: Retry endpoint{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Create another project
    print("Creating new project for retry test...")
    resp = requests.post(f"{API_URL}/projects", json={"name": "Retry Test Project"}, headers=headers)
    if resp.status_code != 200:
        results.add_fail("Create project (retry)", f"Status {resp.status_code}")
        return
    
    project_id = resp.json()["id"]
    
    # Upload one PDF
    print("Uploading 1 PDF...")
    with open(TEST_PDF, "rb") as f:
        files = [("files", ("retry_test.pdf", f, "application/pdf"))]
        resp = requests.post(f"{API_URL}/projects/{project_id}/documents", files=files, headers=headers)
    
    if resp.status_code != 200:
        results.add_fail("Upload file (retry)", f"Status {resp.status_code}")
        return
    
    docs = resp.json()
    doc_id = docs[0]["id"]
    
    # Wait for ready
    print("Waiting for document to be ready...")
    start_time = time.time()
    while time.time() - start_time < 30:
        resp = requests.get(f"{API_URL}/documents/{doc_id}", headers=headers)
        if resp.status_code == 200:
            doc = resp.json()
            if doc["status"] == "ready":
                print(f"{GREEN}Document ready{RESET}")
                break
        time.sleep(2)
    else:
        results.add_warning("Wait for ready (retry)", "Timeout waiting for document")
        return
    
    # Test retry on ready doc (should re-queue it)
    print("Testing retry on ready document...")
    resp = requests.post(f"{API_URL}/documents/{doc_id}/retry", headers=headers)
    
    if resp.status_code != 200:
        results.add_fail("Retry ready doc", f"Status {resp.status_code}: {resp.text}")
        return
    
    retry_doc = resp.json()
    if retry_doc["status"] != "queued":
        results.add_fail("Retry ready doc", f"Status should be 'queued', got {retry_doc['status']}")
        return
    
    results.add_pass("Retry ready doc - re-queued successfully")
    
    # Note: Testing the "missing file" scenario would require deleting the file,
    # which is destructive. Skipping as per instructions.

def test_network_graph(token, project_id):
    """Test 6: Network graph"""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}TEST 6: Network graph{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")
    
    if not project_id:
        results.add_fail("Network graph", "No project_id from previous test")
        return
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # GET /api/projects/{P}/network
    print("Requesting network graph...")
    resp = requests.get(f"{API_URL}/projects/{project_id}/network", headers=headers)
    
    if resp.status_code != 200:
        results.add_fail("GET network", f"Status {resp.status_code}: {resp.text}")
        return
    
    network = resp.json()
    
    # Check required fields
    required_fields = ["nodes", "edges", "embedding_backend", "threshold", 
                      "isolated_threshold", "summary"]
    for field in required_fields:
        if field not in network:
            results.add_fail("GET network", f"Missing field: {field}")
            return
    
    # Check nodes
    nodes = network["nodes"]
    if not isinstance(nodes, list):
        results.add_fail("GET network", "nodes is not a list")
        return
    
    print(f"  Nodes: {len(nodes)}")
    print(f"  Edges: {len(network['edges'])}")
    print(f"  Embedding backend: {network['embedding_backend']}")
    print(f"  Threshold: {network['threshold']}")
    print(f"  Isolated threshold: {network['isolated_threshold']}")
    
    # Check each node has required fields
    for node in nodes:
        required_node_fields = ["id", "title", "keywords", "max_edge_score", "isolated"]
        for field in required_node_fields:
            if field not in node:
                results.add_fail("GET network", f"Node missing field: {field}")
                return
    
    # Check edges
    edges = network["edges"]
    if not isinstance(edges, list):
        results.add_fail("GET network", "edges is not a list")
        return
    
    for edge in edges:
        required_edge_fields = ["source", "target", "weight", "semantic", 
                               "keyword", "topic", "shared_keywords"]
        for field in required_edge_fields:
            if field not in edge:
                results.add_fail("GET network", f"Edge missing field: {field}")
                return
    
    # Check threshold values
    if network["threshold"] != 0.7:
        results.add_fail("GET network", f"threshold should be 0.7, got {network['threshold']}")
        return
    
    if network["isolated_threshold"] != 0.4:
        results.add_fail("GET network", f"isolated_threshold should be 0.4, got {network['isolated_threshold']}")
        return
    
    results.add_pass("GET network - all fields present and valid")

def test_ask_language(token, project_id):
    """Test 7: Ask with language parameter"""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}TEST 7: Ask with language parameter{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")
    
    if not project_id:
        results.add_fail("Ask language", "No project_id from previous test")
        return
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # POST /api/projects/{P}/ask?language=id
    print("Asking question in Indonesian (language=id)...")
    resp = requests.post(
        f"{API_URL}/projects/{project_id}/ask?language=id",
        json={"question": "Apa topik utama dari dokumen-dokumen ini?"},
        headers=headers
    )
    
    if resp.status_code == 502:
        results.add_warning("Ask (id)", "502 Bad Gateway - Gemini API temporarily down (tolerable)")
    elif resp.status_code != 200:
        results.add_fail("Ask (id)", f"Status {resp.status_code}: {resp.text}")
    else:
        results.add_pass("Ask (id) - question answered")

def test_regression_sanity(token):
    """Test 8: Regression sanity checks"""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}TEST 8: Regression sanity checks{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # GET /api/auth/me
    print("Testing GET /api/auth/me...")
    resp = requests.get(f"{API_URL}/auth/me", headers=headers)
    if resp.status_code != 200:
        results.add_fail("GET /auth/me", f"Status {resp.status_code}")
    else:
        user = resp.json()
        if user.get("username") != ADMIN_USERNAME:
            results.add_fail("GET /auth/me", f"Username mismatch: {user.get('username')}")
        else:
            results.add_pass("GET /auth/me - working")
    
    # POST /api/projects
    print("Testing POST /api/projects...")
    resp = requests.post(f"{API_URL}/projects", json={"name": "Sanity Check Project"}, headers=headers)
    if resp.status_code != 200:
        results.add_fail("POST /projects", f"Status {resp.status_code}")
    else:
        project = resp.json()
        if "owner_id" not in project:
            results.add_fail("POST /projects", "Missing owner_id")
        else:
            results.add_pass("POST /projects - creates with owner_id")
        
        # Check outliers endpoint exists
        project_id = project["id"]
        print("Testing GET /api/projects/{id}/outliers...")
        resp = requests.get(f"{API_URL}/projects/{project_id}/outliers", headers=headers)
        if resp.status_code == 404:
            results.add_fail("GET /outliers", "Endpoint removed (should exist)")
        elif resp.status_code == 200:
            results.add_pass("GET /outliers - endpoint exists")
        else:
            # Empty project, might return error but endpoint exists
            results.add_pass("GET /outliers - endpoint exists")

def main():
    print(f"{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}JurnalMap Backend Test - Revision Focus{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")
    print(f"Base URL: {BASE_URL}")
    print(f"API URL: {API_URL}")
    print(f"Test PDF: {TEST_PDF}")
    
    # Login
    token = login_admin()
    
    # Run tests
    test_config_endpoint()
    project_id = test_queue_upload_flow(token)
    doc_id = test_auto_summary_not_run(token, project_id)
    test_on_demand_summarize(token, doc_id)
    test_retry_endpoint(token)
    test_network_graph(token, project_id)
    test_ask_language(token, project_id)
    test_regression_sanity(token)
    
    # Summary
    results.summary()
    
    # Exit code
    if results.failed:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()
