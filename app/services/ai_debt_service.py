"""دفترِ بدهیِ مصرفِ هوش مصنوعی (P33-C).

مسئله: سوییچِ «ادامهٔ سفارش با اعتبارِ صفر» (P30-C) فروش را باز می‌گذارد، ولی کسرِ هزینهٔ AI
ناموفق می‌ماند و `wallet_service.deduct` فقط لاگِ هشدار می‌زد ⇒ هزینهٔ واقعیِ پلتفرم بی‌ثبت
و سقفِ بدهی هم فقط کمیسیون را می‌دید. این دفتر همان هزینه را ثبت می‌کند تا:
* ادمین ببیند چه کسی چقدر مصرفِ پرداخت‌نشده دارد،
* `order_access_service` سقف را با **مجموعِ** بدهی (کمیسیون + AI) بسنجد، نه فقط کمیسیون.

وصولِ خودکار عمدًا اینجا نیست (تصمیمِ محصول: آیا از شارژِ بعدی کسر شود یا دستی). ادمین می‌تواند
`waive` کند و ردیف هرگز حذف نمی‌شود — مثلِ دفترِ کمیسیون.
"""
from __future__ import annotations

import datetime as dt
import secrets
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import AiUsageDebt, ShopOwner

OPEN = "open"
WAIVED = "waived"


async def record(
    session: AsyncSession, *, owner_id: int, amount_toman: int, reason: str, note: str | None = None
) -> str | None:
    """یکِ مصرفِ پرداخت‌نشده ثبت می‌کند. `None` یعنی مبلغِ نامعتبر بود."""
    amount = int(amount_toman or 0)
    if amount <= 0:
        return None
    key = f"ai-debt:{secrets.token_hex(12)}"
    try:
        # savepoint: قیدِ یکتا فقط همین درج را لغو می‌کند، نه کلِ تراکنشِ خواننده.
        async with session.begin_nested():
            session.add(
                AiUsageDebt(
                    shop_owner_id=owner_id,
                    amount_toman=amount,
                    reason=str(reason)[:32],
                    status=OPEN,
                    note=(note or "")[:180] or None,
                    idempotency_key=key,
                )
            )
    except IntegrityError:
        return None
    await session.flush()
    return key


async def open_totals_by_owner(session: AsyncSession, owner_ids: set[int]) -> dict[int, int]:
    """جمعِ بدهیِ بازِ AI به‌ازایِ هر فروشگاه، در یکِ کوئری (همان قاعدهٔ P29: نه حلقهٔ per-shop)."""
    if not owner_ids:
        return {}
    rows = await session.execute(
        select(AiUsageDebt.shop_owner_id, func.sum(AiUsageDebt.amount_toman))
        .where(AiUsageDebt.status == OPEN, AiUsageDebt.shop_owner_id.in_(owner_ids))
        .group_by(AiUsageDebt.shop_owner_id)
    )
    return {int(owner_id): int(total or 0) for owner_id, total in rows.all()}


async def open_total_for_owner(session: AsyncSession, owner_id: int) -> int:
    return int((await open_totals_by_owner(session, {owner_id})).get(int(owner_id), 0))


async def summary(session: AsyncSession) -> dict[str, Any]:
    row = (
        await session.execute(
            select(
                func.count().filter(AiUsageDebt.status == OPEN),
                func.coalesce(func.sum(AiUsageDebt.amount_toman).filter(AiUsageDebt.status == OPEN), 0),
                func.count().filter(AiUsageDebt.status == WAIVED),
            )
        )
    ).one()
    return {"open_count": int(row[0] or 0), "open_toman": int(row[1] or 0), "waived_count": int(row[2] or 0)}


async def open_report(session: AsyncSession, limit: int = 10) -> list[dict[str, Any]]:
    """بدهی‌هایِ بازِ AI با نامِ صاحبِ فروشگاه، بزرگ‌ترین اول (کنارِ گزارشِ کمیسیون)."""
    result = await session.execute(
        select(AiUsageDebt, ShopOwner.first_name, ShopOwner.last_name, ShopOwner.telegram_id)
        .join(ShopOwner, ShopOwner.id == AiUsageDebt.shop_owner_id)
        .where(AiUsageDebt.status == OPEN)
        .order_by(AiUsageDebt.amount_toman.desc(), AiUsageDebt.id)
        .limit(limit)
    )
    rows: list[dict[str, Any]] = []
    for debt, first_name, last_name, telegram_id in result.all():
        rows.append(
            {
                "id": int(debt.id),
                "amount_toman": int(debt.amount_toman),
                "reason": debt.reason,
                "owner_label": " ".join(part for part in (first_name, last_name) if part) or str(telegram_id),
            }
        )
    return rows


async def waive(session: AsyncSession, *, debt_id: int, note: str) -> bool:
    """بخشودنِ یکِ بدهیِ AI (تصمیمِ دستیِ ادمین) — سابقه می‌ماند."""
    result = await session.execute(
        update(AiUsageDebt)
        .where(AiUsageDebt.id == debt_id, AiUsageDebt.status == OPEN)
        .values(status=WAIVED, note=note[:180], settled_at=dt.datetime.now(dt.timezone.utc))
    )
    await session.flush()
    return int(result.rowcount or 0) == 1
