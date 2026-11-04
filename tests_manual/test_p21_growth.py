"""
تست: P21-D — رشد (خلاصهٔ پولی، پخشِ زمان‌بندی‌شده، پیگیریِ مشاوره، اخطارِ موجودی)

پوشش:
۱. `parse_when`/`validate_when`: «۲۱:۳۰» به وقتِ تهران، ساعتِ گذشته ⇒ فردا، «+۲h/+۴۵m/+۳d»،
   ورودیِ بی‌ربط ⇒ None، و مرزهایِ «خیلی زود»/«خیلی دور».
۲. `scheduled_broadcast_service`: زمانِ رسید ⇒ هر گیرنده یک ردیف در صندوقِ اعلان، با dedupe ⇒
   اجرایِ دوباره پیامِ تکراری نمی‌سازد؛ بخشِ CRM فقط گیرنده‌هایِ خودش را می‌گیرد؛ لغو فقط
   داخلِ رباتِ خودش (شمارهٔ ردیفِ دیگری کاریکرنی‌پذیر نیست).
۳. `stock_alert_service`: موجودیِ واقعی = موجودی کمِ رزرو؛ آستانهٔ NULL ⇒ هیچ؛ سقفِ ۲۴ ساعت.
۴. خطوطِ پولیِ اضافه‌شده به گزارشِ شبانه (F1) و عنوانِ مشاوره‌ایِ فهرستِ سفارش‌ها (F5).

اجرا: python3 tests_manual/test_p21_growth.py
"""
from __future__ import annotations

import asyncio
import datetime
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from sqlalchemy import select  # noqa: E402

from harness import reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot import texts as main_texts  # noqa: E402
from app.bots.shop_bot import texts as shop_texts  # noqa: E402
from app.database.models import (  # noqa: E402
    Customer,
    Notification,
    Product,
    ScheduledBroadcast,
    ShopBot,
)  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import notification_service, scheduled_broadcast_service, stock_alert_service  # noqa: E402
from app.utils.jalali import TEHRAN_TZ

OWNER_TG_ID = 999_771
SHOP_BOT_TG_ID = 999_772
NOW = datetime.datetime(2026, 11, 1, 8, 0, tzinfo=datetime.timezone.utc)  # ۱۱:۳۰ تهران


# ============================================================================= ۱ — خواندنِ زمان
def test_parse_when() -> None:
    assert scheduled_broadcast_service.parse_when("۲۱:۳۰", NOW) == scheduled_broadcast_service.parse_when("21:30", NOW)
    tonight = scheduled_broadcast_service.parse_when("21:30", NOW)
    assert tonight.tzinfo is not None and tonight.utcoffset() is not None
    assert tonight.astimezone(TEHRAN_TZ).strftime("%H:%M") == "21:30", tonight
    # ساعتِ گذشته ⇒ همان ساعت در روزِ بعد (نه ردِ ورودی)
    tomorrow_nine = scheduled_broadcast_service.parse_when("09:00", NOW)
    assert tomorrow_nine > tonight and tomorrow_nine.astimezone(TEHRAN_TZ).strftime("%H:%M") == "09:00", tomorrow_nine
    assert (tomorrow_nine - tonight) == datetime.timedelta(hours=11, minutes=30), "۲۱:۳۰ امروز تا ۰۹:۰۰ فردا"
    assert scheduled_broadcast_service.parse_when("+2h", NOW) == NOW + datetime.timedelta(hours=2)
    assert scheduled_broadcast_service.parse_when("+45m", NOW) == NOW + datetime.timedelta(minutes=45)
    assert scheduled_broadcast_service.parse_when("+3d", NOW) == NOW + datetime.timedelta(days=3)
    assert scheduled_broadcast_service.parse_when("هر‌وقتی", NOW) is None
    assert scheduled_broadcast_service.parse_when("25:00", NOW) is None, "ساعتِ نامعتبر"
    assert scheduled_broadcast_service.parse_when("", NOW) is None
    assert scheduled_broadcast_service.parse_when(None, NOW) is None
    print("✅ test_parse_when PASSED")


def test_validate_when_bounds() -> None:
    ok, why = scheduled_broadcast_service.validate_when(NOW + datetime.timedelta(minutes=30), NOW)
    assert ok and why == ""
    assert scheduled_broadcast_service.validate_when(NOW + datetime.timedelta(minutes=2), NOW) == (False, "too_soon")
    assert scheduled_broadcast_service.validate_when(NOW - datetime.timedelta(minutes=5), NOW)[1] == "too_soon"
    assert scheduled_broadcast_service.validate_when(NOW + datetime.timedelta(days=90), NOW)[1] == "too_far"
    assert scheduled_broadcast_service.validate_when(None, NOW)[1] == "format"
    print("✅ test_validate_when_bounds PASSED")


