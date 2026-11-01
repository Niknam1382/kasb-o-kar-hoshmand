"""
تست: P18 · A2 — بیوگرافیِ اجباریِ ربات‌هایِ فروشگاهی (برندینگ) + P21-A.

پوشش:
۱. خالص: ترکیبِ «متنِ فروشگاه‌دار — متنِ ادمین» با سقفِ ۱۲۰؛ اگر جا نشد متنِ فروشگاه‌دار کوتاه
   می‌شود و متنِ ادمین هرگز. از P21-A نبودنِ متنِ ادمین، محافظتِ متنِ خودِ فروشگاه را خاموش نمی‌کند.
۲. `_apply_to_bot`: unchanged/applied/tampered/skipped/error — خطایِ شبکه هرگز کرش نمی‌کند؛
   متنِ جاگذاریِ تلگرام («A default short description…») بیویِ تنظیم‌نشده حساب می‌شود نه دست‌کاری؛
   و رباتِ اصلیِ پلتفرم هرگز نمی‌تواند بیو بگیرد (قاعدهٔ محصول، B6).
۳. `sync_all`: شمارش‌ها، اعلانِ نرخ‌محدود به فروشگاه‌دار (یک‌بار در ۲۴ ساعت، ماندگار در دیتابیس)،
   ثبتِ ممیزی و شمارندهٔ تخلف، نوبتِ per-ربات، و پوششِ رباتِ بله در کنارِ تلگرام.
۴. پنلِ ادمین: اعتبارسنجیِ ۶۰ نویسه، ذخیره، ممیزی، «ذخیره شد» بدونِ رباتِ وصل‌شده، فاصلهِ بازرسی.
۵. پنلِ فروشگاه‌دار: «🧴 بیوگرافیِ ربات» → متنِ خودت، ردِّ بلند، «خالی» برایِ پاک کردن، برگشت،
   و «🔄 بازبینیِ همین الان».
۶. جابِ دوره‌ای: `is_due`/`is_due_for` و `run_periodic_pass` که بیویِ دستکاری‌شده را برمی‌گرداند.
۷. باگِ گزارش‌شده: ذخیرهٔ بیو از پنلِ فروشگاه‌دار باید بیویِ رباتِ *خودِ فروشگاه* را عوض کند و
   هرگز بیویِ رباتِ اصلی را (regression روی `apply_for_shop_bot`).

اجرا: python3 tests_manual/test_p18_bot_branding.py
"""
from __future__ import annotations

import asyncio
import datetime
import sys
from types import SimpleNamespace

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from sqlalchemy import select  # noqa: E402

from harness import build_test_dispatchers, make_shop_bot, register_fake_shop_bot, reset_database  # noqa: E402
from phase4_helpers import Chat  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot import texts as main_texts  # noqa: E402
from app.database.models import AuditEventType, AuditLogEntry, ShopBot, ShopOwner  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import bot_branding_service as branding  # noqa: E402
from app.services import scheduler  # noqa: E402
from app.services.admin_settings_service import get_admin_settings  # noqa: E402

ADMIN_TG_ID = 12345
OWNER_TG_ID = 999_931
SHOP_BOT_TG_ID = 999_932
OTHER_OWNER_TG_ID = 999_941
OTHER_SHOP_BOT_TG_ID = 999_942
ADMIN_TEXT = "ساخته‌شده با @kasbokar"


class _BioBot:
    """جانشینِ aiogram.Bot فقط برایِ دو متدِ بیوگرافی."""

    def __init__(self, initial: str = "", fail_on: str | None = None, token: str = "111111:SHOP_FAKE"):
        self.bio = initial
        self.fail_on = fail_on
        self.set_calls = 0
        self.get_calls = 0
        self.token = token

    async def get_my_short_description(self, **_kwargs):
        self.get_calls += 1
        if self.fail_on == "get":
            raise RuntimeError("network down")
        return SimpleNamespace(short_description=self.bio)

    async def set_my_short_description(self, short_description=None, **_kwargs):
        self.set_calls += 1
        if self.fail_on == "set":
            raise RuntimeError("429 too many requests")
        self.bio = short_description
        return SimpleNamespace(ok=True)


class _Manager:
    """دو ترنسپورتِ واقعیِ ShopBotManager را تقلید می‌کند (تلگرام + بله)."""

    def __init__(self, bots: dict[int, _BioBot], bale_bots: dict[int, _BioBot] | None = None):
        self._bots = bots
        self._bale_bots = bale_bots or {}

    def registered_shop_bot_ids(self) -> list[int]:
        return list(self._bots)

    def registered_bale_bot_ids(self) -> list[int]:
        return list(self._bale_bots)

    def get_bot(self, shop_bot_id: int):
        return self._bots.get(shop_bot_id)

    def get_bale_bot(self, shop_bot_id: int):
        return self._bale_bots.get(shop_bot_id)


