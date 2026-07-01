#!/usr/bin/env python3
"""
Comprehensive backend test for JurnalMap API.
Tests all endpoints as specified in the review request.
"""
import requests
import time
import sys
from typing import Dict, List, Optional

# Backend URL from frontend/.env
BASE_URL = "https://8ae4e47a-c558-4ee8-a207-6fce7d1b5e4d.preview.emergentagent.com/api"

# Test credentials
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin"

# Demo PDFs
DEMO_PDFS = [
    "/tmp/demo_pdfs/doc1.pdf",
    "/tmp/demo_pdfs/doc2.pdf",
    "/tmp/demo_pdfs/doc3.pdf",
]

# Test results tracking
test_results = []


def log_test(name: str, passed: bool, details: str = ""):
    """Log a test result."""
    status = "✅ PASS" if passed else "❌ FAIL"
    test_results.append({"name": name, "passed": passed, "details": details})
    print(f"{status}: {name}")
    if details:
        print(f"  Details: {details}")


def test_health():
    """Test GET /api/"""
    try:
        resp = requests.get(f"{BASE_URL}/", timeout=10)
        if resp.status_code == 200 and resp.json().get("status") == "ok":
            log_test("Health endpoint", True, f"Response: {resp.json()}")
            return True
        else:
            log_test("Health endpoint", False, f"Status: {resp.status_code}, Body: {resp.text}")
            return False
    except Exception as e:
        log_test("Health endpoint", False, f"Exception: {e}")
        return False


def test_auth_register_weak_passwords():
    """Test POST /api/auth/register with various weak passwords."""
    test_cases = [
        ("weak", "at least 8 characters"),
        ("NoDigit!", "must contain at least one digit"),
        ("NoSymbol1", "must contain at least one symbol"),
        ("nosymbol1!", "must contain at least one uppercase letter"),
    ]
    
    for password, expected_msg in test_cases:
        try:
            resp = requests.post(
                f"{BASE_URL}/auth/register",
                json={
                    "username": f"testuser_{int(time.time())}",
                    "email": f"test_{int(time.time())}@example.com",
                    "password": password,
                },
                timeout=10,
            )
            if resp.status_code == 422:
                body = resp.json()
                detail_str = str(body.get("detail", ""))
                if expected_msg.lower() in detail_str.lower():
                    log_test(f"Register with password '{password}'", True, f"Got expected 422 with message containing '{expected_msg}'")
                else:
                    log_test(f"Register with password '{password}'", False, f"Got 422 but message doesn't contain '{expected_msg}': {detail_str}")
            else:
                log_test(f"Register with password '{password}'", False, f"Expected 422, got {resp.status_code}: {resp.text}")
        except Exception as e:
            log_test(f"Register with password '{password}'", False, f"Exception: {e}")


def test_auth_register_duplicate_username():
    """Test POST /api/auth/register with duplicate username (admin)."""
    try:
        resp = requests.post(
            f"{BASE_URL}/auth/register",
            json={
                "username": "admin",
                "email": "newemail@example.com",
                "password": "StrongPass1!",
            },
            timeout=10,
        )
        if resp.status_code == 409:
            log_test("Register with duplicate username", True, f"Got expected 409: {resp.json()}")
        else:
            log_test("Register with duplicate username", False, f"Expected 409, got {resp.status_code}: {resp.text}")
    except Exception as e:
        log_test("Register with duplicate username", False, f"Exception: {e}")


def test_auth_register_new_user():
    """Test POST /api/auth/register with valid new user."""
    try:
        resp = requests.post(
            f"{BASE_URL}/auth/register",
            json={
                "username": "testera",
                "email": "testera@example.com",
                "password": "StrongPass1!",
            },
            timeout=10,
        )
        if resp.status_code == 200:
            body = resp.json()
            if "access_token" in body and "user" in body:
                log_test("Register new user testerA", True, f"Got JWT and user object")
                return body["access_token"]
            else:
                log_test("Register new user testerA", False, f"Missing access_token or user in response: {body}")
                return None
        else:
            log_test("Register new user testerA", False, f"Expected 200, got {resp.status_code}: {resp.text}")
            return None
    except Exception as e:
        log_test("Register new user testerA", False, f"Exception: {e}")
        return None


