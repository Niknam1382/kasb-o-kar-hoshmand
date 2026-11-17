"""عملیاتِ گروهیِ ادمین: هدیه‌یِ اعتبار (K1) و تمدیدِ روزِ اشتراک (K2) — پیش‌نمایش ← تایید ← اجرا.

مجموعه‌یِ هدف موقعِ *پیش‌نمایش* منجمد می‌شه (owner_ids در params)؛ اجرا همان‌ها رو می‌زنه، نه یک فیلترِ دوباره‌خوانده‌شده.
ایدمپوتنسی: `batch_id` یکتا + یک ردیفِ AdminCreditBatchItem (UNIQUE) به‌ازایِ هر فروشگاه‌دار که با اثرش هم‌تراکنش
(savepoint) ثبت می‌شه ⇒ دابل‌تپ/کرشِ وسطِ کار/اجرایِ دوباره هیچ اثرِ دومی ندارد و ادامه‌پذیر است."""

from __future__ import annotations

import datetime
import json
import secrets
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    AdminCreditBatch,
    AdminCreditBatchItem,
    ShopOwner,
    Subscription,
    SubscriptionStatus,
    WalletTransactionReason,
)
from app.services import wallet_service

MAX_TARGETS = 2000
GIFT_MIN_TOMAN, GIFT_MAX_TOMAN = 1_000, 10_000_000
EXTEND_MIN_DAYS, EXTEND_MAX_DAYS = 1, 365
GIFT_VALIDITY_MIN_MONTHS, GIFT_VALIDITY_MAX_MONTHS = 1, 24

FILTERS: dict[str, str] = {
    "all": "همه‌یِ فروشگاه‌دارها",
    "active": "اشتراکِ فعال/آزمایشی",
    "expiring": "اشتراکی که تا ۷ روزِ دیگه تموم می‌شه",
}


@dataclass
class BatchResult:
    batch: AdminCreditBatch | None
    changed: bool = False
    applied_owner_ids: list[int] = field(default_factory=list)
    skipped: int = 0


async def _latest_subscriptions(session: AsyncSession) -> dict[int, Subscription]:
    latest = select(Subscription.shop_owner_id, func.max(Subscription.id).label("max_id")).group_by(Subscription.shop_owner_id).subquery()
    rows = (await session.execute(select(Subscription).join(latest, Subscription.id == latest.c.max_id))).scalars().all()
    return {s.shop_owner_id: s for s in rows}


async def select_owner_ids(session: AsyncSession, flt: str, *, allowed_owner_ids: set[int] | None = None) -> list[int]:
    """مجموعهٔ هدف. `allowed_owner_ids` (P21-F): دامنهٔ ادمینِ عملیاتی — None ⇒ همه.

    عملیاتِ گروهی دقیقاً همان جایی بود که «دامنه» معنا دارد: دکمهٔ «🎁 هدیه‌یِ اعتبار (گروهی)» برایِ
    هر ادمین نمایش داده می‌شود، پس بدونِ این فیلتر یکِ ادمینِ دامنه‌دار می‌توانست به ۲۰۰۰
    فروشگاه‌دارِ کلِ پلتفرم اعتبار هدیه بدهد.
    """
    owner_ids = list((await session.execute(select(ShopOwner.id).order_by(ShopOwner.id))).scalars().all())
    if allowed_owner_ids is not None:
        owner_ids = [i for i in owner_ids if i in allowed_owner_ids]
    if flt == "all":
        return owner_ids
    subs = await _latest_subscriptions(session)
    now = datetime.datetime.now(datetime.timezone.utc)
    if flt == "active":
        return [i for i in owner_ids if i in subs and subs[i].status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL)]
    if flt == "expiring":
        horizon = now + datetime.timedelta(days=7)
        return [
            i for i in owner_ids
            if i in subs and subs[i].status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL) and subs[i].end_date <= horizon
        ]
    return []


async def create_batch(
    session: AsyncSession,
    *,
    kind: str,
    flt: str,
    by: str,
    amount: int | None = None,
    validity_months: int | None = None,
    days: int | None = None,
    allowed_owner_ids: set[int] | None = None,
) -> AdminCreditBatch | None:
    """None وقتی پارامتر نامعتبر یا هدف خالی/بیشتر از سقف باشه."""
    if flt not in FILTERS:
        return None
    if kind == "gift":
        if amount is None or not (GIFT_MIN_TOMAN <= amount <= GIFT_MAX_TOMAN):
            return None
        if validity_months is not None and not (GIFT_VALIDITY_MIN_MONTHS <= validity_months <= GIFT_VALIDITY_MAX_MONTHS):
            return None
        params: dict = {"amount": amount, "validity_months": validity_months}
    elif kind == "extend":
        if days is None or not (EXTEND_MIN_DAYS <= days <= EXTEND_MAX_DAYS):
            return None
        params = {"days": days}
    else:
        return None
    owner_ids = await select_owner_ids(session, flt, allowed_owner_ids=allowed_owner_ids)
    if not owner_ids or len(owner_ids) > MAX_TARGETS:
        return None
    params.update({"filter": flt, "owner_ids": owner_ids})
    batch = AdminCreditBatch(
        batch_id=secrets.token_hex(8),
        kind=kind,
        params_json=json.dumps(params),
        status="previewed",
        target_count=len(owner_ids),
        created_by=by[:64],
    )
    session.add(batch)
    await session.flush()
    return batch


