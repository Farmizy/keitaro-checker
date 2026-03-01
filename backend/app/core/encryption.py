from functools import lru_cache

from cryptography.fernet import Fernet

from app.config import settings


@lru_cache(maxsize=1)
def _get_fernet() -> Fernet:
    return Fernet(settings.encryption_key.encode())


def encrypt(value: str) -> str:
    """Encrypt a string value. Returns base64-encoded ciphertext."""
    return _get_fernet().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    """Decrypt a base64-encoded ciphertext. Returns original string."""
    return _get_fernet().decrypt(value.encode()).decode()
