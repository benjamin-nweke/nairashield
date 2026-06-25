"""
Integration test suite for NairaShield JWT Authentication & RBAC.
Prerequisite: The Flask API must be running on http://localhost:5000.
"""

import requests
import sys

BASE_URL = "http://localhost:5000"

def run_tests():
    print("==============================================================")
    print(" NairaShield REST API JWT & RBAC Integration Tests")
    print("==============================================================")
    
    # 1. Test public route
    print("\n[Test 1] Testing public root endpoint '/'...")
    r = requests.get(f"{BASE_URL}/")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    print(" -> PASS (HTML page loaded successfully)")
    
    # 2. Test missing token protection
    print("\n[Test 2] Testing unprotected access to '/health'...")
    r = requests.get(f"{BASE_URL}/health")
    assert r.status_code == 401, f"Expected 401, got {r.status_code}"
    assert "Token is missing" in r.json().get("error", ""), "Expected 'Token is missing' error message"
    print(" -> PASS (Unauthorized access blocked with 401)")
    
    # 3. Test invalid login
    print("\n[Test 3] Testing authentication with invalid credentials...")
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"username": "admin", "password": "wrongpassword"})
    assert r.status_code == 401, f"Expected 401, got {r.status_code}"
    assert "Invalid username or password" in r.json().get("error", ""), "Expected 'Invalid username or password' error"
    print(" -> PASS (Invalid login blocked)")
    
    # 4. Authenticate all three roles
    print("\n[Test 4] Authenticating Viewer, Analyst, and Admin...")
    
    # Viewer
    r_viewer = requests.post(f"{BASE_URL}/api/auth/login", json={"username": "viewer", "password": "viewer123"}).json()
    token_viewer = r_viewer["access_token"]
    refresh_viewer = r_viewer["refresh_token"]
    print(f" -> Authenticated Viewer (Role: {r_viewer['role']})")
    
    # Analyst
    r_analyst = requests.post(f"{BASE_URL}/api/auth/login", json={"username": "analyst", "password": "analyst123"}).json()
    token_analyst = r_analyst["access_token"]
    print(f" -> Authenticated Analyst (Role: {r_analyst['role']})")
    
    # Admin
    r_admin = requests.post(f"{BASE_URL}/api/auth/login", json={"username": "admin", "password": "admin123"}).json()
    token_admin = r_admin["access_token"]
    print(f" -> Authenticated Admin (Role: {r_admin['role']})")
    
    # 5. Role-based Access Control (RBAC) - Viewer Role Permissions
    print("\n[Test 5] Checking Viewer (Read-only) permissions...")
    headers_viewer = {"Authorization": f"Bearer {token_viewer}"}
    
    # Can access /health
    r = requests.get(f"{BASE_URL}/health", headers=headers_viewer)
    assert r.status_code == 200, f"Viewer expected 200 on /health, got {r.status_code}"
    
    # Can access /predict
    dummy_tx = {
        "amount": 0.5,
        "channel_TRANSFER": 1.0,
        "source_dataset_PaySim": 1.0
    }
    r = requests.post(f"{BASE_URL}/predict", json=dummy_tx, headers=headers_viewer)
    assert r.status_code == 200, f"Viewer expected 200 on /predict, got {r.status_code}"
    
    # Can access /api/transactions
    r = requests.get(f"{BASE_URL}/api/transactions", headers=headers_viewer)
    assert r.status_code == 200, f"Viewer expected 200 on /api/transactions, got {r.status_code}"
    
    # CANNOT access /api/flag
    r = requests.post(f"{BASE_URL}/api/flag", json={"alert_id": "ALT998008"}, headers=headers_viewer)
    assert r.status_code == 403, f"Viewer expected 403 on /api/flag, got {r.status_code}"
    
    # CANNOT access /api/admin/config
    r = requests.post(f"{BASE_URL}/api/admin/config", json={"fraud_threshold": 0.3}, headers=headers_viewer)
    assert r.status_code == 403, f"Viewer expected 403 on /api/admin/config, got {r.status_code}"
    print(" -> PASS (Viewer restricted from writing or modifying configurations)")
    
    # 6. Role-based Access Control (RBAC) - Analyst Role Permissions
    print("\n[Test 6] Checking Analyst (View & Flag) permissions...")
    headers_analyst = {"Authorization": f"Bearer {token_analyst}"}
    
    # Can access /health and /predict
    assert requests.get(f"{BASE_URL}/health", headers=headers_analyst).status_code == 200
    assert requests.post(f"{BASE_URL}/predict", json=dummy_tx, headers=headers_analyst).status_code == 200
    
    # Can access /api/flag (returns 200 or 404, but definitely not 403)
    r = requests.post(f"{BASE_URL}/api/flag", json={"alert_id": "ALT998008", "action": "BLOCKED"}, headers=headers_analyst)
    assert r.status_code in [200, 404], f"Analyst expected 200/404 on /api/flag, got {r.status_code}"
    
    # CANNOT access /api/admin/config
    r = requests.post(f"{BASE_URL}/api/admin/config", json={"fraud_threshold": 0.3}, headers=headers_analyst)
    assert r.status_code == 403, f"Analyst expected 403 on /api/admin/config, got {r.status_code}"
    print(" -> PASS (Analyst allowed to flag alerts but restricted from admin setting changes)")
    
    # 7. Role-based Access Control (RBAC) - Admin Role Permissions
    print("\n[Test 7] Checking Admin (Full Access) permissions...")
    headers_admin = {"Authorization": f"Bearer {token_admin}"}
    
    # Send test predict to get initial probability
    test_tx = {
        "amount": 0.65,
        "channel_TRANSFER": 1.0,
        "source_dataset_PaySim": 1.0
    }
    r_init = requests.post(f"{BASE_URL}/predict", json=test_tx, headers=headers_admin).json()
    prob = r_init["fraud_probability"]
    print(f" -> Initial prediction probability: {prob}")
    
    # We will test threshold adjustment relative to the returned probability
    # Case A: Threshold is set HIGHER than the probability -> prediction should be 0
    # Formula: halfway between prob and 1.0
    high_threshold = round(prob + (1.0 - prob) / 2.0, 4)
    r = requests.post(f"{BASE_URL}/api/admin/config", json={"fraud_threshold": high_threshold}, headers=headers_admin)
    assert r.status_code == 200, f"Admin expected 200 on /api/admin/config, got {r.status_code}"
    
    r_pred = requests.post(f"{BASE_URL}/predict", json=test_tx, headers=headers_admin).json()
    assert r_pred["prediction"] == 0, f"Expected prediction to be 0 for threshold {high_threshold}, got {r_pred['prediction']} (prob: {r_pred['fraud_probability']})"
    
    # Case B: Threshold is set LOWER than the probability -> prediction should be 1
    # Formula: halfway between 0.0 and prob
    low_threshold = round(prob / 2.0, 4)
    requests.post(f"{BASE_URL}/api/admin/config", json={"fraud_threshold": low_threshold}, headers=headers_admin)
    
    r_pred = requests.post(f"{BASE_URL}/predict", json=test_tx, headers=headers_admin).json()
    assert r_pred["prediction"] == 1, f"Expected prediction to be 1 for threshold {low_threshold}, got {r_pred['prediction']} (prob: {r_pred['fraud_probability']})"
    
    # Restore threshold to 0.50
    requests.post(f"{BASE_URL}/api/admin/config", json={"fraud_threshold": 0.50}, headers=headers_admin)
    print(" -> PASS (Admin successfully configured system and verified threshold propagation)")
    
    # 8. Token Refresh Flow
    print("\n[Test 8] Testing token refresh endpoint...")
    r = requests.post(f"{BASE_URL}/api/auth/refresh", json={"refresh_token": refresh_viewer})
    assert r.status_code == 200, f"Expected 200 on refresh, got {r.status_code}"
    new_access_token = r.json().get("access_token")
    assert new_access_token is not None
    
    # Test new token works
    r = requests.get(f"{BASE_URL}/health", headers={"Authorization": f"Bearer {new_access_token}"})
    assert r.status_code == 200, f"Refreshed token failed on /health check: {r.status_code}"
    print(" -> PASS (Token refresh successfully generated a functional access token)")
    
    # 9. Token Logout & Blocklist Revocation Flow
    print("\n[Test 9] Testing token logout revocation...")
    # Logout Viewer
    r = requests.post(f"{BASE_URL}/api/auth/logout", headers={"Authorization": f"Bearer {new_access_token}"})
    assert r.status_code == 200, f"Expected 200 on logout, got {r.status_code}"
    
    # Try using the logged-out token
    r = requests.get(f"{BASE_URL}/health", headers={"Authorization": f"Bearer {new_access_token}"})
    assert r.status_code == 401, f"Expected 401 on revoked token, got {r.status_code}"
    assert "revoked" in r.json().get("error", "").lower(), f"Expected 'revoked' error message, got {r.json()}"
    print(" -> PASS (Token revoked and blocklist successfully intercepts subsequent calls)")

    # 10. Test Public Registration
    print("\n[Test 10] Testing public registration...")
    reg_data = {
        "username": "new_viewer",
        "password": "newpassword123",
        "role": "Viewer"
    }
    # Clean up username if it already exists from a previous run
    # (By reloading users we don't need manual cleanup, but let's register with a unique timestamp-based or static name)
    import time
    unique_user = f"user_{int(time.time())}"
    reg_data["username"] = unique_user
    
    r = requests.post(f"{BASE_URL}/api/auth/register", json=reg_data)
    assert r.status_code == 201, f"Expected 201 on registration, got {r.status_code}: {r.text}"
    res = r.json()
    assert "access_token" in res, "Expected access token in registration response"
    
    # Test new registered user login works
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"username": unique_user, "password": "newpassword123"})
    assert r.status_code == 200, f"Expected 200 on login for registered user, got {r.status_code}"
    print(" -> PASS (Public registration and login of registered user succeeded)")

    # 11. Test Admin User Creation
    print("\n[Test 11] Testing administrative user provisioning...")
    unique_prov_user = f"prov_{int(time.time())}"
    admin_prov_data = {
        "username": unique_prov_user,
        "password": "provpassword123",
        "role": "Analyst"
    }
    r = requests.post(f"{BASE_URL}/api/admin/create-user", json=admin_prov_data, headers=headers_admin)
    assert r.status_code == 201, f"Expected 201 on admin user creation, got {r.status_code}: {r.text}"
    
    # Verify the provisioned analyst can log in
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"username": unique_prov_user, "password": "provpassword123"})
    assert r.status_code == 200, f"Expected 200 on login for provisioned user, got {r.status_code}"
    prov_user_data = r.json()
    assert prov_user_data["role"] == "Analyst", f"Expected Analyst role, got {prov_user_data['role']}"
    
    # Verify a Viewer cannot provision a user
    r = requests.post(f"{BASE_URL}/api/admin/create-user", json=admin_prov_data, headers=headers_viewer)
    assert r.status_code == 403, f"Expected 403 when Viewer attempts user creation, got {r.status_code}"
    print(" -> PASS (Admin provisioning succeeded and role restrictions enforced)")

    print("\n==============================================================")
    print(" All NairaShield Auth/RBAC Tests Completed Successfully!")
    print("==============================================================")

if __name__ == "__main__":
    try:
        run_tests()
    except AssertionError as e:
        print(f"\n[FAIL] Test failure: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Test run error: {e}")
        sys.exit(2)
