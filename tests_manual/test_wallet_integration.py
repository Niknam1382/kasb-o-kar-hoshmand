"""
تست: یکپارچه‌سازیِ کیف‌پول با جریانِ واقعیِ پیام‌رسانی به مشتری (متن/تشخیصِ سفارش).

این فایل چهار نگرانیِ اصلی رو پوشش می‌ده:
۱. وقتی موجودیِ فروشگاه‌دار صفره، ربات به مشتری جواب نمی‌ده و به فروشگاه‌دار
   (فقط یه‌بار، نه هر پیام) خبر می‌ده.
۲. یه پاسخِ موفقِ چت، دقیقاً به‌اندازه‌ی توکنِ واقعی‌ای که مصرف شده از کیف‌پول کم
   می‌کنه (نه یه مقدارِ تقریبی/ثابت).
۳. باگِ مهمی که هنگامِ ساختِ این تست‌ها پیدا و فیکس شد: کلاسیفایرِ تشخیصِ سفارش
   قبلاً وقتی هیچ سفارشی «تکمیل‌شده» تشخیص نمی‌داد (رایج‌ترین حالت)، توکنِ
   مصرف‌شده‌ش رو دور می‌ریخت و اصلاً کسری از کیف‌پول اتفاق نمی‌افتاد — یعنی
   اکثرِ فراخوانی‌های کلاسیفایر «رایگان» می‌موندن. حالا حتی بدونِ تشخیصِ سفارش،
   هزینه‌ی واقعی کسر می‌شه.
۴. وقتی موجودی از یه آستانه‌ی مشخص کمتر می‌شه (ولی هنوز صفر نشده)، فروشگاه‌دار
   یه هشدارِ جداگانه می‌گیره.
۵. کارِ زمان‌بندی‌شده‌ی روزانه (wallet_expiry_service): بسته‌های واقعاً منقضی‌شده
   از موجودی کم می‌شن، و بسته‌هایی که در آستانه‌ی انقضان یادآوری می‌گیرن.

اجرا: python3 tests_manual/test_wallet_integration.py
"""
from __future__ import annotations

import asyncio
import datetime
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402
from sqlalchemy import select  # noqa: E402

from harness import FakeSession, build_test_dispatchers, make_callback_update, make_message_update, reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.database.models import OrderConsultation, ShopOwner, WalletTransaction, WalletTransactionReason  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import ai_service, shop_owner_service, wallet_expiry_service, wallet_service  # noqa: E402
from app.services.admin_settings_service import get_admin_settings  # noqa: E402
from app.services.ai_service import AiCallResult  # noqa: E402
from app.services.order_detection_service import _CLASSIFIER_USER_PROMPT  # noqa: E402

OWNER_TG_ID = 999601
SHOP_BOT_TG_ID = 999602
CUSTOMER_TG_ID = 999603


class _FakeAiServiceWithKnownTokens:
    """جواب‌های ثابت می‌ده ولی total_tokensِ متفاوت برای فراخوانیِ چت در برابرِ
    فراخوانیِ کلاسیفایرِ تشخیصِ سفارش برمی‌گردونه، تا بشه کسرِ هرکدوم رو جدا سنجید."""

    def __init__(self, chat_tokens: int = 1000, classifier_tokens: int = 500, classifier_completes_order: bool = False) -> None:
        self.chat_tokens = chat_tokens
        self.classifier_tokens = classifier_tokens
        self.classifier_completes_order = classifier_completes_order

    async def get_reply(self, system_prompt: str, history: list[dict[str, str]], user_message: str) -> AiCallResult:
        if user_message == _CLASSIFIER_USER_PROMPT:
            if self.classifier_completes_order:
                text = (
                    '{"completed": true, "type": "consultation", "summary": "مشاوره‌ی آزمایشی", '
                    '"estimated_value_toman": null, "product_id": null, "quantity": null, '
                    '"customer_phone": null, "customer_address": null}'
                )
            else:
                text = '{"completed": false}'
            return AiCallResult(text=text, total_tokens=self.classifier_tokens)
        return AiCallResult(text="این پاسخِ آزمایشیِ هوشِ مصنوعیه.", total_tokens=self.chat_tokens)

    async def analyze_image(self, prompt: str, image_bytes: bytes, mime_type: str = "image/jpeg") -> AiCallResult:
        return AiCallResult(text="", total_tokens=1)

    async def transcribe_audio(self, audio_bytes: bytes, filename: str = "voice.ogg") -> str:
        return ""


