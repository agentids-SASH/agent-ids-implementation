# SASH Agent ID Protocol Implementation

This repository contains the reference implementation and step-by-step protocol simulator for the **SASH Agent ID** specification. This protocol solves the challenge of AI Agent user accountability and workload authorization by establishing a chain-of-trust linking the **Deployer**, the **LLM Developer**, the **Compute Provider**, and the **Agent's Ephemeral Key**. 

This project is a local reference implementation of the interactive flow shown in the [SASH Agent ID Technical Demo](https://agentids-sash.github.io/agentids-technical-demo/).

---

## 1. Architectural Overview

The platform is split into **five independent microservices** cooperating to perform secure, cryptographically validated actions (such as financial bank transfers) on behalf of users:

```
                                  [ Central Registry ] (Port 8000)
                                           |
                    +----------------------+----------------------+
                    |                      |                      |
            [ Agent Runtime ]     [ Agent Identity ]       [ Audit Service ]
               (Port 8001)           (Port 8002)              (Port 8004)
                    |                      |                      |
                    +----------------------+----------------------+
                                           |
                                    [ Bank Service ] (Port 8003)
```

1.  **Agent Registry (Port 8000):** Holds the registry catalog of all provisioned agents (`agents_db.json`), receives prompt submissions, and acts as the central logs aggregator. It also hosts the simulator's web UI.
2.  **Agent Runtime (Port 8001):** Manages the active agent compute process, executes background worker threads, manages the ephemeral SECP256R1 EC key pair, and runs the backchannel CIBA authorization loop.
3.  **Agent Identity Service (Port 8002):** Simulates model-provider safety verifications (LLM Developer signature for Developer Attestation JWS) and compute-provider environment claims compilation (Compute Provider signature for Provider Attestation JWS).
4.  **Bank Service (Port 8003):** The Relying Party (target application). It manages OAuth 2.0 CIBA request registrations, renders the user consent approval UI, issues access tokens, and verifies the full cryptographic Agent ID attestation chain before approving transfers.
5.  **Audit Service (Port 8004):** Acts as the compliance auditor. It hosts the RSA keys used to construct client-side JWE accountability payloads and decrypts transaction logs to identify the responsible user.

---

## 2. The 13-Step Protocol Lifecycle

The platform implements the 13 steps of the official protocol lifecycle as demonstrated in the [SASH Agent ID Technical Demo](https://agentids-sash.github.io/agentids-technical-demo/):

*   **Step 0: Create Agent:** Deployer requests the Provider to register the agent name, description, and LLM model parameters in the registry database.
*   **Step 1: Start Agent Instance:** Provider provisions the compute process (harness) and boots up the active worker thread.
*   **Step 2: Initial Prompt:** Deployer client-side encrypts the accountability identifier ("Jane Doe") using JWE and signs the Deployer Attestation JWS, before submitting the instruction to the Provider.
*   **Step 3: Call the Foundation Model:** Provider forwards the instruction to the LLM Developer model call endpoint.
*   **Step 4: Developer returns safety attestation:** LLM Developer returns a signed safety attestation JWT linked to the Deployer Attestation.
*   **Step 5: Prepare Agent to Act:** Compute Provider signs environment claims (Provider Attestation), and the Agent signs its ephemeral public key binding (Agent Instance Binding). The flat cryptographic Agent ID presentation is compiled.
*   **Step 6: Agent asks service for authorization:** Agent runtime worker initiates an OAuth 2.0 CIBA request with the Bank.
*   **Step 7: Service asks for authorization from deployer:** Bank registers the request and raises an out-of-band user consent alert.
*   **Step 8: Deployer confirms authorization:** Deployer reviews transaction details and signs the consent approval on the Bank's consent card.
*   **Step 9: OAuth Response to Agent:** Bank issues a valid Bearer access token to the polling Agent runtime.
*   **Step 10: Agent Performs Action:** Agent submits the bank transfer request, attaching the access token and the nested Agent ID JWS container.
*   **Step 11: Service Logging:** Bank validates the attestation signatures, chains, and IDs, then requests the Auditor to decrypt the JWE ciphertext to log the Deployer's accountability ID.
*   **Step 12: Action Outcome:** Bank returns the successful transaction response to the Agent.

---

## 3. Environment Setup

### Prerequisites
*   Python 3.8 or higher
*   Windows / Linux / macOS

### Installation
1. Clone the repository and navigate into the implementation directory:
   ```bash
   cd agent-ids-implementation
   ```

2. Create a virtual environment and activate it:
   ```bash
   # Windows (PowerShell)
   python -m venv .venv
   .venv\Scripts\activate

   # Linux/macOS
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

---

## 4. Running the Microservices

You need to run all 5 microservices concurrently. Open 5 separate terminals (ensure the virtual environment is activated in each) and run the corresponding commands:

```bash
# Terminal 1: Agent Registry (Port 8000)
cd services/agent-registry
python -m uvicorn main:app --host 127.0.0.1 --port 8000

# Terminal 2: Agent Runtime (Port 8001)
cd services/agent-runtime
python -m uvicorn main:app --host 127.0.0.1 --port 8001

# Terminal 3: Agent Identity (Port 8002)
cd services/agent-identity
python -m uvicorn main:app --host 127.0.0.1 --port 8002

# Terminal 4: Bank Service (Port 8003)
cd services/bank-service
python -m uvicorn main:app --host 127.0.0.1 --port 8003

# Terminal 5: Audit Service (Port 8004)
cd services/audit-service
python -m uvicorn main:app --host 127.0.0.1 --port 8004
```

---

## 5. Usage Guides

### Option A: The Step-by-Step Web Simulator (UI)
1. Open your web browser and navigate to: `http://127.0.0.1:8000/`
2. Enter your custom **Agent Name** and **Description**, choose the **LLM Model**, and click **Initialize**.
3. Use the **Next Step** button (or press `Enter`) to step through the protocol.
4. When you reach **Step 8**, the simulator will halt, displaying the **Bank Consent Card**. Click **Approve Consent** to confirm Deployer approval.
5. Step through the remaining steps to verify compliance decryption (Step 11) and view the final transfer outcome.

### Option B: The Automated Command-Line Client (CLI)
To run the entire handshake and transfer execution autonomously as a script, execute:
```bash
python scripts/deploy_agent.py
```
This script will programmatically run the exact sequence, print payload traces, approve the bank consent card, execute the transfer, and verify the auditor log results directly in your terminal.