class _AlertingBot:
    def __init__(self):
        self.sent: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str, **_kwargs):
        self.sent.append((chat_id, text))


async def _shop_bot(shop_bot_id: int) -> ShopBot:
    async with session_scope() as session:
        return (await session.execute(select(ShopBot).where(ShopBot.id == shop_bot_id))).scalar_one()


async def _set_branding(text: str | None) -> None:
    async with session_scope() as session:
        admin = await get_admin_settings(session)
        admin.branding_text = text


async def _set_owner_text(shop_bot_id: int, text: str | None) -> None:
    async with session_scope() as session:
        row = (await session.execute(select(ShopBot).where(ShopBot.id == shop_bot_id))).scalar_one()
        row.branding_owner_text = text


async def _set_synced(value: datetime.datetime | None) -> None:
    async with session_scope() as session:
        admin = await get_admin_settings(session)
        admin.branding_synced_at = value


# ============================================================================= ۱ — ترکیب
def test_compose_rules() -> None:
    assert branding.compose("", "") == "" and branding.compose(None, None) == "", "هیچ متنی ⇒ هیچ کاری"
    assert branding.compose("فروشگاهِ علی", "") == "فروشگاهِ علی", "P21-A: متنِ خودِ فروشگاه هم محافظت می‌شود"
    assert branding.compose("فروشگاهِ علی", None) == "فروشگاهِ علی"
    assert branding.compose("", ADMIN_TEXT) == ADMIN_TEXT
    assert branding.compose("   ", ADMIN_TEXT) == ADMIN_TEXT
    assert branding.compose("فروشگاهِ علی", ADMIN_TEXT) == f"فروشگاهِ علی — {ADMIN_TEXT}"

    long_owner = "ی" * 200
    composed = branding.compose(long_owner, ADMIN_TEXT)
    assert composed.endswith(ADMIN_TEXT), "متنِ ادمین همیشه کامل می‌ماند"
    assert len(composed) == branding.BIO_LIMIT and composed.startswith("ی" * (branding.BIO_LIMIT - len(ADMIN_TEXT) - 3))

    # متنِ ادمین به‌تنهایی از سقفِ ۱۲۰ بلندتر ⇒ فقط همان متن، بریده
    huge_admin = "آ" * 130
    assert branding.compose("کوتاه", huge_admin) == huge_admin[:120]
    assert branding.compose("ی" * 200, "") == "ی" * 120, "متنِ فروشگاه هم به سقفِ ۱۲۰ بریده می‌شود"

    assert branding.normalize_admin_text("  " + ADMIN_TEXT + "  ") == ADMIN_TEXT
    assert branding.normalize_admin_text("خالی") is None and branding.normalize_admin_text(None) is None
    assert branding.normalize_admin_text("ب" * 70) == "ب" * 60, "سقفِ ۶۰ با برش اعمال می‌شود"
    assert branding.valid_admin_text("ب" * 60) and not branding.valid_admin_text("ب" * 61)
    assert branding.valid_owner_text("ی" * 120) and not branding.valid_owner_text("ی" * 121)
    print("✅ test_compose_rules PASSED")


# ============================================================================= ۱-ب — فاصلهٔ بازرسی
def test_check_interval_rules() -> None:
    assert branding.valid_check_minutes("60") and branding.valid_check_minutes("5") and branding.valid_check_minutes("1440")
    assert not branding.valid_check_minutes("4"), "زیرِ ۵ دقیقه یعنی هر لوپِ زمان‌بند یک درخواستِ اضافه"
    assert not branding.valid_check_minutes("1441") and not branding.valid_check_minutes("abc")
    assert not branding.valid_check_minutes("-30") and not branding.valid_check_minutes("")
    assert branding.normalize_check_minutes("90") == 90
    assert branding.interval_of(SimpleNamespace(branding_check_minutes=90)) == 90
    assert branding.interval_of(SimpleNamespace(branding_check_minutes=1)) == 5, "دادهٔ جدول هم clamp می‌شود"
    assert branding.interval_of(SimpleNamespace(branding_check_minutes=99_999)) == 1440
    assert branding.interval_of(SimpleNamespace(branding_check_minutes=None)) == 5
    print("✅ test_check_interval_rules PASSED")


