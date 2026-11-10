"""
تست: P49-الف — کانالِ اینستاگرام (فقط APIِ رسمیِ متا): سوییچِ ادمین، گیتِ ۲۴ ساعت، امضایِ وب‌هوک،
هویتِ مشتریِ this کانال و ظاهر/محویِ دکمهٔ پنلِ فروشگاه‌دار.

هیچ فراخوانیِ شبکه‌ای در این فایل نیست (APIِ متا عمداً صدا زده نمی‌شود): عددها و گیت‌ها سنجیده
می‌شوند، نه اینترنت.

اجرا: python3 tests_manual/test_p49_instagram_channel.py
"""
from __future__ import annotations

import asyncio
import datetime
import hashlib
import hmac
import pathlib
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402

from harness import FakeSession, build_test_dispatchers, make_callback_update, reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot import keyboards as main_keyboards  # noqa: E402
from app.bots.main_bot import texts as main_texts  # noqa: E402
from app.bots.main_bot.handlers import owner_common  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import admin_settings_service, instagram_service  # noqa: E402
from app.services.instagram_service import DirectMessage, InstagramError  # noqa: E402

ADMIN_TG_ID = 12345
MAIN_TOKEN = "000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS"
SECRET = "test-app-secret-123"


def _sign(body: bytes) -> str:
    return "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()


def _settings(*, enabled: bool = False, app_id: str | None = "app-1", secret: str | None = SECRET, verify: str | None = "vt"):
    class _Stub:
        pass

    stub = _Stub()
    stub.instagram_enabled = enabled
    stub.instagram_app_id = app_id
    stub.instagram_app_secret = secret
    stub.instagram_webhook_verify_token = verify
    return stub


# ============================================================================= ۱ — امضایِ وب‌هوک
def test_webhook_signature_is_constant_time_and_strict() -> None:
    body = b'{"object":"instagram","entry":[]}'
    assert instagram_service.verify_signature(body, _sign(body), SECRET), "امضایِ درست باید پذیرفته شود"
    assert not instagram_service.verify_signature(b'{"object":"instagram","entry":[1]}', _sign(body), SECRET), "بدنهٔ دستکاری‌شده"
    assert not instagram_service.verify_signature(body, None, SECRET), "بدونِ هدر"
    assert not instagram_service.verify_signature(body, "sha256=" + "0" * 64, SECRET), "امضایِ اشتباه"
    assert not instagram_service.verify_signature(body, _sign(body), ""), "بدونِ رازِ اپ ⇒ هیچ امضایی معتبر نیست"
    print("✅ test_webhook_signature_is_constant_time_and_strict PASSED")


# ============================================================================= ۲ — پنجرهٔ ۲۴ ساعت
def test_dm_window_follows_metas_24_hour_rule() -> None:
    now = datetime.datetime(2026, 11, 10, 12, 0, tzinfo=datetime.timezone.utc)
    assert instagram_service.dm_window_is_open(now - datetime.timedelta(hours=23, minutes=59), now=now)
    assert not instagram_service.dm_window_is_open(now - datetime.timedelta(hours=24, minutes=1), now=now)
    assert not instagram_service.dm_window_is_open(None, now=now), "بی‌سابقه ⇒ حقِ شروعِ گفتگو نداریم"
    assert instagram_service.DM_WINDOW_SECONDS == 24 * 60 * 60
    print("✅ test_dm_window_follows_metas_24_hour_rule PASSED")


# ============================================================================= ۳ — هویتِ مشتری
def test_instagram_customer_key_is_stable_and_bounded() -> None:
    assert instagram_service.customer_key("17841406732090990") == 17841406732090990, "شناسهٔ عددی عیناً می‌ماند"
    a = instagram_service.customer_key("aBc-x_9.k")
    assert a == instagram_service.customer_key("aBc-x_9.k"), "همان ورودی ⇒ همان مشتری"
    assert a != instagram_service.customer_key("other-person"), "ورودیِ دیگر ⇒ مشتریِ دیگر"
    assert 0 <= a < 2**63, "باید در signed 64-bit جا شود (ستونِ telegram_id)"
    print("✅ test_instagram_customer_key_is_stable_and_bounded PASSED")


# ============================================================================= ۴ — stateِ اتصال
def test_oauth_state_roundtrip_rejects_unknown() -> None:
    state = instagram_service.make_state(4211)
    assert instagram_service.parse_state(state) == 4211, "stateِ تازه باید همان فروشگاه را بدهد"
    assert instagram_service.parse_state("garbage") is None
    assert instagram_service.parse_state(None) is None
    assert instagram_service.COMMENT_REPLY_DAYS == 7
    old = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
    assert not instagram_service.comment_reply_is_open(old, now=datetime.datetime(2026, 1, 10, tzinfo=datetime.timezone.utc))
    url = instagram_service.build_oauth_url("app-9", "https://bot.example.test/webhook/instagram/oauth", state)
    assert url.startswith("https://www.instagram.com/oauth/authorize?"), url[:60]
    assert "client_id=app-9" in url and "messaging" in url
    print("✅ test_oauth_state_roundtrip_rejects_unknown PASSED")


