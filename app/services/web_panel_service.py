"""پ۱۰۹ · پنجرهٔ نوشتنیِ وب: صدورِ لینکِ یکبارمصرف از ربات، تبدیلِ آن به نشستِ امضاشده، و چهار فعلِ مجاز.

چرا این شکل (نه رمزِ کاربری): هویتِ هرِ فروشگاه‌دار در این محصول *تلگرام* است و رباتِ مرکزی او را
احراز کرده. رمزِ مستقل یعنی رازِ دومی که باید بازیابی شود و فهرستِ اهدافِ حملَه را بلندتر می‌کند.
لینکِ یکبارمصرف با مهلتِ ۱۵ دقیقه، هش‌شده در دیتابیس و ابطال‌شدنی از همان ربات ⇒ همان احرازِ تلگرام،
بدونِ رازِ تازه.

چرا فقط چهار فعل: نوشتن از وب یعنی عبورِ *نویسندهٔ تازه* به سرویس‌هایی که امروز از ربات صدا زده
می‌شوند. هر فعلِ اینجا همان تابعِ همان دکمهٔ ربات است (مالکیتِ ردیف، قفلِ سطری، گذارِ مجاز و دفترِ
ممیزی از همان‌جا می‌آید) و هیچ مسیرِ پولیِ تازه‌ای ساخته نشده: نه پرداخت، نه استرداد، نه کیف‌پول،
نه ارسالِ پیام به مشتری.
"""
from __future__ import annotations

import datetime
import hashlib
import hmac
import secrets

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.models import (
    AuditEventType,
    ShopOwner,
    ShopBot,
    WebPanelSession,
)
from app.services import (
    audit_log_service,
    order_service,
    order_state,
    order_transition_service,
    product_service,
    shop_bot_service,
)

LINK_TTL_SECONDS = 900  # عمرِ لینکِ ارسال‌شده در چتِ فروشگاه‌دار
SESSION_TTL_SECONDS = 6 * 3600  # بعد ازِ بازِ لینک، نشستِ مرورگر چند ساعت می‌چرخد
COOKIE_NAME = "kasbokar_panel"
MAX_ACTIONS_PER_SESSION = 200  # سقفِ نوشتن در یکِ نشست (دیوارِ در مقابلِ اسکریپتِ پرسرعت)
STOCK_MAX = 1_000_000
PRICE_MAX = 5_000_000_000
_USER_AGENT_MAX = 120

ACTIONS: frozenset[str] = frozenset(
    {"product_toggle_active", "product_set_stock", "product_set_price", "order_next_step"}
)


