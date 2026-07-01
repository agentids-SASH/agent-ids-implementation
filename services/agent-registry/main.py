import uuid
import requests
import jwt
import os
import time
import base64
import hashlib
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, Any, Optional
from cryptography.hazmat.primitives.asymmetric import padding, ec
from cryptography.hazmat.primitives import serialization, hashes

import database
from logger_utils import log_event

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Agent ID Platform - Agent Registry")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from threading import Lock
logs_db = []
logs_lock = Lock()

class SimulatorState:
    def __init__(self):
        self.reset()
        
    def reset(self):
        self.current_step = 0
        self.agent_name = None
        self.description = None
        self.model = None
        self.agent_id = None
        self.agent_instance_identifier = None
        self.deployer_attestation = None
        self.developer_attestation = None
        self.provider_attestation = None
        self.agent_instance_binding = None
        self.jwe = None
        self.ciba_auth_req_id = None
        self.ciba_approved = False
        self.transfer_status = "none"
        self.transfer_response = None
        self.decrypted_accountability_id = None
        self.ephemeral_private_key_pem = None
        self.ephemeral_public_key_pem = None

sim_state = SimulatorState()

class SimulatorInitRequest(BaseModel):
    agent_name: str
    description: str
    model: str

def get_sim_state_payload():
    return {
        "current_step": sim_state.current_step,
        "agent_name": sim_state.agent_name,
        "description": sim_state.description,
        "model": sim_state.model,
        "agent_id": sim_state.agent_id,
        "agent_instance_identifier": sim_state.agent_instance_identifier,
        "deployer_attestation": sim_state.deployer_attestation,
        "developer_attestation": sim_state.developer_attestation,
        "provider_attestation": sim_state.provider_attestation,
        "agent_instance_binding": sim_state.agent_instance_binding,
        "jwe": sim_state.jwe,
        "ciba_auth_req_id": sim_state.ciba_auth_req_id,
        "ciba_approved": sim_state.ciba_approved,
        "transfer_status": sim_state.transfer_status,
        "transfer_response": sim_state.transfer_response,
        "decrypted_accountability_id": sim_state.decrypted_accountability_id,
    }

@app.post("/api/simulator/init")
def simulator_init(request: SimulatorInitRequest):
    # Reset bank CIBA database state (to clean up old approvals/tokens)
    try:
        requests.delete("http://127.0.0.1:8003/api/oauth/ciba", timeout=5)
    except Exception as e:
        print(f"Failed to reset Bank CIBA state: {str(e)}")
        
    # Reset logs database
    with logs_lock:
        logs_db.clear()
        
    sim_state.reset()
    sim_state.agent_name = request.agent_name
    sim_state.description = request.description
    sim_state.model = request.model
    sim_state.current_step = 0
    
    log_event("", "=== Agent ID Platform - Step-by-Step Simulator Initialized ===")
    
    # Run Step 0: Create Agent (Register agent metadata in Registry DB)
    log_event("", ">>> Starting Step 0: Create Agent <<<")
    log_event("", "Description: Deployer asks the provider to initialize an AI Agent instance backed by a third-party developer's foundation model.")
    
    log_event("Deployer", f"Sending HTTP POST request to Register agent: http://localhost:8000/api/agents. Payload: {{'name': '{sim_state.agent_name}', 'description': '{sim_state.description}', 'model': '{sim_state.model}'}}")
    
    agent_id = str(uuid.uuid4())
    agent_data = {
        "id": agent_id,
        "name": sim_state.agent_name,
        "description": sim_state.description,
        "model": sim_state.model,
        "deployer_identifier": None,
        "deployer_accountability_id": None,
        "status": "initializing",
        "agent_instance_identifier": None,
        "agent_id_jwt": None
    }
    database.save_agent(agent_id, agent_data)
    sim_state.agent_id = agent_id
    
    log_event("Deployer", f"Registry responded with HTTP 200 OK. Response: {{'status': 'success', 'agent_id': '{agent_id}', 'status': 'initializing'}}")
    log_event("Provider", f"Agent {agent_id} saved to registry database with status: initializing")
    
    return {"status": "success", "state": get_sim_state_payload()}

