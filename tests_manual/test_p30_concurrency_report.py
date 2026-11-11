"""
تست: P30 — دکمهٔ «📈 وضعیتِ همزمانی و عملکرد» در پنلِ ادمین

چه چیزی را قفل می‌کند:
۱. دانه‌ها: دو مشتری در یکِ دانه ⇒ همزمانیِ آن دانه = ۲ (نه تعدادِ پیام)
۲. پنجره: پیامِ ۳۰ ساعته در گزارشِ ۲۴ ساعته نیست، ولی در گزارشِ ۷ روزه هست
۳. تفکیکِ قابلیت: شمارشِ فراخوانی‌ها از دفترِ کیف‌پول، و حذفِ ردیف‌هایِ صفر از متن
۴. دکمهٔ بازه: perf_range:7d گزارش را عوض می‌کند؛ کلیدِ ناشناخته فقط توست می‌دهد و پیامِ تازه نمی‌سازد
۵. قاعدهٔ §۲-۶: هر دکمهٔ تازهٔ پنل در `_KNOWN_MENU_BUTTONS` ثبت شود

زمانِ تست لنگرِ ثابت دارد (ثانیهٔ ۱۰۰ و ۱۲۰ِ دانهٔ ۱۰ دقیقه‌ایِ جاری) تا نه مرزِ دانه و نه
پنجرهٔ «۵ دقیقهٔ آخر» به ساعتِ واقعیِ اجرا وابسته نباشد.

اجرا: python3 tests_manual/run_one.py test_p30_concurrency_report.py
"""
from __future__ import annotations

import asyncio
import datetime as dt
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from harness import FakeSession, build_test_dispatchers, make_callback_update, make_message_update, reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from aiogram import Bot  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.bots.main_bot import keyboards, router as main_router, texts  # noqa: E402
from app.database.models import ConversationMessage, ShopBot, WalletTransaction, WalletTransactionReason  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import customer_service, perf_report_service  # noqa: E402

ADMIN_TG_ID = 12345
OWNER_TG_ID = 999971
SHOP_BOT_TG_ID = 999972
MAIN_TOKEN = "000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS"
PERF_BUTTON = "📈 وضعیتِ همزمانی و عملکرد"

_BUCKET_SECONDS = 600
_RECENT_A = 100
_RECENT_B = 120
_STALE_OFFSET = 30 * 3600
_REPORT_NOW_OFFSET = 400

BUCKET_START = int(dt.datetime.now(dt.timezone.utc).timestamp()) // _BUCKET_SECONDS * _BUCKET_SECONDS


def _moment(offset: int) -> dt.datetime:
    return dt.datetime.fromtimestamp(BUCKET_START + offset, dt.timezone.utc)


async def _seed_traffic(shop_bot_id: int) -> None:
    async with session_scope() as session:
        owner_id = int((await session.execute(select(ShopBot.shop_owner_id).where(ShopBot.id == shop_bot_id))).scalar_one())
        first = await customer_service.get_or_create_customer(session, shop_bot_id, 7001, "مشتریِ اول", "c1", platform="telegram")
        second = await customer_service.get_or_create_customer(session, shop_bot_id, 7002, "مشتریِ دوم", "c2", platform="telegram")
        third = await customer_service.get_or_create_customer(session, shop_bot_id, 7003, "مشتریِ قدیمی", "c3", platform="telegram")
        session.add_all(
            [
                ConversationMessage(customer_id=first.id, role="user", content="سلام", created_at=_moment(_RECENT_A)),
                ConversationMessage(customer_id=first.id, role="assistant", content="درود", created_at=_moment(_RECENT_A)),
                ConversationMessage(customer_id=second.id, role="user", content="قیمت؟", created_at=_moment(_RECENT_B)),
                ConversationMessage(customer_id=third.id, role="user", content="قدیمی", created_at=_moment(_RECENT_A - _STALE_OFFSET)),
                WalletTransaction(
                    shop_owner_id=owner_id, amount_toman=-50, reason=WalletTransactionReason.CHAT_MESSAGE,
                    status="settled", idempotency_key="p30-perf-chat-1", created_at=_moment(_RECENT_A),
                ),
                WalletTransaction(
                    shop_owner_id=owner_id, amount_toman=-50, reason=WalletTransactionReason.CRM_SUMMARY,
                    status="settled", idempotency_key="p30-perf-crm-1", created_at=_moment(_RECENT_B),
                ),
            ]
        )
        await session.commit()



async def _report(range_key: str) -> dict:
    """همان چیزی که هندلرِ پنل می‌کند: یکِ سشن + بازه + اکنونِ مصنوعی."""
    async with session_scope() as session:
        return await perf_report_service.build(session, range_key, now=_moment(_REPORT_NOW_OFFSET))


