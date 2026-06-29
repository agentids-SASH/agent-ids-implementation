import uuid
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict

from agent_worker import AgentWorker
from logger_utils import log_event

app = FastAPI(title="Agent ID Platform - Agent Runtime Service")

# Registry of active worker threads mapping agent_id -> AgentWorker instance
active_workers: Dict[str, AgentWorker] = {}

import time

class RuntimeStartRequest(BaseModel):
    agent_id: str
    model: str

class RuntimePromptRequest(BaseModel):
    deployer_prompt: str
    receiving_service: str
    deployer_identifier_on_service: str
    deployer_attestation: str

class RuntimeStopRequest(BaseModel):
    agent_id: str

@app.on_event("startup")
def on_startup():
    log_event("Provider", "Agent Runtime Service started on port 8001.")

@app.post("/api/runtime/start")
def start_runtime(request: RuntimeStartRequest):
    """
    Step 1: Spawns a new background execution thread simulating the AI Agent compute process.
    Does not perform key generation or identity binding yet.
    """
    log_event("Provider", f"Agent Runtime received request to spawn worker thread. Input Payload: agent_id='{request.agent_id}', model='{request.model}'")
    
    if request.agent_id in active_workers:
        log_event("Provider", f"Agent {request.agent_id} is already running. Returning status: already_running")
        return {"agent_instance_identifier": f"worker-{request.agent_id}", "status": "already_running"}

    try:
        # Create and start the worker thread in an idle, unsigned state
        worker = AgentWorker(agent_id=request.agent_id, model=request.model)
        worker.start()
        
        # Save to active workers registry
        active_workers[request.agent_id] = worker
        agent_instance_identifier = f"spiffe://provider.net/agent/worker-{request.agent_id}"
        
        log_event("Provider", f"Worker thread {agent_instance_identifier} successfully created and running.")
        response_payload = {
            "agent_instance_identifier": agent_instance_identifier,
            "status": "running"
        }
        log_event("Provider", f"Agent Runtime returning HTTP 200 OK. Response Payload: {response_payload}")
        return response_payload
    except Exception as e:
        log_event("Provider", f"Failed to spawn thread for Agent {request.agent_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error spinning up worker.")

@app.post("/api/runtime/{agent_id}/prompt")
def receive_prompt(agent_id: str, request: RuntimePromptRequest):
    """
    Step 2: Receives an operational prompt. Triggers key generation and fetches the composite Agent ID.
    """
    log_event("Provider", f"Agent Runtime received prompt request for Agent {agent_id}. Input Payload: deployer_prompt='{request.deployer_prompt}', receiving_service='{request.receiving_service}', deployer_identifier_on_service='{request.deployer_identifier_on_service}', deployer_attestation (JWT)='{request.deployer_attestation[:30]}...'")
    
    worker = active_workers.get(agent_id)
    if not worker:
        raise HTTPException(status_code=404, detail="Agent worker thread not found.")

    # Trigger the cryptographic handshake inside the worker thread
    success = worker.initialize_cryptographic_identity(
        deployer_attestation=request.deployer_attestation,
        prompt=request.deployer_prompt,
        receiving_service=request.receiving_service,
        deployer_identifier_on_service=request.deployer_identifier_on_service
    )

    if not success or worker.agent_id_jwt is None:
        log_event("Provider", f"Agent Runtime cryptographic composition failed inside worker thread for Agent {agent_id}.")
        raise HTTPException(status_code=500, detail="Failed to compose cryptographic Agent ID JWT.")

    response_payload = {
        "status": "prepared",
        "agent_id_jwt": worker.agent_id_jwt
    }
    log_event("Provider", f"Agent Runtime returning HTTP 200 OK. Response Payload: status='prepared', agent_id_jwt (flat JSON container containing 4 tokens)")
    return response_payload

@app.post("/api/runtime/stop")
def stop_runtime(request: RuntimeStopRequest):
    """
    Stops a running worker thread. This simulates an emergency shutdown scenario.
    """
    log_event("Provider", f"Agent Runtime received request to terminate worker thread for Agent: {request.agent_id}")
    
    worker = active_workers.get(request.agent_id)
    if not worker:
        log_event("Provider", f"No active worker found for Agent: {request.agent_id}")
        raise HTTPException(status_code=404, detail="No active worker thread found for this Agent ID.")

    try:
        # Signal the thread to stop and remove from registry
        worker.stop()
        worker.join(timeout=3)  # Wait up to 3 seconds for graceful exit
        del active_workers[request.agent_id]
        
        log_event("Provider", f"Worker thread for Agent {request.agent_id} stopped successfully.")
        return {"status": "stopped", "agent_id": request.agent_id}
    except Exception as e:
        log_event("Provider", f"Error while shutting down Agent {request.agent_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to cleanly stop worker thread.")

@app.get("/api/runtime/status/{agent_id}")
def check_status(agent_id: str):
    """Checks the operational status of an agent's execution thread."""
    worker = active_workers.get(agent_id)
    if not worker:
        return {"agent_id": agent_id, "active": False, "status": "not_running"}
    
    is_alive = worker.is_alive()
    return {
        "agent_id": agent_id,
        "active": is_alive,
        "status": "running" if is_alive else "zombie"
    }
