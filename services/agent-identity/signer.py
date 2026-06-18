import os
import jwt
import logging
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("SignerUtils")

DEV_KEY_FILE = "developer_key.pem"
PROV_KEY_FILE = "provider_key.pem"

def load_or_generate_key(filepath: str) -> ec.EllipticCurvePrivateKey:
    """Loads an Elliptic Curve private key from PEM file or generates a new one."""
    if os.path.exists(filepath):
        with open(filepath, "rb") as f:
            return serialization.load_pem_private_key(f.read(), password=None)
    
    # Generate new P-256 EC key
    logger.info(f"Identity Service - Generating new cryptographic key at {filepath}...")
    private_key = ec.generate_private_key(ec.SECP256R1())
    
    # Save key to file
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    with open(filepath, "wb") as f:
        f.write(pem)
        
    return private_key

# Load Developer and Provider keys
developer_key = load_or_generate_key(DEV_KEY_FILE)
provider_key = load_or_generate_key(PROV_KEY_FILE)

def get_developer_public_key_pem() -> str:
    """Returns Developer's public key as PEM string."""
    return developer_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode("utf-8")

def get_provider_public_key_pem() -> str:
    """Returns Provider's public key as PEM string."""
    return provider_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode("utf-8")

def create_developer_attestation(model_name: str) -> str:
    """
    Step 4: LLM Developer signs the foundation model details and safety evidence.
    """
    payload = {
        "iss": "LLM Developer XYZ",
        "foundation_model_identifier": f"Commercial {model_name}_4.2",
        "foundation_model_safety_evidence": "LLMDevXYZ.org/commercial_modelname_4_2_safety_report"
    }
    # Sign developer attestation with Developer private key
    token = jwt.encode(payload, developer_key, algorithm="ES256")
    logger.info(f"Developer - Created Developer Attestation JWT for model: {model_name}")
    return token

def create_provider_attestation(
    agent_id: str,
    agent_public_key: str,
    deployer_identifier: str,
    deployer_accountability_id: str,
    developer_attestation: str
) -> str:
    """
    Step 5: Provider wraps the pre-signed Developer Attestation, Deployer identity elements,
    and binds them to the Agent's public key. Signs with Provider private key.
    """
    # Build Provider Attestation payload (Step 5)
    payload = {
        "iss": "provider #202",
        "sub": f"agent_instance_{agent_id}",
        "provider_security_evidence": f"provider.net/security_evidence/agent_instance_{agent_id}",
        "agent_instance_identifier": f"agent_instance #{agent_id[:8]}", # Using shortened ID as friendly identifier
        "agent_instance_shutdown_command": "agent_instance_shutdown code: 5559",
        
        # Deployer identity context bound to the token
        "deployer_identifier": deployer_identifier,
        "deployer_accountability_id": deployer_accountability_id,
        "signed_attestations": "nested signed attestations",

        # Cryptographically bind the Agent's public key
        "agent_public_key": agent_public_key,

        # Nest the pre-signed Developer Attestation
        "developer_attestation": developer_attestation
    }

    # Sign composite Agent ID with Provider private key
    agent_id_token = jwt.encode(payload, provider_key, algorithm="ES256")
    logger.info(f"Provider - Created composite Agent ID JWT for agent: {agent_id}")
    return agent_id_token
