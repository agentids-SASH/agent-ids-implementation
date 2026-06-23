import uuid
import requests
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
    deployer_identifier: str
    deployer_accountability_id: str

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
    log_event("Provider", f"Agent Registry received registration request for agent: {request.name} (Model: {request.model})")

    # Create agent record with 'initializing' status
    agent_data = {
        "id": agent_id,
        "name": request.name,
        "description": request.description,
        "model": request.model,
        "deployer_identifier": None,
        "deployer_accountability_id": None,
        "status": "initializing",
        "runtime_id": None,
        "agent_id_jwt": None
    }
    database.save_agent(agent_id, agent_data)
    log_event("Provider", f"Agent {agent_id} saved to registry database with 'initializing' status.")

    try:
        payload = {
            "agent_id": agent_id,
            "model": request.model
        }
        log_event("Provider", f"Agent Registry asking Runtime Service at {RUNTIME_SERVICE_URL} to spin up agent...")
        response = requests.post(RUNTIME_SERVICE_URL, json=payload, timeout=5)
        
        if response.status_code == 200:
            runtime_info = response.json()
            # Update the agent status to 'idle'
            agent_data["status"] = "idle"
            agent_data["runtime_id"] = runtime_info.get("runtime_id")
            database.save_agent(agent_id, agent_data)
            log_event("Provider", f"Agent {agent_id} successfully provisioned on runtime (IDLE): {runtime_info.get('runtime_id')}")
        else:
            agent_data["status"] = "failed_to_provision"
            database.save_agent(agent_id, agent_data)
            log_event("Provider", f"Runtime service returned error {response.status_code}: {response.text}")
            raise HTTPException(status_code=502, detail="Failed to start agent in the runtime environment.")

    except requests.exceptions.RequestException as e:
        agent_data["status"] = "failed_to_provision"
        database.save_agent(agent_id, agent_data)
        log_event("Provider", f"Could not connect to Runtime Service: {str(e)}")
        raise HTTPException(status_code=503, detail="Agent Runtime Service is currently offline.")

    return {
        "agent_id": agent_id,
        "name": agent_data["name"],
        "status": agent_data["status"],
        "runtime_id": agent_data["runtime_id"]
    }

@app.post("/api/agents/{agent_id}/prompt")
def submit_prompt(agent_id: str, request: AgentPromptRequest):
    """
    Step 2: Receives prompt from Deployer, triggers key generation and composite JWT signature.
    """
    log_event("Provider", f"Agent Registry received operational prompt for agent ID: {agent_id}")
    
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
            "deployer_identifier": request.deployer_identifier,
            "deployer_accountability_id": request.deployer_accountability_id
        }
        log_event("Provider", f"Agent Registry forwarding prompt to Runtime Service: {runtime_url}")
        response = requests.post(runtime_url, json=payload, timeout=8)
        
        if response.status_code == 200:
            result = response.json()
            # 3. Update agent DB with deployer credentials and composite JWT
            agent_data["status"] = "prepared"
            agent_data["deployer_identifier"] = request.deployer_identifier
            agent_data["deployer_accountability_id"] = request.deployer_accountability_id
            agent_data["agent_id_jwt"] = result.get("agent_id_jwt")
            database.save_agent(agent_id, agent_data)
            
            log_event("Provider", f"Agent ID JWT successfully received and saved for agent: {agent_id}")
            return {
                "status": "prepared",
                "agent_id_jwt": agent_data["agent_id_jwt"]
            }
        else:
            log_event("Provider", f"Runtime prompt trigger returned error {response.status_code}: {response.text}")
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
