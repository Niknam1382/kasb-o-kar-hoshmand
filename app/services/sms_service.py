from __future__ import annotations

import abc

import aiohttp


class SmsServiceError(Exception):
    pass


class BaseSmsService(abc.ABC):
    @abc.abstractmethod
    async def send_otp(self, phone_number: str, code: str) -> None: ...


class KavenegarSmsService(BaseSmsService):
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    async def send_otp(self, phone_number: str, code: str) -> None:
        url = f"https://api.kavenegar.com/v1/{self.api_key}/verify/lookup.json"
        params = {"receptor": phone_number, "token": code, "template": "registerotp"}
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as http:
                async with http.get(url, params=params) as resp:
                    data = await resp.json()
        except Exception as exc:
            raise SmsServiceError(f"ارسال پیامک ناموفق بود: {exc}") from exc

        if data.get("return", {}).get("status") != 200:
            raise SmsServiceError(f"کاوه‌نگار خطا برگردوند: {data}")


def get_sms_service(api_key: str) -> BaseSmsService:
    return KavenegarSmsService(api_key)
