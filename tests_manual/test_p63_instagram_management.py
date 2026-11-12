"""پ۶۳ · خواستهٔ مالکِ محصول: پنلِ مدیریتیِ اینستاگرام در پنلِ *خودِ* فروشگاه (حلقهٔ دوم).

پوششِ داده‌شده:
۱. `is_muted` / `mute_until` فقط تا زمانی که مهلت نرسیده خاموش می‌گویند (NULL، گذشته، آینده).
۲. درِ هرِ دو مسیر (کامنت و دایرکت) **پیش ازِ هرِ هزینه** می‌بندد: وقتی کانال خاموشِ موقت است،
   هیچِ کوئریِ فروشگاه، هیچِ فراخوانِ AI و هیچِ پیامی ساخته نمی‌شود (ادعایِ منفیِ واقعی، نه متنی).
۳. `set_mute` فقط ستونِ mute را عوض می‌کند: اتصال، توکن، سوییچ‌ها و متنِ هوشمندسازی دست‌نخورده
   می‌مانند و هر دو تغییر در ممیزی ثبت می‌شود.
۴. `activity_summary` فقط دایرکتِ *همینِ* فروشگاه را می‌شمارد (پنجرهٔ ۲۴ ساعت و ۷ روز،
   گفتگوهایِ متمایز) و مشتریِ تلگرامی یا فروشگاهِ دیگر وارد عدد نمی‌شود.
۵. جریانِ واقعیِ پنل: «⏸ خاموش‌سازیِ موقت» ← مهلت ← «✅ رویِ همان مهلت» ← «▶️ آزاد کردن» ←
   بازگشت به صفحهٔ اینستاگرام؛ ورودیِ خراب (`ig_mute:abc` و مهلتِ بیرونِ فهرست) رد می‌شود و
   هیچِ ستونی را عوض نمی‌کند؛ کال‌بکِ فروشگاهِ دیگر به ردیفِ اینِ فروشگاه نمی‌رسد.
۶. «📊 فعالیتِ اینستاگرام» عددِ جلالی + صراحتِ «کامنت‌ها شمارش نمی‌شوند» را نشان می‌دهد و
   تازه‌سازی دوباره می‌خواند.
۷. کیبورد: بودجهٔ ۶۴ بایتی و دو دکمهٔ تازه فقط وقتی اتصال برقرار است در می‌آیند.

اجرا: python3 tests_manual/run_one.py test_p63_instagram_management.py
"""
from __future__ import annotations

import asyncio
import datetime as dt
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from sqlalchemy import select  # noqa: E402
from harness import build_test_dispatchers, reset_database  # noqa: E402
from phase4_helpers import Chat, callbacks  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot import keyboards, texts  # noqa: E402
from app.database.models import (  # noqa: E402
    AuditEventType, AuditLogEntry, ConversationMessage, InstagramAccount,
)
from app.database.session import session_scope  # noqa: E402
from app.services import (  # noqa: E402
    admin_settings_service, customer_service, instagram_service, platform_service, shop_owner_service,
)

OWNER_TG_ID = 996_301
SHOP_BOT_TG_ID = 996_302
OTHER_OWNER_TG_ID = 996_303
OTHER_SHOP_TG_ID = 996_304
NOW = dt.datetime(2026, 11, 12, 9, 0, tzinfo=dt.timezone.utc)


def _edit_markup(chat) -> object:
    """کیبوردِ آخرین ویرایش (بعد ازِ tap پیام تازه‌ای فرستاده نمی‌شود، پس `last_markup` چیزی نیست)."""
    return chat.edits[-1]["reply_markup"]


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
        "instructions": "",
        "muted_until": None,
    }
    fields.update(changes)
    return type("A", (), fields)()


def _settings_on():
    class _S:
        instagram_enabled = True
        instagram_app_id = "1234567890"
        instagram_app_secret = "secret-for-tests"
        instagram_platform_instructions = ""
        maintenance_mode = False
        public_base_url = "https://example.test"

    return _S()


