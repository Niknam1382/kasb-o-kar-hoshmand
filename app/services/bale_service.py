from __future__ import annotations

import aiohttp

from app.config import settings

# =============================================================================
# نکته‌ی مهم درباره‌ی این فایل — لطفاً قبل از فعال‌کردنِ Bale Pay در production
# بخونید (جزئیاتِ کامل‌تر در docs/changelog-phase1a-recovery.md):
#
# ‏API بله (bot API) بر پایه‌ی همون طرحِ Telegram Bot API ـه (chat_id، sendInvoice،
# pre_checkout_query، successful_payment، …) و این بخش‌ها مستقیم از
# docs.bale.ir تایید شدن. ولی متدِ createInvoiceLink که این فایل ازش استفاده
# می‌کنه (تا نیازی به chat_idِ از قبل‌ثبت‌شده نباشه و بشه به مشتریِ تلگرامی یه
# لینکِ قابل‌کلیک داد) در مستنداتِ عمومیِ docs.bale.ir پیدا نشد — نه در این
# جلسه، نه در جلسه‌ی چتِ قبلی وقتی مستقیم چک شده بود. طبقِ فایلی که کاربر
# فرستاد پیاده‌سازی شده، ولی **تاییدنشده** ـست. حتماً قبل از production با یه
# تراکنشِ واقعیِ کوچیک تستش کنید و اگه پاسخِ واقعیِ بله با چیزی که اینجا فرض
# شده فرق داشت، فقط همین فایل کافیه که اصلاح بشه (بقیه‌ی سیستم بهش وابسته
# نیست).
#
# به‌روزرسانیِ فازِ ۳ (۲۰۲۶-۰۹-۲۷): این توابعِ همین فایل حالا برایِ **دو**
# مصرفِ کاملاً جدا صدا زده می‌شن: (۱) پرداختِ فروشگاه‌دار به پلتفرم
# (شارژِ کیف‌پول/تمدیدِ اشتراک — panel.py، با admin_settings.bale_provider_token
# ی مشترکِ پلتفرم) و (۲) پرداختِ مشتری به فروشگاه‌دار برایِ یه سفارشِ محصول
# (customer.py، با ShopBot.bale_provider_tokenِ خودِ همون فروشگاه). چون طبقِ
# تاییدِ خودِ کاربر مصرفِ اول هنوز با یه تراکنشِ واقعی تست نشده، مصرفِ دوم هم
# رویِ همون پایه‌ی تاییدنشده سوار شده — تا وقتی حداقل یه تراکنشِ واقعی (هرکدوم
# از این دو مصرف) با موفقیت انجام نشه، به هیچ‌کدوم در production در مقیاس
# واقعی تکیه نکنید.
# =============================================================================

SUCCESS_TRANSACTION_STATUSES = {"succeed", "successful", "success", "paid", "ok"}
FAILED_TRANSACTION_STATUSES = {"failed", "failure", "rejected", "canceled", "cancelled", "timeout", "expired"}
PENDING_TRANSACTION_STATUSES = {"pending", "processing", "in_progress"}


class BaleError(Exception):
    pass


def _api_url(bot_token: str, method: str) -> str:
    """B1: آدرسِ پایه از تنظیمات (BALE_API_BASE؛ پیش‌فرض https://tapi.bale.ai) — دیگه هاردکد نیست."""
    return f"{settings.bale_api_base.rstrip('/')}/bot{bot_token}/{method}"


def toman_to_rial(toman: int) -> int:
    """B4: تنها جایِ تبدیلِ تومان→ریال (قبلاً «×۱۰» در سه فایلِ جدا پخش بود)."""
    return int(toman) * 10


def classify_transaction_status(transaction: dict | None) -> str:
    """وضعیتِ استعلامِ تراکنش → success / pending / failed / unknown (B3؛ بله «succeed» برمی‌گردونه)."""
    status = str((transaction or {}).get("status", "")).strip().lower()
    if status in SUCCESS_TRANSACTION_STATUSES:
        return "success"
    if status in PENDING_TRANSACTION_STATUSES:
        return "pending"
    if status in FAILED_TRANSACTION_STATUSES:
        return "failed"
    return "unknown"


def verify_transaction_amount(transaction: dict | None, expected_rial: int) -> bool | None:
    """True/False = مبلغِ تراکنش با مبلغِ مورد انتظار می‌خونه/نمی‌خونه؛ None = بله مبلغ رو برنگردوند (قابلِ راستی‌آزمایی نیست)."""
    raw = (transaction or {}).get("amount")
    if raw is None:
        return None
    try:
        return int(raw) == int(expected_rial)
    except (TypeError, ValueError):
        return False


