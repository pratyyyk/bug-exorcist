import sys
import os
import asyncio

# Add current directory to path so we can import app
sys.path.append(os.getcwd())

from app.sandbox import Sandbox
import time

async def test_sandbox():
    print("Initializing Sandbox...")
    try:
        sandbox = Sandbox()
    except Exception as e:
        print(f"Failed to initialize Sandbox: {e}")
        return

    print("\n--- Test 1: Normal Execution ---")
    result = await sandbox.run_code("print('Hello from Sandbox')")
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
    result = await sandbox.run_code(network_code)
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
    result = await sandbox.run_code(timeout_code)
    duration = time.time() - start_time
    print(f"Result: {result.strip()} (Duration: {duration:.2f}s)")
    if "timed out" in result:
        print("PASS")
    else:
        print("FAIL")

if __name__ == "__main__":
    asyncio.run(test_sandbox())
