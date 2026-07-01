import time
import threading
import requests
import jwt

import crypto_utils
from logger_utils import log_event

IDENTITY_COMPOSE_URL = "http://127.0.0.1:8002/api/identity/compose"
IDENTITY_CALL_MODEL_URL = "http://127.0.0.1:8002/api/identity/call-model"

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
        log_event("Agent", f"[Agent-{self.agent_id}] Status: IDLE. Waiting for prompt inputs...")

        while not self._stop_event.is_set():
            self._stop_event.wait(timeout=120.0)
            if not self._stop_event.is_set():
                log_event("Agent", f"[Agent-{self.agent_id}] Status: IDLE. Waiting for prompt inputs...")

        log_event("Provider", f"[Agent-{self.agent_id}] Thread stop signal received. Shutting down gracefully...")

    def initialize_cryptographic_identity(
        self,
        deployer_attestation: str,
        prompt: str,
        receiving_service: str,
        deployer_identifier_on_service: str
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

        import hashlib

        # Calculate Deployer Attestation SHA-256 hash
        deployer_hash = hashlib.sha256(self.deployer_attestation.encode('utf-8')).hexdigest()

        # 2. Step 3 & 4: Call Model and Get Developer Attestation
        try:
            model_payload = {
                "prompt": prompt,
                "receiving_service": receiving_service,
                "request_attestation": True,
                "model": self.model,
                "parent_token_hash": deployer_hash
            }
            log_event("Provider", f"[Agent-{self.agent_id}] [Step 3] Calling LLM Developer attestation endpoint: {IDENTITY_CALL_MODEL_URL}. Payload: {model_payload}")
            model_res = requests.post(IDENTITY_CALL_MODEL_URL, json=model_payload, timeout=5)
            
            if model_res.status_code != 200:
                log_event("Provider", f"[Agent-{self.agent_id}] LLM Developer call failed. Status Code: HTTP {model_res.status_code}. Response: {model_res.text}")
                return False
            
            model_data = model_res.json()
            dev_attestation = model_data.get("developer_attestation")
            log_event("Provider", f"[Agent-{self.agent_id}] [Step 4] Received safety attestation. Response Body: foundation_model_identifier='{model_data.get('foundation_model_identifier')}', developer_identifier='{model_data.get('developer_identifier')}', safety_evidence_url='{model_data.get('foundation_model_safety_evidence')}', developer_attestation (JWT)='{dev_attestation[:30]}...'")
 
            # Calculate Developer Attestation SHA-256 hash
            developer_hash = hashlib.sha256(dev_attestation.encode('utf-8')).hexdigest()
 
            # 3. Step 5: Compose Provider Attestation
            compose_payload = {
                "agent_id": self.agent_id,
                "parent_token_hash": developer_hash
            }
            log_event("Provider", f"[Agent-{self.agent_id}] [Step 5] Requesting Provider signature to compile Provider Attestation JWT: {IDENTITY_COMPOSE_URL}. Payload: agent_id='{compose_payload['agent_id']}', parent_token_hash='{compose_payload['parent_token_hash']}'")
            compose_res = requests.post(IDENTITY_COMPOSE_URL, json=compose_payload, timeout=5)
            
            if compose_res.status_code == 200:
                provider_attestation = compose_res.json().get("provider_attestation")
                log_event("Provider", f"[Agent-{self.agent_id}] Provider composition succeeded. Status Code: HTTP 200 OK. Received Provider Attestation JWT (len: {len(provider_attestation)} bytes, algorithm: ES256)")

                # Calculate Provider Attestation SHA-256 hash
                provider_hash = hashlib.sha256(provider_attestation.encode('utf-8')).hexdigest()

                # 4. Create Agent Instance Binding JWT (Signed by Agent Private Key)
                spiffe_id = f"spiffe://provider.net/agent/worker-{self.agent_id}"
                binding_payload = {
                    "iss": spiffe_id,
                    "sub": spiffe_id,
                    "agent_instance_identifier": spiffe_id,
                    "agent_public_key": self.public_key_pem,
                    "parent_token_hash": provider_hash
                }
                binding_jwt = jwt.encode(binding_payload, self.private_key, algorithm="ES256")
                log_event("Agent", f"[Agent-{self.agent_id}] Generated Agent Instance Binding JWT with parent_token_hash (Signed using ES256 with Agent ephemeral private key)")
                
                # Assemble final flat JSON Agent ID presentation
                self.agent_id_jwt = {
                    "developer_attestation": dev_attestation,
                    "provider_attestation": provider_attestation,
                    "deployer_attestation": self.deployer_attestation,
                    "agent_instance_binding": binding_jwt
                }
                
                # Decode and inspect all 4 JWT claims locally at the peer level
                log_event("Agent", f"[Agent-{self.agent_id}] Token Inspection - Decoded Peer-Level Agent ID claims:")
                
                # 1. Deployer Attestation
                dep_claims = jwt.decode(self.deployer_attestation, options={"verify_signature": False})
                log_event("Agent", f"  --- Deployer Attestation Claims ---")
                log_event("Agent", f"    iss (Issuer):               {dep_claims.get('iss')}")
                log_event("Agent", f"    deployer_identifier:        {dep_claims.get('deployer_identifier')}")
                log_event("Agent", f"    deployer_accountability_id (JWE): {dep_claims.get('deployer_accountability_id')[:30]}...")

                # 2. Developer Attestation
                dev_claims = jwt.decode(dev_attestation, options={"verify_signature": False})
                log_event("Agent", f"  --- Developer Attestation Claims ---")
                log_event("Agent", f"    iss (Issuer):               {dev_claims.get('iss')}")
                log_event("Agent", f"    developer_identifier:        {dev_claims.get('developer_identifier')}")
                log_event("Agent", f"    foundation_model_identifier: {dev_claims.get('foundation_model_identifier')}")
                log_event("Agent", f"    parent_token_hash:          {dev_claims.get('parent_token_hash')}")

                # 3. Provider Attestation
                prov_claims = jwt.decode(provider_attestation, options={"verify_signature": False})
                log_event("Agent", f"  --- Provider Attestation Claims ---")
                log_event("Agent", f"    iss (Issuer):               {prov_claims.get('iss')}")
                log_event("Agent", f"    provider_identifier:        {prov_claims.get('provider_identifier')}")
                log_event("Agent", f"    sub (Subject):             {prov_claims.get('sub')}")
                log_event("Agent", f"    agent_instance_identifier:  {prov_claims.get('agent_instance_identifier')}")
                log_event("Agent", f"    provider_security_evidence: {prov_claims.get('provider_security_evidence')}")
                log_event("Agent", f"    agent_instance_shutdown_command: {prov_claims.get('agent_instance_shutdown_command')}")
                log_event("Agent", f"    parent_token_hash:          {prov_claims.get('parent_token_hash')}")

                # 4. Agent Instance Binding
                bind_claims = jwt.decode(binding_jwt, options={"verify_signature": False})
                log_event("Agent", f"  --- Agent Instance Binding Claims ---")
                log_event("Agent", f"    iss (Issuer):               {bind_claims.get('iss')}")
                log_event("Agent", f"    sub (Subject):             {bind_claims.get('sub')}")
                log_event("Agent", f"    agent_instance_identifier:  {bind_claims.get('agent_instance_identifier')}")
                log_event("Agent", f"    agent_public_key (truncated):     {bind_claims.get('agent_public_key')[:40].replace(chr(10),'')}...")
                log_event("Agent", f"    parent_token_hash:          {bind_claims.get('parent_token_hash')}")

                log_event("Agent", f"[Agent-{self.agent_id}] Cryptographic Agent ID flat presentation successfully assembled.")
                
                # 5. OAuth 2.0 CIBA Authorization (Steps 6-9)
                log_event("Agent", f"[Agent-{self.agent_id}] [Step 6] Initiating OAuth 2.0 CIBA request to Bank Service...")
                ciba_url = "http://127.0.0.1:8003/api/oauth/ciba"
                ciba_payload = {
                    "requested_scopes": ["transfer_funds"],
                    "deployer_identifier_on_service": deployer_identifier_on_service
                }
                
                try:
                    ciba_res = requests.post(ciba_url, json=ciba_payload, timeout=5)
                    if ciba_res.status_code != 200:
                        log_event("Agent", f"[Agent-{self.agent_id}] [ERROR] CIBA request failed (HTTP {ciba_res.status_code}): {ciba_res.text}")
                        return False
                    
                    ciba_data = ciba_res.json()
                    auth_req_id = ciba_data.get("auth_req_id")
                    interval = ciba_data.get("interval", 1.5)
                    log_event("Agent", f"[Agent-{self.agent_id}] CIBA request registered. Received auth_req_id: {auth_req_id}. Entering polling loop for OAuth token...")
                except Exception as e:
                    log_event("Agent", f"[Agent-{self.agent_id}] [ERROR] Failed to connect to CIBA endpoint: {str(e)}")
                    return False
                
                # Polling loop for token (Step 9)
                token_url = "http://127.0.0.1:8003/api/oauth/token"
                token_payload = {
                    "grant_type": "urn:openid:params:grant-type:ciba",
                    "auth_req_id": auth_req_id
                }
                
                access_token = None
                max_polls = 60
                for poll_num in range(max_polls):
                    try:
                        token_res = requests.post(token_url, json=token_payload, timeout=5)
                        if token_res.status_code == 200:
                            token_data = token_res.json()
                            access_token = token_data.get("access_token")
                            log_event("Agent", f"[Agent-{self.agent_id}] [Step 9] OAuth access token successfully retrieved: {access_token[:15]}...")
                            break
                        elif token_res.status_code == 400:
                            err_data = token_res.json()
                            if err_data.get("error") == "authorization_pending":
                                log_event("Agent", f"[Agent-{self.agent_id}] [Step 7-8] OAuth token authorization pending. Awaiting Deployer out-of-band approval (Poll {poll_num+1}/{max_polls})...")
                            else:
                                log_event("Agent", f"[Agent-{self.agent_id}] [ERROR] Token endpoint returned error: {err_data}")
                                return False
                        else:
                            log_event("Agent", f"[Agent-{self.agent_id}] [ERROR] Token endpoint returned HTTP {token_res.status_code}")
                            return False
                    except Exception as e:
                        log_event("Agent", f"[Agent-{self.agent_id}] [ERROR] Polling token failed: {str(e)}")
                        return False
                    
                    time.sleep(interval)
                
                if not access_token:
                    log_event("Agent", f"[Agent-{self.agent_id}] [ERROR] CIBA authentication timed out after {max_polls * interval} seconds.")
                    return False
                
                # 6. Target Service transaction execution (Step 10)
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
                
                log_event("Agent", f"[Agent-{self.agent_id}] [Step 10] Submitting transaction with OAuth access token to target service...")
                bank_url = "http://127.0.0.1:8003/api/bank/transfer"
                bank_payload = {
                    "amount": amount,
                    "from_account": from_account,
                    "to_account": to_account,
                    "agent_id_jwt": self.agent_id_jwt
                }
                bank_headers = {
                    "Authorization": f"Bearer {access_token}"
                }
                log_event("Agent", f"[Agent-{self.agent_id}] HTTP POST to Bank Service: {bank_url}. Headers: Authorization: Bearer {access_token[:10]}...")
                try:
                    res = requests.post(bank_url, json=bank_payload, headers=bank_headers, timeout=10)
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