# ============================================================================= ۲ — یک ربات
async def test_apply_to_bot_outcomes() -> None:
    await reset_database()
    fresh_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    await _set_owner_text(fresh_id, "فروشگاهِ علی")
    expected = f"فروشگاهِ علی — {ADMIN_TEXT}"

    # رباتِ تازه: هیچ چیزی خودمان ننوشته‌ایم ⇒ خالی/پیش‌فرضِ تلگرام «اولینِ نوشتن» است، نه تخلف
    fresh = await _shop_bot(fresh_id)
    assert fresh.branding_applied_bio is None
    bot = _BioBot(initial="")
    assert await branding._apply_to_bot(bot, fresh, ADMIN_TEXT) == ("applied", "")
    assert bot.bio == expected and fresh.branding_applied_bio == expected, "بعد از نوشتن باید بدانیم چه نوشتیم"

    placeholder = _BioBot(initial="A default short description made by @BotFather")
    outcome, previous = await branding._apply_to_bot(placeholder, await _shop_bot(fresh_id), ADMIN_TEXT)
    assert (outcome, previous) == ("applied", ""), "پیش‌فرضِ تلگرام نباید اخطارِ دست‌کاری بسازد"

    # چرخهٔ عمرِ رویِ همان ربات: سالم ← دستکاری ← حذف
    same = await _shop_bot(fresh_id)
    same.branding_applied_bio = expected
    bot = _BioBot(initial=expected)
    assert await branding._apply_to_bot(bot, same, ADMIN_TEXT) == ("unchanged", expected)
    assert bot.set_calls == 0, "وقتی درست است چیزی نوشته نمی‌شود"

    tampered_bot = _BioBot(initial="بیویِ دستکاری‌شده")
    outcome, previous = await branding._apply_to_bot(tampered_bot, same, ADMIN_TEXT)
    assert (outcome, previous) == ("tampered", "بیویِ دستکاری‌شده") and tampered_bot.bio == expected

    deleted = _BioBot(initial="")
    outcome, previous = await branding._apply_to_bot(deleted, same, ADMIN_TEXT)
    assert (outcome, previous) == ("removed", ""), "P21-A: حذفِ بیویی که خودمان نوشته بودیم = تخلف، نه اولینِ نوشتن"
    assert deleted.bio == expected

    # بدونِ متنِ ادمین، «متنِ خودِ فروشگاه» هدفِ بازرسی است (نه بی‌کاری)
    no_admin = _BioBot(initial="هرچی")
    outcome, previous = await branding._apply_to_bot(no_admin, same, None)
    assert (outcome, previous) == ("tampered", "هرچی") and no_admin.bio == "فروشگاهِ علی"

    # هیچ متنی در هیچ سمتی ⇒ skipped و صفر درخواست
    empty_shop = await _shop_bot(fresh_id)
    empty_shop.branding_owner_text = None
    empty_bot = _BioBot(initial="هرچی")
    assert await branding._apply_to_bot(empty_bot, empty_shop, None) == ("skipped", "")
    assert empty_bot.get_calls == 0 and empty_bot.set_calls == 0

    failing = _BioBot(initial="x", fail_on="get")
    assert await branding._apply_to_bot(failing, same, ADMIN_TEXT) == ("error", "")
    failing = _BioBot(initial="x", fail_on="set")
    outcome, _prev = await branding._apply_to_bot(failing, same, ADMIN_TEXT)
    assert outcome == "error", "خطایِ نوشتن فقط لاگ می‌شود، استثنا نه"
    print("✅ test_apply_to_bot_outcomes PASSED")


# ============================================================================= ۲-پ — ویرایشِ برند = تخلف نیست
async def test_admin_text_change_is_not_counted_as_tampering() -> None:
    """مثبتِ کاذبِ P18: با هر تغییرِ متنِ ادمین، بیویِ کهنه «نامطابق» بود ⇒ برایِ همه تخلف و اخطار می‌رفت."""
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    await _set_owner_text(shop_bot_id, "فروشگاهِ علی")
    await _set_branding(ADMIN_TEXT)
    bot = _BioBot(initial="")
    main_bot = _AlertingBot()
    async with session_scope() as session:
        counts = await branding.sync_all(session, _Manager({shop_bot_id: bot}), main_bot, force=True)
    assert counts["applied"] == 1 and bot.bio == f"فروشگاهِ علی — {ADMIN_TEXT}", counts
    assert main_bot.sent == []

    # ادمین برند را عوض می‌کند
    new_admin_text = "پشتیبانی: @kasbokar_help"
    await _set_branding(new_admin_text)
    same = await _shop_bot(shop_bot_id)
    bot.bio = same.branding_applied_bio  # همان چیزی که ما نوشته بودیم، هنوز رویِ ربات است
    async with session_scope() as session:
        counts = await branding.sync_all(session, _Manager({shop_bot_id: bot}), main_bot, force=True)
        row = await session.get(ShopBot, shop_bot_id)
    assert bot.bio == f"فروشگاهِ علی — {new_admin_text}", "متنِ تازه اعمال شد"
    assert counts["tampered"] == 0 and counts["removed"] == 0 and counts["applied"] == 1, counts
    assert row.branding_tamper_count == 0, "ویرایشِ خودِ پلتفرم تخلف شمرده نمی‌شود"
    assert main_bot.sent == [], "و هیچ اخطارِ «بیوت دستکاری شد» به فروشگاه‌دار نمی‌رود"
    print("✅ test_admin_text_change_is_not_counted_as_tampering PASSED")


