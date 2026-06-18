import os
import base64
import logging
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("AuditAuthorityService")

app = FastAPI(title="Agent ID Platform - Audit Authority Service")

KEY_FILE = "audit_key.pem"
AUDIT_SECRET_TOKEN = "audit_secret_token"  # Simulated API key for authorized auditors

def load_or_generate_key() -> rsa.RSAPrivateKey:
    """Loads an RSA private key from PEM file or generates a new one."""
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, "rb") as f:
            return serialization.load_pem_private_key(f.read(), password=None)
    
    logger.info("Audit Authority - Generating new cryptographic RSA key pair...")
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    with open(KEY_FILE, "wb") as f:
        f.write(pem)
        
    return private_key

# Load RSA keys
private_key = load_or_generate_key()
public_key = private_key.public_key()

class DecryptRequest(BaseModel):
    ciphertext_base64: str

@app.on_event("startup")
def on_startup():
    logger.info("Audit Authority Service started on port 8004.")

@app.get("/api/audit/public-key")
def get_public_key():
    """Returns Audit Authority public key as PEM string."""
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode("utf-8")
    return {"public_key_pem": public_pem}

@app.post("/api/audit/decrypt")
def decrypt_data(request: DecryptRequest, authorization: str = Header(None)):
    """Decrypts a JWE ciphertext using the Audit Authority private key if authorized."""
    # Authenticate the auditor (e.g. Bank or CLI simulation)
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header.")
    
    token = authorization.split(" ")[1]
    if token != AUDIT_SECRET_TOKEN:
        raise HTTPException(status_code=403, detail="Unauthorized access to audit decryption.")
    
    try:
        # Decode and decrypt ciphertext
        encrypted_bytes = base64.b64decode(request.ciphertext_base64)
        decrypted_bytes = private_key.decrypt(
            encrypted_bytes,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        decrypted_value = decrypted_bytes.decode("utf-8")
        logger.info("Audit Authority - Successfully decrypted sensitive claim.")
        return {"decrypted_value": decrypted_value}
    except Exception as e:
        logger.error(f"Audit Authority - Decryption failed: {str(e)}")
        raise HTTPException(status_code=400, detail="Failed to decrypt ciphertext. Invalid key or formatting.")
