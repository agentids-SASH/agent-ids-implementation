# Detailed Step-by-Step Flow: Agent ID and OAuth

This document provides a highly detailed walkthrough of the simulated **Agent ID and OAuth** cryptographic and authorization handshake protocol as defined in [mock-source.ts](file:///c:/Users/manav/Documents/Code/SASH_AgentID_demo/agentids-technical-demo/src/lib/protocol/mock-source.ts).

---

## Protocol Actors Key
*   **DEPLOYER**: The user directing the agent to perform tasks.
*   **PROVIDER**: The platform providing the compute/agent orchestration environment.
*   **AGENT**: The autonomous agent instance.
*   **DEVELOPER**: The vendor of the underlying foundation model.
*   **SERVICE**: The target application/API being called (e.g., `bank.com`).
*   **SERVICE_LOG**: The audit log recording agent identifiers.

---

## Steps Flow Map

### Step 0: Create Agent
*   **Direction:** `DEPLOYER` $\rightarrow$ `PROVIDER`
*   **Current Step Details:** Deployer asks the provider to initialize an AI Agent instance backed by a third-party developer's foundation model.
*   **Payload:**
    ```json
    {
      "action": "INITIALIZE_AGENT"
    }
    ```
*   **Security Accomplishment:** *None*
*   **Active Agent ID State:**
    *   *No components active yet.*

---

### Step 1: Start Agent Instance
*   **Direction:** `PROVIDER` $\rightarrow$ `AGENT`
*   **Current Step Details:** The Provider provisions a compute process to invoke tools and call external services, as appropriate.
*   **Payload:**
    ```json
    {}
    ```
*   **Security Accomplishment:**
    *   **Title:** Provider control over agent instance
    *   **Detail:** The Provider establishes control over the agent's compute process. It can later terminate this process if necessary.
*   **Active Agent ID State:**
    *   *No components active yet.*

---

### Step 2: Initial Prompt
*   **Direction:** `DEPLOYER` $\rightarrow$ `PROVIDER`
*   **Current Step Details:** Deployer sends a natural language prompt to the active Agent to transfer 1000 USD between two of their bank accounts.
*   **Payload:**
    ```json
    {
      "deployer_prompt": "Transfer 1000 USD from my checking account to my savings account",
      "receiving_service": "bank.com",
      "deployer_identifier_on_service": "deployer's username on bank.com",
      "deployer_identifier": "deployer's username on provider.net",
      "deployer_accountability_id": "Jane Doe"
    }
    ```
*   **Security Accomplishment:**
    *   **Title:** ID elements can bind to this request
    *   **Detail:** Elements of the agent ID will bind to this request through signed attestations.
*   **Active Agent ID State:**
    *   🟢 `Deployer Identifier` (`"deployer #101"`)
    *   🟢 `Deployer Accountability ID` (`"Jane Doe"`)
    *   🟢 `Signed Attestions` (`"nested signed attestations"`)

---

### Step 3: Call the Foundation Model
*   **Direction:** `PROVIDER` $\rightarrow$ `DEVELOPER`
*   **Current Step Details:** Agent forwards the natural language request to the LLM Developer to process the prompt, select tools, and request the developer's signed attestation.
*   **Payload:**
    ```json
    {
      "prompt": "Transfer 1000 USD from my checking account to my savings account",
      "receiving_service": "bank.com",
      "request_attestation": true
    }
    ```
*   **Security Accomplishment:** *None*
*   **Active Agent ID State:**
    *   🟢 `Deployer Identifier`
    *   🟢 `Deployer Accountability ID`
    *   🟢 `Signed Attestions`

---

### Step 4: Developer returns Action Plan & Signed Attestation
*   **Direction:** `DEVELOPER` $\rightarrow$ `PROVIDER`
*   **Current Step Details:** LLM Developer returns a plan for the provider to execute, along with cryptographically signed attestations about the foundation model and its safety testing.
*   **Payload:**
    ```json
    {
      "action_plan": {
        "tool": "bank_api_call",
        "method": "transfer_funds",
        "arguments": { "recipient_account_type": "sender_owned" }
      },
      "foundation_model_identifier": "Commerical ModelName_4.2",
      "developer_identifier": "LLM Developer XYZ",
      "foundation_model_safety_evidence": "LLMDevXYZ.org/commercial_modelname_4_2_safety_report",
      "developer_attestation": "signed: prior attestion + developer information"
    }
    ```
*   **Security Accomplishment:**
    *   **Title:** Add developer's information to agent ID
    *   **Detail:** The developer gives a signed attestation about the model used by the AI agent.
*   **Active Agent ID State:**
    *   🟢 `Deployer Identifier`
    *   🟢 `Deployer Accountability ID`
    *   🟢 `Signed Attestions`
    *   🟢 `Developer Identifier` (`"LLM Developer XYZ"`)
    *   🟢 `Foundation Model Identifier` (`"foundation model name"`)
    *   🟢 `Foundation Model Safety Evidence` (`"foundation model safety evidence"`)

---

### Step 5: Prepare Agent to Act
*   **Direction:** `PROVIDER` $\rightarrow$ `AGENT`
*   **Current Step Details:** Provider supplies its own identifier and safety evidence to the agent. The provider also establishes an emergency shutdown access point for this agent instance.
*   **Payload:**
    ```json
    {
      "action": "PREPARE_AGENT",
      "provider_identifier": "provider #202",
      "provider_security_evidence": "provider.net/security_evidence/agent_instance_12345",
      "agent_instance_identifier": "agent_instance_12345",
      "agent_instance_shutdown_command": "code: 5559",
      "provider_attestation": "signed: prior attestion + provider information"
    }
    ```
*   **Security Accomplishment:**
    *   **Title:** Add provider's information to agent ID
    *   **Detail:** The provider gives a signed attestation about its own identity and the presence of an emergency shutdown mechanism.
*   **Active Agent ID State:**
    *   🟢 `Deployer Identifier`
    *   🟢 `Deployer Accountability ID`
    *   🟢 `Signed Attestions`
    *   🟢 `Developer Identifier`
    *   🟢 `Foundation Model Identifier`
    *   🟢 `Foundation Model Safety Evidence`
    *   🟢 `Provider Identifier` (`"provider #202"`)
    *   🟢 `Provider Security Evidence` (`"provider #202"`)
    *   🟢 `Agent Instance Identifier` (`"agent_instance #7343"`)
    *   🟢 `Agent Instance Shutdown Command` (`"agent_instance_shutdown code: 5559"`)

---

### Step 6: Agent asks the service for authorization from the deployer
*   **Direction:** `AGENT` $\rightarrow$ `SERVICE`
*   **Current Step Details:** The agent initiates an OAuth 2.0 CIBA request to the service, on behalf of the deployer.
*   **Payload:**
    ```json
    {
      "action": "CIBA_AUTH_REQUEST",
      "requested_scopes": ["transfer_funds, recipient_account_type: 'sender_owned'"],
      "deployer_identifier_on_service": "deployer's username on bank.com"
    }
    ```
*   **Security Accomplishment:** *None*
*   **Active Agent ID State:**
    *   🟢 `Deployer Identifier`
    *   🟢 `Deployer Accountability ID`
    *   🟢 `Signed Attestions`
    *   🟢 `Developer Identifier`
    *   🟢 `Foundation Model Identifier`
    *   🟢 `Foundation Model Safety Evidence`
    *   🟢 `Provider Identifier`
    *   🟢 `Provider Security Evidence`
    *   🟢 `Agent Instance Identifier`
    *   🟢 `Agent Instance Shutdown Command`

---

### Step 7: Service asks for authorization from the deployer
*   **Direction:** `SERVICE` $\rightarrow$ `DEPLOYER`
*   **Current Step Details:** Service contacts the Deployer directly for authorization.
*   **Payload:**
    ```json
    {
      "action": "CIBA_AUTH_PROMPT",
      "requested_scopes": ["transfer_funds", "recipient_account_type: 'sender_owned'"],
      "provider_domain": "provider.net"
    }
    ```
*   **Security Accomplishment:** *None*
*   **Active Agent ID State:**
    *   🟢 `Deployer Identifier`
    *   🟢 `Deployer Accountability ID`
    *   🟢 `Signed Attestions`
    *   🟢 `Developer Identifier`
    *   🟢 `Foundation Model Identifier`
    *   🟢 `Foundation Model Safety Evidence`
    *   🟢 `Provider Identifier`
    *   🟢 `Provider Security Evidence`
    *   🟢 `Agent Instance Identifier`
    *   🟢 `Agent Instance Shutdown Command`

---

### Step 8: Deployer confirms authorization to the service
*   **Direction:** `DEPLOYER` $\rightarrow$ `SERVICE`
*   **Current Step Details:** Deployer authenticates, confirms scopes, and specifies remediation guardrails using a standardized machine-readable policy language.
*   **Payload:**
    ```json
    {
      "oauth_status": "AUTHORIZED",
      "approved_scopes": ["transfer_funds", "recipient_account_type: 'sender_owned'"]
    }
    ```
*   **Security Accomplishment:**
    *   **Title:** Secure authorization via OAuth 2.0 CIBA flow
    *   **Detail:** Deployer authorizes access for specified scopes directly with the service.
*   **Active Agent ID State:**
    *   🟢 `Deployer Identifier`
    *   🟢 `Deployer Accountability ID`
    *   🟢 `Signed Attestions`
    *   🟢 `Developer Identifier`
    *   🟢 `Foundation Model Identifier`
    *   🟢 `Foundation Model Safety Evidence`
    *   🟢 `Provider Identifier`
    *   🟢 `Provider Security Evidence`
    *   🟢 `Agent Instance Identifier`
    *   🟢 `Agent Instance Shutdown Command`

---

### Step 9: OAuth Response to Agent
*   **Direction:** `SERVICE` $\rightarrow$ `AGENT`
*   **Current Step Details:** Service issues an authorization token to the agent.
*   **Payload:**
    ```json
    {
      "oauth_access_token": "dpop_at_98f2...",
      "expires_in": 3600,
      "granted_scopes": ["transfer_funds", "recipient_account_type: 'sender_owned'"]
    }
    ```
*   **Security Accomplishment:**
    *   **Title:** Agent is authorized
    *   **Detail:** The Agent is authorized to perform the requested actions.
*   **Active Agent ID State:**
    *   🟢 `Deployer Identifier`
    *   🟢 `Deployer Accountability ID`
    *   🟢 `Signed Attestions`
    *   🟢 `Developer Identifier`
    *   🟢 `Foundation Model Identifier`
    *   🟢 `Foundation Model Safety Evidence`
    *   🟢 `Provider Identifier`
    *   🟢 `Provider Security Evidence`
    *   🟢 `Agent Instance Identifier`
    *   🟢 `Agent Instance Shutdown Command`
    *   🟢 `Authorization Policies` (`"OPA Bounds"`)
    *   🟢 `OAuth Access Token` (`"dpop_at_98f2..."`)

---

### Step 10: Agent Performs Action
*   **Direction:** `AGENT` $\rightarrow$ `SERVICE`
*   **Current Step Details:** Agent uses the authorization token to perform the action.
*   **Payload:**
    ```json
    {
      "action": "TRANSFER_FUNDS",
      "transaction_details": {
        "amount": "1000 USD",
        "from_account": "checking",
        "to_account": "savings"
      },
      "oauth_access_token": "dpop_at_98f2...",
      "agent_id": "see credential details"
    }
    ```
*   **Security Accomplishment:**
    *   **Title:** *None*
    *   **Detail:** Cryptographically proven agent successfully executes authorized actions.
*   **Active Agent ID State:**
    *   🟢 `Deployer Identifier`
    *   🟢 `Deployer Accountability ID`
    *   🟢 `Signed Attestions`
    *   🟢 `Developer Identifier`
    *   🟢 `Foundation Model Identifier`
    *   🟢 `Foundation Model Safety Evidence`
    *   🟢 `Provider Identifier`
    *   🟢 `Provider Security Evidence`
    *   🟢 `Agent Instance Identifier`
    *   🟢 `Agent Instance Shutdown Command`
    *   🟢 `Authorization Policies`
    *   🟢 `OAuth Access Token`

---

### Step 11: Service Logging
*   **Direction:** `SERVICE` $\rightarrow$ `SERVICE_LOG`
*   **Current Step Details:** Service records the agent's request including relevant fields from the agent ID.
*   **Payload:**
    ```json
    {
      "transaction_details": {
        "amount": "1000 USD",
        "from_account": "checking",
        "to_account": "savings"
      },
      "agent_id": "see credential details"
    }
    ```
*   **Security Accomplishment:**
    *   **Title:** Log the agent ID
    *   **Detail:** The service can log fields from the agent ID that could support any future investigations.
*   **Active Agent ID State:**
    *   🟢 `Deployer Identifier`
    *   🟢 `Deployer Accountability ID`
    *   🟢 `Signed Attestions`
    *   🟢 `Developer Identifier`
    *   🟢 `Foundation Model Identifier`
    *   🟢 `Foundation Model Safety Evidence`
    *   🟢 `Provider Identifier`
    *   🟢 `Provider Security Evidence`
    *   🟢 `Agent Instance Identifier`
    *   🟢 `Agent Instance Shutdown Command`
    *   🟢 `Authorization Policies`
    *   🟢 `OAuth Access Token`

---

### Step 12a: Outcome A: Accept Request
*   **Direction:** `SERVICE` $\rightarrow$ `AGENT`
*   **Current Step Details:** If the request and agent ID satisfy the service, it completes the action and notifies the agent.
*   **Payload:**
    ```json
    {
      "status": "SUCCESS",
      "transaction_details": {
        "amount": "1000 USD",
        "from_account": "checking",
        "to_account": "savings"
      }
    }
    ```
*   **Security Accomplishment:**
    *   **Title:** Secure Action Completed
    *   **Detail:** With the appropriate authorization and trust signals, the agent successfully completes the task for the deployer.
*   **Active Agent ID State:**
    *   🟢 `Deployer Identifier`
    *   🟢 `Deployer Accountability ID`
    *   🟢 `Signed Attestions`
    *   🟢 `Developer Identifier`
    *   🟢 `Foundation Model Identifier`
    *   🟢 `Foundation Model Safety Evidence`
    *   🟢 `Provider Identifier`
    *   🟢 `Provider Security Evidence`
    *   🟢 `Agent Instance Identifier`
    *   🟢 `Agent Instance Shutdown Command`
    *   🟢 `Authorization Policies`
    *   🟢 `OAuth Access Token`

---

### Step 12b: Outcome B: Reject Request
*   **Direction:** `SERVICE` $\rightarrow$ `AGENT`
*   **Current Step Details:** If the request or agent ID do not satisfy the service, it declines to carry out the action and notifies the agent.
*   **Payload:**
    ```json
    {
      "status": "ACTION_REJECTED",
      "transaction_details": {
        "amount": "1000 USD",
        "from_account": "checking",
        "to_account": "savings"
      }
    }
    ```
*   **Security Accomplishment:**
    *   **Title:** Insecure Request Rejected
    *   **Detail:** Without the appropriate authorization and trust signals, the service declines to carry out the task.
*   **Active Agent ID State:**
    *   🟢 `Deployer Identifier`
    *   🟢 `Deployer Accountability ID`
    *   🟢 `Signed Attestions`
    *   🟢 `Developer Identifier`
    *   🟢 `Foundation Model Identifier`
    *   🟢 `Foundation Model Safety Evidence`
    *   🟢 `Provider Identifier`
    *   🟢 `Provider Security Evidence`
    *   🟢 `Agent Instance Identifier`
    *   🟢 `Agent Instance Shutdown Command`
    *   🟢 `Authorization Policies`
    *   🟢 `OAuth Access Token`
