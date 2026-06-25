"""
NairaShield Unified Application Runner.
Executes the custom antigravity welcome sequence, boots the REST API server,
and automatically opens the Web GUI dashboard in the browser.
"""

import sys
import threading
import time
import webbrowser

# 1. Set the flag to direct antigravity to bypass the CLI dashboard
sys._antigravity_api_mode = True

print("Initializing NairaShield AI System Core...")
time.sleep(0.5)

# 2. Import antigravity to trigger the green-and-white security boot sequence
import antigravity

# 3. Thread helper to open the Web GUI after the server binds to port 5000
def launch_browser():
    time.sleep(1.8)  # Wait for server startup logging to complete
    print("\n[Browser Launcher] Opening NairaShield Fraud Detection Portal...")
    webbrowser.open("http://localhost:5000/")

browser_thread = threading.Thread(target=launch_browser, daemon=True)
browser_thread.start()

# 4. Import and start the API Server
try:
    import api
except ImportError as e:
    print(f"[Error] Failed to load REST API module: {e}")
    sys.exit(1)

import os
port_number = int(os.environ.get("PORT", 5000))

if api.FLASK_AVAILABLE:
    api.start_flask_server(port_number)
else:
    api.start_fallback_server(port_number)

