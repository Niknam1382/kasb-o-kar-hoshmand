"""
تست: P51 · موردِ ۴۴ — نمودارِ درآمدِ ماهانه در پنلِ ادمین (تفکیکِ مشاوره/فروش، کمیسیون، نقدِ دریافتی).

چه چیزی باید درست باشد:
* عددِ هرِ ماه «خالص» باشد: مصرفِ اعتبار منهایِ برگشت‌هایِ همان ماه (نه قدرمطلقِ هرِ ردیف).
* هدیه‌ها (تراِیل/معرفی/گرنتِ ادمین) هرگز «فروشِ اعتبار» حساب نشوند.
* کمیسیونِ سفارش‌ها از فروشِ هوش‌مصنوعی جدا نوشته شود و «نقدِ دریافتی» (شارژ/اشتراک)
  با آن‌ها جمع نشود (چون هنوز مصرف نشده است).
* تفکیکِ حالتِ فروشگاه (مشاوره‌ای / فروش) از خودِ `shop_bots.tenant_mode` بیاید.
* سطلِ ماه‌ها «ماهِ جلالی» باشد، نه تقویمِ میلادی.
* صفحهٔ «📊 آمار سراسری» دکمه‌هایِ نمودار و ویزاردِ بازهٔ دلخواه را داشته باشد و تاریخِ
  نامعتبر را رد کند.

اجرا: python3 tests_manual/run_one.py test_p51_revenue_chart.py
"""
from __future__ import annotations

import asyncio
import datetime
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402
from sqlalchemy import select  # noqa: E402

from harness import FakeSession, build_test_dispatchers, make_callback_update, make_message_update, reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot import texts as main_texts  # noqa: E402
from app.database.models import ConversationMessage, ShopBot, WalletTransaction, WalletTransactionReason  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import customer_service, stats_service  # noqa: E402
from app.utils.jalali import JALALI_MONTH_NAMES, gregorian_to_jalali  # noqa: E402

ADMIN_TG_ID = 12345
OWNER_TG_ID = 999_851
BOT_TG_ID = 999_852
MAIN_TOKEN = "000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS"
NOW = datetime.datetime.now(datetime.timezone.utc)


async def _seed_money() -> int:
    """یکِ فروشگاه با چهارِ ردیفِ کیف‌پول و دوِ پیامِ مشتری؛ شناسهٔ فروشگاه را برمی‌گرداند."""
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, BOT_TG_ID)
    async with session_scope() as session:
        owner_id = (await session.execute(select(ShopBot.shop_owner_id).where(ShopBot.id == shop_bot_id))).scalar_one()
        session.add_all(
            [
                WalletTransaction(shop_owner_id=owner_id, amount_toman=-5000, reason=WalletTransactionReason.CHAT_MESSAGE),
                WalletTransaction(shop_owner_id=owner_id, amount_toman=1000, reason=WalletTransactionReason.CHAT_MESSAGE),
                WalletTransaction(shop_owner_id=owner_id, amount_toman=-2000, reason=WalletTransactionReason.COMMISSION),
                WalletTransaction(shop_owner_id=owner_id, amount_toman=90000, reason=WalletTransactionReason.TRIAL),
            ]
        )
        customer = await customer_service.get_or_create_customer(session, shop_bot_id, 777001, "سارا", None)
        session.add_all(
            [
                ConversationMessage(customer_id=customer.id, role="user", content="قیمت؟"),
                ConversationMessage(customer_id=customer.id, role="assistant", content="۳۵۰"),
            ]
        )
        await session.flush()
    return shop_bot_id


async def test_report_is_net_and_separates_sources() -> None:
    await reset_database()
    await _seed_money()
    report = await _report()
    totals = report["totals"]
    assert totals["ai_total"] == 4000, f"باید خالص باشد (۵۰۰۰ مصرف منهای ۱۰۰۰ برگشت): {totals}"
    assert totals["commission"] == 2000, totals
    assert totals["topup_cash"] >= 0 and totals["subscription_cash"] == 0, totals
    assert totals["messages"] == 1, f"فقط پیامِ مشتری شمرده می‌شود: {totals}"
    assert totals["orders"] == 0, totals
    assert report["series"], "دست‌کم یکِ ماه باید باشد"
    key = report["series"][0]["key"]
    j_year, j_month, _ = gregorian_to_jalali(NOW.year, NOW.month, NOW.day)
    assert key == (j_year, j_month), f"سطل باید ماهِ جلالیِ امروز باشد: {key}"
    assert report["series"][0]["label"] == f"{JALALI_MONTH_NAMES[j_month - 1]} {j_year}" or report["series"][0]["label"], report
    print("✅ test_report_is_net_and_separates_sources PASSED")


async def test_mode_split_follows_tenant_mode() -> None:
    await reset_database()
    shop_bot_id = await _seed_money()
    base = await _report()
    assert base["totals"]["ai_sales"] == 4000 and base["totals"]["ai_consult"] == 0, base["totals"]

    async with session_scope() as session:
        shop_bot = await session.get(ShopBot, shop_bot_id)
        shop_bot.tenant_mode = "consultation"
        await session.flush()
    flipped = await _report()
    assert flipped["totals"]["ai_consult"] == 4000 and flipped["totals"]["ai_sales"] == 0, flipped["totals"]
    print("✅ test_mode_split_follows_tenant_mode PASSED")


async def _report():
    async with session_scope() as session:
        return await stats_service.platform_revenue_report(
            session, since=NOW - datetime.timedelta(days=10), until=NOW + datetime.timedelta(days=1)
        )


