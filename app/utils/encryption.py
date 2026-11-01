from __future__ import annotations

from cryptography.fernet import Fernet

from app.config import settings

_fernet = Fernet(settings.encryption_key.encode())


def encrypt_token(raw_token: str) -> str:
    return _fernet.encrypt(raw_token.encode()).decode()


def decrypt_token(encrypted_token: str) -> str:
    return _fernet.decrypt(encrypted_token.encode()).decode()


def looks_encrypted(value: str | None) -> bool:
    """True اگر مقدارِ ذخیره‌شده رمزِ Fernet باشد (پیشوندِ نسخه‌یِ Fernet `gAAAAA` است).

    برایِ مسیرهایِ «بازنویسیِ یک‌باره» لازم است: ستون‌هایی که به `EncryptedToken` منتقل شده‌اند
    داده‌هایِ قدیمیِ *رمزنشده* را هم می‌پذیرند، پس باید بتوان تشخیص داد کدام ردیف هنوز
    خام است و باید دوباره نوشته شود.
    """
    return bool(value) and value.startswith("gAAAAA")
