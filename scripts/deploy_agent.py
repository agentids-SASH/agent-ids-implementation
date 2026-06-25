import sys
import time
import base64
import requests
import jwt  # Used to decode the returned JWT to show claims
from cryptography.hazmat.primitives.asymmetric import padding, ec
from cryptography.hazmat.primitives import serialization, hashes

REGISTRY_URL = "http://localhost:8000/api/agents"

def log_deployer_event(message: str):
    now = time.time()
    local_time = time.localtime(now)
    time_str = time.strftime("%Y-%m-%d %H:%M:%S", local_time)
    ms = int((now - int(now)) * 1000)
    timestamp_str = f"{time_str}.{ms:03d}"
    
    # Print locally with Deployer color (Magenta)
    print(f"{timestamp_str} - \033[95m[Deployer]\033[0m - {message}", flush=True)
    
    # Post to central log aggregator
    try:
        requests.post("http://localhost:8000/api/logs", json={
            "timestamp": now,
            "actor": "Deployer",
            "message": message
        }, timeout=0.5)
    except Exception:
        pass
def get_key_from_jwks(jwks_url: str, kid: str) -> ec.EllipticCurvePublicKey:
    """Fetches key set from JWKS endpoint and reconstructs the public key for kid."""
    res = requests.get(jwks_url, timeout=5)
    if res.status_code != 200:
        raise Exception(f"Failed to fetch JWKS from {jwks_url}: HTTP {res.status_code}")
    keys = res.json().get("keys", [])
    for key in keys:
        if key.get("kid") == kid:
            # Decode base64url coordinates x and y
            def b64url_decode(s: str) -> bytes:
                rem = len(s) % 4
                if rem > 0:
                    s += '=' * (4 - rem)
                return base64.urlsafe_b64decode(s.encode('utf-8'))
            
            x_bytes = b64url_decode(key["x"])
            y_bytes = b64url_decode(key["y"])
            x = int.from_bytes(x_bytes, byteorder='big')
            y = int.from_bytes(y_bytes, byteorder='big')
            
            public_numbers = ec.EllipticCurvePublicNumbers(x, y, ec.SECP256R1())
            return public_numbers.public_key()
    raise Exception(f"Key with kid '{kid}' not found in JWKS at {jwks_url}")

