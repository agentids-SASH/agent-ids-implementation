import os
import subprocess
import sys
import time

# Resolve the absolute path of the workspace root from the scripts folder
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)
SERVICES_DIR = os.path.join(BASE_DIR, "services")

services = {
    "Registry": (os.path.join(SERVICES_DIR, "agent-registry"), 8000),
    "Runtime": (os.path.join(SERVICES_DIR, "agent-runtime"), 8001),
    "Identity": (os.path.join(SERVICES_DIR, "agent-identity"), 8002),
    "Bank": (os.path.join(SERVICES_DIR, "bank-service"), 8003),
    "Audit": (os.path.join(SERVICES_DIR, "audit-service"), 8004),
}

processes = []
try:
    for name, (path, port) in services.items():
        print(f"Starting {name} on port {port}...")
        p = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(port)],
            cwd=path
        )
        processes.append(p)
        time.sleep(0.5)
    
    print("\nAll services running. Press Ctrl+C to stop all.\n")
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\nStopping services...")
    for p in processes:
        p.terminate()
