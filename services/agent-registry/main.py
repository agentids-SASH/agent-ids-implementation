import uuid
import requests
import jwt
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, Any

import database
from logger_utils import log_event

app = FastAPI(title="Agent ID Platform - Agent Registry")

from threading import Lock
logs_db = []
logs_lock = Lock()

class LogMessage(BaseModel):
    timestamp: float
    actor: str
    message: str

@app.post("/api/logs")
def add_log(log: LogMessage):
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
            "deployer_attestation": request.deployer_attestation
        }
        log_event("Provider", f"Agent Registry forwarding prompt. Sending HTTP POST to Runtime Service: {runtime_url}. Payload: deployer_prompt='{payload['deployer_prompt']}', receiving_service='{payload['receiving_service']}', deployer_attestation (JWT)='{payload['deployer_attestation'][:30]}...'")
        response = requests.post(runtime_url, json=payload, timeout=8)
        
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
