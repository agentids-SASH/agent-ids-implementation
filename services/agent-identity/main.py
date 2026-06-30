from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import jwt

import signer
from logger_utils import log_event

app = FastAPI(title="Agent ID Platform - Agent Identity & Attestation Service")

class CallModelRequest(BaseModel):
    prompt: str
    receiving_service: str
    request_attestation: bool
    model: str
    parent_token_hash: str = None

class ComposeIdentityRequest(BaseModel):
    agent_id: str
    parent_token_hash: str = None

@app.on_event("startup")
def on_startup():
    log_event("Provider", "Agent Identity Service started on port 8002.")

@app.get("/.well-known/jwks.json")
def get_jwks():
    """Exposes the JWK Set containing public keys for Developer and Provider."""
    return signer.get_jwks()

@app.post("/api/identity/call-model")
def call_model(request: CallModelRequest):
    """
    Step 3 & 4: Receives a prompt and returns the action plan + Developer Attestation.
    """
    log_event("Developer", f"Received LLM invocation request. Input Payload: prompt='{request.prompt}', receiving_service='{request.receiving_service}', request_attestation={request.request_attestation}, model='{request.model}', parent_token_hash='{request.parent_token_hash}'")
    try:
        # Generate the developer attestation signature if requested
        dev_attestation = None
        if request.request_attestation:
            dev_attestation = signer.create_developer_attestation(
                model_name=request.model,
                parent_token_hash=request.parent_token_hash
            )

        # Mock action plan matching the target Bank scenario
        action_plan = {
            "tool": "bank_api_call",
            "method": "transfer_funds",
            "arguments": { "recipient_account_type": "sender_owned" }
        }

        response_payload = {
            "action_plan": action_plan,
            "foundation_model_identifier": f"Commercial {request.model}_4.2",
            "developer_identifier": "LLM Developer XYZ",
            "foundation_model_safety_evidence": "LLMDevXYZ.org/commercial_modelname_4_2_safety_report",
            "developer_attestation": dev_attestation
        }
        log_event("Developer", f"LLM Developer returning safety attestation. HTTP 200 OK. Response Payload: model_id='{response_payload['foundation_model_identifier']}', developer_attestation (JWT)='{response_payload['developer_attestation'][:30]}...' (Signed using ES256 with Developer Private Key)")
        return response_payload
    except Exception as e:
        log_event("Developer", f"Failed during Developer model call: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to invoke LLM model.")

@app.post("/api/identity/compose")
def compose_identity(request: ComposeIdentityRequest):
    """
    Step 5: Composes and signs the Provider Attestation JWT.
    """
    log_event("Provider", f"Provider Attestation request received. Input Payload: agent_id='{request.agent_id}', parent_token_hash='{request.parent_token_hash}'")
    try:
        provider_attestation = signer.create_provider_attestation(
            agent_id=request.agent_id,
            parent_token_hash=request.parent_token_hash
        )

        # Decode and log the Provider Attestation JWT claims
        claims = jwt.decode(provider_attestation, options={"verify_signature": False})
        log_event("Provider", f"Token Inspection - Composed Provider Attestation Claims: iss='{claims.get('iss')}', sub='{claims.get('sub')}', agent_instance_identifier='{claims.get('agent_instance_identifier')}', shutdown_cmd='{claims.get('agent_instance_shutdown_command')}', parent_token_hash='{claims.get('parent_token_hash')}'")

        response_payload = {
            "provider_attestation": provider_attestation
        }
        log_event("Provider", f"Provider returning Provider Attestation JWT. HTTP 200 OK. Response Payload: provider_attestation='{provider_attestation[:30]}...' (Signed using ES256 with Provider Private Key)")
        return response_payload
    except Exception as e:
        log_event("Provider", f"Failed to compose Provider Attestation: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to compose cryptographic Provider Attestation.")

@app.get("/api/identity/public-keys")
def get_public_keys():
    """
    Exposes public keys of the Developer and Provider.
    External services (like target banks) will call this to verify the JWT signatures.
    """
    return {
        "developer_public_key_pem": signer.get_developer_public_key_pem(),
        "provider_public_key_pem": signer.get_provider_public_key_pem()
    }
