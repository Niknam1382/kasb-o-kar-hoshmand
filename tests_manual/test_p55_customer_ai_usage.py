"""پ۵۵ · موردِ ۲۳: رتبه‌بندیِ مصرفِ هوشِ مصنوعیِ هر کاربر + سقف/توقف/بلاک.

پوششِ داده‌شده:
۱. `ai_usage_service.rank_page`: پنجرهٔ [since,until)، رتبه‌بندیِ نزولیِ مصرف با شکستِ تساوی
   بر شناسه، شمارِ کاربرانِ متمایز، بیرون‌ماندنِ برگشتِ اعتبار و ردیف‌هایِ بی‌مشتری، صفحه‌بندی.
۲. اعتبارسنجیِ سختِ ورودی‌ها (صفحه، اندازهٔ صفحه، مبلغِ سقف، مدتِ توقف).
۳. `block_reason`: کاربرِ بی‌تنظیم ⇒ صفرِ کوئری (سقفِ statementهایِ مسیرِ پیام حفظ می‌شود)؛
   توقفِ آینده ⇒ متوقف؛ توقفِ گذشته ⇒ آزاد؛ سقفِ رسیده ⇒ محدود.
۴. مسیرِ واقعیِ پیام: کسرِ اعتبارِ AI حالا `customer_id` دارد و عددِ پول دست‌نخورده است.
۵. سقفِ روزانه و توقفِ موقت رویِ همان مسیر: پاسخِ AI ساخته نمی‌شود، کسرِ تازه‌ای ثبت نمی‌شود
   و موجودیِ فروشگاه‌دار عوض نمی‌شود؛ با برداشتنِ محدودیت، پاسخ برمی‌گردد.
۶. صفحهٔ پنل: فهرست ← پنجرهٔ ۳۰ روز ← صفحهٔ دوم ← جزئیات ← توقف/آزادکردن ← سقفِ ۲۴ ساعت
   (FSM با ورودیِ بد و انصراف) ← بلاک/رفعِ بلاک، با ممیزیِ هر تصمیم و صفر جابه‌جاییِ پول.
۷. دسترسی: ادمینِ عملیاتی و کاربرِ معمولی ⇒ صفر پیام، صفر ویرایش؛ پنجرهٔ ناشناخته رد می‌شود.
۸. کیبورد: بودجهٔ ۶۴ بایتی، صفحه‌گردانیِ بی‌مورد نبودن، دکمه در `_KNOWN_MENU_BUTTONS` و فقط
   در کیبوردِ سوپرادمین.

اجرا: python3 tests_manual/run_one.py test_p55_customer_ai_usage.py
"""
from __future__ import annotations

import asyncio
import contextlib
import datetime as dt
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402
from sqlalchemy import event, select  # noqa: E402

from harness import FakeSession, build_test_dispatchers, make_callback_update, make_message_update, reset_database  # noqa: E402
from phase4_helpers import Chat, callbacks  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot import keyboards, router as main_router, texts as main_texts  # noqa: E402
from app.bots.shop_bot import texts as shop_texts  # noqa: E402
from app.database.models import (  # noqa: E402
    AuditEventType, AuditLogEntry, Customer, ShopBot, ShopOwner, WalletTransaction, WalletTransactionReason,
)
from app.database.session import engine, session_scope  # noqa: E402
from app.services import (  # noqa: E402
    admin_role_service, admin_settings_service, ai_service, ai_usage_service, customer_service,
)
from app.services.ai_service import AiCallResult  # noqa: E402

UTC = dt.timezone.utc
ADMIN_TG_ID = 12345
OPERATOR_TG_ID = 995543
OWNER_TG_ID = 995541
SHOP_BOT_TG_ID = 995542
CUSTOMER_TG_ID = 995549
MAIN_TOKEN = "550000:FAKE_MAIN_BOT_TOKEN_FOR_P55_TESTING"
# شناسهٔ رباتِ داخلِ توکن باید با `SHOP_BOT_TG_ID`ِ سیدشده یکی باشد، وگرنه `get_by_bot`
# چیزی پیدا نمی‌کند و هندلر پیش ازِ هر فراخوانِ AI خارج می‌شود (الگویِ test_p31).
SHOP_TOKEN = f"{SHOP_BOT_TG_ID}:FAKE_SHOP_BOT_TOKEN_FOR_P55_TESTING"
NOW = dt.datetime.now(UTC).replace(microsecond=0)


