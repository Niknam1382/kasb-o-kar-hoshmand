"""
تست: P18 · A3 — پیامکِ کاوه‌نگار (درِ روشن/خاموش، سرشماره و قالب از پنل، سقفِ ساعتی، رمزنگاریِ کلید).

پوشش:
۱. `otp_service.send_phone_code`: خاموش ⇒ «disabled» (بدونِ هیچ درخواستِ شبکه)؛ بدونِ کلید ⇒ «no_key»؛
   سقفِ ساعتی ⇒ «rate_limited»؛ موفق ⇒ sent_at/provider_status ثبت می‌شود. هیچ حالتی ثبت‌نام را نمی‌خواباند.
۲. `KavenegarSmsService`: فرستنده و قالب واقعاً به درخواست می‌رسند، ارقامِ فارسیِ سرشماره نرمال می‌شود،
   متنِ قالبِ خالی ⇒ registerotp، و پیامِ خطا هیچ‌جا کلیدِ API را ندارد.
۳. پنلِ ادمین: درِ روشن/خاموش + هشدارِ «کلید نداری» + اعتبارسنجیِ فرمتِ سرشماره/قالب + نمایشِ ماسک‌شده.
۴. د(۴): کلیدهایِ کاوه‌نگار و AI در دیتابیس رمزنگاری می‌شوند، مقدارِ قدیمیِ خام همچنان خوانده می‌شود
   و هیچ‌جا (نه لاگ، نه پیام) کلیدِ خام بیرون نمی‌آید.

اجرا: python3 tests_manual/test_p18_sms.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from sqlalchemy import select, text  # noqa: E402

from harness import build_test_dispatchers, reset_database  # noqa: E402
from phase4_helpers import Chat  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot import texts as main_texts  # noqa: E402
from app.database.models import OtpCode, ShopOwner  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import otp_service, sms_service  # noqa: E402
from app.services.admin_settings_service import get_admin_settings  # noqa: E402
from app.utils.validators import fa_text  # noqa: E402

ADMIN_TG_ID = 12345
OWNER_TG_ID = 999_911
SHOP_BOT_TG_ID = 999_912
PHONE = "09125550000"
API_KEY = "sk-kavenegar-secret-value-123"


class _FakeSms:
    """جانشینِ `sms_service.get_sms_service` — درخواست‌ها را ضبط می‌کند و طبقِ خواستِ تست جواب می‌دهد."""

    instances: list["_FakeSms"] = []

    def __init__(self, api_key, sender=None, template=None, fail_with=None, status="200"):
        self.api_key = api_key
        self.sender = sender
        self.template = template
        self.fail_with = fail_with
        self.status = status
        self.sent: list[tuple[str, str]] = []
        _FakeSms.instances.append(self)

    async def send_otp(self, phone_number: str, code: str) -> str:
        self.sent.append((phone_number, code))
        if self.fail_with is not None:
            raise sms_service.SmsServiceError(self.fail_with)
        return self.status


async def _sms_enabled(key: str | None = API_KEY, sender: str | None = None, template: str | None = None) -> None:
    async with session_scope() as session:
        admin = await get_admin_settings(session)
        admin.sms_enabled = True
        admin.sms_api_key = key
        admin.sms_sender_number = sender
        admin.sms_otp_template = template


def _patch_service(monkey: dict, factory):
    monkey["original"] = otp_service.sms_service.get_sms_service
    otp_service.sms_service.get_sms_service = factory


def _restore(monkey: dict) -> None:
    otp_service.sms_service.get_sms_service = monkey["original"]


# ============================================================================= ۱ — منطقِ تحویلِ کد
async def test_send_phone_code_paths() -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    monkey: dict = {}

    async def owner_id() -> int:
        async with session_scope() as session:
            return (await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == OWNER_TG_ID))).scalar_one().id

    oid = await owner_id()

    async with session_scope() as session:
        admin = await get_admin_settings(session)
        admin.sms_enabled = False
        admin.sms_api_key = API_KEY
        _FakeSms.instances.clear()
        _patch_service(monkey, lambda *a, **k: _FakeSms("x"))
        result = await otp_service.send_phone_code(
            session, shop_owner_id=oid, purpose="registration_phone", phone=PHONE, admin_settings=admin
        )
        _restore(monkey)
    assert (result.delivered, result.reason) == (False, "disabled"), result
    assert _FakeSms.instances == [], "وقتی خاموش است هیچ سرویسی ساخته/صدا زده نمی‌شود"
    code_off = result.code
    assert len(code_off) == 6 and code_off.isdigit()

    async with session_scope() as session:
        admin = await get_admin_settings(session)
        admin.sms_enabled = True
        admin.sms_api_key = "   "
        _FakeSms.instances.clear()
        _patch_service(monkey, lambda *a, **k: _FakeSms("x"))
        result = await otp_service.send_phone_code(
            session, shop_owner_id=oid, purpose="registration_phone", phone=PHONE, admin_settings=admin
        )
        _restore(monkey)
    assert (result.delivered, result.reason) == (False, "no_key"), result
    assert _FakeSms.instances == [], "بدونِ کلید هم شبکه صدا زده نمی‌شود"

    # موفق: وضعیتِ provider ثبت می‌شود
    async with session_scope() as session:
        admin = await get_admin_settings(session)
        admin.sms_enabled = True
        admin.sms_api_key = API_KEY
        admin.sms_sender_number = "۱۰۰۰۱۲۳۴۵۶"
        admin.sms_otp_template = None
        _FakeSms.instances.clear()
        _patch_service(monkey, lambda key, sender=None, template=None: _FakeSms(key, sender, template, status="200"))
        result = await otp_service.send_phone_code(
            session, shop_owner_id=oid, purpose="registration_phone", phone=PHONE, admin_settings=admin
        )
        _restore(monkey)
    assert (result.delivered, result.reason) == (True, None), result
    fake = _FakeSms.instances[0]
    assert fake.sender == "1000123456", "ارقامِ فارسیِ سرشماره نرمال می‌شود"
    assert fake.template == sms_service.DEFAULT_OTP_TEMPLATE, "قالبِ تنظیم‌نشده ⇒ پیش‌فرض"
    assert fake.sent == [(PHONE, result.code)]
    async with session_scope() as session:
        rows = list((await session.execute(select(OtpCode).where(OtpCode.code == result.code))).scalars().all())
        assert len(rows) == 1 and rows[0].sent_at is not None and rows[0].provider_status == "200"
        assert rows[0].phone_number == PHONE

    # سقفِ ساعتی به‌ازایِ هر شماره (و فقط برایِ همان هدف)
    for _ in range(otp_service.MAX_SENDS_PER_PHONE_PER_HOUR - 1):
        async with session_scope() as session:
            admin = await get_admin_settings(session)
            _FakeSms.instances.clear()
            _patch_service(monkey, lambda key, sender=None, template=None: _FakeSms(key, sender, template))
            again = await otp_service.send_phone_code(
                session, shop_owner_id=oid, purpose="registration_phone", phone=PHONE, admin_settings=admin
            )
            _restore(monkey)
        assert again.delivered is True, again
    async with session_scope() as session:
        admin = await get_admin_settings(session)
        _FakeSms.instances.clear()
        _patch_service(monkey, lambda key, sender=None, template=None: _FakeSms(key, sender, template))
        capped = await otp_service.send_phone_code(
            session, shop_owner_id=oid, purpose="registration_phone", phone=PHONE, admin_settings=admin
        )
        _restore(monkey)
    assert (capped.delivered, capped.reason) == (False, "rate_limited"), capped
    assert _FakeSms.instances == [], "وقتی سقف خورده شده اصلاً درخواستی ساخته نمی‌شود"

    # شکستِ ارسال ⇒ جایگزینِ «کد در چت»، نه کرش (هدفِ دیگر، تا سقفِ بالا دست‌کم گرفته نشود)
    async with session_scope() as session:
        admin = await get_admin_settings(session)
        _FakeSms.instances.clear()
        _patch_service(monkey, lambda key, sender=None, template=None: _FakeSms(key, sender, template, fail_with="شبکه قطع"))
        failed = await otp_service.send_phone_code(
            session, shop_owner_id=oid, purpose="profile_phone", phone="09129998877", admin_settings=admin
        )
        _restore(monkey)
    assert (failed.delivered, failed.reason) == (False, "send_failed"), failed
    assert failed.code.isdigit() and len(failed.code) == 6, "کد هست تا در چت نشان داده شود"
    assert API_KEY not in _FakeSms.instances[0].fail_with, "متنِ خطایِ جانشین هیچ رازی ندارد"
    async with session_scope() as session:
        row = (await session.execute(select(OtpCode).where(OtpCode.code == failed.code))).scalar_one()
        assert row.sent_at is None and row.provider_status is None, "ارسالِ ناموفق به‌عنوانِ ارسالِ موفق ثبت نمی‌شود"

    # حجمِ ۳۰ روز اخیر = تعدادِ پیامک‌هایِ واقعاً رفته (مبنایِ برآوردِ هزینه در پنلِ ادمین)
    async with session_scope() as session:
        assert await otp_service.sent_count_within(session) == otp_service.MAX_SENDS_PER_PHONE_PER_HOUR
    print("✅ test_send_phone_code_paths PASSED")


# ============================================================================= ۲ — سرویسِ کاوه‌نگار
def test_kavenegar_request_shape_and_no_key_leak() -> None:
    assert sms_service.normalize_sender_digits(" ۱۰۰۰۱۲۳۴۵۶ ") == "1000123456"
    assert sms_service.normalize_sender_digits("+۹۸۹۱۲۰۰۰۱۱۱۲") == "+989120001112"
    assert sms_service.normalize_sender_digits("  ") is None and sms_service.normalize_sender_digits(None) is None

    service = sms_service.KavenegarSmsService(API_KEY, sender="۱۰۰۰ ۱۲۳ ۴۵۶", template="  myOtp-1  ")
    assert service.sender == "1000123456" and service.template == "myOtp-1"
    assert sms_service.KavenegarSmsService(API_KEY).template == "registerotp"
    assert sms_service.KavenegarSmsService(API_KEY, template="").template == "registerotp"
    assert isinstance(sms_service.get_sms_service(API_KEY), sms_service.KavenegarSmsService)
    print("✅ test_kavenegar_request_shape_and_no_key_leak PASSED")


# ============================================================================= ۳ — پنلِ ادمین
async def test_admin_sms_panel(main_dp) -> None:
    await reset_database()
    admin = Chat(main_dp, ADMIN_TG_ID)

    async def settings():
        async with session_scope() as session:
            return await get_admin_settings(session)

    assert (await settings()).sms_enabled is False, "پیش‌فرض خاموش ⇒ رفتارِ امروزِ همه‌یِ نصب‌ها"
    await admin.tap("admin_toggle_sms")
    assert (await settings()).sms_enabled is True
    assert admin.last_toast["text"] == fa_text(main_texts.SMS_SENT_VOLUME_LINE, days=otp_service.COST_WINDOW_DAYS, count=0)
    assert any(m["text"] == main_texts.SMS_ENABLED_WITHOUT_KEY for m in admin.sent), "هشدارِ «کلید نداری»"

    await admin.tap("admin_toggle_sms")
    assert (await settings()).sms_enabled is False

    await admin.tap("admin_setting_edit:sms_api_key")
    assert admin.last_text == main_texts.ADMIN_ASK_SMS_API_KEY
    await admin.say(API_KEY)
    assert (await settings()).sms_api_key == API_KEY

    await admin.tap("admin_setting_edit:sms_sender_number")
    assert admin.last_text == main_texts.ADMIN_ASK_SMS_SENDER
    for bad in ("abc", "۱۲", "+۹۸" + "۱" * 30):
        await admin.say(bad)
        assert admin.last_text == main_texts.ADMIN_INVALID_SMS_SENDER, bad
    await admin.say("۱۰۰۰۱۲۳۴۵۶")
    assert (await settings()).sms_sender_number == "1000123456"
    # ذخیره‌یِ موفق state را پاک می‌کند ⇒ برایِ پاک‌کردن باید دوباره از منو وارد شد
    await admin.tap("admin_setting_edit:sms_sender_number")
    await admin.say("خالی")
    assert (await settings()).sms_sender_number is None

    await admin.tap("admin_setting_edit:sms_otp_template")
    for bad in ("قالبِ فارسی", "a" * 65, "with space"):
        await admin.say(bad)
        assert admin.last_text == main_texts.ADMIN_INVALID_SMS_TEMPLATE, bad
    await admin.say("myOtp_1")
    assert (await settings()).sms_otp_template == "myOtp_1"

    labels = dict(main_texts.admin_settings_button_labels(await settings()))
    assert API_KEY not in labels["sms_api_key"] and "●●●●" in labels["sms_api_key"], labels["sms_api_key"]
    assert "myOtp_1" in labels["sms_otp_template"], labels["sms_otp_template"]
    # سرشماره در همین تست پاک شده بود ⇒ برچسب باید صادق بگوید «تنظیم‌نشده»
    assert labels["sms_sender_number"].endswith("تنظیم‌نشده"), labels["sms_sender_number"]

    await admin.tap("admin_setting_edit:sms_otp_template")  # ذخیره state را پاک می‌کند ⇒ دوباره وارد شو
    await admin.say("خالی")
    assert (await settings()).sms_otp_template is None
    labels = dict(main_texts.admin_settings_button_labels(await settings()))
    assert sms_service.DEFAULT_OTP_TEMPLATE in labels["sms_otp_template"], labels["sms_otp_template"]
    print("✅ test_admin_sms_panel PASSED")


# ============================================================================= ۴ — رمزنگاریِ کلیدها
async def test_keys_are_encrypted_at_rest() -> None:
    await reset_database()
    async with session_scope() as session:
        admin = await get_admin_settings(session)
        admin.sms_api_key = API_KEY
        admin.ai_api_key = API_KEY
        admin.ai_fallback_api_key = API_KEY
        await session.flush()

    async with session_scope() as session:
        raw = (await session.execute(text("SELECT sms_api_key, ai_api_key, ai_fallback_api_key FROM admin_settings"))).first()
    assert raw and all(API_KEY not in str(value) for value in raw), "در دیتابیس فقط رمزِ ciphertext است"
    assert all(value is not None and len(str(value)) > len(API_KEY) for value in raw), raw

    async with session_scope() as session:
        admin = await get_admin_settings(session)
        assert admin.sms_api_key == API_KEY and admin.ai_api_key == API_KEY and admin.ai_fallback_api_key == API_KEY

    # مقدارِ قدیمیِ رمزنگاری‌نشده (قبلِ این تغییر) بخوبی خوانده می‌شود و با نوشتنِ دوباره رمز می‌شود
    async with session_scope() as session:
        await session.execute(text("UPDATE admin_settings SET ai_api_key = :legacy"), {"legacy": "legacy-plain-key"})
    async with session_scope() as session:
        admin = await get_admin_settings(session)
        assert admin.ai_api_key == "legacy-plain-key", "خواندنِ مقدارِ خامِ قدیمی نباید بشکند"
        admin.ai_api_key = API_KEY
        await session.flush()
    async with session_scope() as session:
        stored = (await session.execute(text("SELECT ai_api_key FROM admin_settings"))).scalar_one()
        assert stored != API_KEY and API_KEY not in stored

    print("✅ test_keys_are_encrypted_at_rest PASSED")


async def main() -> None:
    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    test_kavenegar_request_shape_and_no_key_leak()
    await test_send_phone_code_paths()
    await test_admin_sms_panel(main_dp)
    await test_keys_are_encrypted_at_rest()


if __name__ == "__main__":
    asyncio.run(main())
