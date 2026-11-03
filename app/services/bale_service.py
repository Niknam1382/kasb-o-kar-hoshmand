from __future__ import annotations

import asyncio
import re
from urllib.parse import quote

import aiohttp

from app.config import settings

# =============================================================================
# نکته‌ی مهم درباره‌ی این فایل — وضعیتِ راستی‌آزماییِ Bale Pay (به‌روز: P26، ۲۰۲۶-۱۱-۰۲)
#
# API بله بر پایه‌ی همان طرحِ Telegram Bot API است (chat_id، sendInvoice،
# pre_checkout_query، successful_payment، inquireTransaction). درباره‌ی «لینکِ پرداخت»
# سه شاهدِ مستقل داریم:
# ۱) MEASURED در این محیط: پاسخِ `createInvoiceLink` رشتهٔ `invoice_id=M6dm…` است،
#    یعنی بله آدرسی برنمی‌گرداند. «currency» را هم نمی‌فرستیم و پاسخ ok بوده، پس آن
#    فیلد در این API لزومی ندارد (برخلافِ متنِ داکیومنت).
# ۲) MEASURED با پروبِ زنده (P26): `https://bale.ai/pay/<id>` ⇒ ۴۰۴،
#    `https://ble.ir/pay/abc` ⇒ ۴۰۴، ولی `https://ble.ir/<username>` ⇒ ۲۰۰ و
#    `?start=<payload>` هم در HTML همان صفحه می‌نشیند. یعنی آدرسِ پرداختی وجود ندارد؛
#    چیزی که وجود دارد چتِ ربات است. همان سندِ بله، همان `invoice_id` را «شناسهٔ
#    مینی‌اپ» می‌داند که با `openInvoice(invoiceParams)` مصرف می‌شود — و مینی‌اپ
#    میزبانیِ HTTPSِ خودمان را می‌خواست، که نداریم و لازم نیست.
# ۳) جریانِ چتی (sendInvoice + answerPreCheckoutQuery + inquireTransaction) که در
#    app/main.py هندل می‌شود؛ طبقِ همان سند پاسخِ pre_checkout باید حداکثر ظرف ۱۰
#    ثانیه برسد (اولویتِ پردازش در bale_updates_service).
#
# پس لینکِ پرداخت = `pay_chat_link()` (چتِ رباتِ پرداخت با start param) و صورتحساب
# با `send_invoice()` در همان چت فرستاده می‌شود. `create_invoice_link` فقط در
# «🧪 آزمایشِ بله‌پی» مانده تا اثباتِ کارکردنِ توکنِ درگاه حفظ شود.
# زنجیره‌ی «لینک → چت → صورتحساب → پرداختِ واقعی → تاییدِ سفارش» اندازه‌گیری شد (MEASURED،
# ۱۴۰۵-۰۸-۱۱، ۱٬۰۰۰ تومان، همین نصبِ توسعه): تصحیحِ pre_checkout_query در ۲۱۴ میلی‌ثانیه
# (سقف ۱۰ ثانیه) و بعد successful_payment و inquire_result=success در payment_event_logs.
# آنچه هنوز بی‌تراکنشِ واقعی مانده (NOT RUN): همین زنجیره برایِ «شارژِ کیف‌پول»ِ پلتفرم و
# پرداختِ زرین‌پال.
# =============================================================================

SUCCESS_TRANSACTION_STATUSES = {"succeed", "successful", "success", "paid", "ok"}
FAILED_TRANSACTION_STATUSES = {"failed", "failure", "rejected", "canceled", "cancelled", "timeout", "expired"}
PENDING_TRANSACTION_STATUSES = {"pending", "processing", "in_progress"}


class BaleError(Exception):
    pass


# P25-E: sessionِ مشترکِ HTTP (نگه‌داشتنِ connection pool) + سقفِ زمانیِ هر درخواستِ API.
API_REQUEST_TIMEOUT_SECONDS = 20.0
LONG_POLL_TIMEOUT_SECONDS = 25
_http_session: aiohttp.ClientSession | None = None
_http_loop: object | None = None


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


