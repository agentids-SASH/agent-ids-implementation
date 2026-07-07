import os
import jwt
import logging
import base64
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from logger_utils import log_event

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("SignerUtils")

SIGNER_DIR = os.path.dirname(os.path.abspath(__file__))
DEV_KEY_FILE = os.path.join(SIGNER_DIR, "developer_key.pem")
PROV_KEY_FILE = os.path.join(SIGNER_DIR, "provider_key.pem")

import uuid
import time

def load_or_generate_key(filepath: str) -> ec.EllipticCurvePrivateKey:
    """Loads an Elliptic Curve private key from PEM file or generates a new one."""
    if os.path.exists(filepath):
        with open(filepath, "rb") as f:
            return serialization.load_pem_private_key(f.read(), password=None)
    
    # Generate new P-256 EC key
    log_event("Provider", f"Identity Service - Generating new cryptographic Elliptic Curve key pair (P-256 / SECP256R1) at {filepath}...")
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

DEPLOYER_PUB_KEY_FILE = os.path.join(SIGNER_DIR, "deployer_public_key.pem")

def load_deployer_public_key() -> ec.EllipticCurvePublicKey:
    """Loads Deployer's public key from file if it exists."""
    if os.path.exists(DEPLOYER_PUB_KEY_FILE):
        try:
            with open(DEPLOYER_PUB_KEY_FILE, "rb") as f:
                return serialization.load_pem_public_key(f.read())
        except Exception as e:
            log_event("Provider", f"Failed to load deployer public key from file: {str(e)}")
    return None

def get_jwk_from_public_key(public_key: ec.EllipticCurvePublicKey, kid: str) -> dict:
    """Serializes the public key into RFC 7517 JWK format."""
    numbers = public_key.public_numbers()
    
    def b64url(val: int) -> str:
        # Convert integer to bytes, then base64url-encode
        size = (val.bit_length() + 7) // 8
        octets = val.to_bytes(size, byteorder='big')
        return base64.urlsafe_b64encode(octets).rstrip(b'=').decode('utf-8')
    
    return {
        "kty": "EC",
        "crv": "P-256",
        "x": b64url(numbers.x),
        "y": b64url(numbers.y),
        "kid": kid
    }

def get_jwks() -> dict:
    """Returns the JWK Set containing public keys for Developer, Provider, and Deployer."""
    keys = [
        get_jwk_from_public_key(developer_key.public_key(), "developer-key-1"),
        get_jwk_from_public_key(provider_key.public_key(), "provider-key-1")
    ]
    dep_pub_key = load_deployer_public_key()
    if dep_pub_key:
        keys.append(get_jwk_from_public_key(dep_pub_key, "deployer-key-1"))
    return {
        "keys": keys
    }

def create_developer_attestation(model_name: str, parent_token_hash: str = None) -> str:
    """
    Step 4: LLM Developer signs the foundation model details, safety evidence, and Deployer hash.
    """
    payload = {
        "iss": "LLM Developer XYZ",
        "developer_identifier": "LLM Developer XYZ",
        "foundation_model_identifier": f"Commercial {model_name}_4.2",
        "foundation_model_safety_evidence": "LLMDevXYZ.org/commercial_modelname_4_2_safety_report"
    }
    if parent_token_hash:
        payload["parent_token_hash"] = parent_token_hash

    # Sign developer attestation with Developer private key
    token = jwt.encode(payload, developer_key, algorithm="ES256")
    log_event("Developer", f"LLM Developer - Created Developer Attestation JWT for model: {model_name} (Signed using ES256 with Developer private key)")
    return token

def create_provider_attestation(agent_id: str, parent_token_hash: str = None) -> str:
    """
    Step 5: Provider signs compute environment claims and Developer hash.
    """
    spiffe_id = f"spiffe://provider.net/agent/worker-{agent_id}"
    payload = {
        "iss": "provider #202",
        "provider_identifier": "provider #202",
        "sub": spiffe_id,
        "agent_instance_identifier": spiffe_id,
        "provider_security_evidence": f"provider.net/security_evidence/agent_instance_{agent_id}",
        "agent_instance_shutdown_command": "agent_instance_shutdown code: 5559"
    }
    if parent_token_hash:
        payload["parent_token_hash"] = parent_token_hash

    # Sign provider attestation with Provider private key
    agent_id_token = jwt.encode(payload, provider_key, algorithm="ES256")
    log_event("Provider", f"Provider - Created Provider Attestation JWT for agent: {agent_id} (Signed using ES256 with Provider private key)")
    return agent_id_token
