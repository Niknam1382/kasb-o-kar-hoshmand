"""
تست: P24 — دکمه‌هایِ مرده، دامنهٔ پرداختِ ادمین، سقفِ ورودی‌ها و «آخرینِ زنجیرِ نجات»

باگ‌هایی که همین فایل می‌بندد (همه از گزارشِ کاربر + بازرسیِ کد، نه حدس):

۱. «⬅️ بازگشت به پنل» (`main_menu`) در پنج کیبورد ساخته می‌شد و هیچ هندلری نداشت ⇒ هر صفحهٔ
   خالیِ پنل به بن‌بست می‌خورد (گزارشِ کاربر: «دکمه ... چیزی نداره که کار کنه»).
۲. صفحهٔ «⏰ ارسال‌هایِ زمان‌بندی‌شده»: حالتِ خالی هیچ دکمه‌ای نداشت، حالتِ پر فقط لغو داشت و
   برچسبِ لغو شناسهٔ داخلیِ دیتابیس را نشان می‌داد.
۳. تایید/ردِ پرداختِ کارت‌به‌کارت هیچ دامنه‌ای نداشت ⇒ ادمینِ عملیاتیِ دامنه‌دار با حدس‌زدنِ
   payment_id می‌توانست شارژِ کیف‌پولِ فروشگاهِ بیرونِ دامنه را تایید کند (پولِ واقعی).
۴. ورودی‌هایِ پنلِ ادمین: سقفِ اعدادِ پولی/درصدی و اعتبارِ آدرسِ سرویسِ هوش مصنوعی (SSRF/نشتِ کلید).
۵. هندلرِ سراسریِ خطا: callback_data دستکاری‌شده (`…:abc`) نباید سکوت بسازد.
۶. درِوازهٔ «حالتِ تعمیر» رویِ دکمه‌هایِ رباتِ فروشگاه و حذفِ دکمه‌هایِ مردهٔ رباتِ مشاوره‌ای.

اجرا: python3 tests_manual/run_one.py test_p24_dead_buttons_and_scope.py
"""
from __future__ import annotations

import asyncio
import datetime
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests_manual"))

from sqlalchemy import delete as sa_delete  # noqa: E402
from sqlalchemy import select  # noqa: E402

from harness import build_test_dispatchers, reset_database  # noqa: E402
from phase4_helpers import Chat  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402
from test_orders_w2 import _Env, _seed  # noqa: E402

from app.bots.common.error_handler import CALLBACK_FAILED_TOAST  # noqa: E402
from app.bots.main_bot import keyboards as main_keyboards  # noqa: E402
from app.bots.main_bot import texts as main_texts  # noqa: E402
from app.bots.main_bot.handlers import admin as admin_handlers  # noqa: E402
from app.bots.shop_bot import keyboards as shop_keyboards  # noqa: E402
from app.bots.shop_bot import texts as shop_texts  # noqa: E402
from app.database.models import (  # noqa: E402
    Payment,
    PaymentPurpose,
    PaymentStatus,
    ScheduledBroadcast,
    ShopBot,
    ShopOwner,
    TenantMode,
)
from app.database.session import session_scope  # noqa: E402
from app.services import (  # noqa: E402
    admin_role_service,
    customer_service,
    payment_service,
    scheduled_broadcast_service,
)

from app.services.admin_settings_service import get_admin_settings  # noqa: E402

ADMIN_TG_ID = 12345
OPERATOR_TG_ID = 999_941
OWNER_TG_ID = 999_942
OWNER_BOT_TG_ID = 999_943
OUTSIDE_OWNER_TG_ID = 999_944
OUTSIDE_BOT_TG_ID = 999_945


def _labels(markup) -> list[str]:
    if markup is None:
        return []
    rows = getattr(markup, "keyboard", None) or getattr(markup, "inline_keyboard", None) or []
    return [btn.text for row in rows for btn in row]


async def _pending_card_payment(owner_tg_id: int) -> int:
    async with session_scope() as session:
        owner = (await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == owner_tg_id))).scalar_one()
        payment = await payment_service.create_card_to_card_payment(
            session, owner, 200_000, None, purpose=PaymentPurpose.WALLET_TOPUP
        )
        return payment.id


