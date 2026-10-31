"""
تست: P18 · A5 — تنظیماتِ per-shop که از پنلِ ادمین به پنلِ فروشگاه‌دار منتقل شدند.

پوشش:
۱. پنلِ ادمین دیگر هیچ‌کدام از این تنظیم‌ها را نشان نمی‌دهد و دکمه‌یِ کهنه‌شان پیامِ روشن می‌دهد؛
   ستون‌ها و پیش‌فرض‌هایِ سراسریِ `AdminSettings` دست‌نخورده‌اند.
۲. بازه‌هایِ W5 (کف/سقفِ مهلتِ پرداخت و بررسیِ رسید) فقط از کد می‌آیند، نه از پنلِ ادمین.
۳. ملغیِ مقدار: per-shop اگر تنظیم شده، وگرنه پیش‌فرضِ سراسری؛ همیشه داخلِ بازه‌یِ ایمنی.
۴. اثرِ هر تنظیم در مصرف‌کننده‌یِ واقعی‌اش دیده می‌شود (رزروِ مبلغ، رزروِ موجودی، مهلتِ تاییدِ مشتری،
   پاکسازیِ گفتگو) و دو فروشگاه جدا می‌مانند.
۵. پنلِ فروشگاه‌دار: تنظیم، مقدارِ دلخواه، ردِّ نامعتبر، بازگشت به پیش‌فرض، و مودِ مشاوره‌ای فقط
   آنچه معنا دارد نشان می‌دهد.

اجرا: python3 tests_manual/test_p18_per_shop_settings.py
"""
from __future__ import annotations

import asyncio
import datetime
import pathlib
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402
from sqlalchemy import select  # noqa: E402

from harness import FakeSession, build_test_dispatchers, make_callback_update, make_message_update, reset_database  # noqa: E402
from phase4_helpers import Chat  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot import keyboards, texts as main_texts  # noqa: E402
from app.bots.main_bot.handlers import admin as admin_handlers  # noqa: E402
from app.bots.main_bot.states import ShopSettingsStates  # noqa: E402
from app.database.models import (
    AdminSettings,
    ConversationMessage,
    Customer,
    OrderConsultation,
    OrderStatus,
    OrderType,
    Payment,
    Product,
    ShopBot,
    TenantMode,
)
from app.database.session import session_scope  # noqa: E402
from app.services import (
    conversation_service,
    customer_service,
    order_service,
    payment_service,
    shop_prefs_service as prefs,
    shop_owner_service,
)
from app.services import payment_settings_service as pss
from app.services.admin_settings_service import get_admin_settings  # noqa: E402

ADMIN_TG_ID = 12345
OWNER_TG_ID = 999_851
SHOP_BOT_TG_ID = 999_852
OTHER_OWNER_TG_ID = 999_861
OTHER_SHOP_BOT_TG_ID = 999_862
CUSTOMER_TG_ID = 999_853
MAIN_TOKEN = "000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS"
UTC = datetime.timezone.utc

# فهرستِ «از پنلِ ادمین برداشته شد» را از خودِ محصول می‌خوانیم تا تست و کد جدا افتادنِ معنی‌دار نداشته باشن.
REMOVED_KEYS = tuple(sorted(prefs.REMOVED_FROM_ADMIN))


def _datas(markup) -> list[str]:
    return [b.callback_data for row in markup.inline_keyboard for b in row if b.callback_data] if markup else []


async def _shop_bot(shop_bot_id: int) -> ShopBot:
    async with session_scope() as session:
        return (await session.execute(select(ShopBot).where(ShopBot.id == shop_bot_id))).scalar_one()


async def _set_pref(shop_bot_id: int, **fields) -> None:
    async with session_scope() as session:
        row = (await session.execute(select(ShopBot).where(ShopBot.id == shop_bot_id))).scalar_one()
        for key, value in fields.items():
            setattr(row, key, value)