def _comment_event():
    return instagram_service.CommentEvent(
        comment_id="c1", media_id="m1", ig_account_id="17841400", text="قیمت این چند؟",
        username="sara", created_at=NOW,
    )


def _dm_event():
    return instagram_service.DirectMessage(
        shop_account_id="17841400", sender_psid="12345:54321", text="سلام", message_id="d1", created_at=NOW
    )


async def _seed_two_shops() -> tuple[int, int]:
    """دو فروشگاهِ قابلِ استفاده با کانالِ رونمایی‌شده و اتصالِ برقرار (دیتابیسِ تمیز)."""
    await reset_database()
    shop_a = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    shop_b = await seed_usable_shop(OTHER_OWNER_TG_ID, OTHER_SHOP_TG_ID)
    async with session_scope() as session:
        admin_settings = await admin_settings_service.get_admin_settings(session)
        admin_settings.instagram_enabled = True
        admin_settings.instagram_app_id = "1234567890"
        owner_b = await shop_owner_service.get_by_telegram_id(session, OTHER_OWNER_TG_ID)
        await shop_owner_service.set_business_mode(session, owner_b, "consultation")
        for shop_bot_id in (shop_a, shop_b):
            session.add(
                InstagramAccount(
                    shop_bot_id=shop_bot_id, ig_account_id=f"178414{shop_bot_id}", ig_username="my.shop",
                    access_token="IGQVJ6fake.token.for.tests", is_active=True, auto_reply_dm=True,
                    auto_reply_comments=True, private_reply_enabled=True,
                )
            )
        await session.flush()
    return shop_a, shop_b


async def _account_row(shop_bot_id: int) -> InstagramAccount:
    async with session_scope() as session:
        return (
            await session.execute(select(InstagramAccount).where(InstagramAccount.shop_bot_id == shop_bot_id))
        ).scalar_one()


async def _audit_details(shop_bot_id: int) -> list[str]:
    async with session_scope() as session:
        rows = (
            await session.execute(
                select(AuditLogEntry.details).where(
                    AuditLogEntry.shop_bot_id == shop_bot_id,
                    AuditLogEntry.event_type == AuditEventType.INSTAGRAM_TOGGLED,
                )
            )
        ).scalars().all()
    return list(rows)


async def test_mute_helpers_are_time_scoped() -> None:
    assert instagram_service.is_muted(_account()) is False, "NULL یعنی روشن"
    assert instagram_service.mute_until(_account()) is None
    future = _account(muted_until=NOW + dt.timedelta(hours=5))
    assert instagram_service.is_muted(future, NOW) is True
    assert instagram_service.mute_until(future, NOW) == future.muted_until
    past = _account(muted_until=NOW - dt.timedelta(seconds=1))
    assert instagram_service.is_muted(past, NOW) is False, "مهلتِ گذشته خودش آزاد می‌شود"
    assert instagram_service.mute_until(past, NOW) is None
    naive = _account(muted_until=dt.datetime(2026, 11, 12, 14, 0))
    assert instagram_service.is_muted(naive, NOW) is True, "ستونِ naive هم با UTC مقایسه می‌شود"
    assert instagram_service.is_muted(None) is False
    print("PASS test_mute_helpers_are_time_scoped")