# ============================================================================= ۲ — چرخهٔ پخشِ زمان‌بندی‌شده
async def _shop_ids() -> tuple[int, int]:
    async with session_scope() as session:
        shop_bot = (await session.execute(select(ShopBot).where(ShopBot.bot_telegram_id == SHOP_BOT_TG_ID))).scalar_one()
        return shop_bot.id, shop_bot.shop_owner_id


async def _add_customers(count: int) -> list[int]:
    shop_bot_id, _owner_id = await _shop_ids()
    ids = []
    async with session_scope() as session:
        for index in range(count):
            row = Customer(shop_bot_id=shop_bot_id, telegram_id=999_780 + index, platform="telegram" if index % 2 == 0 else "bale")
            session.add(row)
            await session.flush()
            ids.append(row.id)
        await session.commit()
    return ids


async def test_scheduled_broadcast_queues_into_the_outbox() -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    shop_bot_id, owner_id = await _shop_ids()
    await _add_customers(4)  # دو تلگرامی، دو بله‌ای

    async with session_scope() as session:
        shop_bot = await session.get(ShopBot, shop_bot_id)
        when = NOW + datetime.timedelta(hours=3)
        result = await scheduled_broadcast_service.schedule(
            session, shop_bot=shop_bot, owner_id=owner_id, text="تخفیفِ ۲۰٪ امشب", scheduled_at=when
        )
        assert isinstance(result, ScheduledBroadcast), result
        assert await scheduled_broadcast_service.active_count(session, shop_bot_id) == 1
        await session.commit()

    # زودتر از موعد ⇒ هیچ
    async with session_scope() as session:
        summary = await scheduled_broadcast_service.queue_due(session, now=NOW + datetime.timedelta(hours=1))
    assert summary == {"scheduled": 0, "queued": 0, "empty": 0}, summary

    async with session_scope() as session:
        summary = await scheduled_broadcast_service.queue_due(session, now=NOW + datetime.timedelta(hours=4))
        assert summary["scheduled"] == 1, summary
        assert summary["queued"] == 4, summary
        await session.commit()

    async with session_scope() as session:
        rows = list((await session.execute(select(Notification))).scalars().all())
        broadcast = (await session.execute(select(ScheduledBroadcast))).scalar_one()
    assert len(rows) == 4, rows
    assert {row.platform for row in rows} == {"telegram", "bale"}, "پلتفرمِ هر گیرنده باید همراهش باشد"
    assert {row.chat_id for row in rows} == {999780, 999781, 999782, 999783}
    assert all(row.status == notification_service.PENDING for row in rows)
    assert broadcast.status == scheduled_broadcast_service.QUEUED and broadcast.queued_count == 4

    # دورِ دومِ همان جاب ⇒ dedupe صفِ دوتایی نمی‌سازد (ردیف حالا queued است، حتی اگر queue_due تکرار شود)
    async with session_scope() as session:
        again = await scheduled_broadcast_service.queue_due(session, now=NOW + datetime.timedelta(hours=5))
    assert again["scheduled"] == 0, again

    # سقفِ پنجِ هم‌زمان + لغوِ فقط داخلِ همان ربات
    async with session_scope() as session:
        shop_bot = await session.get(ShopBot, shop_bot_id)
        for index in range(6):
            await scheduled_broadcast_service.schedule(
                session, shop_bot=shop_bot, owner_id=owner_id, text=f"پیامِ {index}", scheduled_at=NOW + datetime.timedelta(days=1 + index)
            )
        pending = await scheduled_broadcast_service.upcoming(session, shop_bot_id, limit=20)
        assert len(pending) <= scheduled_broadcast_service.MAX_ACTIVE_PER_SHOP, len(pending)
        foreign = await scheduled_broadcast_service.cancel(session, shop_bot_id=999_999, broadcast_id=pending[0].id)
        assert foreign is False, "شمارهٔ ردیفِ رباتِ دیگر نباید قابلِ لغو باشد"
        mine = await scheduled_broadcast_service.cancel(session, shop_bot_id=shop_bot_id, broadcast_id=pending[0].id)
        assert mine is True
        await session.commit()
    print("✅ test_scheduled_broadcast_queues_into_the_outbox PASSED")


async def test_scheduled_broadcast_honours_crm_segment() -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    shop_bot_id, owner_id = await _shop_ids()
    ids = await _add_customers(5)

    async with session_scope() as session:
        shop_bot = await session.get(ShopBot, shop_bot_id)
        row = await scheduled_broadcast_service.schedule(
            session,
            shop_bot=shop_bot,
            owner_id=owner_id,
            text="فقط بخشِ انتخابی",
            scheduled_at=NOW + datetime.timedelta(hours=1),
            recipient_ids=ids[:2],
        )
        assert isinstance(row, ScheduledBroadcast), row
        await session.commit()

    async with session_scope() as session:
        summary = await scheduled_broadcast_service.queue_due(session, now=NOW + datetime.timedelta(hours=2))
    assert summary["queued"] == 2, summary
    print("✅ test_scheduled_broadcast_honours_crm_segment PASSED")


