"""
تست: P1-S1 (هویت) — ویزاردِ ثبت‌نام v2 (A1/A3/N1)، پروفایلِ یکپارچه (A2)، تغییرِ مود (A3)،
نمایشِ هویتِ متنی بدونِ آیدیِ عددی (H2) و دو شناسه‌یِ پشتیبانی (D1/D2).

اجرا: python3 tests_manual/test_identity_and_profile.py
(AUTH_MODE=test؛ مثلِ بقیه‌یِ تست‌ها دیسپچرها فقط یه‌بار ساخته می‌شن.)
"""
from __future__ import annotations

import ast
import asyncio
import pathlib
import sys
import types

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram.types import Contact, Update  # noqa: E402
from sqlalchemy import select  # noqa: E402

from harness import build_test_dispatchers, make_message_update, reset_database  # noqa: E402
from phase4_helpers import Chat, add_customer, add_order, callbacks  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot import texts  # noqa: E402
from app.database.models import (  # noqa: E402
    AdminSettings,
    AuditEventType,
    AuditLogEntry,
    Customer,
    OrderConsultation,
    OrderStatus,
    ShopBot,
    ShopOwner,
    TenantMode,
)
from app.database.session import session_scope  # noqa: E402
from app.services import customer_service, identity_service, shop_bot_service, shop_owner_service  # noqa: E402

ADMIN_TG_ID = 12345  # باید با ADMIN_TELEGRAM_IDS توی .env یکی باشه
# آیدی‌هایِ بزرگ: شماره‌یِ بذرِ seed_usable_shop از ۷ رقمِ آخرِ آیدی ساخته می‌شه؛ با آیدیِ کوچک، آیدی داخلِ شماره دیده می‌شد
OWNER_TG_ID = 7_100_000_001
OWNER_BOT_ID = 7_100_000_002
OTHER_TG_ID = 7_100_000_011
OTHER_BOT_ID = 7_100_000_012
NEW_USER_ID = 7_200_000_001
NEW_USER2_ID = 7_200_000_002
NEW_USER3_ID = 7_200_000_003


def _button_texts(markup) -> list[str]:
    return [b.text for row in markup.keyboard for b in row]


async def _owner_row(tg_id: int) -> ShopOwner:
    async with session_scope() as session:
        return (await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == tg_id))).scalar_one()


async def _audit_events(event: AuditEventType) -> list[AuditLogEntry]:
    async with session_scope() as session:
        return list((await session.execute(select(AuditLogEntry).where(AuditLogEntry.event_type == event))).scalars().all())