async def test_bucket_counts_distinct_customers() -> None:
    data = await _report("24h")
    assert data["peak_customers"] == 2, f"دو مشتری در یکِ دانه ⇒ همزمانیِ ۲؛ شد {data['peak_customers']}"
    assert data["messages"] == 2, f"در ۲۴ ساعت دو پیامِ مشتری داریم (سوم ۳۰ ساعت قبل است)، و پاسخِ ربات شمرده نمی‌شود؛ شد {data['messages']}"
    assert data["customers"] == 2
    assert data["active_now"] == 2, f"در ۵ دقیقهٔ آخر دو مشتری؛ شد {data['active_now']}"
    assert len(data["series"]) == 144, "۲۴ ساعت با دانهٔ ۱۰ دقیقه ⇒ ۱۴۴ دانه"
    assert sum(value for _m, value in data["series"]) == data["messages"], "جمعِ دانه‌ها باید با تعدادِ پیامِ مشتری بخورد"
    print("✅ test_bucket_counts_distinct_customers PASSED")


async def test_window_excludes_stale_message() -> None:
    short = await _report("24h")
    week = await _report("7d")
    assert short["messages"] == 2, "پیامِ ۳۰ ساعته در پنجرهٔ ۲۴ ساعت نیست"
    assert week["messages"] == 3, "همان پیامِ قدیمی در پنجرهٔ ۷ روز دیده می‌شود"
    assert len(week["series"]) == 168, "۷ روز با دانهٔ یک ساعت ⇒ ۱۶۸ دانه"
    print("✅ test_window_excludes_stale_message PASSED")


async def test_feature_breakdown_and_text() -> None:
    data = await _report("24h")
    features = dict(data["features"])
    assert features["چتِ متنی"] == 1 and features["خلاصهٔ مشتری"] == 1, features
    body = texts.perf_report_text(data)
    assert "چتِ متنی: ۱" in body and "خلاصهٔ مشتری: ۱" in body, body
    assert "تحلیلِ عکس" not in body, "قابلیتِ صفرفرخوانده نباید در گزارش بیاید"
    assert "📈 وضعیتِ همزمانی و عملکرد — ۲۴ ساعت (هر ۱۰ دقیقه)" in body
    print("✅ test_feature_breakdown_and_text PASSED")


def test_sparkline_shape() -> None:
    moments = [_moment(index * 60) for index in range(4)]
    assert perf_report_service.sparkline([(m, 0) for m in moments]) == "····"
    strip = perf_report_service.sparkline(list(zip(moments, [1, 2, 4, 0], strict=True)))
    assert strip[-1] == "·" and strip[2] != "·", strip
    print("✅ test_sparkline_shape PASSED")


def test_button_registered_in_menu_escape_set() -> None:
    assert PERF_BUTTON in main_router._KNOWN_MENU_BUTTONS, "قاعدهٔ §۲-۶: ثبتِ دکمهٔ تازه در مجموعهٔ فرارِ منو"
    for is_super in (True, False):
        labels = {btn.text for row in keyboards.admin_panel_keyboard(is_super).keyboard for btn in row}
        assert PERF_BUTTON in labels, f"دکمه باید در پنلِ سوپرادمین و عملیاتی باشد (is_super={is_super})"
    print("✅ test_button_registered_in_menu_escape_set PASSED")


async def test_panel_flow_and_range_buttons(main_dp) -> None:
    main_bot = Bot(token=MAIN_TOKEN, session=FakeSession())
    await main_dp.feed_update(main_bot, make_message_update(1, text=PERF_BUTTON, user_id=ADMIN_TG_ID))
    body = main_bot.session.sent_messages[-1]["text"]
    assert body.startswith("📈 وضعیتِ همزمانی و عملکرد"), body[:80]
    assert "۲۴ ساعت" in body and "همزمانیِ مشتریان در هر دانه" in body, body[:200]

    await main_dp.feed_update(main_bot, make_callback_update(2, data="perf_range:7d", user_id=ADMIN_TG_ID))
    week = main_bot.session.sent_messages[-1]["text"]
    assert "۷ روز (هر ساعت)" in week, week[:80]

    before = len(main_bot.session.sent_messages)
    await main_dp.feed_update(main_bot, make_callback_update(3, data="perf_range:99h", user_id=ADMIN_TG_ID))
    assert len(main_bot.session.sent_messages) == before, "کلیدِ ناشناخته نباید گزارش بسازد"
    toast = main_bot.session.answered_callbacks[-1]
    assert "شناخته‌شده نیست" in toast["text"], toast
    print("✅ test_panel_flow_and_range_buttons PASSED")


async def main() -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    await _seed_traffic(shop_bot_id)

    await test_bucket_counts_distinct_customers()
    await test_window_excludes_stale_message()
    await test_feature_breakdown_and_text()
    test_sparkline_shape()
    test_button_registered_in_menu_escape_set()

    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    await test_panel_flow_and_range_buttons(main_dp)


if __name__ == "__main__":
    asyncio.run(main())