class _FakeAi:
    def __init__(self) -> None:
        self.calls = 0

    async def get_reply(self, system_prompt, history, user_message) -> AiCallResult:
        self.calls += 1
        return AiCallResult(text="پاسخِ آزمایشی", total_tokens=10)

    async def analyze_image(self, prompt, image_bytes, mime_type="image/jpeg") -> AiCallResult:
        return AiCallResult(text="تحلیلِ آزمایشی", total_tokens=10)

    async def transcribe_audio(self, audio_bytes, filename="voice.ogg") -> str:
        return "متنِ آزمایشی"


@contextlib.contextmanager
def _counted():
    """شمارندهٔ جمله رویِ همان engine (الگویِ test_p31؛ شمارندهٔ کلاس‌ای نه)."""
    seen: list[str] = []

    def _listener(_conn, _cursor, statement, _params, _context, _executemany):
        seen.append(" ".join(statement.split()))

    event.listen(engine.sync_engine, "before_cursor_execute", _listener)
    try:
        yield seen
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", _listener)


async def seed_customers(count: int = 12) -> tuple[int, list[int]]:
    """یکِ فروشگاهِ قابلِ استفاده + `count` مشتری؛ مصرفِ مشتریِ i ام = (count-i)×۷ تومان."""
    await reset_database()
    shop_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    ids: list[int] = []
    async with session_scope() as session:
        shop_bot = await session.get(ShopBot, shop_id)
        owner_id = shop_bot.shop_owner_id
        for index in range(count):
            customer = await customer_service.get_or_create_customer(
                session, shop_id, 5500 + index, f"مشتری{index}", None, platform="telegram"
            )
            ids.append(customer.id)
            spent = (count - index) * 7
            rows = [
                WalletTransaction(
                    shop_owner_id=owner_id, customer_id=customer.id, amount_toman=-spent,
                    reason=WalletTransactionReason.CHAT_MESSAGE,
                    created_at=NOW - dt.timedelta(minutes=30 + index),
                )
            ]
            if index == 0:
                # ردیفِ مثبت (استرداد/اصلاح) نباید رتبه را بالا ببرد و ردیفِ بی‌مشتری نباید شمرده شود
                rows += [
                    WalletTransaction(shop_owner_id=owner_id, customer_id=customer.id, amount_toman=spent,
                                      reason=WalletTransactionReason.ADMIN_CORRECTION,
                                      created_at=NOW - dt.timedelta(minutes=1)),
                    WalletTransaction(shop_owner_id=owner_id, customer_id=None, amount_toman=999_999,
                                      reason=WalletTransactionReason.CHAT_MESSAGE,
                                      created_at=NOW - dt.timedelta(minutes=2)),
                ]
            session.add_all(rows)
        old = await customer_service.get_or_create_customer(session, shop_id, 5600, "قدیمی", None, platform="telegram")
        session.add(
            WalletTransaction(shop_owner_id=owner_id, customer_id=old.id, amount_toman=-50_000,
                              reason=WalletTransactionReason.CHAT_MESSAGE, created_at=NOW - dt.timedelta(days=3))
        )
    return shop_id, ids


async def _owner_balance() -> int:
    async with session_scope() as session:
        shop_bot = (await session.execute(select(ShopBot).limit(1))).scalar_one()
        owner = await session.get(ShopOwner, shop_bot.shop_owner_id)
        return owner.wallet_balance_toman


async def _customer_charges(customer_id: int) -> list[WalletTransaction]:
    async with session_scope() as session:
        rows = (
            await session.execute(select(WalletTransaction).where(WalletTransaction.customer_id == customer_id))
        ).scalars().all()
        return list(rows)


async def _first_customer_id() -> int:
    async with session_scope() as session:
        return (await session.execute(select(Customer).order_by(Customer.id))).scalars().first().id


async def _telegram_reply(shop_dp, text: str, user_id: int, update_id: int) -> tuple[list[dict], int]:
    """یکِ پیامِ مشتری از راهِ dispatcherِ فروشگاهی؛ برمی‌گرداند (پیام‌هایِ رفته، تعدادِ فراخوانِ AI)."""
    admin_settings_service.reset_read_cache()
    fake = _FakeAi()
    original = ai_service.get_ai_service
    ai_service.get_ai_service = lambda *args, **kwargs: fake
    try:
        bot = Bot(token=SHOP_TOKEN, session=FakeSession())
        await shop_dp.feed_update(bot, make_message_update(update_id, text=text, user_id=user_id))
        await asyncio.sleep(4.5)
        sent = list(bot.session.sent_messages)
        await bot.session.close()
    finally:
        ai_service.get_ai_service = original
    return sent, fake.calls