# ============================================================================= ۱ و ۲ — پنلِ ادمین
async def test_admin_panel_no_longer_offers_them(main_dp) -> None:
    await reset_database()
    async with session_scope() as session:
        admin_settings = await get_admin_settings(session)
        labels = {key for key, _ in main_texts.admin_settings_button_labels(admin_settings)}
        assert not (labels & set(REMOVED_KEYS)), labels & set(REMOVED_KEYS)
        before = (admin_settings.order_reservation_minutes, admin_settings.conversation_retention_days)
        assert before == (60, 90), "ستون‌ها و پیش‌فرض‌هایِ سراسری باید بمانند"

    for key in REMOVED_KEYS:
        assert key not in admin_handlers._INT_FIELDS, key
        assert key not in admin_handlers._INT_FIELDS_MAX, key
        assert key not in admin_handlers._INT_FIELDS_ALLOW_ZERO, key
    # باقیِ تنظیم‌هایِ واقعیِ پلتفرم هنوز در پنلِ ادمین‌اند ⇒ حذفِ بی‌جا انجام نشده
    assert "grace_period_hours" in admin_handlers._INT_FIELDS
    assert "periodic_report_frequency_days" in admin_handlers._INT_FIELDS
    assert "conversation_history_limit" in admin_handlers._INT_FIELDS

    admin_source = pathlib.Path("app/bots/main_bot/handlers/admin.py").read_text(encoding="utf-8")
    for key in REMOVED_KEYS:
        assert f'"{key}":' not in admin_source, key

    admin_bot = Bot(token=MAIN_TOKEN, session=FakeSession())
    session_obj: FakeSession = admin_bot.session  # type: ignore[assignment]
    n = 0
    for key in REMOVED_KEYS:
        n += 1
        await main_dp.feed_update(admin_bot, make_callback_update(n, data=f"admin_setting_edit:{key}", user_id=ADMIN_TG_ID))
    assert len(session_obj.sent_messages) == len(REMOVED_KEYS), session_obj.sent_messages
    assert all(m["text"] == main_texts.ADMIN_SETTING_REMOVED for m in session_obj.sent_messages)
    async with session_scope() as session:
        admin_settings = await get_admin_settings(session)
        assert (admin_settings.order_reservation_minutes, admin_settings.conversation_retention_days) == before
    for key in REMOVED_KEYS:
        assert key in AdminSettings.__table__.columns, f"{key}: داده نباید پاک شود"
    print("✅ test_admin_panel_no_longer_offers_them PASSED")


# ============================================================================= ۲ — بازه‌ها فقط از کد
def test_bounds_come_from_code_only() -> None:
    assert pss.deadline_bounds() == (5, 1440)
    assert pss.review_hold_bounds() == (60, 4320)
    assert pss.clamp_deadline(0) == 1 and pss.clamp_deadline(99999) == 10080
    assert pss.clamp_review_hold(1) == 10 and pss.clamp_review_hold(10**9) == 43200
    # هیچ ارجاعِ باقی‌مانده‌ای به آن چهار ستونِ بازه در سرویسِ تنظیماتِ پرداخت نمانده
    source = pathlib.Path("app/services/payment_settings_service.py").read_text(encoding="utf-8")
    for key in ("payment_deadline_min_minutes", "review_hold_max_hours"):
        assert key not in source, key
    print("✅ test_bounds_come_from_code_only PASSED")


