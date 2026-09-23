from __future__ import annotations

import enum

from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthMode(str, enum.Enum):
    TEST = "test"
    SMS = "sms"
    EMAIL = "email"


class RunMode(str, enum.Enum):
    POLLING = "polling"
    WEBHOOK = "webhook"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    main_bot_token: str
    admin_telegram_ids: str = ""

    run_mode: RunMode = RunMode.POLLING
    webhook_base_url: str = ""
    webhook_listen_host: str = "0.0.0.0"
    webhook_listen_port: int = 8000
    main_bot_webhook_secret: str = ""
    # ربات بله‌پی برای پرداخت (اختیاری — اگه خالی بمونه، Bale Pay غیرفعال می‌مونه).
    # مشابهِ main_bot_token، چون یه Bot ثابته و موقعِ startup ساخته می‌شه، نه یه
    # چیزی که بدونِ ری‌استارت از پنلِ ادمین عوض بشه (برخلافِ bale_provider_token
    # که در AdminSettings ذخیره می‌شه، چون فقط یه پارامترِ per-request ـه).
    bale_bot_token: str = ""
    bale_webhook_secret: str = ""

    auth_mode: AuthMode = AuthMode.TEST

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_use_tls: bool = True

    encryption_key: str

    @property
    def admin_ids(self) -> set[int]:
        return {int(x.strip()) for x in self.admin_telegram_ids.split(",") if x.strip()}


settings = Settings()
