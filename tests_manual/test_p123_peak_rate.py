"""پ۱۲۳ · پیکِ واقعیِ «درخواست در ثانیه» (خواستِ مستقیمِ مالکِ محصول: میانگین نه).

پیش ازِ این گزارشِ «📈 وضعیتِ همزمانی و عملکرد» فقط این را می‌داد: *چند مشتریِ متمایز در هر دانه*
(دانه = ۵ تا ۱۴۴۰ دقیقه) و یکِ **میانگینِ** «X پیام در دقیقه» که از تقسیمِ کلِ پیام‌ها بر طولِ بازه
می‌آمد. آن عدد نمی‌توانست بگوید بدترینِ ثانیهٔ سرور چند درخواست دیده، آنِ کِی بوده و چند ثانیه
کشیده است. اضافه‌شده:

۱. `_peak_per_second` دو پاس است: سطلِ یک‌دقیقه‌ای رویِ کلِ بازه (یک aggregate) ⇒ شلوغ‌ترینِ سه دقیقه؛
   بعدِ هیستوگرامِ ثانیه‌ای فقط حولِ همان دقایق (هر طرف ۶۰ ثانیه، تا رَکوردِ پیوستهٔ پیک به دو تکه
   نشکند). پیکِ هر ثانیه‌ای در جایِ دیگرِ بازه نمی‌تواند از پیکِ این پنجره‌ها بیشتر باشد، پس عددِ
   «بیشینه» صادق است.
۲. دو منبع: `messages` (پیامِ مشتری) و `ai_requests` (ردیف‌هایِ واقعیِ مصرفِ AI در دفترِ کیف‌پول).
۳. متنِ گزارش: بلوکِ «⏱ پیکِ واقعی در ثانیه» با سه عدد (چند تا / چند ثانیه پیوسته / کِی، با ثانیه)
   و خطِ «⚙️ بارِ لازم» حالا **اول** عددِ اوج را می‌گوید و میانگین را صریح «میانگین است، نه اوج»
   برچسب می‌زند.

این فایل چهار چیز را می‌بندد: پیکِ درست، طولِ رَکوردِ درست وقتی پیک از مرزِ دقیقه رد می‌شود،
بی‌اثربودنِ داده‌هایِ بیرونِ بازه، و خالی‌بودنِ بازه ⇒ «—» نه صفرِ گمراه‌کننده.

اجرا: python3 tests_manual/run_one.py test_p123_peak_rate.py
"""
from __future__ import annotations

import asyncio
import datetime as dt
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from harness import reset_database  # noqa: E402
from phase4_helpers import add_customer  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot import texts  # noqa: E402
from app.database.models import ConversationMessage, WalletTransaction, WalletTransactionReason  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import perf_report_service  # noqa: E402

OWNER_TG = 12_300_001
SHOP_TG = 12_300_002
CUSTOMER_TG = 12_300_003
# پیک عمداً از مرزِ دقیقه رد می‌شود: ۵۷، ۵۸، ۵۹ ثانیهٔ یکِ دقیقه و ۰۰ ثانیهٔ دقیقهٔ بعد
BASE = dt.datetime(2026, 11, 18, 10, 30, 57, tzinfo=dt.timezone.utc)
SINCE = BASE - dt.timedelta(minutes=30)
UNTIL = BASE + dt.timedelta(minutes=10)


async def _seed_traffic(customer_id: int, owner_id: int) -> None:
    async with session_scope() as session:
        # پنج پیام در هر یک از سه ثانیهٔ متوالی ⇒ پیک = ۵ و رَکوردِ پیوسته = ۳ ثانیه
        for second in (0, 1, 2):
            for _ in range(5):
                session.add(
                    ConversationMessage(
                        customer_id=customer_id, role="user", content="سلام", created_at=BASE + dt.timedelta(seconds=second)
                    )
                )
        # یکِ ثانیهٔ کمی شلوغ‌تر ازِ آستانه (۴ = ۸۰٪ پیک) تا «ثانیه‌هایِ داغ» هم سنجیده شود
        for _ in range(4):
            session.add(
                ConversationMessage(customer_id=customer_id, role="user", content="سلام", created_at=BASE + dt.timedelta(seconds=3))
            )
        # سرد و بی‌ربط: یکِ دقیقهٔ بعد (باید رویِ پیک اثری نداشته باشد)
        session.add(
            ConversationMessage(
                customer_id=customer_id, role="user", content="سلام", created_at=BASE + dt.timedelta(minutes=5)
            )
        )
        # بیرونِ بازه: یکِ ساعتِ پیش ⇒ نباید دیده شود (اگر دیده شود، پیکِ دقیقه‌اش رقیب می‌شد)
        for _ in range(9):
            session.add(
                ConversationMessage(
                    customer_id=customer_id, role="user", content="سلام", created_at=BASE - dt.timedelta(hours=1)
                )
            )
        # پاسخ‌هایِ ربات (نقشِ assistant) هم نباید در شمارِ «پیامِ مشتری» بیایند
        session.add(
            ConversationMessage(customer_id=customer_id, role="assistant", content="بفرمایید", created_at=BASE)
        )
        # درخواست‌هایِ واقعیِ AI: سه تا در هر یک از دو ثانیه
        for second in (0, 1):
            for _ in range(3):
                session.add(
                    WalletTransaction(
                        shop_owner_id=owner_id,
                        amount_toman=-100,
                        reason=WalletTransactionReason.CHAT_MESSAGE,
                        created_at=BASE + dt.timedelta(seconds=second),
                    )
                )
        await session.commit()


