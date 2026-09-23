"""
تست: باگِ بزرگِ #8 / #14 — کسرِ ناپایدارِ موجودی بعد از تاییدِ سفارش.

ریشه‌ی باگ: کلاسیفایرِ تشخیصِ سفارش قبلاً اسمِ محصول رو به‌صورتِ متنِ آزاد از
هوش مصنوعی می‌گرفت و با تطبیقِ فازی (fuzzy match) به یه محصولِ واقعی وصلش
می‌کرد؛ وقتی عبارتِ هوش مصنوعی دقیقاً با اسمِ محصول یکی نبود (که اغلب همینه)،
تطبیق بی‌صدا fail می‌شد، product_id خالی می‌موند، و کسرِ موجودی رد می‌شد —
ولی خودِ هوش مصنوعی (توی خلاصه/حافظه‌ش) فکر می‌کرد سفارش کامل با محصولِ درست
ثبت شده. این دقیقاً همون چیزیه که کاربر توصیف کرد: «توی پنل بعضی‌وقتا کم
می‌شه بعضی‌وقتا نه، ولی توی حافظه‌ی مدل همیشه کم می‌شه».

فیکس: کلاسیفایر حالا مستقیم «product_id» رو (نه اسم) از یه لیستِ صریحِ
«شناسه | نام» که توی پرامپت تزریق می‌شه برمی‌گردونه؛ دیگه نیازی به حدسِ
تطبیقِ اسم نیست. این تست سه سناریو رو پوشش می‌ده:
۱. شناسه‌ی معتبر → سفارش با product_id درست ساخته و بعد از تایید، موجودی
   دقیقاً به‌اندازه‌ی تعداد کم می‌شه.
۲. شناسه‌ی ساختگی/توهمی (که متعلق به این فروشگاه نیست) → بی‌خطر به None
   برمی‌گرده، بدونِ کرش.
۳. سفارشی که اصلاً محصولِ خاصی رو مشخص نکرده → product_id همچنان None.

اجرا: python3 tests_manual/test_order_product_id_matching.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402

from harness import FakeSession, build_test_dispatchers, make_message_update, reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.database.session import session_scope  # noqa: E402
from app.services import ai_service, order_service, product_service  # noqa: E402
from app.services.ai_service import AiCallResult  # noqa: E402
from app.services.order_detection_service import _CLASSIFIER_USER_PROMPT  # noqa: E402

OWNER_TG_ID = 999501
SHOP_BOT_TG_ID = 999502
CUSTOMER_TG_ID = 999503


class _FakeAiServiceReturningProductId:
    """مثلِ یه هوش مصنوعیِ واقعی که دقیقاً طبقِ فرمتِ جدید (product_id، نه اسم) جواب می‌ده."""

    def __init__(self, product_id_to_return) -> None:
        self.product_id_to_return = product_id_to_return

    async def get_reply(self, system_prompt: str, history: list[dict[str, str]], user_message: str) -> AiCallResult:
        if user_message != _CLASSIFIER_USER_PROMPT:
            return AiCallResult(text="باشه، الان براتون ثبت می‌کنم.", total_tokens=42)
        text = (
            '{"completed": true, "type": "order", "summary": "سفارشِ مشتری", '
            f'"estimated_value_toman": 250000, "product_id": {self.product_id_to_return}, '
            '"quantity": 2, "customer_phone": null, "customer_address": null}'
        )
        return AiCallResult(text=text, total_tokens=88)

    async def analyze_image(self, prompt: str, image_bytes: bytes, mime_type: str = "image/jpeg") -> AiCallResult:
        return AiCallResult(text="")

    async def transcribe_audio(self, audio_bytes: bytes, filename: str = "voice.ogg") -> str:
        return ""


async def _seed_shop_with_product() -> tuple[int, int]:
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    async with session_scope() as session:
        product = await product_service.create_product(session, shop_bot_id, "کیف چرم دست‌دوز مشکی", "توضیحات", 125_000, None, stock_quantity=10)
        product_id = product.id
    return shop_bot_id, product_id


async def _run_order_flow(shop_dp, fake_ai) -> None:
    original_get_ai_service = ai_service.get_ai_service
    ai_service.get_ai_service = lambda api_key, model, base_url=None, fallback_api_key=None, fallback_model=None, fallback_base_url=None: fake_ai
    try:
        shop_bot_instance = Bot(token=f"{SHOP_BOT_TG_ID}:FAKE", session=FakeSession())
        await shop_dp.feed_update(
            shop_bot_instance, make_message_update(1, user_id=CUSTOMER_TG_ID, text="۲ تا کیف چرمی مشکی می‌خوام، لطفاً ثبت کنید")
        )
        await asyncio.sleep(4.5)  # صبر برای اتمامِ debounce (۳ ثانیه) + پردازش
    finally:
        ai_service.get_ai_service = original_get_ai_service


async def test_valid_product_id_decrements_stock_correctly(shop_dp) -> None:
    await reset_database()
    shop_bot_id, product_id = await _seed_shop_with_product()

    await _run_order_flow(shop_dp, _FakeAiServiceReturningProductId(product_id))

    async with session_scope() as session:
        from sqlalchemy import select

        from app.database.models import OrderConsultation

        result = await session.execute(select(OrderConsultation).where(OrderConsultation.shop_bot_id == shop_bot_id))
        order = result.scalar_one()
        assert order.product_id == product_id, f"انتظار داشتیم product_id دقیقاً {product_id} باشه، ولی {order.product_id} بود"
        assert order.quantity == 2, f"انتظار داشتیم quantity برابرِ ۲ باشه، ولی {order.quantity} بود"

        confirmed = await order_service.confirm_order(session, order)
        assert confirmed is True

        product = await product_service.get_by_id(session, product_id)
        assert product.stock_quantity == 8, f"موجودی باید از ۱۰ به ۸ برسه (۲ تا کم بشه)، ولی {product.stock_quantity} شد"

    print("✅ test_valid_product_id_decrements_stock_correctly PASSED")


async def test_hallucinated_product_id_falls_back_safely(shop_dp) -> None:
    await reset_database()
    shop_bot_id, real_product_id = await _seed_shop_with_product()
    fake_hallucinated_id = real_product_id + 9999  # قطعاً متعلق به این فروشگاه نیست

    await _run_order_flow(shop_dp, _FakeAiServiceReturningProductId(fake_hallucinated_id))

    async with session_scope() as session:
        from sqlalchemy import select

        from app.database.models import OrderConsultation

        result = await session.execute(select(OrderConsultation).where(OrderConsultation.shop_bot_id == shop_bot_id))
        order = result.scalar_one()
        assert order.product_id is None, "شناسه‌ی ساختگی/نامعتبر نباید به‌عنوانِ product_id پذیرفته بشه"
        assert order.quantity is None, "وقتی product_id نامعتبره، quantity هم نباید ست بشه"

        product = await product_service.get_by_id(session, real_product_id)
        assert product.stock_quantity == 10, "موجودیِ محصولِ واقعی نباید دست‌نخورده نمونه (نباید تغییر کنه)"

    print("✅ test_hallucinated_product_id_falls_back_safely PASSED")


async def test_null_product_id_stays_none(shop_dp) -> None:
    await reset_database()
    shop_bot_id, _ = await _seed_shop_with_product()

    await _run_order_flow(shop_dp, _FakeAiServiceReturningProductId("null"))

    async with session_scope() as session:
        from sqlalchemy import select

        from app.database.models import OrderConsultation

        result = await session.execute(select(OrderConsultation).where(OrderConsultation.shop_bot_id == shop_bot_id))
        order = result.scalar_one()
        assert order.product_id is None
        print("✅ test_null_product_id_stays_none PASSED")


async def main() -> None:
    _main_dp, shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    await test_valid_product_id_decrements_stock_correctly(shop_dp)
    await test_hallucinated_product_id_falls_back_safely(shop_dp)
    await test_null_product_id_stays_none(shop_dp)


if __name__ == "__main__":
    asyncio.run(main())
