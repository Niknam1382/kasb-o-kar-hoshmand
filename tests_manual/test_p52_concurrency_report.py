from __future__ import annotations

import asyncio
import datetime as dt
import math
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402
from harness import FakeSession, build_test_dispatchers, make_callback_update, make_message_update, reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot import keyboards, router as main_router, texts  # noqa: E402
from app.bots.main_bot.states import PerfRangeStates  # noqa: E402
from app.database.models import (  # noqa: E402
    ConversationMessage, OrderConsultation, OrderPayment, OrderType, PaymentEventLog,
    ShopBot, WalletTransaction, WalletTransactionReason,
)
from app.database.session import session_scope  # noqa: E402
from app.services import customer_service, perf_report_service as perf  # noqa: E402
from app.utils.jalali import format_jalali_datetime  # noqa: E402

UTC = dt.timezone.utc
START = dt.datetime(2026, 10, 1, 10, 2, tzinfo=UTC)
END = START + dt.timedelta(minutes=13)
NOW = END + dt.timedelta(days=20)
ADMIN = 12345
OWNER = 995201
TOKEN = "520000:FAKE_MAIN_BOT_TOKEN_FOR_P52_TESTING_ONLY"


def test_grain_and_estimate() -> None:
    for hours, minutes in ((1, 5), (24, 10), (168, 60), (960, 360), (4776, 1440)):
        assert perf.auto_grain(hours) == minutes
    for hours in (2, 26, 192, 960, 4800, 24 * 365 * 500):
        assert math.ceil(hours * 60 / perf.auto_grain(hours)) + 1 <= perf.MAX_BUCKETS
    assert perf.ai_concurrency_estimate(120) == 10
    assert perf.ai_concurrency_estimate(0.00001) == 1
    assert perf.ai_concurrency_estimate(0) == 0
    assert perf.ai_concurrency_estimate(60, 12) == 12
    print("PASS test_grain_and_estimate")


async def seed() -> None:
    await reset_database()
    shop_id = await seed_usable_shop(OWNER, 995202)
    async with session_scope() as session:
        shop = await session.get(ShopBot, shop_id)
        customers = [
            await customer_service.get_or_create_customer(session, shop_id, 5200 + index, "مشتری", None, platform=platform)
            for index, platform in enumerate(("telegram", "bale", "instagram"))
        ]
        moments = (START - dt.timedelta(microseconds=1), START, END - dt.timedelta(microseconds=1), END, NOW + dt.timedelta(days=1))
        for index, moment in enumerate(moments):
            session.add_all([
                ConversationMessage(customer_id=customers[0].id, role="user", content="سلام", created_at=moment),
                WalletTransaction(shop_owner_id=shop.shop_owner_id, amount_toman=-50,
                                  reason=WalletTransactionReason.CHAT_MESSAGE, created_at=moment),
                OrderConsultation(shop_bot_id=shop_id, customer_id=customers[0].id, type=OrderType.ORDER,
                                  summary="سفارش", created_at=moment),
                OrderConsultation(shop_bot_id=shop_id, customer_id=customers[0].id, type=OrderType.CONSULTATION,
                                  summary="مشاوره", created_at=moment),
                OrderPayment(shop_bot_id=shop_id, group_id=f"p52-{index}", method="bale", status="paid",
                             amount_toman=100, created_at=moment),
                PaymentEventLog(provider="bale", direction="in", method="test", created_at=moment),
            ])
        session.add_all([
            ConversationMessage(customer_id=customers[0].id, role="assistant", content="پاسخ", created_at=START),
            ConversationMessage(customer_id=customers[1].id, role="user", content="سلام", created_at=START),
            ConversationMessage(customer_id=customers[2].id, role="user", content="سلام", created_at=START),
            ConversationMessage(customer_id=customers[0].id, role="user", content="اکنون", created_at=NOW - dt.timedelta(minutes=1)),
        ])


async def report(**kwargs) -> dict:
    async with session_scope() as session:
        return await perf.build(session, now=NOW, **kwargs)


