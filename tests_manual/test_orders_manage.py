"""
تست: «🧾 مدیریتِ سفارش‌ها (جاری)» در پنلِ فروشگاه‌دار — منطقِ خالصِ فهرست (اولویت/فیلتر/صفحه‌بندی/callback) و جریانِ واقعیِ ربات
(فهرست، فیلتر «منتظرِ اقدام»، بازکردنِ سفارش با دکمه‌هایِ اقدامِ همان وضعیت، ایزولاسیونِ فروشگاه‌ها، callbackِ جعلی).

اجرا: python3 tests_manual/test_orders_manage.py
"""
from __future__ import annotations

import asyncio
import sys
from types import SimpleNamespace

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from sqlalchemy import select  # noqa: E402

from harness import build_test_dispatchers  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402
from test_orders_w2 import OTHER_OWNER, OTHER_SHOP_TG, OWNER, _Env, _seed  # noqa: E402
from test_payments_w3w4 import _configure, _datas  # noqa: E402

from app.bots.main_bot import keyboards  # noqa: E402
from app.bots.main_bot.handlers import orders_manage  # noqa: E402
from app.database.models import OrderConsultation  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import orders_manage_service as oms  # noqa: E402


def _row(row_id: int, status: str, group: str | None = None, customer_id: int = 1) -> SimpleNamespace:
    return SimpleNamespace(id=row_id, status=status, cart_checkout_group_id=group, customer_id=customer_id)


async def test_pure_grouping_priority_filter_and_paging() -> None:
    rows = [
        _row(1, "awaiting_payment", "gA"),
        _row(2, "awaiting_payment", "gA"),
        _row(3, "paid", "gB"),
        _row(4, "pending"),  # تک‌سفارش ⇒ کلیدِ o4
        _row(5, "receipt_submitted", "gC"),
        _row(6, "shipped", "gD"),
        _row(7, "refund_pending", "gE"),
    ]
    groups = oms.group_rows(rows)
    keys = [oms.group_key_of(g[0]) for g in groups]
    assert keys == ["gC", "o4", "gE", "gB", "gD", "gA"], "اولویت: رسید ← pending ← استرداد ← paid ← ارسال‌شده ← منتظرِ پرداخت"
    assert [r.id for r in groups[-1]] == [1, 2], "ردیف‌هایِ هر گروه کنارِ هم و مرتب"
    assert oms.group_status([_row(1, "awaiting_payment"), _row(2, "pending")]) == "pending", "گروهِ مختلط: تصمیم‌خواه‌تر"
    action = oms.apply_filter(groups, oms.FILTER_ACTION)
    assert [oms.group_key_of(g[0]) for g in action] == ["gC", "o4", "gE", "gB"]
    assert oms.apply_filter(groups, oms.FILTER_ALL) == groups
    counts = oms.status_counts(groups)
    assert counts["awaiting_payment"] == 1 and counts["paid"] == 1 and sum(counts.values()) == 6

    page, number, total = oms.paginate(list(range(12)), 2)
    assert page == [5, 6, 7, 8, 9] and (number, total) == (2, 3)
    assert oms.paginate(list(range(12)), 99)[1:] == (3, 3) and oms.paginate(list(range(12)), 0)[1] == 1
    assert oms.paginate([], 5) == ([], 1, 1)

    assert oms.parse_list_callback("om_l:act:2") == ("act", 2) and oms.parse_list_callback("om_l:all:1") == ("all", 1)
    for bad in (None, "", "om_l:xxx:1", "om_l:all:x", "om_l:all:-1", "om_l:all", "om_l:all:1:2", "om_l:all:12345", "other:all:1", "om_l:all:۱"):
        assert oms.parse_list_callback(bad) is None, bad
    assert oms.is_current_group([_row(1, "paid")]) and not oms.is_current_group([_row(1, "completed")]) and not oms.is_current_group([])
    print("✅ test_pure_grouping_priority_filter_and_paging PASSED")