# =============================================================================
# A1 / A3 / N1 — ویزاردِ ثبت‌نام
# =============================================================================
async def test_registration_wizard_flow(main_dp) -> None:
    await reset_database()
    u = Chat(main_dp, NEW_USER_ID)

    await u.say("/start")
    assert callbacks(u.last_markup) == ["reg_mode:sales", "reg_mode:consultation", "reg_cancel"], "قدمِ ۰: انتخابِ مود"
    await u.tap("reg_mode:bogus")
    assert u.last_toast["text"] == texts.REG_STALE_BUTTON, "callbackِ جعلی نباید مود رو خراب کنه"

    await u.tap("reg_mode:sales")
    assert u.last_text == texts.ASK_FIRST_NAME and "بنویس" in texts.ASK_FIRST_NAME and "نامِ کوچک" in texts.ASK_FIRST_NAME, "N1"
    await u.say("a1b")
    assert u.last_text == texts.REG_NAME_BAD_CHARS
    await u.say("ع")
    assert u.last_text == texts.REG_NAME_BAD_LENGTH

    await u.say("علی رضا")  # نامِ دوکلمه‌ای: خودکار جدا نمی‌شه
    assert callbacks(u.last_markup) == ["reg_fn_keep", "reg_fn_split", "reg_fn_edit"]
    await u.tap("reg_fn_split")
    assert u.last_text == texts.ASK_PHONE, "نامِ خانوادگی از جدا کردن گرفته شد؛ قدمِ بعد موبایله"

    await u.say(texts.REG_BACK_BUTTON)
    assert u.last_text == texts.ASK_LAST_NAME + texts.reg_hint_previous("رضا"), "برگشت: مقدارِ قبلی حفظ و نشون داده می‌شه"
    await u.say("نوری")
    assert u.last_text == texts.ASK_PHONE

    await u.say("123")
    assert u.last_text == texts.INVALID_PHONE
    await u.say("۰۹۱۲۳۴۵۶۷۸۹")  # ارقامِ فارسی
    assert u.last_text == texts.ASK_EMAIL
    await u.say("bad")
    assert u.last_text == texts.INVALID_EMAIL
    await u.say("ali@example.com")
    assert "مرورِ نهایی" in u.last_text and "+989123456789" in u.last_text and "علی" in u.last_text
    assert "reg_confirm" in callbacks(u.last_markup) and "reg_edit:mode" in callbacks(u.last_markup)

    await u.tap("reg_edit:first_name")
    assert u.last_text == texts.ASK_FIRST_NAME + texts.reg_hint_previous("علی")
    await u.say("سینا")
    assert "مرورِ نهایی" in u.last_text and "سینا" in u.last_text

    await u.say("/start")  # وسطِ ویزارد: از همون‌جا ادامه، نه از صفر
    assert texts.REG_RESUME in [m["text"] for m in u.sent[-2:]] and "مرورِ نهایی" in u.last_text

    await u.say(texts.REG_CANCEL_BUTTON)
    assert u.last_text == texts.REG_CANCEL_ASK and callbacks(u.last_markup) == ["reg_cancel_yes", "reg_cancel_no"]
    await u.tap("reg_cancel_no")
    assert "مرورِ نهایی" in u.last_text

    assert (await _owner_row(NEW_USER_ID)).registration_completed is False, "قبل از تایید چیزی نهایی ذخیره نمی‌شه"
    await u.tap("reg_confirm")
    owner = await _owner_row(NEW_USER_ID)
    assert owner.registration_completed is True
    assert (owner.first_name, owner.last_name, owner.phone_number, owner.email) == ("سینا", "نوری", "09123456789", "ali@example.com")
    assert owner.business_mode == "sales" and owner.phone_verified is True and owner.email_verified is True

    await u.tap("reg_confirm")  # دابل‌تپ/دکمه‌یِ کهنه
    assert u.last_toast["text"] == texts.REG_STALE_BUTTON, "دکمه‌یِ کهنه پیامِ مودبانه می‌ده"
    async with session_scope() as session:
        count = len((await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == NEW_USER_ID))).scalars().all())
    assert count == 1

    print("✅ test_registration_wizard_flow PASSED")


async def test_registration_duplicates_cancel_and_contact(main_dp) -> None:
    await reset_database()
    async with session_scope() as session:
        owner = await shop_owner_service.get_or_create_shop_owner(session, NEW_USER_ID)
        await shop_owner_service.complete_registration(session, owner, "قبلی", "کاربر", "09123456789", "taken@example.com", True, True)

    u2 = Chat(main_dp, NEW_USER2_ID)
    await u2.say("/start")
    await u2.tap("reg_mode:consultation")
    await u2.say("نیما")
    await u2.say("کاظمی")
    await u2.say("+98 912 345 6789")  # همون شماره با فرمتِ دیگه
    assert u2.last_text == texts.REG_PHONE_TAKEN, "موبایلِ تکراری (با هر فرمتی) رد می‌شه"

    # مخاطبِ دیگران (user_id متفاوت) پذیرفته نمی‌شه
    upd = make_message_update(900, text=None, user_id=NEW_USER2_ID, contact_phone="+989120000009")
    foreign = upd.message.model_copy(update={"contact": Contact.model_construct(phone_number="+989120000009", first_name="x", user_id=NEW_USER2_ID + 5)})
    await main_dp.feed_update(u2.bot, Update.model_construct(update_id=900, message=foreign))
    assert u2.last_text == texts.REG_PHONE_NOT_YOURS

    # مخاطبِ خودش پذیرفته می‌شه
    await main_dp.feed_update(u2.bot, make_message_update(901, text=None, user_id=NEW_USER2_ID, contact_phone="+989120000009"))
    assert u2.last_text == texts.ASK_EMAIL
    await u2.say("TAKEN@example.com")
    assert u2.last_text == texts.REG_EMAIL_TAKEN, "ایمیلِ تکراری (بدونِ حساسیت به حروف) رد می‌شه"

    # انصرافِ قطعی: چیزی نهایی نمی‌شه و /start دوباره از قدمِ ۰ شروع می‌کنه
    u3 = Chat(main_dp, NEW_USER3_ID)
    await u3.say("/start")
    await u3.say(texts.REG_CANCEL_BUTTON)
    await u3.tap("reg_cancel_yes")
    assert u3.last_text == texts.REG_CANCELLED
    assert (await _owner_row(NEW_USER3_ID)).registration_completed is False
    await u3.say("/start")
    assert u3.last_text == texts.REG_ASK_MODE

    print("✅ test_registration_duplicates_cancel_and_contact PASSED")