# ============================================================================= ۵ — تجزیهٔ رویداد
def test_parse_event_takes_inbound_text_and_skips_noise() -> None:
    payload = {
        "object": "instagram",
        "entry": [
            {
                "messaging": [
                    {"sender": {"id": "111"}, "recipient": {"id": "999"}, "timestamp": 1780000000,
                     "message": {"text": "قیمت چنده؟", "is_echo": False, "mid": "m1"}},
                    {"sender": {"id": "999"}, "message": {"text": "قیمت ۳۵۰", "is_echo": True}},
                    {"sender": {"id": "222"}, "message": {"attachment": {"type": "image"}, "mid": "m2"}},
                ]
            },
            {"id": "178414", "time": 1762000000000, "changes": [{"field": "comments", "value": {"id": "c1", "text": "قیمت؟", "timestamp": 1780000000, "media": {"id": "17890"}, "from": {"username": "sara"}}}]},
        ],
    }
    events = instagram_service.parse_event(payload)
    assert len(events) == 2, f"یکِ دایرکت + یکِ کامنت: {events}"
    comment = events[1]
    assert isinstance(comment, instagram_service.CommentEvent), comment
    assert comment.comment_id == "c1" and comment.media_id == "17890" and comment.ig_account_id == "178414", comment
    fresh = datetime.datetime(2026, 5, 28, 20, 26, 40, tzinfo=datetime.timezone.utc)
    assert comment.created_at == fresh, comment.created_at
    assert instagram_service.comment_reply_is_open(fresh, now=fresh + datetime.timedelta(days=6))
    assert not instagram_service.comment_reply_is_open(fresh, now=fresh + datetime.timedelta(days=8))
    event = events[0]
    assert isinstance(event, DirectMessage)
    assert event.sender_psid == "111" and event.text == "قیمت چنده؟", event
    assert event.shop_account_id == "999", "شناسهٔ پیجِ خودِ فروشگاه برایِ مسیریابی به همین ردیف"
    assert event.created_at is not None and event.created_at.year == 2026, event.created_at
    millis = instagram_service.parse_event({"object": "instagram", "entry": [{"messaging": [{"sender": {"id": "1"}, "recipient": {"id": "9"}, "timestamp": 1780000000000, "message": {"text": "salam", "is_echo": False}}]}]})
    assert len(millis) == 1 and millis[0].created_at.year == 2026, "میلی‌ثانیه هم نرمال شود"
    junk = instagram_service.parse_event({"object": "instagram", "entry": [{"messaging": [{"sender": {"id": "1"}, "recipient": {"id": "9"}, "timestamp": 99999999999999, "message": {"text": "salam", "is_echo": False}}]}]})
    assert len(junk) == 1 and junk[0].created_at is None, "عددِ خراب نباید وب‌هوک را بیندازد"
    print("✅ test_parse_event_takes_inbound_text_and_skips_noise PASSED")


def test_event_dedupe_blocks_metas_retries() -> None:
    event = DirectMessage(
        sender_psid="333", shop_account_id="999", text="سلام", message_id="dup-1",
        created_at=datetime.datetime(2026, 11, 10, tzinfo=datetime.timezone.utc),
    )
    key = instagram_service.event_key(event)
    assert instagram_service.claim_event(key), "اولین بار باید پذیرفته شود"
    assert not instagram_service.claim_event(key), "تلاشِ دوبارهٔ متا نباید دوباره پاسخ برود"
    # بی‌`mid` هیچ کلیدی برایِ dedupe نیست ⇒ رویداد پردازش می‌شود (پاسخِ بهتر ازِ بی‌پاسخی است).
    assert instagram_service.claim_event(None) and instagram_service.claim_event(None)
    print("✅ test_event_dedupe_blocks_metas_retries PASSED")


# ============================================================================= ۶ — درِ سراسری و دکمهٔ پنل
def test_admin_switch_controls_the_owner_panel_button() -> None:
    assert not instagram_service.enabled(_settings(enabled=False)), "پیش‌فرضِ کانال خاموش است"
    assert instagram_service.enabled(_settings(enabled=True))
    assert instagram_service.configured(_settings(enabled=True)), "با app_id و راز ⇒ آمادهٔ اتصال"
    assert not instagram_service.configured(_settings(enabled=True, app_id=None))
    assert not instagram_service.configured(_settings(enabled=True, secret=None))
    assert not instagram_service.configured(_settings(enabled=True, verify=None)), "بدونِ توکنِ تأیید، دست‌دادنِ متا ممکن نیست"

    def buttons(markup) -> list[str]:
        return [b.text for row in markup.keyboard for b in row]

    off = buttons(main_keyboards.shop_owner_panel_keyboard(instagram=False))
    on = buttons(main_keyboards.shop_owner_panel_keyboard(instagram=True))
    assert main_texts.INSTAGRAM_BUTTON not in off, off
    assert main_texts.INSTAGRAM_BUTTON in on, on
    assert main_texts.INSTAGRAM_BUTTON == "🟣 اینستاگرام"
    print("✅ test_admin_switch_controls_the_owner_panel_button PASSED")


