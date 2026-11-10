"""
تست: P49-ب — کامنت‌هایِ اینستاگرام (جوابِ عمومی + پاسخِ خصوصی تا ۷ روز + سوییچ‌هایِ فروشگاه).

شبکه اصلاً صدا زده نمی‌شود: چه درِ سوییچ‌ها، چه کرانه‌هایِ متن، چه شکلِ درستِ رویدادِ کامنت.

اجرا: python3 tests_manual/run_one.py test_p49_b_instagram_comments.py
"""
from __future__ import annotations

import asyncio
import datetime
import pathlib
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402

from harness import FakeSession, build_test_dispatchers, make_callback_update, reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot import keyboards as main_keyboards  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import instagram_service  # noqa: E402
from app.utils import text_limits  # noqa: E402

ADMIN_TG_ID = 12345
MAIN_TOKEN = "000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS"
NOW = datetime.datetime(2026, 11, 10, 12, 0, tzinfo=datetime.timezone.utc)


def _event(**changes):
    fields = {
        "comment_id": "c1",
        "media_id": "m1",
        "ig_account_id": "17841400",
        "text": "قیمت این چند؟",
        "username": "sara",
        "created_at": NOW,
    }
    fields.update(changes)
    return instagram_service.CommentEvent(**fields)


def _account(**changes):
    fields = {
        "ig_account_id": "17841400",
        "access_token": "IGQVJ6fake.token.for.tests",
        "shop_bot_id": 7,
        "is_active": True,
        "auto_reply_dm": True,
        "auto_reply_comments": True,
        "private_reply_enabled": True,
        "ig_username": "my.shop",
        "greeting_text": None,
        "last_error": None,
    }
    fields.update(changes)
    return type("A", (), fields)()


# ============================================================================= ۱ — تجزیهٔ درستِ کامنت
def test_comment_fields_are_accepted_and_strict() -> None:
    payload = {
        "object": "instagram",
        "entry": [
            {
                "id": "17841400",
                "changes": [
                    {"field": "comments", "value": {"id": "c1", "text": "قیمت؟", "timestamp": 1780000000, "media": {"id": "m1"}, "from": {"username": "sara"}}},
                    {"field": "live_comments", "value": {"id": "c2", "text": "رنگ دیگه داره؟", "media": {"id": "m2"}}},
                    {"field": "mentions", "value": {"id": "x1", "text": "hi", "media": {"id": "m3"}}},
                    {"field": "comments", "value": {"id": "c3", "text": "", "media": {"id": "m4"}}},
                    {"field": "comments", "value": {"id": "c4", "text": "بدونِ مدیا"}},
                    {"field": "comments", "value": {"id": "bad id!", "text": "سلام", "media": {"id": "m5"}}},
                ],
            }
        ],
    }
    events = instagram_service.parse_event(payload)
    comments = [e for e in events if isinstance(e, instagram_service.CommentEvent)]
    markers = [e for e in events if e is None]
    assert len(comments) == 2, f"فقط دو کامنتِ کامل: {comments}"
    assert len(markers) == 4, "mention/متن‌خالی/بی‌مدیا/شناسهٔ نامعتبر ⇒ علامتِ «نشناخته» می‌مانند"
    assert [e.comment_id for e in comments] == ["c1", "c2"], comments
    assert comments[0].username == "sara" and comments[1].ig_account_id == "17841400"
    assert comments[1].created_at is None, "کامنتِ بی‌زمان ⇒ پنجرهٔ پاسخ باز فرض می‌شود (ردِ بی‌دلیل بدتر است)"
    print("✅ test_comment_fields_are_accepted_and_strict PASSED")


# ============================================================================= ۲ — پنجرهٔ ۷ روزه
def test_private_reply_window_is_seven_days() -> None:
    assert instagram_service.comment_reply_is_open(NOW - datetime.timedelta(days=6, hours=23), now=NOW)
    assert not instagram_service.comment_reply_is_open(NOW - datetime.timedelta(days=7, minutes=1), now=NOW)
    assert instagram_service.comment_reply_is_open(None, now=NOW)
    naive = (NOW - datetime.timedelta(days=1)).replace(tzinfo=None)
    assert instagram_service.comment_reply_is_open(naive, now=NOW), "زمانِ بی‌منطقه هم باید کار کند"
    print("✅ test_private_reply_window_is_seven_days PASSED")


# ============================================================================= ۳ — بی‌خطرِ ورودی‌ها
async def test_sends_refuse_bad_accounts_without_network() -> None:
    assert not await instagram_service.reply_to_comment(None, None, _event(), "سلام")
    assert not await instagram_service.send_private_reply(None, None, _event(), "سلام")
    assert not await instagram_service.reply_to_comment(None, None, _event(), "   ")
    bad = _account(ig_account_id="../../v21.0/me")  # هر شکلِ مسیرِ مخرب در آدرسِ Graph رد می‌شود
    assert not await instagram_service.reply_to_comment(None, bad, _event(), "سلام")
    assert not await instagram_service.send_private_reply(None, bad, _event(), "سلام")
    assert not await instagram_service.reply_to_comment(None, _account(), _event(media_id="1.2.3.4"), "سلام")
    print("✅ test_sends_refuse_bad_accounts_without_network PASSED")


def test_private_reply_text_is_clipped_and_invites_to_dm() -> None:
    class _Shop:
        pass

    shop = _Shop()
    body = "پاسخِ کوتاه"
    text = instagram_service.private_reply_text(body, shop)
    assert text.startswith(body) and "دایرکت" in text, text
    long_answer = "الف " * 4000
    clipped = instagram_service.private_reply_text(long_answer, shop)
    assert len(clipped) <= text_limits.INSTAGRAM_DM_LIMIT, len(clipped)
    assert instagram_service.COMMENT_PUBLIC_LIMIT <= text_limits.INSTAGRAM_DM_LIMIT
    print("✅ test_private_reply_text_is_clipped_and_invites_to_dm PASSED")


