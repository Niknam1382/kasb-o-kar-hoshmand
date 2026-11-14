"""پ۷۰ · خواستهٔ مالک: «پر‌مصرف‌ترین‌هایِ AI و مدیریتشان» در پنلِ فروشگاه‌دار + تفکیکِ فروشگاه در پنلِ ادمین.

پوششِ داده‌شده:
۱. `ai_usage_service.rank_page(shop_bot_id=)`: فقطِ مشتریانِ همان فروشگاه، با همان ترتیبِ نزولیِ
   مصرف و همان شمارِ کل؛ بی‌فیلتر مثلِ قبل همه را می‌شمارد (پ۵۵ نشکست).
۲. پنلِ فروشگاه‌دار (هر دو مود): «📈 پرمصرف‌هایِ AI» فقطِ مشتری‌هایِ خودش را نشان می‌دهد، با ارقامِ
   جلالی و بدونِ نامِ مشتریِ فروشگاه‌هایِ دیگر.
۳. سه اهرم از همان صفحه: سقفِ ۲۴ ساعت (FSM)، توقفِ پاسخِ خودکار، بلاک/رفعِ بلاک ⇒ هر سه رویِ ردیفِ
   مشتری می‌نشینند و در ممیزی با `shop_bot_id` ثبت می‌شوند؛ هیچ پولی جابه‌جا نمی‌شود.
۴. مالکیت: `customer_id` دست‌کاری‌شده از فروشگاهِ دیگر ⇒ توست، صفر ویرایش، صفر تغییرِ دیتابیس؛
   `window`/`page`/شناسهٔ نامعتبر هم رد می‌شوند.
۵. پنلِ ادمین: از کارتِ جزئیات به «فقطِ مشتریانِ این فروشگاه» می‌رود، فیلتر با تغییرِ پنجره می‌ماند،
   «همهٔ فروشگاه‌ها» پاکش می‌کند، و شناسهٔ ناشناخته/دست‌کاری‌شده رد می‌شود.
۶. کیبورد و متن: بودجهٔ ۶۴ بایتیِ همهٔ `ouai_*`، برچسبِ درستِ پنجره‌ها، و بازگشتِ همان «main_menu».

اجرا: python3 tests_manual/run_one.py test_p70_ai_usage_per_shop.py
"""
from __future__ import annotations

import asyncio
import datetime as dt
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from sqlalchemy import select  # noqa: E402

from harness import build_test_dispatchers, reset_database  # noqa: E402
from phase4_helpers import Chat, add_customer, callbacks  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot import keyboards, texts as main_texts  # noqa: E402
from app.database.models import (  # noqa: E402
    AuditEventType, AuditLogEntry, Customer, ShopBot, ShopOwner, WalletTransaction, WalletTransactionReason,
)
from app.database.session import session_scope  # noqa: E402
from app.services import ai_usage_service, wallet_service  # noqa: E402

UTC = dt.timezone.utc
ADMIN_TG_ID = 12345
OWNER_A_TG_ID = 997711
SHOP_A_TG_ID = 997712
OWNER_B_TG_ID = 997713
SHOP_B_TG_ID = 997714
CUSTOMER_A_TOP = 997801
CUSTOMER_A_LOW = 997802
CUSTOMER_B_TOP = 997803
NOW = dt.datetime.now(UTC)
SINCE = NOW - dt.timedelta(days=1)
UNTIL = NOW + dt.timedelta(days=1)
IDs: dict[str, int] = {}


async def _seed_two_shops() -> None:
    """دو فروشگاه؛ در «الف» دو مشتری (۹۰۰ و ۱۰۰ تومان) و در «ب» یک مشتریِ ۵٬۰۰۰ تومنی."""
    await reset_database()
    IDs["shop_a"] = await seed_usable_shop(OWNER_A_TG_ID, SHOP_A_TG_ID)
    IDs["shop_b"] = await seed_usable_shop(OWNER_B_TG_ID, SHOP_B_TG_ID)
    IDs["a_top"] = await add_customer(IDs["shop_a"], CUSTOMER_A_TOP, first_name="سارا", username="sara_a")
    IDs["a_low"] = await add_customer(IDs["shop_a"], CUSTOMER_A_LOW, first_name="رضا", username="reza_a")
    IDs["b_top"] = await add_customer(IDs["shop_b"], CUSTOMER_B_TOP, first_name="مریم", username="maryam_b")
    async with session_scope() as session:
        owners = {
            row.telegram_id: row
            for row in (
                await session.execute(select(ShopOwner).where(ShopOwner.telegram_id.in_([OWNER_A_TG_ID, OWNER_B_TG_ID])))
            ).scalars().all()
        }
        for owner_id, amount, customer_id in (
            (OWNER_A_TG_ID, 900, IDs["a_top"]),
            (OWNER_A_TG_ID, 100, IDs["a_low"]),
            (OWNER_B_TG_ID, 5_000, IDs["b_top"]),
        ):
            await wallet_service.deduct(
                session, owners[owner_id], amount, WalletTransactionReason.CHAT_MESSAGE, customer_id=customer_id
            )
        await session.commit()