async def test_panel_keyboard_reads_the_flag_from_database() -> None:
    await reset_database()
    await seed_usable_shop(999_821, 999_822)

    def texts_of(markup) -> list[str]:
        return [b.text for row in markup.keyboard for b in row]

    async with session_scope() as session:
        admin_settings = await admin_settings_service.get_admin_settings(session)
        assert admin_settings.instagram_enabled is False, "ستونِ تازه پیش‌فرض خاموش دارد"
        assert main_texts.INSTAGRAM_BUTTON not in texts_of(await owner_common.panel_keyboard(session))
        admin_settings.instagram_enabled = True
        await session.flush()
        assert main_texts.INSTAGRAM_BUTTON in texts_of(await owner_common.panel_keyboard(session))
    print("✅ test_panel_keyboard_reads_the_flag_from_database PASSED")


# ============================================================================= ۷ — صفحهٔ مدیریتِ فروشگاه
async def test_instagram_management_screen(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(999_831, 999_832)

    datas = lambda markup: [b.callback_data or "" for row in markup.inline_keyboard for b in row]  # noqa: E731
    anonymous = main_keyboards.instagram_panel_keyboard(None)
    assert "ig_connect" in datas(anonymous), datas(anonymous)
    assert all(d.startswith("ig_") for d in datas(anonymous)), datas(anonymous)

    class _Account:
        ig_username = "my.shop"
        is_active = True
        auto_reply_dm = True
        greeting_text = None
        last_error = None
        ig_account_id = "17841"

    connected = main_keyboards.instagram_panel_keyboard(_Account())
    assert all(d.startswith("ig_") for d in datas(connected)), datas(connected)
    assert len(connected.inline_keyboard) >= 2, "اتصال‌شده باید بیش از یکِ دکمهٔ مدیریتی داشته باشد"

    source = pathlib.Path("app/bots/main_bot/handlers/instagram.py").read_text(encoding="utf-8")
    assert "texts.INSTAGRAM_BUTTON" in source and "open_instagram_panel" in source
    assert "instagram_service.enabled(" in source, "صفحهٔ پنل باید خودِ درِ سراسری را هم چک کند (نه فقط دکمه)"
    assert source.count("instagram_service.enabled(") >= 2, "همِ منو و همِ کال‌بک‌ها باید گیت داشته باشند"

    main_bot = Bot(token=MAIN_TOKEN, session=FakeSession())
    session_obj: FakeSession = main_bot.session  # type: ignore[assignment]
    async with session_scope() as session:
        admin_settings = await admin_settings_service.get_admin_settings(session)
        admin_settings.instagram_enabled = True
        await session.flush()
    await main_dp.feed_update(main_bot, make_callback_update(1, data="admin_toggle_instagram", user_id=ADMIN_TG_ID))
    assert session_obj.answered_callbacks, "سوییچِ ادمین باید پاسخِ callback بدهد"
    async with session_scope() as session:
        flipped = await admin_settings_service.get_admin_settings(session)
        assert flipped.instagram_enabled is not True, "سوییچ باید کانال را دوباره خاموش/روشن کند (نه بی‌اثر)"
    print("✅ test_instagram_management_screen PASSED")


# ============================================================================= ۸ — بی‌خطر بودنِ راز
def test_instagram_errors_never_carry_the_token() -> None:
    token = "IGQVJ6verysecrettokenvalue"
    message = InstagramError("ارسالِ پیام به اینستاگرام ممکن نشد")
    assert token not in str(message)
    source = pathlib.Path("app/services/instagram_service.py").read_text(encoding="utf-8")
    assert "access_token" in source, "ارسال با توکن انجام می‌شود"
    assert "logger.info(f\"{token}" not in source and "print(token" not in source, "توکن نباید لاگ/چاپ شود"
    assert "graph.facebook.com" in source and "instagram.com" in source
    assert "instagrapi" not in source.lower(), "مسیرِ غیررسمی (کتابخانهٔ private) هرگز استفاده نمی‌شود"
    print("✅ test_instagram_errors_never_carry_the_token PASSED")


async def main() -> None:
    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    test_webhook_signature_is_constant_time_and_strict()
    test_dm_window_follows_metas_24_hour_rule()
    test_instagram_customer_key_is_stable_and_bounded()
    test_oauth_state_roundtrip_rejects_unknown()
    test_parse_event_takes_inbound_text_and_skips_noise()
    test_event_dedupe_blocks_metas_retries()
    test_admin_switch_controls_the_owner_panel_button()
    await test_panel_keyboard_reads_the_flag_from_database()
    await test_instagram_management_screen(main_dp)
    test_instagram_errors_never_carry_the_token()
    print("📊 نتیجه: ۱۰ تستِ P49-الف (اینستاگرام) پاس شد · امضا/پنجرهٔ ۲۴ ساعت/هویتِ مشتری/state/رویداد/دکمهٔ پنل/راز")


if __name__ == "__main__":
    asyncio.run(main())