async def _get_owner(owner_tg_id: int) -> ShopOwner:
    async with session_scope() as session:
        return await shop_owner_service.get_by_telegram_id(session, owner_tg_id)


async def _sum_transactions(owner_id: int, reason: WalletTransactionReason) -> int:
    async with session_scope() as session:
        result = await session.execute(
            select(WalletTransaction.amount_toman).where(
                WalletTransaction.shop_owner_id == owner_id, WalletTransaction.reason == reason
            )
        )
        return sum(result.scalars().all())


async def test_zero_balance_blocks_message_and_notifies_owner_once(shop_dp, main_bot) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID, initial_balance_toman=0)

    shop_bot_instance = Bot(token=f"{SHOP_BOT_TG_ID}:FAKE", session=FakeSession())
    shop_session_obj: FakeSession = shop_bot_instance.session  # type: ignore[assignment]

    main_session_obj: FakeSession = main_bot.session  # type: ignore[assignment]
    main_session_obj.sent_messages.clear()

    await shop_dp.feed_update(shop_bot_instance, make_message_update(1, text="سلام", user_id=CUSTOMER_TG_ID))
    await asyncio.sleep(0.2)  # _check_access سینکرونه، نیازی به صبرِ debounce نیست

    assert len(shop_session_obj.sent_messages) == 1, "مشتری باید دقیقاً یه پیامِ «فروشگاه در دسترس نیست» بگیره"
    assert "دسترس نیست" in shop_session_obj.sent_messages[0]["text"], "پیام باید نبودِ دسترسی رو اعلام کنه، نه خطای کیف‌پول"

    owner_notifications = [m for m in main_session_obj.sent_messages if m["chat_id"] == OWNER_TG_ID]
    assert len(owner_notifications) == 1, f"فروشگاه‌دار باید دقیقاً یه اطلاع از اتمامِ کیف‌پول بگیره، نه {len(owner_notifications)} تا"
    assert "موجودیِ کیف‌پولت تموم شده" in owner_notifications[0]["text"]

    # پیامِ دومِ مشتری (وقتی موجودی هنوز صفره) نباید یه اطلاع‌رسانیِ تکراری بسازه
    await shop_dp.feed_update(shop_bot_instance, make_message_update(2, text="کسی هست؟", user_id=CUSTOMER_TG_ID))
    await asyncio.sleep(0.2)

    owner_notifications_after = [m for m in main_session_obj.sent_messages if m["chat_id"] == OWNER_TG_ID]
    assert len(owner_notifications_after) == 1, "نباید به‌ازای هر پیامِ مشتریِ جدید، دوباره به فروشگاه‌دار اطلاع بدیم (ضدِاسپم)"

    print("✅ test_zero_balance_blocks_message_and_notifies_owner_once PASSED")


