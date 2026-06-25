import os
import base64
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes

from logger_utils import log_event

app = FastAPI(title="Agent ID Platform - Audit Authority Service")

KEY_FILE = "audit_key.pem"
AUDIT_SECRET_TOKEN = "audit_secret_token"  # Simulated API key for authorized auditors

def load_or_generate_key() -> rsa.RSAPrivateKey:
    """Loads an RSA private key from PEM file or generates a new one."""
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, "rb") as f:
            return serialization.load_pem_private_key(f.read(), password=None)
    
    log_event("Audit", "Generating new cryptographic RSA key pair...")
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
    log_event("Audit", "Audit Authority Service started on port 8004.")

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
    log_event("Audit", f"Audit Authority received decryption request. Input Payload: ciphertext_base64 (JWE)='{request.ciphertext_base64[:30]}...'")
    
    # Authenticate the auditor (e.g. Bank or CLI simulation)
    if not authorization or not authorization.startswith("Bearer "):
        log_event("Audit", "Decryption failed. HTTP 401 Unauthorized: Missing or malformed Authorization header.")
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header.")
    
    token = authorization.split(" ")[1]
    if token != AUDIT_SECRET_TOKEN:
        log_event("Audit", "Decryption failed. HTTP 403 Forbidden: Unauthorized access token.")
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
        log_event("Audit", f"Successfully decrypted sensitive claim using RSA-OAEP with SHA-256 padding. Decrypted Value: '{decrypted_value}'")
        
        response_payload = {"decrypted_value": decrypted_value}
        log_event("Audit", f"Audit Authority returning HTTP 200 OK. Response Payload: {response_payload}")
        return response_payload
    except Exception as e:
        log_event("Audit", f"Decryption failed using RSA-OAEP-256 (Error: {str(e)})")
        raise HTTPException(status_code=400, detail="Failed to decrypt ciphertext. Invalid key or formatting.")