async def test_mute_gates_both_paths_before_any_cost() -> None:
    original_claim = instagram_service.claim_event
    original_settings = instagram_service.cached_admin_settings
    original_account = instagram_service.account_by_ig_id
    original_shop_bot = instagram_service.shop_bot_service.get_by_id
    seen: list[str] = []

    async def _settings(_session):
        return _settings_on()

    async def _shop_bot(_session, _shop_bot_id):
        seen.append("shop_bot")
        return None

    instagram_service.claim_event = lambda key: True
    instagram_service.cached_admin_settings = _settings
    instagram_service.shop_bot_service.get_by_id = _shop_bot
    try:
        for account, label in (
            # درِ واقعی با ساعتِ زندهٔ پروسه مقایسه می‌کند ⇒ اینجا مهلت *واقعاً* آینده لازم است
            (_account(muted_until=dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=2)), "خاموش"),
            (_account(), "روشن"),
        ):
            async def _account_for(_session, _ig_id, _a=account):
                return _a

            instagram_service.account_by_ig_id = _account_for
            async with session_scope() as session:
                await instagram_service.handle_comment(session, None, _comment_event())
                await instagram_service.handle_inbound(session, None, _dm_event())
            if label == "خاموش":
                assert seen == [], "کانالِ خاموش نباید به کوئریِ فروشگاه برسد"
            else:
                assert seen == ["shop_bot", "shop_bot"], "کانالِ روشن مثلِ قبل ادامه می‌دهد"
                seen.clear()
    finally:
        instagram_service.claim_event = original_claim
        instagram_service.cached_admin_settings = original_settings
        instagram_service.account_by_ig_id = original_account
        instagram_service.shop_bot_service.get_by_id = original_shop_bot
    print("PASS test_mute_gates_both_paths_before_any_cost")


async def test_set_mute_persists_and_audits_only_the_mute_column() -> None:
    shop_a, _shop_b = await _seed_two_shops()
    before = await _account_row(shop_a)
    async with session_scope() as session:
        account = (
            await session.execute(select(InstagramAccount).where(InstagramAccount.shop_bot_id == shop_a))
        ).scalar_one()
        account.auto_reply_dm = False
        account.instructions = "قیمت نگویید"
        await session.flush()
    until = await _set_mute(shop_a, 6)
    assert until is not None and abs((until - (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=6))).total_seconds()) < 60
    after = await _account_row(shop_a)
    assert after.auto_reply_dm is False and after.auto_reply_comments is True
    assert after.instructions == "قیمت نگویید", "متنِ هوشمندسازی پاک نمی‌شود"
    assert after.access_token == before.access_token and after.is_active is True, "اتصال و توکن دست‌نخورده"
    assert after.muted_until is not None
    details = await _audit_details(shop_a)
    assert any("خاموش تا" in item for item in details), details

    released = await _set_mute(shop_a, None)
    assert released is None
    after = await _account_row(shop_a)
    assert after.muted_until is None
    details = await _audit_details(shop_a)
    assert any("لغوِ خاموشیِ موقت" in item for item in details), details
    print("PASS test_set_mute_persists_and_audits_only_the_mute_column")


async def _set_mute(shop_bot_id: int, hours: int | None):
    async with session_scope() as session:
        account = (
            await session.execute(select(InstagramAccount).where(InstagramAccount.shop_bot_id == shop_bot_id))
        ).scalar_one()
        result = await instagram_service.set_mute(session, account, hours, actor_telegram_id=OWNER_TG_ID)
        await session.commit()
    return result


