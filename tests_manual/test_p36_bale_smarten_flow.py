"""
تست: P36 — هوشمندسازیِ رباتِ بلهٔ فروشگاه (همان مسیرِ AI، همان کیف‌پول، مالکیتِ یکِ رونوشت)

پوشش:
۱. مشتریِ بله‌ای از همان روترهایِ فروشگاهی رد می‌شود: یکِ پاسخِ AI می‌گیرد، آن پاسخ از **همان
   رباتِ بله** می‌رود، هزینه از کیف‌پولِ همان فروشگاه کم می‌شود و ردیفِ مشتری `platform=bale` است.
۲. دروازهٔ مالکیتِ polling: با `bale_polling_owner=False` هیچ اتصالِ بله‌ای شروع نمی‌شود (دیپلویِ
   چندرونشتی)، با `True` شروع می‌شود — با وجودِ این‌که سوییچِ ادمین روشن و توکنِ فروشگاه ثبت است.
۳. درست بعد ازِ وصل‌کردنِ رباتِ تلگرام، پنل «🔵 توکنِ رباتِ بله» را پیشنهاد می‌دهد (اگر ویژگی
   رونمایی شده باشد و فروشگاه توکنِ بله نداشته باشد)؛ با توکنِ بله‌یِ ثبت‌شده پیشنهاد نمی‌دهد.

اجرا: python3 tests_manual/run_one.py test_p36_bale_smarten_flow.py
"""
from __future__ import annotations

import asyncio
import sys
from types import SimpleNamespace

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot
from sqlalchemy import select

from harness import FakeSession, build_test_dispatchers, make_message_update, reset_database  # noqa: E402
from phase4_helpers import Chat  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app import main as app_main  # noqa: E402
from app.bots.main_bot import texts  # noqa: E402
from app.bots.main_bot.handlers import panel as panel_handlers  # noqa: E402
from app.database.models import (  # noqa: E402
    Customer,
    ShopBot,
    ShopOwner,
    WalletTransaction,
    WalletTransactionReason,
)
from app.database.session import session_scope  # noqa: E402
from app.services import ai_service, platform_service  # noqa: E402
from app.services.ai_service import AiCallResult  # noqa: E402
from app.services.admin_settings_service import update_setting  # noqa: E402
from app.services.order_detection_service import _CLASSIFIER_USER_PROMPT  # noqa: E402

OWNER_TG_ID = 7_200_000_071
SHOP_BOT_TG_ID = 7_200_000_072
CUSTOMER_TG_ID = 7_200_000_073
BALE_BOT_ID = 7_200_000_074
BALE_TOKEN = f"{BALE_BOT_ID}:SHOPBALEFAKETOKENFORTESTS000000"
NEW_TG_BOT_ID = 7_200_000_075
NEW_TG_TOKEN = f"{NEW_TG_BOT_ID}:NEWSHOPBOTFAKETOKENFORTESTS0000"


class _FakeAiService:
    def __init__(self) -> None:
        self.received_prompts: list[str] = []

    async def get_reply(self, system_prompt: str, history: list[dict[str, str]], user_message: str) -> AiCallResult:
        if user_message != _CLASSIFIER_USER_PROMPT:
            self.received_prompts.append(user_message)
        text = '{"status": "none"}' if user_message == _CLASSIFIER_USER_PROMPT else "این پاسخِ آزمایشیِ هوشِ مصنوعیه."
        return AiCallResult(text=text, total_tokens=42)

    async def analyze_image(self, prompt: str, image_bytes: bytes, mime_type: str = "image/jpeg") -> AiCallResult:
        return AiCallResult(text="تحلیلِ آزمایشیِ تصویر", total_tokens=42)

    async def transcribe_audio(self, audio_bytes: bytes, filename: str = "voice.ogg") -> str:
        return "متنِ آزمایشیِ رونویسی‌شده"


async def _connect_bale(shop_bot_id: int) -> None:
    """همان چیزی که پنل پس ازِ `getMe`یِ بله می‌نویسد (بی‌شبکه: توکن و شناسه را مستقیم می‌گذاریم)."""
    async with session_scope() as session:
        shop_bot = await session.get(ShopBot, shop_bot_id)
        shop_bot.bale_encrypted_token = BALE_TOKEN
        shop_bot.bale_bot_id = BALE_BOT_ID
        shop_bot.bale_bot_username = "shop_bale_bot"
        shop_bot.bale_bot_enabled = True
        await session.flush()


async def _reveal(enabled: bool) -> None:
    async with session_scope() as session:
        await update_setting(session, "bale_shop_bots_enabled", enabled)


def _bale_bot() -> Bot:
    bot = Bot(token=BALE_TOKEN, session=FakeSession())
    bot.bale_platform = True
    return bot


