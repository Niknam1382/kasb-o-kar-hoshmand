"""سرویسِ پیامکِ احرازِ هویت (کاوه‌نگار) — P18 · A3.

کلیدِ API، شماره‌یِ فرستنده و نامِ قالب از پنلِ ادمین می‌آیند (کلید رمزنگاری‌شده ذخیره می‌شود).
`AdminSettings.sms_enabled` صریح روشن/خاموش می‌کند؛ خاموش بودنش یعنی همان مسیرِ بدونِ پیامکِ امروز،
پس ثبت‌نام هیچ‌وقت به سرویسِ پیامک وابسته نمی‌ماند.

نکته‌یِ امنیتی: آدرسِ درخواستِ کاوه‌نگار خودش کلیدِ API را در path دارد، پس هیچ‌جا — نه در پیامِ
استثنا، نه در لاگ — متنِ خامِ exceptionِ شبکه‌ای منتقل نمی‌شود. فقط نوعِ خطا و کدِ وضعیت می‌آید.
"""
from __future__ import annotations

import abc
import logging

import aiohttp

logger = logging.getLogger(__name__)

KAVENEGAR_BASE_URL = "https://api.kavenegar.com/v1"
DEFAULT_OTP_TEMPLATE = "registerotp"
REQUEST_TIMEOUT_SECONDS = 15
_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


class SmsServiceError(Exception):
    """دلیلِ فارسی و بدونِ هیچ رازِ فنی — قابلِ نشان‌دادن به ادمین."""


class BaseSmsService(abc.ABC):
    @abc.abstractmethod
    async def send_otp(self, phone_number: str, code: str) -> str:
        """وضعیتِ provider را برمی‌گرداند؛ خطا ⇒ `SmsServiceError`."""


class KavenegarSmsService(BaseSmsService):
    def __init__(self, api_key: str, sender: str | None = None, template: str | None = None) -> None:
        self.api_key = api_key
        self.sender = normalize_sender_digits(sender)
        self.template = (template or "").strip() or DEFAULT_OTP_TEMPLATE

    async def send_otp(self, phone_number: str, code: str) -> str:
        url = f"{KAVENEGAR_BASE_URL}/{self.api_key}/verify/lookup.json"
        params: dict[str, str] = {"receptor": phone_number, "token": code, "template": self.template}
        if self.sender:
            params["sender"] = self.sender
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)) as http:
                async with http.get(url, params=params) as resp:
                    status = resp.status
                    payload = await _safe_json(resp)
        except aiohttp.ClientError as exc:
            raise SmsServiceError(f"ارتباطِ شبکه‌ای با سرویسِ پیامک برقرار نشد ({type(exc).__name__}).") from exc
        except Exception as exc:  # noqa: BLE001 — پاسخِ غیرمنتظره هم نباید ثبت‌نام را بشکند
            raise SmsServiceError(f"پاسخِ سرویسِ پیامک قابلِ پردازش نبود ({type(exc).__name__}).") from exc

        provider_status = str((payload or {}).get("return", {}).get("status") or status)
        if status != 200 or not provider_status.startswith("2"):
            raise SmsServiceError(f"سرویسِ پیامک خطا داد (HTTP {status}، وضعیتِ {provider_status}).")
        return provider_status


async def _safe_json(resp: aiohttp.ClientResponse) -> dict | None:
    try:
        data = await resp.json()
    except Exception:  # noqa: BLE001 — بدنه‌یِ غیرJSON هم یک شکستِ عادی است، نه کرش
        return None
    return data if isinstance(data, dict) else None


def normalize_sender_digits(raw: str | None) -> str | None:
    """ارقامِ فارسی/عربی ← لاتین؛ فاصله و خط‌تیره حذف، + اولِ خط می‌ماند."""
    if not raw:
        return None
    return raw.strip().translate(_DIGITS).replace(" ", "").replace("-", "") or None


def get_sms_service(api_key: str, sender: str | None = None, template: str | None = None) -> BaseSmsService:
    return KavenegarSmsService(api_key, sender=sender, template=template)