async def test_activity_summary_counts_only_instagram_of_this_shop() -> None:
    shop_a, shop_b = await _seed_two_shops()
    async with session_scope() as session:
        # دو مشتریِ اینستاگرامیِ فروشگاه A (اولی دو پیام در ۲۴ ساعت، دومی یک پیام در ۳ روز و یکی در ۳۰ روز)
        # + یک مشتریِ تلگرامیِ همان فروشگاه + یک مشتریِ اینستاگرامیِ فروشگاه B
        ids = []
        for index, platform in ((0, platform_service.INSTAGRAM), (1, platform_service.INSTAGRAM), (2, "telegram")):
            customer = await customer_service.get_or_create_customer(
                session, shop_a, 996300 + index, f"مشتری{index}", None, platform=platform
            )
            ids.append(customer.id)
        other_id = (
            await customer_service.get_or_create_customer(
                session, shop_b, 996399, "فروشگاهِ دیگر", None, platform=platform_service.INSTAGRAM
            )
        ).id
        rows = [
            ConversationMessage(customer_id=ids[0], role="user", content="سلام", created_at=NOW - dt.timedelta(hours=2)),
            ConversationMessage(customer_id=ids[0], role="assistant", content="علیک", created_at=NOW - dt.timedelta(hours=2)),
            ConversationMessage(customer_id=ids[0], role="user", content="قیمت؟", created_at=NOW - dt.timedelta(hours=1)),
            ConversationMessage(customer_id=ids[1], role="user", content="سلام", created_at=NOW - dt.timedelta(days=3)),
            ConversationMessage(customer_id=ids[1], role="user", content="قدیمی", created_at=NOW - dt.timedelta(days=30)),
            ConversationMessage(customer_id=ids[2], role="user", content="تلگرامی", created_at=NOW - dt.timedelta(minutes=5)),
            ConversationMessage(customer_id=other_id, role="user", content="دیگر", created_at=NOW - dt.timedelta(minutes=5)),
        ]
        session.add_all(rows)
        await session.commit()
    async with session_scope() as session:
        summary = await instagram_service.activity_summary(session, shop_a, now=NOW)
        other_summary = await instagram_service.activity_summary(session, shop_b, now=NOW)
    assert summary["since_24h"] == 2, summary
    assert summary["since_7d"] == 3, summary
    assert summary["chats_7d"] == 2, summary
    assert other_summary["since_7d"] == 1 and other_summary["chats_7d"] == 1, other_summary
    print("PASS test_activity_summary_counts_only_instagram_of_this_shop")


async def test_mute_panel_flow(main_dp) -> None:
    shop_a, shop_b = await _seed_two_shops()
    owner = Chat(main_dp, OWNER_TG_ID)
    await owner.say("🟣 اینستاگرام")
    flat = callbacks(owner.last_markup)
    assert "ig_mute" in flat and "ig_activity" in flat, flat
    assert texts.INSTAGRAM_MUTE_BUTTON in [b.text for r in owner.last_markup.inline_keyboard for b in r]

    await owner.tap("ig_mute")
    screen = owner.last_edit_text
    assert screen.startswith("⏸ خاموش‌سازیِ موقتِ اینستاگرام"), screen
    assert "وضعیتِ کانال: ✅ روشن" in screen, screen
    mute_flat = callbacks(_edit_markup(owner))
    assert {"ig_mute:1", "ig_mute:6", "ig_mute:24", "ig_mute:72", "ig_mute:0", "ig_screen"} <= set(mute_flat), mute_flat

    await owner.tap("ig_mute:6")
    assert owner.last_toast["text"] == texts.INSTAGRAM_MUTE_ON_TOAST, owner.last_toast
    muted_screen = owner.last_edit_text
    assert "خاموش تا" in muted_screen and "وضعیتِ کانال" not in muted_screen, muted_screen
    labels = [b.text for r in _edit_markup(owner).inline_keyboard for b in r]
    assert any(label.startswith("✅ ۶ ساعت") for label in labels), labels
    row = await _account_row(shop_a)
    assert row.muted_until is not None

    await owner.tap("ig_screen")
    assert "🟣" in owner.last_edit_text or "اینستاگرام" in owner.last_edit_text, owner.last_edit_text
    assert "خاموش تا" in owner.last_edit_text, "خطِ وضعیتِ صفحهٔ اصلی هم باید خاموشی را بگوید"

    # ورودیِ خراب و مهلتِ بیرونِ فهرست ⇒ رد، بی‌تغییریِ ستون
    before = (await _account_row(shop_a)).muted_until
    for bad in ("ig_mute:abc", "ig_mute:5", "ig_mute:", "ig_mute:-6", "ig_mute:999999999999999999999"):
        await owner.tap(bad)
        assert owner.last_toast["text"] == texts.INSTAGRAM_MUTE_INVALID, (bad, owner.last_toast)
    assert (await _account_row(shop_a)).muted_until == before, "ورودیِ خراب هیچ چیزی را عوض نمی‌کند"

    # فروشگاهِ دیگر نمی‌تواند اینِ فروشگاه را خاموش/روشن کند
    other = Chat(main_dp, OTHER_OWNER_TG_ID)
    await other.tap("ig_mute:0")
    assert (await _account_row(shop_a)).muted_until == before, "کال‌بکِ فروشگاهِ دیگر ردیفِ اینِ فروشگاه را نمی‌بیند"

    await owner.tap("ig_mute:0")
    assert owner.last_toast["text"] == texts.INSTAGRAM_MUTE_OFF_TOAST, owner.last_toast
    assert "وضعیتِ کانال: ✅ روشن" in owner.last_edit_text, owner.last_edit_text
    assert (await _account_row(shop_a)).muted_until is None
    assert shop_b != shop_a
    print("PASS test_mute_panel_flow")