async def test_all_counts_use_exact_boundaries() -> None:
    data = await report(since=START, until=END)
    assert data["since"] == START and data["until"] == END
    assert data["messages"] == 4 and data["customers"] == 3
    for key in ("orders", "consultations", "payments_paid", "gateway_events"):
        assert data[key] == 2, (key, data[key])
    assert dict(data["features"])["چتِ متنی"] == 2
    assert data["channels"] == [("telegram", 1, 2), ("bale", 1, 1), ("instagram", 1, 1)]
    assert data["top_shops"] == [("shop_995202", 3, 4)]
    assert data["active_now"] == 1
    assert math.isclose(data["messages_per_minute"], 4 / 13)
    assert [value for _, value in data["series"]] == [3, 0, 1]
    assert data["series"][0][0] == START
    assert data["series"][-1][0] == END - dt.timedelta(minutes=5)
    assert data["peak_moment"] == START
    assert data["label"] == f"{format_jalali_datetime(START)} تا {format_jalali_datetime(END)}"
    print("PASS test_all_counts_use_exact_boundaries")


async def test_empty_long_and_open_ranges() -> None:
    empty = await report(since=START - dt.timedelta(days=10), until=START - dt.timedelta(days=1))
    assert empty["messages"] == 0 and empty["peak_moment"] is None
    assert empty["peak_customers"] == 0 and not any(n for _, n in empty["series"])
    assert empty["active_now"] == 1
    long = await report(since=dt.datetime(1900, 1, 1, tzinfo=UTC), until=END)
    assert len(long["series"]) <= perf.MAX_BUCKETS
    assert len(texts.perf_report_text(long)) < 4096
    opened = await report(since=START)
    assert opened["until"] == NOW and opened["messages"] == 6
    assert (await report(since=START, until=NOW + dt.timedelta(days=10)))["until"] == NOW
    for since, until in ((END, START), (END, END), (NOW + dt.timedelta(days=1), None)):
        try:
            await report(since=since, until=until)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid range accepted")
    print("PASS test_empty_long_and_open_ranges")


async def test_historical_epoch_edges() -> None:
    since = dt.datetime(1969, 12, 31, 23, 54, 59, 500000, tzinfo=UTC)
    until = dt.datetime(1969, 12, 31, 23, 58, tzinfo=UTC)
    shop_id = await seed_usable_shop(995230, 995231)
    async with session_scope() as session:
        customer = await customer_service.get_or_create_customer(session, shop_id, 5400, "مشتری", None)
        session.add(ConversationMessage(customer_id=customer.id, role="user", content="سلام", created_at=since))
    data = await report(since=since, until=until)
    assert data["messages"] == 1 and data["peak_customers"] == 1
    assert [value for _, value in data["series"]] == [1, 0]
    aligned = await report(since=since, until=dt.datetime(1969, 12, 31, 23, 55, tzinfo=UTC))
    assert aligned["series"] == [(since, 1)]
    earliest = await report(since=dt.datetime(1, 1, 1, tzinfo=UTC), until=dt.datetime(1, 10, 1, tzinfo=UTC))
    assert earliest["messages"] == 0 and len(earliest["series"]) <= perf.MAX_BUCKETS
    assert earliest["series"][0][0] == earliest["since"]
    assert all(earliest["since"] <= moment < earliest["until"] for moment, _ in earliest["series"])
    print("PASS test_historical_epoch_edges")


async def test_top_shops_are_separate_and_bounded() -> None:
    for index in range(6):
        shop_id = await seed_usable_shop(995210 + index, 995220 + index)
        async with session_scope() as session:
            shop = await session.get(ShopBot, shop_id)
            shop.bot_username = "shared_name"
            customer = await customer_service.get_or_create_customer(session, shop_id, 5300 + index, "مشتری", None)
            session.add_all([
                ConversationMessage(customer_id=customer.id, role="user", content="سلام", created_at=START)
                for _ in range(index + 1)
            ])
    data = await report(since=START, until=END)
    assert len(data["top_shops"]) == 5
    assert [messages for _, _, messages in data["top_shops"]] == [6, 5, 4, 4, 3]
    print("PASS test_top_shops_are_separate_and_bounded")