# ============================================================================= ۳ — ملغیِ مقدار
def test_resolve_prefers_shop_then_global() -> None:
    admin = _Settings()
    blank = _ShopBot()
    assert prefs.resolve(prefs.ORDER_RESERVATION, blank, admin) == 60, "NULL ⇒ پیش‌فرضِ سراسری"
    assert prefs.resolve(prefs.ORDER_RESERVATION, _ShopBot(order_reservation_minutes=5), admin) == 5
    assert prefs.resolve(prefs.ORDER_RESERVATION, None, admin) == 60
    assert prefs.resolve(prefs.CONVERSATION_RETENTION, _ShopBot(conversation_retention_days=0), admin) == 0, "۰ یعنی خاموش"
    assert prefs.resolve(prefs.KNOWLEDGE_ITEMS, _ShopBot(knowledge_items_limit=999), admin) == 100, "clampِ ایمنی"
    assert prefs.resolve(prefs.CONFIRMATION_TIMEOUT, _ShopBot(order_confirmation_timeout_minutes=-5), admin) == 5
    assert prefs.resolve(prefs.KNOWLEDGE_ITEMS, blank, None) == 1, "بدونِ تنظیماتِ سراسری هم نمی‌ترکد"

    sales = prefs.prefs_for(False)
    consultation = prefs.prefs_for(True)
    assert {p.key for p in consultation} == {"conversation_retention_days", "knowledge_items_limit"}
    assert len(sales) == 5 and "payment_reservation_minutes" not in {p.key for p in consultation}

    assert prefs.parse_value(prefs.ORDER_RESERVATION, "۴۵") == 45, "ارقامِ فارسی"
    assert prefs.parse_value(prefs.ORDER_RESERVATION, "0") is None and prefs.parse_value(prefs.ORDER_RESERVATION, "10081") is None
    assert prefs.parse_value(prefs.ORDER_RESERVATION, "abc") is None and prefs.parse_value(prefs.ORDER_RESERVATION, None) is None
    assert prefs.parse_value(prefs.ORDER_RESERVATION, "1" * 8) is None
    assert prefs.parse_value(prefs.CONVERSATION_RETENTION, "0") == 0
    print("✅ test_resolve_prefers_shop_then_global PASSED")


class _Settings:
    payment_reservation_minutes = 60
    order_reservation_minutes = 60
    order_customer_confirmation_timeout_minutes = 60
    conversation_retention_days = 90
    knowledge_items_limit = 15


class _ShopBot:
    def __init__(self, **fields):
        for key in ("payment_reservation_minutes", "order_reservation_minutes", "order_confirmation_timeout_minutes",
                    "conversation_retention_days", "knowledge_items_limit"):
            setattr(self, key, fields.get(key))


# ============================================================================= ۴ — اثر در مصرف‌کننده‌ها
async def test_each_setting_changes_its_own_consumer() -> None:
    await reset_database()
    first = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    second = await seed_usable_shop(OTHER_OWNER_TG_ID, OTHER_SHOP_BOT_TG_ID)
    await _set_pref(first, order_reservation_minutes=10, payment_reservation_minutes=7)
    await _set_pref(second, order_reservation_minutes=600)

    async with session_scope() as session:
        admin_settings = await get_admin_settings(session)

        # رزروِ موجودیِ سفارش (per-shop)
        product_a = Product(shop_bot_id=first, name="الف", price_toman=100_000, stock_quantity=5, kind="physical")
        product_b = Product(shop_bot_id=second, name="ب", price_toman=100_000, stock_quantity=5, kind="physical")
        session.add_all([product_a, product_b])
        await session.flush()
        customer_a = await customer_service.get_or_create_customer(session, first, CUSTOMER_TG_ID, "مشتری", None)
        customer_b = await customer_service.get_or_create_customer(session, second, CUSTOMER_TG_ID, "مشتری", None)
        now_before = datetime.datetime.now(UTC)
        order_a = await order_service.create_order(session, first, customer_a.id, OrderType.ORDER, "خ", 100_000, product_a.id, 1)
        order_b = await order_service.create_order(session, second, customer_b.id, OrderType.ORDER, "خ", 100_000, product_b.id, 1)
        span_a = order_a.reservation_expires_at - now_before
        span_b = order_b.reservation_expires_at - now_before
        assert datetime.timedelta(minutes=9) < span_a < datetime.timedelta(minutes=11), span_a
        assert datetime.timedelta(minutes=599) < span_b < datetime.timedelta(minutes=601), span_b
        assert prefs.resolve(prefs.ORDER_RESERVATION, None, admin_settings) == 60, "پیش‌فرضِ سراسری دست‌نخورده"

        # رزروِ مبلغِ پرداختِ شارژِ کیف‌پول (per-owner)
        owner_a = await shop_owner_service.get_by_id(session, (await session.get(ShopBot, first)).shop_owner_id)
        topup = await payment_service.create_card_to_card_payment(session, owner_a, 100_000, None)
        span_p = topup.reserved_until - datetime.datetime.now(UTC)
        assert datetime.timedelta(minutes=6) < span_p < datetime.timedelta(minutes=8), span_p
    print("✅ test_each_setting_changes_its_own_consumer PASSED")