async def _call(bot_token: str, method: str, payload: dict) -> dict:
    from app.services import payment_event_service  # لازیم: جلوگیریِ importِ دایره‌ای

    url = _api_url(bot_token, method)
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as http:
            async with http.post(url, json=payload) as resp:
                data = await resp.json()
    except Exception as exc:
        await payment_event_service.log_event("bale", "out", method, status="net_error", raw={"request": payload, "error": str(exc)})
        raise BaleError(f"ارتباط با بله برقرار نشد ({method}): {exc}") from exc

    ok = bool(data.get("ok", False))
    await payment_event_service.log_event("bale", "out", method, status="ok" if ok else "error", raw={"request": payload, "response": data})
    if not ok:
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
    یه لینکِ پرداخت می‌سازه که کاربر می‌تونه توی مرورگر یا اپِ بله بازش کنه — نیازی به chat_idِ از قبل نیست.
    amount_rial باید به ریال باشه (نه تومان؛ از toman_to_rial استفاده کن). B2: فیلدِ currency نداریم (بله فقط ریال می‌شناسه)،
    طولِ title (≤۳۲) و description (≤۲۵۵) می‌بُره و payload بیشتر از ۱۲۸ بایت رو صراحتاً رد می‌کنه (بریدنش تطبیقِ پرداخت رو خراب می‌کرد).
    """
    clean_title = (title or "").strip()[:32] or "پرداخت"
    clean_description = (description or "").strip()[:255] or clean_title
    if not payload or len(payload.encode("utf-8")) > 128:
        raise BaleError("payload باید بینِ ۱ تا ۱۲۸ بایت باشه.")
    if int(amount_rial) <= 0:
        raise BaleError("مبلغِ پرداخت باید مثبت باشه.")
    body = {
        "title": clean_title,
        "description": clean_description,
        "payload": payload,
        "provider_token": provider_token,
        "prices": [{"label": clean_title, "amount": int(amount_rial)}],
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
    استعلامِ نهاییِ وضعیتِ تراکنش از خودِ سرورِ بله — همیشه قبل از اعتبارکردنِ کیف‌پول این رو صدا می‌زنیم، حتی اگه
    successful_payment از وب‌هوک رسیده باشه، تا یه وب‌هوکِ جعلی نتونه کیف‌پول رو شارژ کنه.
    """
    return await _call(bot_token, "inquireTransaction", {"transaction_id": transaction_id})


async def set_webhook(bot_token: str, url: str, secret_token: str | None = None) -> None:
    """B5: بله فقط «url» می‌شناسه (نه secret_token/drop_pending_updates)؛ رازِ وب‌هوک باید داخلِ مسیرِ url باشه."""
    await _call(bot_token, "setWebhook", {"url": url})


async def delete_webhook(bot_token: str) -> None:
    """برایِ حالتِ getUpdates لازمه (بله اجازه‌یِ webhook و getUpdates هم‌زمان رو نمی‌ده)."""
    await _call(bot_token, "deleteWebhook", {})


async def get_updates(bot_token: str, offset: int | None = None, timeout: int = 10, limit: int = 100) -> list[dict]:
    """getUpdates با long-poll. عمداً با `_call` فرق داره: موفقیت‌هایِ خالیِ هر چند ثانیه نباید payment_event_logs رو پر کنن؛
    فقط خطا لاگ می‌شه (BaleError). نتیجه همیشه list است."""
    from app.services import payment_event_service  # لازیم: importِ دایره‌ای

    payload: dict = {"timeout": timeout, "limit": limit}
    if offset is not None:
        payload["offset"] = offset
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout + 15)) as http:
            async with http.post(_api_url(bot_token, "getUpdates"), json=payload) as resp:
                data = await resp.json()
    except Exception as exc:
        raise BaleError(f"ارتباط با بله برقرار نشد (getUpdates): {exc}") from exc
    if not data.get("ok", False):
        await payment_event_service.log_event("bale", "out", "getUpdates", status="error", raw={"response": data})
        raise BaleError(f"getUpdates ناموفق بود: {data.get('description') or data}")
    result = data.get("result")
    return result if isinstance(result, list) else []


async def get_me(bot_token: str) -> dict:
    return await _call(bot_token, "getMe", {})


async def get_webhook_info(bot_token: str) -> dict:
    return await _call(bot_token, "getWebhookInfo", {})