# =============================================================================
# A2 — پروفایلِ یکپارچه + H2 (بدونِ آیدیِ عددی)
# =============================================================================
async def test_profile_card_edit_and_audit(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, OWNER_BOT_ID)
    await seed_usable_shop(OTHER_TG_ID, OTHER_BOT_ID)
    owner = Chat(main_dp, OWNER_TG_ID)

    await owner.say("👤 پروفایل من")
    # ایمیلِ بذرِ seed_usable_shop از روی آیدی ساخته می‌شه (دیتایِ تست، نه نشتِ کد)؛ پس خطِ ایمیل کنار گذاشته می‌شه
    visible = "\n".join(line for line in owner.last_text.split("\n") if not line.startswith("ایمیل"))
    assert str(OWNER_TG_ID) not in visible and "آیدی" not in visible, "H2: آیدیِ عددی نباید در پروفایل باشه"
    assert "فروشنده فعال" in owner.last_text and "+98912" in owner.last_text
    assert callbacks(owner.last_markup) == [
        "pf_edit:first_name", "pf_edit:last_name", "pf_edit:phone", "pf_edit:email", "pf_mode", "pf_support",
    ]
    for legacy in ("✏️ ویرایش اطلاعات", "🔀 نوعِ کسب‌وکار"):  # دکمه‌یِ کهنه → همون پروفایل
        await owner.say(legacy)
        assert owner.last_text.startswith("👤 پروفایل من")

    await owner.tap("pf_edit:first_name")
    assert owner.last_text == texts.profile_ask("first_name")
    await owner.say("x1")
    assert owner.last_text == texts.REG_NAME_BAD_CHARS
    await owner.say("نیما")
    assert (await _owner_row(OWNER_TG_ID)).first_name == "نیما"
    assert texts.PROFILE_UPDATED in [m["text"] for m in owner.sent[-2:]]

    await owner.tap("pf_edit:phone")
    await owner.say("09120000011")  # موبایلِ فروشگاه‌دارِ دیگه
    assert owner.last_text == texts.REG_PHONE_TAKEN
    await owner.say("۰۹۳۵۱۱۱۲۲۳۳")
    stored = await _owner_row(OWNER_TG_ID)
    assert stored.phone_number == "09351112233" and stored.phone_verified is True

    await owner.tap("pf_edit:email")
    await owner.say("new.mail@example.com")
    assert (await _owner_row(OWNER_TG_ID)).email == "new.mail@example.com"

    events = await _audit_events(AuditEventType.OWNER_PROFILE_UPDATED)
    assert len(events) == 3, "هر تغییر یک رکوردِ ممیزی"
    joined = " ".join(e.details or "" for e in events)
    assert "09351112233" not in joined and "new.mail@example.com" not in joined, "مقدارِ کاملِ موبایل/ایمیل در ممیزی ثبت نمی‌شه"
    assert "+98935***33" in joined

    await owner.tap("pf_edit:bogus")
    assert owner.last_toast["text"] == texts.PROFILE_STALE

    # پشتیبانیِ پلتفرم (D2): تنظیم‌نشده ← پیامِ مودبانه؛ تنظیم‌شده ← شناسه‌ها
    await owner.tap("pf_support")
    assert owner.last_text == texts.PROFILE_SUPPORT_NOT_SET
    async with session_scope() as session:
        row = (await session.execute(select(AdminSettings))).scalars().first()
        row.platform_support_username = "my_support"
        row.platform_support_phone = "+989125550000"
    await owner.tap("pf_support")
    assert "@my_support" in owner.last_text and "+989125550000" in owner.last_text

    print("✅ test_profile_card_edit_and_audit PASSED")


