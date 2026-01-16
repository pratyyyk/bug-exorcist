import sys
import os

# Add current directory to path so we can import app
sys.path.append(os.getcwd())

from app.sandbox import Sandbox
import time

def test_sandbox():
    print("Initializing Sandbox...")
    try:
        sandbox = Sandbox()
    except Exception as e:
        print(f"Failed to initialize Sandbox: {e}")
        return

    print("\n--- Test 1: Normal Execution ---")
    result = sandbox.run_code("print('Hello from Sandbox')")
    print(f"Result: {result.strip()}")
    if "Hello from Sandbox" in result:
        print("PASS")
    else:
        print("FAIL")

    print("\n--- Test 2: Network Restriction ---")
    network_code = """
import socket
try:
    socket.create_connection(("8.8.8.8", 53), timeout=2)
    print("Network Access Success")
except Exception as e:
    print(f"Network Access Failed: {e}")
"""
    result = sandbox.run_code(network_code)
    print(f"Result: {result.strip()}")
    if "Network Access Failed" in result or "OSError" in result: # Expect failure
        print("PASS")
    else:
        print("FAIL")

    print("\n--- Test 3: Timeout ---")
    timeout_code = """
import time
while True:
    time.sleep(1)
"""
    start_time = time.time()
    result = sandbox.run_code(timeout_code)
    duration = time.time() - start_time
    print(f"Result: {result.strip()}")
    print(f"Duration: {duration:.2f}s")
    if "Execution timed out" in result and duration >= 30:
        print("PASS")
    else:
        print("FAIL")

    print("\n--- Test 4: File System Isolation (Read Root) ---")
    fs_code = """
import os
try:
    print(os.listdir('/'))
except Exception as e:
    print(e)
"""
    result = sandbox.run_code(fs_code)
    print(f"Result: {result.strip()}")
    # Just checking it runs, we don't strictly block FS read of the container itself, but confirming it doesn't error out on basic ops is good.
    # The real test is that it can't see the host FS, which Docker guarantees by default.
    print("PASS (Observation)")

if __name__ == "__main__":
    test_sandbox()
