import time
import logging
import threading

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("AgentWorker")

class AgentWorker(threading.Thread):
    def __init__(self, agent_id: str, model: str):
        super().__init__()
        self.agent_id = agent_id
        self.model = model
        self._stop_event = threading.Event()
        # Make the thread a daemon so it dies when the main process exits
        self.daemon = True 

    def run(self):
        """Main execution loop for the agent instance."""
        logger.info(f"[Agent-{self.agent_id}] Thread started. Initializing agent logic using {self.model} model...")
        
        # Simulate loading prompt templates, tools, and LLM clients
        time.sleep(1)
        logger.info(f"[Agent-{self.agent_id}] Agent is active and listening for prompts.")

        while not self._stop_event.is_set():
            # In a production environment, this loop would poll a queue (Kafka/Redis)
            # or listen on a socket for instructions from the deployer.
            logger.info(f"[Agent-{self.agent_id}] Status: IDLE. Waiting for prompt inputs...")
            # Sleep for 10 seconds to avoid flooding the logs
            self._stop_event.wait(timeout=10.0)

        logger.info(f"[Agent-{self.agent_id}] Thread stop signal received. Shutting down gracefully...")

    def stop(self):
        """Triggers the thread to break out of its execution loop."""
        self._stop_event.set()
