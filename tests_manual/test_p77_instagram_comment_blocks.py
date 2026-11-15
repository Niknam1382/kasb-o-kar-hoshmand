"""پ۷۷ · حلقهٔ چهارمِ اینستاگرام: «به این حساب جواب نده» + فایلِ اکسلِ کامنت‌ها.

پوششِ داده‌شده:
۱. `normalize_comment_username`: @ و بزرگی/کوچکی و نقطه و خطِ تیره یکسان می‌شوند؛ ورودیِ بی‌نام ⇒ خالی.
۲. `block_comment_sender` idempotent است («exists»)، نامِ بی‌اعتبار ⇒ «invalid»، و سقفِ فهرست ⇒ «full»؛
   هر افزودن/برداشتن یکِ ردیفِ ممیزی می‌سازد و هیچ ستونِ دیگری را عوض نمی‌کند.
۳. درِ پاسخگویی: کامنتِ حسابِ مسدود ⇒ `skipped/sender_blocked`، صفر فراخوانِ AI، صفر ردیفِ کیف‌پول،
   صفر پاسخِ ارسال‌شده — و بعد ازِ آزاد کردن، همانِ حساب دوباره جواب می‌گیرد.
۴. مالکیتِ ردیف: کال‌بکِ `ig_unblk` با شناسهٔ فروشگاهِ دیگر چیزی حذف نمی‌کند.
۵. کیبورد: دکمهٔ «🚫» فقط برایِ کامنت‌هایِ مسدودنشده ساخته می‌شود و بودجهٔ ۶۴ بایتی نگه داشته می‌شود.
۶. پنلِ فروشگاه‌دار: افزودن/فهرست/آزاد کردن با توست‌هایِ درست و ارقامِ جلالی؛ ورودیِ دست‌کاری‌شده
   صفحه را عوض نمی‌کند؛ کاربرِ غریبه هیچ صفحه‌ای نمی‌سازد.
۷. اکسل: ردیف‌ها با نتیجه/دلیلِ فارسی و سقفِ `IG_COMMENTS_MAX_ROWS`؛ بازهٔ خالی ⇒ صفر فایل.

اجرا: python3 tests_manual/run_one.py test_p77_instagram_comment_blocks.py
"""
from __future__ import annotations

import asyncio
import datetime as dt
import io
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402
from openpyxl import load_workbook  # noqa: E402
from sqlalchemy import func, select  # noqa: E402

from app.bots.main_bot import keyboards, texts  # noqa: E402
from app.database.models import (  # noqa: E402
    AuditEventType,
    InstagramAccount,
    InstagramCommentBlock,
    InstagramCommentEvent,
    WalletTransaction,
)
from app.database.session import session_scope  # noqa: E402
from app.services import admin_settings_service, excel_export_service, instagram_service  # noqa: E402
from harness import FakeSession, build_test_dispatchers, make_callback_update, reset_database  # noqa: E402
from phase4_helpers import Chat, FakeAi, callbacks  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

UTC = dt.timezone.utc
OWNER_A = 997_701
SHOP_A = 997_702
OWNER_B = 997_703
SHOP_B = 997_704
IG_A = "17977010"
IG_B = "17977020"
NOW = dt.datetime(2026, 11, 15, 9, 0, tzinfo=UTC)
MAIN_TOKEN = "550007:FAKE_MAIN_BOT_TOKEN_FOR_P77_TESTING"
IDS: dict[str, int] = {}