# ============================================================================= ۲-ب — رباتِ اصلی ممنوع
async def test_main_bot_can_never_receive_a_bio() -> None:
    """B6: قاعدهٔ محصول — بیو فقط رویِ ربات‌هایِ ساخته‌شده؛ رباتِ اصلی حتی اگر پاس شود خطا می‌دهد."""
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    await _set_owner_text(shop_bot_id, "فروشگاهِ علی")
    await _set_branding(ADMIN_TEXT)
    shop_bot = await _shop_bot(shop_bot_id)

    original_settings = branding.settings
    branding.settings = SimpleNamespace(
        main_bot_token="9247775867:MAIN_ROBOT_FAKE_TOKEN", bale_bot_token="9247775868:BALE_ROBOT_FAKE_TOKEN"
    )
    try:
        main_like = _BioBot(initial="بیویِ رباتِ اصلی", token="9247775867:MAIN_ROBOT_FAKE_TOKEN")
        try:
            await branding._apply_to_bot(main_like, shop_bot, ADMIN_TEXT)
        except ValueError as exc:
            assert "رباتِ اصلی" in str(exc)
        else:
            raise AssertionError("رباطِ اصلی نباید بتواند بیو بگیرد")
        assert main_like.get_calls == 0 and main_like.set_calls == 0, "حتی خوانده هم نمی‌شود"

        # P21-F: توکنِ بله‌یِ پلتفرم هم محسوب می‌شود — اگر یکِ فروشگاه آن را در تنظیماتش جا بزند
        bale_like = _BioBot(initial="بیویِ رباتِ بلهٔ پلتفرم", token="9247775868:BALE_ROBOT_FAKE_TOKEN")
        try:
            await branding._apply_to_bot(bale_like, shop_bot, ADMIN_TEXT)
        except ValueError as exc:
            assert "رباتِ اصلی" in str(exc)
        else:
            raise AssertionError("رباتِ بلهٔ پلتفرم نباید بتواند بیو بگیرد")
        assert bale_like.get_calls == 0 and bale_like.set_calls == 0

        # مسیرِ واقعیِ پنلِ فروشگاه‌دار: ترنسپورت از منیجر خوانده می‌شود، نه از caller
        manager_bot = _BioBot(initial="", token="111111:SHOP_FAKE")
        async with session_scope() as session:
            outcome = await branding.apply_for_shop_bot(_Manager({shop_bot_id: manager_bot}), session, shop_bot)
        assert outcome == "applied" and manager_bot.bio == f"فروشگاهِ علی — {ADMIN_TEXT}", outcome
    finally:
        branding.settings = original_settings
    print("✅ test_main_bot_can_never_receive_a_bio PASSED")


