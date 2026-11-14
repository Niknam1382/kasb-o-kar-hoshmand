"""تحلیلِ AIِ رسیدِ کارت‌به‌کارت (W5 · 2.1) — **فقط مشورتی**: هیچ‌وقت تایید/ردِ خودکار نمی‌کند.

خروجیِ مدلِ بینایی JSONِ سخت‌گیرانه است و دفاعی پارس می‌شه (خراب/ناقص/توهمی ⇒ «تحلیل ناموفق»، نه کرش).
مقایسه با مبلغِ سفارش، ۴رقمِ آخرِ کارتِ فروشگاه، بازه‌یِ زمانی و تکراری‌بودنِ شماره‌پیگیری فقط *پرچم* می‌سازد.
هزینه از کیفِ پولِ فروشگاه‌دار **بعد از موفقیت** و commit قبلِ فراخوانیِ AI (scripts/audit_ai_commit.py)."""

from __future__ import annotations

import datetime
import json
import logging
import re
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import OrderPayment, WalletTransactionReason
from app.services import ai_pool_service, ai_service, wallet_service
from app.utils.jalali import gregorian_to_jalali, to_tehran

logger = logging.getLogger(__name__)

VERDICT_OK = "ok"
VERDICT_WARN = "warn"
VERDICT_BAD = "bad"
VERDICT_ERROR = "error"

RECEIPT_JSON_PROMPT = (
    "این تصویر را بررسی کن. فقط و فقط یک JSON معتبر برگردان، بدونِ هیچ متنِ اضافه و بدونِ ```. کلیدها: "
    '{"is_receipt": true|false, "amount": عدد صحیح یا null, "date": "YYYY/MM/DD یا null", "time": "HH:MM یا null", '
    '"dest_card_last4": "۴ رقمِ آخرِ کارتِ مقصد یا null", "tracking_no": "شماره‌یِ پیگیری/مرجع یا null", '
    '"status": "successful|failed|unknown", "confidence": عددی بینِ 0 و 1}. '
    "اگه تصویر رسیدِ بانکی نیست is_receipt=false بذار و بقیه را null. چیزی را حدس نزن."
)

_DIGIT_TABLE = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_FENCE_RE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$")
_ALLOWED_STATUS = {"successful", "failed", "unknown"}


@dataclass(frozen=True)
class ReceiptAnalysis:
    is_receipt: bool
    amount: int | None
    date: str | None
    time: str | None
    dest_card_last4: str | None
    tracking_no: str | None
    status: str
    confidence: float


def _digits(value) -> str:
    return str(value).translate(_DIGIT_TABLE)


def _opt_str(value, max_len: int) -> str | None:
    if value is None or isinstance(value, (dict, list, bool)):
        return None
    text = " ".join(str(value).split())
    return text[:max_len] or None


def parse_receipt_json(raw: str | None) -> ReceiptAnalysis | None:
    """پارسِ دفاعی. None = نامعتبر (JSONِ خراب، غیرِ شیء، is_receiptِ غیرِ بولی…)."""
    text = (raw or "").strip()
    if not text:
        return None
    text = _FENCE_RE.sub("", text).strip()
    if not text.startswith("{"):
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            return None
        text = text[start : end + 1]
    try:
        data = json.loads(text)
    except (TypeError, ValueError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("is_receipt"), bool):
        return None

    amount = None
    raw_amount = data.get("amount")
    if isinstance(raw_amount, (int, float)) and not isinstance(raw_amount, bool):
        amount = int(raw_amount) if float(raw_amount).is_integer() and raw_amount > 0 else None
    elif isinstance(raw_amount, str):
        cleaned = re.sub(r"[,\s٬]", "", _digits(raw_amount))
        amount = int(cleaned) if cleaned.isascii() and cleaned.isdecimal() and 0 < len(cleaned) <= 13 else None

    last4 = _opt_str(data.get("dest_card_last4"), 8)
    tail = _digits(last4)[-4:] if last4 else ""
    last4 = tail if len(tail) == 4 and tail.isascii() and tail.isdecimal() else None
    status = data.get("status") if data.get("status") in _ALLOWED_STATUS else "unknown"
    confidence = data.get("confidence")
    confidence = float(confidence) if isinstance(confidence, (int, float)) and not isinstance(confidence, bool) else 0.0
    return ReceiptAnalysis(
        is_receipt=data["is_receipt"],
        amount=amount,
        date=_opt_str(data.get("date"), 16),
        time=_opt_str(data.get("time"), 8),
        dest_card_last4=last4,
        tracking_no=_opt_str(data.get("tracking_no"), 40),
        status=status,
        confidence=max(0.0, min(1.0, confidence)),
    )