async def test_panel_keyboard_has_button_for_sales_only() -> None:
    def texts_of(mode):
        return [b.text for row in keyboards.shop_owner_panel_keyboard(mode).keyboard for b in row]

    assert orders_manage.BTN_ORDERS_MANAGE in texts_of("sales") and orders_manage.BTN_ORDERS_MANAGE in texts_of(None)
    assert orders_manage.BTN_ORDERS_MANAGE not in texts_of("consultation")
    print("✅ test_panel_keyboard_has_button_for_sales_only PASSED")


async def test_flow_list_filter_open_and_isolation(shop_dp, main_dp, bot_manager, main_bot) -> None:
    shop_bot_id, p1, p2 = await _seed()
    env = _Env(shop_dp, main_dp, bot_manager, main_bot, shop_bot_id, p1, p2)
    for pid in (p1, p2):  # چند چک‌اوتِ پشت‌سرهم ⇒ موجودی نباید تمام بشه
        async with session_scope() as session:
            from app.database.models import Product

            (await session.get(Product, pid)).stock_quantity = 50

    sent = env.owner_bot.session.sent_messages
    await env.owner_say(orders_manage.BTN_ORDERS_MANAGE)
    assert sent[-1]["text"] == orders_manage.EMPTY_ALL, "بدونِ سفارش: پیامِ خالی"

    # g_pending: پرداختِ دستی (بدونِ روشِ پرداخت) ⇒ pending
    g_pending = await env.checkout([p1])
    # g_receipt: کارت‌به‌کارت با رسیدِ ثبت‌شده؛ g_wait: منتظرِ پرداخت
    await _configure(shop_bot_id, card=True)
    g_receipt = await env.checkout([p1, p2])
    await env.cust_cb(f"pm_card:{g_receipt}")
    await env.cust_cb(f"pay_receipt:{g_receipt}")
    await env.cust_say("۱۲۳۴۵۶۷۸۹۰۱۲")
    g_wait = await env.checkout([p2])
    await env.cust_cb(f"pm_card:{g_wait}")
    # g_dead: ردشده ⇒ جاری نیست
    g_dead = await env.checkout([p2])
    async with session_scope() as session:
        for row in (await session.execute(select(OrderConsultation).where(OrderConsultation.cart_checkout_group_id == g_dead))).scalars().all():
            row.status = "rejected"
    assert len({g_pending, g_receipt, g_wait, g_dead}) == 4

    await env.owner_say(orders_manage.BTN_ORDERS_MANAGE)
    message = sent[-1]
    datas = [d for d in _datas(message["reply_markup"]) if d.startswith("om_v:")]
    assert datas == [f"om_v:{g_receipt}", f"om_v:{g_pending}", f"om_v:{g_wait}"], datas
    assert "سفارش‌هایِ جاری: 3 مورد" in message["text"] and "منتظرِ اقدامِ تو: 2 مورد" in message["text"]
    assert f"om_v:{g_dead}" not in str(_datas(message["reply_markup"]))
    assert "om_l:act:1" in _datas(message["reply_markup"]) and "om_l:all:1" in _datas(message["reply_markup"])

    # فیلترِ «فقط منتظرِ اقدام» (edit)
    await env.owner_cb("om_l:act:1")
    edited = env.owner_bot.session.edited_texts[-1]
    assert "فیلتر: فقط منتظرِ اقدام" in edited["text"]
    assert [d for d in _datas(edited["reply_markup"]) if d.startswith("om_v:")] == [f"om_v:{g_receipt}", f"om_v:{g_pending}"]
    await env.owner_cb("om_l:all:99")  # صفحه‌یِ خارج از محدوده ⇒ clamp، نه خطا
    assert "صفحه" not in env.owner_bot.session.edited_texts[-1]["text"] or "1 از 1" in env.owner_bot.session.edited_texts[-1]["text"]

    # بازکردنِ سفارشِ رسیدِ ثبت‌شده ⇒ دکمه‌هایِ بررسیِ رسید
    await env.owner_cb(f"om_v:{g_receipt}")
    detail = sent[-1]
    assert "جمعِ کل" in detail["text"] and "250,000" in detail["text"] and "🧾 سفارش" in detail["text"]
    detail_datas = _datas(detail["reply_markup"])
    assert any(d.startswith("rcpt_ok:") for d in detail_datas) and any(d.startswith("rcpt_no:") for d in detail_datas)
    assert f"og_msg:{g_receipt}" in detail_datas and "om_l:all:1" in detail_datas

    # سفارشِ pending (گروهی) ⇒ تایید/ردِ قدیمی؛ تایید که بشه، با باز کردنِ دوباره «شروعِ پردازش» می‌بینه
    await env.owner_cb(f"om_v:{g_pending}")
    assert f"confirm_cart_group:{g_pending}" in _datas(sent[-1]["reply_markup"])
    await env.owner_cb(f"confirm_cart_group:{g_pending}")
    await env.owner_cb(f"om_v:{g_pending}")
    assert f"og_start:{g_pending}" in _datas(sent[-1]["reply_markup"]), "همان دکمه‌هایِ اقدامِ وضعیتِ فعلی"

    # منتظرِ پرداخت ⇒ ردِ سفارش + پیام به مشتری
    await env.owner_cb(f"om_v:{g_wait}")
    wait_datas = _datas(sent[-1]["reply_markup"])
    assert f"og_rej:{g_wait}" in wait_datas and f"og_msg:{g_wait}" in wait_datas

    # ردشده/جعلی/کهنه ⇒ هشدار؛ فروشگاهِ دیگه نمی‌بینه
    before = len(sent)
    for data in (f"om_v:{g_dead}", "om_v:zzzzzz", "om_v:", "om_l:bad:1", "om_l:all:x"):
        await env.owner_cb(data)
        assert env.owner_alerts()[-1].get("show_alert") is True, data
    assert len(sent) == before
    await seed_usable_shop(OTHER_OWNER, OTHER_SHOP_TG)
    await env.owner_cb(f"om_v:{g_receipt}", user_id=OTHER_OWNER)
    assert env.owner_alerts()[-1].get("show_alert") is True and len(sent) == before, "سفارشِ فروشگاهِ دیگه دیده نمی‌شه"
    await env.owner_say(orders_manage.BTN_ORDERS_MANAGE, user_id=OTHER_OWNER)
    assert sent[-1]["text"] == orders_manage.EMPTY_ALL, "فهرستِ فروشگاهِ دیگه خالی است"
    print("✅ test_flow_list_filter_open_and_isolation PASSED")