def test_auth_register_duplicate_email():
    """Test POST /api/auth/register with duplicate email."""
    try:
        resp = requests.post(
            f"{BASE_URL}/auth/register",
            json={
                "username": "anotheruser",
                "email": "testera@example.com",  # Same email as testerA
                "password": "StrongPass1!",
            },
            timeout=10,
        )
        if resp.status_code == 409:
            body = resp.json()
            if "email" in str(body).lower():
                log_test("Register with duplicate email", True, f"Got expected 409 with email message: {body}")
            else:
                log_test("Register with duplicate email", False, f"Got 409 but no email mention: {body}")
        else:
            log_test("Register with duplicate email", False, f"Expected 409, got {resp.status_code}: {resp.text}")
    except Exception as e:
        log_test("Register with duplicate email", False, f"Exception: {e}")


def test_auth_login_lockout():
    """Test POST /api/auth/login with 3 failed attempts and lockout."""
    username = "testera"
    wrong_password = "WrongPass1!"
    
    # Attempt 1
    try:
        resp = requests.post(
            f"{BASE_URL}/auth/login",
            json={"username": username, "password": wrong_password},
            timeout=10,
        )
        if resp.status_code == 401:
            body = resp.json()
            detail = body.get("detail", {})
            if isinstance(detail, dict):
                remaining = detail.get("remaining_attempts")
                if remaining == 2:
                    log_test("Login attempt 1 (wrong password)", True, f"Got 401 with remaining_attempts=2")
                else:
                    log_test("Login attempt 1 (wrong password)", False, f"Expected remaining_attempts=2, got {remaining}")
            else:
                log_test("Login attempt 1 (wrong password)", False, f"Detail is not a dict: {detail}")
        else:
            log_test("Login attempt 1 (wrong password)", False, f"Expected 401, got {resp.status_code}: {resp.text}")
    except Exception as e:
        log_test("Login attempt 1 (wrong password)", False, f"Exception: {e}")
    
    # Attempt 2
    try:
        resp = requests.post(
            f"{BASE_URL}/auth/login",
            json={"username": username, "password": wrong_password},
            timeout=10,
        )
        if resp.status_code == 401:
            body = resp.json()
            detail = body.get("detail", {})
            if isinstance(detail, dict):
                remaining = detail.get("remaining_attempts")
                if remaining == 1:
                    log_test("Login attempt 2 (wrong password)", True, f"Got 401 with remaining_attempts=1")
                else:
                    log_test("Login attempt 2 (wrong password)", False, f"Expected remaining_attempts=1, got {remaining}")
            else:
                log_test("Login attempt 2 (wrong password)", False, f"Detail is not a dict: {detail}")
        else:
            log_test("Login attempt 2 (wrong password)", False, f"Expected 401, got {resp.status_code}: {resp.text}")
    except Exception as e:
        log_test("Login attempt 2 (wrong password)", False, f"Exception: {e}")
    
    # Attempt 3 (should trigger lockout)
    try:
        resp = requests.post(
            f"{BASE_URL}/auth/login",
            json={"username": username, "password": wrong_password},
            timeout=10,
        )
        if resp.status_code == 401:
            body = resp.json()
            detail = body.get("detail", {})
            if isinstance(detail, dict):
                locked = detail.get("locked")
                remaining_seconds = detail.get("remaining_seconds")
                if locked and remaining_seconds and remaining_seconds > 0:
                    log_test("Login attempt 3 (lockout triggered)", True, f"Got 401 with locked=True, remaining_seconds={remaining_seconds}")
                else:
                    log_test("Login attempt 3 (lockout triggered)", False, f"Expected locked=True with remaining_seconds, got {detail}")
            else:
                log_test("Login attempt 3 (lockout triggered)", False, f"Detail is not a dict: {detail}")
        else:
            log_test("Login attempt 3 (lockout triggered)", False, f"Expected 401, got {resp.status_code}: {resp.text}")
    except Exception as e:
        log_test("Login attempt 3 (lockout triggered)", False, f"Exception: {e}")
    
    # Attempt 4 (should return 429 locked)
    try:
        resp = requests.post(
            f"{BASE_URL}/auth/login",
            json={"username": username, "password": "StrongPass1!"},  # Correct password
            timeout=10,
        )
        if resp.status_code == 429:
            body = resp.json()
            detail = body.get("detail", {})
            if isinstance(detail, dict):
                remaining_seconds = detail.get("remaining_seconds")
                if remaining_seconds and remaining_seconds > 0:
                    log_test("Login attempt 4 (locked with correct password)", True, f"Got 429 with remaining_seconds={remaining_seconds}")
                else:
                    log_test("Login attempt 4 (locked with correct password)", False, f"Expected remaining_seconds > 0, got {detail}")
            else:
                log_test("Login attempt 4 (locked with correct password)", False, f"Detail is not a dict: {detail}")
        else:
            log_test("Login attempt 4 (locked with correct password)", False, f"Expected 429, got {resp.status_code}: {resp.text}")
    except Exception as e:
        log_test("Login attempt 4 (locked with correct password)", False, f"Exception: {e}")
    
    # Wait for lockout to expire
    print("  Waiting 31 seconds for lockout to expire...")
    time.sleep(31)
    
    # Attempt 5 (should succeed after lockout expires)
    try:
        resp = requests.post(
            f"{BASE_URL}/auth/login",
            json={"username": username, "password": "StrongPass1!"},
            timeout=10,
        )
        if resp.status_code == 200:
            body = resp.json()
            if "access_token" in body:
                log_test("Login after lockout expires", True, f"Got 200 with JWT")
                return body["access_token"]
            else:
                log_test("Login after lockout expires", False, f"Missing access_token: {body}")
                return None
        else:
            log_test("Login after lockout expires", False, f"Expected 200, got {resp.status_code}: {resp.text}")
            return None
    except Exception as e:
        log_test("Login after lockout expires", False, f"Exception: {e}")
        return None