def enabled() -> bool:
    """پنلِ نوشتنی بدونِ `WEB_PANEL_SECRET` وجود ندارد (مسیرها ۴۰۴ می‌شوند)."""
    return bool((settings.panel_secret or "").strip())


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sign(payload: str) -> str:
    return hmac.new(settings.panel_secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def _equals(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


def cookie_value(row_id: int) -> str:
    return f"{row_id}.{_sign(f'cookie:{row_id}')[:32]}"


def csrf_token(row_id: int) -> str:
    return _sign(f"csrf:{row_id}")[:32]


def parse_cookie(raw: str | None) -> int | None:
    """شناسه فقط وقتی برمی‌گردد که امضایِ همان شناسه با کلیدِ همین استقرار بسازد."""
    if not raw or not enabled() or "." not in raw:
        return None
    head, _, tail = raw.partition(".")
    if not head.isdigit():
        return None
    if not _equals(tail, _sign(f"cookie:{head}")[:32]):
        return None
    return int(head)


def csrf_ok(row_id: int, provided: str | None) -> bool:
    return bool(provided) and _equals(provided or "", csrf_token(row_id))


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _expiry(seconds: int) -> datetime.datetime:
    return _now() + datetime.timedelta(seconds=seconds)


async def issue_link(session: AsyncSession, owner_telegram_id: int, base_url: str) -> str | None:
    """لینکِ تازه می‌سازد و ردیفش را می‌نویسد؛ بی‌آدرسِ پایه یا بی‌کلید ⇒ None (صادق، نه لینکِ شکسته)."""
    if not enabled() or not (base_url or "").strip():
        return None
    token = secrets.token_urlsafe(32)
    session.add(
        WebPanelSession(
            owner_telegram_id=owner_telegram_id,
            token_hash=_digest(token),
            expires_at=_expiry(LINK_TTL_SECONDS),
        )
    )
    await session.flush()
    return f"{base_url.rstrip('/')}/web/login?t={token}"


async def redeem(session: AsyncSession, raw_token: str | None, *, user_agent: str = "") -> WebPanelSession | None:
    """لینک را به نشست تبدیل می‌کند: یک‌بار، پیش ازِ مهلت، و ابطال‌نشده. مهلتِ نشست از همین لحظه است."""
    if not raw_token or not enabled():
        return None
    row = (
        await session.execute(select(WebPanelSession).where(WebPanelSession.token_hash == _digest(raw_token)))
    ).scalar_one_or_none()
    if row is None or row.used_at is not None or row.revoked_at is not None or row.expires_at <= _now():
        return None
    row.used_at = _now()
    row.expires_at = _expiry(SESSION_TTL_SECONDS)
    row.last_seen_at = row.used_at
    row.user_agent = (user_agent or "")[:_USER_AGENT_MAX]
    await session.flush()
    return row


async def load_session(session: AsyncSession, row_id: int) -> WebPanelSession | None:
    """ردیفِ نشستِ زنده (ساخته‌شده از کوکیِ امضاشده) یا None."""
    row = await session.get(WebPanelSession, row_id)
    if row is None or row.used_at is None or row.revoked_at is not None or row.expires_at <= _now():
        return None
    return row


async def touch(session: AsyncSession, row: WebPanelSession) -> None:
    row.last_seen_at = _now()
    await session.flush()


async def revoke_for_owner(session: AsyncSession, owner_telegram_id: int) -> int:
    now = _now()
    result = await session.execute(
        update(WebPanelSession)
        .where(
            WebPanelSession.owner_telegram_id == owner_telegram_id,
            WebPanelSession.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    return int(result.rowcount or 0)


async def active_links(session: AsyncSession, owner_telegram_id: int) -> list[WebPanelSession]:
    rows = (
        await session.execute(
            select(WebPanelSession)
            .where(
                WebPanelSession.owner_telegram_id == owner_telegram_id,
                WebPanelSession.revoked_at.is_(None),
                WebPanelSession.expires_at > _now(),
            )
            .order_by(WebPanelSession.id.desc())
            .limit(10)
        )
    ).scalars().all()
    return list(rows)


async def shop_for_owner(session: AsyncSession, owner_telegram_id: int) -> ShopBot | None:
    """فروشگاهِ همین فروشگاه‌دار (یک‌به‌یک؛ همان کمکی که پنلِ تلگرام استفاده می‌کند)."""
    owner = (
        await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == owner_telegram_id))
    ).scalar_one_or_none()
    if owner is None:
        return None
    return await shop_bot_service.get_by_owner(session, owner)


async def apply_action(
    session: AsyncSession,
    *,
    row: WebPanelSession,
    shop_bot: ShopBot,
    action: str,
    target_id: int,
    value: int | None = None,
) -> tuple[bool, str]:
    """یکِ فعلِ مجاز رویِ یکِ ردیفِ *همین* فروشگاه. خروجی: (موفق، دلیلِ کوتاه برایِ لاگ).

    مالکیت از سرویسِ خودِ ردیف می‌آید (`get_owned_by_id`)، نه از ورودیِ فرم؛ پس حدس‌زدنِ شناسهٔ
    فروشگاهِ دیگر فقط «پیدا نشد» می‌گیرد. نوشتنِ موجودی با `lock_for_update` است ⇒ همان قفلی که دو
    مشتریِ هم‌زمان هم رویش رقابت می‌کنند. هیچ commit اینجا انجام نمی‌شود (لایهٔ وب بعد ازِ موفقیت).
    """
    if action not in ACTIONS:
        return False, "action-not-allowed"
    if row.actions_count >= MAX_ACTIONS_PER_SESSION:
        return False, "session-limit"

    if action == "order_next_step":
        order = await order_service.get_owned_by_id(session, target_id, shop_bot.id)
        if order is None:
            return False, "not-found"
        step = order_state.next_step(order.status)
        if step is None:
            return False, "no-next-step"
        result = await order_transition_service.transition_group(
            session, order, step, actor_type="owner", actor_ref=str(row.owner_telegram_id), reason="web-panel"
        )
        if not result.ok:
            return False, f"illegal:{result.reason}"
        await _finish(session, row, shop_bot.id, action, order.id, f"{result.from_status}->{result.to_status}")
        return True, f"{result.from_status}->{result.to_status}"

    product = await product_service.get_owned_by_id(session, target_id, shop_bot.id)
    if product is None:
        return False, "not-found"

    if action == "product_toggle_active":
        product.is_active = not product.is_active
        await session.flush()
        await _finish(session, row, shop_bot.id, action, product.id, "active" if product.is_active else "inactive")
        return True, "active" if product.is_active else "inactive"

    if value is None:
        return False, "value-required"
    if action == "product_set_stock":
        if not 0 <= value <= STOCK_MAX:
            return False, "value-range"
        locked = await product_service.lock_for_update(session, product.id)
        if locked is None:
            return False, "not-found"
        locked.stock_quantity = value
        await session.flush()
        await _finish(session, row, shop_bot.id, action, locked.id, str(value))
        return True, "stock"
    if action == "product_set_price":
        if not 1 <= value <= PRICE_MAX:
            return False, "value-range"
        product.price_toman = value
        await session.flush()
        await _finish(session, row, shop_bot.id, action, product.id, str(value))
        return True, "price"
    return False, "action-not-allowed"


async def _finish(
    session: AsyncSession, row: WebPanelSession, shop_bot_id: int, action: str, target: object, detail: str
) -> None:
    """شمارندهٔ نشست + یکِ ردیفِ ممیزی با زنجیرهٔ هش برایِ هرِ نوشتنِ وب."""
    row.actions_count += 1
    await session.flush()
    await audit_log_service.log(
        session,
        AuditEventType.WEB_PANEL_ACTION,
        shop_bot_id=shop_bot_id,
        actor_telegram_id=row.owner_telegram_id,
        details=f"{action} target={target} value={detail}",
    )
