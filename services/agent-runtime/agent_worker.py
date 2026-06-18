import time
import logging
import threading
import requests

import crypto_utils

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("AgentWorker")

IDENTITY_COMPOSE_URL = "http://localhost:8002/api/identity/compose"
IDENTITY_CALL_MODEL_URL = "http://localhost:8002/api/identity/call-model"

class AgentWorker(threading.Thread):
    def __init__(self, agent_id: str, model: str):
        super().__init__()
        self.agent_id = agent_id
        self.model = model
        self._stop_event = threading.Event()
        self.daemon = True 
        
        # Cryptographic fields initialized as None (bootstrapped in idle state)
        self.private_key = None
        self.public_key_pem = None
        self.agent_id_jwt = None
        self.deployer_identifier = None
        self.deployer_accountability_id = None

    def run(self):
        """Main execution loop for the agent instance (booted idle)."""
        logger.info(f"Provider - [Agent-{self.agent_id}] Thread started. Initializing agent logic using {self.model} model...")
        
        # Simulate loading prompt templates, tools, and LLM clients
        time.sleep(1)
        logger.info(f"Agent - [Agent-{self.agent_id}] Agent is active and listening for prompts.")

        while not self._stop_event.is_set():
            logger.info(f"Agent - [Agent-{self.agent_id}] Status: IDLE. Waiting for prompt inputs...")
            self._stop_event.wait(timeout=10.0)

        logger.info(f"Provider - [Agent-{self.agent_id}] Thread stop signal received. Shutting down gracefully...")

    def initialize_cryptographic_identity(
        self,
        deployer_identifier: str,
        deployer_accountability_id: str,
        prompt: str,
        receiving_service: str
    ):
        """
        Runs the cryptographic handshake (Steps 2 to 5) when an initial prompt is received.
        Generates keys, fetches LLM attestation, and signs the composite Agent ID token.
        """
        logger.info(f"Agent - [Agent-{self.agent_id}] Prompt received. Starting cryptographic identity composition...")
        self.deployer_identifier = deployer_identifier
        self.deployer_accountability_id = deployer_accountability_id

        # 1. Step 1: Generate EC Key Pair
        logger.info(f"Provider - [Agent-{self.agent_id}] [Step 1] Generating EC P-256 Key Pair for this request...")
        self.private_key, self.public_key_pem = crypto_utils.generate_ec_key_pair()

        # 2. Step 3 & 4: Call Model and Get Developer Attestation
        try:
            logger.info(f"Agent - [Agent-{self.agent_id}] [Step 3] Calling LLM Developer attestation endpoint...")
            model_payload = {
                "prompt": prompt,
                "receiving_service": receiving_service,
                "request_attestation": True,
                "model": self.model
            }
            model_res = requests.post(IDENTITY_CALL_MODEL_URL, json=model_payload, timeout=5)
            if model_res.status_code != 200:
                logger.error(f"Agent - [Agent-{self.agent_id}] LLM Developer call failed: {model_res.text}")
                return False
            
            model_data = model_res.json()
            dev_attestation = model_data.get("developer_attestation")
            logger.info(f"Agent - [Agent-{self.agent_id}] [Step 4] Received action plan and Developer safety attestation.")

            # 3. Step 5: Compose provider attestation / Agent ID JWT
            logger.info(f"Agent - [Agent-{self.agent_id}] [Step 5] Requesting Provider signature to compile Agent ID JWT...")
            compose_payload = {
                "agent_id": self.agent_id,
                "agent_public_key": self.public_key_pem,
                "deployer_identifier": self.deployer_identifier,
                "deployer_accountability_id": self.deployer_accountability_id,
                "developer_attestation": dev_attestation
            }
            compose_res = requests.post(IDENTITY_COMPOSE_URL, json=compose_payload, timeout=5)
            if compose_res.status_code == 200:
                self.agent_id_jwt = compose_res.json().get("agent_id_jwt")
                logger.info(f"Agent - [Agent-{self.agent_id}] Cryptographic Agent ID JWT successfully received and bound.")
                return True
            else:
                logger.error(f"Agent - [Agent-{self.agent_id}] Provider composition failed: {compose_res.text}")
                return False

        except requests.exceptions.RequestException as e:
            logger.error(f"Agent - [Agent-{self.agent_id}] Cryptographic handshake failed due to connection error: {str(e)}")
            return False

    def stop(self):
        """Triggers the thread to break out of its execution loop."""
        self._stop_event.set()