async def test_rank_page_orders_and_pages() -> None:
    _shop_id, ids = await seed_customers()
    since = NOW - dt.timedelta(hours=24)
    async with session_scope() as session:
        first, total = await ai_usage_service.rank_page(session, since=since, until=NOW, page=0)
        second, _ = await ai_usage_service.rank_page(session, since=since, until=NOW, page=1)
        beyond, _ = await ai_usage_service.rank_page(session, since=since, until=NOW, page=9)
        month, month_total = await ai_usage_service.rank_page(session, since=NOW - dt.timedelta(days=30), until=NOW)
    assert total == len(ids), (total, len(ids))
    assert [customer_id for customer_id, _s, _c in first] == ids[:10], "بیشترینِ مصرف اول"
    assert [customer_id for customer_id, _s, _c in second] == ids[10:], second
    assert beyond == [], "صفحهٔ بیرونِ دامنه خالی است نه خطا"
    assert first[0][1] == 12 * 7 and first[0][2] == 1, first[0]
    assert month_total == len(ids) + 1 and month[0][1] == 50_000, "کسرِ سه‌روزِ پیش فقط در پنجرهٔ بزرگ"
    assert all(spent > 0 for _id, spent, _c in first), "برگشتِ مثبت رتبه نمی‌سازد"
    print("PASS test_rank_page_orders_and_pages")


async def test_service_validates_inputs() -> None:
    await seed_customers(2)
    async with session_scope() as session:
        customer = (await session.execute(select(Customer).order_by(Customer.id))).scalars().first()
        for bad in (-1, "0", 1.0, None, True):
            try:
                await ai_usage_service.rank_page(session, since=NOW, until=NOW + dt.timedelta(hours=1), page=bad)
            except ValueError:
                pass
            else:
                raise AssertionError(f"صفحهٔ نامعتبر پذیرفته شد: {bad!r}")
        for bad_size in (0, 51, "10"):
            try:
                await ai_usage_service.rank_page(
                    session, since=NOW, until=NOW + dt.timedelta(hours=1), page=0, page_size=bad_size
                )
            except ValueError:
                pass
            else:
                raise AssertionError(f"اندازهٔ صفحهٔ نامعتبر پذیرفته شد: {bad_size!r}")
        for bad_limit in (0, -5, "5000", 5.0):
            try:
                await ai_usage_service.set_daily_limit(session, customer, bad_limit)
            except ValueError:
                pass
            else:
                raise AssertionError(f"سقفِ نامعتبر پذیرفته شد: {bad_limit!r}")
        for bad_hours in (0, 24 * 30 + 1, "24"):
            try:
                await ai_usage_service.set_paused(session, customer, bad_hours)
            except ValueError:
                pass
            else:
                raise AssertionError(f"مدتِ توقفِ نامعتبر پذیرفته شد: {bad_hours!r}")

        assert await ai_usage_service.set_daily_limit(session, customer, 40_000) == 40_000
        assert await ai_usage_service.set_daily_limit(session, customer, None) is None
        until = await ai_usage_service.set_paused(session, customer, 24)
        assert until is not None and until > dt.datetime.now(UTC)
        assert await ai_usage_service.set_paused(session, customer, None) is None
        spent, calls = await ai_usage_service.spend_and_calls(session, customer.id, NOW - dt.timedelta(hours=1), NOW)
        assert calls == 1 and spent > 0, (spent, calls)
        print("PASS test_service_validates_inputs")


async def test_block_reason_is_free_when_unset() -> None:
    await seed_customers(2)
    async with session_scope() as session:
        customer = (await session.execute(select(Customer).order_by(Customer.id))).scalars().first()
        with _counted() as seen:
            assert await ai_usage_service.block_reason(session, customer, now=NOW) is None
        assert not seen, f"کاربرِ بی‌تنظیم نباید کوئری بزند؛ زده شد {seen}"

        await ai_usage_service.set_paused(session, customer, 24)
        assert await ai_usage_service.block_reason(session, customer, now=NOW) == ai_usage_service.REASON_PAUSED
        customer.ai_paused_until = NOW - dt.timedelta(minutes=1)
        assert await ai_usage_service.block_reason(session, customer, now=NOW) is None, "توقفِ گذشته آزاد است"

        await ai_usage_service.set_daily_limit(session, customer, 1)
        with _counted() as seen_limited:
            assert await ai_usage_service.block_reason(session, customer, now=NOW) == ai_usage_service.REASON_DAILY_LIMIT
        assert len([s for s in seen_limited if "wallet_transactions" in s]) == 1, seen_limited
        assert await ai_usage_service.block_reason(session, None, now=NOW) is None
        print("PASS test_block_reason_is_free_when_unset")