async def test_expiry_and_prune_jobs_use_per_shop_values() -> None:
    await reset_database()
    first = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    second = await seed_usable_shop(OTHER_OWNER_TG_ID, OTHER_SHOP_BOT_TG_ID)
    await _set_pref(first, order_confirmation_timeout_minutes=10, conversation_retention_days=5)
    await _set_pref(second, order_confirmation_timeout_minutes=600, conversation_retention_days=0)

    now = datetime.datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    async with session_scope() as session:
        customer_a = await customer_service.get_or_create_customer(session, first, CUSTOMER_TG_ID, "الف", None)
        customer_b = await customer_service.get_or_create_customer(session, second, CUSTOMER_TG_ID + 1, "ب", None)
        old_a = await order_service.create_order_awaiting_confirmation(
            session, first, customer_a.id, OrderType.ORDER, "خ", 100_000, None, None, None, None
        )
        old_b = await order_service.create_order_awaiting_confirmation(
            session, second, customer_b.id, OrderType.ORDER, "خ", 100_000, None, None, None, None
        )
        for order in (old_a, old_b):
            order.created_at = now - datetime.timedelta(minutes=30)
        await session.flush()
        old_ids = (old_a.id, old_b.id)

    async with session_scope() as session:
        admin_settings = await get_admin_settings(session)
        default = prefs.resolve(prefs.CONFIRMATION_TIMEOUT, None, admin_settings)
        timeouts = await prefs.confirmation_timeout_by_shop(session, admin_settings)
        assert timeouts[first] == 10 and timeouts[second] == 600, timeouts
        expired = await order_service.expire_stale_customer_confirmations(session, timeouts, default, now=now)

    assert [o.id for o in expired] == [old_ids[0]], "فقط فروشگاهِ با مهلتِ کوتاه‌تر لغو می‌شود"
    async with session_scope() as session:
        rows = list((await session.execute(select(OrderConsultation).where(OrderConsultation.id.in_(list(old_ids))))).scalars().all())
        by_id = {row.id: row for row in rows}
        assert by_id[old_ids[0]].status == OrderStatus.CANCELLED
        assert by_id[old_ids[1]].status == OrderStatus.AWAITING_CUSTOMER_CONFIRMATION

    # پاکسازیِ گفتگو: فروشگاهِ ۵ روزه پاک می‌شود، فروشگاهِ ۰ هرگز
    old = now - datetime.timedelta(days=30)
    async with session_scope() as session:
        customer_a_id = (await session.execute(select(Customer.id).where(Customer.shop_bot_id == first))).scalars().one()
        customer_b_id = (await session.execute(select(Customer.id).where(Customer.shop_bot_id == second))).scalars().one()
        session.add_all(
            [
                ConversationMessage(customer_id=customer_a_id, role="user", content="قدیمیِ الف", created_at=old),
                ConversationMessage(customer_id=customer_b_id, role="user", content="قدیمیِ ب", created_at=old),
            ]
        )
        await session.flush()

    async with session_scope() as session:
        admin_settings = await get_admin_settings(session)
        default_days = prefs.resolve(prefs.CONVERSATION_RETENTION, None, admin_settings)
        retention = await prefs.retention_by_shop(session, admin_settings)
        assert retention[first] == 5 and retention[second] == 0, retention
        deleted = await conversation_service.prune_old_messages_for_shops(session, retention, default_days, now=now)
    assert deleted == 1, deleted
    async with session_scope() as session:
        contents = [row.content for row in (await session.execute(select(ConversationMessage))).scalars().all()]
    assert "قدیمیِ الف" not in contents and "قدیمیِ ب" in contents, contents
    print("✅ test_expiry_and_prune_jobs_use_per_shop_values PASSED")


