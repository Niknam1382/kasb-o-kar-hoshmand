"""
تست: P21-F — بازرسیِ امنیتی و رفعِ یافته‌ها

پوشش (هر مورد یکِ یافتهٔ تأییدشده از بازرسی است):
۱. دامنهٔ تهی دیگر «بدونِ دامنه» نیست: `set_scope(role, [])` دسترسیِ کامل نمی‌سازد، و
   ادمینی که فهرستِ اشتباه می‌فرستد به همهٔ فروشگاه‌ها نمی‌رسد (برعکسِ رفتارِ P21-E).
۲. اصلاحِ کیف‌پول — تنها مسیری که دامنه را نمی‌سنجید — هم در شروعِ فرم، هم در لحظهٔ
   نوشتنِ پول بسته می‌شود؛ کال‌بکِ دست‌کاری‌شده other نمی‌شکند و یادداشتِ آزاد دیگر
   کلیدِ ایدمپوتنسی نیست (دو اصلاحِ پیاپی با دلیلِ یکسان).
۳. دفترِ ممیزیِ ادمینِ دامنه‌دار فقط ردیف‌هایِ فروشگاه‌هایِ خودش را می‌بیند
   (ردیف‌هایِ پلتفرمیِ بی‌فروشگاه می‌مانند).
۴. «تلاشِ دوبارهٔ» صفِ اعلان تاریخچهٔ شکست را پاک نمی‌کند و کلِ صف را یک‌جا برنمی‌گرداند.
۵. لاگِ استثنا (traceback) هم از ماسکِ راز رد می‌شود، نه فقط پیامِ اصلی.
۶. نگهبانِ «رباتِ اصلی»: توکنِ بله‌یِ پلتفرم هم مثلِ توکنِ تلگرامِ اصلی رد می‌شود، و
   متنِ بیویِ دیده‌شده پیش ازِ ورود به دفترِ ممیزی تک‌خط می‌شود (جعلِ ردیفِ ممیزی).
۷. عملیاتِ گروهی (هدیه/تمدید) هم به دامنهٔ ادمینِ عملیاتی محدود می‌شود.

اجرا: python3 tests_manual/test_p21_security.py
"""
from __future__ import annotations

import asyncio
import logging
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402
from sqlalchemy import func, select, update  # noqa: E402

from harness import build_test_dispatchers, reset_database  # noqa: E402
from phase4_helpers import Chat  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot import texts as main_texts  # noqa: E402
from app.config import settings  # noqa: E402
from app.database.models import (  # noqa: E402
    AuditEventType,
    Notification,
    ShopBot,
    ShopOwner,
    WalletCharge,
)
from app.database.session import session_scope  # noqa: E402
from app.observability import CORRELATION_PLAIN_FORMAT, ScrubbingFormatter  # noqa: E402
from app.services import (  # noqa: E402
    admin_role_service,
    audit_log_service,
    bot_branding_service,
    credit_batch_service,
    notification_service,
)

ADMIN_TG_ID = 12345
OPERATOR_TG_ID = 999_861
OWNER_A_TG_ID = 999_862
OWNER_B_TG_ID = 999_863
SHOP_A_BOT_TG_ID = 999_864
SHOP_B_BOT_TG_ID = 999_865

FAKE_MAIN_TG_TOKEN = "777000:AAHnPk0lQ2mZxR7tYbCuVaBgT6sErI9oK"
FAKE_MAIN_BALE_TOKEN = "888000:BBHnPk0lQ2mZxR7tYbCuVaBgT6sErI9oK"
FAKE_SHOP_TOKEN = "999111:CCshop-own-token_AAAAAAAAAAAAAAAAAA"


async def _owner_id(telegram_id: int) -> int:
    async with session_scope() as session:
        return int((await session.execute(select(ShopOwner.id).where(ShopOwner.telegram_id == telegram_id))).scalar_one())


async def _charge_count(owner_id: int) -> int:
    async with session_scope() as session:
        return int(await session.scalar(select(func.count()).select_from(WalletCharge).where(WalletCharge.shop_owner_id == owner_id)) or 0)


