import time
import threading
import requests
import jwt

import crypto_utils
from logger_utils import log_event

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
        log_event("Provider", f"[Agent-{self.agent_id}] Thread started. Initializing agent logic using {self.model} model...")
        
        # Simulate loading prompt templates, tools, and LLM clients
        time.sleep(1)
        log_event("Agent", f"[Agent-{self.agent_id}] Agent is active and listening for prompts.")

        while not self._stop_event.is_set():
            log_event("Agent", f"[Agent-{self.agent_id}] Status: IDLE. Waiting for prompt inputs...")
            self._stop_event.wait(timeout=10.0)

        log_event("Provider", f"[Agent-{self.agent_id}] Thread stop signal received. Shutting down gracefully...")

    def initialize_cryptographic_identity(
        self,
        deployer_attestation: str,
        prompt: str,
        receiving_service: str
    ):
        """
        Runs the cryptographic handshake (Steps 2 to 5) when an initial prompt is received.
        Generates keys, signs Agent Binding, fetches Developer & Provider attestations,
        and assembles the flat JSON presentation.
        """
        log_event("Agent", f"[Agent-{self.agent_id}] Prompt received. Starting cryptographic identity composition...")
        self.deployer_attestation = deployer_attestation

        # 1. Step 1: Generate EC Key Pair
        log_event("Provider", f"[Agent-{self.agent_id}] [Step 1] Generating ephemeral key pair using SECP256R1 (P-256) Elliptic Curve...")
        self.private_key, self.public_key_pem = crypto_utils.generate_ec_key_pair()
        truncated_pub_key = self.public_key_pem.replace('\n', '').replace('-----BEGIN PUBLIC KEY-----', '').replace('-----END PUBLIC KEY-----', '')[:40]
        log_event("Provider", f"[Agent-{self.agent_id}] [Step 1] Ephemeral EC Public Key generated: {truncated_pub_key}... Algorithm: ECDSA (SHA-256 binding ready)")

        # 2. Step 3 & 4: Call Model and Get Developer Attestation
        try:
            model_payload = {
                "prompt": prompt,
                "receiving_service": receiving_service,
                "request_attestation": True,
                "model": self.model
            }
            log_event("Agent", f"[Agent-{self.agent_id}] [Step 3] Calling LLM Developer attestation endpoint: {IDENTITY_CALL_MODEL_URL}. Payload: {model_payload}")
            model_res = requests.post(IDENTITY_CALL_MODEL_URL, json=model_payload, timeout=5)
            
            if model_res.status_code != 200:
                log_event("Agent", f"[Agent-{self.agent_id}] LLM Developer call failed. Status Code: HTTP {model_res.status_code}. Response: {model_res.text}")
                return False
            
            model_data = model_res.json()
            dev_attestation = model_data.get("developer_attestation")
            log_event("Agent", f"[Agent-{self.agent_id}] [Step 4] Received safety attestation. Response Body: foundation_model_identifier='{model_data.get('foundation_model_identifier')}', developer_identifier='{model_data.get('developer_identifier')}', safety_evidence_url='{model_data.get('foundation_model_safety_evidence')}', developer_attestation (JWT)='{dev_attestation[:30]}...'")

            # 3. Create Agent Instance Binding JWT (Signed by Agent Private Key)
            spiffe_id = f"spiffe://provider.net/agent/worker-{self.agent_id}"
            binding_payload = {
                "iss": spiffe_id,
                "sub": spiffe_id,
                "agent_instance_identifier": spiffe_id,
                "agent_public_key": self.public_key_pem
            }
            binding_jwt = jwt.encode(binding_payload, self.private_key, algorithm="ES256")
            log_event("Agent", f"[Agent-{self.agent_id}] Generated Agent Instance Binding JWT (Signed using ES256 with Agent ephemeral private key)")

            # 4. Step 5: Compose Provider Attestation
            compose_payload = {
                "agent_id": self.agent_id
            }
            log_event("Agent", f"[Agent-{self.agent_id}] [Step 5] Requesting Provider signature to compile Provider Attestation JWT: {IDENTITY_COMPOSE_URL}. Payload: agent_id='{compose_payload['agent_id']}'")
            compose_res = requests.post(IDENTITY_COMPOSE_URL, json=compose_payload, timeout=5)
            
            if compose_res.status_code == 200:
                provider_attestation = compose_res.json().get("provider_attestation")
                log_event("Agent", f"[Agent-{self.agent_id}] Provider composition succeeded. Status Code: HTTP 200 OK. Received Provider Attestation JWT (len: {len(provider_attestation)} bytes, algorithm: ES256)")
                
                # Assemble final flat JSON Agent ID presentation
                self.agent_id_jwt = {
                    "developer_attestation": dev_attestation,
                    "provider_attestation": provider_attestation,
                    "deployer_attestation": self.deployer_attestation,
                    "agent_instance_binding": binding_jwt
                }
                
                # Decode and inspect all 4 JWT claims locally at the peer level
                log_event("Agent", f"[Agent-{self.agent_id}] Token Inspection - Decoded Peer-Level Agent ID claims:")
                
                # 1. Developer Attestation
                dev_claims = jwt.decode(dev_attestation, options={"verify_signature": False})
                log_event("Agent", f"  --- Developer Attestation Claims ---")
                log_event("Agent", f"    iss (Issuer):               {dev_claims.get('iss')}")
                log_event("Agent", f"    developer_identifier:        {dev_claims.get('developer_identifier')}")
                log_event("Agent", f"    foundation_model_identifier: {dev_claims.get('foundation_model_identifier')}")
                log_event("Agent", f"    jti (Nonce):                {dev_claims.get('jti')}")
                log_event("Agent", f"    iat (Issued At):            {dev_claims.get('iat')}")

                # 2. Provider Attestation
                prov_claims = jwt.decode(provider_attestation, options={"verify_signature": False})
                log_event("Agent", f"  --- Provider Attestation Claims ---")
                log_event("Agent", f"    iss (Issuer):               {prov_claims.get('iss')}")
                log_event("Agent", f"    provider_identifier:        {prov_claims.get('provider_identifier')}")
                log_event("Agent", f"    sub (Subject):             {prov_claims.get('sub')}")
                log_event("Agent", f"    agent_instance_identifier:  {prov_claims.get('agent_instance_identifier')}")
                log_event("Agent", f"    provider_security_evidence: {prov_claims.get('provider_security_evidence')}")
                log_event("Agent", f"    agent_instance_shutdown_command: {prov_claims.get('agent_instance_shutdown_command')}")

                # 3. Deployer Attestation
                dep_claims = jwt.decode(self.deployer_attestation, options={"verify_signature": False})
                log_event("Agent", f"  --- Deployer Attestation Claims ---")
                log_event("Agent", f"    iss (Issuer):               {dep_claims.get('iss')}")
                log_event("Agent", f"    deployer_identifier:        {dep_claims.get('deployer_identifier')}")
                log_event("Agent", f"    deployer_accountability_id (JWE): {dep_claims.get('deployer_accountability_id')[:30]}...")

                # 4. Agent Instance Binding
                bind_claims = jwt.decode(binding_jwt, options={"verify_signature": False})
                log_event("Agent", f"  --- Agent Instance Binding Claims ---")
                log_event("Agent", f"    iss (Issuer):               {bind_claims.get('iss')}")
                log_event("Agent", f"    sub (Subject):             {bind_claims.get('sub')}")
                log_event("Agent", f"    agent_instance_identifier:  {bind_claims.get('agent_instance_identifier')}")
                log_event("Agent", f"    agent_public_key (truncated):     {bind_claims.get('agent_public_key')[:40].replace(chr(10),'')}...")

                log_event("Agent", f"[Agent-{self.agent_id}] Cryptographic Agent ID flat presentation successfully assembled.")
                
                # 5. Direct target Service invocation (original flow alignment)
                import re
                amount = 1000.0
                from_account = "checking"
                to_account = "savings"
                
                lower_prompt = prompt.lower()
                if "checking" in lower_prompt:
                    from_account = "checking"
                if "savings" in lower_prompt:
                    to_account = "savings"
                
                numbers = re.findall(r'\b\d+(?:\.\d+)?\b', lower_prompt)
                if numbers:
                    try:
                        amount = float(numbers[0])
                    except ValueError:
                        pass
                
                log_event("Agent", f"[Agent-{self.agent_id}] Direct Invocation: Submitting transaction to target service '{receiving_service}'...")
                bank_url = "http://127.0.0.1:8003/api/bank/transfer"
                bank_payload = {
                    "amount": amount,
                    "from_account": from_account,
                    "to_account": to_account,
                    "agent_id_jwt": self.agent_id_jwt
                }
                log_event("Agent", f"[Agent-{self.agent_id}] HTTP POST to Bank Service: {bank_url}. Payload: Transfer {amount:.2f} USD from '{from_account}' to '{to_account}' using flat Agent ID.")
                try:
                    res = requests.post(bank_url, json=bank_payload, timeout=10)
                    if res.status_code == 200:
                        log_event("Agent", f"[Agent-{self.agent_id}] Bank Service Response (HTTP 200 OK): {res.json()}")
                        log_event("Agent", f"[Agent-{self.agent_id}] [SUCCESS] Transaction completed successfully!")
                    else:
                        log_event("Agent", f"[Agent-{self.agent_id}] [ERROR] Bank Service rejected transaction (HTTP {res.status_code}): {res.text}")
                except Exception as e:
                    log_event("Agent", f"[Agent-{self.agent_id}] [ERROR] Connection to Bank Service failed: {str(e)}")

                return True
            else:
                log_event("Agent", f"[Agent-{self.agent_id}] Provider composition failed. Status Code: HTTP {compose_res.status_code}. Response: {compose_res.text}")
                return False
        except requests.exceptions.RequestException as e:
            log_event("Agent", f"[Agent-{self.agent_id}] Cryptographic handshake failed due to connection error: {str(e)}")
            return False

    def stop(self):
        """Triggers the thread to break out of its execution loop."""
        self._stop_event.set()

