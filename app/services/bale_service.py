from __future__ import annotations

import asyncio
import re
from urllib.parse import urlsplit

import aiohttp

from app.config import settings

# =============================================================================
# نکته‌ی مهم درباره‌ی این فایل — وضعیتِ راستی‌آزماییِ Bale Pay (به‌روز: P25، ۲۰۲۶-۱۱-۰۲)
#
# API بله بر پایه‌ی همان طرحِ Telegram Bot API است (chat_id، sendInvoice،
# pre_checkout_query، successful_payment، inquireTransaction). درباره‌ی
# createInvoiceLink سه شاهدِ مستقل داریم:
# ۱) MEASURED در این محیط: پاسخ `result: "invoice_id=M6dm…"` است، یعنی بله خودِ
#    آدرسِ کامل را برنمی‌گرداند. «currency» را هم نمی‌فرستیم و پاسخ ok بوده، پس آن
#    فیلد در این API لزومی ندارد (برخلافِ متنِ داکیومنت).
# ۲) سندِ «دستورالعملِ نهاییِ درگاهِ پرداختِ بله‌پی» که کاربر از docs.bale.ai
#    استخراج کرده: خروجی آدرسی به‌شکلِ `https://bale.ai/pay/<id>` است. این دو با هم
#    سازگارند، پس DEFAULT_PAY_LINK_TEMPLATE پیش‌فرضِ داخلی شده و دیگر لازم نیست
#    ادمین چیزی را دستی کپی کند (قبلاً اگر متنِ نمونه‌ی داکیومنت را می‌چسباند،
#    تلگرام آدرس را رد می‌کرد و دکمه می‌مرد).
# ۳) جریانِ چتی (sendInvoice + answerPreCheckoutQuery + inquireTransaction) که در
#    app/main.py هندل می‌شود؛ طبقِ همان سند پاسخِ pre_checkout باید حداکثر ظرف ۱۰
#    ثانیه برسد (اولویتِ پردازش در bale_updates_service).
#
# با این حال زنجیره‌ی کاملِ «لینک → پرداخت در اپ بله → شارژِ کیف‌پول» هنوز با یکِ
# تراکنشِ واقعیِ کوچک تایید نشده (NOT RUN — هزینه‌ی واقعیِ پولِ خودت). هر دو مصرفِ
# این فایل (پرداختِ فروشگاه‌دار به پلتفرم و پرداختِ مشتری به فروشگاه) رویِ همین
# پایه‌اند؛ اگر بله شکلِ لینک را عوض کرد، فقط همین فایل و ستونِ «قالبِ لینک» کافی است.
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


INVOICE_ID_FIELD = "invoice_id"
PLACEHOLDER_ID = "{invoice_id}"
PLACEHOLDER_PARAMS = "{invoice_params}"
# از «دستورالعملِ نهاییِ درگاهِ پرداختِ بله‌پی» (سندِ رسمیِ docs.bale.ai که کاربر داد): خروجیِ
# createInvoiceLink یکِ آدرسِ `https://bale.ai/pay/<id>` است. در این محیط اندازه گرفته شد که بله
# خودِ این را به‌شکلِ `invoice_id=<id>` برمی‌گرداند، پس همین قالبِ رسمی به‌عنوانِ پیش‌فرضِ داخلی
# استفاده می‌شود و «قالبِ لینک» در پنل فقط برایِ override است (بدونِ آن دکمه می‌مرد).
DEFAULT_PAY_LINK_TEMPLATE = "https://bale.ai/pay/{invoice_id}"

# میزبانِ واقعی: برچسب‌هایِ کوچکِ الف/رقم/خط‌تیره، جداشده با نقطه، بدونِ زیرخط و بدونِ حرفِ بزرگ.
# دقیقاً همین قانون، مقدارِ نمونهٔ داکیومنت‌ها (`YOUR_BALE_PAYMENT_BASE_URL`) را رد می‌کند — تلگرام
# چنین آدرسی را «Wrong HTTP URL» می‌زند و هندلرِ پرداخت بعد ازِ ساختِ invoice می‌ترکد (MEASURED).
_HOSTNAME_RE = re.compile(
    r"^(?=.{1,253}$)[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$"
)



