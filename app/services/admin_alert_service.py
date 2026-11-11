"""هشدارِ تلگرامیِ سبک به ادمین (د-و).

سه محرک: خطایِ `ERROR` تکراری در لاگ، شکستِ پرداخت، و ۴۰۳ مکررِ وب‌هوک.
طراحی عمداً سبک و بی‌خطر است: هرگز exception نمی‌دهد، هرگز مسیرِ درخواست را بلاک نمی‌کند (ارسال در پس‌زمینه)،
هرگز رازی را نمی‌فرستد (متن با `payment_event_service.sanitize` پاک‌سازی می‌شود)، و با پنجره‌یِ لغزان +
خنک‌شدنِ هر کلید + سقفِ ساعتی از طوفانِ پیام جلوگیری می‌کند.
"""

from __future__ import annotations

import asyncio
import collections
import hashlib
import logging
import time

from app.config import settings
from app.utils.validators import fa_number

logger = logging.getLogger(__name__)

KIND_ERROR = "error"
KIND_PAYMENT = "payment"
KIND_FORBIDDEN = "forbidden"
KIND_LEDGER = "ledger"  # PHASE 5E: اختلافِ همسنجیِ دفترِ کیف‌پول

WINDOW_SECONDS = 300.0
# آستانهٔ ۱ برایِ ledger عمدی است: یک اختلافِ حسابداری هم باید دیده شود؛ cooldown و
# سقفِ ساعتیِ خودِ سرویس از اسپمِ هشدار جلوگیری می‌کنند.
THRESHOLDS: dict[str, int] = {KIND_ERROR: 5, KIND_PAYMENT: 3, KIND_FORBIDDEN: 10, KIND_LEDGER: 1}
ALERT_COOLDOWN_SECONDS = 1800.0
MAX_ALERTS_PER_HOUR = 12
MAX_DETAIL_LENGTH = 300

KIND_LABELS: dict[str, str] = {
    KIND_ERROR: "خطایِ تکراریِ برنامه",
    KIND_PAYMENT: "شکستِ پرداخت",
    KIND_FORBIDDEN: "درخواستِ ردشده‌ی وب‌هوک (۴۰۳)",
    KIND_LEDGER: "اختلافِ همسنجیِ دفترِ کیف‌پول",
}

_events: dict[str, collections.deque] = {}
_details: dict[str, str] = {}
_last_alert: dict[str, float] = {}
_alert_times: collections.deque = collections.deque()
_bot = None
# فقط بعدِ install() (یعنی در اجرایِ واقعیِ برنامه) پیامی ارسال می‌شود؛ در تست فقط شمارش می‌شود.
_enabled = False


def reset() -> None:
    """پاک‌کردنِ شمارنده‌ها و غیرفعال‌کردنِ ارسال (تست / ری‌استارت)."""
    global _bot, _enabled
    _enabled = False
    _events.clear()
    _details.clear()
    _last_alert.clear()
    _alert_times.clear()
    _bot = None


def threshold_reached() -> list[tuple[str, str, int]]:
    """(کلید, جزئیاتِ پاک‌شده, تعداد) برایِ کلیدهایی که به آستانه رسیده‌اند — فقط برایِ تست/عیب‌یابی."""
    now = time.monotonic()
    out = []
    for key, times in _events.items():
        while times and now - times[0] > WINDOW_SECONDS:
            times.popleft()
        threshold = THRESHOLDS.get(key.split(":", 1)[0], 0)
        if threshold and len(times) >= threshold:
            out.append((key, _details.get(key, ""), len(times)))
    return out


def _scrub(detail: str) -> str:
    """پاک‌سازیِ رازِ احتمالی از متنِ هشدار (توکن/شماره‌کارت) و کوتاه‌کردنش."""
    from app.services.payment_event_service import sanitize

    return sanitize(detail)[:MAX_DETAIL_LENGTH]


def _budget_allows(now: float) -> bool:
    while _alert_times and now - _alert_times[0] > 3600.0:
        _alert_times.popleft()
    return len(_alert_times) < MAX_ALERTS_PER_HOUR