def test_auth_forgot_password():
    """Test POST /api/auth/forgot-password."""
    # Test with wrong email
    try:
        resp = requests.post(
            f"{BASE_URL}/auth/forgot-password",
            json={
                "username": "testera",
                "email": "wrong@example.com",
                "new_password": "NewStrongPass1!",
            },
            timeout=10,
        )
        if resp.status_code == 400:
            body = resp.json()
            if "do not match" in str(body).lower():
                log_test("Forgot password with wrong email", True, f"Got expected 400: {body}")
            else:
                log_test("Forgot password with wrong email", False, f"Got 400 but wrong message: {body}")
        else:
            log_test("Forgot password with wrong email", False, f"Expected 400, got {resp.status_code}: {resp.text}")
    except Exception as e:
        log_test("Forgot password with wrong email", False, f"Exception: {e}")
    
    # Test with correct username+email
    try:
        resp = requests.post(
            f"{BASE_URL}/auth/forgot-password",
            json={
                "username": "testera",
                "email": "testera@example.com",
                "new_password": "NewStrongPass2!",
            },
            timeout=10,
        )
        if resp.status_code == 200:
            body = resp.json()
            if "access_token" in body:
                log_test("Forgot password with correct credentials", True, f"Got 200 with JWT")
                # Verify login with new password
                login_resp = requests.post(
                    f"{BASE_URL}/auth/login",
                    json={"username": "testera", "password": "NewStrongPass2!"},
                    timeout=10,
                )
                if login_resp.status_code == 200:
                    log_test("Login with new password after forgot-password", True, f"Login successful")
                    return login_resp.json()["access_token"]
                else:
                    log_test("Login with new password after forgot-password", False, f"Login failed: {login_resp.status_code}")
                    return body["access_token"]
            else:
                log_test("Forgot password with correct credentials", False, f"Missing access_token: {body}")
                return None
        else:
            log_test("Forgot password with correct credentials", False, f"Expected 200, got {resp.status_code}: {resp.text}")
            return None
    except Exception as e:
        log_test("Forgot password with correct credentials", False, f"Exception: {e}")
        return None


