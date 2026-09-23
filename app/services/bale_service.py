from __future__ import annotations

import aiohttp

# =============================================================================
# نکته‌ی مهم درباره‌ی این فایل — لطفاً قبل از فعال‌کردنِ Bale Pay در production
# بخونید (جزئیاتِ کامل‌تر در docs/changelog-phase1a-recovery.md):
#
# ‏API بله (bot API) بر پایه‌ی همون طرحِ Telegram Bot API ـه (chat_id، sendInvoice،
# pre_checkout_query، successful_payment، …) و این بخش‌ها مستقیم از
# docs.bale.ai تایید شدن. ولی متدِ createInvoiceLink که این فایل ازش استفاده
# می‌کنه (تا نیازی به chat_idِ از قبل‌ثبت‌شده نباشه و بشه به مشتریِ تلگرامی یه
# لینکِ قابل‌کلیک داد) در مستنداتِ عمومیِ docs.bale.ai پیدا نشد — نه در این
# جلسه، نه در جلسه‌ی چتِ قبلی وقتی مستقیم چک شده بود. طبقِ فایلی که کاربر
# فرستاد پیاده‌سازی شده، ولی **تاییدنشده** ـست. حتماً قبل از production با یه
# تراکنشِ واقعیِ کوچیک تستش کنید و اگه پاسخِ واقعیِ بله با چیزی که اینجا فرض
# شده فرق داشت، فقط همین فایل کافیه که اصلاح بشه (بقیه‌ی سیستم بهش وابسته
# نیست).
# =============================================================================

API_BASE = "https://tapi.bale.ir/bot{token}/{method}"


class BaleError(Exception):
    pass


async def _call(bot_token: str, method: str, payload: dict) -> dict:
    url = API_BASE.format(token=bot_token, method=method)
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as http:
            async with http.post(url, json=payload) as resp:
                data = await resp.json()
    except Exception as exc:
        raise BaleError(f"ارتباط با بله برقرار نشد ({method}): {exc}") from exc

    if not data.get("ok", False):
        raise BaleError(f"درخواستِ {method} به بله ناموفق بود: {data.get('description') or data}")
    return data.get("result")


async def create_invoice_link(
    bot_token: str,
    provider_token: str,
    title: str,
    description: str,
    payload: str,
    amount_rial: int,
) -> str:
    """
    یه لینکِ پرداخت می‌سازه که کاربر می‌تونه توی مرورگر یا اپِ بله بازش کنه —
    نیازی به chat_idِ از قبل نیست. amount_rial باید به ریال باشه (نه تومان).
    """
    body = {
        "title": title[:32],
        "description": description[:255],
        "payload": payload,
        "provider_token": provider_token,
        "currency": "IRR",
        "prices": [{"label": title[:32], "amount": amount_rial}],
    }
    result = await _call(bot_token, "createInvoiceLink", body)
    if not isinstance(result, str) or not result:
        raise BaleError(f"پاسخِ createInvoiceLink فرمتِ منتظره رو نداشت: {result!r}")
    return result


async def answer_pre_checkout_query(
    bot_token: str, pre_checkout_query_id: str, ok: bool, error_message: str | None = None
) -> None:
    body: dict = {"pre_checkout_query_id": pre_checkout_query_id, "ok": ok}
    if not ok and error_message:
        body["error_message"] = error_message
    await _call(bot_token, "answerPreCheckoutQuery", body)


async def inquire_transaction(bot_token: str, transaction_id: str) -> dict:
    """
    استعلامِ نهاییِ وضعیتِ تراکنش از خودِ سرورِ بله — همیشه قبل از اعتبارکردنِ
    کیف‌پول این رو صدا می‌زنیم، حتی اگه successful_payment از وب‌هوک رسیده
    باشه، تا یه وب‌هوکِ جعلی نتونه کیف‌پول رو شارژ کنه.
    """
    return await _call(bot_token, "inquireTransaction", {"transaction_id": transaction_id})


async def set_webhook(bot_token: str, url: str, secret_token: str | None) -> None:
    body: dict = {"url": url, "drop_pending_updates": True}
    if secret_token:
        body["secret_token"] = secret_token
    await _call(bot_token, "setWebhook", body)