def params_of(batch: AdminCreditBatch) -> dict:
    try:
        data = json.loads(batch.params_json)
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


async def get_batch(session: AsyncSession, batch_id: str, *, lock: bool = False) -> AdminCreditBatch | None:
    query = select(AdminCreditBatch).where(AdminCreditBatch.batch_id == batch_id)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    return (await session.execute(query)).scalar_one_or_none()


async def cancel(session: AsyncSession, batch_id: str) -> bool:
    batch = await get_batch(session, batch_id, lock=True)
    if batch is None or batch.status != "previewed":
        return False
    batch.status = "cancelled"
    await session.flush()
    return True


async def _apply_one(session: AsyncSession, batch: AdminCreditBatch, params: dict, owner: ShopOwner, subs: dict[int, Subscription]) -> bool:
    if batch.kind == "gift":
        await wallet_service.add_charge(
            session,
            owner,
            int(params["amount"]),
            WalletTransactionReason.ADMIN_GRANT,
            validity_months=params.get("validity_months"),
            reference=f"batch:{batch.batch_id}",
            merge_into_latest=True,  # P42 · موردِ ۵: هدیه به دیرترین شارژِ زنده اضافه می‌شود
        )
        return True
    # P42 · موردِ ۵: «تمدیدِ روز» در دنیایِ امروزِ پلتفرم یعنی جابه‌جاکردنِ انقضایِ *همهٔ*
    # بسته‌هایِ اعتبار، چون بیشترِ فروشگاه‌ها ردیفِ Subscription ندارند (مدلِ مصرفِ اعتبار).
    # تا پیشِ این، نبودنِ همان ردیف یعنی `False` ⇒ «۰ اعمال، ۱ رد».
    extended_lots = await wallet_service.extend_live_charges(session, owner, int(params["days"]))
    sub = subs.get(owner.id)
    if sub is None or sub.status == SubscriptionStatus.EXPIRED:
        return bool(extended_lots)
    sub.end_date = sub.end_date + datetime.timedelta(days=int(params["days"]))
    if sub.status == SubscriptionStatus.GRACE and sub.end_date > datetime.datetime.now(datetime.timezone.utc):
        sub.status = SubscriptionStatus.ACTIVE
        sub.grace_reminder_sent = False
    return True


async def execute(session: AsyncSession, batch_id: str, *, by: str) -> BatchResult:
    """اجرایِ دسته. `done`/`cancelled` ⇒ بدونِ اثر. `running` (کرشِ قبلی) ادامه می‌ده؛ ردیف‌هایِ انجام‌شده رد می‌شن."""
    batch = await get_batch(session, batch_id, lock=True)
    if batch is None:
        return BatchResult(None)
    if batch.status in ("done", "cancelled"):
        return BatchResult(batch, changed=False)
    params = params_of(batch)
    batch.status = "running"
    await session.flush()
    subs = await _latest_subscriptions(session) if batch.kind == "extend" else {}
    applied: list[int] = []
    skipped = 0
    for owner_id in params.get("owner_ids", []):
        owner = await session.get(ShopOwner, owner_id)
        if owner is None:
            skipped += 1
            continue
        try:
            async with session.begin_nested():
                session.add(AdminCreditBatchItem(batch_id=batch.batch_id, shop_owner_id=owner_id))
                await session.flush()  # UNIQUE: قبلاً انجام شده ⇒ IntegrityError و rollbackِ savepoint
                if await _apply_one(session, batch, params, owner, subs):
                    applied.append(owner_id)
                else:
                    skipped += 1
                    raise _Skip()
        except IntegrityError:
            skipped += 1
        except _Skip:
            pass
    total_items = (
        await session.execute(select(func.count()).select_from(AdminCreditBatchItem).where(AdminCreditBatchItem.batch_id == batch.batch_id))
    ).scalar_one()
    batch.status = "done"
    batch.applied_count = int(total_items)
    batch.skipped_count = batch.target_count - int(total_items)
    batch.executed_at = datetime.datetime.now(datetime.timezone.utc)
    await session.flush()
    return BatchResult(batch, changed=True, applied_owner_ids=applied, skipped=batch.skipped_count)


class _Skip(Exception):
    """رد کردنِ یک فروشگاه‌دار بدونِ اثر: savepoint rollback می‌شه (ردیفِ item هم برنمی‌ماند تا بعداً قابلِ تلاش باشه)."""
