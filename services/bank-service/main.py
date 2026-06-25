import base64
import requests
import jwt
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization

import database
from logger_utils import log_event

app = FastAPI(title="Agent ID Platform - Bank Service")

class TransferRequest(BaseModel):
    amount: float
    from_account: str
    to_account: str
    agent_id_jwt: dict  # The flat JSON representation container containing 4 tokens

@app.on_event("startup")
def on_startup():
    database.init_db()
    log_event("Bank", "Bank Service started on port 8003. Initialized accounts database.")

def get_key_from_jwks(keys: list, kid: str) -> ec.EllipticCurvePublicKey:
    """Reconstructs the public key for kid from a list of JWKs."""
    for key in keys:
        if key.get("kid") == kid:
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
            
    raise HTTPException(status_code=400, detail=f"Key with kid '{kid}' not found in JWKS.")

@app.post("/api/bank/transfer")
def transfer_funds(request: TransferRequest):
    """
    Relying Party endpoint: Verifies all 4 peer-level independent tokens in the Agent ID
    and performs the transaction if validations pass.
    """
    log_event("Bank", f"Received transfer request: Transfer {request.amount:.2f} USD from '{request.from_account}' to '{request.to_account}'.")
    
    # 1. Extract the tokens
    dev_jwt = request.agent_id_jwt.get("developer_attestation")
    prov_jwt = request.agent_id_jwt.get("provider_attestation")
    dep_jwt = request.agent_id_jwt.get("deployer_attestation")
    bind_jwt = request.agent_id_jwt.get("agent_instance_binding")
    
    if not all([dev_jwt, prov_jwt, dep_jwt, bind_jwt]):
        log_event("Bank", "Validation failed: Missing one or more tokens in the Agent ID container.")
        raise HTTPException(status_code=400, detail="Invalid Agent ID: flat container must contain developer_attestation, provider_attestation, deployer_attestation, and agent_instance_binding.")
    
    # Resolve JWKS from Identity Service (using 127.0.0.1 to avoid Windows localhost delay)
    jwks_url = "http://127.0.0.1:8002/.well-known/jwks.json"
    log_event("Bank", f"Resolving public keys from Identity Service JWKS endpoint: {jwks_url}")
    try:
        res = requests.get(jwks_url, timeout=5)
        if res.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Failed to fetch JWKS from Identity Service: HTTP {res.status_code}")
        jwks_keys = res.json().get("keys", [])
    except Exception as e:
        log_event("Bank", f"Failed to connect to JWKS endpoint: {str(e)}")
        raise HTTPException(status_code=502, detail=f"Failed to connect to Identity Service: {str(e)}")
    
    # 2. Cryptographic Signature Verifications
    try:
        # 2a. Verify Developer Attestation
        log_event("Bank", "Verifying Developer Attestation signature...")
        dev_key = get_key_from_jwks(jwks_keys, "developer-key-1")
        dev_claims = jwt.decode(dev_jwt, dev_key, algorithms=["ES256"])
        log_event("Bank", f"[VERIFICATION SUCCESS] Developer Attestation verified. (Issuer: {dev_claims.get('iss')}, Model: {dev_claims.get('foundation_model_identifier')})")
        
        # 2b. Verify Provider Attestation
        log_event("Bank", "Verifying Provider Attestation signature...")
        prov_key = get_key_from_jwks(jwks_keys, "provider-key-1")
        prov_claims = jwt.decode(prov_jwt, prov_key, algorithms=["ES256"])
        log_event("Bank", f"[VERIFICATION SUCCESS] Provider Attestation verified. (Issuer: {prov_claims.get('iss')}, Workload ID: {prov_claims.get('agent_instance_identifier')})")
        
        # 2c. Verify Deployer Attestation
        log_event("Bank", "Verifying Deployer Attestation signature...")
        dep_key = get_key_from_jwks(jwks_keys, "deployer-key-1")
        dep_claims = jwt.decode(dep_jwt, dep_key, algorithms=["ES256"])
        log_event("Bank", f"[VERIFICATION SUCCESS] Deployer Attestation verified. (Issuer: {dep_claims.get('iss')}, Deployer ID: {dep_claims.get('deployer_identifier')})")
        
        # 2d. Verify Agent Instance Binding using embedded ephemeral key
        log_event("Bank", "Verifying Agent Instance Binding signature using embedded ephemeral key...")
        unverified_claims = jwt.decode(bind_jwt, options={"verify_signature": False})
        agent_pub_pem = unverified_claims.get("agent_public_key")
        if not agent_pub_pem:
            raise HTTPException(status_code=400, detail="Missing agent_public_key inside Agent Instance Binding claims.")
        
        agent_pub_key = serialization.load_pem_public_key(agent_pub_pem.encode('utf-8'))
        bind_claims = jwt.decode(bind_jwt, agent_pub_key, algorithms=["ES256"])
        log_event("Bank", f"[VERIFICATION SUCCESS] Agent Instance Binding verified. (Issuer/Subject: {bind_claims.get('sub')})")
        
    except jwt.PyJWTError as e:
        log_event("Bank", f"Cryptographic validation failed: {str(e)}")
        raise HTTPException(status_code=400, detail=f"JWT Signature Verification Failed: {str(e)}")
    except Exception as e:
        log_event("Bank", f"Unexpected validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Validation Failed: {str(e)}")

    # 3. Claims Binding Verification
    log_event("Bank", "Verifying binding claims consistency between attestations...")
    bind_instance_id = bind_claims.get("agent_instance_identifier")
    prov_instance_id = prov_claims.get("agent_instance_identifier")
    
    if bind_instance_id != prov_instance_id:
        log_event("Bank", f"Claims Binding Failed: Agent Instance Binding ID ('{bind_instance_id}') does not match Provider Attestation Workload ID ('{prov_instance_id}').")
        raise HTTPException(status_code=400, detail="Claims Binding Failed: agent_instance_identifier mismatch between binding and provider attestation.")
    
    log_event("Bank", "Binding claims verified successfully. Agent ID validated.")
    
    # 4. Check balances and execute transfer
    current_from_balance = database.get_balance(request.from_account)
    current_to_balance = database.get_balance(request.to_account)
    
    log_event("Bank", f"Pre-transfer balances: checking = ${current_from_balance:.2f}, savings = ${current_to_balance:.2f}")
    
    success = database.update_balances(request.from_account, request.to_account, request.amount)
    if not success:
        log_event("Bank", f"Transaction rejected: Insufficient funds or invalid accounts.")
        raise HTTPException(status_code=400, detail="Transaction rejected: Insufficient funds or invalid account names.")
        
    new_from_balance = database.get_balance(request.from_account)
    new_to_balance = database.get_balance(request.to_account)
    
    log_event("Bank", f"Transfer executed successfully! Post-transfer balances: checking = ${new_from_balance:.2f}, savings = ${new_to_balance:.2f}")
    
    return {
        "status": "success",
        "message": f"Successfully transferred {request.amount:.2f} USD from {request.from_account} to {request.to_account}.",
        "balances": {
            request.from_account: new_from_balance,
            request.to_account: new_to_balance
        }
    }
