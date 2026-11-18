"""پ۱۱۷ · دو یافتهٔ بازرسیِ ۱۴۰۵-۰۸-۱۴ که به «قفل» و «وضعیتِ سفارش» دست می‌زدند.

یافتهٔ ۸ (انقضایِ گروهی): `expire_stale_reservations` ردیفِ منقضی‌شده را مستقیم EXPIRED می‌کرد.
در سبدِ چندقلمی گروه رویِ {expired, pending} می‌ماند و چون EXPIRED پایانی است، قلمِ باقی‌مانده
دیگر هیچ‌وقت تایید/رد نمی‌شد. درمان: گذارِ اتمیِ کلِ گروه با `transition_group` (رویداد + آزادسازیِ
رزروِ خودکار). اگر گروه قابلِ گذار نبود (مثلاً یکِ قلمِ تاییدشده در همان سبد) وضعیت دست‌نخورده
می‌ماند ولی رزروِ همان ردیف آزاد می‌شود و در لاگ دلیلش نوشته می‌شود.

یافتهٔ ۶ (حلقهٔ مرگِ قفل): `deduct`/`add_charge` اولِ `wallet_charges` را قفل می‌کردند بعدِ
`shop_owners`، ولی `commission_service.settle` و دریافتِ کمیسیون اولِ owner را قفل می‌کردند بعدِ
deduct ⇒ دو ترتیبِ مخالف در همان ساحب. درمان: ترتیبِ یکتایِ سراسری «اولِ ShopOwner، بعدِ
WalletCharge» — با یکِ `SELECT … FOR UPDATE` رویِ ردیفِ صاحبِ فروشگاه در ابتدایِ هر دو تابع.

ادعاها:
۱. گروهِ منقضی‌شده **کاملاً** EXPIRED می‌شود (نه فقط ردیفِ رزروشده) و رویدادِ وضعیت ثبت می‌شود.
۲. اجرایِ دوبارهٔ جارو بی‌اثر است (ایدبمپوتنت).
۳. گروهی که خواهرِ تاییدشده دارد: وضعیت‌ها دست‌نخورده، ولی رزرو آزاد می‌شود و دیگر انتخاب نمی‌شود.
۴. دو تراکنشِ هم‌زمان (کسرِ کیف‌پول در برابرِ تسویهٔ کمیسیون) رویِ یکِ صاحبِ فروشگاه: بدونِ
   `DeadlockDetected`، هر دو ردیفِ دفتری می‌مانند و موجودیِ کش‌شده با دفتر می‌خواند.

اجرا: python3 tests_manual/run_one.py test_p117_lock_order_and_expiry.py
"""
from __future__ import annotations

import asyncio
import datetime as dt
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from decimal import Decimal

from sqlalchemy import func, select  # noqa: E402

from app.database.models import (  # noqa: E402
    OrderConsultation,
    OrderEvent,
    OrderStatus,
    ShopOwner,
    WalletTransactionReason,
)
from app.database.session import session_scope  # noqa: E402
from app.services import (  # noqa: E402
    commission_service,
    order_service,
    order_state,
    order_transition_service,
    wallet_service,
)
from app.services.admin_settings_service import get_admin_settings  # noqa: E402
from harness import reset_database  # noqa: E402
from phase4_helpers import add_customer, add_order, owner_balance, wallet_transactions  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

OWNER_TG = 11_700_001
SHOP_TG = 11_700_002
CUSTOMER_TG = 11_700_003
PAST = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=30)


_SHOP_BOT_ID: int | None = None
_CUSTOMER_ID: int | None = None


