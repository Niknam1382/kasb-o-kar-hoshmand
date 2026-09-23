from __future__ import annotations

import aiohttp

REQUEST_URL = "https://payment.zarinpal.com/pg/v4/payment/request.json"
VERIFY_URL = "https://payment.zarinpal.com/pg/v4/payment/verify.json"
START_PAY_URL = "https://www.zarinpal.com/pg/StartPay/{authority}"


class ZarinpalError(Exception):
    pass


async def request_payment(merchant_id: str, amount_toman: int, callback_url: str, description: str) -> tuple[str, str]:
    payload = {
        "merchant_id": merchant_id,
        "currency": "IRT",
        "amount": amount_toman,
        "callback_url": callback_url,
        "description": description,
    }
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as http:
            async with http.post(REQUEST_URL, json=payload) as resp:
                data = await resp.json()
    except Exception as exc:
        raise ZarinpalError(f"ارتباط با زرین‌پال برقرار نشد: {exc}") from exc

    result = data.get("data") or {}
    if result.get("code") != 100:
        raise ZarinpalError(f"درخواست پرداخت زرین‌پال ناموفق بود: {data.get('errors') or result}")

    authority = result["authority"]
    return authority, START_PAY_URL.format(authority=authority)


async def verify_payment(merchant_id: str, amount_toman: int, authority: str) -> str:
    payload = {"merchant_id": merchant_id, "amount": amount_toman, "currency": "IRT", "authority": authority}
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as http:
            async with http.post(VERIFY_URL, json=payload) as resp:
                data = await resp.json()
    except Exception as exc:
        raise ZarinpalError(f"ارتباط با زرین‌پال برقرار نشد: {exc}") from exc

    result = data.get("data") or {}
    if result.get("code") not in (100, 101):
        raise ZarinpalError(f"تایید پرداخت زرین‌پال ناموفق بود: {data.get('errors') or result}")

    return str(result.get("ref_id", ""))