async def _payment_status(session, payment_id: int) -> Payment:
    return (await session.execute(select(Payment).where(Payment.id == payment_id))).scalar_one()


async def _wallet_balance(owner_tg_id: int) -> int:
    async with session_scope() as session:
        owner = (await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == owner_tg_id))).scalar_one()
        return owner.wallet_balance_toman


# ============================================================================= ۱ — بازگشت به پنل
async def test_main_menu_button_returns_to_the_panel(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, OWNER_BOT_TG_ID)
    chat = Chat(main_dp, OWNER_TG_ID)

    await chat.say("🧾 تاریخچه‌ی پرداخت")  # صفحه‌ای که هیچ ورودی دیگری ندارد
    assert any("بازگشت" in label for label in _labels(chat.last_markup)), _labels(chat.last_markup)

    await chat.tap("main_menu")
    assert getattr(chat.last_markup, "keyboard", None), "کیبوردِ پنل برنگشت"
    assert "💰 کیف‌پول" in " ".join(_labels(chat.last_markup)), _labels(chat.last_markup)

    admin = Chat(main_dp, ADMIN_TG_ID)
    await admin.tap("main_menu")
    assert "📊 آمار سراسری" in " ".join(_labels(admin.last_markup)), _labels(admin.last_markup)
    print("✅ test_main_menu_button_returns_to_the_panel PASSED")


# ============================================================================= ۲ — صفحهٔ زمان‌بندی‌ها
async def test_scheduled_screen_is_actionable(main_dp) -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, OWNER_BOT_TG_ID)
    async with session_scope() as session:
        await customer_service.get_or_create_customer(session, shop_bot_id, 777_941, "مشتری", None)
    chat = Chat(main_dp, OWNER_TG_ID)

    await chat.say(main_texts.SCHEDULED_LIST_BUTTON)
    assert chat.last_text == main_texts.SCHEDULE_EMPTY, chat.last_text
    labels = _labels(chat.last_markup)
    assert main_texts.SCHEDULE_NEW_BUTTON in labels, f"صفحهٔ خالی باید راهِ ادامه داشته باشد: {labels}"
    assert any("بازگشت" in label for label in labels), labels

    await chat.tap("sched_new")
    assert chat.last_text == main_texts.ASK_CUSTOMER_BROADCAST_MESSAGE, chat.last_text

    # بدونِ هیچ مشتری‌ای «زمان‌بندیِ تازه» پیامک نمی‌خواهد؛ توستِ دلیل را می‌دهد
    async with session_scope() as session:
        from app.database.models import Customer

        await session.execute(sa_delete(Customer).where(Customer.shop_bot_id == shop_bot_id))
        await session.commit()
    second = Chat(main_dp, OWNER_TG_ID)
    await second.say(main_texts.SCHEDULED_LIST_BUTTON)
    await second.tap("sched_new")
    assert second.last_toast["text"] == main_texts.SCHEDULE_NO_CUSTOMERS, second.last_toast
    print("✅ test_scheduled_screen_is_actionable PASSED")


async def test_scheduled_list_hides_internal_ids(main_dp) -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, OWNER_BOT_TG_ID)
    async with session_scope() as session:
        shop_bot = await session.get(ShopBot, shop_bot_id)
        now = datetime.datetime.now(datetime.timezone.utc)
        for offset, text in ((1, "سلام ۱"), (2, "سلام ۲")):
            session.add(
                ScheduledBroadcast(
                    shop_bot_id=shop_bot_id,
                    owner_id=shop_bot.shop_owner_id,
                    text=text,
                    scheduled_at=now + datetime.timedelta(days=offset),
                    status=scheduled_broadcast_service.PENDING,
                )
            )
        await session.flush()
        ids = [row.id for row in await scheduled_broadcast_service.upcoming(session, shop_bot_id)]
    assert len(ids) == 2, ids

    chat = Chat(main_dp, OWNER_TG_ID)
    await chat.say(main_texts.SCHEDULED_LIST_BUTTON)
    labels = _labels(chat.last_markup)
    assert main_texts.schedule_cancel_button_label(1) in labels, labels
    assert main_texts.schedule_cancel_button_label(2) in labels, labels
    shown = " ".join(labels) + " " + chat.last_text
    for internal_id in ids:
        assert str(internal_id) not in shown, f"شناسهٔ داخلیِ {internal_id} در متنِ کاربر نیاید"

    await chat.tap(f"sched_cancel:{ids[0]}")
    assert chat.last_toast["text"] == main_texts.SCHEDULE_CANCELLED, chat.last_toast
    async with session_scope() as session:
        left = await scheduled_broadcast_service.upcoming(session, shop_bot_id)
        assert [row.id for row in left] == [ids[1]], left
    print("✅ test_scheduled_list_hides_internal_ids PASSED")


