"""
تست: P40 · بچ A — پنج رفعِ کم‌ریسک از بازرسیِ فنی/امنیتی (۱۴۰۵-۰۸-۱۴)

پوشش (شماره‌ها همان شماره‌هایِ گزارشِ بازرسی است):
۱. A1 — `/webhook/bale` بدونِ رازِ مسیری: در `BALE_UPDATES_MODE=polling` (پیش‌فرضِ .env) هیچ
   رازی ساخته نمی‌شود ⇒ مسیر باید ۴۰۴ بدهد؛ در حالتِ webhook با هدرِ درست قبول و با هدرِ
   غلط/نبودِ هدر ۴۰۳.
۲. A3 — رازِ وب‌هوک در `payment_event_logs.raw` ماسک می‌شود (`setWebhook` و `getWebhookInfo`)،
   بدونِ از‌بین‌بردنِ شناسهٔ عددیِ `/webhook/shop/42`.
۳. A2 — پاسخِ AI به سقفِ ۴۰۹۶ نویسه برش می‌خورد، تاریخچه فقط پس ازِ ارسالِ موفق نوشته می‌شود،
   پاسخِ نرسیده هزینه کم نمی‌کند، و متنِ جمع‌شدهٔ مشتری به ۸۰۰۰ نویسه محدود می‌شود.
۴. A4 — «سفارشت پرداخت شد» و فاکتور وقتی گروه جلو نرفته (needs_review) به مشتری نمی‌رود، ولی
   فروشگاه‌دار همان خطِ «نیازِ بررسی» را می‌بیند.
۵. A5 — دو ایندکسِ partial ساخته شده‌اند و اسکنِ مهلتِ پرداخت حالا batching دارد.

اجرا: python3 tests_manual/run_one.py test_p40_inspection_fixes.py
"""
from __future__ import annotations

import asyncio
import datetime
import sys
from types import SimpleNamespace

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from sqlalchemy import select, text  # noqa: E402

from harness import FakeSession, build_test_dispatchers, make_message_update, register_fake_shop_bot, reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app import main as app_main  # noqa: E402
from app.bots.shop_bot import texts as shop_texts  # noqa: E402
from app.bots.shop_bot.handlers import customer as customer_handlers  # noqa: E402
from app.config import settings  # noqa: E402
from app.database.models import ConversationMessage, OrderStatus, OrderType  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import (  # noqa: E402
    ai_service,
    bale_credentials_service,
    customer_service,
    order_payment_service,
    order_service,
    order_state,
    payment_event_service,
    payment_notify_service,
    shop_owner_service,
)
from app.services.ai_service import AiCallResult  # noqa: E402
from app.services.order_detection_service import _CLASSIFIER_USER_PROMPT  # noqa: E402
from app.utils import text_limits  # noqa: E402

OWNER_TG_ID = 7_440_000_011
SHOP_BOT_TG_ID = 7_440_000_012
CUSTOMER_TG_ID = 7_440_000_013
BALE_FAKE_TOKEN = "111111:BALEFAKEPLATFORMTOKENTEST00000"
WEBHOOK_SECRET = "راز-آزمونِ-وب‌هوک-بله"
LONG_REPLY = "قیمتِ مداد ۱۲٬۰۰۰ تومان است. " * 300  # >۴۰۹۶ نویسه


# ============================================================================= A1 — وب‌هوکِ بله
class _Req:
    """جایِ `Request` استارلت: فقط همان سه چیزی که مسیر مصرف می‌کند را دارد."""

    def __init__(self, headers: dict | None = None) -> None:
        self.headers = headers or {}
        self.client = SimpleNamespace(host="127.0.0.1")

    async def json(self) -> dict:
        return {"message": {"text": "/start payment-0-0", "chat": {"id": 5}}}