# ============================================================================= ۳ — همگام‌سازیِ همه
async def test_sync_all_counts_alerts_and_audit() -> None:
    await reset_database()
    first = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    second = await seed_usable_shop(OTHER_OWNER_TG_ID, OTHER_SHOP_BOT_TG_ID)
    await _set_owner_text(first, "فروشگاهِ الف")
    await _set_branding(ADMIN_TEXT)

    bots = {first: _BioBot(initial="دستکاری‌شده"), second: _BioBot(initial="")}
    main_bot = _AlertingBot()
    async with session_scope() as session:
        counts = await branding.sync_all(session, _Manager(bots), main_bot)

    assert counts["shops"] == 2 and counts["total"] == 2, counts
    assert counts["tampered"] == 1 and counts["applied"] == 1, counts
    assert counts["unchanged"] == 0 and counts["error"] == 0
    assert bots[first].bio == f"فروشگاهِ الف — {ADMIN_TEXT}" and bots[second].bio == ADMIN_TEXT
    assert [chat for chat, _ in main_bot.sent] == [OWNER_TG_ID], "فقط به صاحبِ رباتِ دستکاری‌شده"
    async with session_scope() as session:
        row = (await session.execute(select(ShopBot).where(ShopBot.id == first))).scalar_one()
        assert row.branding_tamper_count == 1, "شمارنده‌یِ تخلف"
        assert row.branding_checked_at is not None and row.branding_next_check_at is not None, "نوبتِ per-ربات"
        assert row.branding_last_alert_at is not None, "سقفِ اخطار حالا در دیتابیس است نه حافظهٔ پروسه"
        entries = list((await session.execute(
            select(AuditLogEntry).where(AuditLogEntry.event_type == AuditEventType.BOT_BIO_TAMPERED.value)
        )).scalars().all())
        assert len(entries) == 1 and entries[0].shop_bot_id == first
        admin = await get_admin_settings(session)
        assert admin.branding_synced_at is not None

    # P21-A: پاسِ بعدیِ زمان‌بند (بدونِ force) هیچ رباتی را اذیت نمی‌کند — نوبتشان نرسیده است
    spy = {first: _BioBot(initial=bots[first].bio), second: _BioBot(initial=bots[second].bio)}
    async with session_scope() as session:
        counts = await branding.sync_all(session, _Manager(spy), main_bot)
    assert counts["shops"] == 0 and counts["total"] == 0, counts
    assert spy[first].get_calls == 0 and spy[second].get_calls == 0, "رباتِ دست‌نخورده در هر لوپ خوانده نمی‌شود"

    # پاسِ دستیِ ادمین (force=True) ⇒ همه unchanged و هیچ اعلانِ تکراری
    async with session_scope() as session:
        counts = await branding.sync_all(session, _Manager(bots), main_bot, force=True)
    assert counts["unchanged"] == 2 and counts["tampered"] == 0, counts
    assert len(main_bot.sent) == 1, "اعلانِ دوباره در کول‌دان فرستاده نمی‌شود"

    # دست‌کاریِ دوباره در همان ۲۴ ساعت ⇒ بازنویسی می‌شود ولی اعلانِ تازه نمی‌رود
    bots[first].bio = "دوباره دستکاری"
    async with session_scope() as session:
        counts = await branding.sync_all(session, _Manager(bots), main_bot, force=True)
    assert counts["tampered"] == 1
    assert len(main_bot.sent) == 1, "اعلان نرخ‌محدود است (سقفِ ماندگار)"
    assert bots[first].bio == f"فروشگاهِ الف — {ADMIN_TEXT}"
    async with session_scope() as session:
        row = (await session.execute(select(ShopBot).where(ShopBot.id == first))).scalar_one()
        assert row.branding_tamper_count == 2

    # حذفِ بیو (نه جایگزینی) ⇒ همان ربات اخطار می‌گیرد، و به‌عنوانِ تخلف شمرده می‌شود
    bots[first].bio = ""
    async with session_scope() as session:
        await _reset_alert_clock(first)
    async with session_scope() as session:
        counts = await branding.sync_all(session, _Manager(bots), main_bot, force=True)
    assert counts["removed"] == 1 and counts["tampered"] == 0, counts
    assert len(main_bot.sent) == 2, "حذفِ بیو هم اخطار دارد"
    assert "حذف" in main_bot.sent[-1][1], main_bot.sent[-1][1]
    async with session_scope() as session:
        row = (await session.execute(select(ShopBot).where(ShopBot.id == first))).scalar_one()
        assert row.branding_tamper_count == 3

    # بدونِ متنِ ادمین و بدونِ متنِ فروشگاه ⇒ هیچ درخواستی
    await _set_branding(None)
    await _set_owner_text(second, None)
    spy_second = _BioBot(initial="هرچی")
    async with session_scope() as session:
        counts = await branding.sync_all(session, _Manager({second: spy_second}), main_bot, force=True)
    assert counts["skipped"] == 1 and counts["shops"] == 1, counts
    assert spy_second.get_calls == 0 and spy_second.bio == "هرچی"
    print("✅ test_sync_all_counts_alerts_and_audit PASSED")


async def _reset_alert_clock(shop_bot_id: int) -> None:
    async with session_scope() as session:
        row = (await session.execute(select(ShopBot).where(ShopBot.id == shop_bot_id))).scalar_one()
        row.branding_last_alert_at = None
        await session.flush()