# =============================================================================
# A3 — تغییرِ مود
# =============================================================================
async def test_business_mode_change_flow(main_dp) -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, OWNER_BOT_ID)
    owner = Chat(main_dp, OWNER_TG_ID)

    await owner.tap("pf_mode")
    assert "تغییرش بدی" in owner.edits[-1]["text"], "هشدارِ پیامد"
    await owner.tap("tenant_mode_ask:consultation")
    assert "آخرین تایید" in owner.edits[-1]["text"], "تاییدِ دوباره قبلِ ثبت"
    await owner.tap("set_tenant_mode:bogus")
    assert owner.last_toast["text"] == texts.PROFILE_STALE

    await owner.tap("set_tenant_mode:consultation")  # callbackِ قدیمی همچنان نهایی‌کننده است
    stored = await _owner_row(OWNER_TG_ID)
    assert stored.business_mode == "consultation"
    async with session_scope() as session:
        assert (await session.execute(select(ShopBot.tenant_mode).where(ShopBot.id == shop_bot_id))).scalar_one() == TenantMode.CONSULTATION
    assert "🗂 خدمات و بسته‌ها" in _button_texts(owner.last_markup), "منوی تازه با مودِ جدید ساخته می‌شه"
    assert len(await _audit_events(AuditEventType.OWNER_BUSINESS_MODE_CHANGED)) == 1

    # سفارشِ باز ← تغییر مسدود (هم از مسیرِ منو، هم callbackِ مستقیم)
    customer_id = await add_customer(shop_bot_id, 7_300_000_001, first_name="مشتری")
    order_id = await add_order(shop_bot_id, customer_id, status=OrderStatus.PENDING)
    await owner.tap("pf_mode")
    assert owner.last_toast["text"] == texts.TENANT_MODE_BLOCKED and owner.last_toast["show_alert"]
    await owner.tap("set_tenant_mode:sales")
    assert owner.last_toast["text"] == texts.TENANT_MODE_BLOCKED
    assert (await _owner_row(OWNER_TG_ID)).business_mode == "consultation", "هیچ تغییری نباید اعمال بشه"

    async with session_scope() as session:
        order = (await session.execute(select(OrderConsultation).where(OrderConsultation.id == order_id))).scalar_one()
        order.status = OrderStatus.COMPLETED
    await owner.tap("set_tenant_mode:sales")
    assert (await _owner_row(OWNER_TG_ID)).business_mode == "sales", "بعد از بسته‌شدنِ سفارش مجازه"

    # مالکِ بدونِ رباتِ فروشگاهی هم می‌تونه مود رو عوض کنه؛ رباتِ بعدی با همون مود ساخته می‌شه
    async with session_scope() as session:
        fresh = await shop_owner_service.get_or_create_shop_owner(session, OTHER_TG_ID)
        await shop_owner_service.complete_registration(session, fresh, "بی", "ربات", "09127776655", "nb@example.com", True, True)
    other = Chat(main_dp, OTHER_TG_ID)
    await other.tap("set_tenant_mode:consultation")
    assert (await _owner_row(OTHER_TG_ID)).business_mode == "consultation"
    async with session_scope() as session:
        fresh = (await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == OTHER_TG_ID))).scalar_one()
        bot = await shop_bot_service.upsert_shop_bot(session, fresh, "fake-token", OTHER_BOT_ID, "other_shop_bot")
        assert bot.tenant_mode == TenantMode.CONSULTATION, "رباتِ تازه مودِ فروشگاه‌دار رو می‌گیره (نه پیش‌فرضِ ثابت)"

    stranger = Chat(main_dp, 7_300_000_999)  # ثبت‌نام‌نکرده
    await stranger.tap("set_tenant_mode:consultation")
    assert stranger.last_toast["text"] == texts.PROFILE_STALE

    print("✅ test_business_mode_change_flow PASSED")


