import sys
import time
import requests

REGISTRY_URL = "http://localhost:8000/api/agents"

def main():
    print("=== Agent ID Platform - Deployer CLI Simulation ===")
    print("Initiating agent provisioning process...")

    # Define the agent configuration payload
    payload = {
        "name": "FinancialAssistantAgent",
        "description": "Autonomous agent authorized to manage transfers.",
        "model": "gpt-4o"
    }

    # Step 1: Send the registration request to the Agent Registry Service
    try:
        print(f"\nSending agent registration to: {REGISTRY_URL}...")
        response = requests.post(REGISTRY_URL, json=payload, timeout=5)
        
        if response.status_code != 200:
            print(f"Error registering agent: {response.status_code} - {response.text}")
            sys.exit(1)
            
        result = response.json()
        agent_id = result.get("agent_id")
        status = result.get("status")
        runtime_id = result.get("runtime_id")
        
        print("\n[SUCCESS] Registration received!")
        print(f"  Agent Name: {result.get('name')}")
        print(f"  Agent ID:   {agent_id}")
        print(f"  Status:     {status}")
        print(f"  Runtime ID: {runtime_id}")

    except requests.exceptions.RequestException as e:
        print(f"\n[ERROR] Connection failed: {str(e)}")
        print("Please verify that the Agent Registry Service is running on port 8000.")
        sys.exit(1)

    # Step 2: Poll status to verify agent is running
    status_url = f"{REGISTRY_URL}/{agent_id}"
    print(f"\nPolling agent status from: {status_url}...")
    
    for i in range(3):
        time.sleep(1)
        try:
            res = requests.get(status_url, timeout=2)
            if res.status_code == 200:
                details = res.json()
                print(f"  [Poll {i+1}] Status: {details.get('status')} | Runtime worker active: {details.get('runtime_id') is not None}")
                if details.get("status") == "running":
                    break
            else:
                print(f"  [Poll {i+1}] Received unexpected status code: {res.status_code}")
        except requests.exceptions.RequestException:
            print(f"  [Poll {i+1}] Connection error during poll.")

    print("\nProvisioning pipeline test completed.")

if __name__ == "__main__":
    main()