async def _http(timeout: float) -> aiohttp.ClientSession:
    """P25-E: یکِ `ClientSessionِ` مشترک به‌جایِ ساختنِ یکی در هر درخواست.

    هر گردشِ getUpdates و هر فراخوانِ پرداخت session تازه می‌ساخت ⇒ TCP + DNSِ دوباره بدونِ
    reuse (با long-pollِ ۱۰ ثانیه ≈ ۷٬۹۰۰ دورِ TCP در روز فقط برایِ پرسیدنِ «چیزی هست؟»).
    session به event loop بسته می‌شود، پس اگر loop عوض شد (تست‌ها) نسخهٔ کهنه دور انداخته و
    تازه ساخته می‌شود — بستنِ cross-loop انجام نمی‌دهیم چون خودش منبعِ hang است.
    """
    global _http_session, _http_loop
    loop = asyncio.get_running_loop()
    if _http_session is None or _http_session.closed or _http_loop is not loop:
        _http_session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=timeout),
            connector=aiohttp.TCPConnector(limit=10, ttl_dns_cache=300),
        )
        _http_loop = loop
    return _http_session


async def _drop_http_session() -> None:
    """P25-E: بعدِ خطایِ شبکه، استخرِ اتصالات را دور می‌اندازیم.

    دو سود: (۱) کانکتورِ نیمه‌خرابِ ناشی از timeout/قطعِ شبکه دوباره استفاده نمی‌شود،
    (۲) در پروسه‌هایِ کوتاه (تست) session بازِ بی‌صاحب نمی‌ماند و asyncio «Unclosed client
    session» چاپ نمی‌کند.
    """
    global _http_session, _http_loop
    if _http_session is not None and not _http_session.closed:
        try:
            await _http_session.close()
        except Exception:  # noqa: BLE001 — پاکیزگیِ مسیرِ خطا نباید خودِ خطا را بپوشاند
            pass
    _http_session = None
    _http_loop = None


async def close_http_session() -> None:
    """در shutdownِ برنامه صدا زده می‌شود (بستنِ تمیزِ connector)."""
    await _drop_http_session()


async def _call(bot_token: str, method: str, payload: dict) -> dict:
    from app.services import payment_event_service  # لازیم: جلوگیریِ importِ دایره‌ای

    url = _api_url(bot_token, method)
    http = await _http(API_REQUEST_TIMEOUT_SECONDS)
    try:
        async with http.post(url, json=payload) as resp:
            data = await resp.json()
    except Exception as exc:
        await payment_event_service.log_event("bale", "out", method, status="net_error", raw={"request": payload, "error": str(exc)})
        await _drop_http_session()
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
    شناسهٔ پرداخت برایِ **مینی‌اپ** می‌سازد (سندِ رسمی: «برای استفاده در مینی‌اپ‌ها») — این آدرسِ
    قابل‌کلیک در مرورگر **نیست** و از P26 دیگر به‌عنوانِ لینکِ پرداخت مصرف می‌شود؛ مصرفِ فعلی‌اش
    فقط «🧪 آزمایشِ بله‌پی» است (اثباتِ این‌که توکنِ درگاه کار می‌کند).
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


async def send_invoice(
    bot_token: str,
    chat_id: int,
    provider_token: str,
    title: str,
    description: str,
    payload: str,
    amount_rial: int,
) -> None:
    """P26: صورتحسابِ **بومیِ** بله را در یکِ چت می‌فرستد — همین است که دکمهٔ «پرداخت» را با
    کیف‌پولِ بله باز می‌کند و بعد `pre_checkout_query` و `successful_payment` را برایِ همین
    ربات می‌فرستد (که در `app/main.py` هندل می‌شوند).

    برخلافِ `createInvoiceLink` این مسیر در مستنداتِ رسمیِ بله کامل آمده و به مرورگر/میزبانی
    نیاز ندارد؛ تنها پیش‌نیازش این است که فرستنده‌یِ پرداخت با این ربات در اپِ بله گفتگو کرده
    باشد — همان کاری که `pay_chat_link()` با یکِ لمس انجام می‌دهد.
    """
    clean_title = (title or "").strip()[:32] or "پرداخت"
    clean_description = (description or "").strip()[:255] or clean_title
    if not payload or len(payload.encode("utf-8")) > 128:
        raise BaleError("payload باید بینِ ۱ تا ۱۲۸ بایت باشه.")
    if int(amount_rial) <= 0:
        raise BaleError("مبلغِ پرداخت باید مثبت باشه.")
    if not str(chat_id).strip():
        raise BaleError("برایِ sendInvoice نشانیِ چت لازم است.")
    await _call(
        bot_token,
        "sendInvoice",
        {
            "chat_id": int(chat_id),
            "title": clean_title,
            "description": clean_description,
            "payload": payload,
            "provider_token": provider_token,
            "prices": [{"label": clean_title, "amount": int(amount_rial)}],
        },
    )