# ============================================================================= ۱ — همان مسیر، همان هزینه
async def test_bale_customer_is_answered_and_charged(shop_dp, main_bot, bot_manager) -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID, initial_balance_toman=10_000)
    await _connect_bale(shop_bot_id)
    await _reveal(True)

    fake_ai = _FakeAiService()
    original = ai_service.get_ai_service
    ai_service.get_ai_service = lambda *_args, **_kwargs: fake_ai
    bale_bot = _bale_bot()
    bot_manager._bale_bots[shop_bot_id] = bale_bot
    try:
        await shop_dp.feed_update(bale_bot, make_message_update(1, text="قیمتِ محصولِ الف چنده؟", user_id=CUSTOMER_TG_ID))
        await asyncio.sleep(4.5)

        sent = [m["text"] for m in bale_bot.session.sent_messages]
        assert any("پاسخِ آزمایشیِ هوشِ مصنوعی" in t for t in sent), sent
        assert fake_ai.received_prompts == ["قیمتِ محصولِ الف چنده؟"], fake_ai.received_prompts

        async with session_scope() as session:
            owner = (await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == OWNER_TG_ID))).scalar_one()
            assert owner.wallet_balance_toman < 10_000, "هزینه‌یِ پاسخِ بله‌ای باید از کیف‌پول کم شود"
            rows = (
                await session.execute(
                    select(WalletTransaction).where(
                        WalletTransaction.shop_owner_id == owner.id,
                        WalletTransaction.reason == WalletTransactionReason.CHAT_MESSAGE,
                    )
                )
            ).scalars().all()
            assert len(rows) == 1, rows
            customers = (await session.execute(select(Customer).where(Customer.shop_bot_id == shop_bot_id))).scalars().all()
            assert [c.platform for c in customers] == [platform_service.BALE], customers
    finally:
        ai_service.get_ai_service = original
        await bale_bot.session.close()
    print("✅ test_bale_customer_is_answered_and_charged PASSED")


# ============================================================================= ۲ — دروازهٔ مالکیتِ polling
async def test_bale_polling_starts_only_on_the_lock_holder(bot_manager, main_bot) -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    await _connect_bale(shop_bot_id)
    await _reveal(True)

    registered: list[int] = []

    async def fake_register(shop_bot):
        registered.append(shop_bot.id)

    async def fake_telegram_register(shop_bot):
        return None

    bot_manager.register_bale = fake_register  # type: ignore[method-assign]
    bot_manager.register = fake_telegram_register  # type: ignore[method-assign]
    try:
        await app_main._load_active_shop_bots(bot_manager, main_bot, bale_polling_owner=False)
        assert registered == [], "رونوشتِ بدونِ قفل نباید pollingِ بله را شروع کند"
        await app_main._load_active_shop_bots(bot_manager, main_bot, bale_polling_owner=True)
        assert registered == [shop_bot_id], registered
    finally:
        del bot_manager.register_bale
        del bot_manager.register
    print("✅ test_bale_polling_starts_only_on_the_lock_holder PASSED")


# ============================================================================= ۳ — پیشنهادِ اتصالِ بله در اتصالِ اولیه
class _FakeTelegramBot:
    """جایِ `panel.Bot` — `get_me`یِ واقعی نیازِ شبکه دارد و در سوئیت نباید به شبکه بزند."""

    def __init__(self, token: str) -> None:
        self.token = token
        self.session = SimpleNamespace(close=lambda: asyncio.sleep(0))

    async def get_me(self):
        return SimpleNamespace(id=NEW_TG_BOT_ID, username="new_shop_bot")


async def test_bale_is_offered_right_after_telegram_token(main_dp, bot_manager) -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    await _reveal(True)
    registered: list[int] = []

    async def fake_register(shop_bot):
        registered.append(shop_bot.id)

    real_bot_class = panel_handlers.Bot
    panel_handlers.Bot = _FakeTelegramBot  # type: ignore[misc]
    bot_manager.register = fake_register  # type: ignore[method-assign]
    owner = Chat(main_dp, OWNER_TG_ID)
    try:
        await owner.say("🔑 ثبت/ویرایش توکن ربات")
        await owner.say(NEW_TG_TOKEN)
        assert registered == [shop_bot_id], registered
        last = owner.sent[-1]["text"]
        assert last == texts.BALE_SMARTEN_OFFER, last
        datas = [b.callback_data for row in owner.sent[-1]["reply_markup"].inline_keyboard for b in row]
        assert "bale_edit" in datas, datas

        # توکنِ بله دارد ⇒ پیشنهاد تکراری نمی‌بیند (فقط «وصل شد» + راهنمایِ مرحله)
        await _connect_bale(shop_bot_id)
        before = len(owner.sent)
        await owner.say("🔑 ثبت/ویرایش توکن ربات")
        await owner.say(NEW_TG_TOKEN)
        assert len(owner.sent) == before + 2, owner.sent[before:]
    finally:
        panel_handlers.Bot = real_bot_class
        del bot_manager.register
    print("✅ test_bale_is_offered_right_after_telegram_token PASSED")


async def main() -> None:
    main_dp, shop_dp, bot_manager, main_bot = build_test_dispatchers()
    await test_bale_customer_is_answered_and_charged(shop_dp, main_bot, bot_manager)
    await test_bale_polling_starts_only_on_the_lock_holder(bot_manager, main_bot)
    await test_bale_is_offered_right_after_telegram_token(main_dp, bot_manager)


if __name__ == "__main__":
    asyncio.run(main())
