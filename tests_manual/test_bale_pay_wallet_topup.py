"""
تست: یکپارچه‌سازیِ بله‌پی برای شارژِ کیف‌پول (فازِ ۱-ج).

مهم: هیچ تماسِ HTTPِ واقعی‌ای به بله زده نمی‌شه — توابعِ bale_service که با
سرورِ واقعیِ بله حرف می‌زنن (answer_pre_checkout_query، inquire_transaction)
با پیاده‌سازیِ جعلی monkeypatch می‌شن، دقیقاً مثلِ الگویی که برای ai_service
توی test_message_debounce.py استفاده شده. create_invoice_link هم مستقیم تست
نمی‌شه (چون واقعاً باید با سرورِ بله حرف بزنه) — این تستـا فقط منطقِ سمتِ ما
(webhook، ذخیره‌ی Payment، استعلامِ اجباری قبل از شارژ) رو پوشش می‌دن.

اجرا: python3 tests_manual/test_bale_pay_wallet_topup.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from harness import reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from sqlalchemy import select  # noqa: E402

from app import main as app_main  # noqa: E402
from app.config import settings  # noqa: E402
from app.database.models import PaymentPurpose, PaymentStatus, ShopOwner  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import bale_service, payment_service  # noqa: E402
from app.services.admin_settings_service import get_admin_settings, update_setting  # noqa: E402

OWNER_TG_ID = 999701


async def _seed_owner_and_settings() -> int:
    await seed_usable_shop(OWNER_TG_ID, 999702)
    async with session_scope() as session:
        admin_settings = await get_admin_settings(session)
        await update_setting(session, "bale_pay_enabled", True)
        await update_setting(session, "bale_provider_token", "TEST-PROVIDER-TOKEN")
        result = await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == OWNER_TG_ID))
        owner = result.scalar_one()
        return owner.id


async def test_create_bale_payment_stores_pending_row_with_payload() -> None:
    await reset_database()
    owner_id = await _seed_owner_and_settings()
    async with session_scope() as session:
        owner = await session.get(ShopOwner, owner_id)
        payment = await payment_service.create_bale_payment(
            session, owner, base_amount=100_000, discount=None, invoice_payload="payment-test-abc",
            purpose=PaymentPurpose.WALLET_TOPUP,
        )
        assert payment.status == PaymentStatus.PENDING
        assert payment.bale_invoice_payload == "payment-test-abc"

        found = await payment_service.get_by_bale_payload(session, "payment-test-abc")
        assert found is not None and found.id == payment.id
    print("✅ test_create_bale_payment_stores_pending_row_with_payload PASSED")


async def test_pre_checkout_accepted_for_known_pending_payment() -> None:
    await reset_database()
    owner_id = await _seed_owner_and_settings()
    answered: dict = {}

    async def fake_answer(bot_token, query_id, ok, error_message=None):
        answered["ok"] = ok
        answered["query_id"] = query_id

    bale_service.answer_pre_checkout_query = fake_answer

    async with session_scope() as session:
        owner = await session.get(ShopOwner, owner_id)
        await payment_service.create_bale_payment(
            session, owner, base_amount=50_000, discount=None, invoice_payload="payment-precheck-1",
            purpose=PaymentPurpose.WALLET_TOPUP,
        )

    await app_main._handle_bale_pre_checkout({"id": "pcq_1", "invoice_payload": "payment-precheck-1"})
    assert answered.get("ok") is True
    assert answered.get("query_id") == "pcq_1"
    print("✅ test_pre_checkout_accepted_for_known_pending_payment PASSED")


async def test_pre_checkout_rejected_for_unknown_payload() -> None:
    await reset_database()
    await _seed_owner_and_settings()
    answered: dict = {}

    async def fake_answer(bot_token, query_id, ok, error_message=None):
        answered["ok"] = ok

    bale_service.answer_pre_checkout_query = fake_answer
    await app_main._handle_bale_pre_checkout({"id": "pcq_2", "invoice_payload": "این-پیلود-وجود-نداره"})
    assert answered.get("ok") is False
    print("✅ test_pre_checkout_rejected_for_unknown_payload PASSED")


async def test_successful_payment_requires_inquiry_before_crediting_wallet() -> None:
    """
    مهم‌ترین تست: حتی اگه successful_payment از وب‌هوک برسه، بدونِ تاییدِ
    inquire_transaction نباید کیف‌پول شارژ بشه — این جلوی وب‌هوکِ جعلی رو می‌گیره.
    """
    await reset_database()
    owner_id = await _seed_owner_and_settings()

    inquiry_calls: list[str] = []

    async def fake_inquire_fails(bot_token, transaction_id):
        inquiry_calls.append(transaction_id)
        return {"status": "failed"}  # یعنی بله می‌گه این تراکنش موفق نبوده

    bale_service.inquire_transaction = fake_inquire_fails

    async with session_scope() as session:
        owner = await session.get(ShopOwner, owner_id)
        wallet_before = owner.wallet_balance_toman
        payment = await payment_service.create_bale_payment(
            session, owner, base_amount=70_000, discount=None, invoice_payload="payment-verify-1",
            purpose=PaymentPurpose.WALLET_TOPUP,
        )
        payment_id = payment.id

    app_main._state["main_bot"] = object()
    original_notify = app_main._notify_payment_result
    app_main._notify_payment_result = lambda *a, **k: asyncio.sleep(0)  # جلوگیری از تلاش برای فرستادنِ پیامِ واقعی

    try:
        await app_main._handle_bale_successful_payment(
            {"invoice_payload": "payment-verify-1", "telegram_payment_charge_id": "charge_123"}
        )
    finally:
        app_main._notify_payment_result = original_notify

    assert inquiry_calls == ["charge_123"], "باید حتماً inquire_transaction صدا زده بشه"

    async with session_scope() as session:
        payment = await payment_service.get_by_id(session, payment_id)
        assert payment.status == PaymentStatus.PENDING, "چون inquire_transaction گفته failed، نباید APPROVE بشه"
        owner = await session.get(ShopOwner, owner_id)
        assert owner.wallet_balance_toman == wallet_before, "کیف‌پول نباید شارژ شده باشه"

    print("✅ test_successful_payment_requires_inquiry_before_crediting_wallet PASSED")


async def test_successful_payment_credits_wallet_when_inquiry_confirms() -> None:
    await reset_database()
    owner_id = await _seed_owner_and_settings()

    async def fake_inquire_ok(bot_token, transaction_id):
        return {"status": "successful"}

    bale_service.inquire_transaction = fake_inquire_ok

    async with session_scope() as session:
        owner = await session.get(ShopOwner, owner_id)
        wallet_before = owner.wallet_balance_toman
        payment = await payment_service.create_bale_payment(
            session, owner, base_amount=70_000, discount=None, invoice_payload="payment-verify-2",
            purpose=PaymentPurpose.WALLET_TOPUP,
        )
        payment_id = payment.id

    app_main._state["main_bot"] = object()
    app_main._notify_payment_result = lambda *a, **k: asyncio.sleep(0)

    await app_main._handle_bale_successful_payment(
        {"invoice_payload": "payment-verify-2", "telegram_payment_charge_id": "charge_456"}
    )

    async with session_scope() as session:
        payment = await payment_service.get_by_id(session, payment_id)
        assert payment.status == PaymentStatus.APPROVED
        assert payment.bale_transaction_id == "charge_456"
        owner = await session.get(ShopOwner, owner_id)
        assert owner.wallet_balance_toman == wallet_before + 70_000

    # وب‌هوکِ تکراری (بله دوباره همون successful_payment رو می‌فرسته) نباید دوباره شارژ کنه
    await app_main._handle_bale_successful_payment(
        {"invoice_payload": "payment-verify-2", "telegram_payment_charge_id": "charge_456"}
    )
    async with session_scope() as session:
        owner = await session.get(ShopOwner, owner_id)
        assert owner.wallet_balance_toman == wallet_before + 70_000, "وب‌هوکِ تکراری نباید دوباره شارژ کنه"

    print("✅ test_successful_payment_credits_wallet_when_inquiry_confirms PASSED")


async def main() -> None:
    await test_create_bale_payment_stores_pending_row_with_payload()
    await test_pre_checkout_accepted_for_known_pending_payment()
    await test_pre_checkout_rejected_for_unknown_payload()
    await test_successful_payment_requires_inquiry_before_crediting_wallet()
    await test_successful_payment_credits_wallet_when_inquiry_confirms()


if __name__ == "__main__":
    asyncio.run(main())
