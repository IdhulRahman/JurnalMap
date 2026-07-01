#!/usr/bin/env python3
"""
Test downstream endpoints with existing ready documents.
"""
import requests
import sys

BASE_URL = "https://8ae4e47a-c558-4ee8-a207-6fce7d1b5e4d.preview.emergentagent.com/api"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin"

def main():
    print("=" * 80)
    print("Testing Downstream Endpoints with Existing Documents")
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
            print(f"❌ Failed to login: {resp.status_code}")
            return 1
        admin_token = resp.json()["access_token"]
        print("✅ Logged in as admin")
    except Exception as e:
        print(f"❌ Exception: {e}")
        return 1
    
    # Get all projects
    try:
        resp = requests.get(
            f"{BASE_URL}/projects",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10,
        )
        projects = resp.json()
        print(f"\n📁 Found {len(projects)} projects")
    except Exception as e:
        print(f"❌ Failed to get projects: {e}")
        return 1
    
    # Find a project with ready documents
    ready_docs = []
    proj_id = None
    
    for proj in projects:
        try:
            resp = requests.get(
                f"{BASE_URL}/projects/{proj['id']}/documents",
                headers={"Authorization": f"Bearer {admin_token}"},
                timeout=10,
            )
            docs = resp.json()
            ready = [d for d in docs if d.get("status") == "ready"]
            if ready:
                ready_docs = ready
                proj_id = proj["id"]
                print(f"✅ Found project '{proj['name']}' with {len(ready)} ready documents")
                break
        except Exception as e:
            continue
    
    if not ready_docs:
        print("❌ No ready documents found in any project")
        return 1
    
    doc_ids = [d["id"] for d in ready_docs]
    print(f"   Document IDs: {doc_ids[:3]}")  # Show first 3
    
    # Test downstream endpoints
    print("\n### Testing Downstream Endpoints")
    
    # 1. GET /documents/{id}/summary
    try:
        resp = requests.get(
            f"{BASE_URL}/documents/{doc_ids[0]}/summary",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10,
        )
        if resp.status_code == 200:
            body = resp.json()
            required = ["title", "summary", "sections", "claims", "status"]
            if all(k in body for k in required):
                print(f"✅ GET /documents/{{id}}/summary - All keys present")
            else:
                print(f"❌ GET /documents/{{id}}/summary - Missing keys")
        else:
            print(f"❌ GET /documents/{{id}}/summary - Status {resp.status_code}")
    except Exception as e:
        print(f"❌ GET /documents/{{id}}/summary - Exception: {e}")
    
    # 2. GET /documents/{id}/status
    try:
        resp = requests.get(
            f"{BASE_URL}/documents/{doc_ids[0]}/status",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10,
        )
        if resp.status_code == 200:
            body = resp.json()
            if "summary" in body and body.get("status") == "ready":
                print(f"✅ GET /documents/{{id}}/status - Has summary object")
            else:
                print(f"❌ GET /documents/{{id}}/status - Missing summary or wrong status")
        else:
            print(f"❌ GET /documents/{{id}}/status - Status {resp.status_code}")
    except Exception as e:
        print(f"❌ GET /documents/{{id}}/status - Exception: {e}")
    
    # 3. POST /claims/{claim_id}/evidence
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
                    print(f"✅ POST /claims/{{claim_id}}/evidence - Got items array (len={len(body['items'])})")
                else:
                    print(f"❌ POST /claims/{{claim_id}}/evidence - Missing items")
            else:
                print(f"❌ POST /claims/{{claim_id}}/evidence - Status {resp.status_code}")
        else:
            print(f"⚠️  POST /claims/{{claim_id}}/evidence - No claims found")
    except Exception as e:
        print(f"❌ POST /claims/{{claim_id}}/evidence - Exception: {e}")
    
    # 4. POST /documents/{id}/section-evidence
    try:
        resp = requests.post(
            f"{BASE_URL}/documents/{doc_ids[0]}/section-evidence",
            json={"text": "blockchain trust management"},
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=30,
        )
        if resp.status_code == 200:
            body = resp.json()
            if "items" in body:
                print(f"✅ POST /documents/{{id}}/section-evidence - Got items array (len={len(body['items'])})")
            else:
                print(f"❌ POST /documents/{{id}}/section-evidence - Missing items")
        else:
            print(f"❌ POST /documents/{{id}}/section-evidence - Status {resp.status_code}")
    except Exception as e:
        print(f"❌ POST /documents/{{id}}/section-evidence - Exception: {e}")
    
    # 5. GET /projects/{proj_id}/outliers
    try:
        resp = requests.get(
            f"{BASE_URL}/projects/{proj_id}/outliers",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=30,
        )
        if resp.status_code == 200:
            body = resp.json()
            if "points" in body:
                print(f"✅ GET /projects/{{proj_id}}/outliers - Got {len(body['points'])} points")
            else:
                print(f"❌ GET /projects/{{proj_id}}/outliers - Missing points")
        else:
            print(f"❌ GET /projects/{{proj_id}}/outliers - Status {resp.status_code}")
    except Exception as e:
        print(f"❌ GET /projects/{{proj_id}}/outliers - Exception: {e}")
    
    # 6. POST /projects/{proj_id}/matrix
    try:
        resp = requests.post(
            f"{BASE_URL}/projects/{proj_id}/matrix",
            json={},
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=60,
        )
        if resp.status_code == 200:
            body = resp.json()
            if "fields" in body and "rows" in body:
                print(f"✅ POST /projects/{{proj_id}}/matrix - Got fields and {len(body['rows'])} rows")
            else:
                print(f"❌ POST /projects/{{proj_id}}/matrix - Missing fields or rows")
        else:
            print(f"❌ POST /projects/{{proj_id}}/matrix - Status {resp.status_code}")
    except Exception as e:
        print(f"❌ POST /projects/{{proj_id}}/matrix - Exception: {e}")
    
    # 7. POST /projects/{proj_id}/ask
    try:
        resp = requests.post(
            f"{BASE_URL}/projects/{proj_id}/ask",
            json={"question": "What methods are used for trust management?"},
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=60,
        )
        if resp.status_code == 200:
            body = resp.json()
            required = ["answer", "citations", "overall_tier"]
            if all(k in body for k in required):
                print(f"✅ POST /projects/{{proj_id}}/ask - Got all required keys")
            else:
                print(f"❌ POST /projects/{{proj_id}}/ask - Missing keys")
        else:
            print(f"❌ POST /projects/{{proj_id}}/ask - Status {resp.status_code}")
    except Exception as e:
        print(f"❌ POST /projects/{{proj_id}}/ask - Exception: {e}")
    
    # 8. POST /projects/{proj_id}/check
    try:
        resp = requests.post(
            f"{BASE_URL}/projects/{proj_id}/check",
            json={"text": "Blockchain provides tamper-resistant trust in federated learning."},
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=60,
        )
        if resp.status_code == 200:
            body = resp.json()
            required = ["units", "summary", "annotated_html", "badges", "references_used"]
            if all(k in body for k in required):
                print(f"✅ POST /projects/{{proj_id}}/check - Got all required keys")
            else:
                print(f"❌ POST /projects/{{proj_id}}/check - Missing keys")
        else:
            print(f"❌ POST /projects/{{proj_id}}/check - Status {resp.status_code}")
    except Exception as e:
        print(f"❌ POST /projects/{{proj_id}}/check - Exception: {e}")
    
    print("\n" + "=" * 80)
    print("Downstream endpoint testing complete")
    print("=" * 80)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