# ============================================================================= ۳ — دامنهٔ پرداخت
async def test_operator_cannot_approve_payment_outside_scope(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, OWNER_BOT_TG_ID)
    await seed_usable_shop(OUTSIDE_OWNER_TG_ID, OUTSIDE_BOT_TG_ID)
    payment_id = await _pending_card_payment(OUTSIDE_OWNER_TG_ID)

    async with session_scope() as session:
        await admin_role_service.grant_operator(session, OPERATOR_TG_ID, granted_by_telegram_id=ADMIN_TG_ID)
        role = await admin_role_service.get_by_telegram_id(session, OPERATOR_TG_ID)
        inside = (await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == OWNER_TG_ID))).scalar_one()
        await admin_role_service.set_scope(session, role, [inside.id])

    operator = Chat(main_dp, OPERATOR_TG_ID)
    before = await _wallet_balance(OUTSIDE_OWNER_TG_ID)
    await operator.tap(f"admin_approve_payment:{payment_id}")
    assert operator.last_toast["text"] == main_texts.ADMIN_OWNER_OUT_OF_SCOPE_TOAST, operator.last_toast
    async with session_scope() as session:
        payment = await _payment_status(session, payment_id)
        assert payment.status == PaymentStatus.PENDING, "پرداختِ بیرونِ دامنه تایید نشد"
    assert await _wallet_balance(OUTSIDE_OWNER_TG_ID) == before, "هیچ اعتباری اضافه نشد"

    await operator.tap("admin_approve_payment:abc")
    assert operator.last_toast["text"], "کال‌بکِ بی‌جواب ماند"
    print("✅ test_operator_cannot_approve_payment_outside_scope PASSED")


# ============================================================================= ۴ — سقفِ ورودی و آدرس
async def _set_admin_field(admin: Chat, field: str, value: str) -> None:
    await admin.say("🔑 تنظیمات کلیدها")
    await admin.tap(f"admin_setting_edit:{field}")
    await admin.say(value)


async def test_setting_bounds_and_url_are_enforced(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, OWNER_BOT_TG_ID)
    admin = Chat(main_dp, ADMIN_TG_ID)

    await _set_admin_field(admin, "referral_reward_value", "5000")
    assert admin.last_text == main_texts.ADMIN_INVALID_NUMBER, admin.last_text
    assert await _admin_referral() != 5000, "ورودیِ خارجِ بازه ذخیره نشود"

    await _set_admin_field(admin, "referral_reward_value", "10")
    assert main_texts.ADMIN_SETTING_SAVED in [m["text"] for m in admin.sent][-3:], admin.sent[-3:]
    assert await _admin_referral() == 10

    original_base_url = await _admin_base_url()
    for bad in ("http://api.example.test/v1", "https://127.0.0.1:11434/v1", "https://169.254.169.254/latest"):
        await _set_admin_field(admin, "ai_base_url", bad)
        assert admin.last_text == main_texts.ADMIN_INVALID_AI_URL, (bad, admin.last_text)
    assert await _admin_base_url() == original_base_url, "هیچ‌کدام از آدرس‌هایِ داخلی/ناامن ذخیره نشد"

    await _set_admin_field(admin, "ai_base_url", "https://api.example.test/v1")
    assert (await _admin_base_url()) == "https://api.example.test/v1"
    print("✅ test_setting_bounds_and_url_are_enforced PASSED")


async def _admin_referral() -> int:
    async with session_scope() as session:
        from app.services.admin_settings_service import get_admin_settings

        return (await get_admin_settings(session)).referral_reward_value


