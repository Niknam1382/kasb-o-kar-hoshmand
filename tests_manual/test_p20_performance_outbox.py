"""
تست: P20-D/E — بهینه‌سازی و صندوقِ اعلان‌ها

پوشش:
۱. `notification_service.enqueue` ⇒ ردیفِ در‌انتظار؛ `send_due` با رباتِ جواب‌دهنده ⇒ sent.
۲. شکستِ ارسال ⇒ attempts+1، backoffِ درست، و بعد از سقف ⇒ failed (نه گم‌شدنِ بی‌صدا).
۳. dedupe: دو بار صف‌کردنِ همان رویداد ⇒ یک ردیف.
۴. `notify_customer` (تاییدِ سفارشِ فروشگاه‌دار): خطایِ گذرا ⇒ صف؛ بلاکِ مشتری ⇒ بدونِ صف (بی‌فایده).
۵. جابِ دوره‌ای، صف را واقعاً تخلیه می‌کند (سیم‌کشیِ scheduler، نه فقط تابعِ تنها).
۶. `wallet_service.credit_summary`: «قابل‌استفاده» = موجودی کمِ holdِ کمیسیون؛ «در آستانهٔ انقضا»
   فقط بسته‌هایِ زندهٔ ۳۰ روزِ آینده را می‌شمارد.
۷. رابطهٔ `ShopBot.products` دیگر selectin نیست (کوئریِ پنهانِ «همهٔ محصولات» در هر پیامِ مشتری).
۸. پنلِ ادمین: گزارشِ صفِ اعلان‌ها + دکمهٔ «تلاشِ دوباره» که شکست‌خورده‌ها را با backoffِ تازه
   به صف برمی‌گرداند (بدونِ این دکمه، `failed` یک‌باره برایِ همیشه ساکت می‌ماند).

اجرا: python3 tests_manual/test_p20_performance_outbox.py
"""
from __future__ import annotations

import asyncio
import datetime
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError  # noqa: E402
from sqlalchemy import select  # noqa: E402

from harness import build_test_dispatchers, make_shop_bot, reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.database.models import (
    Customer,
    Notification,
    OrderConsultation,
    OrderStatus,
    OrderType,
    ShopBot,
    ShopOwner,
    WalletTransactionReason,
)  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import (
    notification_service,
    order_transition_service,
    platform_service,
    scheduler,
    shop_bot_service,
    wallet_service,
)
from app.services.admin_settings_service import get_admin_settings  # noqa: E402

OWNER_TG_ID = 999_731
SHOP_BOT_TG_ID = 999_732
CUSTOMER_TG_ID = 999_733
ADMIN_TG_ID = 12345


class _SendBot:
    """رباتِ جعلی: حالتِ 'fail' هر بار TelegramAPIError می‌دهد."""

    def __init__(self, *, fail_with: Exception | None = None) -> None:
        self.sent: list[tuple[int, str]] = []
        self.fail_with = fail_with

    async def send_message(self, chat_id: int, text: str, **_kwargs):
        if self.fail_with is not None:
            raise self.fail_with
        self.sent.append((chat_id, text))
        return True


def _forbidden() -> TelegramForbiddenError:
    return TelegramForbiddenError(method=None, message="chat was destroyed")


def _api_error() -> TelegramAPIError:
    return TelegramAPIError(method=None, message="service unavailable")


# ============================================================================= ۱ تا ۳ — خودِ صف
async def test_outbox_lifecycle_and_dedupe() -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)

    async with session_scope() as session:
        assert await notification_service.enqueue(
            session, CUSTOMER_TG_ID, "سفارشت ثبت شد", platform=platform_service.TELEGRAM, shop_bot_id=shop_bot_id,
            label="order-status:1", dedupe_key="ordstat:1:abc",
        )
        assert await notification_service.enqueue(
            session, CUSTOMER_TG_ID, "سفارشت ثبت شد", platform=platform_service.TELEGRAM, shop_bot_id=shop_bot_id,
            dedupe_key="ordstat:1:abc",
        ) is False, "کلیدِ تکراری نباید دومینِ صف بسازد"
        assert await notification_service.enqueue(session, CUSTOMER_TG_ID, "   ") is False, "متنِ خالی اعلان نیست"
        await session.commit()

    async with session_scope() as session:
        rows = list((await session.execute(select(Notification))).scalars().all())
    assert len(rows) == 1 and rows[0].status == "pending", rows

    manager = _Manager({shop_bot_id: _SendBot()})
    main_bot = _SendBot()
    async with session_scope() as session:
        summary = await notification_service.send_due(session, manager, main_bot)
        await session.commit()
    assert summary == {"sent": 1, "retrying": 0, "failed": 0}, summary
    assert manager.bots[shop_bot_id].sent == [(CUSTOMER_TG_ID, "سفارشت ثبت شد")], manager.bots[shop_bot_id].sent
    async with session_scope() as session:
        row = (await session.execute(select(Notification))).scalars().one()
        assert row.status == "sent" and row.sent_at is not None
    print("✅ test_outbox_lifecycle_and_dedupe PASSED")


