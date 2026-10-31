"""
تست: P18 · A2 — بیوگرافیِ اجباریِ ربات‌هایِ فروشگاهی (برندینگ).

پوشش:
۱. خالص: ترکیبِ «متنِ فروشگاه‌دار — متنِ ادمین» با سقفِ ۱۲۰؛ اگر جا نشد متنِ فروشگاه‌دار کوتاه
   می‌شود و متنِ ادمین هرگز. بدونِ متنِ ادمین هیچ نوشتنی انجام نمی‌شود.
۲. `apply_to_bot`: unchanged/applied/tampered/skipped/error — و خطایِ شبکه هرگز کرش نمی‌کند.
۳. `sync_all`: شمارش‌ها، اعلانِ نرخ‌محدود به فروشگاه‌دار (یک‌بار در ۲۴ ساعت)، ثبتِ ممیزی و شمارنده‌یِ تخلف.
۴. پنلِ ادمین: اعتبارسنجیِ ۶۰ نویسه، ذخیره، ممیزی، «ذخیره شد» بدونِ رباتِ وصل‌شده.
۵. پنلِ فروشگاه‌دار: «🧴 بیوگرافیِ ربات» → متنِ خودت، ردِّ بلند، «خالی» برایِ پاک کردن، برگشت.
۶. جابِ ۶ ساعته: `is_due`.

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

from harness import build_test_dispatchers, reset_database  # noqa: E402
from phase4_helpers import Chat  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot import texts as main_texts  # noqa: E402
from app.database.models import AuditEventType, AuditLogEntry, ShopBot  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import bot_branding_service as branding  # noqa: E402
from app.services.admin_settings_service import get_admin_settings  # noqa: E402

ADMIN_TG_ID = 12345
OWNER_TG_ID = 999_931
SHOP_BOT_TG_ID = 999_932
OTHER_OWNER_TG_ID = 999_941
OTHER_SHOP_BOT_TG_ID = 999_942
ADMIN_TEXT = "ساخته‌شده با @kasbokar"


class _BioBot:
    """جانشینِ aiogram.Bot فقط برایِ دو متدِ بیوگرافی."""

    def __init__(self, initial: str = "", fail_on: str | None = None):
        self.bio = initial
        self.fail_on = fail_on
        self.set_calls = 0
        self.get_calls = 0

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
    def __init__(self, bots: dict[int, _BioBot]):
        self._bots = bots

    def registered_shop_bot_ids(self) -> list[int]:
        return list(self._bots)

    def get_bot(self, shop_bot_id: int):
        return self._bots.get(shop_bot_id)


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


# ============================================================================= ۱ — ترکیب
def test_compose_rules() -> None:
    assert branding.compose("فروشگاهِ علی", "") == ""
    assert branding.compose("فروشگاهِ علی", None) == "", "بدونِ متنِ ادمین هیچ کاری نمی‌کنیم"
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

    assert branding.normalize_admin_text("  " + ADMIN_TEXT + "  ") == ADMIN_TEXT
    assert branding.normalize_admin_text("خالی") is None and branding.normalize_admin_text(None) is None
    assert branding.normalize_admin_text("ب" * 70) == "ب" * 60, "سقفِ ۶۰ با برش اعمال می‌شود"
    assert branding.valid_admin_text("ب" * 60) and not branding.valid_admin_text("ب" * 61)
    assert branding.valid_owner_text("ی" * 120) and not branding.valid_owner_text("ی" * 121)
    print("✅ test_compose_rules PASSED")


# ============================================================================= ۲ — یک ربات
async def test_apply_to_bot_outcomes() -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    await _set_owner_text(shop_bot_id, "فروشگاهِ علی")
    shop_bot = await _shop_bot(shop_bot_id)
    expected = f"فروشگاهِ علی — {ADMIN_TEXT}"

    bot = _BioBot(initial=expected)
    assert await branding.apply_to_bot(bot, shop_bot, ADMIN_TEXT) == ("unchanged", expected)
    assert bot.set_calls == 0, "وقتی درست است چیزی نوشته نمی‌شود"

    bot = _BioBot(initial="")
    assert await branding.apply_to_bot(bot, shop_bot, ADMIN_TEXT) == ("applied", "")
    assert bot.bio == expected

    bot = _BioBot(initial="بیویِ دستکاری‌شده")
    outcome, previous = await branding.apply_to_bot(bot, shop_bot, ADMIN_TEXT)
    assert (outcome, previous) == ("tampered", "بیویِ دستکاری‌شده") and bot.bio == expected

    bot = _BioBot(initial="هرچی")
    assert await branding.apply_to_bot(bot, shop_bot, None) == ("skipped", "")
    assert bot.get_calls == 0 and bot.set_calls == 0, "متنِ ادمین خالی ⇒ هیچ درخواستی به تلگرام"

    failing = _BioBot(initial="x", fail_on="get")
    assert await branding.apply_to_bot(failing, shop_bot, ADMIN_TEXT) == ("error", "")
    failing = _BioBot(initial="x", fail_on="set")
    outcome, _prev = await branding.apply_to_bot(failing, shop_bot, ADMIN_TEXT)
    assert outcome == "error", "خطایِ نوشتن فقط لاگ می‌شود، استثنا نه"
    print("✅ test_apply_to_bot_outcomes PASSED")


# ============================================================================= ۳ — همگام‌سازیِ همه
async def test_sync_all_counts_alerts_and_audit() -> None:
    await reset_database()
    branding.reset_alert_cache()
    first = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    second = await seed_usable_shop(OTHER_OWNER_TG_ID, OTHER_SHOP_BOT_TG_ID)
    await _set_owner_text(first, "فروشگاهِ الف")
    await _set_branding(ADMIN_TEXT)

    bots = {first: _BioBot(initial="دستکاری‌شده"), second: _BioBot(initial="")}
    main_bot = _AlertingBot()
    async with session_scope() as session:
        counts = await branding.sync_all(session, _Manager(bots), main_bot)

    assert counts["total"] == 2 and counts["tampered"] == 1 and counts["applied"] == 1, counts
    assert counts["unchanged"] == 0 and counts["error"] == 0
    assert bots[first].bio == f"فروشگاهِ الف — {ADMIN_TEXT}" and bots[second].bio == ADMIN_TEXT
    assert [chat for chat, _ in main_bot.sent] == [OWNER_TG_ID], "فقط به صاحبِ رباتِ دستکاری‌شده"
    async with session_scope() as session:
        row = (await session.execute(select(ShopBot).where(ShopBot.id == first))).scalar_one()
        assert row.branding_tamper_count == 1, "شمارنده‌یِ تخلف"
        entries = list((await session.execute(
            select(AuditLogEntry).where(AuditLogEntry.event_type == AuditEventType.BOT_BIO_TAMPERED.value)
        )).scalars().all())
        assert len(entries) == 1 and entries[0].shop_bot_id == first
        admin = await get_admin_settings(session)
        assert admin.branding_synced_at is not None

    # دوباره ⇒ همه unchanged و هیچ اعلانِ تکراری
    async with session_scope() as session:
        counts = await branding.sync_all(session, _Manager(bots), main_bot)
    assert counts["unchanged"] == 2 and counts["tampered"] == 0, counts
    assert len(main_bot.sent) == 1, "اعلانِ دوباره در کول‌دان فرستاده نمی‌شود"

    # دست‌کاریِ دوباره در همان ۲۴ ساعت ⇒ بازنویسی می‌شود ولی اعلانِ تازه نمی‌رود
    bots[first].bio = "دوباره دستکاری"
    async with session_scope() as session:
        counts = await branding.sync_all(session, _Manager(bots), main_bot)
    assert counts["tampered"] == 1
    assert len(main_bot.sent) == 1, "اعلان نرخ‌محدود است"
    assert bots[first].bio == f"فروشگاهِ الف — {ADMIN_TEXT}"
    async with session_scope() as session:
        row = (await session.execute(select(ShopBot).where(ShopBot.id == first))).scalar_one()
        assert row.branding_tamper_count == 2

    # بدونِ متنِ ادمین ⇒ هیچ درخواستی
    await _set_branding(None)
    spy = _BioBot(initial="هرچی")
    async with session_scope() as session:
        counts = await branding.sync_all(session, _Manager({first: spy}), main_bot)
    assert counts == {"total": 0, "applied": 0, "tampered": 0, "unchanged": 0, "skipped": 0, "error": 0}, counts
    assert spy.get_calls == 0 and spy.bio == "هرچی"
    print("✅ test_sync_all_counts_alerts_and_audit PASSED")


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
    branding.reset_alert_cache()
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

    await owner.say("خالی")
    assert (await _shop_bot(shop_bot_id)).branding_owner_text is None
    await owner.tap("br_back")
    assert "مدتِ تجمیعِ پیام‌ها" in owner.last_edit_text
    print("✅ test_owner_branding_screen PASSED")


# ============================================================================= ۶ — جابِ دوره‌ای
def test_branding_job_interval() -> None:
    now = datetime.datetime(2026, 11, 1, 12, 0, tzinfo=datetime.timezone.utc)
    assert branding.is_due(None, now) is True
    assert branding.is_due(now - datetime.timedelta(hours=5, minutes=59), now) is False
    assert branding.is_due(now - datetime.timedelta(hours=6), now) is True
    assert branding.is_due(now - datetime.timedelta(hours=30), now) is True
    assert branding.is_due((now - datetime.timedelta(hours=7)).replace(tzinfo=None), now) is True, "naive ⇒ UTC فرض می‌شود"
    print("✅ test_branding_job_interval PASSED")


async def main() -> None:
    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    test_compose_rules()
    test_branding_job_interval()
    await test_apply_to_bot_outcomes()
    await test_sync_all_counts_alerts_and_audit()
    await test_admin_branding_settings(main_dp)
    await test_owner_branding_screen(main_dp)


if __name__ == "__main__":
    asyncio.run(main())