async def test_chat_reply_deducts_exact_token_cost(shop_dp, main_bot) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID + 1, SHOP_BOT_TG_ID + 1, initial_balance_toman=300_000)

    async with session_scope() as session:
        admin_settings = await get_admin_settings(session)
        admin_settings.wallet_cost_per_1k_tokens_toman = 100  # عددِ گرد برای محاسبه‌ی ساده
        await session.flush()

    fake_ai = _FakeAiServiceWithKnownTokens(chat_tokens=1000, classifier_tokens=500, classifier_completes_order=False)
    original_get_ai_service = ai_service.get_ai_service
    ai_service.get_ai_service = lambda api_key, model, base_url=None, fallback_api_key=None, fallback_model=None, fallback_base_url=None: fake_ai

    try:
        shop_bot_instance = Bot(token=f"{SHOP_BOT_TG_ID + 1}:FAKE", session=FakeSession())
        shop_session_obj: FakeSession = shop_bot_instance.session  # type: ignore[assignment]

        await shop_dp.feed_update(shop_bot_instance, make_message_update(1, text="قیمت چنده؟", user_id=CUSTOMER_TG_ID + 1))
        await asyncio.sleep(5.0)  # صبر برای debounce + پاسخ + تسکِ پس‌زمینه‌ی تشخیصِ سفارش

        assert len(shop_session_obj.sent_messages) == 1, "مشتری باید یه پاسخ بگیره"

        owner = await _get_owner(OWNER_TG_ID + 1)
        chat_cost_total = await _sum_transactions(owner.id, WalletTransactionReason.CHAT_MESSAGE)
        # هزینه: round(1000 توکن × ۱۰۰ تومن / ۱۰۰۰) = ۱۰۰ تومن، به‌صورتِ منفی ثبت می‌شه
        assert chat_cost_total == -100, f"انتظارِ کسرِ دقیقاً ۱۰۰ تومن بابتِ پاسخِ چت، ولی {chat_cost_total} بود"

        print("✅ test_chat_reply_deducts_exact_token_cost PASSED")
    finally:
        ai_service.get_ai_service = original_get_ai_service


async def test_classifier_cost_deducted_even_when_no_order_found(shop_dp, main_bot) -> None:
    """رگرسیونِ باگِ فیکس‌شده: قبلاً وقتی کلاسیفایر سفارشی تشخیص نمی‌داد (رایج‌ترین
    حالت)، توکنِ مصرف‌شده‌ش دور ریخته می‌شد و هیچ کسری از کیف‌پول اتفاق نمی‌افتاد."""
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID + 2, SHOP_BOT_TG_ID + 2, initial_balance_toman=300_000)

    async with session_scope() as session:
        admin_settings = await get_admin_settings(session)
        admin_settings.wallet_cost_per_1k_tokens_toman = 100
        await session.flush()

    fake_ai = _FakeAiServiceWithKnownTokens(chat_tokens=1000, classifier_tokens=500, classifier_completes_order=False)
    original_get_ai_service = ai_service.get_ai_service
    ai_service.get_ai_service = lambda api_key, model, base_url=None, fallback_api_key=None, fallback_model=None, fallback_base_url=None: fake_ai

    try:
        shop_bot_instance = Bot(token=f"{SHOP_BOT_TG_ID + 2}:FAKE", session=FakeSession())

        await shop_dp.feed_update(shop_bot_instance, make_message_update(1, text="فقط یه سوال داشتم", user_id=CUSTOMER_TG_ID + 2))
        await asyncio.sleep(5.0)

        owner = await _get_owner(OWNER_TG_ID + 2)

        order_detection_cost_total = await _sum_transactions(owner.id, WalletTransactionReason.ORDER_DETECTION)
        # هزینه: round(۵۰۰ توکن × ۱۰۰ تومن / ۱۰۰۰) = ۵۰ تومن — باید کسر شده باشه، با اینکه
        # هیچ سفارشی تشخیص داده نشده (completed: false)
        assert order_detection_cost_total == -50, (
            f"حتی بدونِ تشخیصِ سفارش، باید بابتِ فراخوانیِ کلاسیفایر ۵۰ تومن کسر بشه، ولی {order_detection_cost_total} بود "
            "(این دقیقاً همون باگیه که تازه فیکس شد)"
        )

        async with session_scope() as session:
            result = await session.execute(select(OrderConsultation).where(OrderConsultation.shop_bot_id == shop_bot_id))
            orders = result.scalars().all()
        assert len(orders) == 0, "چون کلاسیفایر completed:false برگردونده، نباید هیچ سفارش/مشاوره‌ای ساخته بشه"

        print("✅ test_classifier_cost_deducted_even_when_no_order_found PASSED")
    finally:
        ai_service.get_ai_service = original_get_ai_service