class _Manager:
    def __init__(self, bots: dict[int, _SendBot]) -> None:
        self.bots = bots

    def customer_bot(self, shop_bot_id: int, platform: str | None) -> _SendBot | None:
        return self.bots.get(shop_bot_id)

    def registered_shop_bot_ids(self) -> list[int]:
        return list(self.bots)

    def registered_bale_bot_ids(self) -> list[int]:
        return []


async def test_outbox_backs_off_and_gives_up_loudly() -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    async with session_scope() as session:
        await notification_service.enqueue(session, CUSTOMER_TG_ID, "خبر", shop_bot_id=shop_bot_id, label="t")
        await session.commit()

    manager = _Manager({shop_bot_id: _SendBot(fail_with=_api_error())})
    base = datetime.datetime(2026, 11, 1, 12, 0, tzinfo=datetime.timezone.utc)
    for attempt in range(1, notification_service.MAX_ATTEMPTS):
        now = base + datetime.timedelta(hours=3 * attempt)  # هر بار از backoffِ آن مرحله رد می‌شویم
        async with session_scope() as session:
            summary = await notification_service.send_due(session, manager, _SendBot(), now=now)
            await session.commit()
        assert summary["retrying"] == 1, summary
        async with session_scope() as session:
            row = (await session.execute(select(Notification))).scalars().one()
            assert row.status == "pending" and row.attempts == attempt, (row.status, row.attempts)
            assert row.next_attempt_at > now, "تلاشِ بعدی باید عقب بیفتد (backoff)"
            assert row.last_error and "service unavailable" in row.last_error

    final_now = base + datetime.timedelta(days=5)
    async with session_scope() as session:
        summary = await notification_service.send_due(session, manager, _SendBot(), now=final_now)
        await session.commit()
    assert summary["failed"] == 1, summary
    async with session_scope() as session:
        row = (await session.execute(select(Notification))).scalars().one()
        assert row.status == "failed" and row.attempts == notification_service.MAX_ATTEMPTS
        stats = await notification_service.stats(session)
    assert stats["failed"] == 1 and stats["pending"] == 0, stats
    print("✅ test_outbox_backs_off_and_gives_up_loudly PASSED")