async def test_activity_panel_flow(main_dp) -> None:
    shop_a, _shop_b = await _seed_two_shops()
    owner = Chat(main_dp, OWNER_TG_ID)
    await owner.say("🟣 اینستاگرام")
    await owner.tap("ig_activity")
    body = owner.last_edit_text
    assert body.startswith("📊 فعالیتِ اینستاگرام — "), body
    assert "گفتگوهایِ دایرکت در ۷ روز: ۰" in body, body
    assert "کامنت‌ها در دیتابیسِ ما ذخیره نمی‌شوند" in body, "صراحتِ لازم دربارهٔ کامنت"
    assert not any(char.isascii() and char.isdigit() for char in body), "ارقامِ جلالی"
    flat = callbacks(_edit_markup(owner))
    assert "ig_activity" in flat and "ig_screen" in flat, flat
    answers_before = len(owner.session.answered_callbacks)
    await owner.tap("ig_activity")
    assert len(owner.session.answered_callbacks) == answers_before + 1, "دقیقاً یکِ پاسخِ کال‌بک"
    assert len(owner.edits) == 2, owner.edits
    print("PASS test_activity_panel_flow")


async def test_keyboard_bounds_and_connection_gate() -> None:
    connected = keyboards.instagram_panel_keyboard(_account())
    flat = callbacks(connected)
    assert "ig_mute" in flat and "ig_activity" in flat, flat
    for value in flat + ["ig_mute:72", "ig_screen"]:
        assert len(value.encode("utf-8")) <= 64, value
    disconnected = callbacks(keyboards.instagram_panel_keyboard(None))
    assert "ig_mute" not in disconnected and "ig_activity" not in disconnected, "بی‌اتصال این فعل‌ها معنا ندارد"
    assert "ig_connect" in disconnected
    mute_kb = callbacks(keyboards.instagram_mute_keyboard(_account(muted_until=NOW + dt.timedelta(hours=24))))
    assert set(mute_kb) >= {"ig_mute:1", "ig_mute:24", "ig_mute:0"}
    print("PASS test_keyboard_bounds_and_connection_gate")


async def main() -> None:
    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    await test_mute_helpers_are_time_scoped()
    await test_mute_gates_both_paths_before_any_cost()
    await test_set_mute_persists_and_audits_only_the_mute_column()
    await test_activity_summary_counts_only_instagram_of_this_shop()
    await test_mute_panel_flow(main_dp)
    await test_activity_panel_flow(main_dp)
    await test_keyboard_bounds_and_connection_gate()
    print("📊 نتیجه: ۷ تستِ پ۶۳ (مدیریتِ زمان‌دار و گزارشِ فعالیتِ اینستاگرام) پاس شد · در/ممیزی/مالکیت/پنل/کیبورد")


if __name__ == "__main__":
    asyncio.run(main())