async def test_message_path_attributes_the_charge(shop_dp) -> None:
    shop_id, _ids = await seed_customers(1)
    before = await _owner_balance()
    sent, calls = await _telegram_reply(shop_dp, "سلام", CUSTOMER_TG_ID, 1)
    # `seed_usable_shop` تشخیصِ سفارشِ قدیمی را روشن می‌گذارد ⇒ علاوه بر چت، یکِ فراخوانِ
    # دوم هم ممکن است؛ آنچه مهم است «حداقل یکِ فراخوانِ واقعی» و اتصالِ همان کسرهاست.
    assert calls >= 1, sent
    async with session_scope() as session:
        customer = (
            await session.execute(
                select(Customer).where(Customer.shop_bot_id == shop_id, Customer.telegram_id == CUSTOMER_TG_ID)
            )
        ).scalar_one()
        customer_id = customer.id
    rows = await _customer_charges(customer_id)
    assert rows, "کسرِ AI باید به همین مشتری وصل شود"
    assert any(row.reason == WalletTransactionReason.CHAT_MESSAGE for row in rows), rows
    assert all(row.customer_id == customer_id for row in rows), rows
    after = await _owner_balance()
    assert after < before, "مبلغ از موجودیِ فروشگاه‌دار کم شده است"
    assert before - after == sum(-row.amount_toman for row in rows), "عددِ پول با همان کسر می‌خواند"
    print("PASS test_message_path_attributes_the_charge")


async def test_limit_and_pause_cost_nothing(shop_dp) -> None:
    shop_id, _ids = await seed_customers(1)
    # اول یکِ پیامِ عادی تا هم مشتری ساخته شود و هم یکِ کسرِ واقعی به او وصل شود
    sent, calls = await _telegram_reply(shop_dp, "سلام", CUSTOMER_TG_ID, 1)
    assert calls >= 1, sent
    async with session_scope() as session:
        customer = (
            await session.execute(
                select(Customer).where(Customer.shop_bot_id == shop_id, Customer.telegram_id == CUSTOMER_TG_ID)
            )
        ).scalar_one()
        await ai_usage_service.set_daily_limit(session, customer, 1)
        target_id = customer.id

    rows_before = await _customer_charges(target_id)
    balance_before = await _owner_balance()
    sent, calls = await _telegram_reply(shop_dp, "قیمت؟", CUSTOMER_TG_ID, 2)
    assert any(shop_texts.AI_USAGE_LIMIT_REPLY in row["text"] for row in sent), sent
    assert calls == 0, "با سقفِ پرشده نباید فراخوانِ AI ساخته شود"
    assert await _owner_balance() == balance_before, "سقفِ پرشده هیچ مبلغی کم نمی‌کند"
    assert len(await _customer_charges(target_id)) == len(rows_before), "کسرِ تازه‌ای ثبت نمی‌شود"

    async with session_scope() as session:
        customer = await session.get(Customer, target_id)
        await ai_usage_service.set_daily_limit(session, customer, None)
        await ai_usage_service.set_paused(session, customer, 24)
    sent, calls = await _telegram_reply(shop_dp, "سلام", CUSTOMER_TG_ID, 3)
    assert any(shop_texts.AI_USAGE_PAUSED_REPLY in row["text"] for row in sent), sent
    assert calls == 0 and await _owner_balance() == balance_before, "توقف هم بی‌هزینه است"

    async with session_scope() as session:
        customer = await session.get(Customer, target_id)
        await ai_usage_service.set_paused(session, customer, None)
    sent, calls = await _telegram_reply(shop_dp, "سلام دوباره", CUSTOMER_TG_ID, 4)
    assert calls >= 1, "با برداشتنِ توقف پاسخِ خودکار برمی‌گردد"
    assert await _owner_balance() < balance_before
    print("PASS test_limit_and_pause_cost_nothing")