# ============================================================================= ۴ — مسیرِ واقعیِ سفارش
async def test_order_status_notice_falls_into_the_outbox(main_dp, bot_manager) -> None:
    from app.bots.main_bot.handlers import order_ops
    from app.bots.shop_bot import texts as shop_texts  # noqa: F401
    from app.services import customer_service, shop_owner_service

    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    async with session_scope() as session:
        shop_bot = await shop_bot_service.get_by_id(session, shop_bot_id)
        customer = await customer_service.get_or_create_customer(session, shop_bot_id, CUSTOMER_TG_ID, "خریدار", None)
        order = OrderConsultation(
            shop_bot_id=shop_bot_id,
            customer_id=customer.id,
            type=OrderType.CONSULTATION,
            summary="مشاوره",
            status=OrderStatus.PENDING,
        )
        session.add(order)
        await session.flush()
        order_id = order.id
        owner = await shop_owner_service.get_by_id(session, shop_bot.shop_owner_id)
        owner_id = owner.id

    transient = _Manager({shop_bot_id: _SendBot(fail_with=_api_error())})
    async with session_scope() as session:
        shop_bot = await shop_bot_service.get_by_id(session, shop_bot_id)
        rows = list((await session.execute(select(OrderConsultation).where(OrderConsultation.id == order_id))).scalars().all())
        ok = await order_ops.notify_customer(session, shop_bot, rows, "سفارشت تایید شد", transient)
        assert ok is False, "خطایِ ارسال باید به caller گزارش شود"
        await session.commit()

    async with session_scope() as session:
        queued = list((await session.execute(select(Notification))).scalars().all())
    assert len(queued) == 1 and queued[0].chat_id == CUSTOMER_TG_ID and queued[0].platform == "telegram", queued
    assert queued[0].label == f"order-status:{order_id}", queued[0].label

    # همان خبرِ دوباره‌فراخوانی‌شده ⇒ هنوز یک ردیف (dedupe با کلیدِ رویداد)
    async with session_scope() as session:
        shop_bot = await shop_bot_service.get_by_id(session, shop_bot_id)
        rows = list((await session.execute(select(OrderConsultation).where(OrderConsultation.id == order_id))).scalars().all())
        await order_ops.notify_customer(session, shop_bot, rows, "سفارشت تایید شد", transient)
        await session.commit()
    async with session_scope() as session:
        assert len(list((await session.execute(select(Notification))).scalars().all())) == 1

    # مشتریِ بلاک‌شده (Forbidden) ⇒ صف نمی‌شود، چون تلاشِ دوباره فایده ندارد
    async with session_scope() as session:
        customer = (await session.execute(select(Customer).where(Customer.telegram_id == CUSTOMER_TG_ID))).scalars().one()
        customer.is_blocked = True
        await session.commit()
    async with session_scope() as session:
        shop_bot = await shop_bot_service.get_by_id(session, shop_bot_id)
        rows = list((await session.execute(select(OrderConsultation).where(OrderConsultation.id == order_id))).scalars().all())
        forbidden = _Manager({shop_bot_id: _SendBot(fail_with=TelegramForbiddenError(method=None, message="chat was destroyed"))})
        assert await order_ops.notify_customer(session, shop_bot, rows, "سفارشت لغو شد", forbidden) is False
        await session.commit()
    async with session_scope() as session:
        still = list((await session.execute(select(Notification).where(Notification.label == f"order-status:{order_id}"))).scalars().all())
    assert len(still) == 1, "فقط خطایِ گذرا واردِ صف می‌شود"
    assert owner_id is not None
    print("✅ test_order_status_notice_falls_into_the_outbox PASSED")


# ============================================================================= ۵ — سیم‌کشیِ جاب
async def test_periodic_pass_drains_the_outbox(bot_manager) -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    bot_manager._bale_bots.clear()
    async with session_scope() as session:
        await notification_service.enqueue(session, CUSTOMER_TG_ID, "خبرِ معوق", shop_bot_id=shop_bot_id)
        await session.commit()

    deliveries = _Manager({shop_bot_id: _SendBot()})
    main_bot = make_shop_bot("000000:MAIN_FAKE")
    await scheduler.run_periodic_pass(main_bot, deliveries)

    async with session_scope() as session:
        row = (await session.execute(select(Notification))).scalars().one()
    assert row.status == "sent", row.status
    assert deliveries.bots[shop_bot_id].sent == [(CUSTOMER_TG_ID, "خبرِ معوق")]
    print("✅ test_periodic_pass_drains_the_outbox PASSED")


# ============================================================================= ۶ — عددِ کیف‌پول
async def test_credit_summary_shows_usable_and_expiring() -> None:
    from app.services import commission_service

    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID, initial_balance_toman=0)
    async with session_scope() as session:
        owner = (await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == OWNER_TG_ID))).scalars().one()
        admin = await get_admin_settings(session)
        admin.wallet_topup_validity_months = 12
        await session.flush()
        near_expiry = await wallet_service.add_charge(session, owner, 40_000, reason=WalletTransactionReason.TOPUP)
        near_expiry.expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=10)
        far = await wallet_service.add_charge(session, owner, 60_000, reason=WalletTransactionReason.TOPUP)
        owner.commission_reserved_toman = 25_000
        await session.commit()

    async with session_scope() as session:
        owner = (await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == OWNER_TG_ID))).scalars().one()
        usable, expiring, days_left = await wallet_service.credit_summary(session, owner)
    assert usable == 75_000, usable  # ۱۰۰٬۰۰۰ موجودی منهای ۲۵٬۰۰۰ hold
    assert commission_service.usable_credit(owner) == usable
    assert expiring == 40_000, expiring  # فقط بسته‌ای که ۱۰ روز مانده دارد
    assert days_left == 10, days_left
    print("✅ test_credit_summary_shows_usable_and_expiring PASSED")