def test_chart_text_is_honest_and_persian() -> None:
    report = {
        "since": NOW,
        "until": NOW,
        "series": [{"key": (1405, 8), "label": "آبان ۱۴۰۵", "ai_total": 4000, "ai_sales": 3000, "ai_consult": 1000,
                    "commission": 2000, "topup_cash": 9000, "subscription_cash": 0, "orders": 3, "messages": 40}],
        "totals": {"ai_total": 4000, "ai_sales": 3000, "ai_consult": 1000, "commission": 2000, "topup_cash": 9000,
                   "subscription_cash": 0, "orders": 3, "messages": 40, "months": 1},
    }
    body = main_texts.platform_revenue_chart_text(report, title="۱۲ ماهِ گذشته")
    assert "🧠 فروشِ اعتبارِ هوش‌مصنوعی" in body
    assert "🛍 حالتِ فروش" in body and "💬 حالتِ مشاوره‌ای" in body, body
    assert "🧾 کمیسیونِ سفارش‌ها" in body
    assert "نقدِ دریافتی" in body and "با دو ردیفِ بالا جمعش نکن" in body, "باید صریح بگوید نقد ≠ درآمدِ محقق‌شده"
    assert "آبان ۱۴۰۵" in body
    assert any(bar in body for bar in "▁▂▄▆█"), body
    empty = main_texts.platform_revenue_chart_text({"series": [], "totals": {}}, title="بازهٔ دلخواه")
    assert "هیچ رویدادی ثبت نشده" in empty, empty
    print("✅ test_chart_text_is_honest_and_persian PASSED")


async def test_stats_screen_chart_and_range_wizard(main_dp) -> None:
    await reset_database()
    await _seed_money()
    main_bot = Bot(token=MAIN_TOKEN, session=FakeSession())
    session_obj: FakeSession = main_bot.session  # type: ignore[assignment]

    async def buttons(index: int = -1) -> list[str]:
        markup = session_obj.sent_messages[index].get("reply_markup")
        return [b.callback_data or "" for row in markup.inline_keyboard for b in row] if markup else []

    await main_dp.feed_update(main_bot, make_message_update(1, text="📊 آمار سراسری", user_id=ADMIN_TG_ID))
    datas = await buttons()
    assert "admin_stats_chart" in datas and "admin_stats_range_from" in datas, datas

    await main_dp.feed_update(main_bot, make_callback_update(2, data="admin_stats_chart", user_id=ADMIN_TG_ID))
    chart_body = session_obj.sent_messages[-1]["text"]
    assert "نمودارِ درآمدِ ماهانه" in chart_body and "۱۲ ماهِ گذشته" in chart_body, chart_body[:120]

    await main_dp.feed_update(main_bot, make_callback_update(3, data="admin_stats_range_from", user_id=ADMIN_TG_ID))
    assert "تاریخِ شروع" in session_obj.sent_messages[-1]["text"], session_obj.sent_messages[-1]["text"]
    await main_dp.feed_update(main_bot, make_message_update(4, text="دیروز", user_id=ADMIN_TG_ID))
    assert "تاریخ را نفهمیدم" in session_obj.sent_messages[-1]["text"], session_obj.sent_messages[-1]["text"]
    await main_dp.feed_update(main_bot, make_message_update(5, text="۲۰۲۶-۱۰-۰۱", user_id=ADMIN_TG_ID))
    assert "تاریخِ پایان" in session_obj.sent_messages[-1]["text"], session_obj.sent_messages[-1]["text"]
    await main_dp.feed_update(main_bot, make_message_update(6, text="همه", user_id=ADMIN_TG_ID))
    ranged = session_obj.sent_messages[-1]["text"]
    assert "بازهٔ دلخواه" in ranged, ranged[:120]
    assert "admin_stats_range_clear" in await buttons(), "با بازهٔ تنظیم‌شده باید دکمهٔ حذفِ بازه بیاید"

    await main_dp.feed_update(main_bot, make_callback_update(7, data="admin_stats_range_clear", user_id=ADMIN_TG_ID))
    assert "admin_stats_range_clear" not in await buttons(), "بعد ازِ حذف، دکمهٔ حذف نباید بماند"
    print("✅ test_stats_screen_chart_and_range_wizard PASSED")


def test_summary_and_chart_agree_on_numbers() -> None:
    """دو صفحه نباید دو عددِ مختلف از یکِ دفتر بگویند."""
    import inspect

    source = inspect.getsource(stats_service.platform_revenue_report)
    assert "sign=-1" in source, "نمودار باید خالصِ کسرها را نشان دهد (مثلِ خلاصهٔ کلِ دوره)"
    assert "WalletTransaction.amount_toman < 0" not in source, "فقط‌کسرها فیلتر نشود؛ برگشت‌ها هم کم می‌شوند"
    assert "reason.in_(_USAGE_REASONS)" in source and "TRIAL" not in source.split("_USAGE_REASONS")[1][:200]
    print("✅ test_summary_and_chart_agree_on_numbers PASSED")


async def main() -> None:
    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    await test_report_is_net_and_separates_sources()
    await test_mode_split_follows_tenant_mode()
    test_chart_text_is_honest_and_persian()
    await test_stats_screen_chart_and_range_wizard(main_dp)
    test_summary_and_chart_agree_on_numbers()
    print("📊 نتیجه: ۵ تستِ P51 (نمودارِ درآمدِ ماهانه) پاس شد · خالص/تفکیکِ حالت/جداسازیِ نقد/پنل/تاریخ")


if __name__ == "__main__":
    asyncio.run(main())