def _jalali_str(moment: datetime.datetime) -> str:
    jy, jm, jd = gregorian_to_jalali(*to_tehran(moment).timetuple()[:3])
    return f"{jy:04d}/{jm:02d}/{jd:02d}"


def _norm_date(raw: str | None) -> str | None:
    match = re.fullmatch(r"(\d{4})\D(\d{1,2})\D(\d{1,2})", _digits(raw or "").strip())
    return f"{int(match[1]):04d}/{int(match[2]):02d}/{int(match[3]):02d}" if match else None


def compare(
    analysis: ReceiptAnalysis,
    *,
    expected_toman: int,
    expected_last4: str | None,
    order_created_at: datetime.datetime,
    now: datetime.datetime,
) -> list[str]:
    """پرچم‌ها (فقط مشورتی). مبلغ به تومان یا ریال پذیرفته می‌شه؛ تاریخ جلالی یا میلادی."""
    if not analysis.is_receipt:
        return ["not_receipt"]
    flags: list[str] = []
    if analysis.status == "failed":
        flags.append("tx_failed")
    if analysis.amount is None:
        flags.append("amount_unreadable")
    elif analysis.amount not in (expected_toman, expected_toman * 10):
        flags.append("amount_mismatch")
    if expected_last4 and analysis.dest_card_last4 and analysis.dest_card_last4 != expected_last4:
        flags.append("card_mismatch")
    date = _norm_date(analysis.date)
    if date is not None:
        window_days = {_jalali_str(order_created_at - datetime.timedelta(minutes=10)), _jalali_str(now + datetime.timedelta(minutes=5))}
        if date not in window_days:
            gregorian = {to_tehran(m).strftime("%Y/%m/%d") for m in (order_created_at - datetime.timedelta(minutes=10), now + datetime.timedelta(minutes=5))}
            if date not in gregorian:
                flags.append("date_out_of_window")
    return flags


def verdict_for(analysis: ReceiptAnalysis | None, flags: list[str]) -> str:
    if analysis is None:
        return VERDICT_ERROR
    if not analysis.is_receipt or "tx_failed" in flags:
        return VERDICT_BAD
    return VERDICT_WARN if flags else VERDICT_OK


_FLAG_TEXT = {
    "not_receipt": "تصویر شبیهِ رسیدِ بانکی نیست",
    "tx_failed": "رسید «ناموفق» نشون می‌ده",
    "amount_unreadable": "مبلغ خونده نشد",
    "amount_mismatch": "مبلغِ رسید با مبلغِ سفارش نمی‌خونه",
    "card_mismatch": "۴رقمِ آخرِ کارتِ مقصد با کارتِ فروشگاه فرق داره",
    "date_out_of_window": "تاریخِ رسید خارج از بازه‌یِ سفارش است",
    "dup_tracking": "این شماره‌پیگیری قبلاً روی پرداختِ دیگری هم ثبت شده",
}


def advisory_line(verdict: str, flags: list[str]) -> str:
    """یک خط برایِ فروشگاه‌دار؛ همیشه با «تصمیم با توئه» روشن می‌کنه که تایید/ردِ خودکار نیست."""
    if verdict == VERDICT_ERROR:
        return "🤖 تحلیلِ خودکارِ رسید ناموفق بود؛ خودت بررسی کن."
    if verdict == VERDICT_OK:
        return "🤖 تحلیلِ خودکار (مشورتی): مبلغ و کارت و زمان با سفارش هم‌خوان به نظر می‌رسه — تصمیم با توئه."
    reasons = "؛ ".join(_FLAG_TEXT.get(flag, flag) for flag in flags)
    return f"🤖 تحلیلِ خودکار (مشورتی): ⚠️ {reasons} — تصمیم با توئه."