@app.get("/api/simulator/state")
def get_simulator_state():
    return get_sim_state_payload()

@app.post("/api/simulator/approve")
def simulator_approve_ciba():
    if not sim_state.ciba_auth_req_id:
        raise HTTPException(status_code=400, detail="No active CIBA request to approve.")
    try:
        approve_url = "http://127.0.0.1:8003/api/oauth/ciba/approve"
        payload = {"auth_req_id": sim_state.ciba_auth_req_id}
        log_event("Deployer", f"Sending HTTP POST to Bank approval endpoint: {approve_url}. Payload: {payload}")
        res = requests.post(approve_url, json=payload, timeout=5)
        if res.status_code == 200:
            sim_state.ciba_approved = True
            log_event("Bank", f"Bank responded with HTTP 200 OK. Response: {{'status': 'approved'}}")
            log_event("Deployer", "Consent successfully submitted. CIBA Request approved.")
            return {"status": "approved"}
        else:
            raise HTTPException(status_code=res.status_code, detail=f"Failed to approve CIBA request: {res.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error connecting to Bank Service: {str(e)}")

@app.post("/api/simulator/step/{step_num}")
def simulator_step(step_num: int):
    if step_num != sim_state.current_step + 1:
        raise HTTPException(status_code=400, detail=f"Invalid step transition. Expected step {sim_state.current_step + 1}, got {step_num}")
        
    step_details = {
        1: ("Start Agent Instance", "The Provider provisions a compute process to invoke tools and call external services."),
        2: ("Initial Prompt", "Deployer encrypts accountability ID using JWE and signs Deployer Attestation."),
        3: ("Call the Foundation Model", "Agent forwards natural language prompt and parent token hash to LLM Developer."),
        4: ("Developer returns safety attestation", "LLM Developer returns signed developer attestation JWT."),
        5: ("Prepare Agent to Act", "Compute Provider signs environment claims and Agent signs ephemeral key binding."),
        6: ("Agent asks the service for authorization", "Agent initiates OAuth 2.0 CIBA request with Bank Service."),
        7: ("Service asks for authorization from the deployer", "Bank registers CIBA request and prompts Deployer out-of-band."),
        8: ("Deployer confirms authorization to the service", "Deployer authenticates and approves scopes directly on Bank consent card."),
        9: ("OAuth Response to Agent", "Bank issues valid Bearer access token to polling Agent runtime worker."),
        10: ("Agent Performs Action", "Agent submits transfer transaction with Bearer token and nested Agent ID JWT."),
        11: ("Service Logging", "Auditor decrypts JWE ciphertext to log Deployer's accountability ID."),
        12: ("Action Outcome", "Bank returns transaction confirmation status back to the Agent.")
    }
    
    title, desc = step_details[step_num]
    log_event("", f">>> Starting Step {step_num}: {title} <<<")
    log_event("", f"Description: {desc}")
    
    try:
        if step_num == 1:
            # Step 1: Start Agent Instance
            payload = {"agent_id": sim_state.agent_id, "model": sim_state.model}
            log_event("Provider", f"Agent Runtime received request to spawn worker thread. Payload: {payload}")
            response = requests.post(RUNTIME_SERVICE_URL, json=payload, timeout=5)
            if response.status_code == 200:
                runtime_info = response.json()
                sim_state.agent_instance_identifier = runtime_info["agent_instance_identifier"]
                log_event("Provider", f"Runtime worker booted. Agent Instance ID={sim_state.agent_instance_identifier}")
                agent_data = database.get_agent(sim_state.agent_id)
                if agent_data:
                    agent_data["status"] = "idle"
                    agent_data["agent_instance_identifier"] = sim_state.agent_instance_identifier
                    database.save_agent(sim_state.agent_id, agent_data)
            else:
                raise HTTPException(status_code=500, detail="Failed to spawn runtime worker thread.")
                
        elif step_num == 2:
            # Step 2: Deployer Attestation, JWE & Prompt Submission
            log_event("Deployer", "Sending HTTP GET request to Audit Service: http://127.0.0.1:8004/api/audit/public-key")
            audit_res = requests.get("http://127.0.0.1:8004/api/audit/public-key", timeout=5)
            audit_res_payload = audit_res.json()
            audit_pub_pem = audit_res_payload["public_key_pem"]
            log_event("Deployer", f"Audit Service responded with HTTP 200 OK. Response Payload: public_key_pem='{audit_pub_pem[:40].replace(chr(10),'')}'...")
            
            log_event("Deployer", "Encrypting Deployer Accountability ID ('Jane Doe') client-side using JWE (RSA-OAEP with SHA-256 algorithm)...")
            audit_key = serialization.load_pem_public_key(audit_pub_pem.encode('utf-8'))
            
            accountability_id = "Jane Doe"
            ciphertext = audit_key.encrypt(
                accountability_id.encode('utf-8'),
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            jwe = base64.b64encode(ciphertext).decode('utf-8')
            sim_state.jwe = jwe
            log_event("Deployer", f"Generated JWE ciphertext using RSA-OAEP-256: {jwe[:30]}...")
            
            log_event("Deployer", "Loading or generating Deployer's local cryptographic private key...")
            with open("../../scripts/deployer_key.pem", "rb") as f:
                deployer_key = serialization.load_pem_private_key(f.read(), password=None)
            log_event("Deployer", "Loaded existing Deployer private key from scripts/deployer_key.pem.")
            
            dep_pub_pem = deployer_key.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            with open("../agent-identity/deployer_public_key.pem", "wb") as f:
                f.write(dep_pub_pem)
            log_event("Deployer", "Published Deployer public key to services/agent-identity/deployer_public_key.pem.")
                
            log_event("Deployer", "Constructing and signing Deployer Attestation JWT client-side...")
            dep_claims = {
                "iss": "deployer #101",
                "deployer_identifier": "deployer #101",
                "deployer_accountability_id": jwe,
                "iat": int(time.time())
            }
            dep_jwt = jwt.encode(dep_claims, deployer_key, algorithm="ES256")
            sim_state.deployer_attestation = dep_jwt
            log_event("Deployer", f"Signed Deployer Attestation JWT (ES256): {dep_jwt[:30]}...")
            
            # Submission of prompt to Provider Registry
            prompt_payload = {
                "deployer_prompt": "Transfer 1000 USD from my checking account to my savings account",
                "receiving_service": "bank.com",
                "deployer_identifier_on_service": "deployer's username on bank.com",
                "deployer_attestation": f"{sim_state.deployer_attestation[:30]}..."
            }
            log_event("Deployer", f"Sending HTTP POST request to Registry prompt endpoint: http://127.0.0.1:8000/api/agents/{sim_state.agent_id}/prompt. Payload: {prompt_payload}")
            log_event("Provider", f"Agent Registry received operational prompt for Agent ID: {sim_state.agent_id}. Input Payload: {prompt_payload}")
            
            agent_data = database.get_agent(sim_state.agent_id)
            if agent_data:
                agent_data["deployer_identifier"] = "deployer #101"
                agent_data["deployer_accountability_id"] = sim_state.jwe
                database.save_agent(sim_state.agent_id, agent_data)
            
        elif step_num == 3:
            # Step 3: Call the Foundation Model
            forward_payload = {
                "deployer_attestation": f"{sim_state.deployer_attestation[:30]}...",
                "prompt": "Transfer 1000 USD from my checking account to my savings account",
                "receiving_service": "bank.com",
                "deployer_identifier_on_service": "deployer's username on bank.com"
            }
            log_event("Provider", f"Agent Registry forwarding prompt. Sending HTTP POST to Runtime Service: http://127.0.0.1:8001/api/runtime/{sim_state.agent_id}/prompt. Payload: {forward_payload}")
            log_event("Provider", "Prompt received. Starting cryptographic identity composition...")
            
            dep_hash = hashlib.sha256(sim_state.deployer_attestation.encode('utf-8')).hexdigest()
            model_payload = {
                "prompt": "Transfer 1000 USD from checking to savings",
                "receiving_service": "bank.com",
                "request_attestation": True,
                "model": sim_state.model,
                "parent_token_hash": dep_hash
            }
            log_event("Provider", f"Calling LLM Developer model endpoint: http://127.0.0.1:8002/api/identity/call-model. Payload: {model_payload}")
            res = requests.post("http://127.0.0.1:8002/api/identity/call-model", json=model_payload, timeout=5)
            if res.status_code == 200:
                sim_state.developer_attestation = res.json().get("developer_attestation")
            else:
                raise HTTPException(status_code=500, detail="Failed to fetch Developer Attestation.")
                
        elif step_num == 4:
            # Step 4: Developer returns safety attestation
            log_event("Developer", f"LLM Developer responded with HTTP 200 OK. Response: {{'developer_attestation': '{sim_state.developer_attestation[:30]}...', 'foundation_model_identifier': 'Commercial {sim_state.model}_4.2'}}")
            log_event("Provider", f"Received safety attestation. Developer Attestation JWT (ES256): {sim_state.developer_attestation[:30]}...")
                
        elif step_num == 5:
            # Step 5: Compose Provider Attestation
            dev_hash = hashlib.sha256(sim_state.developer_attestation.encode('utf-8')).hexdigest()
            compose_payload = {
                "agent_id": sim_state.agent_id,
                "parent_token_hash": dev_hash
            }
            log_event("Provider", f"Requesting Provider signature to compile Provider Attestation JWT: http://127.0.0.1:8002/api/identity/compose. Payload: agent_id='{sim_state.agent_id}', parent_token_hash='{dev_hash}'")
            res = requests.post("http://127.0.0.1:8002/api/identity/compose", json=compose_payload, timeout=5)
            if res.status_code == 200:
                sim_state.provider_attestation = res.json().get("provider_attestation")
                log_event("Agent", f"Provider composition succeeded. Status Code: HTTP 200 OK. Received Provider Attestation JWT (len: {len(sim_state.provider_attestation)} bytes, algorithm: ES256)")
            else:
                raise HTTPException(status_code=500, detail="Failed to fetch Provider Attestation.")
            
            log_event("Provider", "Generating ephemeral key pair using SECP256R1 (P-256) Elliptic Curve...")
            private_key = ec.generate_private_key(ec.SECP256R1())
            private_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ).decode('utf-8')
            public_pem = private_key.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            ).decode('utf-8')
            
            sim_state.ephemeral_private_key_pem = private_pem
            sim_state.ephemeral_public_key_pem = public_pem
            
            truncated_pub_key = public_pem.replace('\n', '').replace('-----BEGIN PUBLIC KEY-----', '').replace('-----END PUBLIC KEY-----', '')[:40]
            log_event("Provider", f"Ephemeral EC Public Key generated: {truncated_pub_key}... Algorithm: ECDSA (SHA-256 binding ready)")
            
            prov_hash = hashlib.sha256(sim_state.provider_attestation.encode('utf-8')).hexdigest()
            
            spiffe_id = f"spiffe://provider.net/agent/worker-{sim_state.agent_id}"
            binding_payload = {
                "iss": spiffe_id,
                "sub": spiffe_id,
                "agent_instance_identifier": spiffe_id,
                "agent_public_key": public_pem,
                "parent_token_hash": prov_hash
            }
            binding_jwt = jwt.encode(binding_payload, private_key, algorithm="ES256")
            sim_state.agent_instance_binding = binding_jwt
            log_event("Agent", "Generated Agent Instance Binding JWT with parent_token_hash (Signed using ES256 with Agent ephemeral private key)")
            
            log_event("Agent", "Token Inspection - Decoded Peer-Level Agent ID claims:")
            
            # 1. Deployer Attestation
            dep_claims = jwt.decode(sim_state.deployer_attestation, options={"verify_signature": False})
            log_event("Agent", "  --- Deployer Attestation Claims ---")
            log_event("Agent", f"    iss (Issuer):               {dep_claims.get('iss')}")
            log_event("Agent", f"    deployer_identifier:        {dep_claims.get('deployer_identifier')}")
            log_event("Agent", f"    deployer_accountability_id (JWE): {dep_claims.get('deployer_accountability_id')[:30]}...")

            # 2. Developer Attestation
            dev_claims = jwt.decode(sim_state.developer_attestation, options={"verify_signature": False})
            log_event("Agent", "  --- Developer Attestation Claims ---")
            log_event("Agent", f"    iss (Issuer):               {dev_claims.get('iss')}")
            log_event("Agent", f"    developer_identifier:        {dev_claims.get('developer_identifier')}")
            log_event("Agent", f"    foundation_model_identifier: {dev_claims.get('foundation_model_identifier')}")
            log_event("Agent", f"    parent_token_hash:          {dev_claims.get('parent_token_hash')}")

            # 3. Provider Attestation
            prov_claims = jwt.decode(sim_state.provider_attestation, options={"verify_signature": False})
            log_event("Agent", "  --- Provider Attestation Claims ---")
            log_event("Agent", f"    iss (Issuer):               {prov_claims.get('iss')}")
            log_event("Agent", f"    provider_identifier:        {prov_claims.get('provider_identifier')}")
            log_event("Agent", f"    sub (Subject):             {prov_claims.get('sub')}")
            log_event("Agent", f"    agent_instance_identifier:  {prov_claims.get('agent_instance_identifier')}")
            log_event("Agent", f"    provider_security_evidence: {prov_claims.get('provider_security_evidence')}")
            log_event("Agent", f"    agent_instance_shutdown_command: {prov_claims.get('agent_instance_shutdown_command')}")
            log_event("Agent", f"    parent_token_hash:          {prov_claims.get('parent_token_hash')}")

            # 4. Agent Instance Binding
            bind_claims = jwt.decode(binding_jwt, options={"verify_signature": False})
            log_event("Agent", "  --- Agent Instance Binding Claims ---")
            log_event("Agent", f"    iss (Issuer):               {bind_claims.get('iss')}")
            log_event("Agent", f"    sub (Subject):             {bind_claims.get('sub')}")
            log_event("Agent", f"    agent_instance_identifier:  {bind_claims.get('agent_instance_identifier')}")
            log_event("Agent", f"    agent_public_key (truncated):     {bind_claims.get('agent_public_key')[:40].replace(chr(10),'')}...")
            log_event("Agent", f"    parent_token_hash:          {bind_claims.get('parent_token_hash')}")

            log_event("Agent", "Cryptographic Agent ID flat presentation successfully assembled.")
            
            agent_id_jwt = {
                "developer_attestation": sim_state.developer_attestation,
                "provider_attestation": sim_state.provider_attestation,
                "deployer_attestation": sim_state.deployer_attestation,
                "agent_instance_binding": sim_state.agent_instance_binding
            }
            agent_data = database.get_agent(sim_state.agent_id)
            if agent_data:
                agent_data["status"] = "prepared"
                agent_data["agent_id_jwt"] = agent_id_jwt
                database.save_agent(sim_state.agent_id, agent_data)
            
        elif step_num == 6:
            # Step 6: Agent asks the service for authorization
            ciba_payload = {
                "requested_scopes": ["transfer_funds"],
                "deployer_identifier_on_service": "deployer's username on bank.com"
            }
            log_event("Agent", f"Sending HTTP POST to Bank CIBA endpoint: http://127.0.0.1:8003/api/oauth/ciba. Payload: {ciba_payload}")
            res = requests.post("http://127.0.0.1:8003/api/oauth/ciba", json=ciba_payload, timeout=5)
            if res.status_code == 200:
                res_body = res.json()
                sim_state.ciba_auth_req_id = res_body.get("auth_req_id")
                log_event("Agent", f"Bank responded with HTTP 200 OK. Response: {res_body}")
                log_event("Agent", f"CIBA request registered. Received auth_req_id: {sim_state.ciba_auth_req_id}")
            else:
                raise HTTPException(status_code=500, detail="Failed to initialize CIBA request.")
                
        elif step_num == 7:
            # Step 7: Service asks for authorization from the deployer
            log_event("Bank", "Consent Request Alert: Transfer 1000 USD from checking to savings.")
            
        elif step_num == 8:
            # Step 8: Deployer confirms authorization to the service
            log_event("Deployer", "Waiting for Deployer approval input...")
            
        elif step_num == 9:
            # Step 9: OAuth Response to Agent
            if not sim_state.ciba_approved:
                raise HTTPException(status_code=400, detail="Please approve the CIBA consent request in the UI card before moving to step 9.")
            token_payload = {
                "grant_type": "urn:openid:params:grant-type:ciba",
                "auth_req_id": sim_state.ciba_auth_req_id
            }
            log_event("Agent", f"Sending HTTP POST to Bank Token endpoint: http://127.0.0.1:8003/api/oauth/token. Payload: {token_payload}")
            res = requests.post("http://127.0.0.1:8003/api/oauth/token", json=token_payload, timeout=5)
            if res.status_code == 200:
                sim_state.transfer_response = res.json()
                log_event("Agent", f"Bank responded with HTTP 200 OK. Response: {sim_state.transfer_response}")
                log_event("Agent", "OAuth access token successfully retrieved.")
            else:
                raise HTTPException(status_code=500, detail="OAuth token pending or rejected.")
                
        elif step_num == 10:
            # Step 10: Agent Performs Action
            access_token = sim_state.transfer_response.get("access_token")
            agent_id_jwt = {
                "developer_attestation": sim_state.developer_attestation,
                "provider_attestation": sim_state.provider_attestation,
                "deployer_attestation": sim_state.deployer_attestation,
                "agent_instance_binding": sim_state.agent_instance_binding
            }
            transfer_payload = {
                "amount": 1000.0,
                "from_account": "checking",
                "to_account": "savings",
                "agent_id_jwt": agent_id_jwt
            }
            headers = {"Authorization": f"Bearer {access_token}"}
            log_event("Agent", f"Sending HTTP POST to Bank Transfer endpoint: http://127.0.0.1:8003/api/bank/transfer.")
            log_event("Agent", f"Headers: {headers}")
            log_event("Agent", f"Payload: {{'amount': 1000.0, 'from_account': 'checking', 'to_account': 'savings', 'agent_id_jwt': <Nested 4 Attestations>}}")
            
            res = requests.post("http://127.0.0.1:8003/api/bank/transfer", json=transfer_payload, headers=headers, timeout=5)
            sim_state.transfer_status = "success" if res.status_code == 200 else "failed"
            sim_state.transfer_response = res.json()
            log_event("Agent", "Submitting transaction request execution to Bank Service...")
            
        elif step_num == 11:
            # Step 11: Service Logging
            decrypt_payload = {
                "ciphertext_base64": sim_state.jwe
            }
            headers = {"Authorization": "Bearer audit_secret_token"}
            log_event("Audit", f"Sending HTTP POST request to Auditor decryption endpoint: http://127.0.0.1:8004/api/audit/decrypt. Headers: {headers}. Payload: {{'ciphertext_base64': '{sim_state.jwe[:30]}...'}}")
            res = requests.post("http://127.0.0.1:8004/api/audit/decrypt", json=decrypt_payload, headers=headers, timeout=5)
            if res.status_code == 200:
                res_body = res.json()
                sim_state.decrypted_accountability_id = res_body.get("decrypted_value")
                log_event("Audit", f"Auditor responded with HTTP 200 OK. Response: {res_body}")
                log_event("Audit", f"Decrypted accountability ID: {sim_state.decrypted_accountability_id}")
            else:
                raise HTTPException(status_code=500, detail="Audit decryption failed.")
                
        elif step_num == 12:
            # Step 12: Action Outcome
            if sim_state.transfer_status == "success":
                log_event("Bank", f"Bank responded with HTTP 200 OK. Response: {sim_state.transfer_response}")
                log_event("Bank", "Bank Service approved and executed transaction.")
                log_event("Agent", "Action outcome: SUCCESS. Transaction completed.")
            else:
                log_event("Bank", f"Bank responded with HTTP {res.status_code}. Response: {sim_state.transfer_response}")
                log_event("Bank", f"Bank Service rejected transaction: {sim_state.transfer_response.get('detail')}")
                log_event("Agent", "Action outcome: ACTION_REJECTED. Transaction failed.")

        sim_state.current_step = step_num
        return {"status": "success", "state": get_sim_state_payload()}
        
    except Exception as e:
        log_event("Provider", f"Simulator Step {step_num} error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

from fastapi.responses import HTMLResponse

@app.get("/", response_class=HTMLResponse)
def get_simulator_ui():
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Simulator Frontend File Not Found</h1>"

class LogMessage(BaseModel):
    timestamp: float
    actor: str
    message: str

@app.post("/api/logs")
def add_log(log: LogMessage):
    if "Cleared CIBA requests and access tokens state" in log.message:
        return {"status": "ignored"}
    with logs_lock:
        logs_db.append({
            "timestamp": log.timestamp,
            "actor": log.actor,
            "message": log.message
        })
    return {"status": "ok"}

@app.get("/api/logs")
def get_logs():
    with logs_lock:
        # Sort logs by timestamp to guarantee sequential ordering
        sorted_logs = sorted(logs_db, key=lambda x: x["timestamp"])
    return sorted_logs

@app.delete("/api/logs")
def clear_logs():
    with logs_lock:
        logs_db.clear()
    return {"status": "cleared"}

# Define the target URL for the Agent Runtime service
RUNTIME_SERVICE_URL = "http://localhost:8001/api/runtime/start"

# Request schema for agent registration (Steps 0 & 1)
class AgentCreateRequest(BaseModel):
    name: str
    description: str
    model: str

# Request schema for prompt execution (Step 2)
class AgentPromptRequest(BaseModel):
    deployer_prompt: str
    receiving_service: str
    deployer_identifier_on_service: str
    deployer_attestation: str

@app.on_event("startup")
def on_startup():
    database.init_db()
    log_event("Provider", "Agent Registry Service started and database initialized.")

@app.post("/api/agents")
def register_agent(request: AgentCreateRequest):
    """
    Step 0 & 1: Registers a blank agent in the system and provisions an idle runtime worker.
    """
    agent_id = str(uuid.uuid4())
    log_event("Provider", f"Agent Registry received registration request. Input Payload: name='{request.name}', description='{request.description}', model='{request.model}'")

    # Create agent record with 'initializing' status
    agent_data = {
        "id": agent_id,
        "name": request.name,
        "description": request.description,
        "model": request.model,
        "deployer_identifier": None,
        "deployer_accountability_id": None,
        "status": "initializing",
        "agent_instance_identifier": None,
        "agent_id_jwt": None
    }
    database.save_agent(agent_id, agent_data)
    log_event("Provider", f"Agent {agent_id} saved to registry database with status: initializing")

    try:
        payload = {
            "agent_id": agent_id,
            "model": request.model
        }
        log_event("Provider", f"Agent Registry sending HTTP POST request to Runtime Service: {RUNTIME_SERVICE_URL}. Payload: {payload}")
        response = requests.post(RUNTIME_SERVICE_URL, json=payload, timeout=5)
        
        if response.status_code == 200:
            runtime_info = response.json()
            # Update the agent status to 'idle'
            agent_data["status"] = "idle"
            agent_data["agent_instance_identifier"] = runtime_info.get("agent_instance_identifier")
            database.save_agent(agent_id, agent_data)
            log_event("Provider", f"Runtime service responded with HTTP 200 OK. Response Body: {runtime_info}")
            log_event("Provider", f"Agent {agent_id} successfully provisioned on runtime (IDLE): {runtime_info.get('agent_instance_identifier')}")
        else:
            agent_data["status"] = "failed_to_provision"
            database.save_agent(agent_id, agent_data)
            log_event("Provider", f"Runtime service returned error HTTP {response.status_code}: {response.text}")
            raise HTTPException(status_code=502, detail="Failed to start agent in the runtime environment.")

    except requests.exceptions.RequestException as e:
        agent_data["status"] = "failed_to_provision"
        database.save_agent(agent_id, agent_data)
        log_event("Provider", f"Could not connect to Runtime Service (Error: {str(e)})")
        raise HTTPException(status_code=503, detail="Agent Runtime Service is currently offline.")

    response_payload = {
        "agent_id": agent_id,
        "name": agent_data["name"],
        "status": agent_data["status"],
        "agent_instance_identifier": agent_data["agent_instance_identifier"]
    }
    log_event("Provider", f"Agent Registry returning HTTP 200 OK. Response Payload: {response_payload}")
    return response_payload

@app.post("/api/agents/{agent_id}/prompt")
def submit_prompt(agent_id: str, request: AgentPromptRequest):
    """
    Step 2: Receives prompt from Deployer, triggers key generation and composite flat Agent ID construction.
    """
    log_event("Provider", f"Agent Registry received operational prompt for Agent ID: {agent_id}. Input Payload: deployer_prompt='{request.deployer_prompt}', receiving_service='{request.receiving_service}', deployer_attestation (JWT)='{request.deployer_attestation[:30]}...'")
    
    # 1. Verify agent exists in registry
    agent_data = database.get_agent(agent_id)
    if not agent_data:
        raise HTTPException(status_code=404, detail="Agent not found in registry.")

    # 2. Forward request to Runtime Service to trigger handshake
    try:
        runtime_url = f"http://localhost:8001/api/runtime/{agent_id}/prompt"
        payload = {
            "deployer_prompt": request.deployer_prompt,
            "receiving_service": request.receiving_service,
            "deployer_identifier_on_service": request.deployer_identifier_on_service,
            "deployer_attestation": request.deployer_attestation
        }
        log_event("Provider", f"Agent Registry forwarding prompt. Sending HTTP POST to Runtime Service: {runtime_url}. Payload: deployer_prompt='{payload['deployer_prompt']}', receiving_service='{payload['receiving_service']}', deployer_identifier_on_service='{payload['deployer_identifier_on_service']}', deployer_attestation (JWT)='{payload['deployer_attestation'][:30]}...'")
        response = requests.post(runtime_url, json=payload, timeout=120)
        
        if response.status_code == 200:
            result = response.json()
            
            # Decode deployer_attestation to extract properties for legacy DB fields
            try:
                dep_claims = jwt.decode(request.deployer_attestation, options={"verify_signature": False})
                deployer_id = dep_claims.get("deployer_identifier")
                accountability_id = dep_claims.get("deployer_accountability_id")
            except Exception as e:
                log_event("Provider", f"[WARNING] Failed to decode deployer_attestation claims: {str(e)}")
                deployer_id = "Unknown"
                accountability_id = "Unknown"

            # 3. Update agent DB with deployer credentials and flat Agent ID presentation
            agent_data["status"] = "prepared"
            agent_data["deployer_identifier"] = deployer_id
            agent_data["deployer_accountability_id"] = accountability_id
            agent_data["agent_id_jwt"] = result.get("agent_id_jwt")
            database.save_agent(agent_id, agent_data)
            
            log_event("Provider", f"Runtime service responded with HTTP 200 OK. Received flat Agent ID presentation container.")
            log_event("Provider", f"Agent ID presentation successfully saved in database for agent: {agent_id}")
            
            response_payload = {
                "status": "prepared",
                "agent_id_jwt": agent_data["agent_id_jwt"]
            }
            log_event("Provider", f"Agent Registry returning HTTP 200 OK. Response Payload: status='prepared', agent_id_jwt (flat JSON presentation container)")
            return response_payload
        else:
            log_event("Provider", f"Runtime prompt trigger returned error HTTP {response.status_code}: {response.text}")
            raise HTTPException(status_code=response.status_code, detail="Failed to initialize cryptographic identity.")
            
    except requests.exceptions.RequestException as e:
        log_event("Provider", f"Error connecting to Runtime Service: {str(e)}")
        raise HTTPException(status_code=503, detail="Agent Runtime Service is currently offline.")

@app.get("/api/agents")
def list_agents():
    """Lists all registered agents in the database."""
    return database.get_all_agents()

@app.get("/api/agents/{agent_id}")
def get_agent_details(agent_id: str):
    """Retrieves the details and current status of a specific agent."""
    agent = database.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found in registry.")
    return agent
