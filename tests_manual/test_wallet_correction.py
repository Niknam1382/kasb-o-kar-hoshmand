"""
تست: استرداد/اصلاحِ تراکنشِ کیف‌پول توسطِ ادمین (فازِ ۲-ب، زیربخشِ ۳).

+ یه تستِ کوچیک برایِ فیکسِ جانبی: هدیه‌ی کیف‌پول حالا باید توی گزارشِ
ممیزی هم ثبت بشه (قبلاً enum ِ OWNER_GIFT_GRANTED تعریف شده بود ولی هیچ‌جا
استفاده نمی‌شد).

نکته: کاربرِ ادمین در این تست‌ها آیدیِ ۱۲۳۴۵ داره، که باید با متغیرِ محیطیِ
ADMIN_TELEGRAM_IDS هنگامِ اجرا مچ بشه (دقیقاً مثلِ test_admin_owner_management.py).

اجرا: python3 tests_manual/run_all_tests.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402
from sqlalchemy import select  # noqa: E402

from harness import FakeSession, build_test_dispatchers, make_callback_update, make_message_update, reset_database  # noqa: E402

from app.database.models import AuditEventType, AuditLogEntry, ShopOwner, WalletTransaction, WalletTransactionReason  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import shop_bot_service, shop_owner_service, wallet_service  # noqa: E402
from app.utils.encryption import encrypt_token  # noqa: E402

ADMIN_TG_ID = 12345
OWNER_TG_ID = 999700


async def _seed_owner_with_shop_bot(owner_tg: int, bot_tg: int, initial_balance: int = 0) -> int:
    async with session_scope() as session:
        owner = await shop_owner_service.get_or_create_shop_owner(session, owner_tg)
        owner = await shop_owner_service.complete_registration(
            session, owner, "فروشگاه‌دار", "تست", "09120000006", "wc@example.com", True, True
        )
        shop_bot = await shop_bot_service.upsert_shop_bot(session, owner, "fake", bot_tg, f"shop_{bot_tg}")
        shop_bot.encrypted_token = encrypt_token(f"{bot_tg}:AAFakeTokenForTestingPurposesOnlyXYZ")
        if initial_balance:
            await wallet_service.add_charge(session, owner, initial_balance, reason=WalletTransactionReason.TOPUP)
        await session.flush()
        return owner.id


async def test_wallet_correction_positive_adds_credit_and_logs(main_dp) -> None:
    await reset_database()
    owner_id = await _seed_owner_with_shop_bot(OWNER_TG_ID, OWNER_TG_ID + 1)
    admin_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())

    await main_dp.feed_update(admin_bot, make_callback_update(1, data=f"admin_owner_wallet_correction:{owner_id}", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(admin_bot, make_message_update(2, text="50000", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(admin_bot, make_message_update(3, text="جبرانِ خطایِ فاکتورِ قبلی", user_id=ADMIN_TG_ID))

    async with session_scope() as session:
        owner = await session.get(ShopOwner, owner_id)
        assert owner.wallet_balance_toman == 50_000, f"باید ۵۰٬۰۰۰ اضافه بشه، نه {owner.wallet_balance_toman}"

        tx_result = await session.execute(
            select(WalletTransaction).where(
                WalletTransaction.shop_owner_id == owner_id, WalletTransaction.reason == WalletTransactionReason.ADMIN_CORRECTION
            )
        )
        transactions = tx_result.scalars().all()
        assert len(transactions) == 1
        assert transactions[0].amount_toman == 50_000
        assert transactions[0].reference == "جبرانِ خطایِ فاکتورِ قبلی"

        audit_result = await session.execute(
            select(AuditLogEntry).where(AuditLogEntry.event_type == AuditEventType.OWNER_WALLET_CORRECTED)
        )
        audit_entries = audit_result.scalars().all()
        assert len(audit_entries) == 1, "باید دقیقاً یه رکوردِ ممیزی ثبت بشه"
        assert str(owner_id) in audit_entries[0].details
        assert audit_entries[0].actor_telegram_id == ADMIN_TG_ID

    print("✅ test_wallet_correction_positive_adds_credit_and_logs PASSED")


async def test_wallet_correction_negative_deducts_credit(main_dp) -> None:
    await reset_database()
    owner_id = await _seed_owner_with_shop_bot(OWNER_TG_ID + 10, OWNER_TG_ID + 11, initial_balance=200_000)
    admin_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())

    await main_dp.feed_update(admin_bot, make_callback_update(1, data=f"admin_owner_wallet_correction:{owner_id}", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(admin_bot, make_message_update(2, text="-50000", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(admin_bot, make_message_update(3, text="شارژِ اشتباهی زده شده بود", user_id=ADMIN_TG_ID))

    async with session_scope() as session:
        owner = await session.get(ShopOwner, owner_id)
        assert owner.wallet_balance_toman == 150_000, f"باید به ۱۵۰٬۰۰۰ برسه، نه {owner.wallet_balance_toman}"

    print("✅ test_wallet_correction_negative_deducts_credit PASSED")


async def test_wallet_correction_insufficient_balance_allows_retry(main_dp) -> None:
    await reset_database()
    owner_id = await _seed_owner_with_shop_bot(OWNER_TG_ID + 20, OWNER_TG_ID + 21, initial_balance=10_000)
    admin_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())
    session_obj: FakeSession = admin_bot.session  # type: ignore[assignment]

    await main_dp.feed_update(admin_bot, make_callback_update(1, data=f"admin_owner_wallet_correction:{owner_id}", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(admin_bot, make_message_update(2, text="-50000", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(admin_bot, make_message_update(3, text="تلاشِ اولِ ناموفق", user_id=ADMIN_TG_ID))

    async with session_scope() as session:
        owner = await session.get(ShopOwner, owner_id)
        assert owner.wallet_balance_toman == 10_000, "موجودیِ ناکافی نباید هیچ تغییری بده"
    assert "کافی نیست" in session_obj.sent_messages[-1]["text"]

    # باید برگرده به مرحله‌ی «مبلغ» تا بشه دوباره یه عددِ کوچیک‌تر امتحان کرد،
    # نه بمونه توی حلقه‌ی بی‌پایانِ «دلیل».
    await main_dp.feed_update(admin_bot, make_message_update(4, text="-5000", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(admin_bot, make_message_update(5, text="اصلاحِ کوچیک‌تر", user_id=ADMIN_TG_ID))

    async with session_scope() as session:
        owner = await session.get(ShopOwner, owner_id)
        assert owner.wallet_balance_toman == 5_000, f"باید بعدِ تلاشِ دوم به ۵٬۰۰۰ برسه، نه {owner.wallet_balance_toman}"

    print("✅ test_wallet_correction_insufficient_balance_allows_retry PASSED")


async def test_wallet_correction_invalid_amount_rejected(main_dp) -> None:
    await reset_database()
    owner_id = await _seed_owner_with_shop_bot(OWNER_TG_ID + 30, OWNER_TG_ID + 31)
    admin_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())
    session_obj: FakeSession = admin_bot.session  # type: ignore[assignment]

    await main_dp.feed_update(admin_bot, make_callback_update(1, data=f"admin_owner_wallet_correction:{owner_id}", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(admin_bot, make_message_update(2, text="عدد نیست", user_id=ADMIN_TG_ID))
    assert "معتبر نیست" in session_obj.sent_messages[-1]["text"]

    await main_dp.feed_update(admin_bot, make_message_update(3, text="0", user_id=ADMIN_TG_ID))
    assert "معتبر نیست" in session_obj.sent_messages[-1]["text"], "صفر نباید قبول بشه"

    async with session_scope() as session:
        owner = await session.get(ShopOwner, owner_id)
        assert owner.wallet_balance_toman == 0

    print("✅ test_wallet_correction_invalid_amount_rejected PASSED")


async def test_wallet_correction_empty_reason_allows_retry(main_dp) -> None:
    await reset_database()
    owner_id = await _seed_owner_with_shop_bot(OWNER_TG_ID + 40, OWNER_TG_ID + 41)
    admin_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())
    session_obj: FakeSession = admin_bot.session  # type: ignore[assignment]

    await main_dp.feed_update(admin_bot, make_callback_update(1, data=f"admin_owner_wallet_correction:{owner_id}", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(admin_bot, make_message_update(2, text="30000", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(admin_bot, make_message_update(3, text="   ", user_id=ADMIN_TG_ID))
    assert "خالی" in session_obj.sent_messages[-1]["text"]

    async with session_scope() as session:
        owner = await session.get(ShopOwner, owner_id)
        assert owner.wallet_balance_toman == 0, "با دلیلِ خالی هنوز نباید اعمال بشه"

    await main_dp.feed_update(admin_bot, make_message_update(4, text="حالا یه دلیلِ واقعی", user_id=ADMIN_TG_ID))

    async with session_scope() as session:
        owner = await session.get(ShopOwner, owner_id)
        assert owner.wallet_balance_toman == 30_000, "بعدِ دلیلِ واقعی باید اعمال بشه"

    print("✅ test_wallet_correction_empty_reason_allows_retry PASSED")


async def test_non_admin_cannot_use_wallet_correction(main_dp) -> None:
    await reset_database()
    owner_id = await _seed_owner_with_shop_bot(OWNER_TG_ID + 50, OWNER_TG_ID + 51)
    non_admin_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())

    await main_dp.feed_update(
        non_admin_bot, make_callback_update(1, data=f"admin_owner_wallet_correction:{owner_id}", user_id=999999)
    )

    async with session_scope() as session:
        owner = await session.get(ShopOwner, owner_id)
        assert owner.wallet_balance_toman == 0, "کاربرِ غیرِادمین نباید حتی بتونه فلوی اصلاح رو شروع کنه"

    print("✅ test_non_admin_cannot_use_wallet_correction PASSED")


async def test_admin_gift_now_logs_audit_entry(main_dp) -> None:
    """فیکسِ جانبی: قبلاً OWNER_GIFT_GRANTED تعریف شده بود ولی هیچ‌جا لاگ نمی‌شد."""
    await reset_database()
    owner_id = await _seed_owner_with_shop_bot(OWNER_TG_ID + 60, OWNER_TG_ID + 61)
    admin_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())

    await main_dp.feed_update(admin_bot, make_callback_update(1, data=f"admin_owner_gift:{owner_id}", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(admin_bot, make_message_update(2, text="100000", user_id=ADMIN_TG_ID))

    async with session_scope() as session:
        result = await session.execute(select(AuditLogEntry).where(AuditLogEntry.event_type == AuditEventType.OWNER_GIFT_GRANTED))
        entries = result.scalars().all()
        assert len(entries) == 1, "هدیه‌ی کیف‌پول حالا باید یه رکوردِ ممیزی بسازه"
        assert str(owner_id) in entries[0].details

    print("✅ test_admin_gift_now_logs_audit_entry PASSED")


async def main() -> None:
    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    await test_wallet_correction_positive_adds_credit_and_logs(main_dp)
    await test_wallet_correction_negative_deducts_credit(main_dp)
    await test_wallet_correction_insufficient_balance_allows_retry(main_dp)
    await test_wallet_correction_invalid_amount_rejected(main_dp)
    await test_wallet_correction_empty_reason_allows_retry(main_dp)
    await test_non_admin_cannot_use_wallet_correction(main_dp)
    await test_admin_gift_now_logs_audit_entry(main_dp)


if __name__ == "__main__":
    asyncio.run(main())