# =============================================================================
# H2 — نمایشِ هویت
# =============================================================================
async def test_identity_display_and_refresh(main_dp) -> None:
    S = types.SimpleNamespace
    owner = S(first_name="علی", last_name="رضایی", username="ali_r", phone_number="09121234567", telegram_id=7_555_000_111)
    nameless = S(first_name=None, last_name=None, username=None, phone_number=None, telegram_id=7_555_000_222)
    assert identity_service.display_user(owner) == "علی رضایی (@ali_r)"
    assert identity_service.display_user(owner, "full") == "علی رضایی (@ali_r) · +989121234567"
    assert identity_service.display_user(S(first_name="سارا", last_name=None, username=None, phone_number="+989351112233")) == "سارا · +989351112233"
    assert identity_service.display_user(S(first_name="رضا", last_name="", username=None, phone_number=None)) == "رضا (بدونِ یوزرنیم)"
    assert identity_service.display_user(nameless) == "کاربرِ بی‌نام"

    order = S(type="order", summary="دو عدد قهوه", estimated_value_toman=None, customer_phone=None, customer_address=None)
    for rendered in (
        texts.order_detected_notification(order, owner),
        texts.cart_order_notification(owner, [], [], 1000),
        texts.admin_shop_owner_detail(owner, None, 0),
        texts.admin_new_payment_notification(S(duration_months=1, final_amount=1000), owner),
        texts.admin_owner_list_item_label(nameless, None),
    ):
        assert "7555000111" not in rendered and "7555000222" not in rendered, f"آیدیِ عددی نشت کرده: {rendered!r}"
    assert "علی رضایی (@ali_r)" in texts.cart_order_notification(owner, [], [], 1000)
    assert "کاربرِ بی‌نام" in texts.admin_owner_list_item_label(nameless, None)

    # تازه‌سازیِ یوزرنیم (فقط وقتی عوض شده) از راهِ میدل‌ور
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, OWNER_BOT_ID)
    chat = Chat(main_dp, OWNER_TG_ID)
    for n, username, expected in ((1, "fresh_name", "fresh_name"), (2, "fresh_name", "fresh_name"), (3, None, None)):
        await main_dp.feed_update(chat.bot, make_message_update(500 + n, text="👤 پروفایل من", user_id=OWNER_TG_ID, username=username))
        assert (await _owner_row(OWNER_TG_ID)).username == expected, f"گام {n}"
    assert "یوزرنیم: —" in chat.last_text

    # مشتری: نامِ‌خانوادگی ذخیره می‌شه و فقط با مقدارِ تازه عوض می‌شه
    shop_bot_id = await seed_usable_shop(OTHER_TG_ID, OTHER_BOT_ID)
    async with session_scope() as session:
        c = await customer_service.get_or_create_customer(session, shop_bot_id, 7_400_000_001, "سارا", "sara_u", last_name="احمدی")
        assert (c.first_name, c.last_name, c.username) == ("سارا", "احمدی", "sara_u")
        c = await customer_service.get_or_create_customer(session, shop_bot_id, 7_400_000_001, "سارا", None)
        assert c.last_name == "احمدی" and c.username == "sara_u", "None یعنی «اطلاعی نیست»، پاک‌کننده نیست"
        assert c.phone_number is None and c.phone_via_contact is False
        assert identity_service.display_user(c) == "سارا احمدی (@sara_u)"

    print("✅ test_identity_display_and_refresh PASSED")


