import subprocess
import time
import sys
import requests
import os

def main():
    print("Launching test instance of updated Flask API on port 5005...")
    
    runner_code = """
import sys
sys._antigravity_api_mode = True
try:
    import api
    if api.FLASK_AVAILABLE:
        api.start_flask_server(5005)
    else:
        api.start_fallback_server(5005)
except Exception as e:
    import traceback
    print("CRITICAL SERVER START ERROR:", e)
    traceback.print_exc()
    sys.exit(1)
"""
    with open("temp_runner.py", "w") as f:
        f.write(runner_code)
        
    # Open log files for output to avoid pipe buffering blocks
    stdout_file = open("server_stdout.log", "w")
    stderr_file = open("server_stderr.log", "w")
    
    proc = subprocess.Popen([sys.executable, "-u", "temp_runner.py"], stdout=stdout_file, stderr=stderr_file)
    time.sleep(4.0) # Wait for server to bind
    
    # Check if the process crashed immediately
    if proc.poll() is not None:
        stdout_file.close()
        stderr_file.close()
        print("Server failed to start. Reading server logs:")
        with open("server_stderr.log", "r") as f:
            print(f.read())
        with open("server_stdout.log", "r") as f:
            print(f.read())
        sys.exit(1)
        
    print("Server started. Running integration tests against port 5005...")
    
    try:
        with open("test_auth.py", "r") as f:
            code = f.read()
            
        test_code = code.replace('BASE_URL = "http://localhost:5000"', 'BASE_URL = "http://localhost:5005"')
        with open("temp_test.py", "w") as f:
            f.write(test_code)
            
        test_proc = subprocess.run([sys.executable, "temp_test.py"], capture_output=True, text=True)
        print("Test execution output:")
        print(test_proc.stdout)
        if test_proc.returncode != 0:
            print("Test execution failed with errors:")
            print(test_proc.stderr)
            
            # Print server logs as well in case of test failure
            stdout_file.flush()
            stderr_file.flush()
            print("=== Server Stdout ===")
            with open("server_stdout.log", "r") as f:
                print(f.read())
            print("=== Server Stderr ===")
            with open("server_stderr.log", "r") as f:
                print(f.read())
                
            sys.exit(test_proc.returncode)
    finally:
        print("Cleaning up test server and temp files...")
        proc.terminate()
        proc.wait()
        stdout_file.close()
        stderr_file.close()
        for temp_file in ["temp_runner.py", "temp_test.py", "server_stdout.log", "server_stderr.log"]:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception:
                    pass
        
if __name__ == "__main__":
    main()