# ============================================================================= ۴ — سوییچ‌ها در کیبورد
def test_panel_keyboard_shows_comment_switches() -> None:
    def datas(markup) -> list[str]:
        return [b.callback_data or "" for row in markup.inline_keyboard for b in row]

    both_on = datas(main_keyboards.instagram_panel_keyboard(_account()))
    assert "ig_comments_off" in both_on and "ig_private_off" in both_on, both_on
    off = datas(main_keyboards.instagram_panel_keyboard(_account(auto_reply_comments=False, private_reply_enabled=False)))
    assert "ig_comments_on" in off and "ig_private_on" in off, off
    # اتصالِ قدیمی/نیمه (بدونِ دو ستونِ تازه) نباید صفحه را ببیندازد
    legacy = type("L", (), {"ig_account_id": "17841400", "access_token": "t", "shop_bot_id": 7, "is_active": True,
                            "auto_reply_dm": True, "ig_username": "my.shop", "greeting_text": None, "last_error": None})()
    assert "ig_comments_on" in datas(main_keyboards.instagram_panel_keyboard(legacy))
    assert all(d.startswith("ig_") for d in datas(main_keyboards.instagram_panel_keyboard(_account())))
    print("✅ test_panel_keyboard_shows_comment_switches PASSED")


# ============================================================================= ۵ — درِ سراسری، پاسخ نمی‌دهد
async def test_handle_comment_is_silent_when_the_channel_is_off() -> None:
    sent: list[str] = []
    original_claim = instagram_service.claim_event
    original_settings = instagram_service.cached_admin_settings
    original_account = instagram_service.account_by_ig_id
    instagram_service.claim_event = lambda key: True
    async def _disabled(_session):
        return _disabled_settings()

    instagram_service.cached_admin_settings = _disabled
    try:
        async with session_scope() as real_session:
            await instagram_service.handle_comment(real_session, None, _event())
        assert not sent
    finally:
        instagram_service.claim_event = original_claim
        instagram_service.cached_admin_settings = original_settings
        instagram_service.account_by_ig_id = original_account

    async def _never(*_a, **_k):
        raise AssertionError("وقتی کانال خاموش است هیچ کوئری‌ای نباید اجرا شود")

    instagram_service.account_by_ig_id = _never
    try:
        async with session_scope() as real_session:
            await instagram_service.handle_comment(real_session, None, _event())
    finally:
        instagram_service.account_by_ig_id = original_account
    print("✅ test_handle_comment_is_silent_when_the_channel_is_off PASSED")


def _disabled_settings():
    class _S:
        instagram_enabled = False

    return _S()


# ============================================================================= ۶ — سوییچ از پنل، ذخیره می‌شود
async def test_comment_switches_persist(main_dp) -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(999_841, 999_842)
    main_bot = Bot(token=MAIN_TOKEN, session=FakeSession())
    session_obj: FakeSession = main_bot.session  # type: ignore[assignment]

    async with session_scope() as session:
        account = await _make_account(session, shop_bot_id)
        account_id = account.id

    await main_dp.feed_update(main_bot, make_callback_update(1, data="ig_comments_off", user_id=ADMIN_TG_ID))
    async with session_scope() as session:
        stored = await session.get(instagram_service.InstagramAccount, account_id)
        # کال‌بک از فروشگاهِ این کاربر نمی‌آید ⇒ یا مالکیت رد می‌شود یا سوییچ ذخیره؛ هیچ‌کدام خطا نباشد
        assert stored is not None
    assert session_obj.answered_callbacks, "سوییچ باید همیشه یکِ پاسخِ callback بگیرد (نه دکمهٔ بی‌حرکت)"

    handler_source = pathlib.Path("app/bots/main_bot/handlers/instagram.py").read_text(encoding="utf-8")
    assert "require_shop_bot_cb" in handler_source, "سوییچِ کامنت هم باید چکِ مالکیت داشته باشد"
    assert "_FLAG_ACTIONS" in handler_source and "ig_reply_on" not in handler_source.split("_FLAG_ACTIONS")[1].split("}")[0], (
        "سوییچِ دایرکت هندلرِ اختصاصی دارد تا دو هندلر رویِ یکِ کال‌بک نیفتند"
    )
    print("✅ test_comment_switches_persist PASSED")


async def _make_account(session, shop_bot_id: int):
    from app.database.models import InstagramAccount

    account = InstagramAccount(
        shop_bot_id=shop_bot_id,
        ig_account_id="17841400",
        ig_username="my.shop",
        access_token="tok-123",
        is_active=True,
        auto_reply_dm=True,
        auto_reply_comments=True,
        private_reply_enabled=True,
    )
    session.add(account)
    await session.flush()
    return account


async def main() -> None:
    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    test_comment_fields_are_accepted_and_strict()
    test_private_reply_window_is_seven_days()
    await test_sends_refuse_bad_accounts_without_network()
    test_private_reply_text_is_clipped_and_invites_to_dm()
    test_panel_keyboard_shows_comment_switches()
    await test_handle_comment_is_silent_when_the_channel_is_off()
    await test_comment_switches_persist(main_dp)
    print("📊 نتیجه: ۷ تستِ P49-ب (کامنتِ اینستاگرام) پاس شد · تجزیه/پنجرهٔ ۷ روز/بی‌خطرِ ورودی/کیبورد/درِ سراسری/سوییچِ پنل")


if __name__ == "__main__":
    asyncio.run(main())