async def _two_shops() -> tuple[int, int]:
    await reset_database()
    await seed_usable_shop(OWNER_A_TG_ID, SHOP_A_BOT_TG_ID)
    await seed_usable_shop(OWNER_B_TG_ID, SHOP_B_BOT_TG_ID)
    return await _owner_id(OWNER_A_TG_ID), await _owner_id(OWNER_B_TG_ID)


async def _grant_operator(scope: list[int] | None) -> int:
    """یکِ ردیفِ نقش، همیشه. (دو بار grant کردن، get_by_telegram_id را می‌شکند.)"""
    async with session_scope() as session:
        role = await admin_role_service.get_by_telegram_id(session, OPERATOR_TG_ID)
        if role is None:
            role = await admin_role_service.grant_operator(session, OPERATOR_TG_ID, granted_by_telegram_id=ADMIN_TG_ID)
        await admin_role_service.set_scope(session, role, scope)
        return role.id


# ============================================================================= ۱ — دامنهٔ تهی
def test_empty_scope_is_not_unlimited() -> None:
    assert admin_role_service.parse_owner_ids(None) is None, "ستونِ NULL ⇒ بدونِ دامنه"
    assert admin_role_service.parse_owner_ids("") == set(), "رشتهٔ خالی ⇒ دامنهٔ بسته (P21-F)"
    assert admin_role_service.is_in_scope(set(), 7) is False, "دامنهٔ تهی ⇒ هیچِ فروشگاه"
    assert admin_role_service.is_in_scope(None, 7) is True, "بدونِ دامنه ⇒ همه"

    class _Role:
        allowed_owner_ids: str | None = ""

    assert main_texts.admin_role_scope_label(_Role()) == main_texts.ROLE_SCOPE_EMPTY_LABEL
    _Role.allowed_owner_ids = None
    assert main_texts.admin_role_scope_label(_Role()) == main_texts.ROLE_SCOPE_UNLIMITED_LABEL
    print("✅ test_empty_scope_is_not_unlimited PASSED")


async def test_empty_scope_survives_the_database() -> None:
    owner_a, _owner_b = await _two_shops()
    role_id = await _grant_operator([])
    async with session_scope() as session:
        role = await admin_role_service.get_by_id(session, role_id)
        assert role.allowed_owner_ids is not None, "دامنهٔ تهی باید رشتهٔ خالی بماند، نه NULL"
        assert await admin_role_service.can_touch_owner(session, OPERATOR_TG_ID, owner_a) is False
        assert await admin_role_service.can_touch_owner(session, ADMIN_TG_ID, owner_a) is True, (
            "سوپرادمین که در جدولِ نقش‌ها نیست ⇒ بدونِ دامنه"
        )
    print("✅ test_empty_scope_survives_the_database PASSED")


async def test_unknown_ids_do_not_open_every_shop(main_dp) -> None:
    """قصدِ ادمین: «فقطِ این شناسه‌ها». واقعیت: هیچ‌کدام فروشگاه‌دار نیست. P21-E: دامنهٔ تهی
    ذخیره می‌شد و برابرِ «بدونِ دامنه» خوانده می‌شد ⇒ دسترسیِ کامل. حالا ذخیره نمی‌شود."""
    await _two_shops()
    role_id = await _grant_operator(None)
    admin = Chat(main_dp, ADMIN_TG_ID)
    await admin.tap(f"admin_role_scope:{role_id}")
    await admin.say("777777,888888")
    assert main_texts.ROLE_SCOPE_NO_MATCH in admin.last_text, admin.last_text
    async with session_scope() as session:
        role = await admin_role_service.get_by_id(session, role_id)
        assert role.allowed_owner_ids is None, "دامنهٔ بی‌نتیجه ذخیره نشد (قبلاً همین یعنی «همه»)"
        assert main_texts.ADMIN_INVALID_NUMBER not in admin.last_text
    # «هیچ» صریح ⇒ دامنهٔ تهی، و بر اساسِ همان دامنه هیچ فروشگاه‌داری باز نمی‌شود
    await admin.say("هیچ")
    async with session_scope() as session:
        role = await admin_role_service.get_by_id(session, role_id)
        assert role.allowed_owner_ids == "", role.allowed_owner_ids
    operator = Chat(main_dp, OPERATOR_TG_ID)
    await operator.say("👥 مدیریت فروشگاه‌دارها")
    assert main_texts.ADMIN_SHOP_OWNERS_EMPTY in operator.last_text, operator.last_text
    print("✅ test_unknown_ids_do_not_open_every_shop PASSED")