# ============================================================================= ۳ — اخطارِ موجودی
async def test_stock_alert_threshold_and_throttle() -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    _bot_id, owner_id = await _shop_ids()

    async with session_scope() as session:
        shop_bot = await session.get(ShopBot, shop_bot_id)
        assert shop_bot.low_stock_alert_threshold is None, "پیش‌فرض ⇒ خاموش (رفتارِ امروز بدونِ تغییر)"
        session.add_all(
            [
                Product(shop_bot_id=shop_bot_id, name="کالایِ رو-به-اتمام", price_toman=10_000, stock_quantity=2),
                # موجودی ۱۰ دارد ولی ۹تایش رزروِ سفارش‌هایِ باز است ⇒ واقعی = ۱
                Product(shop_bot_id=shop_bot_id, name="رزروشده", price_toman=10_000, stock_quantity=10, reserved_quantity=9),
                Product(shop_bot_id=shop_bot_id, name="بی‌محدود", price_toman=10_000, stock_quantity=None),
                Product(shop_bot_id=shop_bot_id, name="فروش نرفته", price_toman=10_000, stock_quantity=0, is_active=False),
            ]
        )
        await session.commit()

    async with session_scope() as session:
        sent = await stock_alert_service.run(session, _SendBot(), now=NOW)
        assert sent == {"sent": 0, "skipped": 0}, "آستانه تنظیم نشده ⇒ هیچ پیامی"
        shop_bot = await session.get(ShopBot, shop_bot_id)
        shop_bot.low_stock_alert_threshold = 3
        await session.commit()

    bot = _SendBot()
    async with session_scope() as session:
        result = await stock_alert_service.run(session, bot, now=NOW)
        assert result["sent"] == 1, result
        assert "رو-به-اتمام" in bot.sent[0][1] and "رزروشده" in bot.sent[0][1]
        assert "بی‌محدود" not in bot.sent[0][1], "stock_quantity=None یعنی نامحدود، نه کم"
        assert "فروش نرفته" not in bot.sent[0][1], "محصولِ غیرفعال اخطار نمی‌دهد"
        await session.commit()

    # سقفِ ۲۴ ساعت ⇒ دورِ بعدی در همان روز سکوت می‌کند
    async with session_scope() as session:
        again = await stock_alert_service.run(session, _SendBot(), now=NOW + datetime.timedelta(hours=6))
        assert again["skipped"] == 1 and again["sent"] == 0, again
        shop_bot = await session.get(ShopBot, shop_bot_id)
        shop_bot.low_stock_alert_threshold = None
        await session.commit()
    async with session_scope() as session:
        off = await stock_alert_service.run(session, _SendBot(), now=NOW + datetime.timedelta(days=2))
        assert off == {"sent": 0, "skipped": 0}, off
    print("✅ test_stock_alert_threshold_and_throttle PASSED")


# ============================================================================= ۴ — متن‌ها
def test_digest_wallet_line_and_consult_titles() -> None:
    line = main_texts.digest_wallet_line(500_000, 420_000, 90_000, 12, 30_000)
    assert "قابل‌استفاده" in line and "منقضی" in line and "طلبِ کمیسیون" in line, line
    minimal = main_texts.digest_wallet_line(500_000, 500_000, 0, None, 0)
    assert "قابل‌استفاده" not in minimal and "طلبِ کمیسیون" not in minimal, minimal

    rows = [type("P", (), {"name": "کیف", "stock_quantity": 1, "reserved_quantity": 0})()]
    alert = main_texts.stock_alert_text(rows, 3, 8)
    assert "کیف: ۱ عدد" in alert, alert

    consultation = shop_texts.my_orders_list_text(
        [[type("O", (), {"status": "pending", "summary": "مشاورهٔ چرم", "product_id": None})()]],
        {},
        [200_000],
        0,
        1,
        consultation=True,
    )
    assert "مشاوره" in consultation and "سفارش‌هایِ من" not in consultation, consultation
    print("✅ test_digest_wallet_line_and_consult_titles PASSED")


class _SendBot:
    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str, **_kwargs):
        self.sent.append((chat_id, text))
        return True


async def main() -> None:
    test_parse_when()
    test_validate_when_bounds()
    await test_scheduled_broadcast_queues_into_the_outbox()
    await test_scheduled_broadcast_honours_crm_segment()
    await test_stock_alert_threshold_and_throttle()
    test_digest_wallet_line_and_consult_titles()


if __name__ == "__main__":
    asyncio.run(main())
