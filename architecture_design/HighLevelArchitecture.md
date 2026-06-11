# AgentID Platform –  Architecture Proposal


AgentID protocol lifecycle:

1. Agent Creation
2. Runtime Provisioning
3. Attestations
4. Identity
5. Authorization (OAuth CIBA)
6. Policy Enforcement
7. Secure Action Execution
8. Audit Logging
9. Trust-Based Acceptance/Rejection

---

# High-Level Architecture (Microservices based)

```text
Deployer
    │
    ▼
User Portal
    │
    ▼                                            Attestation Service
                                                 (Manages attestations provided by the Deployer, Developer, and Provider.)
Provider Platform                           
├── Agent Registry
├── Agent Identity
├── Policy Service
├── Agent Runtime
    │
    ▼                                         Authorization Service
                                          (Handles auth flow between the Deployer, 
                                           Agent, and Service.)
Developer - External LLM Provider            
    │
    ▼
Target Service
(Bank)
    │
    ▼
Audit Service
```
---

# Project Structure (Just a high level view for understanding)

```text
agentid-platform/

├── frontend/
│   ├── deployer-portal
│   └── admin-console
│
├── services/
│   ├── agent-registry
│   ├── agent-identity
│   ├── attestation
│   ├── authorization
│   ├── policy
│   ├── agent-runtime
│   ├── audit
│   └── shared
│
├── infrastructure/
│   ├── kubernetes
│   ├── terraform
│   ├── monitoring
│   └── secrets
│
├── contracts/
│
└── docs/
```

---

# Microservices 

(I have these 7 main services in mind, can be refactored and all are not necessarily inside provider layer as given above)

## 1. Agent Registry Service

To maintain agent lifecycle and ownership. A source of truth for all agents

Responsibilities:

* Create agents
* Update agents
* Suspend agents
* Revoke agents
* Store metadata

---

## 2. Agent Identity Service

To generate and manage AgentIDs. Provides cryptographic identity and accountability.

Responsibilities:

* Issue AgentID credentials
* Build identity chain
* Sign credentials
* Verify credentials

---

## 3. Attestation Service

To verify, store, and assemble attestations originating from different actors such as the Deployer, Developer, and Provider.

Responsibilities:

* Verify attestations
* Signature validation
* Attestation chain verification

---

## 4. Authorization Service

To implement OAuth/OIDC/CIBA. Allows agents to act only after explicit user authorization.

Responsibilities:

* OAuth/CIBA flow handling
* Authorization state tracking
* OAuth token issuance

---

## 5. Policy Service

To evaluate guardrails and constraints. 

Responsibilities:

* OPA policy evaluation
* Risk checks
* Access decisions

---

## 6. Agent Runtime Service

To Execute agent workflows.

Responsibilities:

* Run agent instances
* LLM interactions
* Tool execution

---

## 7. Audit Service

Responsibilities:

* Action logging
* Policy logging
* Authorization logging
* Investigation

---

# Potential Tech Stack

## Frontend (same as already used in demo)

* Next.js
* React
* TypeScript

---

## Agent Runtime

* Python
* LangGraph
* OpenAI Agents SDK

Alternative: 

* Semantic Kernel, AutoGen (but langgraph is most widely used)


---

## Core Identity Services

* Python (V1): Best for quickly building the first version because it works naturally with AI frameworks.

Alternative:

* Go (Future Scale): Better for high-traffic production systems because it is faster, uses less memory, and handles security and authentication workloads more efficiently.

* Java Spring Boot

---

## Authorization

* Keycloak (Open-source, supports OAuth, OIDC, and CIBA.)

Alternative:

* Auth0
* Curity

---

## Policy Engine

* Open Policy Agent (OPA) - Its Industry-standard policy-as-code framework

Alternative:

* Cedar

---

## Database


* PostgreSQL

---

## Messaging

* Kafka (For it's Event-driven architecture)

Alternative:

* RabbitMQ

---

## Secrets & Keys

* HashiCorp Vault
* AWS KMS / Azure Key Vault

---

## Infrastructure


* Docker
* Kubernetes
* Terraform


---

# Request Flow

```text
Deployer → Create Agent

Provider → Provision Runtime

Developer → Provide Model Attestation

Provider → Provide Runtime Attestation

Provider → Assemble Agent ID

Agent → Request Authorization

Service ↔ Deployer (OAuth CIBA)

Service → Issue Token

Agent → Execute Action

Service → Audit Log

Service → Accept / Reject Request
```