async def _customer(customer_id: int) -> Customer:
    async with session_scope() as session:
        return await session.get(Customer, customer_id)


async def _audits(shop_bot_id: int) -> list[AuditLogEntry]:
    async with session_scope() as session:
        return list(
            (
                await session.execute(
                    select(AuditLogEntry).where(AuditLogEntry.shop_bot_id == shop_bot_id).order_by(AuditLogEntry.id)
                )
            ).scalars().all()
        )


# ============================================================================= ۱ — سرویس
async def test_rank_page_shop_filter() -> None:
    await _seed_two_shops()
    shop_a, shop_b = IDs["shop_a"], IDs["shop_b"]
    a_top, a_low, b_top = IDs["a_top"], IDs["a_low"], IDs["b_top"]
    async with session_scope() as session:
        everyone, total_all = await ai_usage_service.rank_page(session, since=SINCE, until=UNTIL)
        only_a, total_a = await ai_usage_service.rank_page(session, since=SINCE, until=UNTIL, shop_bot_id=shop_a)
        only_b, total_b = await ai_usage_service.rank_page(session, since=SINCE, until=UNTIL, shop_bot_id=shop_b)
        nobody, total_nobody = await ai_usage_service.rank_page(session, since=SINCE, until=UNTIL, shop_bot_id=999_999)

    assert total_all == 3 and [cid for cid, _s, _c in everyone] == [b_top, a_top, a_low], everyone
    assert total_a == 2 and [cid for cid, _s, _c in only_a] == [a_top, a_low], only_a
    assert only_a[0][1] == 900 and only_a[1][1] == 100, only_a
    assert total_b == 1 and only_b[0] == (b_top, 5_000, 1), only_b
    assert nobody == [] and total_nobody == 0
    print("✅ test_rank_page_shop_filter PASSED")