def record_event(kind: str, detail: str) -> bool:
    """یک رویداد را در پنجره‌یِ لغزان ثبت می‌کند؛ True یعنی هشدار برایِ ارسال زمان‌بندی شد."""
    try:
        threshold = THRESHOLDS.get(kind)
        if not threshold:
            return False
        now = time.monotonic()
        clean = _scrub(detail or kind)
        digest = hashlib.sha256(clean.encode("utf-8", "replace")).hexdigest()[:16]
        key = f"{kind}:{digest}"
        bucket = _events.setdefault(key, collections.deque())
        while bucket and now - bucket[0] > WINDOW_SECONDS:
            bucket.popleft()
        bucket.append(now)
        _details[key] = clean
        if len(bucket) < threshold:
            return False
        # P37 (باگِ تولیدی): مقایسه با ۰.0 یعنی «آخرین هشدار سی دقیقه پیش ازِ شروعِ زمانِ یکتا
        # زده شده». `time.monotonic()` رویِ لینوکس از بوتِ ماشین شمرده می‌شود، پس در سرور/کانتینری
        # که تازه بوت شده، اولین هشدارِ هر نوع تا ۳۰ دقیقه خاموش می‌ماند — دقیقاً همان ۳۰ دقیقه‌ای
        # که دیپلوی/بوت نو به هشدار نیاز دارد. «هنوز ارسال نشده» باید None باشد، نه ۰.
        last = _last_alert.get(key)
        if last is not None and now - last < ALERT_COOLDOWN_SECONDS:
            return False
        if not _budget_allows(now):
            return False
        _last_alert[key] = now
        _alert_times.append(now)
        count = len(bucket)
        _dispatch(kind, clean, count)
        return True
    except Exception:  # noqa: BLE001 — هشدار هرگز نباید برنامه را بشکند
        return False


def _dispatch(kind: str, detail: str, count: int) -> None:
    if not _enabled:
        logger.warning("آستانه‌یِ هشدارِ ادمین رد شد (%s، %s بار) ولی ارسال غیرفعال است.", kind, count)
        return
    text = (
        f"🚨 هشدارِ خودکارِ پلتفرم — {KIND_LABELS.get(kind, kind)}\n\n"
        f"تعداد در {fa_number(int(WINDOW_SECONDS // 60))} دقیقه: {fa_number(count)}\n"
        f"نمونه: {detail}\n\n"
        "این هشدار نرخ‌محدود است؛ جزئیاتِ کامل در لاگِ کانتینر و «🔎 آخرین رویدادهایِ پرداخت»."
    )
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.warning("هشدارِ ادمین بدونِ حلقه‌یِ در حالِ اجرا ارسال نشد.")
        return
    loop.create_task(_send(text))


async def _send(text: str) -> None:
    global _bot
    try:
        admin_ids = settings.admin_ids
        if not admin_ids:
            return
        if _bot is None:
            from aiogram import Bot

            _bot = Bot(token=settings.main_bot_token)
        for admin_id in sorted(admin_ids):
            try:
                await _bot.send_message(admin_id, text)
            except Exception:  # noqa: BLE001 — TelegramAPIError/نبودِ دسترسی؛ فقط لاگ
                logger.warning("هشدارِ ادمین به %s نرسید.", admin_id)
    except Exception:  # noqa: BLE001
        logger.warning("ارسالِ هشدارِ ادمین ناموفق بود.", exc_info=True)


class AdminAlertHandler(logging.Handler):
    """ERROR/CRITICAL هایِ تکراری را به هشدارِ تلگرامی تبدیل می‌کند."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            if record.levelno < logging.ERROR or record.name == __name__:
                return
            detail = f"{record.name}: {record.getMessage()}"
            if record.exc_info and record.exc_info[0] is not None:
                detail = f"{detail} | {record.exc_info[0].__name__}"
            record_event(KIND_ERROR, detail)
        except Exception:  # noqa: BLE001
            pass


def install() -> None:
    """ارسال را فعال و هندلر را رویِ لاگرِ ریشه نصب می‌کند (یک‌بار، در startup)."""
    global _enabled
    _enabled = True
    root = logging.getLogger()
    if any(isinstance(handler, AdminAlertHandler) for handler in root.handlers):
        return
    handler = AdminAlertHandler()
    handler.setLevel(logging.ERROR)
    root.addHandler(handler)


async def shutdown() -> None:
    """بستنِ جلسه‌یِ HTTP رباتِ هشدار (در shutdown)."""
    global _bot
    bot, _bot = _bot, None
    if bot is not None:
        try:
            await bot.session.close()
        except Exception:  # noqa: BLE001
            logger.warning("بستنِ جلسه‌یِ رباتِ هشدار ناموفق بود.", exc_info=True)