def test_knowledge_wiring_is_per_shop() -> None:
    """هر دو مصرف‌کننده‌یِ «حافظه‌ی کانالِ دانش» باید از ملغیِ per-shop بخوانند (نگهبانِ استاتیک)."""
    for path in ("app/bots/main_bot/handlers/panel.py", "app/bots/shop_bot/handlers/customer.py"):
        source = pathlib.Path(path).read_text(encoding="utf-8")
        assert "shop_prefs_service.KNOWLEDGE_ITEMS" in source, path
        assert "admin_settings.knowledge_items_limit" not in source, path
    print("✅ test_knowledge_wiring_is_per_shop PASSED")


# ============================================================================= ۵ — پنلِ فروشگاه‌دار
async def test_owner_settings_screen_and_menu(main_dp) -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    owner = Chat(main_dp, OWNER_TG_ID)

    async def stored():
        async with session_scope() as session:
            return (await session.execute(select(ShopBot).where(ShopBot.id == shop_bot_id))).scalar_one()

    await owner.say("⚙️ تنظیماتِ ربات فروشگاه")
    assert "sp_prefs_open" in _datas(owner.last_markup), _datas(owner.last_markup)
    await owner.tap("sp_prefs_open")
    assert "⏱ مهلت‌ها و حافظه" in owner.last_edit_text
    assert "رزروِ مبلغِ پرداخت: 60 دقیقه (پیش‌فرضِ سراسری)" in owner.last_edit_text, owner.last_edit_text
    data = _datas(owner.last_edit_markup)
    assert data[-1] == "sp_prefs_back", data
    assert data[:-1] == [f"sp_pref:{pref.key}" for pref in prefs.ALL_PREFS], data

    # کلیدِ دستکاری‌شده ⇒ پیامِ مودبانه
    await owner.tap("sp_pref:bogus_key")
    assert owner.last_toast["text"] == main_texts.SHOP_PREFS_STALE

    await owner.tap("sp_pref:order_reservation_minutes")
    assert "بازه‌یِ مجاز: 1 تا 10080 دقیقه" in owner.last_edit_text
    await owner.tap("sp_pref_set:order_reservation_minutes:15")
    assert (await stored()).order_reservation_minutes == 15
    assert "مقدارِ خودت: 15 دقیقه" in owner.last_edit_text

    # دابل‌تپ ⇒ همان مقدار
    await owner.tap("sp_pref_set:order_reservation_minutes:15")
    await owner.tap("sp_pref_set:order_reservation_minutes:15")
    assert (await stored()).order_reservation_minutes == 15

    # خارجِ بازه با کلیدِ دستی ⇒ رد (بدونِ خراب‌کردنِ مقدار)
    await owner.tap("sp_pref_set:order_reservation_minutes:99999")
    assert owner.last_toast["text"] == main_texts.SHOP_PREFS_STALE
    assert (await stored()).order_reservation_minutes == 15
    await owner.tap("sp_pref_set:order_reservation_minutes:abc")
    assert (await stored()).order_reservation_minutes == 15

    # مقدارِ دلخواه: ورودیِ نامعتبر ⇒ state می‌ماند، ورودیِ فارسی ⇒ ذخیره
    await owner.tap("sp_pref_custom:order_reservation_minutes")
    assert owner.last_text == main_texts.shop_pref_ask(prefs.ORDER_RESERVATION)
    for bad in ("0", "10081", "abc", "-4"):
        await owner.say(bad)
        assert owner.last_text == main_texts.shop_pref_invalid(prefs.ORDER_RESERVATION), bad
    assert (await stored()).order_reservation_minutes == 15
    await owner.say("۲۰")
    assert (await stored()).order_reservation_minutes == 20

    # بازگشت به پیش‌فرضِ سراسری
    assert "sp_pref_reset:order_reservation_minutes" in _datas(owner.last_markup)
    await owner.tap("sp_pref_reset:order_reservation_minutes")
    assert (await stored()).order_reservation_minutes is None
    assert "پیش‌فرضِ سراسری" in owner.last_edit_text
    assert "sp_pref_reset:order_reservation_minutes" not in _datas(owner.last_edit_markup), "دکمه‌یِ reset فقط وقتی تنظیم شده"

    await owner.tap("sp_pref_back")
    assert "رزروِ موجودیِ سفارش: 60 دقیقه (پیش‌فرضِ سراسری)" in owner.last_edit_text
    await owner.tap("sp_prefs_back")
    assert "مدتِ تجمیعِ پیام‌ها" in owner.last_edit_text

    # هیچ‌وقت نباید شناسه‌یِ سراسری/فنی در متنِ این صفحه باشد
    assert "AdminSettings" not in owner.last_edit_text
    print("✅ test_owner_settings_screen_and_menu PASSED")