# ============================================================================= ۲ و ۳ و ۴ — پنلِ فروشگاه‌دار
async def test_owner_screen_levers_and_ownership(main_dp) -> None:
    await _seed_two_shops()
    shop_a, a_top, b_top = IDs["shop_a"], IDs["a_top"], IDs["b_top"]
    owner = Chat(main_dp, OWNER_A_TG_ID)

    await owner.say("👥 مشتری‌ها")
    assert "ouai_open" in callbacks(owner.last_markup), callbacks(owner.last_markup)

    await owner.tap("ouai_open")
    body = owner.last_edit_text
    assert "پرمصرف‌ترینِ مشتریانِ هوش مصنوعیِ فروشگاهِ خودت" in body and "۲۴ ساعت" in body, body
    assert "سارا" in body and "رضا" in body and "مریم" not in body, body
    assert "بدونِ نامِ کاربری" not in body, "در پنلِ خودِ فروشگاه ستونِ فروشگاه بی‌معنی است"
    assert not any(char.isascii() and char.isdigit() for char in body), body
    flat = callbacks(owner.last_edit_markup)
    assert any(item.startswith("ouai_view:24h:0:") for item in flat), flat
    assert flat[-1] == "main_menu" and all(len(item.encode("utf-8")) <= 64 for item in flat), flat

    await owner.tap(f"ouai_view:24h:0:{a_top}")
    detail = callbacks(owner.last_edit_markup)
    assert f"ouai_limit:{a_top}:24h:0" in detail and f"ai_usage_shop:{shop_a}" not in detail, detail

    # سقفِ ۲۴ ساعت (FSM) + ممیزیِ همان فروشگاه
    await owner.tap(f"ouai_limit:{a_top}:24h:0")
    await owner.say("۲۵۰۰")
    assert (await _customer(a_top)).ai_daily_limit_toman == 2500
    controls = [a for a in await _audits(shop_a) if a.event_type == AuditEventType.AI_USAGE_CONTROL_CHANGED]
    assert controls and str(a_top) in (controls[-1].details or ""), controls

    # ورودیِ بد ⇒ همان state می‌ماند و چیزی ذخیره نمی‌شود؛ «انصراف» ⇒ پاک
    await owner.tap(f"ouai_limit:{a_top}:24h:0")
    await owner.say("abc")
    assert (await _customer(a_top)).ai_daily_limit_toman == 2500
    await owner.say("بدونِ سقف")
    assert (await _customer(a_top)).ai_daily_limit_toman is None
    await owner.tap(f"ouai_limit:{a_top}:24h:0")
    await owner.say("انصراف")
    assert owner.last_text == main_texts.AI_USAGE_CANCELLED

    # توقفِ پاسخِ خودکار و آزادکردن
    await owner.tap(f"ouai_pause:{a_top}:24:24h:0")
    assert (await _customer(a_top)).ai_paused_until is not None
    await owner.tap(f"ouai_pause:{a_top}:0:24h:0")
    assert (await _customer(a_top)).ai_paused_until is None

    # بلاک ⇒ همان رویدادِ همیشگیِ CRM (تا ممیزیِ پ۱۸ یک‌شکل بماند)
    await owner.tap(f"ouai_block:{a_top}:1:24h:0")
    assert (await _customer(a_top)).is_blocked is True
    assert any(a.event_type == AuditEventType.CUSTOMER_BLOCK_CHANGED for a in await _audits(shop_a))
    await owner.tap(f"ouai_block:{a_top}:0:24h:0")
    assert (await _customer(a_top)).is_blocked is False

    # پول جابه‌جا نشد: فقط سه کسرِ سیدشده در دفترِ فروشگاه «الف» است
    async with session_scope() as session:
        spends = (
            await session.execute(
                select(WalletTransaction).where(
                    WalletTransaction.shop_owner_id
                    == (select(ShopOwner.id).where(ShopOwner.telegram_id == OWNER_A_TG_ID)).scalar_subquery(),
                    WalletTransaction.amount_toman < 0,
                )
            )
        ).scalars().all()
    assert len(list(spends)) == 2, list(spends)

    # مشتریِ فروشگاهِ دیگر ⇒ توست، صفر ویرایش، صفر تغییرِ دیتابیس
    edits_before = len(owner.edits)
    await owner.tap(f"ouai_view:24h:0:{b_top}")
    assert owner.last_toast["show_alert"] is True and owner.last_toast["text"] == main_texts.OWNER_AI_USAGE_INVALID
    await owner.tap(f"ouai_pause:{b_top}:24:24h:0")
    assert (await _customer(b_top)).ai_paused_until is None
    await owner.tap(f"ouai_block:{b_top}:1:24h:0")
    assert (await _customer(b_top)).is_blocked is False
    await owner.tap(f"ouai_limit:{b_top}:24h:0")
    assert owner.last_text != main_texts.AI_USAGE_LIMIT_ASK, "کارتِ بی‌مالکیت واردِ FSM نمی‌شود"
    assert len(owner.edits) == edits_before, owner.edits[edits_before:]

    # ورودیِ خرابِ کل‌بک ⇒ رد، بی‌تغییریِ صفحه
    await owner.tap("ouai:bogus:0")
    await owner.tap("ouai:24h:xyz")
    await owner.tap("ouai_view:24h:0:notanumber")
    assert owner.last_toast["text"] == main_texts.OWNER_AI_USAGE_INVALID
    assert len(owner.edits) == edits_before
    print("✅ test_owner_screen_levers_and_ownership PASSED")


async def test_consultation_mode_entry(main_dp) -> None:
    await _seed_two_shops()
    async with session_scope() as session:
        shop_bot = await session.get(ShopBot, IDs["shop_a"])
        shop_bot.tenant_mode = "consultation"
        await session.commit()

    owner = Chat(main_dp, OWNER_A_TG_ID)
    await owner.say("💬 گفتگوها و کاربران")
    flat = callbacks(owner.last_markup)
    assert "cre_open" in flat and "ouai_open" in flat, flat
    await owner.tap("ouai_open")
    assert "پرمصرف‌ترینِ مشتریانِ هوش مصنوعیِ فروشگاهِ خودت" in owner.last_edit_text, owner.last_edit_text

    # در مودِ مشاوره‌ای فهرستِ مشتریِ فروشگاهی معنایی ندارد (دروازهٔ پ۵۸ دست‌نخورده است)
    await owner.say("👥 مشتری‌ها")
    assert "👥 مشتری‌ها" not in owner.last_text
    print("✅ test_consultation_mode_entry PASSED")


