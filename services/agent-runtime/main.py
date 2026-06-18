import uuid
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict

from agent_worker import AgentWorker

# Configure basic logging to console
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("AgentRuntime")

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
    deployer_identifier: str
    deployer_accountability_id: str

class RuntimeStopRequest(BaseModel):
    agent_id: str

@app.on_event("startup")
def on_startup():
    logger.info("Provider - Agent Runtime Service started on port 8001.")

@app.post("/api/runtime/start")
def start_runtime(request: RuntimeStartRequest):
    """
    Step 1: Spawns a new background execution thread simulating the AI Agent compute process.
    Does not perform key generation or identity binding yet.
    """
    logger.info(f"Provider - Agent Runtime received request to spawn worker thread for Agent: {request.agent_id}")
    
    if request.agent_id in active_workers:
        logger.warning(f"Provider - Agent {request.agent_id} is already running in the runtime environment.")
        return {"runtime_id": f"worker-{request.agent_id}", "status": "already_running"}

    try:
        # Create and start the worker thread in an idle, unsigned state
        worker = AgentWorker(agent_id=request.agent_id, model=request.model)
        worker.start()
        
        # Save to active workers registry
        active_workers[request.agent_id] = worker
        runtime_id = f"worker-{request.agent_id}"
        
        logger.info(f"Provider - Worker thread {runtime_id} successfully created and running.")
        return {
            "runtime_id": runtime_id,
            "status": "running"
        }
    except Exception as e:
        logger.error(f"Provider - Failed to spawn thread for Agent {request.agent_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error spinning up worker.")

@app.post("/api/runtime/{agent_id}/prompt")
def receive_prompt(agent_id: str, request: RuntimePromptRequest):
    """
    Step 2: Receives an operational prompt. Triggers key generation and fetches the composite Agent ID JWT.
    """
    logger.info(f"Provider - Agent Runtime received prompt for Agent {agent_id}. Starting cryptographic composition...")
    
    worker = active_workers.get(agent_id)
    if not worker:
        raise HTTPException(status_code=404, detail="Agent worker thread not found.")

    # Trigger the cryptographic handshake inside the worker thread
    success = worker.initialize_cryptographic_identity(
        deployer_identifier=request.deployer_identifier,
        deployer_accountability_id=request.deployer_accountability_id,
        prompt=request.deployer_prompt,
        receiving_service=request.receiving_service
    )

    if not success or worker.agent_id_jwt is None:
        raise HTTPException(status_code=500, detail="Failed to compose cryptographic Agent ID JWT.")

    return {
        "status": "prepared",
        "agent_id_jwt": worker.agent_id_jwt
    }

@app.post("/api/runtime/stop")
def stop_runtime(request: RuntimeStopRequest):
    """
    Stops a running worker thread. This simulates an emergency shutdown scenario.
    """
    logger.info(f"Provider - Agent Runtime received request to terminate worker thread for Agent: {request.agent_id}")
    
    worker = active_workers.get(request.agent_id)
    if not worker:
        logger.warning(f"Provider - No active worker found for Agent: {request.agent_id}")
        raise HTTPException(status_code=404, detail="No active worker thread found for this Agent ID.")

    try:
        # Signal the thread to stop and remove from registry
        worker.stop()
        worker.join(timeout=3)  # Wait up to 3 seconds for graceful exit
        del active_workers[request.agent_id]
        
        logger.info(f"Provider - Worker thread for Agent {request.agent_id} stopped successfully.")
        return {"status": "stopped", "agent_id": request.agent_id}
    except Exception as e:
        logger.error(f"Provider - Error while shutting down Agent {request.agent_id}: {str(e)}")
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
