import sys
import json
import time
import os

# Disable welcome boot screen prints during tests
sys._antigravity_api_mode = True

from api import app, load_users, save_users

def run_in_process_tests():
    print("==============================================================")
    print(" NairaShield In-Process Flask Client Integration Tests")
    print("==============================================================")
    
    client = app.test_client()
    
    # Test 1: Register a new user
    print("\n[Test 1] Testing public registration (/api/auth/register)...")
    unique_username = f"user_{int(time.time())}"
    reg_payload = {
        "username": unique_username,
        "password": "testpassword123",
        "role": "Viewer"
    }
    
    res = client.post('/api/auth/register', json=reg_payload)
    print(f" -> Status: {res.status_code}")
    print(f" -> Body: {res.json}")
    assert res.status_code == 201, f"Expected 201, got {res.status_code}"
    assert "access_token" in res.json
    assert res.json["username"] == unique_username
    assert res.json["role"] == "Viewer"
    
    # Test 2: Verify duplicate registration is blocked
    print("\n[Test 2] Testing duplicate registration block...")
    res = client.post('/api/auth/register', json=reg_payload)
    print(f" -> Status: {res.status_code}")
    print(f" -> Body: {res.json}")
    assert res.status_code == 400, f"Expected 400, got {res.status_code}"
    assert "already in use" in res.json.get("error", "")
    
    # Test 3: Verify the newly registered user can log in
    print("\n[Test 3] Testing newly registered user login...")
    login_payload = {
        "username": unique_username,
        "password": "testpassword123"
    }
    res = client.post('/api/auth/login', json=login_payload)
    print(f" -> Status: {res.status_code}")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    new_user_token = res.json["access_token"]
    
    # Test 4: Access protected /health endpoint with the new token
    print("\n[Test 4] Testing access to protected endpoints with new token...")
    res = client.get('/health', headers={"Authorization": f"Bearer {new_user_token}"})
    print(f" -> Status: {res.status_code}")
    print(f" -> Body: {res.json}")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    
    # Test 5: Verify the Admin can login and get admin token
    print("\n[Test 5] Authenticating Admin...")
    res = client.post('/api/auth/login', json={"username": "admin", "password": "admin123"})
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    admin_token = res.json["access_token"]
    
    # Test 6: Verify Admin user provisioning endpoint (/api/admin/create-user)
    print("\n[Test 6] Testing Admin user provisioning...")
    prov_username = f"prov_{int(time.time())}"
    prov_payload = {
        "username": prov_username,
        "password": "provpassword123",
        "role": "Analyst"
    }
    res = client.post('/api/admin/create-user', json=prov_payload, headers={"Authorization": f"Bearer {admin_token}"})
    print(f" -> Status: {res.status_code}")
    print(f" -> Body: {res.json}")
    assert res.status_code == 201, f"Expected 201, got {res.status_code}"
    
    # Verify the provisioned analyst can log in
    res = client.post('/api/auth/login', json={"username": prov_username, "password": "provpassword123"})
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    assert res.json["role"] == "Analyst"
    
    # Test 7: Verify non-admin (Viewer) cannot provision a user
    print("\n[Test 7] Verifying role restriction (Viewer cannot provision a user)...")
    res = client.post('/api/admin/create-user', json=prov_payload, headers={"Authorization": f"Bearer {new_user_token}"})
    print(f" -> Status: {res.status_code}")
    print(f" -> Body: {res.json}")
    assert res.status_code == 403, f"Expected 403, got {res.status_code}"
    
    print("\n==============================================================")
    print(" All In-Process Endpoint Tests Passed Successfully!")
    print("==============================================================")

if __name__ == "__main__":
    try:
        run_in_process_tests()
    except AssertionError as e:
        print(f"\n[FAIL] Assertion failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Test run crashed: {e}")
        sys.exit(2)
