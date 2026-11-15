"""پ۷۳ · خواستهٔ مالک (۲۰۲۶-۱۱-۱۲، حلقهٔ سومِ اینستاگرام): «چند کامنت آمد، به چندتا جواب دادیم، خرجش چقدر بود».

پوششِ داده‌شده:
۱. `record_comment` یکِ ردیفِ فقط‌مشاهده‌ای می‌سازد و دومیِ همانِ کامنت را «رسیدگی‌شده» برمی‌گرداند
   (dedupِ پایدار، برخلافِ `claim_event` که فقط درونِ یکِ پروسه یکتاست)؛ `mark_comment` نتیجه/دلیل/
   توکن/مبلغ را رویِ همانِ ردیف می‌نشاند و بیرونِ فهرستِ نتیجه‌ها چیزی عوض نمی‌کند.
۲. هرِ «جواب‌نرفتن» با دلیلِ خودش ثبت می‌شود (خاموشیِ سوییچ، خاموشیِ موقت، فروشگاهِ غیرفعال) و در
   همانِ حالت‌ها **هیچ** پولی جابه‌جا نمی‌شود و **هیچ** فراخوانِ AI ساخته نمی‌شود.
۳. مسیرِ موفق: نتیجه=replied، توکنِ واقعیِ همانِ فراخوان و **همانِ مبلغی که از کیف‌پول کم شده** رویِ
   ردیف می‌نشیند (یکِ ردیفِ کسر، نه دو تا)؛ خطایِ AI ⇒ failed/ai_error با صفر کسر.
۴. `comment_report`: فقطِ همین فروشگاه، فقطِ همانِ پنجره (۲۴س/۷ر/۳۰ر)، تفکیکِ دلیل‌ها، و
   صفحه‌گردانیِ کراندار (صفحهٔ بیرونِ فهرست به آخرینِ صفحه می‌چسبد، بی‌خطا).
۵. پنلِ فروشگاه‌دار: دکمه ⇒ فهرست با ارقامِ جلالی و یادداشتِ «از این نسخه به بعد»؛ بازه/صفحهٔ
   دست‌کاری‌شده ⇒ توست و صفر ویرایش؛ بدونِ اتصال ⇒ همانِ توستِ «متصل نشده»؛ فروشگاهِ دیگر ⇒ بی‌دسترسی.
۶. کیبورد: بودجهٔ ۶۴ بایتیِ `ig_cmt:*` و ظاهرشدنِ دکمه فقط وقتی اتصال برقرار است.

اجرا: python3 tests_manual/run_one.py test_p73_instagram_comment_report.py
"""
from __future__ import annotations

import asyncio
import datetime as dt
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402
from sqlalchemy import func, select  # noqa: E402

from app.bots.main_bot import keyboards, texts  # noqa: E402
from app.database.models import (  # noqa: E402
    InstagramAccount, InstagramCommentEvent, ShopBot, WalletTransaction,
)
from app.database.session import session_scope  # noqa: E402
from app.services import admin_settings_service, instagram_service  # noqa: E402
from harness import FakeSession, build_test_dispatchers, make_callback_update, reset_database  # noqa: E402
from phase4_helpers import Chat, FakeAi, callbacks, owner_balance  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

UTC = dt.timezone.utc
OWNER_A = 996_401
SHOP_A = 996_402
OWNER_B = 996_403
SHOP_B = 996_404
IG_A = "17841401"
IG_B = "17841402"
NOW = dt.datetime(2026, 11, 14, 9, 0, tzinfo=UTC)
MAIN_TOKEN = "550000:FAKE_MAIN_BOT_TOKEN_FOR_P73_TESTING"
IDS: dict[str, int] = {}


def _event(comment_id: str = "c1", text: str = "قیمت این چند؟", username: str = "sara", ig_account_id: str = IG_A):
    return instagram_service.CommentEvent(
        comment_id=comment_id, media_id="m1", ig_account_id=ig_account_id, text=text, username=username, created_at=NOW
    )