async def test_text_and_menu() -> None:
    data = await report(since=START, until=END)
    body = texts.perf_report_text(data)
    for phrase in ("تلگرام", "بله", "اینستاگرام", "بازهٔ دلخواه", "تخمینی", "نه ظرفیتِ تضمین‌شده", "مستقل از بازه"):
        assert phrase in body, phrase
    assert "۰٫۳۰۷۷" in body and len(body) < 4096
    assert "تعدادِ مصرف‌هایِ ثبت‌شده" in body
    assert all(not any("a" <= char.lower() <= "z" for char in label) for label, _ in data["features"])
    label = next(button for button in main_router._KNOWN_MENU_BUTTONS if "وضعیتِ همزمانی" in button)
    assert any(b.text == label for row in keyboards.admin_panel_keyboard(True).keyboard for b in row)
    for range_key in ("24h", "7d"):
        for has_range in (False, True):
            buttons = [b for row in keyboards.perf_report_keyboard(range_key, has_range).inline_keyboard for b in row]
            callbacks = [b.callback_data for b in buttons]
            assert all(len(value.encode()) <= 64 for value in callbacks)
            assert ("perf_range_clear" in callbacks) == has_range
            assert callbacks[-1] == "main_menu"
            selected = [b.callback_data for b in buttons if b.text.startswith("✅ ")]
            assert selected == ([] if has_range else [f"perf_range:{range_key}"])
    print("PASS test_text_and_menu")


async def test_panel_range_validation_and_cancel(dp) -> None:
    bot = Bot(token=TOKEN, session=FakeSession())
    state = dp.fsm.get_context(bot=bot, chat_id=ADMIN, user_id=ADMIN)
    seq = 0

    async def send(text=None, callback=None):
        nonlocal seq
        seq += 1
        update = make_callback_update(seq, data=callback, user_id=ADMIN) if callback else make_message_update(seq, text=text, user_id=ADMIN)
        await dp.feed_update(bot, update)
        return bot.session.sent_messages[-1]["text"]

    await send(callback="perf_range_from")
    for text in ("دیروز", "همه", "۲۰۲۶-۱۳-۰۱", "۹۹۹۹-۰۱-۰۱"):
        assert await send(text=text) == texts.PERF_RANGE_INVALID
        assert await state.get_state() == PerfRangeStates.waiting_from.state
    await send(text="۲۰۲۶-۱۰-۰۱ ۱۰:۰۲")
    for text in ("۲۰۲۶-۱۰-۰۱ ۱۰:۰۱", "۲۰۲۶-۱۰-۰۱ ۱۰:۰۲", "نامعتبر", "۹۹۹۹-۰۱-۰۱"):
        assert await send(text=text) == texts.PERF_RANGE_INVALID
        assert await state.get_state() == PerfRangeStates.waiting_until.state
    body = await send(text="۲۰۲۶-۱۰-۰۱ ۱۰:۱۵")
    assert "بازهٔ دلخواه" in body
    old = await state.get_data()
    assert old["perf_since"] == START.isoformat() and old["perf_until"] == END.isoformat()
    assert await state.get_state() is None
    await send(callback="perf_range_from")
    await send(text="۲۰۲۶-۰۹-۰۱")
    assert await send(text="انصراف") == texts.PERF_RANGE_CANCELLED
    assert await state.get_data() == old
    await send(callback="perf_range_from")
    await send(text="۲۰۲۶-۱۰-۰۱")
    assert "بازهٔ دلخواه" in await send(text="همه")
    await send(callback="perf_range:7d")
    assert not any(k.startswith("perf_") for k in await state.get_data())
    assert "۷ روز (هر ساعت)" in bot.session.sent_messages[-1]["text"]
    await send(callback="perf_range_from")
    await send(text="۲۰۲۶-۱۰-۰۱")
    await send(text="همه")
    await send(callback="perf_range_clear")
    assert not any(k.startswith("perf_") for k in await state.get_data())
    await bot.session.close()
    print("PASS test_panel_range_validation_and_cancel")


async def test_non_admin_is_denied(dp) -> None:
    bot = Bot(token=TOKEN, session=FakeSession())
    for index, value in enumerate(("perf_range_from", "perf_range_clear", "perf_range:24h"), 500):
        await dp.feed_update(bot, make_callback_update(index, data=value, user_id=OWNER))
    state = dp.fsm.get_context(bot=bot, chat_id=OWNER, user_id=OWNER)
    assert await state.get_state() is None
    assert not any("همزمانیِ مشتریان در هر دانه" in row["text"] for row in bot.session.sent_messages)
    await bot.session.close()
    print("PASS test_non_admin_is_denied")


async def main() -> None:
    test_grain_and_estimate()
    await seed()
    await test_all_counts_use_exact_boundaries()
    await test_empty_long_and_open_ranges()
    await test_text_and_menu()
    await test_historical_epoch_edges()
    await test_top_shops_are_separate_and_bounded()
    dp, _, _, _ = build_test_dispatchers()
    await test_panel_range_validation_and_cancel(dp)
    await test_non_admin_is_denied(dp)


if __name__ == "__main__":
    asyncio.run(main())
