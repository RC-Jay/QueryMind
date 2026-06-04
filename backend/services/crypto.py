"""Fernet symmetric encryption for secrets stored at rest (DB URL, API keys)."""
from cryptography.fernet import Fernet
from config import get_settings


def _fernet() -> Fernet:
    return Fernet(get_settings().config_encryption_key.encode())


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()


def mask(token: str, visible: int = 4) -> str:
    """Decrypt and return only the last `visible` chars, for safe display."""
    try:
        secret = decrypt(token)
    except Exception:
        return "****"
    if len(secret) <= visible:
        return "****"
    return "…" + secret[-visible:]
