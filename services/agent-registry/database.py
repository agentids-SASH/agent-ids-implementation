import json
import os
from typing import Dict, Any, Optional

DB_FILE = "agents_db.json"

def init_db():
    """Initializes the JSON database file if it does not exist."""
    if not os.path.exists(DB_FILE):
        with open(DB_FILE, "w") as f:
            json.dump({}, f)

def get_all_agents() -> Dict[str, Any]:
    """Retrieves all registered agents from the database."""
    init_db()
    try:
        with open(DB_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}

def save_agent(agent_id: str, agent_data: Dict[str, Any]):
    """Saves or updates an agent record in the JSON database."""
    agents = get_all_agents()
    agents[agent_id] = agent_data
    with open(DB_FILE, "w") as f:
        json.dump(agents, f, indent=4)

def get_agent(agent_id: str) -> Optional[Dict[str, Any]]:
    """Gets a specific agent record by its unique ID."""
    agents = get_all_agents()
    return agents.get(agent_id)
