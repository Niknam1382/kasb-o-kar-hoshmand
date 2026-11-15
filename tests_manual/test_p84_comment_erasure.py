"""پ۸۴ · حقِ فراموشی رویِ کامنت‌ها: «حذفِ دادهٔ این حساب» در پنلِ فروشگاه‌دار.

خواسته‌ای که در بازمانده‌ها مانده بود: اگر کسی درخواست کرد کامنت‌هایش پاک شود، هیچ مسیری نبود.
این فایل ثابت می‌کند:
۱. شمارشِ قبل ازِ تایید *واقعی* است (نه عددِ ساختگی) و نامِ کاربری با *همان* نرمال‌سازیِ فهرستِ
   مسدودها مقایسه می‌شود («@Sara_Test» و «sara.test» یکی‌اند).
۲. پاک‌شدن فقط به همانِ فروشگاه و همانِ نامِ کاربری محدود است؛ ردیفِ فروشگاهِ دیگر و نامِ دیگر
   دست‌نخورده می‌ماند.
۳. هیچ چیزِ دیگری پاک نمی‌شود: مشتری‌هایِ CRM، سفارش‌ها و دفترِ کیف‌پول پیش/پس یکی‌اند (کامنت نه
   مشتری است، نه تراکنش).
۴. تاییدِ صریح لازم است: «بی‌خیال» ⇒ صفر حذف؛ «بله، پاک کن» ⇒ حذف + توستِ عدددار + بازگشتِ فهرست.
۵. ورودیِ دستکاری‌شده ⇒ توستِ «نیست» و صفر ویرایش؛ شکل‌هایِ `callback_data` زیرِ ۶۴ بایت.

اجرا: python3 tests_manual/run_one.py test_p84_comment_erasure.py
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
    Customer,
    InstagramAccount,
    InstagramCommentBlock,
    InstagramCommentEvent,
    OrderConsultation,
    WalletTransaction,
)
from app.database.session import session_scope  # noqa: E402
from app.services import admin_settings_service, instagram_service  # noqa: E402
from harness import FakeSession, build_test_dispatchers, make_callback_update, reset_database  # noqa: E402
from phase4_helpers import Chat, callbacks  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

UTC = dt.timezone.utc
OWNER_A = 998_401
SHOP_A = 998_402
OWNER_B = 998_403
SHOP_B = 998_404
IG_A = "17984010"
IG_B = "17984020"
NOW = dt.datetime(2026, 11, 16, 9, 0, tzinfo=UTC)
MAIN_TOKEN = "550084:FAKE_MAIN_BOT_TOKEN_FOR_P84_TESTING"
IDS: dict[str, int] = {}
DP = None


def _event(comment_id: str, username: str | None, ig_id: str = IG_A):
    return instagram_service.CommentEvent(
        comment_id=comment_id, media_id="m1", ig_account_id=ig_id, text="قیمت چند است؟", username=username, created_at=NOW
    )


async def _seed() -> None:
    await reset_database()
    IDS["shop_a"] = await seed_usable_shop(OWNER_A, SHOP_A, initial_balance_toman=100_000)
    IDS["shop_b"] = await seed_usable_shop(OWNER_B, SHOP_B, initial_balance_toman=100_000)
    async with session_scope() as session:
        admin = await admin_settings_service.get_admin_settings(session)
        admin.instagram_enabled = True
        admin.instagram_app_id = "1234567890"
        for shop_bot_id, ig_id in ((IDS["shop_a"], IG_A), (IDS["shop_b"], IG_B)):
            session.add(
                InstagramAccount(
                    shop_bot_id=shop_bot_id, ig_account_id=ig_id, ig_username="my.shop",
                    access_token="IGQVJ6fake.token.for.p84.tests", is_active=True, auto_reply_dm=True,
                    auto_reply_comments=True, private_reply_enabled=True,
                )
            )
        await session.flush()


async def _account(shop_bot_id: int) -> InstagramAccount:
    async with session_scope() as session:
        return (
            await session.execute(select(InstagramAccount).where(InstagramAccount.shop_bot_id == shop_bot_id))
        ).scalar_one()


async def _add_events(shop_bot_id: int, triples: tuple[tuple[str, str | None], ...]) -> None:
    account = await _account(shop_bot_id)
    async with session_scope() as session:
        for comment_id, username in triples:
            row, _handled = await instagram_service.record_comment(session, account, _event(comment_id, username))
            instagram_service.mark_comment(row, instagram_service.COMMENT_SKIPPED, reason="comments_off")
        await session.commit()


async def _event_rows(shop_bot_id: int | None = None) -> list[InstagramCommentEvent]:
    async with session_scope() as session:
        stmt = select(InstagramCommentEvent).order_by(InstagramCommentEvent.id)
        if shop_bot_id is not None:
            stmt = stmt.where(InstagramCommentEvent.shop_bot_id == shop_bot_id)
        return list((await session.execute(stmt)).scalars().all())


async def _counts() -> dict[str, int]:
    async with session_scope() as session:
        return {
            "customers": (await session.execute(select(func.count()).select_from(Customer))).scalar_one(),
            "orders": (await session.execute(select(func.count()).select_from(OrderConsultation))).scalar_one(),
            "wallet": (await session.execute(select(func.count()).select_from(WalletTransaction))).scalar_one(),
        }


# ============================================================================= ۱ و ۲ و ۳
async def test_erase_is_normalized_scoped_and_harmless_elsewhere() -> None:
    await _seed()
    await _add_events(IDS["shop_a"], (("a1", "@Sara.test"), ("a2", "sara.test"), ("a3", "ali")))
    await _add_events(IDS["shop_b"], (("b1", "Sara-Test"),))
    before = await _counts()
    async with session_scope() as session:
        await instagram_service.block_comment_sender(session, IDS["shop_a"], "@Sara.test", actor_telegram_id=OWNER_A)
        await session.commit()
    async with session_scope() as session:
        found = await instagram_service.comment_sender_event_count(session, IDS["shop_a"], "@SARA.TEST")
    assert found == 2, found  # «@Sara.test» و «sara.test» یکی‌اند؛ «ali» و «Sara-Test» نامِ دیگری‌اند
    async with session_scope() as session:
        events, blocks = await instagram_service.erase_comment_sender_data(
            session, IDS["shop_a"], "@sara.test", actor_telegram_id=OWNER_A
        )
        await session.commit()
    assert (events, blocks) == (2, 1), (events, blocks)
    left = [row.comment_id for row in await _event_rows(IDS["shop_a"])]
    assert left == ["a3"], left
    assert [row.comment_id for row in await _event_rows(IDS["shop_b"])] == ["b1"], "فروشگاهِ دیگر دست‌نخورده"
    async with session_scope() as session:
        assert (await session.execute(select(func.count()).select_from(InstagramCommentBlock))).scalar_one() == 0
    assert await _counts() == before, "CRM/سفارش/کیف‌پول هرگز پاک نمی‌شوند"
    print("PASS test_erase_is_normalized_scoped_and_harmless_elsewhere")


async def test_erase_without_name_is_noop() -> None:
    await _seed()
    async with session_scope() as session:
        assert await instagram_service.erase_comment_sender_data(session, IDS["shop_a"], "  @  ", actor_telegram_id=OWNER_A) == (0, 0)
        assert await instagram_service.comment_sender_event_count(session, IDS["shop_a"], None) == 0
        await session.commit()
    print("PASS test_erase_without_name_is_noop")


# ============================================================================= ۴ و ۵ — پنل
async def _owner() -> Chat:
    assert DP is not None
    return Chat(DP, OWNER_A)


async def test_panel_requires_confirmation_and_reports_counts() -> None:
    await _seed()
    await _add_events(IDS["shop_a"], (("c1", "sara"), ("c2", "Sara_"), ("c3", "ali")))
    async with session_scope() as session:
        row, _status = await instagram_service.block_comment_sender(session, IDS["shop_a"], "@Sara", actor_telegram_id=OWNER_A)
        block_id = row.id
        await session.commit()
    owner = await _owner()
    await owner.tap("ig_blklist")
    flat = callbacks(owner.last_edit_markup)
    assert f"ig_unblk:{block_id}" in flat and f"ig_blk_erase:{block_id}" in flat, flat
    assert all(len(item.encode("utf-8")) <= 64 for item in flat), flat

    await owner.tap(f"ig_blk_erase:{block_id}")
    body = owner.last_edit_text
    assert "🗑 حذفِ داده‌هایِ @sara" in body, body
    assert "۲ کامنت از این حساب دیده شده" in body, body
    assert "آنچه پاک **نمی‌شود**" in body, body
    assert not any(char.isascii() and char.isdigit() for char in body.splitlines()[2]), body

    confirm = callbacks(owner.last_edit_markup)
    assert f"ig_blk_erase_yes:{block_id}" in confirm and "ig_blk_erase_no" in confirm, confirm
    await owner.tap("ig_blk_erase_no")
    assert len(await _event_rows(IDS["shop_a"])) == 3, "انصراف هیچ چیز پاک نمی‌کند"

    await owner.tap(f"ig_blk_erase:{block_id}")
    await owner.tap(f"ig_blk_erase_yes:{block_id}")
    assert "پاک شد: ۲ رویداد" in owner.last_toast["text"], owner.last_toast
    assert len(await _event_rows(IDS["shop_a"])) == 1, "فقطِ sara پاک شد"
    assert "فهرست خالی است" in owner.last_edit_text, owner.last_edit_text

    edits_before = len(owner.edits)
    await owner.tap("ig_blk_erase:abc")
    assert owner.last_toast["text"] == texts.INSTAGRAM_ERASE_INVALID, owner.last_toast
    await owner.tap("ig_blk_erase:424242")
    assert owner.last_toast["text"] == texts.INSTAGRAM_ERASE_INVALID, owner.last_toast
    await owner.tap("ig_blk_erase_yes:424242")
    assert owner.last_toast["text"] == texts.INSTAGRAM_ERASE_INVALID, owner.last_toast
    assert len(owner.edits) == edits_before, "ورودیِ دستکاری‌شده صفحه را عوض نمی‌کند"

    bot = Bot(token=MAIN_TOKEN, session=FakeSession())
    await DP.feed_update(bot, make_callback_update(91, data=f"ig_blk_erase:{block_id}", user_id=999_999))
    assert not bot.session.edited_texts, "کال‌بکِ غریبه صفحه نمی‌سازد"
    await bot.session.close()
    print("PASS test_panel_requires_confirmation_and_reports_counts")


def test_keyboard_shape_and_texts() -> None:
    class _Row:
        id, username = 5, "someone.with.a.very.long.username.value"

    flat = callbacks(keyboards.instagram_blocks_keyboard([_Row()]))
    assert "ig_blk_erase:5" in flat and "ig_unblk:5" in flat, flat
    # دو فعلِ هرِ ردیف (آزاد کردن + حذفِ داده) + افزودنِ دستی + گزارشِ کامنت‌ها + بازگشت
    assert flat == ["ig_unblk:5", "ig_blk_erase:5", "ig_blk_add", "ig_cmt:7d:0", "ig_screen"], flat
    confirm_flat = callbacks(keyboards.instagram_erase_confirm_keyboard(_Row()))
    assert confirm_flat == ["ig_blk_erase_yes:5", "ig_blk_erase_no"], confirm_flat
    assert "برگشتی ندارد" in texts.INSTAGRAM_ERASE_ASK and "دفترِ کیف‌پول" in texts.INSTAGRAM_ERASE_SCOPE
    print("PASS test_keyboard_shape_and_texts")


async def main() -> None:
    global DP
    await test_erase_is_normalized_scoped_and_harmless_elsewhere()
    await test_erase_without_name_is_noop()
    DP = build_test_dispatchers()[0]
    await test_panel_requires_confirmation_and_reports_counts()
    test_keyboard_shape_and_texts()


if __name__ == "__main__":
    asyncio.run(main())
