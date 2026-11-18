"""پ۱۱۹ · تحویلِ اعلان بی‌قفلِ طولانی + تجمیعِ UPDATEهایِ انقضا + دامنهٔ اجرایِ دستهٔ ادمین.

سه بازماندهٔ یافته‌هایِ ۵ و ۱۲ِ بازرسی که در پ۱۱۸ عمداً باز گذاشته شدند:

۱. `notification_service.send_due` تا ۲۰۰ ارسالِ شبکه‌ای را داخلِ یکِ تراکنشِ `FOR UPDATE`
   انجام می‌داد ⇒ قفلِ ردیف‌ها تا دقیقه‌ها باز می‌ماند و کرش/خطا پیش ازِ commit یعنی
   «هیچ وضعیتی ثبت نشده ⇒ همهٔ ۲۰۰ تا دوباره». حالا ردیف‌ها با وضعیتِ `sending` و یکِ
   مهلتِ کوتاه رزرو و commit می‌شوند و نتیجهٔ هر ردیف جدا commit می‌شود؛ ردیفِ گیرکرده در
   `sending` بعد ازِ مهلت به صفِ عادی برمی‌گردد.
۲. `wallet_service.expire_stale_charges` به‌ازایِ هر بسته یکِ `UPDATE shop_owners` می‌زد؛ حالا
   یکِ UPDATE به‌ازایِ هر صاحبِ حساب (جمعِ بسته‌ها) — با شمارشِ واقعیِ statement سنجیده می‌شود.
۳. پیش‌نمایشِ دستهٔ اعتبارِ ادمین دامنه را می‌دید ولی **اجرا/انصراف** هیچ بازبینیِ دامنه‌ای
   نداشت ⇒ `_outside_actor_scope`: دستهٔ ادمینِ دیگر، یا هدفی بیرونِ دامنه ⇒ رد.

اجرا: python3 tests_manual/run_one.py test_p119_outbox_lease_and_bounds.py
"""
from __future__ import annotations

import asyncio
import contextlib
import datetime as dt
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from sqlalchemy import event, select  # noqa: E402

from harness import reset_database  # noqa: E402
from phase4_helpers import owner_balance, wallet_transactions  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot.handlers.admin_time import _outside_actor_scope  # noqa: E402
from app.database.models import AdminRole, Notification, ShopOwner, WalletCharge, WalletTransactionReason  # noqa: E402
from app.database.session import engine, session_scope  # noqa: E402
from app.services import (  # noqa: E402
    admin_role_service,
    credit_batch_service,
    notification_service,
    wallet_service,
)

OWNER_TG = 11_900_001
SHOP_TG = 11_900_002
OTHER_OWNER_TG = 11_900_003
OTHER_SHOP_TG = 11_900_004
CUSTOMER_TG = 11_900_005
OPERATOR_TG = 11_900_006
OTHER_OPERATOR_TG = 11_900_007


class _SendBot:
    def __init__(self, *, fail_with: Exception | None = None) -> None:
        self.sent: list[tuple[int, str]] = []
        self.fail_with = fail_with

    async def send_message(self, chat_id: int, text: str):
        if self.fail_with is not None:
            raise self.fail_with
        self.sent.append((int(chat_id), text))
        return None


class _Manager:
    def __init__(self, bots: dict[int, _SendBot]) -> None:
        self.bots = bots

    def customer_bot(self, shop_bot_id: int, platform: str | None) -> _SendBot | None:
        return self.bots.get(shop_bot_id)


@contextlib.contextmanager
def _counted():
    seen: list[str] = []

    def _listener(_conn, _cursor, statement, _params, _context, _executemany):
        seen.append(" ".join(statement.split()))

    event.listen(engine.sync_engine, "before_cursor_execute", _listener)
    try:
        yield seen
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", _listener)


async def _only_notification() -> Notification:
    async with session_scope() as session:
        return (await session.execute(select(Notification))).scalars().one()


# ============================================================================= ۱ — رزرو، commit، مهلت
async def test_send_due_commits_per_row_and_reclaims_lease() -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG, SHOP_TG)
    async with session_scope() as session:
        assert await notification_service.enqueue(session, CUSTOMER_TG, "خبرِ الف", shop_bot_id=shop_bot_id)
        await session.commit()

    failing = _SendBot(fail_with=RuntimeError("۵۰۳ — سرویس در دسترس نیست"))
    async with session_scope() as session:
        summary = await notification_service.send_due(session, _Manager({shop_bot_id: failing}), None)
    assert summary == {"sent": 0, "retrying": 1, "failed": 0}, summary

    # وضعیتِ شکست همان‌جا commit شده (پیش‌تر تا پایانِ حلقه در حافظهٔ تراکنشِ قفل‌دار می‌ماند)
    row = await _only_notification()
    assert row.status == notification_service.PENDING and row.attempts == 1, (row.status, row.attempts)
    assert row.next_attempt_at > dt.datetime.now(dt.timezone.utc), "backoff ثبت نشد"

    # «کرشِ وسطِ ارسال» ⇒ ردیف در `sending` می‌ماند؛ با گذشتِ مهلت، دورِ بعد خودش را می‌گیرد
    async with session_scope() as session:
        row = (await session.execute(select(Notification))).scalars().one()
        row.status = notification_service.SENDING
        row.next_attempt_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=1)
        await session.commit()

    good = _SendBot()
    async with session_scope() as session:
        summary = await notification_service.send_due(session, _Manager({shop_bot_id: good}), None)
    assert summary["sent"] == 1, summary
    assert good.sent == [(CUSTOMER_TG, "خبرِ الف")], good.sent
    row = await _only_notification()
    assert row.status == notification_service.SENT and row.sent_at is not None, row.status
    print("✅ test_send_due_commits_per_row_and_reclaims_lease PASSED")


