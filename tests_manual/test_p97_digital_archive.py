"""پ۹۷ · بایگانیِ نرمِ محصول‌هایِ دیجیتال — خواستهٔ «حذفِ کامل» بدونِ حذفِ داده.

مالکِ محصول گفت محصول‌هایِ دیجیتال حذف شوند و برایِ دادهٔ موجود «بهترین تصمیمِ فنی را بگیر».
پ۷۸ درِ ساختنِ تازه را بست؛ پ۹۴ ابزارِ حذفِ سخت را با سه قفل ساخت (بکاپ + تاییدِ متنی + توقفِ اجباری
وقتی سفارشی به محصولِ دیجیتال وصل است). این فاز همان خواسته را **بدونِ از‌بین‌رفتنِ داده** محقق می‌کند:
ستونِ افزودنی `products.retired_at` (قاعدهٔ ۴: هیچ ستون/جدولی حذف نمی‌شود ⇒ این برگشتنی است).

ادعاها (همه در همین فایل سنجیده می‌شوند):
۱. بایگانی ⇒ محصولِ دیجیتال از `get_active_by_shop_bot`، از `category_view`، از پرامپتِ AI و از
   هشدارِ موجودی بیرون می‌رود؛ ولی ردیف، `kind='digital'`، استخرِ کد و سفارش‌ها دست‌نخورده می‌مانند.
۲. `unretire_digital` دقیقاً همان تعداد را برمی‌گرداند (صفر ردیفِ بایگانی‌شده باقی نمی‌ماند).
۳. `digital_service.is_digital` به بایگانی نگاه نمی‌کند ⇒ تحویلِ سفارش‌هایِ دیجیتالِ *قبلی* سالم می‌ماند.
۴. `count_digital(retired=True/False/None)` سه حالت را درست می‌شمارد.
۵. پنل: دکمه ⇒ شمارشِ واقعی + صفحهٔ تایید؛ «بی‌خیال» ⇒ صفر تغییر؛ «بله» ⇒ بایگانی؛ صفحهٔ دوم ⇒ فقط
   راهِ بازگشت؛ «بازگرداندنِ بایگانی» ⇒ برگشت. کال‌بکِ کاربرِ دیگر ⇒ صفر ویرایش/صفر تغییرِ داده.

اجرا: python3 tests_manual/run_one.py test_p97_digital_archive.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from sqlalchemy import func, select  # noqa: E402

from app.bots.main_bot import texts  # noqa: E402
from app.database.models import Customer, DigitalCode, OrderConsultation, OrderType, Product, ShopBot  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import ai_context, digital_service, order_service, product_service, stock_alert_service  # noqa: E402
from harness import build_test_dispatchers, reset_database  # noqa: E402
from phase4_helpers import Chat, callbacks  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

OWNER_TG_ID = 9_700_000_001
SHOP_BOT_TG_ID = 9_700_000_002
FOREIGN_TG_ID = 9_700_000_009

SHOP_ID = 0
DP = None


async def _seed(with_digital: bool = True) -> None:
    """یکِ فروشگاهِ فروشگاهی + یکِ محصولِ فیزیکی + (اختیاری) دو دیجیتال، یکی استخرکد و یکی لینک."""
    global SHOP_ID
    await reset_database()
    SHOP_ID = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    async with session_scope() as session:
        await product_service.create_product(session, SHOP_ID, "مدادِ ساده", None, 15_000, None, stock_quantity=1)
        if with_digital:
            await product_service.create_digital_product(
                session, SHOP_ID, "دوره‌یِ ویدیویی", None, 200_000, None, "link", link="https://invalid.example/x"
            )
            pool = await product_service.create_digital_product(session, SHOP_ID, "لایسنس", None, 50_000, None, "code_pool")
            await digital_service.add_codes(session, pool, ["A1B2C3", "D4E5F6"])
            await digital_service.sync_pool_stock(session, pool)
            customer = Customer(shop_bot_id=SHOP_ID, telegram_id=9_700_000_003, first_name="مشتری")
            session.add(customer)
            await session.flush()
            await order_service.create_order(
                session, SHOP_ID, customer.id, OrderType.ORDER, "سفارشِ لایسنس", 50_000, product_id=pool.id, quantity=1
            )
        await session.commit()


async def _counts() -> tuple[int, int, int]:
    """(تعدادِ ردیف‌هایِ محصول، تعدادِ کدها، تعدادِ سفارش‌ها) — برایِ اثباتِ «هیچ چیز پاک نشد»."""
    async with session_scope() as session:
        rows = (
            await session.execute(
                select(func.count()).select_from(Product).where(Product.shop_bot_id == SHOP_ID)
            )
        ).scalar_one()
        codes = (await session.execute(select(func.count()).select_from(DigitalCode))).scalar_one()
        orders = (
            await session.execute(
                select(func.count()).select_from(OrderConsultation).where(OrderConsultation.shop_bot_id == SHOP_ID)
            )
        ).scalar_one()
    return rows, codes, orders


async def _retired_names() -> list[str]:
    async with session_scope() as session:
        return sorted(
            (
                await session.execute(
                    select(Product.name).where(Product.shop_bot_id == SHOP_ID, Product.retired_at.is_not(None))
                )
            )
            .scalars()
            .all()
        )


# ============================================================================= ۱ + ۲
async def test_archive_hides_everything_but_deletes_nothing() -> None:
    await _seed()
    before = await _counts()
    async with session_scope() as session:
        shop_bot = await session.get(ShopBot, SHOP_ID)
        assert len(await product_service.get_active_by_shop_bot(session, SHOP_ID)) == 3
        prompt = ai_context.build_system_prompt(shop_bot, await product_service.get_active_by_shop_bot(session, SHOP_ID))
        assert "لایسنس" in prompt and "دوره‌یِ ویدیویی" in prompt, prompt[-400:]
        assert "مدادِ ساده" in prompt
        # هشدارِ موجودی با سقفِ ۳: هر سه پایین‌اند (فیزیکی=۱، استخرِ کد=۲، لینکی=None ⇒ بی‌موجودی)
        alerts = await stock_alert_service.low_stock_rows(session, SHOP_ID, 3)
        assert "لایسنس" in {p.name for p in alerts}, [p.name for p in alerts]

        assert await product_service.retire_digital(session, SHOP_ID) == 2
        await session.commit()

        active = await product_service.get_active_by_shop_bot(session, SHOP_ID)
        assert [p.name for p in active] == ["مدادِ ساده"], [p.name for p in active]
        prompt = ai_context.build_system_prompt(shop_bot, active)
        assert "لایسنس" not in prompt and "دوره‌یِ ویدیویی" not in prompt, prompt[-400:]
        assert "مدادِ ساده" in prompt
        groups, buckets, unassigned = product_service.category_view(active)
        assert "لایسنس" not in groups, groups
        flat = [p.name for items in buckets.values() for p in items] + [p.name for p in unassigned]
        assert flat == ["مدادِ ساده"], flat
        assert "لایسنس" not in {p.name for p in await stock_alert_service.low_stock_rows(session, SHOP_ID, 3)}

    after = await _counts()
    assert after == before, f"بایگانی نباید ردیف/کد/سفارش را کم کند: {before} → {after}"
    async with session_scope() as session:
        digital = list(
            (
                await session.execute(select(Product).where(Product.shop_bot_id == SHOP_ID, Product.kind == "digital"))
            )
            .scalars()
            .all()
        )
        assert len(digital) == 2, "kind='digital' عوض نشد"
        assert all(digital_service.is_digital(p) for p in digital), "مسیرِ تحویل به بایگانی نگاه نمی‌کند"
        order = (
            await session.execute(select(OrderConsultation).where(OrderConsultation.shop_bot_id == SHOP_ID))
        ).scalars().one()
        assert order.product_id in {p.id for p in digital}, "سفارشِ دیجیتالِ پیشین به ردیفِ بایگانی‌شده وصل می‌ماند"

    async with session_scope() as session:
        assert await product_service.unretire_digital(session, SHOP_ID) == 2
        await session.commit()
    assert await _retired_names() == []
    async with session_scope() as session:
        assert len(await product_service.get_active_by_shop_bot(session, SHOP_ID)) == 3
    print("PASS test_archive_hides_everything_but_deletes_nothing")


# ============================================================================= ۳
async def test_counts_are_exact() -> None:
    await _seed()
    async with session_scope() as session:
        assert await product_service.count_digital(session, SHOP_ID) == 2
        assert await product_service.count_digital(session, SHOP_ID, retired=False) == 2
        assert await product_service.count_digital(session, SHOP_ID, retired=True) == 0
        await product_service.retire_digital(session, SHOP_ID)
        assert await product_service.count_digital(session, SHOP_ID, retired=True) == 2
        assert await product_service.count_digital(session, SHOP_ID, retired=False) == 0
        assert await product_service.count_digital(session, SHOP_ID) == 2, "بدونِ فلگ یعنی «هر دو حالت»"
        await session.commit()
    # فروشگاهِ بدونِ دیجیتال: صفر، و بایگانی کردن چیزی را می‌سازد؟ نه
    await _seed(with_digital=False)
    async with session_scope() as session:
        assert await product_service.count_digital(session, SHOP_ID) == 0
        assert await product_service.retire_digital(session, SHOP_ID) == 0
        assert await product_service.unretire_digital(session, SHOP_ID) == 0
        await session.commit()
    print("PASS test_counts_are_exact")


# ============================================================================= ۴ و ۵
async def test_panel_confirm_and_undo_flow() -> None:
    await _seed()
    owner = Chat(DP, OWNER_TG_ID)
    await owner.say("📦 محصولات")
    flat = callbacks(owner.last_markup)
    assert "product_archive_digital" in flat, flat
    assert max(len(item.encode("utf-8")) for item in flat) <= 64, flat

    await owner.tap("product_archive_digital")
    body = owner.last_text
    assert "۲ محصولِ دیجیتال" in body and "هیچ ردیف، کد یا سفارشی پاک نمی‌شود" in body, body
    markup = callbacks(owner.last_markup)
    assert "product_archive_digital_yes" in markup and "product_archive_digital_no" in markup, markup
    assert "product_archive_digital_undo" not in markup, "هنوز چیزی بایگانی نشده ⇒ راهِ بازگشت نشان داده نمی‌شود"

    await owner.tap("product_archive_digital_no")
    assert owner.last_toast["text"] == "بی‌خیال، چیزی عوض نشود", owner.last_toast
    assert await _retired_names() == []

    await owner.tap("product_archive_digital_yes")
    assert "بایگانی شد: ۲" in owner.last_toast["text"], owner.last_toast
    assert await _retired_names() == ["دوره‌یِ ویدیویی", "لایسنس"]

    # صفحهٔ دوم: چیزی برایِ بایگانی نیست ⇒ به‌جایِ alertِ بی‌مصرف، همان‌جا راهِ بازگشت هست
    await owner.tap("product_archive_digital")
    assert "بایگانی شده‌اند" in owner.last_text, owner.last_text
    markup = callbacks(owner.last_markup)
    assert markup == ["product_archive_digital_undo"], markup

    await owner.tap("product_archive_digital_undo")
    assert "بازگشت: ۲" in owner.last_toast["text"], owner.last_toast
    assert await _retired_names() == []
    print("PASS test_panel_confirm_and_undo_flow")


async def test_foreign_user_changes_nothing() -> None:
    await _seed()
    stranger = Chat(DP, FOREIGN_TG_ID)
    for data in ("product_archive_digital", "product_archive_digital_yes", "product_archive_digital_undo"):
        await stranger.tap(data)
    assert not stranger.session.edited_texts, stranger.session.edited_texts
    assert not stranger.session.sent_messages, stranger.session.sent_messages
    assert await _retired_names() == [], "کال‌بکِ دستکاری‌شده نباید هیچ ردیفی را عوض کند"
    print("PASS test_foreign_user_changes_nothing")


async def main() -> None:
    global DP
    DP = build_test_dispatchers()[0]
    await test_archive_hides_everything_but_deletes_nothing()
    await test_counts_are_exact()
    await test_panel_confirm_and_undo_flow()
    await test_foreign_user_changes_nothing()


if __name__ == "__main__":
    asyncio.run(main())