async def _make_group(group: str, *, sibling_status: OrderStatus | None = None) -> list[int]:
    """یکِ سبدِ دو قلمی: قلمِ اول رزروِ منقضی‌شده، قلمِ دوم بی‌رزرو (یا با وضعیتِ خواسته‌شده).

    فروشگاه و مشتری یک‌بار ساخته می‌شوند؛ هر گروه فقط ردیفِ سفارشِ تازه دارد (تازه‌سازیِ
    فروشگاه با همان توکن، مشتریِ تکراری می‌ساخت).
    """
    global _SHOP_BOT_ID, _CUSTOMER_ID
    if _SHOP_BOT_ID is None:
        _SHOP_BOT_ID = await seed_usable_shop(OWNER_TG, SHOP_TG)
        _CUSTOMER_ID = await add_customer(_SHOP_BOT_ID, CUSTOMER_TG)
    shop_bot_id, customer_id = _SHOP_BOT_ID, _CUSTOMER_ID
    ids = [
        await add_order(
            shop_bot_id, customer_id, status=OrderStatus.PENDING, value=100_000, group_id=group, summary="قلمِ ۱"
        )
    ]
    ids.append(
        await add_order(
            shop_bot_id,
            customer_id,
            status=sibling_status or OrderStatus.PENDING,
            value=50_000,
            group_id=group,
            summary="قلمِ ۲",
        )
    )
    async with session_scope() as session:
        first = await session.get(OrderConsultation, ids[0])
        first.stock_reserved = True
        first.reservation_expires_at = PAST
        await session.commit()
    return ids


async def _statuses(group: str) -> dict[int, str]:
    async with session_scope() as session:
        rows = (
            await session.execute(select(OrderConsultation).where(OrderConsultation.cart_checkout_group_id == group))
        ).scalars().all()
        return {int(r.id): order_state.value_of(r.status) for r in rows}


async def _reservation_state(order_id: int) -> tuple[bool, object]:
    async with session_scope() as session:
        row = await session.get(OrderConsultation, order_id)
        return bool(row.stock_reserved), row.reservation_expires_at


async def test_expiry_closes_the_whole_group() -> None:
    group = "p117group-a"
    ids = await _make_group(group)
    async with session_scope() as session:
        expired = await order_service.expire_stale_reservations(session)
        await session.commit()
    assert len(expired) == 2, [o.id for o in expired]
    statuses = await _statuses(group)
    assert set(statuses.values()) == {order_state.EXPIRED}, statuses
    reserved, _expires_at = await _reservation_state(ids[0])
    assert reserved is False, "رزروِ قلمِ منقضی‌شده باید آزاد شده باشد"
    async with session_scope() as session:
        events = (
            await session.execute(
                select(func.count(OrderEvent.id)).where(
                    OrderEvent.order_id.in_(ids), OrderEvent.to_status == order_state.EXPIRED
                )
            )
        ).scalar_one()
    assert events == 1, f"گذارِ گروهی یکِ رویدادِ وضعیت برایِ گروه می‌نویسد (رویِ ردیفِ اول)؛ دیده شد {events}"
    print("✅ test_expiry_closes_the_whole_group PASSED")


async def test_expiry_sweep_is_idempotent() -> None:
    async with session_scope() as session:
        again = await order_service.expire_stale_reservations(session)
        await session.commit()
    assert again == [], [o.id for o in again]
    print("✅ test_expiry_sweep_is_idempotent PASSED")


async def test_confirmed_sibling_is_not_rewritten_but_stock_is_released() -> None:
    group = "p117group-b"
    ids = await _make_group(group, sibling_status=OrderStatus.CONFIRMED)
    async with session_scope() as session:
        expired = await order_service.expire_stale_reservations(session)
        await session.commit()
    assert expired == [], "گروهی که قلمِ تاییدشده دارد نباید با جارو EXPIRED شود"
    statuses = await _statuses(group)
    assert order_state.PENDING in set(statuses.values()) and order_state.CONFIRMED in set(statuses.values()), statuses
    reserved, expires_at = await _reservation_state(ids[0])
    assert reserved is False, "رزرو باید آزاد می‌شد تا موجودی قفلِ ابدی نماند"
    assert expires_at is None, expires_at
    async with session_scope() as session:
        again = await order_service.expire_stale_reservations(session)
        await session.commit()
    assert again == [], "ردیفِ آزادشده نباید دوباره انتخاب شود"
    print("✅ test_confirmed_sibling_is_not_rewritten_but_stock_is_released PASSED")