# ============================================================================= ۳-ب — پوششِ بله و متنِ فروشگاه
async def test_sync_all_covers_bale_transport_and_owner_text() -> None:
    """B1 + B2: رباتِ بلهٔ همان فروشگاه هم بازبینی می‌شود، و بیوِ خودِ فروشگاه بدونِ برندِ سراسری هم."""
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    await _set_owner_text(shop_bot_id, "فروشگاهِ علی")
    await _set_branding(None)  # ادمین برندِ سراسری ننوشته

    telegram = _BioBot(initial="")
    bale = _BioBot(initial="دستکاری در بله")
    async with session_scope() as session:
        counts = await branding.sync_all(session, _Manager({shop_bot_id: telegram}, {shop_bot_id: bale}), _AlertingBot(), force=True)

    assert counts["shops"] == 1 and counts["total"] == 2, counts
    assert telegram.bio == "فروشگاهِ علی", "متنِ خودِ فروشگاه حتی بدونِ متنِ ادمین نوشته می‌شود"
    assert bale.bio == "فروشگاهِ علی", "رباتِ بله هم همان متن را می‌گیرد"
    assert counts["applied"] == 1 and counts["tampered"] == 1, counts

    # یکِ ترنسپورتِ خراب (توکنِ باطل) نباید نوشتنِ ترنسپورتِ دیگر را متوقف کند
    telegram_fail = _BioBot(initial="x", fail_on="set")
    healthy = _BioBot(initial="")
    async with session_scope() as session:
        counts = await branding.sync_all(session, _Manager({shop_bot_id: telegram_fail}, {shop_bot_id: healthy}), _AlertingBot(), force=True)
    assert counts["error"] == 1 and counts["removed"] == 1, counts
    assert healthy.bio == "فروشگاهِ علی"
    print("✅ test_sync_all_covers_bale_transport_and_owner_text PASSED")


# ============================================================================= ۴ — پنلِ ادمین
async def test_admin_branding_settings(main_dp) -> None:
    await reset_database()
    admin = Chat(main_dp, ADMIN_TG_ID)

    async def stored():
        async with session_scope() as session:
            return (await get_admin_settings(session)).branding_text

    assert await stored() is None, "پیش‌فرض خاموش ⇒ هیچ رباتی دست نمی‌خورد"
    await admin.tap("admin_setting_edit:branding_text")
    assert admin.last_text == main_texts.ADMIN_ASK_BRANDING_TEXT
    await admin.say("ب" * 61)
    assert admin.last_text == main_texts.ADMIN_INVALID_BRANDING_TEXT
    assert await stored() is None

    await admin.say(ADMIN_TEXT)
    assert await stored() == ADMIN_TEXT, "متنِ معتبر ذخیره شد"
    assert any(main_texts.BRANDING_SAVED_NO_BOTS == m["text"] for m in admin.sent), admin.sent[-2:]
    async with session_scope() as session:
        entries = list((await session.execute(
            select(AuditLogEntry).where(AuditLogEntry.event_type == AuditEventType.BRANDING_TEXT_CHANGED.value)
        )).scalars().all())
        assert len(entries) == 1 and ADMIN_TEXT in (entries[0].details or "")

    labels = dict(main_texts.admin_settings_button_labels(await _admin_settings()))
    assert ADMIN_TEXT in labels["branding_text"], labels
    await admin.tap("admin_branding_sync")
    assert admin.last_text == main_texts.BRANDING_SAVED_NO_BOTS, "رباتِ وصل‌شده‌ای نیست ⇒ بی‌خطر"

    await admin.tap("admin_setting_edit:branding_text")
    await admin.say("خالی")
    assert await stored() is None
    print("✅ test_admin_branding_settings PASSED")


async def _admin_settings():
    async with session_scope() as session:
        return await get_admin_settings(session)


# ============================================================================= ۵ — پنلِ فروشگاه‌دار
async def test_owner_branding_screen(main_dp) -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    owner = Chat(main_dp, OWNER_TG_ID)

    await owner.say("⚙️ تنظیماتِ ربات فروشگاه")
    assert "br_open" in [b.callback_data for row in owner.last_markup.inline_keyboard for b in row]
    await owner.tap("br_open")
    assert main_texts.BRANDING_NOT_CONFIGURED in owner.last_edit_text, "پلتفرم هنوز متنِ اجباری ندارد"

    await _set_branding(ADMIN_TEXT)
    await owner.tap("br_open")
    assert "متنِ خودت: —" in owner.last_edit_text, owner.last_edit_text

    await owner.tap("br_edit")
    assert owner.last_text == main_texts.BRANDING_OWNER_ASK
    await owner.say("ی" * 121)
    assert owner.last_text == main_texts.BRANDING_OWNER_INVALID
    assert (await _shop_bot(shop_bot_id)).branding_owner_text is None, "ورودیِ نامعتبر ذخیره نمی‌شود"

    await owner.say("گالریِ گلِ مریم")
    row = await _shop_bot(shop_bot_id)
    assert row.branding_owner_text == "گالریِ گلِ مریم"
    assert main_texts.BRANDING_NOT_CONFIGURED not in owner.last_text
    assert "گالریِ گلِ مریم — " + ADMIN_TEXT in owner.last_text, owner.last_text

    await owner.tap("br_edit")  # ذخیره‌یِ موفق state را پاک کرده ⇒ دوباره واردِ حالتِ ویرایش
    await owner.say("خالی")
    assert (await _shop_bot(shop_bot_id)).branding_owner_text is None
    await owner.tap("br_back")
    assert "مدتِ تجمیعِ پیام‌ها" in owner.last_edit_text
    print("✅ test_owner_branding_screen PASSED")