# ============================================================================= ۲ — اصلاحِ کیف‌پول
async def test_wallet_correction_respects_scope(main_dp) -> None:
    owner_a, owner_b = await _two_shops()
    await _grant_operator([owner_a])

    operator = Chat(main_dp, OPERATOR_TG_ID)
    before_b = await _charge_count(owner_b)
    before_msgs = len(operator.sent)
    await operator.tap(f"admin_owner_wallet_correction:{owner_b}")
    assert operator.last_toast["text"] == main_texts.ADMIN_OWNER_OUT_OF_SCOPE_TOAST
    assert len(operator.sent) == before_msgs, "دفترِ تراکنشِ فروشگاهِ خارج از دامنه نمایش داده نمی‌شود"
    assert await _charge_count(owner_b) == before_b

    # داخلِ دامنه: فرم باز می‌شود، ولی اگر دامنه وسطِ فرم بسته شود پولی نوشته نمی‌شود
    await operator.tap(f"admin_owner_wallet_correction:{owner_a}")
    assert "🧾" in operator.last_text, operator.last_text
    await operator.say("5000")
    assert main_texts.ADMIN_ASK_WALLET_CORRECTION_REASON in operator.last_text
    await _grant_operator([])
    before_a = await _charge_count(owner_a)
    before_msgs = len(operator.sent)
    await operator.say("توضیحِ تست")
    assert await _charge_count(owner_a) == before_a, "پولِ بی‌دامنه نباید کم/زیاد شود"
    assert operator.last_text == main_texts.ADMIN_OWNER_OUT_OF_SCOPE_TOAST, operator.last_text
    assert main_texts.admin_wallet_correction_confirmation("x", 5000, 0) not in operator.last_text
    assert len(operator.sent) == before_msgs + 1, "فقط پیامِ رد، نه پیامِ موفقیت"
    print("✅ test_wallet_correction_respects_scope PASSED")


async def test_wallet_correction_survives_bad_callback_and_repeats(main_dp) -> None:
    """۱) payloadِ دست‌کاری‌شده نباید هندلر را با ValueError بشکند.
    ۲) دو اصلاحِ پیاپی با دلیلِ یکسان: کلیدِ ایدمپوتنسی از پیامِ ادمین می‌آید، نه از متنِ دلیل."""
    owner_a, _owner_b = await _two_shops()
    await _grant_operator([owner_a])
    operator = Chat(main_dp, OPERATOR_TG_ID)

    before = len(operator.sent)
    await operator.tap("admin_owner_wallet_correction:abc")
    assert operator.last_toast["text"] == main_texts.GENERIC_ERROR
    assert len(operator.sent) == before, "کال‌بکِ خراب هیچ صفحه‌ای باز نمی‌کند"

    first = await _charge_count(owner_a)
    for amount in ("5000", "4000"):
        await operator.tap(f"admin_owner_wallet_correction:{owner_a}")
        await operator.say(amount)
        await operator.say("تنظیمِ مانده بر اساسِ فاکتور")  # دلیلِ یکسان در هر دو اصلاح
    assert await _charge_count(owner_a) == first + 2, "دو اصلاحِ جدا با یادداشتِ یکسان هر دو نوشته می‌شوند"
    print("✅ test_wallet_correction_survives_bad_callback_and_repeats PASSED")