async def _seed_two_shops() -> None:
    await reset_database()
    IDS["shop_a"] = await seed_usable_shop(OWNER_A, SHOP_A, initial_balance_toman=100_000)
    IDS["shop_b"] = await seed_usable_shop(OWNER_B, SHOP_B, initial_balance_toman=100_000)
    async with session_scope() as session:
        admin_settings = await admin_settings_service.get_admin_settings(session)
        admin_settings.instagram_enabled = True
        admin_settings.instagram_app_id = "1234567890"
        admin_settings.ai_api_key = "sk-fake-key-for-tests"
        for shop_bot_id, ig_id in ((IDS["shop_a"], IG_A), (IDS["shop_b"], IG_B)):
            session.add(
                InstagramAccount(
                    shop_bot_id=shop_bot_id, ig_account_id=ig_id, ig_username="my.shop",
                    access_token="IGQVJ6fake.token.for.tests", is_active=True, auto_reply_dm=True,
                    auto_reply_comments=True, private_reply_enabled=True,
                )
            )
        await session.flush()


async def _account_row(shop_bot_id: int) -> InstagramAccount:
    async with session_scope() as session:
        return (
            await session.execute(select(InstagramAccount).where(InstagramAccount.shop_bot_id == shop_bot_id))
        ).scalar_one()


async def _set_account(shop_bot_id: int, **changes) -> None:
    async with session_scope() as session:
        row = (
            await session.execute(select(InstagramAccount).where(InstagramAccount.shop_bot_id == shop_bot_id))
        ).scalar_one()
        for field, value in changes.items():
            setattr(row, field, value)


async def _events(shop_bot_id: int | None = None) -> list[InstagramCommentEvent]:
    async with session_scope() as session:
        stmt = select(InstagramCommentEvent).order_by(InstagramCommentEvent.id)
        if shop_bot_id is not None:
            stmt = stmt.where(InstagramCommentEvent.shop_bot_id == shop_bot_id)
        return list((await session.execute(stmt)).scalars().all())


async def _event_row(comment_id: str, shop_bot_id: int | None = None) -> InstagramCommentEvent:
    rows = await _events(shop_bot_id)
    found = [row for row in rows if row.comment_id == comment_id]
    assert len(found) == 1, (comment_id, [(r.comment_id, r.outcome) for r in rows])
    return found[0]


async def _wallet_rows() -> int:
    async with session_scope() as session:
        return (await session.execute(select(func.count()).select_from(WalletTransaction))).scalar_one()


class _Flow:
    """جریانِ واقعیِ `_handle_comment` با سه جایِ شبکه‌ایِ جعلی (فراخوانِ AI، ارسال، پاسخِ خصوصی)."""

    def __init__(self, *, ai=None, send_ok: bool = True) -> None:
        self.ai = ai or FakeAi(chat_reply="قیمت ۱۲۰ هزار تومان است.", tokens=900)
        self.send_ok = send_ok
        self.sent: list[str] = []
        self.private = 0
        self._originals: dict = {}

    async def __aenter__(self) -> "_Flow":
        svc = instagram_service

        async def _build(_session, _settings, _kind):
            return self.ai

        async def _reply(_session, _account, _event, text):
            self.sent.append(text)
            return self.send_ok

        async def _private(_session, _account, _event, _text):
            self.private += 1
            return True

        self._originals = {
            "claim_event": svc.claim_event,
            "ai_pool_build": svc.ai_pool_service.build_ai_service,
            "reply_to_comment": svc.reply_to_comment,
            "send_private_reply": svc.send_private_reply,
        }
        svc.claim_event = lambda _key: True
        svc.ai_pool_service.build_ai_service = _build
        svc.reply_to_comment = _reply
        svc.send_private_reply = _private
        return self

    async def __aexit__(self, *_exc) -> None:
        svc = instagram_service
        svc.claim_event = self._originals["claim_event"]
        svc.ai_pool_service.build_ai_service = self._originals["ai_pool_build"]
        svc.reply_to_comment = self._originals["reply_to_comment"]
        svc.send_private_reply = self._originals["send_private_reply"]