# ============================================================================= ۶ — جابِ دوره‌ای
def test_branding_job_interval() -> None:
    now = datetime.datetime(2026, 11, 1, 12, 0, tzinfo=datetime.timezone.utc)
    assert branding.is_due(None, now) is True
    assert branding.is_due(now - datetime.timedelta(minutes=59), now) is False
    assert branding.is_due(now - datetime.timedelta(hours=1), now) is True
    assert branding.is_due(now - datetime.timedelta(hours=30), now) is True
    assert branding.is_due((now - datetime.timedelta(hours=7)).replace(tzinfo=None), now) is True, "naive ⇒ UTC فرض می‌شود"
    # فاصلهِ تازه از تنظیماتِ ادمین (۱۵ دقیقه) ⇒ همان ردیفِ ۵۹ دقیقه‌ای حالا واجد است
    assert branding.is_due(now - datetime.timedelta(minutes=59), now, 15 * 60) is True

    # P21-A: نوبتِ *هر ربات* (نه یکِ برچسبِ سراسری)
    fresh = SimpleNamespace(branding_next_check_at=None)
    assert branding.is_due_for(fresh, now) is True, "ردیفِ تازه همیشه واجد است"
    branding.mark_checked(fresh, 3600, now)
    assert fresh.branding_checked_at == now and fresh.branding_next_check_at == now + datetime.timedelta(hours=1)
    assert branding.is_due_for(fresh, now + datetime.timedelta(minutes=59)) is False
    assert branding.is_due_for(fresh, now + datetime.timedelta(hours=1)) is True
    naive = SimpleNamespace(branding_next_check_at=(now - datetime.timedelta(minutes=1)).replace(tzinfo=None))
    assert branding.is_due_for(naive, now) is True, "naive ⇒ UTC فرض می‌شود"
    print("✅ test_branding_job_interval PASSED")


# ============ ۶-ب — دکمه‌هایِ تازه: بازبینیِ فوریِ فروشگاه‌دار و گزارشِ ادمین
async def test_owner_check_now_and_admin_report(main_dp, bot_manager) -> None:
    from app.bots.main_bot import texts as brand_texts
    from phase4_helpers import callbacks

    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    await _set_owner_text(shop_bot_id, "گالریِ گلِ مریم")
    await _set_branding(ADMIN_TEXT)
    shop = make_shop_bot()
    register_fake_shop_bot(bot_manager, shop_bot_id, shop)
    expected = f"گالریِ گلِ مریم — {ADMIN_TEXT}"

    owner = Chat(main_dp, OWNER_TG_ID)
    await owner.say("⚙️ تنظیماتِ ربات فروشگاه")
    await owner.tap("br_open")
    assert "br_check" in callbacks(owner.last_edit_markup), "دکمهٔ «بازبینیِ همین الان» در صفحهٔ بیو نیست"
    assert "آخرینِ بازبینی" in owner.last_edit_text, owner.last_edit_text

    # کسی بیو را دستکاری کرده ⇒ «بازبینیِ همین الان» همان لحظه برمی‌گرداند و فقط به خودش خبر می‌دهد
    shop.session.short_description = "بیویِ عوض‌شده"
    await owner.tap("br_check")
    assert shop.session.short_description == expected, shop.session.short_description
    assert any(brand_texts.BRANDING_CHECK_TAMPERED in m["text"] for m in owner.sent[-2:]), owner.sent[-2:]
    assert owner.session.bio_updates == [], "رباطِ اصلی از این مسیر هم نباید بیو بگیرد"
    async with session_scope() as session:
        row = await session.get(ShopBot, shop_bot_id)
        assert row.branding_tamper_count == 1 and row.branding_checked_at is not None
        assert row.branding_last_alert_at is None, "وقتی خودِ فروشگاه‌دار پرسیده، نتیجه را همان لحظه می‌بیند ⇒ اخطارِ جدا نمی‌فرستیم"

    # بیو درست است ⇒ پیامِ «سالم» و هیچ تخلفِ تازه‌ای
    await owner.tap("br_check")
    assert any(brand_texts.BRANDING_CHECK_HEALTHY in m["text"] for m in owner.sent[-2:]), owner.sent[-2:]
    async with session_scope() as session:
        row = await session.get(ShopBot, shop_bot_id)
        assert row.branding_tamper_count == 1, "بازبینیِ سالم تخلف شمرده نمی‌شود"

    # گزارشِ ادمین: همان شمارنده باید دیده شود (پیش‌تر هیچ‌جا نمایش داده نمی‌شد)
    admin = Chat(main_dp, ADMIN_TG_ID)
    await admin.say("/admin")
    await admin.tap("admin_settings_menu")
    await admin.tap("admin_settings_group:branding")
    datas = callbacks(admin.last_edit_markup)
    assert "admin_branding_report" in datas and "admin_branding_sync" in datas, datas
    await admin.tap("admin_branding_report")
    report = admin.last_text
    async with session_scope() as session:
        row = await session.get(ShopBot, shop_bot_id)
        owner_row = await session.get(ShopOwner, row.shop_owner_id)
    assert "1 بار" in report, report
    assert (row.bot_username or f"#{shop_bot_id}").lstrip("@") in report, report
    assert str(owner_row.telegram_id) not in report, "شناسهٔ عددیِ کاربر در متنِ ادمین نشت نمی‌کند"
    print("✅ test_owner_check_now_and_admin_report PASSED")