def parse_invoice_result(result: str) -> tuple[str | None, str, str]:
    """به دو شکل برمی‌گردد: یا آدرسِ کامل، یا `کلید=مقدار`. خروجی: (url|None, شناسه, رشتهٔ خام).

    MEASURED از `payment_event_logs`ِ همین محیط: بله «invoice_id=M6dm…» می‌دهد، نه URL.
    چیزی که نه آدرس است نه `کلید=مقدار` ⇒ (None, "", "")؛ یعنی قابلِ مصرف نیست. جایِ خالی را در
    قالب نمی‌چشانیم، وگرنه لینکِ نصفه دقیقاً همان «دکمهٔ مرده» را برمی‌گرداند.
    """
    text = (result or "").strip()
    if text.startswith("http://") or text.startswith("https://"):
        return text, "", text
    key, sep, value = text.partition("=")
    if sep and key.strip() and value.strip():
        return None, value.strip(), text
    return None, "", ""


def valid_link_template(raw: str | None) -> bool:
    """قالبِ لینک باید آدرسِ http(s) باشد و یکی از جای‌نگهدارها را داشته باشد (اگر خالی است، پاک‌کردن حساب می‌شود)."""
    text = (raw or "").strip()
    if not text:
        return True
    if len(text) > 256 or any(ch.isspace() for ch in text):
        return False
    if not (text.startswith("http://") or text.startswith("https://")):
        return False
    return PLACEHOLDER_ID in text or PLACEHOLDER_PARAMS in text


def usable_link_template(raw: str | None) -> bool:
    """«قالبِ قابلِ استفاده» = سینتکسِ درست + میزبانِ واقعی؛ خالی یعنی «استفاده نکن».

    قالبِ سینتکس‌درستِ میزبانِ جعلی لینکی می‌سازد که تلگرام آن را «Wrong HTTP URL» رد می‌کند و آن
    شکست بعدِ ساختِ invoice و در میانهٔ ارسالِ پیام می‌افتد ⇒ دکمهٔ مرده + پرداختِ rollback‌شده
    (MEASURED در لاگِ همین محیط با `https://YOUR_BALE_PAYMENT_BASE_URL?…`).
    """
    text = (raw or "").strip()
    if not text or not valid_link_template(text):
        return False
    return bool(_HOSTNAME_RE.match(urlsplit(text).hostname or ""))


def payment_link_source(template: str | None) -> str | None:
    """لینک از کجا ساخته می‌شود: `panel` (قالبِ ادمین) / `default` (پیش‌فرضِ مستندِ بله) / `None`."""
    if usable_link_template(template):
        return "panel"
    return "default"


def _build_link(pattern: str, invoice_id: str, raw: str) -> str | None:
    if PLACEHOLDER_ID in pattern:
        if not invoice_id:
            return None
    elif PLACEHOLDER_PARAMS not in pattern:
        return None
    # `.replace` به‌جای `.format` تا هیچ علامتِ دیگرِ آدرس (مثلِ `{}` در query) نترکد.
    built = pattern.replace(PLACEHOLDER_ID, invoice_id).replace(PLACEHOLDER_PARAMS, raw)
    return built if built.startswith(("http://", "https://")) else None


def resolve_payment_link(result: str, template: str | None = None) -> str | None:
    """یا همان URLِ برگشتیِ بله، یا ساختنِ آدرس با قالبِ ادمین و در نبودِ آن با پیش‌فرضِ مستندِ بله.

    لینکِ بی‌اعتبار یا نصفه هرگز برنمی‌گردد (None ⇒ بالاترینِ فراخوان پیامِ صادقانه می‌دهد) و
    قالبِ نامعتبرِ پنل (مثلِ متنِ نمونهٔ `YOUR_BALE_PAYMENT_BASE_URL`) با پیش‌فرض عوض می‌شود.
    """
    url, invoice_id, raw = parse_invoice_result(result)
    if url:
        return url
    if not raw:
        return None
    for pattern in ((template or "").strip(), DEFAULT_PAY_LINK_TEMPLATE):
        if not pattern or not usable_link_template(pattern):
            continue
        built = _build_link(pattern, invoice_id, raw)
        if built:
            return built
    return None


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
