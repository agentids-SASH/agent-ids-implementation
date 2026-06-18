from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from typing import Tuple

def generate_ec_key_pair() -> Tuple[ec.EllipticCurvePrivateKey, str]:
    """
    Generates a new Elliptic Curve P-256 key pair.
    Returns the Private Key object and the serialized Public Key in PEM format.
    """
    private_key = ec.generate_private_key(ec.SECP256R1())
    
    # Serialize the public key to PEM format
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode("utf-8")
    
    return private_key, public_pem