# ============================================================================= ۷ — خاتمهٔ کوئریِ پنهان
def test_shop_bot_products_is_no_longer_eagerly_loaded() -> None:
    from sqlalchemy.orm import class_mapper

    lazy = class_mapper(ShopBot).relationships["products"].lazy
    assert lazy == "raise", (
        f"استراتژیِ بارگذاریِ محصولاتِ فروشگاه = {lazy}؛ با selectin هر بار که ShopBot خوانده می‌شود "
        "(یعنی هر پیامِ مشتری) کلِ فهرستِ محصولات هم با یک کوئریِ اضافه می‌آید"
    )
    print("✅ test_shop_bot_products_is_no_longer_eagerly_loaded PASSED")


# ============================================================================= ۸ — دیدِ ادمینِ صف
async def _make_one_failed_notice(shop_bot_id: int, label: str) -> None:
    async with session_scope() as session:
        await notification_service.enqueue(session, CUSTOMER_TG_ID, "خبرِ سفارش", shop_bot_id=shop_bot_id, label=label)
        row = (await session.execute(select(Notification))).scalars().one()
        row.status = notification_service.FAILED
        row.attempts = notification_service.MAX_ATTEMPTS
        row.last_error = "502: service unavailable"
        await session.commit()


async def test_admin_notification_queue_panel_and_retry(main_dp) -> None:
    """P20-E: ادمین باید بفهمد «چند خبر نرسیده» و بتواند تلاشِ دوباره را راه بیندازد."""
    from aiogram import Bot

    from app.bots.main_bot import keyboards, texts
    from harness import FakeSession, make_callback_update

    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)

    async with session_scope() as session:
        admin = await get_admin_settings(session)
    datas = [b.callback_data for row in keyboards.admin_settings_group_keyboard("shops", admin).inline_keyboard for b in row if b.callback_data]
    assert "admin_notification_queue" in datas, "دکمه‌یِ صف باید در دستهٔ «فروشگاه‌دارها و گزارش‌ها» باشد"

    # صفِ خالی ⇒ گزارشِ «همه‌چیز درست» (نه صفرهایِ گم‌گشاده)
    admin_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())
    await main_dp.feed_update(admin_bot, make_callback_update(1, data="admin_notification_queue", user_id=ADMIN_TG_ID))
    assert "خالی است" in admin_bot.session.sent_messages[-1]["text"]

    await _make_one_failed_notice(shop_bot_id, "order-status:7")
    await main_dp.feed_update(admin_bot, make_callback_update(2, data="admin_notification_queue", user_id=ADMIN_TG_ID))
    report = admin_bot.session.sent_messages[-1]["text"]
    assert "🛑 شکست‌خورده" in report and "order-status:7" in report and "502" in report, report
    markup = admin_bot.session.sent_messages[-1]["reply_markup"]
    assert any(
        (b.callback_data or "") == "admin_notification_retry" for row in markup.inline_keyboard for b in row
    ), "وقتی شکستی هست باید راهِ اقدام هم باشد"

    await main_dp.feed_update(admin_bot, make_callback_update(3, data="admin_notification_retry", user_id=ADMIN_TG_ID))
    assert admin_bot.session.sent_messages[-1]["text"] == texts.NOTIFICATION_QUEUE_RETRY_DONE.format(count=1)
    async with session_scope() as session:
        row = (await session.execute(select(Notification))).scalars().one()
        assert row.status == notification_service.PENDING and row.attempts == 0, (row.status, row.attempts)
        assert row.last_error is None, "دلیلِ شکستِ قبلی پاک می‌شود تا در گزارشِ بعدی گیج‌کننده نباشد"

    # تلاشِ دوبارهٔ بی‌مورد ⇒ پیامِ «نبود»، نه عددِ صفرِ مبهم
    await main_dp.feed_update(admin_bot, make_callback_update(4, data="admin_notification_retry", user_id=ADMIN_TG_ID))
    assert admin_bot.session.sent_messages[-1]["text"] == texts.NOTIFICATION_QUEUE_RETRY_NONE
    print("✅ test_admin_notification_queue_panel_and_retry PASSED")


async def main() -> None:
    main_dp, _shop_dp, bot_manager, _main_bot = build_test_dispatchers()
    await test_outbox_lifecycle_and_dedupe()
    await test_outbox_backs_off_and_gives_up_loudly()
    await test_order_status_notice_falls_into_the_outbox(main_dp, bot_manager)
    await test_periodic_pass_drains_the_outbox(bot_manager)
    await test_credit_summary_shows_usable_and_expiring()
    test_shop_bot_products_is_no_longer_eagerly_loaded()
    await test_admin_notification_queue_panel_and_retry(main_dp)


if __name__ == "__main__":
    asyncio.run(main())