def print_unified_logs():
    print("\n" + "="*80)
    print("                 UNIFIED PROTOCOL SEQUENCE LOGS (CHRONOLOGICAL)")
    print("="*80)
    try:
        res = requests.get("http://localhost:8000/api/logs", timeout=5)
        if res.status_code == 200:
            logs = res.json()
            colors = {
                "Provider": "\033[92m",   # Green
                "Agent": "\033[96m",      # Cyan
                "Developer": "\033[94m",  # Blue
                "Audit": "\033[93m",      # Yellow
                "Deployer": "\033[95m",   # Magenta
                "Bank": "\033[91m",       # Light Red
            }
            reset = "\033[0m"
            for log in logs:
                t = log.get("timestamp")
                actor = log.get("actor")
                msg = log.get("message")
                
                local_time = time.localtime(t)
                time_str = time.strftime("%Y-%m-%d %H:%M:%S", local_time)
                ms = int((t - int(t)) * 1000)
                timestamp_str = f"{time_str}.{ms:03d}"
                
                color = colors.get(actor, reset)
                print(f"{timestamp_str} - {color}[{actor}]{reset} - {msg}")
        else:
            print(f"[ERROR] Failed to fetch unified logs: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"[ERROR] Connection to Central Registry failed: {str(e)}")
    print("="*80 + "\n")

def main():
    print("=== Agent ID Platform - Deployer CLI Simulation ===")
    print("Beginning sequential execution of Steps 0 to 5...")

    # Clear central logs before starting
    try:
        requests.delete("http://localhost:8000/api/logs", timeout=2)
    except Exception:
        pass

    time.sleep(0.5)

    # ==========================================
    # PHASE 1: AGENT INITIALIZATION (Steps 0 & 1)
    # ==========================================
    log_deployer_event("PHASE 1: Starting Agent Registry & Provisioning (Steps 0 & 1)")
    boot_payload = {
        "name": "BankTransferAgent",
        "description": "Autonomous agent authorized to manage transfers.",
        "model": "gpt-4o"
    }

    try:
        log_deployer_event(f"Sending HTTP POST request to Register agent: {REGISTRY_URL}. Payload: {boot_payload}")
        response = requests.post(REGISTRY_URL, json=boot_payload, timeout=5)
        
        if response.status_code != 200:
            log_deployer_event(f"[ERROR] Failed to register agent. Status Code: HTTP {response.status_code}. Response: {response.text}")
            sys.exit(1)
            
        result = response.json()
        agent_id = result.get("agent_id")
        status = result.get("status")
        agent_instance_identifier = result.get("agent_instance_identifier")
        
        log_deployer_event(f"Registry responded with HTTP 200 OK. Response Payload: {result}")
        log_deployer_event(f"Agent Registered: ID={agent_id[:8]}..., Status={status}, Agent Instance ID={agent_instance_identifier}")

    except requests.exceptions.RequestException as e:
        log_deployer_event(f"[ERROR] Connection failed: {str(e)}")
        print("Please verify that the Agent Registry Service is running on port 8000.")
        sys.exit(1)

    time.sleep(1.5)

    # ==================================================
    # PHASE 2: PROMPT & IDENTITY HANDSHAKE (Steps 2 to 5)
    # ==================================================
    log_deployer_event("PHASE 2: Starting Prompt Submission & Cryptographic Handshake (Steps 2 to 5)")
    
    prompt_url = f"{REGISTRY_URL}/{agent_id}/prompt"
    
    # Fetch Audit Authority Public Key to encrypt sensitive Deployer Accountability ID
    log_deployer_event("Sending HTTP GET request to Audit Service: http://localhost:8004/api/audit/public-key")
    try:
        audit_res = requests.get("http://localhost:8004/api/audit/public-key", timeout=5)
        if audit_res.status_code != 200:
            log_deployer_event(f"[ERROR] Failed to fetch Audit public key. Status Code: HTTP {audit_res.status_code}. Response: {audit_res.text}")
            sys.exit(1)
        audit_res_payload = audit_res.json()
        log_deployer_event(f"Audit Service responded with HTTP 200 OK. Response Payload: public_key_pem='{audit_res_payload.get('public_key_pem')[:40].replace('\n','')}'...")
        audit_pub_pem = audit_res_payload.get("public_key_pem")
    except Exception as e:
        log_deployer_event(f"[ERROR] Connection to Audit Authority failed: {str(e)}")
        print("Please verify that the Audit Authority Service is running on port 8004.")
        sys.exit(1)

    # Encrypt Deployer Accountability ID ('Jane Doe') client-side before sending to Provider
    log_deployer_event("Encrypting Deployer Accountability ID ('Jane Doe') client-side using JWE (RSA-OAEP with SHA-256 algorithm)...")
    try:
        audit_pub_key = serialization.load_pem_public_key(audit_pub_pem.encode('utf-8'))
        plain_accountability_id = "Jane Doe"
        encrypted_bytes = audit_pub_key.encrypt(
            plain_accountability_id.encode('utf-8'),
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        encrypted_b64 = base64.b64encode(encrypted_bytes).decode('utf-8')
        log_deployer_event(f"Generated JWE ciphertext using RSA-OAEP-256: {encrypted_b64[:30]}...")
    except Exception as e:
        log_deployer_event(f"[ERROR] Encryption failed: {str(e)}")
        sys.exit(1)

    # Load or generate Deployer private key in scripts/
    deployer_key_file = "scripts/deployer_key.pem"
    deployer_pub_file = "services/agent-identity/deployer_public_key.pem"
    
    log_deployer_event("Loading or generating Deployer's local cryptographic private key...")
    import os
    if os.path.exists(deployer_key_file):
        try:
            with open(deployer_key_file, "rb") as f:
                deployer_private_key = serialization.load_pem_private_key(f.read(), password=None)
            log_deployer_event("Loaded existing Deployer private key from scripts/deployer_key.pem.")
        except Exception as e:
            log_deployer_event(f"[ERROR] Failed to load Deployer private key: {str(e)}")
            sys.exit(1)
    else:
        try:
            deployer_private_key = ec.generate_private_key(ec.SECP256R1())
            pem = deployer_private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            with open(deployer_key_file, "wb") as f:
                f.write(pem)
            log_deployer_event("Generated and saved new Deployer private key to scripts/deployer_key.pem.")
        except Exception as e:
            log_deployer_event(f"[ERROR] Failed to generate/save Deployer private key: {str(e)}")
            sys.exit(1)

    # Publish public key to Identity service directory
    try:
        deployer_public_key = deployer_private_key.public_key()
        pub_pem = deployer_public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        with open(deployer_pub_file, "wb") as f:
            f.write(pub_pem)
        log_deployer_event("Published Deployer public key to services/agent-identity/deployer_public_key.pem.")
    except Exception as e:
        log_deployer_event(f"[ERROR] Failed to publish Deployer public key: {str(e)}")
        sys.exit(1)

    # Construct and sign the Deployer Attestation JWT client-side
    log_deployer_event("Constructing and signing Deployer Attestation JWT client-side...")
    try:
        deployer_payload = {
            "iss": "deployer #101",
            "deployer_identifier": "deployer #101",
            "deployer_accountability_id": encrypted_b64
        }
        deployer_attestation = jwt.encode(deployer_payload, deployer_private_key, algorithm="ES256")
        log_deployer_event(f"Signed Deployer Attestation JWT (ES256): {deployer_attestation[:30]}...")
    except Exception as e:
        log_deployer_event(f"[ERROR] Failed to sign Deployer Attestation: {str(e)}")
        sys.exit(1)

    prompt_payload = {
        "deployer_prompt": "Transfer 1000 USD from my checking account to my savings account",
        "receiving_service": "bank.com",
        "deployer_identifier_on_service": "deployer's username on bank.com",
        "deployer_attestation": deployer_attestation
    }

    try:
        log_deployer_event(f"Sending HTTP POST request to Registry prompt endpoint: {prompt_url}. Payload: deployer_prompt='{prompt_payload['deployer_prompt']}', receiving_service='{prompt_payload['receiving_service']}', deployer_attestation (JWT)='{prompt_payload['deployer_attestation'][:30]}...'")
        response = requests.post(prompt_url, json=prompt_payload, timeout=10)
        
        if response.status_code != 200:
            log_deployer_event(f"[ERROR] Prompt submission failed. Status Code: HTTP {response.status_code}. Response: {response.text}")
            sys.exit(1)
            
        result = response.json()
        status = result.get("status")
        agent_id_jwt = result.get("agent_id_jwt")  # This is the flat JSON presentation dict
        
        log_deployer_event(f"Registry responded with HTTP 200 OK. Response Payload: status='{status}', agent_id_jwt (flat JSON container)")
        log_deployer_event(f"Cryptographic handshake completed! Agent State={status}")
        
        if agent_id_jwt:
            log_deployer_event("Cryptographic Agent ID flat container received successfully.")
            
            # Fetch Developer, Provider, and Deployer public keys from Identity Service JWKS
            log_deployer_event("Fetching Developer, Provider, and Deployer public keys from Identity Service JWKS...")
            try:
                jwks_url = "http://127.0.0.1:8002/.well-known/jwks.json"
                dev_key = get_key_from_jwks(jwks_url, "developer-key-1")
                prov_key = get_key_from_jwks(jwks_url, "provider-key-1")
                dep_key = get_key_from_jwks(jwks_url, "deployer-key-1")
            except Exception as e:
                log_deployer_event(f"[ERROR] Failed to resolve keys from JWKS: {str(e)}")
                sys.exit(1)

            dev_jwt = agent_id_jwt.get("developer_attestation")
            prov_jwt = agent_id_jwt.get("provider_attestation")
            dep_jwt = agent_id_jwt.get("deployer_attestation")
            bind_jwt = agent_id_jwt.get("agent_instance_binding")

            log_deployer_event("Verifying and decoding all 4 peer-level independent JWTs:")
            
            # 1. Verify Developer Attestation
            try:
                decoded_dev = jwt.decode(dev_jwt, dev_key, algorithms=["ES256"])
                log_deployer_event("[VERIFICATION SUCCESS] Developer Attestation verified under Developer JWK.")
                print("    --- Developer Attestation Claims ---")
                print(f"      iss (Issuer):               {decoded_dev.get('iss')}")
                print(f"      developer_identifier:        {decoded_dev.get('developer_identifier')}")
                print(f"      foundation_model_identifier: {decoded_dev.get('foundation_model_identifier')}")
                print(f"      foundation_model_safety_evidence: {decoded_dev.get('foundation_model_safety_evidence')}")
                print(f"      jti (Nonce):                {decoded_dev.get('jti')}")
                print(f"      iat (Issued At):            {decoded_dev.get('iat')}")
            except Exception as e:
                log_deployer_event(f"[VERIFICATION FAILED] Developer Attestation signature verification failed: {str(e)}")

            # 2. Verify Provider Attestation
            try:
                decoded_prov = jwt.decode(prov_jwt, prov_key, algorithms=["ES256"])
                log_deployer_event("[VERIFICATION SUCCESS] Provider Attestation verified under Provider JWK.")
                print("    --- Provider Attestation Claims ---")
                print(f"      iss (Issuer):               {decoded_prov.get('iss')}")
                print(f"      provider_identifier:        {decoded_prov.get('provider_identifier')}")
                print(f"      sub (Subject):             {decoded_prov.get('sub')}")
                print(f"      agent_instance_identifier:  {decoded_prov.get('agent_instance_identifier')}")
                print(f"      provider_security_evidence: {decoded_prov.get('provider_security_evidence')}")
                print(f"      agent_instance_shutdown_command: {decoded_prov.get('agent_instance_shutdown_command')}")
            except Exception as e:
                log_deployer_event(f"[VERIFICATION FAILED] Provider Attestation signature verification failed: {str(e)}")

            # 3. Verify Deployer Attestation
            try:
                decoded_dep = jwt.decode(dep_jwt, dep_key, algorithms=["ES256"])
                log_deployer_event("[VERIFICATION SUCCESS] Deployer Attestation verified under Deployer JWK.")
                print("    --- Deployer Attestation Claims ---")
                print(f"      iss (Issuer):               {decoded_dep.get('iss')}")
                print(f"      deployer_identifier:        {decoded_dep.get('deployer_identifier')}")
                print(f"      deployer_accountability_id: {decoded_dep.get('deployer_accountability_id')[:30]}...")
            except Exception as e:
                log_deployer_event(f"[VERIFICATION FAILED] Deployer Attestation signature verification failed: {str(e)}")

            # 4. Verify Agent Instance Binding
            try:
                unverified = jwt.decode(bind_jwt, options={"verify_signature": False})
                agent_pub_pem = unverified.get("agent_public_key")
                agent_key = serialization.load_pem_public_key(agent_pub_pem.encode('utf-8'))
                decoded_bind = jwt.decode(bind_jwt, agent_key, algorithms=["ES256"])
                log_deployer_event("[VERIFICATION SUCCESS] Agent Instance Binding verified under Agent public key.")
                print("    --- Agent Instance Binding Claims ---")
                print(f"      iss (Issuer):               {decoded_bind.get('iss')}")
                print(f"      sub (Subject):             {decoded_bind.get('sub')}")
                print(f"      agent_instance_identifier:  {decoded_bind.get('agent_instance_identifier')}")
                print(f"      agent_public_key (trunc):  {decoded_bind.get('agent_public_key')[:45].strip()}...")
            except Exception as e:
                log_deployer_event(f"[VERIFICATION FAILED] Agent Instance Binding signature verification failed: {str(e)}")

            # Demonstrate Audit Authority Decryption (available on demand)
            decrypt_url = "http://localhost:8004/api/audit/decrypt"
            decrypt_payload = {
                "ciphertext_base64": decoded_dep.get('deployer_accountability_id')
            }
            log_deployer_event(f"Sending HTTP POST request to Audit Service decrypt endpoint: {decrypt_url}. Header: Authorization='Bearer audit_secret_token'. Payload: ciphertext_base64 (JWE)='{decrypt_payload['ciphertext_base64'][:30]}...'")
            try:
                headers = {
                    "Authorization": "Bearer audit_secret_token"
                }
                decrypt_res = requests.post(decrypt_url, json=decrypt_payload, headers=headers, timeout=5)
                if decrypt_res.status_code == 200:
                    decrypted_name = decrypt_res.json().get("decrypted_value")
                    log_deployer_event(f"Audit Service responded with HTTP 200 OK. Response Payload: {decrypt_res.json()}")
                    log_deployer_event(f"[SUCCESS] Audit Authority decrypted accountability ID: {decrypted_name}")
                else:
                    log_deployer_event(f"[ERROR] Decryption failed. Status Code: HTTP {decrypt_res.status_code}. Response: {decrypt_res.text}")
            except Exception as e:
                log_deployer_event(f"[ERROR] Could not connect to Audit Service: {str(e)}")

        else:
            log_deployer_event("[WARNING] No Agent ID flat container returned from the server.")

    except requests.exceptions.RequestException as e:
        log_deployer_event(f"[ERROR] Connection failed: {str(e)}")
        sys.exit(1)

    time.sleep(1.0)
    log_deployer_event("Exact protocol flow simulation (Steps 0 to 5) completed.")
    
    # Wait a brief moment to let any final background server logs post to the aggregator
    time.sleep(1.0)
    
    # Print the unified chronological sequence
    print_unified_logs()

if __name__ == "__main__":
    main()
