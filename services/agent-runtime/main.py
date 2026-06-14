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

class RuntimeStartRequest(BaseModel):
    agent_id: str
    model: str

class RuntimeStopRequest(BaseModel):
    agent_id: str

@app.on_event("startup")
def on_startup():
    logger.info("Agent Runtime Service started on port 8001.")

@app.post("/api/runtime/start")
def start_runtime(request: RuntimeStartRequest):
    """
    Spawns a new background execution thread simulating the AI Agent compute process.
    """
    logger.info(f"Request to spawn worker thread for Agent: {request.agent_id}")
    
    if request.agent_id in active_workers:
        logger.warning(f"Agent {request.agent_id} is already running in the runtime environment.")
        # Return existing info
        return {"runtime_id": f"worker-{request.agent_id}", "status": "already_running"}

    try:
        # Create and start the worker thread
        worker = AgentWorker(agent_id=request.agent_id, model=request.model)
        worker.start()
        
        # Save to active workers registry
        active_workers[request.agent_id] = worker
        runtime_id = f"worker-{request.agent_id}"
        
        logger.info(f"Worker thread {runtime_id} successfully created and running.")
        return {
            "runtime_id": runtime_id,
            "status": "running"
        }
    except Exception as e:
        logger.error(f"Failed to spawn thread for Agent {request.agent_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error spinning up worker.")

@app.post("/api/runtime/stop")
def stop_runtime(request: RuntimeStopRequest):
    """
    Stops a running worker thread. This simulates an emergency shutdown scenario.
    """
    logger.info(f"Request to terminate worker thread for Agent: {request.agent_id}")
    
    worker = active_workers.get(request.agent_id)
    if not worker:
        logger.warning(f"No active worker found for Agent: {request.agent_id}")
        raise HTTPException(status_code=404, detail="No active worker thread found for this Agent ID.")

    try:
        # Signal the thread to stop and remove from registry
        worker.stop()
        worker.join(timeout=3)  # Wait up to 3 seconds for graceful exit
        del active_workers[request.agent_id]
        
        logger.info(f"Worker thread for Agent {request.agent_id} stopped successfully.")
        return {"status": "stopped", "agent_id": request.agent_id}
    except Exception as e:
        logger.error(f"Error while shutting down Agent {request.agent_id}: {str(e)}")
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