# ============================================================================= ۳ — دامنه در ممیزی
async def test_audit_query_is_scoped() -> None:
    owner_a, owner_b = await _two_shops()
    async with session_scope() as session:
        bot_of = {
            owner_id: int(
                (await session.execute(select(ShopBot.id).where(ShopBot.shop_owner_id == owner_id))).scalar_one()
            )
            for owner_id in (owner_a, owner_b)
        }
        await audit_log_service.log(session, AuditEventType.OWNER_GIFT_GRANTED, shop_bot_id=bot_of[owner_b], details="هدیه به بی")
        await audit_log_service.log(session, AuditEventType.OWNER_GIFT_GRANTED, shop_bot_id=bot_of[owner_a], details="هدیه به ای")
        await audit_log_service.log(session, AuditEventType.KILL_SWITCH_TOGGLED, details="سراسری")
        await session.commit()

    async with session_scope() as session:
        everything = await audit_log_service.query(session)
        scoped = await audit_log_service.query(session, allowed_owner_ids={owner_a})
        nothing = await audit_log_service.query(session, allowed_owner_ids=set())
    assert len(everything) == 3, everything
    assert {row.details for row in scoped} == {"هدیه به ای", "سراسری"}, scoped
    assert {row.details for row in nothing} == {"سراسری"}, "دامنهٔ تهی ⇒ فقط ردیف‌هایِ پلتفرمی"
    print("✅ test_audit_query_is_scoped PASSED")


# ============================================================================= ۴ — تلاشِ دوبارهٔ صف
async def test_retry_failed_is_bounded_and_keeps_evidence() -> None:
    await reset_database()
    async with session_scope() as session:
        for index in range(5):
            await notification_service.enqueue(session, 900_000 + index, f"خبرِ {index}", dedupe_key=f"sec:{index}")
        await session.execute(
            update(Notification).values(
                status=notification_service.FAILED, attempts=6, last_error="429 too many requests"
            )
        )
        await session.commit()

    async with session_scope() as session:
        reset = await notification_service.retry_failed(session, limit=2)
        await session.commit()
    assert reset == 2, reset
    async with session_scope() as session:
        pending = int(await session.scalar(select(func.count()).select_from(Notification).where(Notification.status == "pending")) or 0)
        failed = int(await session.scalar(select(func.count()).select_from(Notification).where(Notification.status == "failed")) or 0)
        sample = (await session.execute(select(Notification).where(Notification.status == "pending"))).scalars().first()
    assert (pending, failed) == (2, 3), (pending, failed)
    assert sample.last_error == "429 too many requests", "شاهدِ شکست پاک نمی‌شود"
    assert sample.attempts == 0
    print("✅ test_retry_failed_is_bounded_and_keeps_evidence PASSED")


# ============================================================================= ۵ — ماسکِ راز در traceback
def test_traceback_secrets_are_scrubbed() -> None:
    token = "123456789:AAFAKEFAKEFAKEFAKEFAKEFAKEFAKE"
    try:
        raise RuntimeError(f"bad url https://api.telegram.org/bot{token}/sendMessage")
    except RuntimeError:
        record = logging.LogRecord("t", logging.ERROR, __file__, 1, "ارسال ناموفق", None, sys.exc_info())
    record.corr = ""
    formatted = ScrubbingFormatter(CORRELATION_PLAIN_FORMAT).format(record)
    assert token not in formatted, formatted
    assert "●●●●" in formatted, "ماسک باید در خطِ استثنا هم نشسته باشد"
    assert "sendMessage" in formatted, "بقیهٔ خطا برایِ عیب‌یابی می‌ماند"
    print("✅ test_traceback_secrets_are_scrubbed PASSED")


# ============================================================================= ۶ — رباتِ اصلی / بیو
def test_platform_bale_token_is_protected_from_branding() -> None:
    original_main, original_bale = settings.main_bot_token, settings.bale_bot_token
    settings.main_bot_token, settings.bale_bot_token = FAKE_MAIN_TG_TOKEN, FAKE_MAIN_BALE_TOKEN
    try:
        for token in (FAKE_MAIN_TG_TOKEN, FAKE_MAIN_BALE_TOKEN):
            bot = Bot(token=token)
            try:
                bot_branding_service._assert_not_main_bot(bot)
                raise AssertionError(f"توکنِ {token[:6]}… باید رد می‌شد")
            except ValueError as error:
                assert "رباتِ اصلی" in str(error)
        allowed = Bot(token=FAKE_SHOP_TOKEN)
        try:
            bot_branding_service._assert_not_main_bot(allowed)  # رباتِ فروشگاه مجاز است
        except ValueError:
            raise AssertionError("توکنِ رباتِ فروشگاه نباید رد شود")
    finally:
        settings.main_bot_token, settings.bale_bot_token = original_main, original_bale
    print("✅ test_platform_bale_token_is_protected_from_branding PASSED")