async def _run_comment(event, bot=None) -> None:
    async with session_scope() as session:
        await instagram_service.handle_comment(session, bot, event)


# ============================================================================= ۱ — خودِ ردیف
async def test_record_is_idempotent_and_mark_is_bounded() -> None:
    await _seed_two_shops()
    account = await _account_row(IDS["shop_a"])
    async with session_scope() as session:
        row, handled = await instagram_service.record_comment(session, account, _event("c1"))
        assert row is not None and handled is False, (row, handled)
        assert row.outcome == instagram_service.COMMENT_RECEIVED and row.shop_bot_id == IDS["shop_a"]
        assert row.username == "sara" and row.text == "قیمت این چند؟" and row.media_id == "m1"
        instagram_service.mark_comment(row, instagram_service.COMMENT_REPLIED, tokens=900, cost=40)
        await session.commit()
    async with session_scope() as session:
        again, handled_again = await instagram_service.record_comment(session, account, _event("c1"))
        assert handled_again is True and again.id == row.id, "دوباره‌ارسالِ متا نباید ردیفِ تازه بسازد"
        assert len(await _events(IDS["shop_a"])) == 1
        # نتیجه‌ای که در فهرست نیست نباید چیزی را خراب کند
        instagram_service.mark_comment(again, "not_a_real_outcome", reason="whatever")
        again.reason = None
        await session.commit()
    fresh = await _event_row("c1", IDS["shop_a"])
    assert fresh.outcome == instagram_service.COMMENT_REPLIED and fresh.ai_tokens == 900 and fresh.cost_toman == 40
    assert fresh.reason is None, "نتیجهٔ ناشناخته ⇒ هیچ ستونی عوض نمی‌شود"
    # بدونِ شناسه یا فروشگاه، ردیفی ساخته نمی‌شود (نه خطا)
    class _Broken:
        shop_bot_id = None
        ig_account_id = IG_A

    async with session_scope() as session:
        assert await instagram_service.record_comment(session, _Broken(), _event("c9")) == (None, False)
    assert len(await _events()) == 1, "ردیفِ بی‌فروشگاه نساخته شد"
    print("PASS test_record_is_idempotent_and_mark_is_bounded")


# ============================================================================= ۲ — جواب‌نرفتن‌ها
async def test_skips_are_recorded_with_reasons_and_no_cost() -> None:
    await _seed_two_shops()
    wallets_before = await _wallet_rows()
    calls: list[str] = []

    async def _no_ai(*_a, **_k):
        calls.append("ai")
        raise AssertionError("مسیرِ ردشده نباید به AI برسد")

    original_build = instagram_service.ai_pool_service.build_ai_service
    original_claim = instagram_service.claim_event
    instagram_service.ai_pool_service.build_ai_service = _no_ai
    instagram_service.claim_event = lambda key: True
    try:
        await _set_account(IDS["shop_a"], muted_until=dt.datetime.now(UTC) + dt.timedelta(hours=2))
        await _run_comment(_event("muted"))
        await _set_account(IDS["shop_a"], muted_until=None, auto_reply_comments=False)
        await _run_comment(_event("off"))
        await _set_account(IDS["shop_a"], auto_reply_comments=True, is_active=False)
        await _run_comment(_event("account"))
        await _set_account(IDS["shop_a"], is_active=True)
        async with session_scope() as session:
            shop = await session.get(ShopBot, IDS["shop_a"])
            shop.is_active = False
            await session.flush()
        await _run_comment(_event("shop"))
        async with session_scope() as session:
            shop = await session.get(ShopBot, IDS["shop_a"])
            shop.is_active = True
            await session.flush()
    finally:
        instagram_service.ai_pool_service.build_ai_service = original_build
        instagram_service.claim_event = original_claim
    rows = {row.comment_id: row for row in await _events(IDS["shop_a"])}
    assert set(rows) == {"muted", "off", "account", "shop"}, set(rows)
    assert {row.outcome for row in rows.values()} == {"skipped"}, rows
    assert rows["muted"].reason == "muted", rows["muted"].reason
    assert rows["off"].reason == "comments_off", rows["off"].reason
    assert rows["account"].reason == "account_off", rows["account"].reason
    assert rows["shop"].reason == "shop_inactive", rows["shop"].reason
    assert all(row.ai_tokens is None and row.cost_toman is None for row in rows.values())
    assert not calls, "هیچ فراخوانِ AI ساخته نشد"
    assert await _wallet_rows() == wallets_before, "پولِ مشتری/فروشگاه دست‌نخورده ماند"
    print("PASS test_skips_are_recorded_with_reasons_and_no_cost")