async def test_bare_bale_webhook_is_closed_outside_webhook_mode() -> None:
    await reset_database()
    saved = (settings.bale_updates_mode, settings.bale_webhook_secret, settings.bale_bot_token)
    calls: list[dict] = []
    real_dispatch = app_main._dispatch_bale_update

    async def fake_dispatch(data, token=None):
        calls.append(data)

    app_main._dispatch_bale_update = fake_dispatch  # type: ignore[assignment]
    try:
        settings.bale_bot_token = BALE_FAKE_TOKEN
        bale_credentials_service.reset_cache()

        # الف) polling (پیش‌فرضِ .env): هیچ رازی ساخته نشده ⇒ مسیر نباید سرویس شود
        settings.bale_updates_mode = "polling"
        settings.bale_webhook_secret = ""
        assert (await app_main.webhook_bale(_Req())).status_code == 404, "در polling مسیرِ بی‌راز باید بسته باشد"

        # ب) polling حتی با هدرِ درست هم سرویس نمی‌شود (پلتفرم در این حالت وب‌هوک ثبت نکرده)
        settings.bale_webhook_secret = WEBHOOK_SECRET
        assert (await app_main.webhook_bale(_Req({"X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET}))).status_code == 404
        assert calls == [], "هیچ آپدیتِ جعلی نباید پردازش شود"

        # ج) حالتِ webhook: بدونِ هدر ⇒ ۴۰۳، هدرِ غلط ⇒ ۴۰۳، هدرِ درست ⇒ پردازش
        settings.bale_updates_mode = "webhook"
        assert (await app_main.webhook_bale(_Req())).status_code == 403
        assert (await app_main.webhook_bale(_Req({"X-Telegram-Bot-Api-Secret-Token": "غلط"}))).status_code == 403
        assert calls == []
        assert (await app_main.webhook_bale(_Req({"X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET}))).status_code == 200
        assert len(calls) == 1, calls

        # د) حالتِ webhook ولی راز هنوز ساخته نشده (دیتابیس در دسترس نبود) ⇒ باز هم بسته
        settings.bale_webhook_secret = ""
        assert (await app_main.webhook_bale(_Req({"X-Telegram-Bot-Api-Secret-Token": "هرچیزی"}))).status_code == 404
    finally:
        settings.bale_updates_mode, settings.bale_webhook_secret, settings.bale_bot_token = saved
        app_main._dispatch_bale_update = real_dispatch  # type: ignore[assignment]
        bale_credentials_service.reset_cache()
    print("✅ test_bare_bale_webhook_is_closed_outside_webhook_mode PASSED")


# ============================================================================= A3 — ماسکِ رازِ وب‌هوک
def test_webhook_secret_is_masked_in_payment_event_log() -> None:
    raw = {
        "request": {"url": f"https://panel.example.test/webhook/bale/{WEBHOOK_SECRET}"},
        "response": {"result": [{"url": f"https://panel.example.test/webhook/bale/{WEBHOOK_SECRET}", "pending_update_count": 3}]},
    }
    out = payment_event_service.sanitize(raw)
    assert WEBHOOK_SECRET not in out, out
    assert "/webhook/bale/***" in out, out
    assert "pending_update_count" in out, "بقیهٔ شاهدِ عیب‌یابی نباید از دست برود"

    main_path = payment_event_service.sanitize({"url": "https://x.test/webhook/main/SuperLongSecret123"})
    assert "SuperLongSecret123" not in main_path, main_path

    # شناسهٔ عددیِ مسیرِ فروشگاه راز نیست و باید بماند (بیش‌ماسک‌کردن = کورشدنِ عیب‌یابی)
    shop_path = payment_event_service.sanitize({"url": "https://x.test/webhook/shop/42"})
    assert "/webhook/shop/42" in shop_path, shop_path
    print("✅ test_webhook_secret_is_masked_in_payment_event_log PASSED")


# ============================================================================= A2 — پاسخِ AI
class _FakeAi:
    def __init__(self, reply: str = LONG_REPLY) -> None:
        self.reply = reply
        self.received: list[str] = []

    async def get_reply(self, system_prompt: str, history, user_message: str) -> AiCallResult:
        if user_message != _CLASSIFIER_USER_PROMPT:
            self.received.append(user_message)
        return AiCallResult(text='{"status": "none"}' if user_message == _CLASSIFIER_USER_PROMPT else self.reply, total_tokens=50)

    async def analyze_image(self, prompt: str, image_bytes: bytes, mime_type: str = "image/jpeg") -> AiCallResult:
        return AiCallResult(text="تحلیل", total_tokens=1)

    async def transcribe_audio(self, audio_bytes: bytes, filename: str = "voice.ogg") -> str:
        return "رونویسی"


async def _owner_balance(owner_tg_id: int) -> int:
    async with session_scope() as session:
        owner = await shop_owner_service.get_by_telegram_id(session, owner_tg_id)
        return int(owner.wallet_balance_toman or 0) if owner is not None else -1


async def _assistant_rows() -> list[str]:
    async with session_scope() as session:
        rows = (
            await session.execute(
                select(ConversationMessage).where(ConversationMessage.role == "assistant").order_by(ConversationMessage.id)
            )
        ).scalars().all()
    return [r.content for r in rows]


async def test_long_ai_reply_is_clipped(shop_dp) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID, initial_balance_toman=200_000)
    fake = _FakeAi()
    original = ai_service.get_ai_service
    ai_service.get_ai_service = lambda *a, **k: fake
    try:
        bot = Bot(token=f"{SHOP_BOT_TG_ID}:CLIPFAKETOKENFORTESTS00000000AB", session=FakeSession())
        session_obj: FakeSession = bot.session  # type: ignore[assignment]
        await shop_dp.feed_update(bot, make_message_update(1, text="قیمتِ مداد؟", user_id=CUSTOMER_TG_ID))
        await asyncio.sleep(4.5)

        delivered = [m["text"] for m in session_obj.sent_messages]
        assert delivered, "پاسخی نرفت"
        body = max(delivered, key=len)
        assert len(body) <= text_limits.TELEGRAM_TEXT_LIMIT, len(body)
        assert body.endswith("…"), "برش باید با علامتِ «ادامه داشت» دیده شود"
        assert await _owner_balance(OWNER_TG_ID) < 200_000, "پاسخِ رسیده هزینه دارد"
        history = await _assistant_rows()
        assert len(history) == 1 and history[0] == body, (len(history), history[:1])
        assert "**" not in body
    finally:
        ai_service.get_ai_service = original
    print("✅ test_long_ai_reply_is_clipped PASSED")


async def test_undelivered_reply_costs_nothing_and_is_not_stored(shop_dp) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID, initial_balance_toman=200_000)
    fake = _FakeAi(reply="پاسخِ کوتاهِ آزمایشی")
    original = ai_service.get_ai_service
    ai_service.get_ai_service = lambda *a, **k: fake
    try:
        bot = Bot(token=f"{SHOP_BOT_TG_ID}:FAILFAKETOKENFORTESTS00000000AB", session=FakeSession())

        async def raiser(*_a, **_k):
            raise TelegramAPIError(method="sendMessage", message="probe: send failed")

        real_send = bot.send_message
        bot.send_message = raiser  # type: ignore[method-assign]
        before = await _owner_balance(OWNER_TG_ID)
        try:
            await shop_dp.feed_update(bot, make_message_update(1, text="قیمتِ مداد؟", user_id=CUSTOMER_TG_ID))
            await asyncio.sleep(4.5)
        finally:
            bot.send_message = real_send  # type: ignore[method-assign]
        assert await _owner_balance(OWNER_TG_ID) == before, "پاسخِ نرسیده نباید کیف‌پول را کم کند"
        assert await _assistant_rows() == [], "تاریخچه فقط پس ازِ ارسالِ موفق نوشته می‌شود"
    finally:
        ai_service.get_ai_service = original
    print("✅ test_undelivered_reply_costs_nothing_and_is_not_stored PASSED")


async def test_combined_customer_text_is_capped(shop_dp) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID, initial_balance_toman=200_000)
    fake = _FakeAi(reply="بله")
    original = ai_service.get_ai_service
    ai_service.get_ai_service = lambda *a, **k: fake
    try:
        bot = Bot(token=f"{SHOP_BOT_TG_ID}:CAPFAKETOKENFORTESTS00000000AB", session=FakeSession())
        for i in range(3):
            await shop_dp.feed_update(bot, make_message_update(10 + i, text="ا" * 3_900, user_id=CUSTOMER_TG_ID))
        await asyncio.sleep(4.5)
        assert fake.received, "پرامپت ساخته نشد"
        assert len(fake.received[0]) <= customer_handlers.COMBINED_TEXT_MAX_CHARS, len(fake.received[0])
        assert fake.received[0].endswith("…"), "برش باید علامت‌دار باشد"
    finally:
        ai_service.get_ai_service = original
    print("✅ test_combined_customer_text_is_capped PASSED")


# ============================================================================= A4 — needs_review
async def test_review_case_does_not_confirm_to_customer(main_bot, bot_manager) -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    async with session_scope() as session:
        customer = await customer_service.get_or_create_customer(session, shop_bot_id, CUSTOMER_TG_ID, "مشتری", None)
        order = await order_service.create_order(session, shop_bot_id, customer.id, OrderType.ORDER, "خلاصه", 200_000)
        order.status = OrderStatus.AWAITING_PAYMENT
        order_id = order.id
        await session.commit()

    shop_bot_instance = Bot(token=f"{SHOP_BOT_TG_ID}:NOTIFYFAKETOKENFORTESTS0000", session=FakeSession())
    register_fake_shop_bot(bot_manager, shop_bot_id, shop_bot_instance)
    main_bot.session.sent_messages.clear()

    await payment_notify_service.notify_online_payment(
        main_bot, bot_manager, shop_bot_id, [order_id], method="bale", late=False, needs_review=True, oversold=False,
        final_status="awaiting_payment",
    )
    assert shop_bot_instance.session.sent_messages == [], "به مشتریِ پرداختِ نامشخص نباید تایید برود"
    assert shop_bot_instance.session.sent_documents == [], "فاکتور هم نباید برود"
    owner_msg = main_bot.session.sent_messages[-1]["text"]
    assert "بله‌پی" in owner_msg and "نیازِ بررسی" in owner_msg, owner_msg

    main_bot.session.sent_messages.clear()
    await payment_notify_service.notify_online_payment(
        main_bot, bot_manager, shop_bot_id, [order_id], method="bale", late=False, needs_review=False, oversold=False,
        final_status="paid",
    )
    cust = [m["text"] for m in shop_bot_instance.session.sent_messages]
    assert any("پرداخت" in t for t in cust), cust
    assert shop_bot_instance.session.sent_documents, "در حالتِ عادی فاکتور می‌رود"
    assert not hasattr(shop_texts, "ONLINE_PAYMENT_CONFIRMED"), "پیامِ قدیمیِ بی‌نامِ روش حذف بماند"
    print("✅ test_review_case_does_not_confirm_to_customer PASSED")


# ============================================================================= A5 — ایندکس‌ها و batching
async def test_indexes_exist_and_expiry_scan_is_bounded() -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    async with session_scope() as session:
        names = set(
            (await session.execute(text("select indexname from pg_indexes where tablename = 'orders_consultations'"))).scalars().all()
        )
    assert "ix_orders_reservation_expires" in names, sorted(names)
    assert "ix_orders_bale_transaction" in names, sorted(names)

    async with session_scope() as session:
        customer = await customer_service.get_or_create_customer(session, shop_bot_id, CUSTOMER_TG_ID, "مشتری", None)
        past = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=5)
        for _ in range(2):
            order = await order_service.create_order(session, shop_bot_id, customer.id, OrderType.ORDER, "خ", 50_000)
            order.status = OrderStatus.AWAITING_PAYMENT
            order.reservation_expires_at = past
            order.cart_checkout_group_id = f"g{order.id}"
        await session.commit()

    saved = order_state.EXPIRY_SCAN_BATCH
    order_state.EXPIRY_SCAN_BATCH = 1
    try:
        async with session_scope() as session:
            groups = await order_payment_service.expire_stale_payment_groups(session)
            await session.commit()
    finally:
        order_state.EXPIRY_SCAN_BATCH = saved
    assert saved == 200, saved
    assert len(groups) == 1, f"هر دور حداکثر به سقفِ batch کار می‌کند، شد {len(groups)}"
    print("✅ test_indexes_exist_and_expiry_scan_is_bounded PASSED")


async def main() -> None:
    _main_dp, shop_dp, bot_manager, main_bot = build_test_dispatchers()
    await test_bare_bale_webhook_is_closed_outside_webhook_mode()
    test_webhook_secret_is_masked_in_payment_event_log()
    await test_long_ai_reply_is_clipped(shop_dp)
    await test_undelivered_reply_costs_nothing_and_is_not_stored(shop_dp)
    await test_combined_customer_text_is_capped(shop_dp)
    await test_review_case_does_not_confirm_to_customer(main_bot, bot_manager)
    await test_indexes_exist_and_expiry_scan_is_bounded()


if __name__ == "__main__":
    asyncio.run(main())