async def test_low_balance_warning_sent_when_crossing_threshold(shop_dp, main_bot) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID + 3, SHOP_BOT_TG_ID + 3, initial_balance_toman=0)

    async with session_scope() as session:
        owner = await shop_owner_service.get_by_telegram_id(session, OWNER_TG_ID + 3)
        admin_settings = await get_admin_settings(session)
        admin_settings.wallet_cost_per_1k_tokens_toman = 100
        admin_settings.wallet_low_balance_warning_toman = 1000
        await session.flush()

        # دقیقاً ۱۰۵۰ تومن شارژ می‌کنیم: بعدِ کسرِ ۱۰۰ تومنیِ پاسخِ چت، ۹۵۰ تومن
        # می‌مونه که هم مثبته (نه خالی) و هم زیرِ آستانه‌ی هشدار (۱۰۰۰) — دقیقاً
        # سناریویی که باید هشدارِ «موجودی داره کم می‌شه» رو (نه هشدارِ «تمومه») بسازه.
        await wallet_service.add_charge(session, owner, 1050, reason=WalletTransactionReason.TOPUP)

    fake_ai = _FakeAiServiceWithKnownTokens(chat_tokens=1000, classifier_tokens=1, classifier_completes_order=False)
    original_get_ai_service = ai_service.get_ai_service
    ai_service.get_ai_service = lambda api_key, model, base_url=None, fallback_api_key=None, fallback_model=None, fallback_base_url=None: fake_ai

    try:
        shop_bot_instance = Bot(token=f"{SHOP_BOT_TG_ID + 3}:FAKE", session=FakeSession())
        main_session_obj: FakeSession = main_bot.session  # type: ignore[assignment]
        main_session_obj.sent_messages.clear()

        await shop_dp.feed_update(shop_bot_instance, make_message_update(1, text="سلام", user_id=CUSTOMER_TG_ID + 3))
        await asyncio.sleep(5.0)

        owner_notifications = [m for m in main_session_obj.sent_messages if m["chat_id"] == OWNER_TG_ID + 3]
        assert len(owner_notifications) == 1, f"فروشگاه‌دار باید دقیقاً یه هشدارِ کمبودِ موجودی بگیره، نه {len(owner_notifications)} تا"
        assert "کم می‌شه" in owner_notifications[0]["text"], "این باید هشدارِ «کمبود» باشه، نه اطلاعِ «اتمامِ کامل»"
        assert "تموم شده" not in owner_notifications[0]["text"]

        owner_after = await _get_owner(OWNER_TG_ID + 3)
        # موجودی: ۱۰۵۰ - ۱۰۰ (کسرِ پاسخِ چت) - ۱ (کسرِ کلاسیفایرِ تشخیصِ سفارش؛ حتی با
        # توکنِ خیلی کم، تابعِ estimate_order_detection_cost کفِ حداقل‌ِ ۱ تومن داره) = ۹۴۹
        assert owner_after.wallet_balance_toman == 949, f"موجودی باید ۹۴۹ تومن بمونه، ولی {owner_after.wallet_balance_toman} بود"

        print("✅ test_low_balance_warning_sent_when_crossing_threshold PASSED")
    finally:
        ai_service.get_ai_service = original_get_ai_service


