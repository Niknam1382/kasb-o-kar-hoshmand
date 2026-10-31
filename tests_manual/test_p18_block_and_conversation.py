"""
تست: P18 · B4 — بلاک/رفعِ بلاکِ مشتری و «💬 دیدنِ گفتگو».

پوشش:
۱. خالص: کول‌دنِ «حداکثر یک پیامِ ادبی» و ایزولاسیونِ فروشگاه‌ها؛ صفحه‌بندیِ گفتگو در SQL.
۲. پنلِ فروشگاه‌دار: مسیرِ واقعیِ «👥 مشتری‌ها» تا کارتِ مشتری، دکمه‌یِ بلاک/رفعِ بلاک، نشانِ بلاک رویِ
   کارت، ثبتِ ممیزی، و بی‌اثر بودنِ دابل‌تپ (دو کالبکِ جدا، نه تلگلِ کور).
۳. رباتِ فروشگاه: مشتریِ بلاک‌شده فقط یک پیامِ ادبی می‌گیرد؛ هیچ هزینه‌یِ کیف‌پول/AI، هیچ سفارشِ تازه
   و هیچ پیامِ دیگری تولید نمی‌شود؛ کالبک‌ها بی‌صدا پاسخ داده می‌شوند.
۴. ایزولاسیون: فروشگاهِ دیگر با همان telegram_id دست‌نخورده می‌ماند و مالکِ دیگر نه کارتِ مشتریِ من را
   می‌بیند، نه گفتگویش را، نه می‌تواند بلاکش کند (IDOR).
۵. مشتریِ بلاک همچنان در آمار/CRM شمرده می‌شود (پنهان یا حذف نمی‌شود) و پسِ از رفعِ بلاک دوباره کار می‌کند.

اجرا: python3 tests_manual/test_p18_block_and_conversation.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402
from sqlalchemy import select  # noqa: E402

from harness import (  # noqa: E402
    FakeSession,
    build_test_dispatchers,
    make_callback_update,
    make_message_update,
    reset_database,
)
from phase4_helpers import Chat  # noqa: E402
from shop_setup import TEST_WALLET_BALANCE_TOMAN, seed_usable_shop  # noqa: E402

from app.bots.main_bot import texts as main_texts  # noqa: E402
from app.bots.shop_bot import middlewares as shop_middlewares  # noqa: E402
from app.bots.shop_bot import texts as shop_texts  # noqa: E402
from app.database.models import AuditEventType, AuditLogEntry, Customer, OrderConsultation, ShopOwner  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import conversation_service, crm_service, customer_service  # noqa: E402

OWNER_TG_ID = 999_831
SHOP_BOT_TG_ID = 999_832
CUSTOMER_TG_ID = 999_833
OTHER_OWNER_TG_ID = 999_841
OTHER_SHOP_BOT_TG_ID = 999_842
MAIN_TOKEN = "000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS"


def _datas(markup) -> list[str]:
    return [b.callback_data for row in markup.inline_keyboard for b in row if b.callback_data] if markup else []


def _labels(markup) -> list[str]:
    return [b.text for row in markup.inline_keyboard for b in row] if markup else []


class _Shop:
    """رباتِ جعلیِ فروشگاه + شمارنده‌یِ update_id برایِ فیدکردنِ آپدیتِ مشتری."""

    def __init__(self, shop_dp, bot_telegram_id: int) -> None:
        self.dp = shop_dp
        self.bot = Bot(token=f"{bot_telegram_id}:FAKE", session=FakeSession())
        self.session: FakeSession = self.bot.session  # type: ignore[assignment]
        self._n = 0

    async def say(self, text: str, user_id: int = CUSTOMER_TG_ID) -> None:
        self._n += 1
        await self.dp.feed_update(self.bot, make_message_update(self._n, text=text, user_id=user_id))

    async def tap(self, data: str, user_id: int = CUSTOMER_TG_ID) -> None:
        self._n += 1
        await self.dp.feed_update(self.bot, make_callback_update(self._n, data=data, user_id=user_id))

    @property
    def sent(self) -> list[dict]:
        return self.session.sent_messages


async def _seed_customer(shop_bot_id: int, telegram_id: int = CUSTOMER_TG_ID, name: str = "مشتری") -> int:
    async with session_scope() as session:
        customer = await customer_service.get_or_create_customer(session, shop_bot_id, telegram_id, name, None)
        await session.flush()
        return customer.id


async def _set_blocked(customer_id: int, blocked: bool) -> None:
    async with session_scope() as session:
        row = await session.get(Customer, customer_id)
        row.is_blocked = blocked


async def _customer(customer_id: int) -> Customer:
    async with session_scope() as session:
        return await session.get(Customer, customer_id)


async def _wallet_balance(owner_tg_id: int = OWNER_TG_ID) -> int:
    async with session_scope() as session:
        owner = (await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == owner_tg_id))).scalar_one()
        return owner.wallet_balance_toman


# ============================================================================= ۱ — خالص
def test_notice_cooldown_and_isolation_pure() -> None:
    shop_middlewares.reset_notice_cache()
    clock = [1000.0]

    def now() -> float:
        return clock[0]

    assert shop_middlewares.notice_allowed(1, 10, now()) is True, "اولین پیامِ ادبی می‌رود"
    assert shop_middlewares.notice_allowed(1, 10, now()) is False, "در کول‌دن تکرار نمی‌شود"
    assert shop_middlewares.notice_allowed(1, 11, now()) is True, "مشتریِ دیگر جداست"
    assert shop_middlewares.notice_allowed(2, 10, now()) is True, "فروشگاهِ دیگر جداست (ایزولاسیون)"
    clock[0] += shop_middlewares.NOTICE_COOLDOWN_SECONDS + 1
    assert shop_middlewares.notice_allowed(1, 10, now()) is True, "بعد از کول‌دن دوباره یک پیام می‌رود"
    shop_middlewares.reset_notice_cache()
    print("✅ test_notice_cooldown_and_isolation_pure PASSED")


async def test_conversation_pagination() -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    customer_id = await _seed_customer(shop_bot_id)
    async with session_scope() as session:
        for index in range(1, 26):
            await conversation_service.save_turn(session, customer_id, f"سوالِ {index}", f"جوابِ {index}")

    async with session_scope() as session:
        messages, page, total_pages, total = await conversation_service.get_history_page(session, customer_id, 0)
        assert (total, total_pages, page) == (50, 5, 0)
        assert len(messages) == 10
        assert messages[-1].content == "جوابِ 25", "صفحه‌یِ اول = تازه‌ترین‌ها"
        assert messages[0].role == "assistant" or messages[0].role == "user"

        last_page, page, total_pages, _ = await conversation_service.get_history_page(session, customer_id, 99)
        assert page == total_pages - 1, "صفحه‌یِ خارجِ بازه snap می‌شود"
        assert last_page[0].content == "سوالِ 1", "کهنه‌ترین پیام در آخرین صفحه"

        empty, page, total_pages, total = await conversation_service.get_history_page(session, 999_999, 0)
        assert (empty, total, total_pages) == ([], 0, 1)
    print("✅ test_conversation_pagination PASSED")


# ============================================================================= ۲ — پنلِ فروشگاه‌دار
async def test_owner_block_flow_from_menu(main_dp) -> None:
    await reset_database()
    shop_middlewares.reset_notice_cache()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    customer_id = await _seed_customer(shop_bot_id)
    owner = Chat(main_dp, OWNER_TG_ID)

    # مسیرِ واقعیِ منو: 👥 مشتری‌ها ← بخش ← کارتِ مشتری
    await owner.say("👥 مشتری‌ها")
    segments = [data for data in _datas(owner.last_markup) if data.startswith("crm_seg:")]
    assert segments, _datas(owner.last_markup)
    for segment in segments:
        await owner.tap(segment)
        if f"crm_card:{customer_id}" in _datas(owner.last_edit_markup):
            break
    else:  # مشتریِ بدونِ خرید باید در یکی از بخش‌ها دیده شود
        raise AssertionError("کارتِ مشتری در هیچ بخشی پیدا نشد")
    await owner.tap(f"crm_card:{customer_id}")
    assert f"crm_block:{customer_id}" in _datas(owner.last_edit_markup)
    assert main_texts.CRM_BLOCKED_BADGE not in owner.last_edit_text

    # بلاک
    await owner.tap(f"crm_block:{customer_id}")
    assert owner.last_toast["text"] == main_texts.CRM_BLOCK_DONE
    assert (await _customer(customer_id)).is_blocked is True
    assert main_texts.CRM_BLOCKED_BADGE in owner.last_edit_text
    assert f"crm_unblock:{customer_id}" in _datas(owner.last_edit_markup)

    # دابل‌تپ: دو بارِ دیگر هم همان «بلاک» ⇒ وضعیت برنمی‌گردد
    await owner.tap(f"crm_block:{customer_id}")
    await owner.tap(f"crm_block:{customer_id}")
    assert (await _customer(customer_id)).is_blocked is True, "دو کالبکِ جدا ⇒ دابل‌تپ بی‌اثر"

    async with session_scope() as session:
        entries = list(
            (
                await session.execute(
                    select(AuditLogEntry).where(AuditLogEntry.event_type == AuditEventType.CUSTOMER_BLOCK_CHANGED.value)
                )
            )
            .scalars()
            .all()
        )
        assert entries and entries[0].shop_bot_id == shop_bot_id, "بلاک باید در ممیزی ثبت شود"
        assert "blocked=True" in (entries[0].details or "")

    # رفعِ بلاک
    await owner.tap(f"crm_unblock:{customer_id}")
    assert owner.last_toast["text"] == main_texts.CRM_UNBLOCK_DONE
    assert (await _customer(customer_id)).is_blocked is False
    assert f"crm_block:{customer_id}" in _datas(owner.last_edit_markup)
    print("✅ test_owner_block_flow_from_menu PASSED")


async def test_owner_conversation_view(main_dp) -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    customer_id = await _seed_customer(shop_bot_id, name="علی")
    async with session_scope() as session:
        for index in range(1, 13):
            await conversation_service.save_turn(session, customer_id, f"سوالِ {index}", f"جوابِ {index}")
    owner = Chat(main_dp, OWNER_TG_ID)

    await owner.tap(f"crm_conv:{customer_id}:0")
    assert "💬 گفتگو با علی" in owner.last_edit_text
    assert "در مجموع 24 پیام" in owner.last_edit_text
    assert "👤 مشتری" in owner.last_edit_text and "🤖 ربات" in owner.last_edit_text
    assert f"crm_conv:{customer_id}:1" in _datas(owner.last_edit_markup), "صفحه‌یِ بعد"
    assert f"crm_card:{customer_id}" in _datas(owner.last_edit_markup)

    await owner.tap(f"crm_conv:{customer_id}:1")
    assert "صفحه‌یِ 2 از 3" in owner.last_edit_text
    assert f"crm_conv:{customer_id}:0" in _datas(owner.last_edit_markup), "صفحه‌یِ قبل"

    # صفحه‌یِ خارجِ بازه snap می‌شود (نه خطا)
    await owner.tap(f"crm_conv:{customer_id}:99")
    assert "صفحه‌یِ 3 از 3" in owner.last_edit_text

    # کلیدهایِ دستکاری‌شده ⇒ پیامِ مودبانه، نه خطا
    for bad in (f"crm_conv:{customer_id}:abc", "crm_conv:abc:0", f"crm_conv:{customer_id}", "crm_conv:", "crm_conv:1:2:3"):
        await owner.tap(bad)
        assert owner.last_toast["text"] == main_texts.CRM_STALE_BUTTON, bad

    # گفتگویِ خالی
    other = await _seed_customer(shop_bot_id, telegram_id=CUSTOMER_TG_ID + 1, name="بی‌گفتگو")
    await owner.tap(f"crm_conv:{other}:0")
    assert owner.last_edit_text == main_texts.CRM_CONVERSATION_EMPTY
    print("✅ test_owner_conversation_view PASSED")


# ============================================================================= ۳ — رباتِ فروشگاه
async def test_blocked_customer_costs_nothing(shop_dp) -> None:
    await reset_database()
    shop_middlewares.reset_notice_cache()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    customer_id = await _seed_customer(shop_bot_id)
    shop = _Shop(shop_dp, SHOP_BOT_TG_ID)

    # پیش از بلاک: مسیرِ عادی کار می‌کند
    await shop.say("/start")
    assert shop.sent[-1]["text"] == shop_texts.SHOP_WELCOME, shop.sent[-1]["text"]

    await _set_blocked(customer_id, True)
    sent_before = len(shop.sent)
    await shop.say("سلام، یه سوال داشتم")
    new = shop.sent[sent_before:]
    assert len(new) == 1 and new[0]["text"] == shop_texts.CUSTOMER_BLOCKED_NOTICE, new
    assert await _wallet_balance() == TEST_WALLET_BALANCE_TOMAN, "هیچ هزینه‌یِ AI نباید کسر شود"

    # پیامِ پشتِ‌همِ دیگر در کول‌دن ⇒ سکوت (نه اسپم)
    await shop.say("چرا جواب نمی‌دی؟")
    assert len(shop.sent) == sent_before + 1, "حداکثر یک پیامِ ادبی در هر کول‌دن"

    # عکس و صدا هم رد می‌شوند: نه تحلیلِ عکس، نه صوت‌به‌متن، نه کسرِ کیف‌پول
    for kwargs in ({"photo": True}, {"voice": True}):
        shop._n += 1
        await shop_dp.feed_update(shop.bot, make_message_update(shop._n, user_id=CUSTOMER_TG_ID, **kwargs))
        assert len(shop.sent) == sent_before + 1, "عکس/صدایِ مشتریِ بلاک هیچ پیامِ تازه‌ای نمی‌سازد"
    assert await _wallet_balance() == TEST_WALLET_BALANCE_TOMAN, "نه تحلیلِ عکس، نه STT: هزینه صفر"

    # کالبک‌ها: فقط پاسخِ بی‌صدا، بدونِ پیام
    sent_before = len(shop.sent)
    await shop.tap("cart_view")
    await shop.tap("cart_browse:0")
    assert len(shop.sent) == sent_before, "کالبکِ مشتریِ بلاک هیچ پیامی نمی‌سازد"
    assert shop.session.answered_callbacks, "اسپینرِ تلگرام نباید گیر کند"

    # هیچ سفارش/گروهی ساخته نشده
    async with session_scope() as session:
        assert list((await session.execute(select(OrderConsultation))).scalars().all()) == []

    # رفعِ بلاک ⇒ دوباره عادی
    await _set_blocked(customer_id, False)
    shop_middlewares.reset_notice_cache()
    await shop.say("/start")
    assert shop.sent[-1]["text"] == shop_texts.SHOP_WELCOME
    print("✅ test_blocked_customer_costs_nothing PASSED")


# ============================================================================= ۴ — ایزولاسیون و IDOR
async def test_isolation_and_idor(main_dp, shop_dp) -> None:
    await reset_database()
    shop_middlewares.reset_notice_cache()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    other_shop_bot_id = await seed_usable_shop(OTHER_OWNER_TG_ID, OTHER_SHOP_BOT_TG_ID)
    customer_id = await _seed_customer(shop_bot_id)
    same_person_elsewhere = await _seed_customer(other_shop_bot_id, name="همان آدم در فروشگاهِ دیگر")
    await _set_blocked(customer_id, True)

    # همان telegram_id در فروشگاهِ دیگر بلاک نیست و عادی کار می‌کند
    other_shop = _Shop(shop_dp, OTHER_SHOP_BOT_TG_ID)
    await other_shop.say("/start")
    assert other_shop.sent[-1]["text"] == shop_texts.SHOP_WELCOME, "بلاک فقط برایِ همان فروشگاه است"

    # مالکِ دیگر هیچ دسترسی‌ای به مشتریِ من ندارد
    stranger = Chat(main_dp, OTHER_OWNER_TG_ID)
    for data in (f"crm_card:{customer_id}", f"crm_conv:{customer_id}:0", f"crm_block:{customer_id}", f"crm_unblock:{customer_id}"):
        await stranger.tap(data)
        assert stranger.last_toast["text"] == main_texts.CRM_NOT_FOUND, data
    assert (await _customer(customer_id)).is_blocked is True, "مالکِ دیگر نتوانست رفعِ بلاک کند"
    assert (await _customer(same_person_elsewhere)).is_blocked is False, "و نتوانست بلاک کند"

    # مشتریِ بلاک همچنان در CRM/آمارِ همان فروشگاه شمرده می‌شود
    async with session_scope() as session:
        stats, _ = await crm_service.load_stats(session, shop_bot_id)
        assert [s.customer_id for s in stats] == [customer_id], "بلاک ⇒ حذف/پنهان از آمار نیست"
    print("✅ test_isolation_and_idor PASSED")


async def main() -> None:
    main_dp, shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    test_notice_cooldown_and_isolation_pure()
    await test_conversation_pagination()
    await test_owner_block_flow_from_menu(main_dp)
    await test_owner_conversation_view(main_dp)
    await test_blocked_customer_costs_nothing(shop_dp)
    await test_isolation_and_idor(main_dp, shop_dp)


if __name__ == "__main__":
    asyncio.run(main())