# ============================================================================= ۲ — بی‌ربات ⇒ صف نمی‌سوزد
async def test_missing_bot_never_marks_failed() -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG, SHOP_TG)
    async with session_scope() as session:
        assert await notification_service.enqueue(session, CUSTOMER_TG, "خبرِ ب", shop_bot_id=shop_bot_id)
        await session.commit()

    for _ in range(notification_service.MAX_ATTEMPTS + 1):
        async with session_scope() as session:
            summary = await notification_service.send_due(session, _Manager({}), None)
        assert summary["retrying"] == 1 and summary["failed"] == 0, summary
        async with session_scope() as session:
            # پنجرهٔ مهلت عمداً عقب می‌رود (وگرنه ردیفِ sending در همین دور برداشته نمی‌شود)
            row = (await session.execute(select(Notification))).scalars().one()
            row.next_attempt_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=1)
            await session.commit()

    row = await _only_notification()
    assert row.status == notification_service.PENDING, f"رباطِ نبودِ ربات باید فقط عقب بیندازد: {row.status}"
    assert row.attempts == notification_service.MAX_ATTEMPTS + 1, row.attempts
    print("✅ test_missing_bot_never_marks_failed PASSED")


# ============================================================================= ۳ — انقضا: یکِ UPDATE به‌ازایِ صاحبِ حساب
async def test_expiry_writes_one_owner_update_per_account() -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG, SHOP_TG, initial_balance_toman=0)
    past = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)
    async with session_scope() as session:
        owner = (await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == OWNER_TG))).scalar_one()
        owner.wallet_balance_toman = 70_000
        charge_ids = []
        for amount in (30_000, 40_000):
            charge = WalletCharge(shop_owner_id=int(owner.id), amount_toman=amount, remaining_toman=amount, expires_at=past)
            session.add(charge)
            await session.flush()
            charge_ids.append(int(charge.id))
        await session.commit()

    with _counted() as seen:
        async with session_scope() as session:
            count = await wallet_service.expire_stale_charges(session)
            await session.commit()
    owner_updates = [s for s in seen if s.startswith("UPDATE shop_owners")]
    assert count == 2, count
    assert len(owner_updates) == 1, f"یکِ UPDATE به‌ازایِ هر صاحبِ حساب لازم است: {owner_updates}"
    assert await owner_balance(OWNER_TG) == 0
    ledger = await wallet_transactions(WalletTransactionReason.EXPIRY)
    assert len(ledger) == 2 and sum(int(t.amount_toman) for t in ledger) == -70_000, ledger
    async with session_scope() as session:
        charges = list(
            (await session.execute(select(WalletCharge).where(WalletCharge.id.in_(charge_ids)))).scalars().all()
        )
    assert len(charges) == 2 and all(ch.is_expired and ch.remaining_toman == 0 for ch in charges), [
        (c.remaining_toman, c.is_expired) for c in charges
    ]
    print(f"✅ test_expiry_writes_one_owner_update_per_account PASSED ({len(seen)} statement برایِ دو بسته)")


# ============================================================================= ۴ — دامنهٔ اجرایِ دسته
async def test_batch_execute_is_scope_and_owner_bound() -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG, SHOP_TG)
    await seed_usable_shop(OTHER_OWNER_TG, OTHER_SHOP_TG)
    async with session_scope() as session:
        own = (await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == OWNER_TG))).scalar_one()
        other = (await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == OTHER_OWNER_TG))).scalar_one()
        for tg in (OPERATOR_TG, OTHER_OPERATOR_TG):
            session.add(AdminRole(telegram_id=tg, role="operator", granted_by_telegram_id=1))
        await session.flush()
        role = (await session.execute(select(AdminRole).where(AdminRole.telegram_id == OPERATOR_TG))).scalar_one()
        other_role = (
            await session.execute(select(AdminRole).where(AdminRole.telegram_id == OTHER_OPERATOR_TG))
        ).scalar_one()
        await admin_role_service.set_scope(session, role, [int(own.id)])
        await admin_role_service.set_scope(session, other_role, [int(other.id)])

        mine = await credit_batch_service.create_batch(
            session, kind="gift", flt="all", by=str(OPERATOR_TG), amount=5_000, allowed_owner_ids={int(own.id)}
        )
        wide = await credit_batch_service.create_batch(
            session, kind="gift", flt="all", by=str(1), amount=5_000, allowed_owner_ids=None
        )
        assert mine is not None and wide is not None
        await session.commit()

        assert await _outside_actor_scope(session, OPERATOR_TG, mine.batch_id) is False, "دستهٔ خودش در دامنهٔ خودش"
        assert await _outside_actor_scope(session, OTHER_OPERATOR_TG, mine.batch_id) is True, "دستهٔ ادمینِ دیگر"
        assert await _outside_actor_scope(session, OPERATOR_TG, wide.batch_id) is True, "هدفِ بیرونِ دامنه"
        assert await _outside_actor_scope(session, 1, wide.batch_id) is False, "بی‌دامنه (سوپرادمین) محدود نیست"
        assert await _outside_actor_scope(session, OPERATOR_TG, "ناموجود") is False, "دستهٔ نبود ⇒ execute خودش رد می‌کند"
    print("✅ test_batch_execute_is_scope_and_owner_bound PASSED")


async def main() -> None:
    await test_send_due_commits_per_row_and_reclaims_lease()
    await test_missing_bot_never_marks_failed()
    await test_expiry_writes_one_owner_update_per_account()
    await test_batch_execute_is_scope_and_owner_bound()


if __name__ == "__main__":
    asyncio.run(main())
