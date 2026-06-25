import os
import sys
import json

# Ensure parent directory is in path to import api.py
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from api import app
    print("[OK] Imported api.py successfully")
except ImportError as e:
    print(f"[FAIL] Could not import api.py: {e}")
    sys.exit(1)

def run_verification():
    # Create test client
    client = app.test_client()
    
    print("\n--- Verifying Authentication and Token Generation ---")
    login_payload = {
        "username": "admin",
        "password": "admin123"
    }
    
    response = client.post("/api/auth/login", json=login_payload)
    if response.status_code != 200:
        print(f"[FAIL] Login failed with status {response.status_code}: {response.data.decode()}")
        sys.exit(1)
        
    data = json.loads(response.data.decode())
    token = data.get("access_token")
    if not token:
        print("[FAIL] Access token not found in login response")
        sys.exit(1)
    print("[OK] Authenticated successfully, retrieved JWT access token")
    
    print("\n--- Verifying PDF Report Download Endpoint ---")
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    response = client.get("/api/report/download", headers=headers)
    if response.status_code != 200:
        print(f"[FAIL] PDF Download failed with status {response.status_code}: {response.data.decode() if response.data else 'No data'}")
        sys.exit(1)
        
    mimetype = response.mimetype or response.headers.get("Content-Type")
    if "application/pdf" not in mimetype:
        print(f"[FAIL] Expected PDF mimetype, got: {mimetype}")
        sys.exit(1)
        
    print(f"[OK] PDF endpoint returned status 200 with Content-Type: {mimetype}")
    
    # Save the output file
    output_pdf = os.path.join(os.path.dirname(__file__), "test_downloaded_report.pdf")
    with open(output_pdf, "wb") as f:
        f.write(response.data)
        
    if not os.path.exists(output_pdf) or os.path.getsize(output_pdf) == 0:
        print("[FAIL] Saved PDF report file is missing or empty")
        sys.exit(1)
        
    # Check PDF magic bytes
    with open(output_pdf, "rb") as f:
        header_bytes = f.read(4)
        if header_bytes != b"%PDF":
            print(f"[FAIL] PDF magic bytes mismatch. Got: {header_bytes}")
            sys.exit(1)
            
    print(f"[OK] Report successfully saved and verified: {output_pdf} ({os.path.getsize(output_pdf) / 1024:.1f} KB)")
    print("PDF MAGIC BYTES CONFIRMED: %PDF")
    print("\nVerification successful!")

if __name__ == "__main__":
    run_verification()