async def test_consultation_sees_only_meaningful_prefs(main_dp) -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    async with session_scope() as session:
        row = (await session.execute(select(ShopBot).where(ShopBot.id == shop_bot_id))).scalar_one()
        row.tenant_mode = TenantMode.CONSULTATION
    owner = Chat(main_dp, OWNER_TG_ID)

    await owner.say("⚙️ تنظیماتِ ربات فروشگاه")
    await owner.tap("sp_prefs_open")
    data = _datas(owner.last_edit_markup)
    assert "sp_pref:conversation_retention_days" in data and "sp_pref:knowledge_items_limit" in data, data
    for key in ("payment_reservation_minutes", "order_reservation_minutes", "order_confirmation_timeout_minutes"):
        assert f"sp_pref:{key}" not in data, key
    assert "رزروِ موجودی" not in owner.last_edit_text and "حافظه‌ی کانالِ دانش" in owner.last_edit_text

    # تنظیمی که در مشاوره معنا ندارد ⇒ حتی با کالبکِ دستی هم ثبت نمی‌شود
    await owner.tap("sp_pref_set:order_reservation_minutes:15")
    assert owner.last_toast["text"] == main_texts.SHOP_PREFS_STALE
    assert (await _shop_bot(shop_bot_id)).order_reservation_minutes is None

    # پاکسازیِ گفتگو در مشاوره کار می‌کند (۰ = هیچ‌وقت پاک نشود)
    await owner.tap("sp_pref:conversation_retention_days")
    await owner.tap("sp_pref_set:conversation_retention_days:0")
    assert (await _shop_bot(shop_bot_id)).conversation_retention_days == 0
    assert "اثرِ فعلی: 0 روز" in owner.last_edit_text
    print("✅ test_consultation_sees_only_meaningful_prefs PASSED")


async def test_other_owner_cannot_touch_my_prefs(main_dp) -> None:
    await reset_database()
    mine = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    theirs = await seed_usable_shop(OTHER_OWNER_TG_ID, OTHER_SHOP_BOT_TG_ID)
    stranger = Chat(main_dp, OTHER_OWNER_TG_ID)

    await stranger.tap("sp_pref:knowledge_items_limit")
    await stranger.tap("sp_pref_set:knowledge_items_limit:3")
    assert (await _shop_bot(theirs)).knowledge_items_limit == 3, "فروشگاهِ خودش عوض شد"
    assert (await _shop_bot(mine)).knowledge_items_limit is None, "فروشگاهِ من دست‌نخورده ماند"
    print("✅ test_other_owner_cannot_touch_my_prefs PASSED")


async def main() -> None:
    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    test_bounds_come_from_code_only()
    test_resolve_prefers_shop_then_global()
    test_knowledge_wiring_is_per_shop()
    await test_admin_panel_no_longer_offers_them(main_dp)
    await test_each_setting_changes_its_own_consumer()
    await test_expiry_and_prune_jobs_use_per_shop_values()
    await test_owner_settings_screen_and_menu(main_dp)
    await test_consultation_sees_only_meaningful_prefs(main_dp)
    await test_other_owner_cannot_touch_my_prefs(main_dp)


if __name__ == "__main__":
    asyncio.run(main())