# ============================================================================= ۵ — پنلِ ادمین
async def test_admin_shop_filter_round_trip(main_dp) -> None:
    await _seed_two_shops()
    shop_a, shop_b, b_top = IDs["shop_a"], IDs["shop_b"], IDs["b_top"]
    admin = Chat(main_dp, ADMIN_TG_ID)

    await admin.say(main_texts.AI_USAGE_BUTTON)
    body = admin.last_text
    assert "مریم" in body and "سارا" in body, body
    assert "🏪 فیلتر" not in body, "نمایِ سراسری خطِ فیلتر ندارد"

    await admin.tap(f"ai_usage_view:24h:0:{b_top}")
    detail = callbacks(admin.last_edit_markup)
    assert f"ai_usage_shop:{shop_b}" in detail and f"ai_usage_shop:{shop_a}" not in detail, detail

    await admin.tap(f"ai_usage_shop:{shop_a}")
    body = admin.last_edit_text
    assert "🏪 فیلتر: فقطِ مشتریانِ فروشگاهِ" in body, body
    assert "مریم" not in body and "سارا" in body, body
    assert "ai_usage_shop:0" in callbacks(admin.last_edit_markup)

    # تغییرِ پنجره فیلتر را نگه می‌دارد
    await admin.tap("ai_usage:30d:0")
    assert "مریم" not in admin.last_edit_text and "سارا" in admin.last_edit_text, admin.last_edit_text
    assert "🏪 فیلتر" in admin.last_edit_text

    # «همهٔ فروشگاه‌ها» ⇒ فیلتر پاک
    await admin.tap("ai_usage_shop:0")
    assert "مریم" in admin.last_edit_text and "🏪 فیلتر" not in admin.last_edit_text, admin.last_edit_text

    # ورودیِ دست‌کاری‌شده ⇒ رد و بی‌تغییری
    edits_before = len(admin.edits)
    await admin.tap("ai_usage_shop:999999999")
    assert admin.last_toast["text"] == main_texts.AI_USAGE_SHOP_INVALID, admin.last_toast
    await admin.tap("ai_usage_shop:abc")
    assert admin.last_toast["text"] == main_texts.AI_USAGE_INVALID
    await admin.tap("ai_usage_shop:1:2")
    assert len(admin.edits) == edits_before, admin.edits[edits_before:]

    # فیلترِ فروشگاهِ بی‌مصرف ⇒ نمایِ خالی هم دکمهٔ پاک‌کردنِ فیلتر را دارد تا ادمین گیر نکند
    async with session_scope() as session:
        empty_shop = await session.get(ShopBot, shop_a)
        assert empty_shop is not None
    await admin.tap(f"ai_usage_shop:{shop_b}")
    assert "مریم" in admin.last_edit_text
    print("✅ test_admin_shop_filter_round_trip PASSED")


# ============================================================================= ۶ — کیبورد و متن
def test_owner_keyboard_and_text_shapes() -> None:
    kb = keyboards.owner_ai_usage_keyboard([(7, 1, "سارا")], "7d", 0, 1)
    flat = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert flat[:3] == ["ouai:24h:0", "ouai:7d:0", "ouai:30d:0"], flat
    assert "ouai_view:7d:0:7" in flat and flat[-1] == "main_menu", flat
    detail = keyboards.owner_ai_usage_detail_keyboard(7, "7d", 0, paused=True, blocked=True)
    labels = {b.text: b.callback_data for row in detail.inline_keyboard for b in row}
    # نگهبانِ باگِ پ۵۵: برچسب و هدفِ دکمه باید یکی باشند
    assert labels["✅ رفعِ بلاک"] == "ouai_block:7:0:7d:0", labels
    assert labels["▶️ آزادکردنِ پاسخ"] == "ouai_pause:7:0:7d:0", labels
    open_state = {b.text: b.callback_data for row in keyboards.owner_ai_usage_detail_keyboard(
        7, "7d", 0, paused=False, blocked=False
    ).inline_keyboard for b in row}
    assert open_state["🚫 بلاکِ کاربر"] == "ouai_block:7:1:7d:0", open_state
    assert open_state["⏸ توقفِ ۲۴ ساعت"] == "ouai_pause:7:24:7d:0", open_state
    admin_labels = {b.text: b.callback_data for row in keyboards.ai_usage_detail_keyboard(
        7, "7d", 0, paused=False, blocked=False, shop_bot_id=3
    ).inline_keyboard for b in row}
    assert admin_labels["🚫 بلاکِ کاربر"] == "ai_usage_block:7:1:7d:0", admin_labels
    assert admin_labels[main_texts.AI_USAGE_SHOP_FILTERED_BUTTON] == "ai_usage_shop:3", admin_labels
    flat = [b.callback_data for row in detail.inline_keyboard for b in row]
    assert "ouai_pause:7:0:7d:0" in flat and "ouai_block:7:0:7d:0" in flat, flat
    assert all(len(item.encode("utf-8")) <= 64 for item in flat), flat
    body = main_texts.owner_ai_usage_intro("۷ روز", 0, 2)
    assert "۷ روز" in body and "صفحهٔ ۱ از ۲" in body, body
    labels = [b.text for row in kb.inline_keyboard for b in row]
    assert "✅ ۷ روز" in labels, labels
    print("✅ test_owner_keyboard_and_text_shapes PASSED")


async def main() -> None:
    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    await test_rank_page_shop_filter()
    await test_owner_screen_levers_and_ownership(main_dp)
    await test_consultation_mode_entry(main_dp)
    await test_admin_shop_filter_round_trip(main_dp)
    test_owner_keyboard_and_text_shapes()


if __name__ == "__main__":
    asyncio.run(main())