async def test_static_no_numeric_ids_in_ui_texts() -> None:
    """نگهبانِ استاتیک: هیچ متن/دکمه‌یِ کاربرمحوری نباید telegram_id رو مستقیم چاپ کنه (صفحه‌هایِ فنی/ممیزی مستثنا)."""
    technical_allowed = {"audit_log_entry_line", "admin_role_detail_text"}
    leaks: list[str] = []
    for path in ("app/bots/main_bot/texts.py", "app/bots/main_bot/keyboards.py", "app/bots/shop_bot/texts.py", "app/bots/shop_bot/keyboards.py"):
        tree = ast.parse(pathlib.Path(path).read_text(encoding="utf-8"))
        for fn in (n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))):
            if fn.name in technical_allowed:
                continue
            for node in ast.walk(fn):
                values = []
                if isinstance(node, ast.JoinedStr):
                    values = [v.value for v in node.values if isinstance(v, ast.FormattedValue)]
                elif isinstance(node, ast.Call) and getattr(node.func, "id", "") == "str" and node.args:
                    values = [node.args[0]]
                for value in values:
                    if isinstance(value, ast.Attribute) and value.attr in ("telegram_id", "granted_by_telegram_id", "actor_telegram_id"):
                        leaks.append(f"{path}:{fn.name}:{node.lineno}")
                    if isinstance(value, ast.Name) and value.id in ("telegram_id", "tg_id"):
                        leaks.append(f"{path}:{fn.name}:{node.lineno}")
    assert not leaks, f"آیدیِ عددی در متن/دکمه: {leaks}"

    # پشتیبانیِ پلتفرم فقط برایِ فروشگاه‌دار است: کدِ رباتِ مشتری هرگز بهش دست نمی‌زنه (D2)
    for p in pathlib.Path("app/bots/shop_bot").rglob("*.py"):
        assert "platform_support" not in p.read_text(encoding="utf-8"), f"{p}: شناسه‌یِ پلتفرم نباید به مشتری برسه"

    print("✅ test_static_no_numeric_ids_in_ui_texts PASSED")