def _event(comment_id: str = "c1", text: str = "قیمت؟", username: str = "Sara.Test_"):
    return instagram_service.CommentEvent(
        comment_id=comment_id, media_id="m1", ig_account_id=IG_A, text=text, username=username, created_at=NOW
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


async def _blocks(shop_bot_id: int | None = None) -> list[InstagramCommentBlock]:
    async with session_scope() as session:
        stmt = select(InstagramCommentBlock).order_by(InstagramCommentBlock.id)
        if shop_bot_id is not None:
            stmt = stmt.where(InstagramCommentBlock.shop_bot_id == shop_bot_id)
        return list((await session.execute(stmt)).scalars().all())


async def _wallet_rows() -> int:
    async with session_scope() as session:
        return (await session.execute(select(func.count()).select_from(WalletTransaction))).scalar_one()


async def _audit_rows() -> int:
    from app.database.models import AuditLogEntry

    async with session_scope() as session:
        stmt = (
            select(func.count())
            .select_from(AuditLogEntry)
            .where(AuditLogEntry.event_type == AuditEventType.INSTAGRAM_TOGGLED)
        )
        return (await session.execute(stmt)).scalar_one()


async def _add_comment_event(comment_id: str, username: str | None) -> int:
    account = await _account_row(IDS["shop_a"])
    async with session_scope() as session:
        row, _handled = await instagram_service.record_comment(session, account, _event(comment_id, username=username))
        instagram_service.mark_comment(row, instagram_service.COMMENT_SKIPPED, reason="muted")
        row_id = row.id
        await session.commit()
    return row_id


class _Flow:
    """جریانِ واقعیِ `handle_comment` با شبکه‌هایِ جعلی (شمارشِ فراخوانِ AI و پاسخ‌هایِ ارسالی)."""

    def __init__(self, *, ai=None) -> None:
        self.ai = ai or FakeAi(chat_reply="قیمت ۱۲۰ هزار تومان است.", tokens=900)
        self.sent: list[str] = []
        self._originals: dict = {}

    async def __aenter__(self) -> "_Flow":
        svc = instagram_service

        async def _build(_session, _settings, _kind):
            return self.ai

        async def _reply(_session, _account, _event, text):
            self.sent.append(text)
            return True

        async def _private(_session, _account, _event, _text):
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


async def _run_comment(event) -> None:
    async with session_scope() as session:
        await instagram_service.handle_comment(session, None, event)


async def _events(comment_id: str) -> list[InstagramCommentEvent]:
    async with session_scope() as session:
        return list(
            (
                await session.execute(
                    select(InstagramCommentEvent).where(InstagramCommentEvent.comment_id == comment_id)
                )
            ).scalars().all()
        )


# ============================================================================= ۱ — یکدست‌سازیِ نام
def test_normalize_comment_username() -> None:
    assert instagram_service.normalize_comment_username("@Sara.Test_") == "sara.test"
    assert instagram_service.normalize_comment_username("  ALI-Rezaee  ") == "ali-rezaee"
    assert instagram_service.normalize_comment_username("@a.b.c") == "a.b.c"
    assert instagram_service.normalize_comment_username(None) == ""
    assert instagram_service.normalize_comment_username("   @   ") == ""
    assert instagram_service.normalize_comment_username("." * 80) == ""
    assert len(instagram_service.normalize_comment_username("n" * 200)) == 64
    print("PASS test_normalize_comment_username")


# ============================================================================= ۲ — افزودن/سقف/ممیزی
async def test_block_is_idempotent_bounded_and_audited() -> None:
    await _seed_two_shops()
    audits_before = await _audit_rows()
    async with session_scope() as session:
        row, status = await instagram_service.block_comment_sender(session, IDS["shop_a"], "@Sara.Test_", actor_telegram_id=OWNER_A)
        assert status == "added" and row is not None and row.username == "sara.test"
        again, status_again = await instagram_service.block_comment_sender(session, IDS["shop_a"], "SARA.TEST", actor_telegram_id=OWNER_A)
        assert status_again == "exists" and again.id == row.id, "دو بار زدنِ همان نام نباید ردیفِ تازه بسازد"
        assert (await instagram_service.block_comment_sender(session, IDS["shop_a"], "@", actor_telegram_id=OWNER_A))[1] == "invalid"
        await session.commit()
    assert len(await _blocks(IDS["shop_a"])) == 1, await _blocks(IDS["shop_a"])
    assert not await _blocks(IDS["shop_b"]), "فهرست per-فروشگاه است"
    assert await _audit_rows() == audits_before + 1, "فقطِ افزودنِ واقعی ممیزی دارد؛ «از پیش هست» نه"
    # سقفِ فهرست: پس ازِ COMMENT_BLOCK_MAX ردیف، افزودنِ نامِ تازه «full» است و ردیفی ساخته نمی‌شود
    async with session_scope() as session:
        for index in range(1, instagram_service.COMMENT_BLOCK_MAX):
            session.add(InstagramCommentBlock(shop_bot_id=IDS["shop_a"], username=f"user{index}"))
        await session.flush()
        over, status_over = await instagram_service.block_comment_sender(session, IDS["shop_a"], "one-more", actor_telegram_id=OWNER_A)
        assert over is None and status_over == "full", status_over
        await session.commit()
    assert len(await _blocks(IDS["shop_a"])) == instagram_service.COMMENT_BLOCK_MAX
    print("PASS test_block_is_idempotent_bounded_and_audited")


# ============================================================================= ۳ — درِ پاسخگویی
async def test_blocked_sender_is_skipped_without_ai_or_cost() -> None:
    await _seed_two_shops()
    wallets_before = await _wallet_rows()
    async with session_scope() as session:
        await instagram_service.block_comment_sender(session, IDS["shop_a"], "@sara.test", actor_telegram_id=OWNER_A)
        await session.commit()
    ai = FakeAi(chat_reply="قیمت ۱۲۰ هزار تومان است.", tokens=900)
    async with _Flow(ai=ai) as flow:
        await _run_comment(_event("blocked-one"))
    assert flow.sent == [], "حسابِ مسدود پاسخی نمی‌گیرد"
    assert not ai.chat_calls, "مسیرِ ردشده نباید به AI برسد"
    rows = await _events("blocked-one")
    assert len(rows) == 1 and rows[0].outcome == instagram_service.COMMENT_SKIPPED
    assert rows[0].reason == instagram_service.COMMENT_BLOCK_REASON, rows[0].reason
    assert rows[0].cost_toman is None and rows[0].ai_tokens is None
    assert await _wallet_rows() == wallets_before, "ردشده هیچ مبلغی جابه‌جا نمی‌کند"

    # آزاد کردن ⇒ همانِ نامِ کاربری دوباره جواب می‌گیرد
    async with session_scope() as session:
        row = (await _blocks(IDS["shop_a"]))[0]
        removed = await instagram_service.unblock_comment_sender(session, IDS["shop_a"], row.id, actor_telegram_id=OWNER_A)
        assert removed is not None
        await session.commit()
    async with _Flow(ai=FakeAi(chat_reply="قیمت ۱۲۰ هزار تومان است.", tokens=900)) as flow2:
        await _run_comment(_event("after-unblock"))
    assert len(flow2.sent) == 1, flow2.sent
    rows = await _events("after-unblock")
    assert rows[0].outcome == instagram_service.COMMENT_REPLIED and rows[0].reason is None
    print("PASS test_blocked_sender_is_skipped_without_ai_or_cost")


# ============================================================================= ۴ — مالکیتِ ردیف
async def test_unblock_respects_shop_ownership() -> None:
    await _seed_two_shops()
    async with session_scope() as session:
        row, _status = await instagram_service.block_comment_sender(session, IDS["shop_a"], "spammer", actor_telegram_id=OWNER_A)
        await session.commit()
        foreign_id = row.id
    async with session_scope() as session:
        assert await instagram_service.unblock_comment_sender(session, IDS["shop_b"], foreign_id, actor_telegram_id=OWNER_B) is None
        await session.commit()
    assert len(await _blocks(IDS["shop_a"])) == 1, "کال‌بکِ فروشگاهِ دیگر ردیفِ دیگری را حذف نمی‌کند"
    print("PASS test_unblock_respects_shop_ownership")


# ============================================================================= ۵ — کیبورد
def test_comments_keyboard_block_buttons() -> None:
    class _Row:
        def __init__(self, rid, username) -> None:
            self.id, self.username = rid, username
            self.outcome, self.reason = "skipped", "muted"
            self.text = "قیمت این چند است؟"
            self.created_at = NOW
            self.comment_created_at = NOW
            self.ai_tokens, self.cost_toman = None, None

    report = {
        "window": "7d", "page": 0, "pages": 1, "page_size": 10,
        "items": [_Row(11, "sara"), _Row(12, "ali"), _Row(13, ""), _Row(14, None)],
    }
    flat = callbacks(keyboards.instagram_comments_keyboard(report, blocked=frozenset({"ali"})))
    assert "ig_blk:11" in flat, flat
    assert "ig_blk:12" not in flat, "حسابِ از پیش مسدود، دکمهٔ دوباره ندارد"
    assert "ig_blk:13" not in flat and "ig_blk:14" not in flat, "کامنتِ بی‌نام دکمهٔ مسدودسازی ندارد"
    assert "ig_blklist" in flat and "ig_cmt_x:7d" in flat, flat
    assert all(len(item.encode("utf-8")) <= 64 for item in flat), flat
    blocks_flat = callbacks(keyboards.instagram_blocks_keyboard([_Row(11, "sara")]))
    assert "ig_unblk:11" in blocks_flat and "ig_blk_add" in blocks_flat, blocks_flat
    assert all(len(item.encode("utf-8")) <= 64 for item in blocks_flat), blocks_flat
    print("PASS test_comments_keyboard_block_buttons")


# ============================================================================= ۶ — پنلِ فروشگاه‌دار
async def test_panel_blocks_flow(main_dp: Bot) -> None:  # noqa: ARG001
    await _seed_two_shops()
    event_row_id = await _add_comment_event("panel-c1", "sara")
    owner = Chat(main_dp, OWNER_A)
    await owner.say("🟣 اینستاگرام")
    await owner.tap("ig_cmt:7d:0")
    assert f"ig_blk:{event_row_id}" in callbacks(owner.last_edit_markup), owner.last_edit_markup
    await owner.tap(f"ig_blk:{event_row_id}")
    assert owner.last_toast["text"] == texts.INSTAGRAM_BLOCK_ADDED, owner.last_toast
    body = owner.last_edit_text
    assert body.startswith(texts.INSTAGRAM_BLOCKS_TITLE), body
    assert "@sara" in body and "فهرست خالی است" not in body, body
    assert not any(char.isascii() and char.isdigit() for char in body.split("\n", 1)[1]), body
    flat = callbacks(owner.last_edit_markup)
    assert "ig_blk_add" in flat, flat

    row = (await _blocks(IDS["shop_a"]))[0]
    await owner.tap(f"ig_unblk:{row.id}")
    assert owner.last_toast["text"] == texts.INSTAGRAM_BLOCK_REMOVED, owner.last_toast
    assert "فهرست خالی است" in owner.last_edit_text, owner.last_edit_text

    edits_before = len(owner.edits)
    await owner.tap("ig_blk:abc")
    assert owner.last_toast["text"] == texts.INSTAGRAM_BLOCK_INVALID, owner.last_toast
    await owner.tap("ig_blk:424242")
    assert owner.last_toast["text"] == texts.INSTAGRAM_COMMENTS_INVALID, owner.last_toast
    await owner.tap("ig_unblk:424242")
    assert owner.last_toast["text"] == texts.INSTAGRAM_BLOCK_INVALID, owner.last_toast
    assert len(owner.edits) == edits_before, "ورودیِ دست‌کاری‌شده صفحه را عوض نمی‌کند"
    assert len(await _blocks(IDS["shop_a"])) == 0

    # افزودنِ دستی با تایپِ نامِ کاربری + لغو با «خالی»
    await owner.tap("ig_blk_add")
    assert "نامِ کاربری را بنویس" in owner.last_text, owner.last_text
    await owner.say("@Ali.Rezaee")
    assert any(texts.INSTAGRAM_BLOCK_ADDED in item["text"] for item in owner.session.sent_messages[-2:]), owner.session.sent_messages[-2:]
    assert [row.username for row in await _blocks(IDS["shop_a"])] == ["ali.rezaee"]
    await owner.tap("ig_blk_add")
    await owner.say("خالی")
    assert texts.INSTAGRAM_BLOCKS_ADD_CANCELLED in owner.last_text, owner.last_text
    assert len(await _blocks(IDS["shop_a"])) == 1

    # کاربرِ غریبه هیچ صفحه‌ای نمی‌سازد
    bot = Bot(token=MAIN_TOKEN, session=FakeSession())
    await main_dp.feed_update(bot, make_callback_update(77, data="ig_blklist", user_id=999_999))
    assert not bot.session.edited_texts and not bot.session.sent_messages, bot.session.sent_messages
    await bot.session.close()
    print("PASS test_panel_blocks_flow")


# ============================================================================= ۷ — فایلِ اکسل
async def test_excel_export_rows_and_limit() -> None:
    await _seed_two_shops()
    account = await _account_row(IDS["shop_a"])
    async with session_scope() as session:
        for index, (username, outcome, reason) in enumerate(
            (("sara", instagram_service.COMMENT_REPLIED, None), ("ali", instagram_service.COMMENT_SKIPPED, "sender_blocked"))
        ):
            row, _handled = await instagram_service.record_comment(session, account, _event(f"x{index}", username=username))
            instagram_service.mark_comment(row, outcome, reason=reason, tokens=800, cost=40)
        await session.commit()
    async with session_scope() as session:
        content, count, truncated = await excel_export_service.build_ig_comments_workbook(
            session, IDS["shop_a"], days=7, window_label="۷ روز"
        )
    assert count == 2 and truncated is False, (count, truncated)
    wb = load_workbook(io.BytesIO(content))
    assert wb.sheetnames == ["کامنت‌ها", "توضیحات"], wb.sheetnames
    ws = wb["کامنت‌ها"]
    header = [cell.value for cell in ws[1]]
    assert header[3] == "متنِ کامنت" and header[4] == "نتیجه" and header[7] == "هزینه (تومان)", header
    results = {(ws.cell(row=i, column=5).value, ws.cell(row=i, column=6).value) for i in range(2, ws.max_row + 1)}
    assert results == {
        ("جواب رفت", texts.COMMENT_REASON_LABELS["unknown"]),
        ("جواب نرفت", texts.COMMENT_REASON_LABELS["sender_blocked"]),
    }, results
    money = [ws.cell(row=i, column=8).value for i in range(2, ws.max_row + 1)]
    assert money == [40, 40], money
    notes = {wb["توضیحات"].cell(row=i, column=1).value: wb["توضیحات"].cell(row=i, column=2).value for i in range(2, 6)}
    assert notes.get("بازه") == "۷ روز از ۷ روزِ گذشته", notes
    assert notes.get("تعدادِ ردیف‌هایِ این فایل") == 2, notes

    async with session_scope() as session:
        empty = await excel_export_service.build_ig_comments_workbook(session, IDS["shop_b"], days=30, window_label="۳۰ روز")
    assert empty[1] == 0 and empty[2] is False, empty
    print("PASS test_excel_export_rows_and_limit")


async def test_export_button_sends_document(main_dp: Bot) -> None:  # noqa: ARG001
    """دکمهٔ «📥 فایلِ اکسل» رویِ همانِ صفحه: فایل می‌رود، و بازهٔ خالی فقط توست است."""
    await _seed_two_shops()
    await _add_comment_event("export-c1", "sara")
    owner = Chat(main_dp, OWNER_A)
    await owner.say("🟣 اینستاگرام")
    await owner.tap("ig_cmt:7d:0")
    assert "ig_cmt_x:7d" in callbacks(owner.last_edit_markup), owner.last_edit_markup
    docs_before = len(owner.session.sent_documents)
    await owner.tap("ig_cmt_x:7d")
    assert len(owner.session.sent_documents) == docs_before + 1, owner.session.sent_documents
    assert owner.session.sent_documents[-1]["document"].filename == texts.INSTAGRAM_EXPORT_FILENAME
    assert "آماده شد" in owner.session.sent_documents[-1]["caption"], owner.session.sent_documents[-1]["caption"]
    await owner.tap("ig_cmt_x:99h")
    assert owner.last_toast["text"] == texts.INSTAGRAM_COMMENTS_INVALID, owner.last_toast

    other = Chat(main_dp, OWNER_B)
    await other.say("🟣 اینستاگرام")
    await other.tap("ig_cmt_x:30d")
    assert other.last_toast["text"] == texts.INSTAGRAM_EXPORT_EMPTY, other.last_toast
    assert len(other.session.sent_documents) == 0
    print("PASS test_export_button_sends_document")


async def main() -> None:
    test_normalize_comment_username()
    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    await test_block_is_idempotent_bounded_and_audited()
    await test_blocked_sender_is_skipped_without_ai_or_cost()
    await test_unblock_respects_shop_ownership()
    test_comments_keyboard_block_buttons()
    await test_panel_blocks_flow(main_dp)
    await test_export_button_sends_document(main_dp)
    await test_excel_export_rows_and_limit()


if __name__ == "__main__":
    asyncio.run(main())
