from __future__ import annotations

from cryptography.fernet import Fernet

from app.config import settings

_fernet = Fernet(settings.encryption_key.encode())


def encrypt_token(raw_token: str) -> str:
    return _fernet.encrypt(raw_token.encode()).decode()


def decrypt_token(encrypted_token: str) -> str:
    return _fernet.decrypt(encrypted_token.encode()).decode()