async def _admin_base_url() -> str | None:
    async with session_scope() as session:
        from app.services.admin_settings_service import get_admin_settings

        return (await get_admin_settings(session)).ai_base_url


# ============================================================================= ۵ — رمزنگاریِ رازِ پرداخت
async def test_platform_card_number_is_encrypted_at_rest(main_dp) -> None:
    """«ENCRYPTION_KEY به شمارهٔ کارتِ پلتفرم هم می‌خورد» باید راست باشد، نه فقط در docs."""
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, OWNER_BOT_TG_ID)
    card = "6037991105634800"
    admin = Chat(main_dp, ADMIN_TG_ID)
    await _set_admin_field(admin, "platform_card_number", card)

    from sqlalchemy import text as sa_text

    async with session_scope() as session:
        stored = (await session.execute(sa_text("select platform_card_number from admin_settings"))).scalar_one()
    assert stored and card not in stored, f"در ستون باید CipherText باشد: {stored[:12]}…"
    async with session_scope() as session:
        assert (await get_admin_settings(session)).platform_card_number == card, "ORM باید شفاف بخواند"
    print("✅ test_platform_card_number_is_encrypted_at_rest PASSED")


# ============================================================================= ۶ — آخرینِ زنجیرِ نجات
async def test_broken_callback_still_answers(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, OWNER_BOT_TG_ID)
    admin = Chat(main_dp, ADMIN_TG_ID)
    await admin.tap("admin_owner_suspend:not-a-number")  # int() رویِ دادهٔ دستکاری‌شده ⇒ ValueError
    assert admin.last_toast["text"] == CALLBACK_FAILED_TOAST, admin.last_toast
    print("✅ test_broken_callback_still_answers PASSED")


# ============================================================================= ۷ — مشاوره و حالتِ تعمیر
def test_consultation_menu_has_no_dead_buttons() -> None:
    markup = shop_keyboards.customer_main_keyboard(TenantMode.CONSULTATION, support_enabled=False)
    assert getattr(markup, "remove_keyboard", None) is True, "کیبوردِ مرده باید برداشته شود"

    labels = _labels(shop_keyboards.customer_main_keyboard(TenantMode.CONSULTATION, support_enabled=True))
    assert labels == [shop_texts.BTN_SUPPORT], labels
    assert shop_texts.BTN_SERVICES not in labels and shop_texts.BTN_MY_ORDERS not in labels

    shop = _labels(shop_keyboards.customer_main_keyboard(TenantMode.SALES, support_enabled=True))
    assert shop_texts.BTN_PRODUCTS in shop and shop_texts.BTN_MY_ORDERS in shop, shop
    print("✅ test_consultation_menu_has_no_dead_buttons PASSED")


async def test_maintenance_mode_blocks_customer_buttons(shop_dp, main_dp, bot_manager, main_bot) -> None:
    await reset_database()
    shop_bot_id, _p1, _p2 = await _seed()
    async with session_scope() as session:
        from app.services.admin_settings_service import get_admin_settings

        admin_settings = await get_admin_settings(session)
        admin_settings.maintenance_mode = True
        await session.flush()

    env = _Env(shop_dp, main_dp, bot_manager, main_bot, shop_bot_id, 1, 2)
    for label in (shop_texts.BTN_CART, shop_texts.BTN_MY_ORDERS):
        await env.cust_say(label)
        assert env.shop_bot.session.sent_messages[-1]["text"] == shop_texts.PLATFORM_MAINTENANCE_REPLY, (
            label,
            env.shop_bot.session.sent_messages[-1]["text"],
        )
    await env.cust_cb("cart_checkout_start")
    assert env.cust_alerts()[-1]["text"] == shop_texts.PLATFORM_MAINTENANCE_REPLY, env.cust_alerts()[-1]
    print("✅ test_maintenance_mode_blocks_customer_buttons PASSED")


# ============================================================================= ۸ — گیتِ تازه و قراردادها
def test_dead_button_gate_passes() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import check_callbacks

    assert check_callbacks.main() == 0, "هر callback_data باید مصرف‌کننده داشته باشد"