# ============================================================================= ۳ و ۴ — موفق و خطا
async def test_reply_and_failure_record_the_real_numbers() -> None:
    await _seed_two_shops()
    bot = Bot(token=MAIN_TOKEN, session=FakeSession())
    before = await _wallet_rows()  # شارژِ اولیهٔ دو فروشگاه
    try:
        async with _Flow() as flow:
            await _run_comment(_event("ok"), bot)
        assert flow.sent == ["قیمت ۱۲۰ هزار تومان است."], flow.sent
        assert flow.private == 1, "پاسخِ خصوصی هم مثلِ قبل فرستاده شد"
        ok = await _event_row("ok", IDS["shop_a"])
        assert ok.outcome == "replied" and ok.reason is None, (ok.outcome, ok.reason)
        assert ok.ai_tokens == 900, ok.ai_tokens
        charged = before + 1
        assert await _wallet_rows() == charged, "دقیقاً یکِ کسرِ کیف‌پول"
        cost = ok.cost_toman
        assert cost and cost > 0, cost
        assert await owner_balance(OWNER_A) == 100_000 - cost, "مبلغِ ردیف == مبلغِ کسرشده"

        # همانِ کامنتِ دوباره‌ارسال‌شده ⇒ بی‌فراخوانِ AI، بی‌کسرِ تازه
        async with _Flow() as second:
            await _run_comment(_event("ok"), bot)
        assert second.sent == [] and second.private == 0, "dedupِ پایدار کار کرد"
        assert await _wallet_rows() == charged and len(await _events(IDS["shop_a"])) == 1

        # خطایِ AI ⇒ بی‌نتیجه، بدونِ کسر، بدونِ پاسخ
        async with _Flow(ai=FakeAi(raises=True)) as failed:
            await _run_comment(_event("bad"), bot)
        assert failed.sent == [], "پاسخی به متا نرفت"
        bad = await _event_row("bad", IDS["shop_a"])
        assert bad.outcome == "failed" and bad.reason == "ai_error", (bad.outcome, bad.reason)
        assert bad.ai_tokens is None and bad.cost_toman is None
        assert await _wallet_rows() == charged, "خطایِ AI هزینه نساخت"

        # پاسخِ نرسیدن به متا ⇒ failed/send_failed و همان‌جا بی‌هزینه
        async with _Flow(send_ok=False) as undelivered:
            await _run_comment(_event("lost"), bot)
        assert undelivered.private == 0
        lost = await _event_row("lost", IDS["shop_a"])
        assert lost.outcome == "failed" and lost.reason == "send_failed" and lost.cost_toman is None
        assert await _wallet_rows() == charged
    finally:
        await bot.session.close()
    print("PASS test_reply_and_failure_record_the_real_numbers")


