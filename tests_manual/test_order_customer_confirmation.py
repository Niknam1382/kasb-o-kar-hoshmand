"""
تست: بازطراحیِ سفارش‌گیری — تاییدِ صریحِ مشتری، حالتِ «مطمئن نیستم»، و فیلدهای
ساختاریافته‌ی تلفن/آدرس.

قبل از این بازطراحی، تشخیصِ سفارش کاملاً پشتِ‌صحنه بود: به‌محضِ اینکه کلاسیفایر
«completed» تشخیص می‌داد، بدونِ هیچ تاییدی از خودِ مشتری، سفارش مستقیم ساخته و
به فروشگاه‌دار اطلاع داده می‌شد؛ تلفن/آدرس هم فقط متنِ آزادِ چسبیده به خلاصه
بودن. این فایل رفتارِ جدید رو پوشش می‌ده:

۱. «completed» → اول یه پیامِ تاییدِ صریح (با فیلدهای ساختاریافته‌ی تلفن/آدرس)
   به خودِ مشتری می‌ره؛ فروشگاه‌دار هنوز هیچی نمی‌بینه.
۲. مشتری روی «تایید» می‌زنه → سفارش PENDING می‌شه و الان فروشگاه‌دار (با همون
   فیلدهای ساختاریافته، جدا از خلاصه) خبردار می‌شه.
۳. مشتری روی «اشتباهه» می‌زنه → سفارش لغو می‌شه؛ فروشگاه‌دار هیچ‌وقت خبردار نمی‌شه.
۴. کلاسیفایرِ «unsure» → هیچ سفارشی ساخته نمی‌شه؛ فقط سوالِ روشن‌کننده مستقیم به
   مشتری می‌ره.
۵. یه مشتری نمی‌تونه با حدسِ order_id، سفارشِ کاندیدِ یه مشتریِ دیگه رو تایید/لغو کنه.
۶. کاندیدی که مشتری هیچ‌وقت جواب نده، بعد از مهلتِ تنظیم‌شده خودکار لغو می‌شه.

اجرا: python3 tests_manual/test_order_customer_confirmation.py
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

from app.database.models import OrderConsultation, OrderStatus, OrderType  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import ai_service, customer_service, order_expiry_service, order_service  # noqa: E402
from app.services.ai_service import AiCallResult  # noqa: E402
from app.services.order_detection_service import _CLASSIFIER_USER_PROMPT  # noqa: E402

OWNER_TG_ID = 999601
SHOP_BOT_TG_ID = 999602
CUSTOMER_TG_ID = 999603
OTHER_CUSTOMER_TG_ID = 999604

_COMPLETED_WITH_CONTACT_INFO = (
    '{"status": "completed", "type": "order", "summary": "سفارشِ ۱ عدد شال کشمیری", '
    '"estimated_value_toman": 450000, "product_id": null, "quantity": 1, '
    '"customer_phone": "09121234567", "customer_address": "تهران، خیابانِ ولیعصر، پلاکِ ۱۰"}'
)
_UNSURE_JSON = '{"status": "unsure", "clarifying_question": "کدوم رنگ رو مدِنظرتونه؟"}'
_NONE_JSON = '{"status": "none"}'


class _FakeClassifierAi:
    """کلاسیفایر رو با یه متنِ ثابتِ JSON پاسخ می‌ده؛ برای پیامِ چتِ عادی هم یه
    جوابِ کوتاهِ ثابت برمی‌گردونه."""

    def __init__(self, classifier_text: str) -> None:
        self.classifier_text = classifier_text

    async def get_reply(self, system_prompt: str, history: list[dict[str, str]], user_message: str) -> AiCallResult:
        if user_message == _CLASSIFIER_USER_PROMPT:
            return AiCallResult(text=self.classifier_text, total_tokens=77)
        return AiCallResult(text="باشه، الان بررسی می‌کنم.", total_tokens=42)

    async def analyze_image(self, prompt: str, image_bytes: bytes, mime_type: str = "image/jpeg") -> AiCallResult:
        return AiCallResult(text="")

    async def transcribe_audio(self, audio_bytes: bytes, filename: str = "voice.ogg") -> str:
        return ""


async def _send_customer_message(shop_dp, fake_ai, text: str, user_id: int = CUSTOMER_TG_ID) -> Bot:
    original_get_ai_service = ai_service.get_ai_service
    ai_service.get_ai_service = (
        lambda api_key, model, base_url=None, fallback_api_key=None, fallback_model=None, fallback_base_url=None: fake_ai
    )
    try:
        shop_bot_instance = Bot(token=f"{SHOP_BOT_TG_ID}:FAKE", session=FakeSession())
        await shop_dp.feed_update(shop_bot_instance, make_message_update(1, user_id=user_id, text=text))
        await asyncio.sleep(4.5)  # صبر برای اتمامِ debounce (۳ ثانیه) + پردازش
        return shop_bot_instance
    finally:
        ai_service.get_ai_service = original_get_ai_service


async def _get_single_order(shop_bot_id: int) -> OrderConsultation:
    async with session_scope() as session:
        result = await session.execute(select(OrderConsultation).where(OrderConsultation.shop_bot_id == shop_bot_id))
        return result.scalar_one()


async def test_completed_detection_asks_customer_before_notifying_owner(shop_dp, main_bot) -> None:
    await reset_database()
    main_bot.session.sent_messages.clear()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)

    shop_bot_instance = await _send_customer_message(shop_dp, _FakeClassifierAi(_COMPLETED_WITH_CONTACT_INFO), "یه شال کشمیری می‌خوام")

    order = await _get_single_order(shop_bot_id)
    assert order.status == OrderStatus.AWAITING_CUSTOMER_CONFIRMATION, "تازه‌تشخیص‌داده‌شده باید منتظرِ تاییدِ مشتری بمونه"
    assert order.customer_phone == "09121234567", "تلفن باید به‌عنوانِ فیلدِ ساختاریافته ذخیره بشه، نه چسبیده به خلاصه"
    assert order.customer_address == "تهران، خیابانِ ولیعصر، پلاکِ ۱۰"
    assert "09121234567" not in (order.summary or ""), "تلفن نباید داخلِ متنِ خلاصه هم تکرار بشه"

    shop_session: FakeSession = shop_bot_instance.session  # type: ignore[assignment]
    assert len(shop_session.sent_messages) == 2, "پیامِ چتِ عادی + پیامِ تاییدِ سفارش، هر دو باید برایِ مشتری فرستاده بشن"
    confirmation_text = shop_session.sent_messages[1]["text"]
    assert "09121234567" in confirmation_text, "شماره تلفن باید توی پیامِ تاییدی که مشتری می‌بینه نشون داده بشه"
    assert "ولیعصر" in confirmation_text
    assert shop_session.sent_messages[1]["reply_markup"] is not None, "پیامِ تاییدی باید دکمه‌ی تایید/رد داشته باشه"

    main_session: FakeSession = main_bot.session  # type: ignore[assignment]
    assert len(main_session.sent_messages) == 0, "قبل از تاییدِ خودِ مشتری، فروشگاه‌دار نباید اصلاً چیزی ببینه"

    print("✅ test_completed_detection_asks_customer_before_notifying_owner PASSED")


async def test_customer_confirm_moves_to_pending_and_notifies_owner(shop_dp, main_bot) -> None:
    await reset_database()
    main_bot.session.sent_messages.clear()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    shop_bot_instance = await _send_customer_message(shop_dp, _FakeClassifierAi(_COMPLETED_WITH_CONTACT_INFO), "یه شال کشمیری می‌خوام")
    order = await _get_single_order(shop_bot_id)

    await shop_dp.feed_update(shop_bot_instance, make_callback_update(2, data=f"cust_confirm_order:{order.id}", user_id=CUSTOMER_TG_ID))

    async with session_scope() as session:
        refreshed = await order_service.get_by_id(session, order.id)
        assert refreshed.status == OrderStatus.PENDING, f"بعدِ تاییدِ مشتری باید PENDING بشه، شد {refreshed.status}"

    shop_session: FakeSession = shop_bot_instance.session  # type: ignore[assignment]
    assert len(shop_session.answered_callbacks) == 1, "باید به کال‌بکِ مشتری جواب داده بشه (لودینگِ دکمه متوقف بشه)"

    main_session: FakeSession = main_bot.session  # type: ignore[assignment]
    assert len(main_session.sent_messages) == 1, "دقیقاً بعدِ تاییدِ مشتری، فروشگاه‌دار باید یه اطلاع‌رسانی بگیره"
    owner_text = main_session.sent_messages[0]["text"]
    assert "09121234567" in owner_text, "تلفن باید جدا از خلاصه، توی اطلاع‌رسانیِ فروشگاه‌دار هم دیده بشه"
    assert "ولیعصر" in owner_text

    print("✅ test_customer_confirm_moves_to_pending_and_notifies_owner PASSED")


async def test_customer_cancel_never_notifies_owner(shop_dp, main_bot) -> None:
    await reset_database()
    main_bot.session.sent_messages.clear()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    shop_bot_instance = await _send_customer_message(shop_dp, _FakeClassifierAi(_COMPLETED_WITH_CONTACT_INFO), "یه شال کشمیری می‌خوام")
    order = await _get_single_order(shop_bot_id)

    await shop_dp.feed_update(shop_bot_instance, make_callback_update(2, data=f"cust_cancel_order:{order.id}", user_id=CUSTOMER_TG_ID))

    async with session_scope() as session:
        refreshed = await order_service.get_by_id(session, order.id)
        assert refreshed.status == OrderStatus.CANCELLED, f"بعدِ لغوِ مشتری باید CANCELLED بشه، شد {refreshed.status}"

    main_session: FakeSession = main_bot.session  # type: ignore[assignment]
    assert len(main_session.sent_messages) == 0, "وقتی مشتری می‌گه اشتباهه، فروشگاه‌دار نباید هیچ‌وقت خبردار بشه"

    print("✅ test_customer_cancel_never_notifies_owner PASSED")


async def test_unsure_asks_clarifying_question_without_creating_order(shop_dp, main_bot) -> None:
    await reset_database()
    main_bot.session.sent_messages.clear()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)

    shop_bot_instance = await _send_customer_message(shop_dp, _FakeClassifierAi(_UNSURE_JSON), "یه چیزی می‌خوام ولی مطمئن نیستم چی")

    async with session_scope() as session:
        result = await session.execute(select(OrderConsultation).where(OrderConsultation.shop_bot_id == shop_bot_id))
        assert result.scalar_one_or_none() is None, "توی حالتِ unsure نباید هیچ سفارشی ساخته بشه"

    shop_session: FakeSession = shop_bot_instance.session  # type: ignore[assignment]
    assert len(shop_session.sent_messages) == 2, "پیامِ چتِ عادی + سوالِ روشن‌کننده، هر دو باید برایِ مشتری فرستاده بشه"
    assert shop_session.sent_messages[1]["text"] == "کدوم رنگ رو مدِنظرتونه؟"
    assert shop_session.sent_messages[1]["reply_markup"] is None, "سوالِ روشن‌کننده دکمه‌ای نداره، فقط یه سوالِ معمولیه"

    main_session: FakeSession = main_bot.session  # type: ignore[assignment]
    assert len(main_session.sent_messages) == 0, "توی حالتِ unsure فروشگاه‌دار اصلاً نباید خبردار بشه"

    print("✅ test_unsure_asks_clarifying_question_without_creating_order PASSED")


async def test_cross_customer_confirm_denied(shop_dp, main_bot) -> None:
    await reset_database()
    main_bot.session.sent_messages.clear()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    shop_bot_instance = await _send_customer_message(shop_dp, _FakeClassifierAi(_COMPLETED_WITH_CONTACT_INFO), "یه شال کشمیری می‌خوام")
    order = await _get_single_order(shop_bot_id)

    async with session_scope() as session:
        await customer_service.get_or_create_customer(session, shop_bot_id, OTHER_CUSTOMER_TG_ID, "مشتریِ دیگه", None)

    # «مشتریِ دیگه» (که خودش مشتریِ واقعیِ همین فروشگاهه، ولی صاحبِ این سفارشِ
    # کاندید نیست) سعی می‌کنه با حدسِ order_id، سفارشِ نفرِ اول رو تایید کنه.
    await shop_dp.feed_update(
        shop_bot_instance, make_callback_update(2, data=f"cust_confirm_order:{order.id}", user_id=OTHER_CUSTOMER_TG_ID)
    )

    async with session_scope() as session:
        refreshed = await order_service.get_by_id(session, order.id)
        assert refreshed.status == OrderStatus.AWAITING_CUSTOMER_CONFIRMATION, "سفارشِ نفرِ اول نباید با تاییدِ نفرِ دوم تغییر کنه"

    shop_session: FakeSession = shop_bot_instance.session  # type: ignore[assignment]
    assert len(shop_session.answered_callbacks) == 1
    assert shop_session.answered_callbacks[0]["show_alert"] is True, "باید یه هشدارِ واضح به مشتریِ دوم نشون داده بشه"

    main_session: FakeSession = main_bot.session  # type: ignore[assignment]
    assert len(main_session.sent_messages) == 0

    print("✅ test_cross_customer_confirm_denied PASSED")


async def test_none_status_does_nothing(shop_dp, main_bot) -> None:
    await reset_database()
    main_bot.session.sent_messages.clear()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)

    shop_bot_instance = await _send_customer_message(shop_dp, _FakeClassifierAi(_NONE_JSON), "سلام، چطورید؟")

    async with session_scope() as session:
        result = await session.execute(select(OrderConsultation).where(OrderConsultation.shop_bot_id == shop_bot_id))
        assert result.scalar_one_or_none() is None, "توی وضعیتِ none نباید هیچ سفارشی ساخته بشه"

    shop_session: FakeSession = shop_bot_instance.session  # type: ignore[assignment]
    assert len(shop_session.sent_messages) == 1, "فقط پاسخِ چتِ عادی؛ برایِ none نباید پیامِ اضافه‌ای فرستاده بشه"

    main_session: FakeSession = main_bot.session  # type: ignore[assignment]
    assert len(main_session.sent_messages) == 0

    print("✅ test_none_status_does_nothing PASSED")


async def test_stale_unconfirmed_candidate_expires_automatically(main_bot) -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)

    async with session_scope() as session:
        customer = await customer_service.get_or_create_customer(session, shop_bot_id, CUSTOMER_TG_ID, "مشتری", None)
        order = await order_service.create_order_awaiting_confirmation(
            session, shop_bot_id, customer.id, OrderType.ORDER, "سفارشِ آزمایشیِ قدیمی", None, None, None, None, None
        )
        order_id = order.id
        # وانمود می‌کنیم این کاندید مالِ خیلی‌وقت‌پیشه (فراتر از مهلتِ پیش‌فرضِ ۶۰ دقیقه‌ای).
        order.created_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=120)
        await session.flush()

    async with session_scope() as session:
        await order_expiry_service.process_order_expiry(session, main_bot)

    async with session_scope() as session:
        refreshed = await order_service.get_by_id(session, order_id)
        assert refreshed.status == OrderStatus.CANCELLED, f"کاندیدِ خیلی‌قدیمی باید خودکار لغو بشه، وضعیتش {refreshed.status} موند"

    print("✅ test_stale_unconfirmed_candidate_expires_automatically PASSED")


async def main() -> None:
    _main_dp, shop_dp, _bot_manager, main_bot = build_test_dispatchers()
    await test_completed_detection_asks_customer_before_notifying_owner(shop_dp, main_bot)
    await test_customer_confirm_moves_to_pending_and_notifies_owner(shop_dp, main_bot)
    await test_customer_cancel_never_notifies_owner(shop_dp, main_bot)
    await test_unsure_asks_clarifying_question_without_creating_order(shop_dp, main_bot)
    await test_cross_customer_confirm_denied(shop_dp, main_bot)
    await test_none_status_does_nothing(shop_dp, main_bot)
    await test_stale_unconfirmed_candidate_expires_automatically(main_bot)


if __name__ == "__main__":
    asyncio.run(main())