async def test_admin_screen_and_actions(main_dp) -> None:
    await seed_customers(12)
    admin = Chat(main_dp, ADMIN_TG_ID)
    await admin.say(main_texts.AI_USAGE_BUTTON)
    screen = admin.last_text
    assert "۱۲ کاربر" in screen and "۲۴ ساعت" in screen, screen
    assert "شمارش از همین نسخه" in screen, "صراحتِ لازم دربارهٔ گذشته"
    flat = callbacks(admin.last_markup)
    assert any(value.startswith("ai_usage_view:24h:0:") for value in flat), flat
    assert "ai_usage:7d:0" in flat and "ai_usage:30d:0" in flat, flat

    await admin.tap("ai_usage:30d:0")
    assert "۳۰ روز" in admin.last_edit_text and "۱۳ کاربر" in admin.last_edit_text, admin.last_edit_text
    await admin.tap("ai_usage:24h:1")
    assert "صفحهٔ ۲ از ۲" in admin.last_edit_text, admin.last_edit_text

    target = await _first_customer_id()
    await admin.tap(f"ai_usage_view:24h:0:{target}")
    detail = admin.last_edit_text
    assert "سقفِ مصرف در ۲۴ ساعت: بدونِ سقف" in detail and "وضعیت: ✅" in detail, detail
    assert "این صفحه مصرف را نشان می‌دهد و مبلغی" in detail, detail

    balance_before = await _owner_balance()
    await admin.tap(f"ai_usage_pause:{target}:24:24h:0")
    assert "متوقف تا" in admin.last_edit_text, admin.last_edit_text
    await admin.tap(f"ai_usage_pause:{target}:0:24h:0")
    assert "وضعیت: ✅ پاسخِ خودکار فعال است" in admin.last_edit_text, admin.last_edit_text

    await admin.tap(f"ai_usage_limit:{target}:24h:0")
    assert "سقفِ مصرفِ این کاربر" in admin.last_text, admin.last_text
    await admin.say("abc")
    assert main_texts.AI_USAGE_LIMIT_INVALID in admin.last_text, admin.last_text
    await admin.say("انصراف")
    assert main_texts.AI_USAGE_CANCELLED in admin.last_text, admin.last_text

    await admin.tap(f"ai_usage_limit:{target}:24h:0")
    await admin.say("۵۰۰۰۰")
    assert "سقفِ مصرفِ این کاربر: ۵۰٬۰۰۰ تومان" in admin.last_text, admin.last_text
    await admin.tap(f"ai_usage_limit:{target}:24h:0")
    await admin.say("بدونِ سقف")
    assert "برداشته شد" in admin.last_text, admin.last_text

    await admin.tap(f"ai_usage_block:{target}:1:24h:0")
    await admin.tap(f"ai_usage_block:{target}:0:24h:0")
    assert await _owner_balance() == balance_before, "این صفحه هیچ مبلغی جابه‌جا نمی‌کند"

    async with session_scope() as session:
        entries = list(
            (
                await session.execute(
                    select(AuditLogEntry).where(
                        AuditLogEntry.event_type.in_(
                            [AuditEventType.ADMIN_SETTING_CHANGED.value, AuditEventType.CUSTOMER_BLOCK_CHANGED.value]
                        )
                    )
                )
            ).scalars().all()
        )
    kinds = [entry.event_type for entry in entries]
    assert kinds.count(AuditEventType.ADMIN_SETTING_CHANGED.value) >= 4, kinds
    assert kinds.count(AuditEventType.CUSTOMER_BLOCK_CHANGED.value) == 2, kinds
    assert any("سقفِ مصرف" in (entry.details or "") for entry in entries), "ممیزی باید بگوید چه عوض شد"
    assert any("توقفِ پاسخِ خودکار" in (entry.details or "") for entry in entries), kinds
    print("PASS test_admin_screen_and_actions")


