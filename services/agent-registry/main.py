import uuid
import logging
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

import database

# Configure basic logging to console
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("AgentRegistry")

app = FastAPI(title="Agent ID Platform - Agent Registry")

# Define the target URL for the Agent Runtime service
RUNTIME_SERVICE_URL = "http://localhost:8001/api/runtime/start"

# Request schema for agent registration
class AgentCreateRequest(BaseModel):
    name: str
    description: str
    model: str

@app.on_event("startup")
def on_startup():
    database.init_db()
    logger.info("Agent Registry Service started and database initialized.")

@app.post("/api/agents")
def register_agent(request: AgentCreateRequest):
    """
    Registers a new agent in the system and triggers its runtime instance startup.
    """
    agent_id = str(uuid.uuid4())
    logger.info(f"Received registration request for agent: {request.name} (Model: {request.model})")

    # Step 1: Create agent record with 'initializing' status
    agent_data = {
        "id": agent_id,
        "name": request.name,
        "description": request.description,
        "model": request.model,
        "status": "initializing",
        "runtime_id": None
    }
    database.save_agent(agent_id, agent_data)
    logger.info(f"Agent {agent_id} saved to registry database with 'initializing' status.")

    # Step 2: Request the Runtime Service to provision and start the Agent instance
    try:
        payload = {
            "agent_id": agent_id,
            "model": request.model
        }
        logger.info(f"Contacting Runtime Service at {RUNTIME_SERVICE_URL} to spin up agent...")
        response = requests.post(RUNTIME_SERVICE_URL, json=payload, timeout=5)
        
        if response.status_code == 200:
            runtime_info = response.json()
            # Update the agent status to 'running' and store the runtime thread/worker ID
            agent_data["status"] = "running"
            agent_data["runtime_id"] = runtime_info.get("runtime_id")
            database.save_agent(agent_id, agent_data)
            logger.info(f"Agent {agent_id} successfully provisioned on runtime: {runtime_info.get('runtime_id')}")
        else:
            agent_data["status"] = "failed_to_provision"
            database.save_agent(agent_id, agent_data)
            logger.error(f"Runtime service returned error {response.status_code}: {response.text}")
            raise HTTPException(status_code=502, detail="Failed to start agent in the runtime environment.")

    except requests.exceptions.RequestException as e:
        agent_data["status"] = "failed_to_provision"
        database.save_agent(agent_id, agent_data)
        logger.error(f"Could not connect to Runtime Service: {str(e)}")
        raise HTTPException(status_code=503, detail="Agent Runtime Service is currently offline.")

    return {
        "agent_id": agent_id,
        "name": agent_data["name"],
        "status": agent_data["status"],
        "runtime_id": agent_data["runtime_id"]
    }

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