async def test_scheduled_expiry_job_expires_charges_and_sends_reminders(shop_dp, main_bot) -> None:
    """پوششِ ارکستریشنِ واقعیِ کارِ روزانه (wallet_expiry_service)، نه فقط توابعِ
    پایه‌ایِ wallet_service که جدا در test_wallet_service.py تست شدن — برای
    اطمینان از اینکه سیم‌کشیِ Bot/متن/فراخوانی واقعاً درست کار می‌کنه."""
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID + 4, SHOP_BOT_TG_ID + 4, initial_balance_toman=0)
    await seed_usable_shop(OWNER_TG_ID + 5, SHOP_BOT_TG_ID + 5, initial_balance_toman=0)

    async with session_scope() as session:
        owner_expiring = await shop_owner_service.get_by_telegram_id(session, OWNER_TG_ID + 4)
        owner_reminder = await shop_owner_service.get_by_telegram_id(session, OWNER_TG_ID + 5)

        # فروشگاه‌دارِ اول: یه بسته‌ی از‌قبل‌منقضی‌شده داره (باید واقعاً expire بشه)
        expired_charge = await wallet_service.add_charge(session, owner_expiring, 40_000, reason=WalletTransactionReason.TOPUP)
        expired_charge.expires_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=2)

        # فروشگاه‌دارِ دوم: یه بسته داره که ۲۰ ساعتِ دیگه منقضی می‌شه (باید یادآوریِ «۱ روز مونده» بگیره)
        reminder_charge = await wallet_service.add_charge(session, owner_reminder, 70_000, reason=WalletTransactionReason.TOPUP)
        reminder_charge.expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=20)
        await session.flush()

    main_session_obj: FakeSession = main_bot.session  # type: ignore[assignment]
    main_session_obj.sent_messages.clear()

    async with session_scope() as session:
        await wallet_expiry_service.process_wallet_expiry_and_reminders(session, main_bot)

    async with session_scope() as session:
        owner_expiring_after = await shop_owner_service.get_by_telegram_id(session, OWNER_TG_ID + 4)
        assert owner_expiring_after.wallet_balance_toman == 0, "بسته‌ی منقضی‌شده باید واقعاً از موجودی کم بشه"

        owner_reminder_after = await shop_owner_service.get_by_telegram_id(session, OWNER_TG_ID + 5)
        assert owner_reminder_after.wallet_balance_toman == 70_000, "بسته‌ی هنوز‌منقضی‌نشده نباید دست بخوره"

    reminder_notifications = [m for m in main_session_obj.sent_messages if m["chat_id"] == OWNER_TG_ID + 5]
    assert len(reminder_notifications) == 1, f"باید دقیقاً یه یادآوریِ انقضا بگیره، نه {len(reminder_notifications)} تا"
    assert "منقضی می‌شه" in reminder_notifications[0]["text"]

    expired_owner_notifications = [m for m in main_session_obj.sent_messages if m["chat_id"] == OWNER_TG_ID + 4]
    assert len(expired_owner_notifications) == 0, "برای بسته‌ای که همین الان expire شده (نه در آستانه‌ی انقضا)، نباید یادآوری بره"

    print("✅ test_scheduled_expiry_job_expires_charges_and_sends_reminders PASSED")


async def test_cost_calculator_shows_monthly_estimate(main_dp, main_bot) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID + 6, SHOP_BOT_TG_ID + 6, initial_balance_toman=0)

    async with session_scope() as session:
        admin_settings = await get_admin_settings(session)
        admin_settings.wallet_cost_per_1k_tokens_toman = 100
        await session.flush()

    main_session_obj: FakeSession = main_bot.session  # type: ignore[assignment]
    main_session_obj.sent_messages.clear()

    await main_dp.feed_update(main_bot, make_callback_update(1, data="cost_calc_start", user_id=OWNER_TG_ID + 6))
    await main_dp.feed_update(main_bot, make_callback_update(2, data="cost_calc_volume:medium", user_id=OWNER_TG_ID + 6))

    # حجمِ «medium» = ۶۰ پیام در روز؛ هزینه‌ی هر پیام با فرضِ ۸۰۰ توکنِ پیش‌فرض و
    # نرخِ ۱۰۰ تومن به‌ازای هر ۱۰۰۰ توکن: round(800*100/1000) = ۸۰ تومن
    # هزینه‌ی ماهانه: ۶۰ × ۳۰ × ۸۰ = ۱۴۴٬۰۰۰ تومن
    last_message = main_session_obj.sent_messages[-1]
    assert "144,000" in last_message["text"], f"باید هزینه‌ی تقریبیِ ۱۴۴٬۰۰۰ تومنی نشون بده: {last_message['text']}"

    print("✅ test_cost_calculator_shows_monthly_estimate PASSED")


async def main() -> None:
    main_dp, shop_dp, _bot_manager, main_bot = build_test_dispatchers()
    await test_zero_balance_blocks_message_and_notifies_owner_once(shop_dp, main_bot)
    await test_chat_reply_deducts_exact_token_cost(shop_dp, main_bot)
    await test_classifier_cost_deducted_even_when_no_order_found(shop_dp, main_bot)
    await test_low_balance_warning_sent_when_crossing_threshold(shop_dp, main_bot)
    await test_scheduled_expiry_job_expires_charges_and_sends_reminders(shop_dp, main_bot)
    await test_cost_calculator_shows_monthly_estimate(main_dp, main_bot)


if __name__ == "__main__":
    asyncio.run(main())