async def _is_duplicate_tracking(session: AsyncSession, payment: OrderPayment, tracking_no: str | None) -> bool:
    if not tracking_no:
        return False
    count = (
        await session.execute(
            select(func.count())
            .select_from(OrderPayment)
            .where(OrderPayment.shop_bot_id == payment.shop_bot_id, OrderPayment.tracking_ref == tracking_no, OrderPayment.id != payment.id)
        )
    ).scalar_one()
    return bool(count)


async def analyze_receipt(
    session: AsyncSession,
    *,
    owner,
    admin_settings,
    payment: OrderPayment,
    image_bytes: bytes,
    expected_toman: int,
    expected_last4: str | None,
    order_created_at: datetime.datetime,
) -> str | None:
    """خطِ مشورتی یا None (غیرفعال/اعتبارِ ناکافی/AI نیست/شکست). ترتیب: بررسیِ اعتبار ← commit ← AI ← ذخیره ← کسرِ هزینه.
    خطایِ AI ⇒ هیچ هزینه و هیچ اثری؛ تحلیلِ نامعتبر ⇒ ذخیره‌یِ verdict=error بدونِ هزینه.

    P21-C (F3): اگر ادمین `wallet_cost_receipt_per_1k_tokens` را روشن کرده باشد، هزینهٔ واقعی
    بعد از پاسخِ AI با توکن‌هایِ گزارش‌شده محاسبه می‌شود؛ سنجشِ *ابتدا* با کفِ ثابت انجام می‌شود
    تا هرگز فراخوانی‌ای که قطعاً پرداخت نمی‌شود شروع نشود.
    """
    floor_cost = wallet_service.estimate_receipt_cost(admin_settings, None)
    if owner is None or owner.wallet_balance_toman < max(floor_cost, 1):
        return None
    ai = await ai_pool_service.build_ai_service(session, admin_settings, "vision")
    if ai is None:
        return None
    await session.commit()  # آزادسازیِ اتصالِ دیتابیس و قطعی‌شدنِ ثبتِ رسید قبل از انتظارِ AI
    try:
        result = await ai.analyze_image(RECEIPT_JSON_PROMPT, image_bytes)
    except ai_service.AiServiceError:
        logger.exception("تحلیلِ رسیدِ پرداخت %s ناموفق بود (بدونِ هزینه).", payment.id)
        return None
    except Exception:  # noqa: BLE001
        logger.exception("تحلیلِ رسیدِ پرداخت %s با خطایِ غیرمنتظره شکست خورد (بدونِ هزینه).", payment.id)
        return None

    analysis = parse_receipt_json(getattr(result, "text", None))
    flags: list[str] = []
    if analysis is not None:
        now = datetime.datetime.now(datetime.timezone.utc)
        flags = compare(analysis, expected_toman=expected_toman, expected_last4=expected_last4, order_created_at=order_created_at, now=now)
        if await _is_duplicate_tracking(session, payment, analysis.tracking_no):
            flags.append("dup_tracking")
    verdict = verdict_for(analysis, flags)
    payment.ai_verdict = verdict
    payment.ai_json = json.dumps(
        {"analysis": None if analysis is None else analysis.__dict__, "flags": flags}, ensure_ascii=False
    )
    if analysis is not None:
        tokens_used = getattr(result, "total_tokens", None)
        cost = wallet_service.estimate_receipt_cost(admin_settings, tokens_used)
        if not await wallet_service.deduct(
            session, owner, cost, WalletTransactionReason.RECEIPT_ANALYSIS,
            reference=f"order_payment:{payment.id}", ai_total_tokens=tokens_used,
        ):
            logger.warning("تحلیلِ رسیدِ پرداخت %s انجام شد ولی هزینه‌اش (%s تومان) از موجودی کم بود.", payment.id, cost)
    await session.commit()
    return advisory_line(verdict, flags)