async def _owner_id() -> int:
    from sqlalchemy import select

    from app.database.models import ShopBot, ShopOwner

    async with session_scope() as session:
        bot = (await session.execute(select(ShopBot).where(ShopBot.bot_telegram_id == SHOP_TG))).scalar_one()
        return int((await session.execute(select(ShopOwner).where(ShopOwner.id == bot.shop_owner_id))).scalar_one().id)


async def _build():
    async with session_scope() as session:
        return await perf_report_service.build(session, "24h", now=UNTIL, since=SINCE, until=UNTIL)


async def test_peak_messages_run_and_time() -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG, SHOP_TG)
    customer_id = await add_customer(shop_bot_id, CUSTOMER_TG)
    await _seed_traffic(customer_id, await _owner_id())

    data = await _build()
    peak = data["peak_messages_per_second"]
    assert peak is not None, "پیکِ پیامِ مشتری محاسبه نشد"
    assert peak["rps"] == 5, peak
    assert peak["run_seconds"] == 3, f"رَکوردِ پیوسته باید ۳ ثانیه باشد: {peak}"
    assert peak["at"] == BASE, f"زمانِ پیک باید خودِ ثانیهٔ نخستِ رَکورد باشد: {peak['at']}"
    assert peak["threshold"] == 4 and peak["hot_seconds"] == 4, peak
    # شمارِ کلِ بازه: ۱۵ پیامِ پیک‌ساز + ۴ پیامِ «داغ» + ۱ پیامِ سرد = ۲۰
    # (۹ پیامِ یکِ ساعتِ پیش و ۱ پاسخِ assistant بیرونِ شمارند)
    assert data["messages"] == 20, data["messages"]
    assert data["customers"] == 1, data["customers"]
    print(f"✅ test_peak_messages_run_and_time PASSED (پیک {peak['rps']}/ثانیه، {peak['run_seconds']} ثانیه پیوسته)")


async def test_peak_ai_requests() -> None:
    data = await _build()
    peak = data["peak_ai_requests_per_second"]
    assert peak is not None and peak["rps"] == 3, peak
    assert peak["run_seconds"] == 2, peak
    assert peak["at"] == BASE, peak
    assert peak["hot_seconds"] == 2, peak
    print("✅ test_peak_ai_requests PASSED")


async def test_report_text_leads_with_peak_not_average() -> None:
    data = await _build()
    body = texts.perf_report_text(data)
    assert "⏱ پیکِ واقعی در ثانیه" in body, body[:400]
    assert "۵ در یکِ ثانیه" in body and "۳ ثانیه پیوسته" in body, body
    assert "۳ در یکِ ثانیه" in body, "پیکِ درخواستِ AI در متن نیست"
    assert "ساعت ۱۴:۰۰:۵۷" in body, f"زمانِ پیک با ثانیه به وقتِ تهران باید بیاید: {body}"
    # میانگین هم می‌ماند، ولی صریح برچسب‌خورده و *پس ازِ* پیک
    assert body.index("پیکِ واقعی") < body.index("میانگین است، نه اوج"), "چیدمان: اولِ اوج، بعدِ میانگین"
    assert "در اوج ۱۵ درخواستِ هم‌زمان" in body, body  # ۳ درخواستِ AI در ثانیه × ۶۰ × ۵ ثانیه ÷ ۶۰
    print("✅ test_report_text_leads_with_peak_not_average PASSED")


async def test_empty_range_has_no_peak() -> None:
    empty_start = dt.datetime(2020, 1, 1, tzinfo=dt.timezone.utc)
    async with session_scope() as session:
        data = await perf_report_service.build(
            session, "24h", now=UNTIL, since=empty_start, until=empty_start + dt.timedelta(minutes=30)
        )
    assert data["peak_messages_per_second"] is None and data["peak_ai_requests_per_second"] is None
    body = texts.perf_report_text(data)
    assert "هیچ رویدادی ثبت نشده" in body, body[:600]
    print("✅ test_empty_range_has_no_peak PASSED")


async def main() -> None:
    await test_peak_messages_run_and_time()
    await test_peak_ai_requests()
    await test_report_text_leads_with_peak_not_average()
    await test_empty_range_has_no_peak()


if __name__ == "__main__":
    asyncio.run(main())