async def test_many_orders_paginate(shop_dp, main_dp, bot_manager, main_bot) -> None:
    shop_bot_id, p1, p2 = await _seed()
    env = _Env(shop_dp, main_dp, bot_manager, main_bot, shop_bot_id, p1, p2)
    from app.database.models import Customer, OrderType
    from app.services import customer_service, order_service

    async with session_scope() as session:
        customer = await customer_service.get_or_create_customer(session, shop_bot_id, 880777, "مشتریِ تست", None)
        for index in range(7):
            await order_service.create_order(session, shop_bot_id, customer.id, OrderType.ORDER, f"کالا {index}", 10_000 + index)
        assert await session.get(Customer, customer.id) is not None
    await env.owner_say(orders_manage.BTN_ORDERS_MANAGE)
    first = env.owner_bot.session.sent_messages[-1]
    assert len([d for d in _datas(first["reply_markup"]) if d.startswith("om_v:")]) == oms.PAGE_SIZE
    assert "صفحه‌یِ 1 از 2" in first["text"] and "om_l:all:2" in _datas(first["reply_markup"])
    await env.owner_cb("om_l:all:2")
    second = env.owner_bot.session.edited_texts[-1]
    assert len([d for d in _datas(second["reply_markup"]) if d.startswith("om_v:")]) == 2
    assert "صفحه‌یِ 2 از 2" in second["text"] and "om_l:all:1" in _datas(second["reply_markup"])
    print("✅ test_many_orders_paginate PASSED")


async def main() -> None:
    main_dp, shop_dp, bot_manager, main_bot = build_test_dispatchers()
    await test_pure_grouping_priority_filter_and_paging()
    await test_panel_keyboard_has_button_for_sales_only()
    await test_flow_list_filter_open_and_isolation(shop_dp, main_dp, bot_manager, main_bot)
    await test_many_orders_paginate(shop_dp, main_dp, bot_manager, main_bot)


if __name__ == "__main__":
    asyncio.run(main())