def test_auth_change_password(token: str):
    """Test POST /api/auth/change-password."""
    # Test with wrong current password
    try:
        resp = requests.post(
            f"{BASE_URL}/auth/change-password",
            json={
                "current_password": "WrongPassword1!",
                "new_password": "AnotherStrongPass1!",
            },
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        if resp.status_code == 401:
            log_test("Change password with wrong current password", True, f"Got expected 401")
        else:
            log_test("Change password with wrong current password", False, f"Expected 401, got {resp.status_code}: {resp.text}")
    except Exception as e:
        log_test("Change password with wrong current password", False, f"Exception: {e}")
    
    # Test with correct current password
    try:
        resp = requests.post(
            f"{BASE_URL}/auth/change-password",
            json={
                "current_password": "NewStrongPass2!",
                "new_password": "FinalStrongPass1!",
            },
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        if resp.status_code == 200:
            body = resp.json()
            if body.get("changed") is True:
                log_test("Change password with correct current password", True, f"Got 200 with changed=True")
                # Verify login with new password
                login_resp = requests.post(
                    f"{BASE_URL}/auth/login",
                    json={"username": "testera", "password": "FinalStrongPass1!"},
                    timeout=10,
                )
                if login_resp.status_code == 200:
                    log_test("Login with new password after change-password", True, f"Login successful")
                    return login_resp.json()["access_token"]
                else:
                    log_test("Login with new password after change-password", False, f"Login failed: {login_resp.status_code}")
                    return token
            else:
                log_test("Change password with correct current password", False, f"Expected changed=True, got {body}")
                return token
        else:
            log_test("Change password with correct current password", False, f"Expected 200, got {resp.status_code}: {resp.text}")
            return token
    except Exception as e:
        log_test("Change password with correct current password", False, f"Exception: {e}")
        return token


def test_auth_me(token: str):
    """Test GET /api/auth/me."""
    # Test without token
    try:
        resp = requests.get(f"{BASE_URL}/auth/me", timeout=10)
        if resp.status_code == 401:
            log_test("GET /auth/me without token", True, f"Got expected 401")
        else:
            log_test("GET /auth/me without token", False, f"Expected 401, got {resp.status_code}: {resp.text}")
    except Exception as e:
        log_test("GET /auth/me without token", False, f"Exception: {e}")
    
    # Test with valid token
    try:
        resp = requests.get(
            f"{BASE_URL}/auth/me",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        if resp.status_code == 200:
            body = resp.json()
            if "username" in body and body["username"] == "testera":
                log_test("GET /auth/me with valid token", True, f"Got user object: {body}")
            else:
                log_test("GET /auth/me with valid token", False, f"Unexpected user object: {body}")
        else:
            log_test("GET /auth/me with valid token", False, f"Expected 200, got {resp.status_code}: {resp.text}")
    except Exception as e:
        log_test("GET /auth/me with valid token", False, f"Exception: {e}")


def test_project_scoping():
    """Test project scoping with owner_id."""
    # Login as admin
    try:
        admin_resp = requests.post(
            f"{BASE_URL}/auth/login",
            json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
            timeout=10,
        )
        if admin_resp.status_code != 200:
            log_test("Login as admin", False, f"Failed to login: {admin_resp.status_code}")
            return None, None
        admin_token = admin_resp.json()["access_token"]
        log_test("Login as admin", True, f"Got JWT")
    except Exception as e:
        log_test("Login as admin", False, f"Exception: {e}")
        return None, None
    
    # Login as testerA
    try:
        testera_resp = requests.post(
            f"{BASE_URL}/auth/login",
            json={"username": "testera", "password": "FinalStrongPass1!"},
            timeout=10,
        )
        if testera_resp.status_code != 200:
            log_test("Login as testerA", False, f"Failed to login: {testera_resp.status_code}")
            return admin_token, None
        testera_token = testera_resp.json()["access_token"]
        log_test("Login as testerA", True, f"Got JWT")
    except Exception as e:
        log_test("Login as testerA", False, f"Exception: {e}")
        return admin_token, None
    
    # Admin creates project
    try:
        resp = requests.post(
            f"{BASE_URL}/projects",
            json={"name": "AdminProj", "description": "Admin's project"},
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10,
        )
        if resp.status_code == 200:
            admin_proj_id = resp.json()["id"]
            log_test("Admin creates project", True, f"Created project {admin_proj_id}")
        else:
            log_test("Admin creates project", False, f"Expected 200, got {resp.status_code}: {resp.text}")
            return admin_token, testera_token
    except Exception as e:
        log_test("Admin creates project", False, f"Exception: {e}")
        return admin_token, testera_token
    
    # TesterA creates project
    try:
        resp = requests.post(
            f"{BASE_URL}/projects",
            json={"name": "TesterProj", "description": "TesterA's project"},
            headers={"Authorization": f"Bearer {testera_token}"},
            timeout=10,
        )
        if resp.status_code == 200:
            testera_proj_id = resp.json()["id"]
            log_test("TesterA creates project", True, f"Created project {testera_proj_id}")
        else:
            log_test("TesterA creates project", False, f"Expected 200, got {resp.status_code}: {resp.text}")
            return admin_token, testera_token
    except Exception as e:
        log_test("TesterA creates project", False, f"Exception: {e}")
        return admin_token, testera_token
    
    # Admin lists projects (should see both)
    try:
        resp = requests.get(
            f"{BASE_URL}/projects",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10,
        )
        if resp.status_code == 200:
            projects = resp.json()
            project_names = [p["name"] for p in projects]
            if "AdminProj" in project_names and "TesterProj" in project_names:
                log_test("Admin lists projects (sees both)", True, f"Sees: {project_names}")
            else:
                log_test("Admin lists projects (sees both)", False, f"Expected both projects, got: {project_names}")
        else:
            log_test("Admin lists projects (sees both)", False, f"Expected 200, got {resp.status_code}: {resp.text}")
    except Exception as e:
        log_test("Admin lists projects (sees both)", False, f"Exception: {e}")
    
    # TesterA lists projects (should see only TesterProj)
    try:
        resp = requests.get(
            f"{BASE_URL}/projects",
            headers={"Authorization": f"Bearer {testera_token}"},
            timeout=10,
        )
        if resp.status_code == 200:
            projects = resp.json()
            project_names = [p["name"] for p in projects]
            if "TesterProj" in project_names and "AdminProj" not in project_names:
                log_test("TesterA lists projects (sees only own)", True, f"Sees: {project_names}")
            else:
                log_test("TesterA lists projects (sees only own)", False, f"Expected only TesterProj, got: {project_names}")
        else:
            log_test("TesterA lists projects (sees only own)", False, f"Expected 200, got {resp.status_code}: {resp.text}")
    except Exception as e:
        log_test("TesterA lists projects (sees only own)", False, f"Exception: {e}")
    
    # TesterA tries to GET admin's project (should get 403)
    try:
        resp = requests.get(
            f"{BASE_URL}/projects/{admin_proj_id}",
            headers={"Authorization": f"Bearer {testera_token}"},
            timeout=10,
        )
        if resp.status_code == 403:
            log_test("TesterA GET admin's project (403)", True, f"Got expected 403")
        else:
            log_test("TesterA GET admin's project (403)", False, f"Expected 403, got {resp.status_code}: {resp.text}")
    except Exception as e:
        log_test("TesterA GET admin's project (403)", False, f"Exception: {e}")
    
    # TesterA tries to DELETE admin's project (should get 403)
    try:
        resp = requests.delete(
            f"{BASE_URL}/projects/{admin_proj_id}",
            headers={"Authorization": f"Bearer {testera_token}"},
            timeout=10,
        )
        if resp.status_code == 403:
            log_test("TesterA DELETE admin's project (403)", True, f"Got expected 403")
        else:
            log_test("TesterA DELETE admin's project (403)", False, f"Expected 403, got {resp.status_code}: {resp.text}")
    except Exception as e:
        log_test("TesterA DELETE admin's project (403)", False, f"Exception: {e}")
    
    # Admin deletes own project
    try:
        resp = requests.delete(
            f"{BASE_URL}/projects/{admin_proj_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10,
        )
        if resp.status_code == 200:
            log_test("Admin DELETE own project", True, f"Deleted successfully")
        else:
            log_test("Admin DELETE own project", False, f"Expected 200, got {resp.status_code}: {resp.text}")
    except Exception as e:
        log_test("Admin DELETE own project", False, f"Exception: {e}")
    
    return admin_token, testera_token


def test_upload_and_downstream(admin_token: str):
    """Test multi-file upload and downstream endpoints."""
    # Create fresh project
    try:
        resp = requests.post(
            f"{BASE_URL}/projects",
            json={"name": "DemoProject", "description": "For testing upload and downstream"},
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10,
        )
        if resp.status_code != 200:
            log_test("Create DemoProject", False, f"Failed: {resp.status_code}")
            return None
        proj_id = resp.json()["id"]
        log_test("Create DemoProject", True, f"Created project {proj_id}")
    except Exception as e:
        log_test("Create DemoProject", False, f"Exception: {e}")
        return None
    
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
        # Close file handles
        for _, (_, fh, _) in files:
            fh.close()
        
        if resp.status_code == 200:
            docs = resp.json()
            if len(docs) == 3 and all(d.get("status") == "processing" for d in docs):
                doc_ids = [d["id"] for d in docs]
                log_test("Upload 3 PDFs", True, f"Uploaded 3 documents: {doc_ids}")
            else:
                log_test("Upload 3 PDFs", False, f"Expected 3 processing docs, got: {docs}")
                return None
        else:
            log_test("Upload 3 PDFs", False, f"Expected 200, got {resp.status_code}: {resp.text}")
            return None
    except Exception as e:
        log_test("Upload 3 PDFs", False, f"Exception: {e}")
        return None
    
    # Poll for documents to become ready (max 5 minutes)
    print("  Polling for documents to become ready (max 5 minutes)...")
    max_wait = 300  # 5 minutes
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
                    log_test("Document processing", False, f"Some documents failed: {failed_docs}")
                    return None
                
                if ready_count == 3:
                    all_ready = True
                    log_test("Document processing (all ready)", True, f"All 3 documents ready")
                    break
        except Exception as e:
            print(f"    Polling error: {e}")
        
        time.sleep(poll_interval)
        elapsed += poll_interval
    
    if not all_ready:
        log_test("Document processing (timeout)", False, f"Timeout after {max_wait}s")
        return None
    
    # Get final document list
    try:
        resp = requests.get(
            f"{BASE_URL}/projects/{proj_id}/documents",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10,
        )
        docs = resp.json()
        doc_ids = [d["id"] for d in docs]
    except Exception as e:
        log_test("Get document list", False, f"Exception: {e}")
        return None
    
    # Test GET /documents/{id}/summary for each doc
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
                    log_test(f"GET /documents/{doc_id}/summary", True, f"Has all required keys")
                else:
                    log_test(f"GET /documents/{doc_id}/summary", False, f"Missing keys or status not ready: {body.keys()}")
            else:
                log_test(f"GET /documents/{doc_id}/summary", False, f"Expected 200, got {resp.status_code}: {resp.text}")
        except Exception as e:
            log_test(f"GET /documents/{doc_id}/summary", False, f"Exception: {e}")
    
    # Test GET /documents/{id}/status for first doc
    try:
        resp = requests.get(
            f"{BASE_URL}/documents/{doc_ids[0]}/status",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10,
        )
        if resp.status_code == 200:
            body = resp.json()
            if "summary" in body and body.get("status") == "ready":
                log_test(f"GET /documents/{doc_ids[0]}/status", True, f"Has summary object")
            else:
                log_test(f"GET /documents/{doc_ids[0]}/status", False, f"Missing summary or status not ready")
        else:
            log_test(f"GET /documents/{doc_ids[0]}/status", False, f"Expected 200, got {resp.status_code}: {resp.text}")
    except Exception as e:
        log_test(f"GET /documents/{doc_ids[0]}/status", False, f"Exception: {e}")
    
    # Test POST /claims/{claim_id}/evidence for first claim of doc1
    try:
        # Get claims from doc1
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
                    log_test(f"POST /claims/{claim_id}/evidence", True, f"Got items array (length: {len(body['items'])})")
                else:
                    log_test(f"POST /claims/{claim_id}/evidence", False, f"Missing items in response")
            else:
                log_test(f"POST /claims/{claim_id}/evidence", False, f"Expected 200, got {resp.status_code}: {resp.text}")
        else:
            log_test("POST /claims/{claim_id}/evidence", False, f"No claims found in doc1")
    except Exception as e:
        log_test("POST /claims/{claim_id}/evidence", False, f"Exception: {e}")
    
    # Test POST /documents/{id}/section-evidence on doc2
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
                log_test(f"POST /documents/{doc_ids[1]}/section-evidence", True, f"Got items array (length: {len(body['items'])})")
            else:
                log_test(f"POST /documents/{doc_ids[1]}/section-evidence", False, f"Missing items in response")
        else:
            log_test(f"POST /documents/{doc_ids[1]}/section-evidence", False, f"Expected 200, got {resp.status_code}: {resp.text}")
    except Exception as e:
        log_test(f"POST /documents/{doc_ids[1]}/section-evidence", False, f"Exception: {e}")
    
    # Test GET /projects/{proj_id}/outliers
    try:
        resp = requests.get(
            f"{BASE_URL}/projects/{proj_id}/outliers",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=30,
        )
        if resp.status_code == 200:
            body = resp.json()
            if "points" in body and len(body["points"]) == 3:
                log_test(f"GET /projects/{proj_id}/outliers", True, f"Got 3 points")
            else:
                log_test(f"GET /projects/{proj_id}/outliers", False, f"Expected 3 points, got: {body.get('points', [])}")
        else:
            log_test(f"GET /projects/{proj_id}/outliers", False, f"Expected 200, got {resp.status_code}: {resp.text}")
    except Exception as e:
        log_test(f"GET /projects/{proj_id}/outliers", False, f"Exception: {e}")
    
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
            if "fields" in body and "rows" in body and len(body["rows"]) == 3:
                log_test(f"POST /projects/{proj_id}/matrix", True, f"Got fields and 3 rows")
            else:
                log_test(f"POST /projects/{proj_id}/matrix", False, f"Expected fields and 3 rows, got: {body.keys()}")
        else:
            log_test(f"POST /projects/{proj_id}/matrix", False, f"Expected 200, got {resp.status_code}: {resp.text}")
    except Exception as e:
        log_test(f"POST /projects/{proj_id}/matrix", False, f"Exception: {e}")
    
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
                log_test(f"POST /projects/{proj_id}/ask", True, f"Got answer, citations, overall_tier")
            else:
                log_test(f"POST /projects/{proj_id}/ask", False, f"Missing keys: {body.keys()}")
        else:
            log_test(f"POST /projects/{proj_id}/ask", False, f"Expected 200, got {resp.status_code}: {resp.text}")
    except Exception as e:
        log_test(f"POST /projects/{proj_id}/ask", False, f"Exception: {e}")
    
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
                log_test(f"POST /projects/{proj_id}/check", True, f"Got all required keys")
            else:
                log_test(f"POST /projects/{proj_id}/check", False, f"Missing keys: {body.keys()}")
        else:
            log_test(f"POST /projects/{proj_id}/check", False, f"Expected 200, got {resp.status_code}: {resp.text}")
    except Exception as e:
        log_test(f"POST /projects/{proj_id}/check", False, f"Exception: {e}")
    
    # Cleanup: Delete DemoProject
    try:
        resp = requests.delete(
            f"{BASE_URL}/projects/{proj_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10,
        )
        if resp.status_code == 200:
            log_test(f"DELETE DemoProject", True, f"Deleted successfully")
        else:
            log_test(f"DELETE DemoProject", False, f"Expected 200, got {resp.status_code}: {resp.text}")
    except Exception as e:
        log_test(f"DELETE DemoProject", False, f"Exception: {e}")
    
    return proj_id


def main():
    """Run all backend tests."""
    print("=" * 80)
    print("JurnalMap Backend Test Suite")
    print("=" * 80)
    print()
    
    # 1. Health check
    print("### 1. Health Check")
    if not test_health():
        print("\n❌ Health check failed. Aborting tests.")
        sys.exit(1)
    print()
    
    # 2. Auth flow
    print("### 2. Auth Flow")
    test_auth_register_weak_passwords()
    test_auth_register_duplicate_username()
    testera_token = test_auth_register_new_user()
    test_auth_register_duplicate_email()
    testera_token = test_auth_login_lockout()
    testera_token = test_auth_forgot_password()
    if testera_token:
        testera_token = test_auth_change_password(testera_token)
        test_auth_me(testera_token)
    print()
    
    # 3. Project scoping
    print("### 3. Project Scoping")
    admin_token, testera_token = test_project_scoping()
    print()
    
    # 4. Upload and downstream
    if admin_token:
        print("### 4. Upload and Downstream Endpoints")
        test_upload_and_downstream(admin_token)
        print()
    
    # Summary
    print("=" * 80)
    print("Test Summary")
    print("=" * 80)
    passed = sum(1 for r in test_results if r["passed"])
    failed = sum(1 for r in test_results if not r["passed"])
    total = len(test_results)
    
    print(f"Total: {total}, Passed: {passed}, Failed: {failed}")
    print()
    
    if failed > 0:
        print("Failed tests:")
        for r in test_results:
            if not r["passed"]:
                print(f"  ❌ {r['name']}")
                if r["details"]:
                    print(f"     {r['details']}")
        print()
    
    print("=" * 80)
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
