import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

import signer

# Configure basic logging to console
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("AgentIdentityService")

app = FastAPI(title="Agent ID Platform - Agent Identity & Attestation Service")

class CallModelRequest(BaseModel):
    prompt: str
    receiving_service: str
    request_attestation: bool
    model: str

class ComposeIdentityRequest(BaseModel):
    agent_id: str
    agent_public_key: str
    deployer_identifier: str
    deployer_accountability_id: str
    developer_attestation: str

@app.on_event("startup")
def on_startup():
    logger.info("Provider - Agent Identity Service started on port 8002.")

@app.post("/api/identity/call-model")
def call_model(request: CallModelRequest):
    """
    Step 3 & 4: Receives a prompt and returns the action plan + Developer Attestation.
    """
    logger.info(f"Developer - Received LLM invocation request for model: {request.model}")
    try:
        # Generate the developer attestation signature if requested
        dev_attestation = None
        if request.request_attestation:
            dev_attestation = signer.create_developer_attestation(request.model)

        # Mock action plan matching the target Bank scenario
        action_plan = {
            "tool": "bank_api_call",
            "method": "transfer_funds",
            "arguments": { "recipient_account_type": "sender_owned" }
        }

        return {
            "action_plan": action_plan,
            "foundation_model_identifier": f"Commercial {request.model}_4.2",
            "developer_identifier": "LLM Developer XYZ",
            "foundation_model_safety_evidence": "LLMDevXYZ.org/commercial_modelname_4_2_safety_report",
            "developer_attestation": dev_attestation
        }
    except Exception as e:
        logger.error(f"Developer - Failed during Developer model call: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to invoke LLM model.")

@app.post("/api/identity/compose")
def compose_identity(request: ComposeIdentityRequest):
    """
    Step 5: Composes and signs the composite Agent ID JWT.
    Binds Developer claims, Deployer context, and the Agent's public key under the Provider's signature.
    """
    logger.info(f"Provider - Identity composition request received for Agent ID: {request.agent_id}")
    try:
        agent_id_jwt = signer.create_provider_attestation(
            agent_id=request.agent_id,
            agent_public_key=request.agent_public_key,
            deployer_identifier=request.deployer_identifier,
            deployer_accountability_id=request.deployer_accountability_id,
            developer_attestation=request.developer_attestation
        )
        return {
            "agent_id_jwt": agent_id_jwt
        }
    except Exception as e:
        logger.error(f"Provider - Failed to compose Agent ID JWT: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to compose cryptographic Agent ID.")

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