# ============================================================================= ۵ — گزارش
async def test_report_scopes_shop_window_and_pages() -> None:
    await _seed_two_shops()
    account_a = await _account_row(IDS["shop_a"])
    account_b = await _account_row(IDS["shop_b"])
    async with session_scope() as session:
        for index, (account, comment_id, when) in enumerate((
            (account_a, "recent1", NOW),
            (account_a, "recent2", NOW - dt.timedelta(hours=5)),
            (account_a, "week", NOW - dt.timedelta(days=3)),
            (account_a, "old", NOW - dt.timedelta(days=45)),
            (account_b, "other", NOW),
        )):
            row, _handled = await instagram_service.record_comment(session, account, _event(comment_id))
            if comment_id in {"recent1", "week", "other"}:
                instagram_service.mark_comment(row, "replied", tokens=500 + index, cost=20 + index)
            elif comment_id == "recent2":
                instagram_service.mark_comment(row, "skipped", reason="muted")
            elif comment_id == "old":
                instagram_service.mark_comment(row, "failed", reason="ai_error")
            else:
                instagram_service.mark_comment(row, "skipped", reason="comments_off")
            row.created_at = when
        await session.commit()

    async with session_scope() as session:
        day = await instagram_service.comment_report(session, IDS["shop_a"], window="24h", now=NOW)
        week = await instagram_service.comment_report(session, IDS["shop_a"], window="7d", now=NOW)
        month = await instagram_service.comment_report(session, IDS["shop_a"], window="30d", now=NOW)
        other = await instagram_service.comment_report(session, IDS["shop_b"], window="30d", now=NOW)
    assert (day["total"], day["replied"], day["skipped"], day["failed"]) == (2, 1, 1, 0), day
    assert (week["total"], week["replied"], week["skipped"]) == (3, 2, 1), week
    assert (month["total"], month["failed"]) == (3, 0), "کامنتِ ۴۵ روزه در ۳۰ روز نمی‌آید"
    assert day["cost"] == 20 and day["tokens"] == 500, day
    assert [reason for reason, _count in day["reasons"]] == ["muted"], day["reasons"]
    assert other["total"] == 1 and [row.comment_id for row in other["items"]] == ["other"], other
    assert [row.comment_id for row in week["items"]] == ["recent1", "recent2", "week"], week["items"]
    assert week["pages"] == 1 and week["page"] == 0

    async with session_scope() as session:
        paged = await instagram_service.comment_report(
            session, IDS["shop_a"], window="30d", page=0, now=NOW, page_size=2
        )
        beyond = await instagram_service.comment_report(
            session, IDS["shop_a"], window="30d", page=9, now=NOW, page_size=2
        )
    assert paged["pages"] == 2 and len(paged["items"]) == 2, paged
    assert beyond["page"] == 1 and len(beyond["items"]) == 1, "صفحهٔ بیرونِ فهرست به آخرینِ صفحه می‌چسبد"
    print("PASS test_report_scopes_shop_window_and_pages")


# ============================================================================= ۶ — پنل
async def test_comments_panel(main_dp) -> None:
    await _seed_two_shops()
    account = await _account_row(IDS["shop_a"])
    async with session_scope() as session:
        for comment_id, outcome, reason in (("c-one", "replied", None), ("c-two", "skipped", "muted")):
            row, _handled = await instagram_service.record_comment(session, account, _event(comment_id, text="سلام، قیمت؟"))
            instagram_service.mark_comment(row, outcome, reason=reason, tokens=700, cost=30)
        await session.commit()

    owner = Chat(main_dp, OWNER_A)
    await owner.say("🟣 اینستاگرام")
    flat = callbacks(owner.last_markup)
    assert any(item.startswith("ig_cmt:") for item in flat), flat
    assert all(len(item.encode("utf-8")) <= 64 for item in flat), flat

    await owner.tap("ig_cmt:7d:0")
    body = owner.last_edit_text
    assert body.startswith("🗨 گزارشِ کامنت‌ها — "), body
    assert "۷ روز" in body and "۲ کامنت" in body and "✅ ۱ جواب رفت" in body, body
    assert "⏸ ۱ جواب نرفت" in body and "کانال موقتاً خاموش بود" in body, body
    assert "از همین نسخه به این سو" in body, body
    assert not any(char.isascii() and char.isdigit() for char in body), body
    markup = callbacks(owner.last_edit_markup)
    assert "ig_cmt:24h:0" in markup and "ig_cmt:30d:0" in markup and "ig_cmt:7d:0" in markup, markup
    assert "ig_screen" in markup, markup

    await owner.tap("ig_cmt:24h:0")
    assert "۲۴ ساعت" in owner.last_edit_text, owner.last_edit_text
    edits_before = len(owner.edits)
    await owner.tap("ig_cmt:99h:0")
    assert owner.last_toast["text"] == texts.INSTAGRAM_COMMENTS_INVALID, owner.last_toast
    await owner.tap("ig_cmt:7d:abc")
    assert owner.last_toast["text"] == texts.INSTAGRAM_COMMENTS_INVALID, owner.last_toast
    assert len(owner.edits) == edits_before, "ورودیِ دست‌کاری‌شده صفحه را عوض نمی‌کند"

    # فروشگاهِ دیگر به ردیف‌هایِ اینِ فروشگاه نمی‌رسد
    other = Chat(main_dp, OWNER_B)
    await other.tap("ig_cmt:30d:0")
    assert "۰ کامنت" in other.last_edit_text, other.last_edit_text
    print("PASS test_comments_panel")