# P26 — پروبِ زنده در همین محیط (پاسخ‌های HTTP واقعی):
#   https://ble.ir/smartbusinessbot                   ⇒ 200 (صفحهٔ همان ربات در اپ/وبِ بله)
#   https://ble.ir/smartbusinessbot?start=pay-TEST    ⇒ 200 و پارامتر به کلاینت می‌رسد
#   https://ble.ir/nonexistentbotxyz123               ⇒ 404 (پس مسیرها سنجیده می‌شوند)
#   https://ble.ir/pay/abc · https://bale.ai/pay/<id> ⇒ 404 — هیچ آدرسِ پرداختی وجود ندارد
# مستنداتِ مینی‌اپ هم می‌گوید خروجیِ createInvoiceLink فقط با `openInvoice(invoiceParams)` داخلِ
# مینی‌اپ مصرف می‌شود. پس «لینکِ پرداخت» یعنی لینکِ چتِ ربات با یکِ start param، و صورتحساب را
# خودِ بله در همان چت نشان می‌دهد (`send_invoice` در این فایل).
BLE_BOT_LINK_BASE = "https://ble.ir"
_BOT_USERNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{4,31}$")


def pay_chat_link(bot_username: str | None, payload: str | None) -> str | None:
    """لینکی که در تلگرام هم باز می‌شود و کاربر را در اپِ بله به چتِ رباتِ پرداخت می‌برد.

    `payload` همان رشته‌ای است که داخلِ صورتحساب می‌نشیند (`payment-…` / `cartgroup-…` / `order-…`)،
    پس `/start` همان کلیدِ lookupِ مسیرِ پرداخت است و جدولِ واسطِ دیگری لازم نیست. None یعنی
    «لینکی نساز» (ربات username ندارد)؛ فراخوانِ بالاتر پیامِ صادقانه می‌دهد، نه لینکِ مرده.
    """
    name = (bot_username or "").strip().lstrip("@")
    if not name or not payload or not _BOT_USERNAME_RE.match(name):
        return None
    return f"{BLE_BOT_LINK_BASE}/{name}?start={quote(payload, safe='-._')}"


async def send_text(bot_token: str, chat_id: int, text: str) -> None:
    """یکِ پیامِ متنی ساده (برایِ پاسخِ `/start`ِ لینکِ پرداخت وقتی چیزی پیدا نشد)."""
    await _call(bot_token, "sendMessage", {"chat_id": int(chat_id), "text": (text or "")[:4000]})


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


async def get_updates(
    bot_token: str, offset: int | None = None, timeout: int = LONG_POLL_TIMEOUT_SECONDS, limit: int = 100
) -> list[dict]:
    """getUpdates با long-poll. عمداً با `_call` فرق داره: موفقیت‌هایِ خالیِ هر چند ثانیه نباید payment_event_logs رو پر کنن؛
    فقط خطا لاگ می‌شه (BaleError). نتیجه همیشه list است.

    P25-E: `timeout` از ۱۰ به ۲۵ ثانیه رفت ⇒ هر دورِ بی‌نتیجه یکِ درخواستِ کاملِ TCP+DNS بود؛ با
    ۲۵ ثانیه از ≈۷٬۹۰۰ دور در روز به ≈۳٬۳۰۰ می‌رسد (−۵۸٪؛ از حسابِ پیکربندی، چون فرضش
    نگه‌داشتنِ long-poll تا پایانِ timeout سمتِ بله است).
    """
    from app.services import payment_event_service  # لازیم: importِ دایره‌ای

    payload: dict = {"timeout": timeout, "limit": limit}
    if offset is not None:
        payload["offset"] = offset
    http = await _http(API_REQUEST_TIMEOUT_SECONDS)
    try:
        async with http.post(
            _api_url(bot_token, "getUpdates"), json=payload, timeout=aiohttp.ClientTimeout(total=timeout + 15)
        ) as resp:
            data = await resp.json()
    except Exception as exc:
        await _drop_http_session()
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