def test_texts_match_service_limits() -> None:
    """اعدادِ متنِ پنل با سرویس یکی باشند (سرویس را به texts ایمپورت نمی‌کنیم: دورِ import)."""
    assert scheduled_broadcast_service.MIN_LEAD_MINUTES == 5 and "حداقلِ ۵ دقیقه" in main_texts.SCHEDULE_TOO_SOON
    assert scheduled_broadcast_service.MAX_LEAD_DAYS == 60 and "۶۰ روز" in main_texts.SCHEDULE_TOO_FAR
    assert scheduled_broadcast_service.MAX_ACTIVE_PER_SHOP == 5 and "فقط ۵ ارسال" in main_texts.SCHEDULE_MAX_REACHED
    assert admin_handlers._INT_FIELDS_MAX["referral_reward_value"] == 100
    assert admin_handlers._INT_FIELDS_MAX["usd_to_toman_rate"] == 500_000
    assert admin_handlers._URL_FIELDS == frozenset({"ai_base_url", "ai_fallback_base_url"})
    buttons = [btn for row in main_keyboards.empty_screen_keyboard().inline_keyboard for btn in row]
    assert buttons and buttons[-1].callback_data == "main_menu", "دکمهٔ بازگشتِ صفحه‌هایِ خالی همان پیشوندی است که هندلر مصرف می‌کند"
    print("✅ test_texts_match_service_limits PASSED")


# ============================================================================= ۹ — یادآوریِ غیرقابل‌ارسال
async def test_undeliverable_reminder_is_not_retried_forever() -> None:
    """«chat not found» یک حالتِ همیشگی است؛ بی‌علامت‌زدن، هر گردشِ جاب همان traceback را می‌ریخت."""
    from aiogram.exceptions import TelegramBadRequest

    from app.database.models import WalletCharge
    from app.services import wallet_expiry_service

    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, OWNER_BOT_TG_ID)
    async with session_scope() as session:
        owner = (await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == OWNER_TG_ID))).scalar_one()
        charge = WalletCharge(
            shop_owner_id=owner.id,
            amount_toman=300_000,
            remaining_toman=300_000,
            expires_at=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=20),
        )
        session.add(charge)
        await session.flush()
        charge_id = charge.id

    attempts: list[int] = []

    class _DeadBot:
        async def send_message(self, chat_id, text, **kwargs):
            attempts.append(chat_id)
            raise TelegramBadRequest(method="SendMessage", message="Bad Request: chat not found")

    async with session_scope() as session:
        await wallet_expiry_service.process_wallet_expiry_and_reminders(session, _DeadBot())
        again = (await session.get(WalletCharge, charge_id)).reminder_30d_sent
    assert again is True, "مرزِ ۳۰ روز «تلاش‌شده» علامت می‌خورد حتی اگر نشود فرستاد"
    assert len(attempts) == 1, attempts

    async with session_scope() as session:
        await wallet_expiry_service.process_wallet_expiry_and_reminders(session, _DeadBot())
    assert len(attempts) == 1, "دوباره برایِ همان مرز تلاش نمی‌کند (لاگِ تکراریِ بی‌پایان در دیپلوی)"
    print("✅ test_undeliverable_reminder_is_not_retried_forever PASSED")


async def main() -> None:
    main_dp, shop_dp, bot_manager, main_bot = build_test_dispatchers()
    test_consultation_menu_has_no_dead_buttons()
    test_texts_match_service_limits()
    test_dead_button_gate_passes()
    await test_main_menu_button_returns_to_the_panel(main_dp)
    await test_scheduled_screen_is_actionable(main_dp)
    await test_scheduled_list_hides_internal_ids(main_dp)
    await test_operator_cannot_approve_payment_outside_scope(main_dp)
    await test_setting_bounds_and_url_are_enforced(main_dp)
    await test_platform_card_number_is_encrypted_at_rest(main_dp)
    await test_broken_callback_still_answers(main_dp)
    await test_maintenance_mode_blocks_customer_buttons(shop_dp, main_dp, bot_manager, main_bot)
    await test_undeliverable_reminder_is_not_retried_forever()


if __name__ == "__main__":
    asyncio.run(main())
