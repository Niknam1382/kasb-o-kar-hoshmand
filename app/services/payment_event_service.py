"""
ردِ رویدادهایِ پرداخت (B12): هر تماسِ خروجی/رویدادِ ورودیِ بله/زرین‌پال با JSONِ خام (بدونِ توکن و شماره‌کارت).
با session مستقل می‌نویسه تا حتی وقتی تراکنشِ اصلی rollback می‌شه رد بمونه؛ هیچ‌وقت exception نمی‌ده (فقط لاگ).
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import PaymentEventLog
from app.database.session import session_scope

logger = logging.getLogger(__name__)

_SENSITIVE_KEYS = {"token", "provider_token", "provider_token_value", "merchant_id", "authorization", "secret", "secret_token", "password", "api_key"}
_BOT_TOKEN_RE = re.compile(r"\d{6,}:[A-Za-z0-9_-]{20,}")
# P36 (دفاعِ لایه‌ای): آدرس‌هایِ Bot API توکن را در مسیر جا می‌دهند (`…/bot<token>/getUpdates`).
# الگویِ بالا فقط شکلِ «رقم‌ها:دنباله» را می‌گیرد؛ این یکی هر `/bot…/` را می‌بندد، حتی اگر شکلِ
# توکنِ سرویسِ دیگری بعداً عوض شود یا رقم‌هایش کمتر از شش باشد.
_BOT_URL_RE = re.compile(r"/bot[^/\s]{1,200}/")
# P40 (دفاعِ لایه‌ای): `setWebhook` و `getWebhookInfo` آدرسِ `/webhook/main|bale/<راز>` را در
# payload/پاسخ دارند و همان‌ها در `payment_event_logs.raw` می‌نشیند (و در هر pg_dump).
# بخشِ عددیِ `/webhook/shop/<id>` عمداً ماسک نمی‌شود؛ فقط چیزی که شبیهِ راز است.
_WEBHOOK_SECRET_RE = re.compile(r"(/webhook/(?:main|bale)/)([^/?#\s\"']{6,})")
_PAN_RE = re.compile(r"(?<!\d)\d{16}(?!\d)")
MAX_RAW_LENGTH = 4000
# د(و): وضعیتی که «شکستِ پرداخت» حساب می‌شود و شمارنده‌یِ هشدارِ ادمین را بالا می‌برد.
FAILURE_STATUSES = frozenset({"failed", "unknown", "no_ref", "net_error", "error"})


def _mask_text(text: str) -> str:
    return _PAN_RE.sub("****", _WEBHOOK_SECRET_RE.sub(r"\1***", _BOT_URL_RE.sub("/bot***/", _BOT_TOKEN_RE.sub("***", text))))


def _scrub(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: ("***" if str(k).lower() in _SENSITIVE_KEYS else _scrub(v)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_scrub(v) for v in value]
    if isinstance(value, str):
        return _mask_text(value)
    return value


def sanitize(raw: Any) -> str:
    """JSON/متنِ خام → رشته‌یِ امن و کوتاه (کلیدهایِ حساس و الگویِ توکن/شماره‌کارت ماسک می‌شن)."""
    try:
        text = json.dumps(_scrub(raw), ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        text = _mask_text(str(raw))
    text = _mask_text(text)  # توکنِ داخلِ URL/متنِ آزاد
    return text[:MAX_RAW_LENGTH]


async def log_event(
    provider: str,
    direction: str,
    method: str,
    reference: str | None = None,
    status: str | None = None,
    raw: Any = None,
    shop_bot_id: int | None = None,
    group_ref: str | None = None,
) -> None:
    """`shop_bot_id`/`group_ref` شناسه‌یِ همبستگی‌اند (د-ز) تا در عیب‌یابی بشود ردیف‌هایِ یک فروشگاه/گروه را پیدا کرد."""
    try:
        async with session_scope() as session:
            session.add(
                PaymentEventLog(
                    provider=provider[:16], direction=direction[:8], method=method[:64],
                    reference=(str(reference)[:128] if reference is not None else None),
                    status=(str(status)[:32] if status is not None else None),
                    raw=sanitize(raw) if raw is not None else None,
                    shop_bot_id=shop_bot_id,
                    group_ref=(str(group_ref)[:64] if group_ref is not None else None),
                )
            )
    except Exception:  # noqa: BLE001 — لاگِ عیب‌یابی نباید پرداخت رو بشکنه
        logger.warning("ثبتِ رویدادِ پرداخت ناموفق بود.", exc_info=True)
    if status in FAILURE_STATUSES:
        # د(و): شکستِ پرداختِ تکراری ⇒ هشدارِ نرخ‌محدود به ادمین. هرگز نباید خودِ مسیرِ پرداخت را بشکند.
        try:
            from app.services import admin_alert_service

            admin_alert_service.record_event(
                admin_alert_service.KIND_PAYMENT, f"{provider}/{method}: {status} (ref={reference}, shop={shop_bot_id})"
            )
        except Exception:  # noqa: BLE001
            pass


async def recent_events(session: AsyncSession, limit: int = 20) -> list[PaymentEventLog]:
    result = await session.execute(select(PaymentEventLog).order_by(PaymentEventLog.id.desc()).limit(limit))
    return list(result.scalars().all())