# =============================================================================
# D1 / D2 — پشتیبانی
# =============================================================================
async def test_support_settings_admin_and_owner(main_dp) -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, OWNER_BOT_ID)

    # --- ادمین: سه فیلدِ پشتیبانیِ پلتفرم در «🔑 تنظیمات کلیدها»
    admin = Chat(main_dp, ADMIN_TG_ID)

    async def platform(field: str):
        async with session_scope() as session:
            return getattr((await session.execute(select(AdminSettings))).scalars().first(), field)

    await admin.tap("admin_setting_edit:platform_support_username")
    await admin.say("ab")
    assert admin.last_text == texts.INVALID_SUPPORT_USERNAME
    await admin.say("@My_Support")
    assert await platform("platform_support_username") == "My_Support"
    assert any("📞 پشتیبانیِ پلتفرم" in b.text for row in admin.last_markup.inline_keyboard for b in row), "منویِ تنظیمات دکمه‌یِ پشتیبانی داره"
    await admin.tap("admin_setting_edit:platform_support_phone")
    await admin.say("123")
    assert admin.last_text == texts.INVALID_SUPPORT_PHONE
    await admin.say("09125550000")
    assert await platform("platform_support_phone") == "+989125550000"
    await admin.tap("admin_setting_edit:platform_support_text")
    await admin.say("پاسخگو: ۹ تا ۱۷")
    assert await platform("platform_support_text") == "پاسخگو: ۹ تا ۱۷"
    await admin.tap("admin_setting_edit:platform_support_phone")
    await admin.say("خالی")
    assert await platform("platform_support_phone") is None

    async with session_scope() as session:
        closed = texts.registration_closed_text((await session.execute(select(AdminSettings))).scalars().first())
    assert "@My_Support" in closed and closed.startswith(texts.REGISTRATION_CLOSED)

    # --- فروشگاه‌دار: «⚙️ تنظیماتِ ربات فروشگاه ← 📞 پشتیبانیِ مشتری‌ها»
    owner = Chat(main_dp, OWNER_TG_ID)

    async def shop() -> ShopBot:
        async with session_scope() as session:
            return (await session.execute(select(ShopBot).where(ShopBot.id == shop_bot_id))).scalar_one()

    await owner.say("⚙️ تنظیماتِ ربات فروشگاه")
    assert "sp_open" in callbacks(owner.last_markup)
    await owner.tap("sp_open")
    assert "پشتیبانیِ مشتری‌ها" in owner.edits[-1]["text"] and "وضعیت: ⛔️ خاموش" in owner.edits[-1]["text"]
    await owner.tap("sp_toggle")
    assert owner.last_toast["text"] == texts.SUPPORT_NEEDS_CONTACT, "بدونِ راهِ تماس فعال نمی‌شه"
    await owner.tap("sp_edit:bogus")
    assert owner.last_toast["text"] == texts.SUPPORT_SETTINGS_STALE
    await owner.tap("sp_edit:username")
    assert owner.last_text == texts.SUPPORT_ASK["username"]
    await owner.say("bad name")
    assert owner.last_text == texts.INVALID_SUPPORT_USERNAME
    await owner.say("@shop_help")
    # B7 (تغییرِ عمدی): ثبتِ هر راهِ تماس ⇒ پشتیبانی خودکار فعال است و دکمه‌اش به مشتری نشان داده می‌شود
    # (قبلاً فروشگاه‌دار باید جداگانه «✅ فعال‌کردن» را می‌زد و چون نمی‌دانست، مشتری هیچ‌وقت دکمه را نمی‌دید).
    bot = await shop()
    assert bot.support_contact_username == "shop_help" and bot.support_enabled is True and bot.support_mode == "direct"
    assert owner.last_text.startswith("📞 پشتیبانیِ مشتری‌ها")
    # خاموش/روشنِ دستی همچنان کار می‌کند
    await owner.tap("sp_toggle")
    assert (await shop()).support_enabled is False
    await owner.tap("sp_toggle")
    assert (await shop()).support_enabled is True
    await owner.tap("sp_edit:phone")
    await owner.say("09123334444")
    assert (await shop()).support_contact_phone == "+989123334444"
    await owner.tap("sp_edit:username")
    await owner.say("خالی")
    assert (await shop()).support_enabled is True, "هنوز تلفن هست"
    await owner.tap("sp_edit:phone")
    await owner.say("خالی")
    assert (await shop()).support_enabled is False, "بدونِ هیچ راهِ تماسی خودکار خاموش می‌شه"
    await owner.tap("sp_back")
    assert "مدتِ تجمیعِ پیام‌ها" in owner.edits[-1]["text"], "برگشت به صفحه‌یِ تنظیماتِ ربات"

    print("✅ test_support_settings_admin_and_owner PASSED")


async def test_new_columns_defaults(main_dp) -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, OWNER_BOT_ID)
    async with session_scope() as session:
        owner = (await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == OWNER_TG_ID))).scalar_one()
        bot = (await session.execute(select(ShopBot).where(ShopBot.id == shop_bot_id))).scalar_one()
        cid = await add_customer(shop_bot_id, 7_400_000_009)
        customer = (await session.execute(select(Customer).where(Customer.id == cid))).scalar_one()
        assert owner.business_mode == "sales" and owner.username is None
        assert (bot.support_enabled, bot.support_mode, bot.support_contact_username) == (False, "direct", None)
        assert (customer.last_name, customer.phone_number, customer.phone_via_contact) == (None, None, False)
        row = (await session.execute(select(AdminSettings))).scalars().first()
        assert (row.platform_support_username, row.platform_support_phone, row.platform_support_text) == (None, None, None)
    print("✅ test_new_columns_defaults PASSED")


async def main() -> None:
    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    await test_registration_wizard_flow(main_dp)
    await test_registration_duplicates_cancel_and_contact(main_dp)
    await test_profile_card_edit_and_audit(main_dp)
    await test_business_mode_change_flow(main_dp)
    await test_identity_display_and_refresh(main_dp)
    await test_static_no_numeric_ids_in_ui_texts()
    await test_support_settings_admin_and_owner(main_dp)
    await test_new_columns_defaults(main_dp)


if __name__ == "__main__":
    asyncio.run(main())