async def test_operator_and_bad_windows_are_denied(main_dp) -> None:
    await seed_customers(3)
    async with session_scope() as session:
        await admin_role_service.grant_operator(session, OPERATOR_TG_ID, granted_by_telegram_id=ADMIN_TG_ID)

    operator_labels = [button.text for row in keyboards.admin_panel_keyboard(False).keyboard for button in row]
    super_labels = [button.text for row in keyboards.admin_panel_keyboard(True).keyboard for button in row]
    assert main_texts.AI_USAGE_BUTTON not in operator_labels, "دکمه فقط در کیبوردِ سوپرادمین"
    assert main_texts.AI_USAGE_BUTTON in super_labels

    bot = Bot(token=MAIN_TOKEN, session=FakeSession())
    for index, data in enumerate(
        ("ai_usage:24h:0", "ai_usage_view:24h:0:1", "ai_usage_pause:1:24:24h:0", "ai_usage_block:1:1:24h:0"), 400
    ):
        await main_dp.feed_update(bot, make_callback_update(index, data=data, user_id=OPERATOR_TG_ID))
    await main_dp.feed_update(bot, make_message_update(420, text=main_texts.AI_USAGE_BUTTON, user_id=OPERATOR_TG_ID))
    await main_dp.feed_update(bot, make_message_update(421, text="۵۰۰۰۰", user_id=OPERATOR_TG_ID))
    assert not bot.session.sent_messages and not bot.session.edited_texts, "فقط سوپرادمین"
    await bot.session.close()

    admin = Chat(main_dp, ADMIN_TG_ID)
    await admin.say(main_texts.AI_USAGE_BUTTON)
    balance_before = await _owner_balance()
    target = await _first_customer_id()
    for data in (
        "ai_usage:abc:0", "ai_usage:24h", "ai_usage:24h:-1", "ai_usage:24h:99999999",
        "ai_usage_view:99h:0:1", "ai_usage_view:24h:0", "ai_usage_view:24h:0:abc",
        "ai_usage_pause:1:24:99h:0", "ai_usage_pause:abc:24:24h:0", "ai_usage_pause:1:999:24h:0",
        "ai_usage_block:1:2:24h:0", "ai_usage_block:1:1:99h:0", "ai_usage_limit:1:24h", "ai_usage_limit:1:99h:0",
    ):
        await admin.tap(data)
        assert admin.last_toast["text"] == main_texts.AI_USAGE_INVALID, (data, admin.last_toast)
    await admin.tap("ai_usage_view:24h:0:999999")
    assert admin.last_toast["text"] == main_texts.AI_USAGE_INVALID, "شناسهٔ ناموجود"
    assert await _owner_balance() == balance_before, "ورودیِ خراب هیچ مبلغی را تکان نمی‌دهد"
    async with session_scope() as session:
        paused = (await session.execute(select(Customer).where(Customer.id == target))).scalar_one().ai_paused_until
    assert paused is None, "کال‌بکِ بیرونِ دامنه نباید ستونی را عوض کند"
    print("PASS test_operator_and_bad_windows_are_denied")


async def test_keyboard_bounds_and_menu_registration(main_dp) -> None:
    await seed_customers(3)
    async with session_scope() as session:
        customer = (await session.execute(select(Customer).order_by(Customer.id))).scalars().first()
    items = [(customer.id, index, "یکِ نامِ نسبتاً بلندِ تستی برایِ برچسب") for index in range(1, 3)]
    flat = callbacks(keyboards.ai_usage_keyboard(items, "24h", 0, 1))
    assert all(len(value.encode("utf-8")) <= 64 for value in flat), flat
    assert "ai_usage:24h:0" in flat and "ai_usage:7d:0" in flat, flat
    assert "ai_usage:24h:1" not in flat, "صفحه‌گردانیِ بی‌مورد نباید باشد"
    assert flat[-1] == "main_menu", flat

    detail = callbacks(keyboards.ai_usage_detail_keyboard(customer.id, "30d", 4, paused=True, blocked=True))
    assert f"ai_usage_pause:{customer.id}:0:30d:4" in detail, detail
    assert f"ai_usage_block:{customer.id}:1:30d:4" in detail, detail
    assert "ai_usage:30d:4" in detail, detail
    assert main_texts.AI_USAGE_BUTTON in main_router._KNOWN_MENU_BUTTONS

    admin = Chat(main_dp, ADMIN_TG_ID)
    await admin.say(main_texts.AI_USAGE_BUTTON)
    labels = [button.text for row in admin.last_markup.inline_keyboard for button in row]
    assert any(label.startswith("۱ · ") for label in labels), labels
    assert all(len(label) <= 64 for label in labels), labels
    print("PASS test_keyboard_bounds_and_menu_registration")


async def main() -> None:
    main_dp, shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    await test_rank_page_orders_and_pages()
    await test_service_validates_inputs()
    await test_block_reason_is_free_when_unset()
    await test_message_path_attributes_the_charge(shop_dp)
    await test_limit_and_pause_cost_nothing(shop_dp)
    await test_admin_screen_and_actions(main_dp)
    await test_operator_and_bad_windows_are_denied(main_dp)
    await test_keyboard_bounds_and_menu_registration(main_dp)
    print("📊 نتیجه: ۸ تستِ پ۵۵ (مصرفِ هوشِ مصنوعیِ هر کاربر) پاس شد · رتبه/سقف/توقف/بلاک/ممیزی/دسترسی")


if __name__ == "__main__":
    asyncio.run(main())