async def test_no_connection_and_other_shop_callbacks(main_dp) -> None:
    await _seed_two_shops()
    async with session_scope() as session:
        row = (
            await session.execute(select(InstagramAccount).where(InstagramAccount.shop_bot_id == IDS["shop_b"]))
        ).scalar_one()
        await session.delete(row)
    owner_b = Chat(main_dp, OWNER_B)
    await owner_b.say("🟣 اینستاگرام")
    assert not any(item.startswith("ig_cmt:") for item in callbacks(owner_b.last_markup)), "بدونِ اتصال دکمه نیست"
    edits_before = len(owner_b.edits)
    await owner_b.tap("ig_cmt:7d:0")
    assert owner_b.last_toast["text"] == texts.INSTAGRAM_NOT_CONNECTED, owner_b.last_toast
    assert len(owner_b.edits) == edits_before

    bot = Bot(token=MAIN_TOKEN, session=FakeSession())
    await main_dp.feed_update(bot, make_callback_update(31, data="ig_cmt:7d:0", user_id=999_999))
    assert not bot.session.edited_texts and not bot.session.sent_messages, "کال‌بکِ غریبه صفحه نمی‌سازد"
    assert bot.session.answered_callbacks[-1]["text"] == texts.SHOP_BOT_NOT_SET_UP, bot.session.answered_callbacks
    print("PASS test_no_connection_and_other_shop_callbacks")
    await bot.session.close()


def test_keyboard_and_window_constants() -> None:
    # پ۷۷ دو دکمهٔ پایینِ همین صفحه را افزود (فهرستِ «جواب نده» + فایلِ اکسلِ همان بازه).
    report = {"window": "7d", "page": 0, "pages": 3, "items": []}
    flat = callbacks(keyboards.instagram_comments_keyboard(report))
    assert flat == [
        "ig_cmt:24h:0", "ig_cmt:7d:0", "ig_cmt:30d:0", "noop", "ig_cmt:7d:1", "ig_cmt:7d:0",
        "ig_blklist", "ig_cmt_x:7d", "ig_screen",
    ], flat
    assert all(len(item.encode("utf-8")) <= 64 for item in flat), flat
    assert instagram_service.COMMENT_WINDOW_KEYS == {"24h", "7d", "30d"}
    assert instagram_service.COMMENT_OUTCOMES == ("received", "replied", "skipped", "failed")
    assert set(texts.COMMENT_REASON_LABELS) >= {
        "account_off", "comments_off", "muted", "shop_inactive", "no_owner", "moderation_block", "no_ai_key",
        "no_ai_pool", "no_access", "empty_reply", "ai_error", "send_failed", "unknown",
    }
    print("PASS test_keyboard_and_window_constants")


async def main() -> None:
    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    await test_record_is_idempotent_and_mark_is_bounded()
    await test_skips_are_recorded_with_reasons_and_no_cost()
    await test_reply_and_failure_record_the_real_numbers()
    await test_report_scopes_shop_window_and_pages()
    await test_comments_panel(main_dp)
    await test_no_connection_and_other_shop_callbacks(main_dp)
    test_keyboard_and_window_constants()
    print("📊 نتیجه: ۷ تستِ پ۷۳ (رویدادِ کامنت + گزارشِ کامنت‌ها) پاس شد")


if __name__ == "__main__":
    asyncio.run(main())
