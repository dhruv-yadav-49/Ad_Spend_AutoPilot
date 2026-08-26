from cryptography.fernet import Fernet
from .config import settings
import base64

def _get_cipher() -> Fernet:
    """Returns the Fernet cipher configured with the environment key."""
    # Ensure it's a valid fernet key length (32 url-safe base64-encoded bytes)
    # The config check already ensures it exists. We assume it's correctly formatted as 32-bytes base64, otherwise Fernet will raise an error here.
    return Fernet(settings.CREDENTIAL_ENCRYPTION_KEY.encode('utf-8'))

def encrypt_token(plain_token: str) -> str:
    """Encrypts a plaintext OAuth token and returns a base64 encoded string."""
    if not plain_token:
        return ""
    cipher = _get_cipher()
    encrypted_bytes = cipher.encrypt(plain_token.encode('utf-8'))
    return encrypted_bytes.decode('utf-8')

def decrypt_token(encrypted_token: str) -> str:
    """Decrypts an encrypted OAuth token string back to plaintext."""
    if not encrypted_token:
        return ""
    cipher = _get_cipher()
    decrypted_bytes = cipher.decrypt(encrypted_token.encode('utf-8'))
    return decrypted_bytes.decode('utf-8')