async def test_concurrent_wallet_and_commission_do_not_deadlock() -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG, SHOP_TG)
    customer_id = await add_customer(shop_bot_id, CUSTOMER_TG)
    group = "p117group-c"
    await add_order(
        shop_bot_id, customer_id, status=OrderStatus.AWAITING_PAYMENT, value=200_000, group_id=group, summary="کیف"
    )
    async with session_scope() as session:
        admin = await get_admin_settings(session)
        admin.commission_enabled = True
        admin.commission_percent = Decimal("2.00")
        rows = list(
            (
                await session.execute(
                    select(OrderConsultation).where(OrderConsultation.cart_checkout_group_id == group)
                )
            ).scalars().all()
        )
        await order_transition_service.apply_commission(session, rows, "awaiting_payment")
        await session.commit()

    async def _deduct(task_no: int) -> None:
        async with session_scope() as session:
            owner = (
                await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == OWNER_TG))
            ).scalar_one()
            await wallet_service.deduct(
                session, owner, 1_000, WalletTransactionReason.CHAT_MESSAGE, idempotency_key=f"p117:deduct:{task_no}"
            )
            await session.commit()

    async def _settle() -> None:
        async with session_scope() as session:
            admin = await get_admin_settings(session)
            owner = (
                await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == OWNER_TG))
            ).scalar_one()
            rows = list(
                (
                    await session.execute(
                        select(OrderConsultation).where(OrderConsultation.cart_checkout_group_id == group)
                    )
                ).scalars().all()
            )
            await commission_service.settle(
                session,
                owner_id=int(owner.id),
                group_key=group,
                rows=rows,
                admin_settings=admin,
                now=dt.datetime.now(dt.timezone.utc),
            )
            await session.commit()

    start = await owner_balance(OWNER_TG)
    results = await asyncio.gather(_deduct(1), _settle(), _deduct(2), _settle(), return_exceptions=True)
    errors = [r for r in results if isinstance(r, BaseException)]
    assert not errors, [f"{type(e).__name__}: {e}" for e in errors]
    deadlocks = [e for e in errors if "40P01" in str(e) or "deadlock" in str(e).lower()]
    assert not deadlocks, deadlocks

    rows = await wallet_transactions()
    chat_rows = [r for r in rows if r.reason == WalletTransactionReason.CHAT_MESSAGE]
    commission_rows = [r for r in rows if r.reason == WalletTransactionReason.COMMISSION]
    assert len(chat_rows) == 2, len(chat_rows)
    # ردیفِ `comm-reserved:` یکِ نشانهٔ صفرمقدارِ رزرو است، نه تسویه؛ تسویه با `comm-settle:` می‌آید.
    settle_rows = [r for r in commission_rows if (r.idempotency_key or "").startswith("comm-settle:")]
    assert len(settle_rows) == 1, [
        (r.idempotency_key, int(r.amount_toman)) for r in commission_rows
    ]
    assert int(settle_rows[0].amount_toman) < 0, settle_rows[0].amount_toman

    balance = await owner_balance(OWNER_TG)
    expected = start - 2_000 + int(settle_rows[0].amount_toman)
    assert balance == expected, (start, balance, expected)
    print("✅ test_concurrent_wallet_and_commission_do_not_deadlock PASSED")


async def main() -> None:
    await reset_database()
    await test_expiry_closes_the_whole_group()
    await test_expiry_sweep_is_idempotent()
    await test_confirmed_sibling_is_not_rewritten_but_stock_is_released()
    await test_concurrent_wallet_and_commission_do_not_deadlock()
    await asyncio.sleep(0)


if __name__ == "__main__":
    asyncio.run(main())
