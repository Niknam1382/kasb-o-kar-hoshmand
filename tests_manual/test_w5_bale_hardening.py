"""
تست: سخت‌سازیِ بله‌پی (W5 · لایه‌یِ ۱ · بند ۱.۵): B6 (getUpdates پایدار)، B7 (رمزنگاریِ provider_token)،
B10 (رقابتِ وب‌هوک/getUpdates روی مسیرِ قدیمیِ bale_paid_at). هیچ تماسِ HTTPِ واقعی زده نمی‌شه.

اجرا: python3 tests_manual/test_w5_bale_hardening.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402
from sqlalchemy import text  # noqa: E402

from harness import FakeSession, build_test_dispatchers, register_fake_shop_bot, reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app import main as app_main  # noqa: E402
from app.config import settings  # noqa: E402
from app.database.models import OrderType, ShopBot  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import bale_service, bale_updates_service, customer_service, order_service  # noqa: E402
from app.services.admin_settings_service import get_admin_settings, update_setting  # noqa: E402
from app.utils.encryption import decrypt_token  # noqa: E402

OWNER_TG_ID = 999851
SHOP_BOT_TG_ID = 999852
CUSTOMER_TG_ID = 999853


# =============================================================================
# B6
# =============================================================================
async def test_polling_pure_helpers() -> None:
    assert [bale_updates_service.backoff_seconds(n) for n in (-1, 0, 1, 2, 3, 6, 7, 50)] == [0.0, 0.0, 2.0, 4.0, 8.0, 60.0, 60.0, 60.0]
    nxt = bale_updates_service.next_offset
    assert nxt(None, []) is None and nxt(5, []) == 5
    assert nxt(None, [{"update_id": 5}, {"update_id": 7}, {"update_id": 6}]) == 8
    assert nxt(20, [{"update_id": 5}]) == 20, "offset هرگز عقب نمی‌ره"
    assert nxt(None, [{"update_id": "x"}, {"update_id": True}, {}, 3]) is None, "update_idِ غیرعددی نادیده"
    print("✅ test_polling_pure_helpers PASSED")


async def test_poll_once_survives_bad_update_and_fetch_error() -> None:
    seen: list[int] = []

    async def handler(update: dict) -> None:
        if update["update_id"] == 6:
            raise RuntimeError("boom")
        seen.append(update["update_id"])

    async def fetch(token: str, offset: int | None) -> list[dict]:
        return [{"update_id": 5}, "junk", {"update_id": 6}, {"update_id": 7}]

    new_offset, processed = await bale_updates_service.poll_once("T", None, handler, fetch)
    assert new_offset == 8 and processed == 3 and seen == [5, 7], "آپدیتِ خراب صف رو قفل نمی‌کنه و offset جلو می‌ره"

    async def broken_fetch(token: str, offset: int | None) -> list[dict]:
        raise bale_service.BaleError("down")

    try:
        await bale_updates_service.poll_once("T", 8, handler, broken_fetch)
        raise AssertionError("خطایِ fetch باید بالا بیاد تا backoff اعمال بشه")
    except bale_service.BaleError:
        pass
    print("✅ test_poll_once_survives_bad_update_and_fetch_error PASSED")


async def test_run_loop_backoff_offset_and_stop() -> None:
    old = (bale_updates_service.BACKOFF_BASE_SECONDS, bale_updates_service.IDLE_SLEEP_SECONDS)
    bale_updates_service.BACKOFF_BASE_SECONDS = 0.01
    bale_updates_service.IDLE_SLEEP_SECONDS = 0.01
    try:
        stop = asyncio.Event()
        offsets: list[int | None] = []
        handled: list[int] = []
        script = [bale_service.BaleError("x"), bale_service.BaleError("y"), [{"update_id": 10}], []]

        async def fetch(token: str, offset: int | None) -> list[dict]:
            offsets.append(offset)
            step = script.pop(0) if script else []
            if isinstance(step, Exception):
                raise step
            if not script:
                stop.set()
            return step

        async def handler(update: dict) -> None:
            handled.append(update["update_id"])

        await asyncio.wait_for(bale_updates_service.run_loop("T", handler, stop, fetch), timeout=3)
        assert handled == [10]
        assert offsets[:3] == [None, None, None] and offsets[3] == 11, offsets  # بعد از خطا offset دست‌نخورده؛ بعد از آپدیتِ ۱۰ → ۱۱

        # stop در وسطِ backoffِ طولانی فوری جواب می‌ده
        bale_updates_service.BACKOFF_BASE_SECONDS = 30.0
        stop2 = asyncio.Event()

        async def always_fail(token: str, offset: int | None) -> list[dict]:
            stop2.set()
            raise bale_service.BaleError("down")

        await asyncio.wait_for(bale_updates_service.run_loop("T", handler, stop2, always_fail), timeout=3)
    finally:
        bale_updates_service.BACKOFF_BASE_SECONDS, bale_updates_service.IDLE_SLEEP_SECONDS = old
    print("✅ test_run_loop_backoff_offset_and_stop PASSED")


async def test_dispatch_reuses_webhook_path() -> None:
    calls: list[tuple[str, dict]] = []
    original = (app_main._handle_bale_pre_checkout, app_main._handle_bale_successful_payment)

    # P34: `_dispatch_bale_update` توکنِ *سطحِ پرداخت* را هم به هندلرها می‌دهد (رباتِ پلتفرم یا
    # رباتِ بلهٔ خودِ فروشگاه). fake هم همان امضا را دارد تا این تست تغییرِ امضا را بپوشاند، نه اینکه
    # با آن بشکند.
    async def fake_pre(pc: dict, token: str | None = None) -> None:
        calls.append(("pre", pc))

    async def fake_paid(sp: dict, token: str | None = None) -> None:
        calls.append(("paid", sp))

    app_main._handle_bale_pre_checkout, app_main._handle_bale_successful_payment = fake_pre, fake_paid
    try:
        await app_main._dispatch_bale_update({"update_id": 1, "pre_checkout_query": {"id": "q1"}})
        await app_main._dispatch_bale_update({"update_id": 2, "message": {"successful_payment": {"invoice_payload": "p", "telegram_payment_charge_id": "c"}}})
        await app_main._dispatch_bale_update({"update_id": 3, "message": {"text": "hi"}})
        await app_main._dispatch_bale_update("garbage")  # type: ignore[arg-type]
        # آپدیتِ داده‌شده از رباتِ فروشگاه ⇒ همان توکن باید به هندلر برسد
        await app_main._dispatch_bale_update({"update_id": 4, "pre_checkout_query": {"id": "q4"}}, token="222222:SHOP-BALE-TOKEN")
    finally:
        app_main._handle_bale_pre_checkout, app_main._handle_bale_successful_payment = original
    assert [c[0] for c in calls] == ["pre", "paid", "pre"]
    print("✅ test_dispatch_reuses_webhook_path PASSED")


# =============================================================================
# B7
# =============================================================================
async def test_provider_token_is_encrypted_at_rest() -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    async with session_scope() as session:
        (await session.get(ShopBot, shop_bot_id)).bale_provider_token = "SHOP-SECRET-PROVIDER"
        await update_setting(session, "bale_provider_token", "ADMIN-SECRET-PROVIDER")

    async with session_scope() as session:
        raw_shop = (await session.execute(text("SELECT bale_provider_token FROM shop_bots WHERE id = :i"), {"i": shop_bot_id})).scalar_one()
        raw_admin = (await session.execute(text("SELECT bale_provider_token FROM admin_settings LIMIT 1"))).scalar_one()
        assert "SHOP-SECRET" not in raw_shop and decrypt_token(raw_shop) == "SHOP-SECRET-PROVIDER", "در دیتابیس فقط رمز"
        assert "ADMIN-SECRET" not in raw_admin and decrypt_token(raw_admin) == "ADMIN-SECRET-PROVIDER"
        assert (await session.get(ShopBot, shop_bot_id)).bale_provider_token == "SHOP-SECRET-PROVIDER", "کد مقدارِ خام می‌بینه"
        assert (await get_admin_settings(session)).bale_provider_token == "ADMIN-SECRET-PROVIDER"

    # مقدارِ قدیمیِ رمزنگاری‌نشده خوانده می‌شه (قبل/وسطِ مایگریشن) و با اولین نوشتن رمز می‌شه
    async with session_scope() as session:
        await session.execute(text("UPDATE shop_bots SET bale_provider_token = 'LEGACY-PLAIN' WHERE id = :i"), {"i": shop_bot_id})
    async with session_scope() as session:
        shop_bot = await session.get(ShopBot, shop_bot_id)
        assert shop_bot.bale_provider_token == "LEGACY-PLAIN"
        shop_bot.bale_provider_token = "LEGACY-PLAIN-2"
    async with session_scope() as session:
        raw = (await session.execute(text("SELECT bale_provider_token FROM shop_bots WHERE id = :i"), {"i": shop_bot_id})).scalar_one()
        assert raw != "LEGACY-PLAIN-2" and decrypt_token(raw) == "LEGACY-PLAIN-2"

    # حذف: None و رشته‌یِ خالی ⇒ NULL
    async with session_scope() as session:
        (await session.get(ShopBot, shop_bot_id)).bale_provider_token = ""
    async with session_scope() as session:
        assert (await session.execute(text("SELECT bale_provider_token FROM shop_bots WHERE id = :i"), {"i": shop_bot_id})).scalar_one() is None
        assert (await session.get(ShopBot, shop_bot_id)).bale_provider_token is None
    print("✅ test_provider_token_is_encrypted_at_rest PASSED")


# =============================================================================
# B10
# =============================================================================
async def _seed_group(group_id: str, amounts: list[int]) -> tuple[int, list[int]]:
    await reset_database()
    settings.bale_bot_token = "TEST-PLATFORM-BALE-BOT-TOKEN"
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    ids: list[int] = []
    async with session_scope() as session:
        customer = await customer_service.get_or_create_customer(session, shop_bot_id, CUSTOMER_TG_ID, "مشتری", None)
        for amount in amounts:
            order = await order_service.create_order(session, shop_bot_id, customer.id, OrderType.ORDER, "x", amount)
            order.cart_checkout_group_id = group_id
            ids.append(order.id)
    return shop_bot_id, ids


async def test_concurrent_duplicate_group_payment_applies_once(main_bot, bot_manager) -> None:
    group_id = "ab" * 12
    shop_bot_id, ids = await _seed_group(group_id, [120_000, 80_000])
    shop_bot_instance = Bot(token=f"{SHOP_BOT_TG_ID}:FAKE", session=FakeSession())
    register_fake_shop_bot(bot_manager, shop_bot_id, shop_bot_instance)
    main_bot.session.sent_messages.clear()
    inquiries = 0

    async def slow_inquire(bot_token, transaction_id):
        nonlocal inquiries
        inquiries += 1
        await asyncio.sleep(0.2)  # هر دو تسک قبل از علامت‌زدن از استعلام رد می‌شن ⇒ رقابتِ واقعی
        return {"status": "successful", "amount": 200_000 * 10}

    original = bale_service.inquire_transaction
    bale_service.inquire_transaction = slow_inquire
    try:
        payment = {"invoice_payload": f"cartgroup-{group_id}-cd34", "telegram_payment_charge_id": "tx_race_1"}
        await asyncio.gather(app_main._handle_bale_successful_payment(payment), app_main._handle_bale_successful_payment(payment))
    finally:
        bale_service.inquire_transaction = original

    assert inquiries == 2, "هر دو به استعلام رسیدن؛ فقط یکی باید اثر بذاره"
    async with session_scope() as session:
        for order_id in ids:
            order = await order_service.get_by_id(session, order_id)
            assert order.bale_paid_at is not None and order.bale_transaction_id == "tx_race_1"
    assert len(main_bot.session.sent_messages) == 1, "فروشگاه‌دار فقط یک‌بار خبردار می‌شه"
    assert len(shop_bot_instance.session.sent_messages) == 1, "مشتری فقط یک‌بار خبردار می‌شه"
    print("✅ test_concurrent_duplicate_group_payment_applies_once PASSED")


async def test_replayed_transaction_on_another_order_is_rejected(main_bot, bot_manager) -> None:
    await reset_database()
    settings.bale_bot_token = "TEST-PLATFORM-BALE-BOT-TOKEN"
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    shop_bot_instance = Bot(token=f"{SHOP_BOT_TG_ID}:FAKE", session=FakeSession())
    register_fake_shop_bot(bot_manager, shop_bot_id, shop_bot_instance)
    async with session_scope() as session:
        customer = await customer_service.get_or_create_customer(session, shop_bot_id, CUSTOMER_TG_ID, "مشتری", None)
        first = await order_service.create_order(session, shop_bot_id, customer.id, OrderType.ORDER, "a", 100_000)
        second = await order_service.create_order(session, shop_bot_id, customer.id, OrderType.ORDER, "b", 100_000)
        first.bale_invoice_payload = "order-first"
        second.bale_invoice_payload = "order-second"
        first_id, second_id = first.id, second.id

    async def inquire_ok(bot_token, transaction_id):
        return {"status": "successful"}

    original = bale_service.inquire_transaction
    bale_service.inquire_transaction = inquire_ok
    try:
        await app_main._handle_bale_successful_payment({"invoice_payload": "order-first", "telegram_payment_charge_id": "tx_same"})
        main_bot.session.sent_messages.clear()
        await app_main._handle_bale_successful_payment({"invoice_payload": "order-second", "telegram_payment_charge_id": "tx_same"})
    finally:
        bale_service.inquire_transaction = original
    async with session_scope() as session:
        assert (await order_service.get_by_id(session, first_id)).bale_paid_at is not None
        assert (await order_service.get_by_id(session, second_id)).bale_paid_at is None, "یک تراکنش دو سفارش را پرداخت‌شده نمی‌کنه"
    assert main_bot.session.sent_messages == []
    print("✅ test_replayed_transaction_on_another_order_is_rejected PASSED")


async def main() -> None:
    _main_dp, _shop_dp, bot_manager, main_bot = build_test_dispatchers()
    app_main._state["bot_manager"] = bot_manager
    app_main._state["main_bot"] = main_bot
    await test_polling_pure_helpers()
    await test_poll_once_survives_bad_update_and_fetch_error()
    await test_run_loop_backoff_offset_and_stop()
    await test_dispatch_reuses_webhook_path()
    await test_provider_token_is_encrypted_at_rest()
    await test_concurrent_duplicate_group_payment_applies_once(main_bot, bot_manager)
    await test_replayed_transaction_on_another_order_is_rejected(main_bot, bot_manager)


if __name__ == "__main__":
    asyncio.run(main())
