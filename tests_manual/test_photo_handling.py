"""
تست: عکسِ مشتری در رباتِ فروشگاهی — P18 · A4.

قبلاً هر عکسِ معمولیِ مشتری با پرامپتِ «رسید» به هوش مصنوعی می‌رفت و هزینه‌یِ
«تحلیلِ عکس» از کیف‌پولِ فروشگاه‌دار کم می‌شد. A4 آن را حذف کرد: تحلیلِ عکس فقط
در مسیرِ رسیدِ پرداخت (handlers/payments.py + receipt_ai_service) می‌ماند. اینجا
بررسی می‌کنیم که عکسِ عادی همان‌طور که باید دانلود و برایِ فروشگاه‌دار فوروارد
می‌شود (از طریقِ main_bot و با فایلِ تازه، چون file_id بینِ دو bot قابل‌انتقال
نیست) ولی هیچ فراخوانیِ AI و هیچ کسرِ هزینه‌ای انجام نمی‌شود.

اجرا: python3 tests_manual/test_photo_handling.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402
from sqlalchemy import select  # noqa: E402

from harness import FakeSession, build_test_dispatchers, make_message_update, reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.database.models import Customer, ShopBot, ShopOwner  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import ai_pool_service, wallet_service  # noqa: E402

OWNER_TG_ID = 999201
SHOP_BOT_TG_ID = 999202
CUSTOMER_TG_ID = 999203

PHOTO_BYTES = b"\xff\xd8\xff\xe0-fake-jpeg-bytes-for-a-receipt-photo"


async def _balance(telegram_id: int) -> int:
    async with session_scope() as session:
        owner = (await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == telegram_id))).scalars().first()
        assert owner is not None, "فروشگاه‌دار باید با seed_usable_shop ساخته شده باشد"
        return owner.wallet_balance_toman


async def _feed_photo(shop_dp, main_bot, shop_tg_id: int, customer_tg_id: int, *, caption: str | None = None):
    shop_bot_instance = Bot(token=f"{shop_tg_id}:FAKE", session=FakeSession())
    shop_session_obj: FakeSession = shop_bot_instance.session  # type: ignore[assignment]
    shop_session_obj.set_downloaded_file("incoming_photo_id", PHOTO_BYTES)
    main_session_obj: FakeSession = main_bot.session  # type: ignore[assignment]
    main_session_obj.sent_photos.clear()
    kwargs = {"caption": caption} if caption else {}
    await shop_dp.feed_update(
        shop_bot_instance, make_message_update(1, user_id=customer_tg_id, photo=True, first_name="مشتریِ تست", **kwargs)
    )
    await asyncio.sleep(0.1)
    return shop_session_obj, main_session_obj


async def test_customer_photo_forwarded_without_any_ai(shop_dp, main_bot) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)

    calls: list[str] = []

    async def _spy(session, admin_settings, capability):
        calls.append(capability)
        raise AssertionError(f"A4: نباید برایِ عکسِ مشتری سرویسِ AI بسازیم ({capability})")

    original = ai_pool_service.build_ai_service
    ai_pool_service.build_ai_service = _spy
    try:
        before = await _balance(OWNER_TG_ID)
        shop_session_obj, main_session_obj = await _feed_photo(shop_dp, main_bot, SHOP_BOT_TG_ID, CUSTOMER_TG_ID, caption="این فیشِ واریزیمه")
        after = await _balance(OWNER_TG_ID)
    finally:
        ai_pool_service.build_ai_service = original

    assert calls == [], f"هیچ سرویسِ AI‌ای نباید ساخته می‌شد، ولی ساخته شد: {calls}"
    assert len(main_session_obj.sent_photos) == 1, (
        f"عکس باید دقیقاً یه‌بار از طریقِ main_bot به فروشگاه‌دار فوروارد بشه، نه {len(main_session_obj.sent_photos)} بار"
    )
    forwarded = main_session_obj.sent_photos[0]
    assert forwarded["chat_id"] == OWNER_TG_ID, "عکس باید به آیدیِ تلگرامِ فروشگاه‌دار فرستاده بشه"
    assert "مشتریِ تست" in forwarded["caption"], "کپشن باید نامِ مشتری رو داشته باشه"
    assert "این فیشِ واریزیمه" in forwarded["caption"], "کپشنِ همراهِ عکسِ مشتری باید توی کپشنِ فوروارد باشه"
    assert "بررسیِ خودکار" not in forwarded["caption"], "نتیجه‌یِ تحلیلِ عکس دیگر نباید در کپشن باشد"
    assert any("فقط برایِ رسید" in m["text"] for m in shop_session_obj.sent_messages), (
        "تاییدِ دریافت باید بگوید تحلیلِ خودکار فقط برایِ رسید است"
    )
    assert after == before, "عکسِ عادی نباید چیزی از کیف‌پول کم کند"
    print("✅ test_customer_photo_forwarded_without_any_ai PASSED")


async def test_blocked_customer_photo_is_not_forwarded(shop_dp, main_bot) -> None:
    """B4 × A4: مشتریِ بلاک‌شده نه هزینه‌ای می‌سازد نه عکسی به فروشگاه‌دار می‌فرستد."""
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID + 1, SHOP_BOT_TG_ID + 1)
    async with session_scope() as session:
        customer = (
            await session.execute(select(Customer).where(Customer.telegram_id == CUSTOMER_TG_ID + 1))
        ).scalars().first()
        if customer is None:
            customer = Customer(
                shop_bot_id=(await session.execute(select(ShopBot.id))).scalars().first(),
                telegram_id=CUSTOMER_TG_ID + 1,
                first_name="مشتریِ بلاک",
            )
            session.add(customer)
            await session.flush()
        customer.is_blocked = True
        await session.commit()

    calls: list[str] = []

    async def _spy(session, admin_settings, capability):
        calls.append(capability)
        raise AssertionError("برایِ مشتریِ بلاک‌شده نباید AI ساخته شود")

    original = ai_pool_service.build_ai_service
    ai_pool_service.build_ai_service = _spy
    try:
        shop_session_obj, main_session_obj = await _feed_photo(shop_dp, main_bot, SHOP_BOT_TG_ID + 1, CUSTOMER_TG_ID + 1)
    finally:
        ai_pool_service.build_ai_service = original

    assert main_session_obj.sent_photos == [], "عکسِ مشتریِ بلاک‌شده نباید به فروشگاه‌دار برسد"
    assert calls == [], calls
    assert any("محدود" in m["text"] or "📸" in m["text"] for m in shop_session_obj.sent_messages), shop_session_obj.sent_messages
    print("✅ test_blocked_customer_photo_is_not_forwarded PASSED")


def test_photo_cost_estimator_is_gone() -> None:
    assert not hasattr(wallet_service, "estimate_photo_cost"), "A4: مسیرِ هزینه‌یِ تحلیلِ عکسِ عمومی باید پاک شود"
    print("✅ test_photo_cost_estimator_is_gone PASSED")


async def main() -> None:
    _main_dp, shop_dp, _bot_manager, main_bot = build_test_dispatchers()
    await test_customer_photo_forwarded_without_any_ai(shop_dp, main_bot)
    await test_blocked_customer_photo_is_not_forwarded(shop_dp, main_bot)
    test_photo_cost_estimator_is_gone()


if __name__ == "__main__":
    asyncio.run(main())