# ============ ۷ — باگِ گزارش‌شده: بیو باید رویِ رباتِ خودِ فروشگاه نوشته شود
async def test_owner_save_targets_own_bot_not_main(main_dp, bot_manager) -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    await _set_branding(ADMIN_TEXT)
    shop = make_shop_bot()
    register_fake_shop_bot(bot_manager, shop_bot_id, shop)
    owner = Chat(main_dp, OWNER_TG_ID)

    await owner.say("⚙️ تنظیماتِ ربات فروشگاه")
    await owner.tap("br_open")
    await owner.tap("br_edit")
    await owner.say("گالریِ گلِ مریم")

    assert shop.session.short_description == f"گالریِ گلِ مریم — {ADMIN_TEXT}", shop.session.short_description
    assert owner.session.bio_updates == [], "رباتِ اصلی هرگز نباید از این مسیر بیو بگیرد"
    assert main_texts.BRANDING_OWNER_SAVED in [m["text"] for m in owner.sent], owner.sent[-2:]

    # رباتِ اتصال‌نکرده ⇒ متن ذخیره می‌شود و پیامِ «در اولین اتصال» می‌رود؛ رباتِ اصلی باز هم دست‌نخورده
    await bot_manager.unregister(shop_bot_id, disable_in_db=False)
    await owner.tap("br_edit")
    await owner.say("گالریِ نقره")
    assert (await _shop_bot(shop_bot_id)).branding_owner_text == "گالریِ نقره"
    assert main_texts.BRANDING_OWNER_SAVED_NOT_CONNECTED in [m["text"] for m in owner.sent], owner.sent[-2:]
    assert owner.session.bio_updates == []
    print("✅ test_owner_save_targets_own_bot_not_main PASSED")


# ============ ۸ — پاسِ دوره‌ای دست‌کاری را برمی‌گرداند و به فروشگاه‌دار خبر می‌دهد
async def test_periodic_pass_restores_tampered_bio(bot_manager, main_bot) -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    await _set_branding(ADMIN_TEXT)
    await _set_synced(None)
    shop = make_shop_bot()
    shop.session.short_description = "بیویِ دستکاری‌شده"
    register_fake_shop_bot(bot_manager, shop_bot_id, shop)

    await scheduler.run_periodic_pass(main_bot, bot_manager)

    assert shop.session.short_description == ADMIN_TEXT, shop.session.short_description
    alerts = [m for m in main_bot.session.sent_messages if m["text"] == main_texts.BOT_BIO_TAMPERED_ALERT]
    assert len(alerts) == 1 and alerts[0]["chat_id"] == OWNER_TG_ID, alerts
    async with session_scope() as session:
        row = await session.get(ShopBot, shop_bot_id)
        assert row.branding_tamper_count == 1 and row.branding_set_at is not None
        admin = await get_admin_settings(session)
        assert admin.branding_synced_at is not None
    print("✅ test_periodic_pass_restores_tampered_bio PASSED")


async def main() -> None:
    main_dp, _shop_dp, bot_manager, main_bot = build_test_dispatchers()
    test_compose_rules()
    test_check_interval_rules()
    test_branding_job_interval()
    await test_apply_to_bot_outcomes()
    await test_main_bot_can_never_receive_a_bio()
    await test_sync_all_counts_alerts_and_audit()
    await test_sync_all_covers_bale_transport_and_owner_text()
    await test_admin_text_change_is_not_counted_as_tampering()
    await test_admin_branding_settings(main_dp)
    await test_owner_branding_screen(main_dp)
    await test_owner_save_targets_own_bot_not_main(main_dp, bot_manager)
    await test_owner_check_now_and_admin_report(main_dp, bot_manager)
    await test_periodic_pass_restores_tampered_bio(bot_manager, main_bot)


if __name__ == "__main__":
    asyncio.run(main())