def test_observed_bio_cannot_fake_audit_rows() -> None:
    assert bot_branding_service._one_line("خطِ اول\nخطِ دوم") == "خطِ اول خطِ دوم"
    assert "\n" not in bot_branding_service._one_line("a\n\nb")
    assert bot_branding_service._one_line("   ") == ""
    assert bot_branding_service._one_line("ک" * 300, 140) == "ک" * 140
    print("✅ test_observed_bio_cannot_fake_audit_rows PASSED")


async def test_gift_write_rechecks_scope(main_dp) -> None:
    """هدیه: دامنه در شروعِ فرم سنجیده می‌شد؛ حالا در لحظهٔ «تایید» هم سنجیده می‌شود."""
    owner_a, owner_b = await _two_shops()
    await _grant_operator([owner_a, owner_b])
    operator = Chat(main_dp, OPERATOR_TG_ID)
    before = await _charge_count(owner_b)
    await operator.tap(f"admin_owner_gift:{owner_b}")
    await operator.say("10000")
    await _grant_operator([])
    await operator.tap("admin_gift_confirm")
    assert await _charge_count(owner_b) == before, "تاییدِ هدیه رویِ فروشگاهِ بی‌دامنه پول نمی‌سازد"
    print("✅ test_gift_write_rechecks_scope PASSED")


# ============================================================================= ۷ — دامنه در عملیاتِ گروهی
async def test_batch_operations_are_scoped() -> None:
    """«🎁 هدیهٔ اعتبار (گروهی)» برایِ هر ادمین نمایش داده می‌شود؛ مجموعهٔ هدف باید به دامنه
    محدود شود، وگرنه یکِ ادمینِ دامنه‌دار به ۲۰۰۰ فروشگاه‌دارِ کلِ پلتفرم اعتبار می‌دهد."""
    owner_a, owner_b = await _two_shops()
    async with session_scope() as session:
        everyone = await credit_batch_service.select_owner_ids(session, "all")
        only_a = await credit_batch_service.select_owner_ids(session, "all", allowed_owner_ids={owner_a})
        none_of_them = await credit_batch_service.select_owner_ids(session, "all", allowed_owner_ids=set())
    assert owner_a in everyone and owner_b in everyone, everyone
    assert only_a == [owner_a], only_a
    assert none_of_them == [], none_of_them

    async with session_scope() as session:
        batch = await credit_batch_service.create_batch(
            session, kind="gift", flt="all", by=str(OPERATOR_TG_ID), amount=5_000, allowed_owner_ids={owner_a}
        )
        assert batch is not None and batch.target_count == 1, batch
        assert credit_batch_service.params_of(batch)["owner_ids"] == [owner_a]
        await session.commit()
    print("✅ test_batch_operations_are_scoped PASSED")


async def main() -> None:
    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    test_empty_scope_is_not_unlimited()
    test_traceback_secrets_are_scrubbed()
    test_platform_bale_token_is_protected_from_branding()
    test_observed_bio_cannot_fake_audit_rows()
    await test_empty_scope_survives_the_database()
    await test_audit_query_is_scoped()
    await test_retry_failed_is_bounded_and_keeps_evidence()
    await test_unknown_ids_do_not_open_every_shop(main_dp)
    await test_wallet_correction_respects_scope(main_dp)
    await test_wallet_correction_survives_bad_callback_and_repeats(main_dp)
    await test_gift_write_rechecks_scope(main_dp)
    await test_batch_operations_are_scoped()


if __name__ == "__main__":
    asyncio.run(main())
