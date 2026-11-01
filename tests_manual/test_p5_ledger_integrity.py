"""
تست‌هایِ PHASE 5E — دفترِ فقط‌افزودنیِ کیف‌پول، ارجاع‌هایِ مالی و همسنجی.

پوشش:
۱. ردیف‌هایِ تازه ستون‌هایِ `currency/status/payment_id/idempotency_key` را درست پر می‌کنند.
۲. ردیفِ دفتر نه ویرایش می‌شود نه حذف (نگهبانِ سطحِ ORM) — تاریخچه بازنویسی‌ناپذیر است.
۳. کلیدِ ایدپوتنسی یکتاست؛ ثبتِ دوبارهٔ یک رویدادِ تکراری با IntegrityError رد می‌شود.
۴. همسنجی رویِ دادهٔ سالم [] می‌دهد و رویِ هر دو سمتِ اختلاف (موجودیِ کش‌شده ↔ دفتر،
   موجودیِ کش‌شده ↔ بسته‌ها) همان فروشگاه‌دار را با عددِ درست برمی‌گرداند.
۵. جابِ همسنجی: ساعتی یک‌بار کار می‌کند، اختلاف را به `admin_alert_service` می‌گوید و
   هیچ داده‌ای را خودش اصلاح نمی‌کند.
۶. پنلِ ادمین: پیامِ «📤 دفترِ کیف‌پول (اکسل)» دکمهٔ «🔎 همسنجیِ دفتر» را دارد؛ فشردنِ آن
   گزارشِ خوانا می‌دهد، ممیزی می‌شود و فقط‌خواندنی است.

اجرا: python3 tests_manual/test_p5_ledger_integrity.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402
from sqlalchemy import select, update  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402

from harness import FakeSession, build_test_dispatchers, make_callback_update, make_message_update, reset_database  # noqa: E402

from app.bots.main_bot import texts as main_texts  # noqa: E402
from app.database.models import (
    AuditEventType,
    AuditLogEntry,
    ShopOwner,
    WalletCharge,
    WalletTransaction,
    WalletTransactionReason,
)
from app.database.session import session_scope  # noqa: E402
from app.services import admin_alert_service, scheduler, shop_owner_service, wallet_service  # noqa: E402

OWNER_TG_ID = 999_521
OTHER_OWNER_TG_ID = 999_522
ADMIN_TG_ID = 12345
MAIN_TOKEN = "000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS"


async def _seed(telegram_id: int = OWNER_TG_ID) -> int:
    async with session_scope() as session:
        owner = await shop_owner_service.get_or_create_shop_owner(session, telegram_id)
        await shop_owner_service.complete_registration(
            session, owner, "دفتر", "تست", "09124444444", "ledger@example.com", True, True
        )
        return owner.id


async def _charge(owner_id: int, amount: int, **kwargs) -> int:
    async with session_scope() as session:
        owner = (await session.execute(select(ShopOwner).where(ShopOwner.id == owner_id))).scalar_one()
        charge = await wallet_service.add_charge(session, owner, amount, **kwargs)
        return charge.id


async def _owner_balance(owner_id: int) -> int:
    async with session_scope() as session:
        return (await session.execute(select(ShopOwner.wallet_balance_toman).where(ShopOwner.id == owner_id))).scalar_one()


async def _ledger_rows(owner_id: int) -> list[WalletTransaction]:
    async with session_scope() as session:
        return list(
            (
                await session.execute(
                    select(WalletTransaction).where(WalletTransaction.shop_owner_id == owner_id).order_by(WalletTransaction.id)
                )
            )
            .scalars()
            .all()
        )


# ============================================================================= ۱ — ستون‌هایِ تازه
async def test_new_ledger_columns_are_filled_on_insert() -> None:
    await reset_database()
    owner_id = await _seed()
    await _charge(owner_id, 200_000, reason=WalletTransactionReason.TOPUP, payment_id=None, reference="topup:42")

    rows = await _ledger_rows(owner_id)
    assert len(rows) == 1, rows
    row = rows[0]
    assert row.currency == "TOMAN" and row.status == "settled", (row.currency, row.status)
    assert row.idempotency_key.endswith(f"owner:{owner_id}") and row.idempotency_key.startswith("charge:topup:42"), row.idempotency_key
    assert row.created_at is not None

    # یک مرجعِ مشترک برایِ دو فروشگاه‌دارِ متفاوت نباید بکشد (case واقعی: هدیه‌یِ گروهیِ K1
    # که reference=«batch:…» را برایِ هر نفر همان‌طور تکرار می‌کند)
    other_id = await _seed(OTHER_OWNER_TG_ID)
    async with session_scope() as session:
        other = (await session.execute(select(ShopOwner).where(ShopOwner.id == other_id))).scalar_one()
        await wallet_service.add_charge(session, other, 10_000, reference="topup:42")
    assert len(await _ledger_rows(other_id)) == 1, "کلیدِ ایدپوتنسی به‌ازایِ (رویداد، فروشگاه‌دار) است نه سراسری"

    # مصرف هم ردیفِ دفتر با ارجاع/کلیدِ درست می‌سازد
    async with session_scope() as session:
        owner = (await session.execute(select(ShopOwner).where(ShopOwner.id == owner_id))).scalar_one()
        await wallet_service.deduct(
            session, owner, 50_000, WalletTransactionReason.CHAT_MESSAGE, reference="usage:7", idempotency_key="spend:7"
        )
    spend = (await _ledger_rows(owner_id))[-1]
    assert spend.amount_toman == -50_000 and spend.idempotency_key == "spend:7"
    assert spend.currency == "TOMAN" and spend.status == "settled"
    print("✅ test_new_ledger_columns_are_filled_on_insert PASSED")


async def test_dangling_order_reference_is_rejected_by_the_database() -> None:
    """PHASE 7: ارجاعِ مالی باید واقعاً ارجاع باشد؛ دیتابیس کلیدِ خارجیِ ناموجود را رد می‌کند."""
    await reset_database()
    owner_id = await _seed()
    await _charge(owner_id, 100_000, reference="topup:ref")
    async with session_scope() as session:
        owner = (await session.execute(select(ShopOwner).where(ShopOwner.id == owner_id))).scalar_one()
        try:
            await wallet_service.deduct(session, owner, 10_000, WalletTransactionReason.CHAT_MESSAGE, order_id=999_999)
            raise AssertionError("order_id جعلی باید با نقضِ کلیدِ خارجی رد شود")
        except IntegrityError:
            pass
        await session.rollback()
    assert len(await _ledger_rows(owner_id)) == 1, "ردیفِ نقض‌کننده نباید باقی بماند"
    print("✅ test_dangling_order_reference_is_rejected_by_the_database PASSED")


# ============================================================================= ۲ — فقط‌افزودنی
async def test_ledger_rows_cannot_be_updated_or_deleted() -> None:
    await reset_database()
    owner_id = await _seed()
    await _charge(owner_id, 100_000, reference="topup:1")
    row_id = (await _ledger_rows(owner_id))[0].id

    async with session_scope() as session:
        row = await session.get(WalletTransaction, row_id)
        row.amount_toman = 1  # تلاش برای بازنویسیِ تاریخچه
        try:
            await session.flush()
            raise AssertionError("ویرایشِ ردیفِ دفتر باید رد شود")
        except wallet_service.LedgerIsAppendOnlyError:
            pass
        await session.rollback()

    async with session_scope() as session:
        row = await session.get(WalletTransaction, row_id)
        await session.delete(row)
        try:
            await session.flush()
            raise AssertionError("حذفِ ردیفِ دفتر باید رد شود")
        except wallet_service.LedgerIsAppendOnlyError:
            pass
        await session.rollback()

    # اصلاحِ درست: ردیفِ معکوسِ جدید، بدونِ دست‌زدنِ تاریخچه
    async with session_scope() as session:
        session.add(
            WalletTransaction(
                shop_owner_id=owner_id,
                amount_toman=-100_000,
                reason=WalletTransactionReason.ADMIN_CORRECTION,
                reference=f"reversal:{row_id}",
                idempotency_key=f"reversal:{row_id}",
            )
        )
    fresh = await _ledger_rows(owner_id)
    assert len(fresh) == 2 and fresh[0].amount_toman == 100_000, "ردیفِ اصلی باید دست‌نخورده بماند"
    print("✅ test_ledger_rows_cannot_be_updated_or_deleted PASSED")


async def test_idempotency_key_is_unique() -> None:
    await reset_database()
    owner_id = await _seed()
    async with session_scope() as session:
        session.add(
            WalletTransaction(shop_owner_id=owner_id, amount_toman=10, reason=WalletTransactionReason.ADMIN_CORRECTION, idempotency_key="dup-1")
        )
        await session.flush()
    async with session_scope() as session:
        session.add(
            WalletTransaction(shop_owner_id=owner_id, amount_toman=10, reason=WalletTransactionReason.ADMIN_CORRECTION, idempotency_key="dup-1")
        )
        try:
            await session.flush()
            raise AssertionError("کلیدِ تکراری نباید قبول شود")
        except IntegrityError:
            await session.rollback()
    async with session_scope() as session:
        rows = list((await session.execute(select(WalletTransaction).where(WalletTransaction.idempotency_key == "dup-1"))).scalars().all())
        assert len(rows) == 1, "ردیفِ دوم نباید ثبت شده باشد"
    print("✅ test_idempotency_key_is_unique PASSED")


# ============================================================================= ۴ — همسنجی
async def test_reconcile_is_clean_on_healthy_data() -> None:
    await reset_database()
    owner_id = await _seed()
    charge_id = await _charge(owner_id, 300_000, validity_months=12, reference="topup:9")
    async with session_scope() as session:
        owner = (await session.execute(select(ShopOwner).where(ShopOwner.id == owner_id))).scalar_one()
        assert await wallet_service.deduct(session, owner, 70_000, WalletTransactionReason.CHAT_MESSAGE, reference="usage:9")
        charge = await session.get(WalletCharge, charge_id)
        charge.expires_at = charge.expires_at.replace(year=charge.expires_at.year - 1)  # منقضی کن
    async with session_scope() as session:
        assert await wallet_service.expire_stale_charges(session) == 1

    async with session_scope() as session:
        assert await wallet_service.reconcile_balances(session) == [], "دادهٔ سالم نباید اختلاف بدهد"
    # ۳۰۰٬۰۰۰ شارژ − ۷۰٬۰۰۰ مصرف − ۲۳۰٬۰۰۰ انقضا = صفر؛ دفتر، بسته‌ها و موجودیِ کش‌شده هر سه صفرند
    assert await _owner_balance(owner_id) == 0
    print("✅ test_reconcile_is_clean_on_healthy_data PASSED")


async def test_reconcile_detects_both_kinds_of_drift() -> None:
    await reset_database()
    a = await _seed(OWNER_TG_ID)
    b = await _seed(OTHER_OWNER_TG_ID)
    await _charge(a, 100_000, reference="topup:a")
    await _charge(b, 100_000, reference="topup:b")

    # الف) موجودیِ کش‌شده با دفتر نمی‌خواند (با Core update از نگهبانِ ORM رد می‌شویم؛
    # این همان حالتِ «دادهٔ خراب/دستی» است که همسنجی باید بگیرد)
    async with session_scope() as session:
        await session.execute(update(ShopOwner).where(ShopOwner.id == a).values(wallet_balance_toman=130_000))
    # ب) موجودی با مجموعِ بسته‌ها نمی‌خواند
    async with session_scope() as session:
        await session.execute(update(WalletCharge).where(WalletCharge.shop_owner_id == b).values(remaining_toman=80_000))

    async with session_scope() as session:
        gaps = await wallet_service.reconcile_balances(session)
    by_id = {g["owner_id"]: g for g in gaps}
    assert set(by_id) == {a, b}, gaps
    assert by_id[a]["ledger_delta_toman"] == 30_000 and by_id[a]["lots_delta_toman"] == 30_000, by_id[a]
    assert by_id[b]["ledger_delta_toman"] == 0, by_id[b]
    assert by_id[b]["lots_delta_toman"] == 20_000, by_id[b]
    print("✅ test_reconcile_detects_both_kinds_of_drift PASSED")


# ============================================================================= ۵ — جاب
async def test_job_is_throttled_alerts_and_fixes_nothing() -> None:
    await reset_database()
    owner_id = await _seed()
    await _charge(owner_id, 100_000, reference="topup:job")
    async with session_scope() as session:
        await session.execute(update(ShopOwner).where(ShopOwner.id == owner_id).values(wallet_balance_toman=999))

    seen: list[tuple[str, str]] = []
    original_record = admin_alert_service.record_event
    admin_alert_service.record_event = lambda kind, detail: seen.append((kind, detail)) or True
    try:
        scheduler.reset_reconcile_clock_for_tests()
        first = await scheduler.reconcile_wallet_ledgers()
        second = await scheduler.reconcile_wallet_ledgers()  # همان ساعت ⇒ نباید دوباره کوئری بزند
    finally:
        admin_alert_service.record_event = original_record

    assert first == 1, first
    assert second == 0, "جاب نباید هر دورِ جاب‌ها کوئریِ گروهیِ دفتر بزند"
    assert seen and seen[0][0] == admin_alert_service.KIND_LEDGER, seen
    assert await _owner_balance(owner_id) == 999, "جاب هیچ داده‌ای را اصلاح نمی‌کند؛ فقط گزارش"
    print("✅ test_job_is_throttled_alerts_and_fixes_nothing PASSED")


# ============================================================================= ۶ — پنلِ ادمین
async def test_admin_panel_reports_and_audits(main_dp) -> None:
    await reset_database()
    await _seed()
    main_bot = Bot(token=MAIN_TOKEN, session=FakeSession())
    session_obj: FakeSession = main_bot.session  # type: ignore[assignment]

    await main_dp.feed_update(main_bot, make_message_update(1, text="📤 دفترِ کیف‌پول (اکسل)", user_id=ADMIN_TG_ID))
    assert len(session_obj.sent_documents) == 1, session_obj.sent_documents
    markup = session_obj.sent_documents[0].get("caption") or ""
    assert markup == main_texts.ADMIN_WALLET_LEDGER_READY or "دفترِ کیف‌پول" in markup

    await main_dp.feed_update(main_bot, make_callback_update(2, data="admin_reconcile_wallets", user_id=ADMIN_TG_ID))
    assert session_obj.sent_messages[-1]["text"] == main_texts.ADMIN_RECONCILE_CLEAN, session_obj.sent_messages[-1]

    async with session_scope() as session:
        rows = list(
            (
                await session.execute(
                    select(AuditLogEntry).where(AuditLogEntry.event_type == AuditEventType.WALLET_RECONCILED.value)
                )
            )
            .scalars()
            .all()
        )
    assert len(rows) == 1 and rows[0].actor_telegram_id == ADMIN_TG_ID, rows

    # با اختلاف، گزارشِ خوانا و «تاریخچه اصلاح نمی‌شود» نمایش داده می‌شود
    async with session_scope() as session:
        await session.execute(update(ShopOwner).where(ShopOwner.telegram_id == OWNER_TG_ID).values(wallet_balance_toman=5))
    await main_dp.feed_update(main_bot, make_callback_update(3, data="admin_reconcile_wallets", user_id=ADMIN_TG_ID))
    report = session_obj.sent_messages[-1]["text"]
    assert "اختلافِ حسابداری" in report and main_texts.ADMIN_RECONCILE_NOTE in report, report
    print("✅ test_admin_panel_reports_and_audits PASSED")


async def main() -> None:
    await test_new_ledger_columns_are_filled_on_insert()
    await test_dangling_order_reference_is_rejected_by_the_database()
    await test_ledger_rows_cannot_be_updated_or_deleted()
    await test_idempotency_key_is_unique()
    await test_reconcile_is_clean_on_healthy_data()
    await test_reconcile_detects_both_kinds_of_drift()
    await test_job_is_throttled_alerts_and_fixes_nothing()

    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    await test_admin_panel_reports_and_audits(main_dp)


if __name__ == "__main__":
    asyncio.run(main())
