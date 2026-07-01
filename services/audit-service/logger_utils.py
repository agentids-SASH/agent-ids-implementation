import time
import requests
import threading

# ANSI color codes
COLORS = {
    "Provider": "\033[92m",   # Green
    "Agent": "\033[96m",      # Cyan
    "Developer": "\033[94m",  # Blue
    "Audit": "\033[93m",      # Yellow
    "Deployer": "\033[95m",   # Magenta
    "Bank": "\033[91m",       # Light Red
}
RESET = "\033[0m"

def submit_log_async(actor: str, message: str, timestamp: float):
    try:
        payload = {
            "timestamp": timestamp,
            "actor": actor,
            "message": message
        }
        # Central Registry on port 8000
        requests.post("http://127.0.0.1:8000/api/logs", json=payload, timeout=0.5)
    except Exception:
        pass

def log_event(actor: str, message: str):
    now = time.time()
    local_time = time.localtime(now)
    time_str = time.strftime("%Y-%m-%d %H:%M:%S", local_time)
    ms = int((now - int(now)) * 1000)
    timestamp_str = f"{time_str}.{ms:03d}"
    
    color = COLORS.get(actor, RESET)
    
    # Print formatted message locally
    print(f"{timestamp_str} - {color}[{actor}]{RESET} - {message}", flush=True)
    
    # Post to Central Aggregator asynchronously
    threading.Thread(target=submit_log_async, args=(actor, message, now), daemon=True).start()
