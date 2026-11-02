"""
تست: ویرایشِ سبدِ خرید با هوش مصنوعی (فازِ ۳، زیربخشِ ۴).

مشتری تویِ همون چتِ آزاد می‌تونه بگه «دوتا از برنج کم کن» و سبدش واقعاً عوض بشه.
این فایل اینا رو پوشش می‌ده:

۱. قوانینِ اعتبارسنجیِ خروجیِ AI (بدونِ دیتابیس): شناسه‌ی ساختگی، تعدادِ نامعقول، ...
۲. یه دستورِ سبد، کاملاً همون‌جا جواب داده می‌شه: سبد عوض می‌شه، چتِ عادی و تشخیصِ
   سفارش اجرا *نمی‌شن*، هزینه‌ی کلاسیفایر (CART_EDIT) از کیف‌پول کسر می‌شه.
۳. «هیچ‌چی» → مسیرِ چتِ عادی دقیقاً مثلِ قبل (چت + تشخیصِ سفارشِ پس‌زمینه).
۴. مشتری‌ای که نه سبد داره نه از «سبد» حرف می‌زنه: کلاسیفایر اصلاً صدا زده نمی‌شه
   (هزینه‌ی صفر، مسیرِ قبلی دست‌نخورده).
۵. «unsure»: سوالِ روشن‌کننده، بدونِ تغییرِ سبد، و سوال توی تاریخچه می‌مونه.
۶. هالوسینیشن: شناسه‌ی ساختگی یا مالِ فروشگاهِ دیگه هیچ‌وقت به سبد راه پیدا نمی‌کنه.
۷. سقفِ موجودی رو صادقانه گزارش می‌کنه (نه موفقیتِ دروغ).
۸. خالی‌کردنِ کلِ سبد فقط با تاییدِ دکمه‌ای؛ دکمه‌ی قدیمی روی سبدِ عوض‌شده کار نمی‌کنه.
۹. شکستِ AI → بدونِ هزینه، و پیام به چتِ عادی می‌ره.
۱۰. پیش‌نمایشِ چک‌اوت بعد از ویرایشِ سبد کهنه می‌شه و ثبت نمی‌شه.
۱۱. دو دستورِ همزمانِ یه مشتری به ترتیب اجرا می‌شن (قفلِ per-customer).
۱۲. مسیرِ کاملِ dispatcher (debounce → pipeline → ویرایشِ سبد).

نکته‌ی هارنس: EditMessageText توی sent_messages ثبت نمی‌شه؛ برایِ چیزهایی که با
edit_text می‌رن وضعیتِ دیتابیس رو چک می‌کنیم. برایِ سرعت، بیشترِ تست‌ها مستقیم
_generate_and_send_reply رو صدا می‌زنن (بدونِ انتظارِ debounce)؛ فقط یه تست از
مسیرِ کاملِ dispatcher می‌ره.

اجرا: python3 tests_manual/test_cart_ai_editing.py
"""
from __future__ import annotations

import asyncio
import dataclasses
import json
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402
from sqlalchemy import select  # noqa: E402

from harness import FakeSession, build_test_dispatchers, make_callback_update, make_message_update, reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402
from checkout_helpers import run_checkout  # noqa: E402

from app.bots.shop_bot import texts as shop_texts  # noqa: E402
from app.bots.shop_bot.handlers import customer as customer_handlers  # noqa: E402
from app.database.models import (  # noqa: E402
    CartItem,
    ConversationMessage,
    Customer,
    OrderConsultation,
    Product,
    WalletTransaction,
    WalletTransactionReason,
)
from app.database.session import session_scope  # noqa: E402
from app.services import ai_service, cart_edit_service, cart_service, product_service, wallet_service  # noqa: E402
from app.services.admin_settings_service import get_admin_settings  # noqa: E402
from app.services.ai_service import AiCallResult  # noqa: E402
from app.services.order_detection_service import _CLASSIFIER_USER_PROMPT  # noqa: E402

OWNER_TG_ID = 999701
SHOP_BOT_TG_ID = 999702
CUSTOMER_TG_ID = 999703

CART_TOKENS = 500  # توکنِ مصرفیِ جعلیِ هر فراخوانیِ کلاسیفایرِ سبد


# =============================================================================
# AIِ جعلی: سه نوع فراخوانی رو از هم تشخیص می‌ده (کلاسیفایرِ سبد / کلاسیفایرِ سفارش / چتِ عادی)
# =============================================================================
class _FakeAi:
    def __init__(
        self,
        cart_json=None,
        order_json: str = '{"status": "none"}',
        cart_raises: bool = False,
        cart_delay: float = 0.0,
    ) -> None:
        # cart_json یا یه رشته‌ی JSON ـه، یا یه تابع (system_prompt, user_message) -> رشته
        self.cart_json = cart_json if cart_json is not None else '{"status": "none"}'
        self.order_json = order_json
        self.cart_raises = cart_raises
        self.cart_delay = cart_delay
        self.cart_calls: list[tuple[str, list[dict[str, str]], str]] = []
        self.order_calls = 0
        self.chat_calls = 0

    async def get_reply(self, system_prompt: str, history: list[dict[str, str]], user_message: str) -> AiCallResult:
        if cart_edit_service.CLASSIFIER_USER_PROMPT in user_message:
            self.cart_calls.append((system_prompt, list(history), user_message))
            if self.cart_delay:
                await asyncio.sleep(self.cart_delay)
            if self.cart_raises:
                raise ai_service.AiServiceError("شکستِ شبیه‌سازی‌شده")
            payload = self.cart_json(system_prompt, user_message) if callable(self.cart_json) else self.cart_json
            return AiCallResult(text=payload, total_tokens=CART_TOKENS)
        if user_message == _CLASSIFIER_USER_PROMPT:
            self.order_calls += 1
            return AiCallResult(text=self.order_json, total_tokens=77)
        self.chat_calls += 1
        return AiCallResult(text="CHAT_REPLY", total_tokens=42)

    async def analyze_image(self, prompt: str, image_bytes: bytes, mime_type: str = "image/jpeg") -> AiCallResult:
        return AiCallResult(text="")

    async def transcribe_audio(self, audio_bytes: bytes, filename: str = "voice.ogg") -> str:
        return ""


_current_ai: _FakeAi | None = None


def _set_ai(ai: _FakeAi) -> _FakeAi:
    global _current_ai
    _current_ai = ai
    return ai


def _patched_get_ai_service(*args, **kwargs):
    assert _current_ai is not None, "تست فراموش کرده AIِ جعلی رو با _set_ai تنظیم کنه"
    return _current_ai


def _edit_json(*operations: dict) -> str:
    return json.dumps({"status": "edit", "operations": list(operations)}, ensure_ascii=False)


_update_counter = 1000


def _uid() -> int:
    global _update_counter
    _update_counter += 1
    return _update_counter


# =============================================================================
# کمک‌کننده‌ها
# =============================================================================
@dataclasses.dataclass
class _Shop:
    shop_bot_id: int
    rice: int  # برنج: موجودیِ ۵ تایی
    tea: int  # چای: موجودیِ نامحدود
    cake: int  # کیک: موجودی صفر


async def _customer_id(session, shop_bot_id: int) -> int:
    result = await session.execute(
        select(Customer).where(Customer.shop_bot_id == shop_bot_id, Customer.telegram_id == CUSTOMER_TG_ID)
    )
    customer = result.scalar_one_or_none()
    if customer is None:
        customer = Customer(shop_bot_id=shop_bot_id, telegram_id=CUSTOMER_TG_ID, first_name="مشتریِ تستی")
        session.add(customer)
        await session.flush()
    return customer.id


async def _seed_shop(cart: dict[str, int] | None = None) -> _Shop:
    """فروشگاهِ تازه با سه محصول + (اختیاری) یه سبدِ اولیه برایِ مشتریِ تستی.
    مشتری همیشه از قبل ساخته می‌شه تا اجرایِ همزمانِ چند پردازش روی ساختنِ مشتری رقابت نکنن."""
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    async with session_scope() as session:
        rice = await product_service.create_product(session, shop_bot_id, "برنج", None, 200_000, None, stock_quantity=5)
        tea = await product_service.create_product(session, shop_bot_id, "چای", None, 50_000, None, stock_quantity=None)
        cake = await product_service.create_product(session, shop_bot_id, "کیک", None, 120_000, None, stock_quantity=1)
        cake.stock_quantity = 0
        await session.flush()

        customer_id = await _customer_id(session, shop_bot_id)
        if cart:
            by_name = {"برنج": rice, "چای": tea}
            cart_row = await cart_service.get_or_create_cart(session, shop_bot_id, customer_id)
            for name, quantity in cart.items():
                await cart_service.add_item(session, cart_row, by_name[name], quantity)
        return _Shop(shop_bot_id, rice.id, tea.id, cake.id)


async def _put_in_cart(shop_bot_id: int, product_id: int, quantity: int) -> None:
    async with session_scope() as session:
        customer_id = await _customer_id(session, shop_bot_id)
        cart = await cart_service.get_or_create_cart(session, shop_bot_id, customer_id)
        product = await product_service.get_by_id(session, product_id)
        await cart_service.add_item(session, cart, product, quantity)


async def _cart_contents(shop_bot_id: int) -> dict[str, int]:
    async with session_scope() as session:
        customer_id = await _customer_id(session, shop_bot_id)
        cart = await cart_service.get_cart(session, shop_bot_id, customer_id)
        if cart is None:
            return {}
        items = await cart_service.get_items_with_products(session, cart.id)
        return {product.name: item.quantity for item, product in items}


async def _reason_total(reason: WalletTransactionReason) -> int:
    async with session_scope() as session:
        result = await session.execute(select(WalletTransaction.amount_toman).where(WalletTransaction.reason == reason))
        return sum(result.scalars().all())


async def _expected_cart_edit_cost(tokens: int = CART_TOKENS) -> int:
    async with session_scope() as session:
        admin_settings = await get_admin_settings(session)
        return wallet_service.estimate_cart_edit_cost(admin_settings, tokens)


async def _history(shop_bot_id: int) -> list[tuple[str, str]]:
    async with session_scope() as session:
        customer_id = await _customer_id(session, shop_bot_id)
        result = await session.execute(
            select(ConversationMessage).where(ConversationMessage.customer_id == customer_id).order_by(ConversationMessage.id)
        )
        return [(message.role, message.content) for message in result.scalars().all()]


async def _orders(shop_bot_id: int) -> list[OrderConsultation]:
    async with session_scope() as session:
        result = await session.execute(select(OrderConsultation).where(OrderConsultation.shop_bot_id == shop_bot_id))
        return list(result.scalars().all())


def _new_bot() -> Bot:
    return Bot(token=f"{SHOP_BOT_TG_ID}:FAKE", session=FakeSession())


def _sent(bot: Bot) -> list[dict]:
    session: FakeSession = bot.session  # type: ignore[assignment]
    return session.sent_messages


def _answered(bot: Bot) -> list[dict]:
    session: FakeSession = bot.session  # type: ignore[assignment]
    return session.answered_callbacks


def _callback_datas(markup) -> list[str]:
    return [button.callback_data for row in markup.inline_keyboard for button in row]


_SHOP_DP = None  # در main() مقدار می‌گیره؛ _apply برایِ زدنِ دکمه‌یِ «✅ اعمال» (W5/C2) لازمش داره


async def _apply(bot: Bot, action: str = "apply") -> str | None:
    """دکمه‌یِ آخرین پیشنهادِ AI (cart_ai_apply/cart_ai_reject) رو می‌زنه؛ متنِ ویرایش‌شده‌یِ پیام رو برمی‌گردونه."""
    message = next(
        m
        for m in reversed(_sent(bot))
        if m.get("reply_markup") is not None and any(d.startswith("cart_ai_apply:") for d in _callback_datas(m["reply_markup"]))
    )
    data = next(d for d in _callback_datas(message["reply_markup"]) if d.startswith(f"cart_ai_{action}:"))
    edits_before = len(bot.session.edited_texts)
    await _SHOP_DP.feed_update(bot, make_callback_update(_uid(), data=data, user_id=CUSTOMER_TG_ID))
    edited = bot.session.edited_texts
    return edited[-1]["text"] if len(edited) > edits_before else None


async def _send(shop_bot_id: int, bot: Bot, main_bot: Bot, text: str) -> None:
    """همون تابعی که بعد از debounce صدا زده می‌شه، مستقیم (بدونِ انتظار)."""
    async with session_scope() as session:
        await customer_handlers._generate_and_send_reply(session, shop_bot_id, CUSTOMER_TG_ID, text, bot, main_bot)


# =============================================================================
# ۱. قوانینِ اعتبارسنجی (بدونِ دیتابیس)
# =============================================================================
async def test_pure_validation_rules() -> None:
    valid = {1, 2, 3}
    parse = cart_edit_service.parse_classifier_output

    assert parse({"status": "none"}, valid) is None
    assert parse({"status": "چیزِ عجیب"}, valid) is None
    assert parse({"status": "unsure"}, valid) is None, "unsure بدونِ سوال بی‌فایده‌ست"

    result = parse({"status": "edit", "operations": [{"action": "add", "product_id": "2"}]}, valid)
    assert result.operations == [cart_edit_service.CartOperation("add", 2, 1)], "شناسه‌ی رشته‌ای قبول می‌شه و add بدونِ تعداد یعنی ۱"

    result = parse({"status": "edit", "operations": [{"action": "add", "product_id": 99, "quantity": 1}]}, valid)
    assert result.status == "unsure" and result.rejected_count == 1, "شناسه‌ی ساختگی هیچ‌وقت عملیات نمی‌شه"

    result = parse(
        {"status": "edit", "operations": [{"action": "add", "product_id": 99, "quantity": 1}, {"action": "remove", "product_id": 2}]}, valid
    )
    assert result.status == "edit" and result.operations == [cart_edit_service.CartOperation("remove", 2, None)]
    assert result.rejected_count == 1

    for bad_quantity in (0, -3, 1001, 2.5, "abc", True):
        result = parse({"status": "edit", "operations": [{"action": "set", "product_id": 1, "quantity": bad_quantity}]}, valid)
        assert result.status == "unsure", f"تعدادِ نامعتبر ({bad_quantity!r}) باید رد بشه"

    result = parse({"status": "edit", "operations": [{"action": "set", "product_id": 1, "quantity": "۳"}]}, valid)
    assert result.operations[0].quantity == 3, "رقمِ فارسی باید به عدد تبدیل بشه"

    result = parse({"status": "edit", "operations": [{"action": "add", "product_id": 1, "quantity": 1}] * 14}, valid)
    assert len(result.operations) == cart_edit_service.MAX_OPERATIONS and result.rejected_count == 4

    result = parse({"status": "edit", "operations": [{"action": "clear"}]}, valid)
    assert result.wants_clear

    assert cart_edit_service.mentions_cart("۳ تا کیک به سبدم اضافه کن")
    assert not cart_edit_service.mentions_cart("قیمتِ برنج چنده؟")

    products = [Product(id=1, name="برنج"), Product(id=2, name="چای")]
    items = [(CartItem(id=1, cart_id=1, product_id=1, quantity=3), products[0])]
    prompt = cart_edit_service.build_classifier_system_prompt(products, items)
    assert "1 | برنج | 3" in prompt and "2 | چای" in prompt, "پرامپت باید سبدِ فعلی و فهرستِ محصولات رو داشته باشه"
    assert "خالیه" in cart_edit_service.build_classifier_system_prompt(products, [])

    print("✅ test_pure_validation_rules PASSED")


# =============================================================================
# ۲. یه دستورِ سبد کاملاً همون‌جا جواب داده می‌شه
# =============================================================================
async def test_edit_applies_changes_and_skips_normal_chat(main_bot) -> None:
    shop = await _seed_shop({"برنج": 3, "چای": 1})
    bot = _new_bot()
    main_bot.session.sent_messages.clear()
    ai = _set_ai(_FakeAi(cart_json=_edit_json({"action": "decrease", "product_id": shop.rice, "quantity": 2})))

    await _send(shop.shop_bot_id, bot, main_bot, "دوتا از برنج کم کن")
    await asyncio.sleep(0.3)  # اگه تسکِ پس‌زمینه‌ی تشخیصِ سفارش اشتباهاً ساخته شده بود، فرصتِ اجرا داشته باشه

    assert await _cart_contents(shop.shop_bot_id) == {"برنج": 3, "چای": 1}, "W5/C2: AI فقط پیشنهاد می‌ده؛ تا «✅ اعمال» سبد دست‌نخورده‌ست"
    assert len(ai.cart_calls) == 1
    assert ai.chat_calls == 0, "پاسخِ چتِ عادی نباید اجرا بشه؛ دستورِ سبد همین‌جا جواب داده شده"
    assert ai.order_calls == 0, "تشخیصِ سفارش هم نباید اجرا بشه"

    sent = _sent(bot)
    assert len(sent) == 1, f"فقط یه پیامِ پیشنهاد باید بره، رفت {len(sent)}"
    text = sent[0]["text"]
    assert "برنج" in text and "کم بشه" in text, "پیشنهاد باید بگه چی عوض می‌شه"
    assert "cart_ai_apply" in "".join(_callback_datas(sent[0]["reply_markup"]))
    edited = await _apply(bot)
    assert await _cart_contents(shop.shop_bot_id) == {"برنج": 1, "چای": 1}
    assert edited is not None and "کم شد" in edited, "تأییدیه باید بگه چی عوض شد"
    assert "۲۵۰٬۰۰۰" in edited, "سبدِ به‌روز (۱×برنج + ۱×چای = ۲۵۰٬۰۰۰) باید نشون داده بشه"
    assert "cart_checkout_start" in _callback_datas(bot.session.edited_texts[-1]["reply_markup"])
    assert len(main_bot.session.sent_messages) == 0, "فروشگاه‌دار نباید چیزی ببینه"

    expected_cost = await _expected_cart_edit_cost()
    assert await _reason_total(WalletTransactionReason.CART_EDIT) == -expected_cost, "هزینه‌ی کلاسیفایر باید کسر بشه"
    assert await _reason_total(WalletTransactionReason.CHAT_MESSAGE) == 0
    assert await _reason_total(WalletTransactionReason.ORDER_DETECTION) == 0

    assert await _history(shop.shop_bot_id) == [("user", "دوتا از برنج کم کن"), ("assistant", text)]

    print("✅ test_edit_applies_changes_and_skips_normal_chat PASSED")


# =============================================================================
# ۳. «هیچی» → مسیرِ چتِ عادی دقیقاً مثلِ قبل
# =============================================================================
async def test_classifier_none_falls_through_to_normal_chat(main_bot) -> None:
    shop = await _seed_shop({"چای": 1})
    bot = _new_bot()
    ai = _set_ai(_FakeAi(cart_json='{"status": "none"}'))

    await _send(shop.shop_bot_id, bot, main_bot, "ارسالتون چند روزه‌ست؟")
    await asyncio.sleep(0.6)  # تشخیصِ سفارشِ پس‌زمینه

    assert await _cart_contents(shop.shop_bot_id) == {"چای": 1}, "سبد نباید دست بخوره"
    assert len(ai.cart_calls) == 1
    assert ai.chat_calls == 1, "پیام باید به چتِ عادی برسه"
    assert ai.order_calls == 1, "تشخیصِ سفارشِ پس‌زمینه باید مثلِ همیشه بعد از چت اجرا بشه"

    sent = _sent(bot)
    assert len(sent) == 1 and sent[0]["text"] == "CHAT_REPLY"
    assert await _reason_total(WalletTransactionReason.CART_EDIT) < 0, "کلاسیفایر صدا زده شده، هزینه‌ش باید کسر بشه"
    assert await _reason_total(WalletTransactionReason.CHAT_MESSAGE) < 0
    assert await _reason_total(WalletTransactionReason.ORDER_DETECTION) < 0

    print("✅ test_classifier_none_falls_through_to_normal_chat PASSED")


# =============================================================================
# ۴. مشتری‌ای که با سبد کاری نداره، هیچ هزینه‌ی اضافه‌ای نداره
# =============================================================================
async def test_no_cart_and_no_mention_never_calls_classifier(main_bot) -> None:
    shop = await _seed_shop()  # بدونِ سبد
    bot = _new_bot()
    ai = _set_ai(_FakeAi(cart_json=_edit_json({"action": "add", "product_id": shop.tea, "quantity": 1})))

    await _send(shop.shop_bot_id, bot, main_bot, "قیمتِ برنج چنده؟")
    await asyncio.sleep(0.6)

    assert len(ai.cart_calls) == 0, "بدونِ سبدِ پر و بدونِ کلمه‌ی «سبد»، کلاسیفایرِ سبد نباید صدا زده بشه"
    assert ai.chat_calls == 1
    assert await _reason_total(WalletTransactionReason.CART_EDIT) == 0
    assert await _cart_contents(shop.shop_bot_id) == {}
    async with session_scope() as session:
        customer_id = await _customer_id(session, shop.shop_bot_id)
        assert await cart_service.get_cart(session, shop.shop_bot_id, customer_id) is None, "حتی ردیفِ سبد هم نباید ساخته بشه"

    print("✅ test_no_cart_and_no_mention_never_calls_classifier PASSED")


async def test_empty_cart_with_cart_mention_adds_item(main_bot) -> None:
    shop = await _seed_shop()
    bot = _new_bot()
    ai = _set_ai(_FakeAi(cart_json=_edit_json({"action": "add", "product_id": shop.tea, "quantity": 3})))

    await _send(shop.shop_bot_id, bot, main_bot, "۳ تا چای به سبدم اضافه کن")

    assert await _cart_contents(shop.shop_bot_id) == {}, "W5/C2: تا تایید چیزی اضافه نمی‌شه"
    edited = await _apply(bot)
    assert await _cart_contents(shop.shop_bot_id) == {"چای": 3}
    assert len(ai.cart_calls) == 1 and ai.chat_calls == 0
    assert "خالیه" in ai.cart_calls[0][0], "AI باید بدونه سبدِ فعلی خالیه"
    assert "اضافه بشه" in _sent(bot)[0]["text"] and "اضافه شد" in (edited or "")

    print("✅ test_empty_cart_with_cart_mention_adds_item PASSED")


# =============================================================================
# ۵. unsure: سوالِ روشن‌کننده، بدونِ تغییر، و سوال توی تاریخچه می‌مونه
# =============================================================================
async def test_unsure_asks_question_and_keeps_context(main_bot) -> None:
    shop = await _seed_shop({"برنج": 2})
    bot = _new_bot()
    question = "کدوم محصول رو و چندتا ازش کم کنم؟"
    ai = _set_ai(_FakeAi(cart_json=json.dumps({"status": "unsure", "clarifying_question": question}, ensure_ascii=False)))

    await _send(shop.shop_bot_id, bot, main_bot, "کمش کن")

    assert await _cart_contents(shop.shop_bot_id) == {"برنج": 2}, "حدس نمی‌زنیم؛ سبد دست‌نخورده می‌مونه"
    sent = _sent(bot)
    assert len(sent) == 1 and sent[0]["text"] == question
    assert ai.chat_calls == 0, "سوالِ روشن‌کننده جایگزینِ پاسخِ چته، نه اضافه‌ش"
    assert await _history(shop.shop_bot_id) == [("user", "کمش کن"), ("assistant", question)]

    ai.cart_json = _edit_json({"action": "decrease", "product_id": shop.rice, "quantity": 1})
    await _send(shop.shop_bot_id, bot, main_bot, "برنج، یکی")
    assert await _cart_contents(shop.shop_bot_id) == {"برنج": 2}, "W5/C2: فقط پیشنهاد؛ تا «✅ اعمال» سبد دست‌نخورده"
    await _apply(bot)

    assert await _cart_contents(shop.shop_bot_id) == {"برنج": 1}
    assert {"role": "assistant", "content": question} in ai.cart_calls[1][1], "AI باید سوالِ قبلیِ خودش رو توی تاریخچه ببینه"

    print("✅ test_unsure_asks_question_and_keeps_context PASSED")


# =============================================================================
# ۶. هالوسینیشن و محصولِ فروشگاهِ دیگه
# =============================================================================
async def test_foreign_and_invented_product_ids_are_rejected(main_bot) -> None:
    shop = await _seed_shop({"برنج": 2})
    bot = _new_bot()

    other_shop_bot_id = await seed_usable_shop(OWNER_TG_ID + 10, SHOP_BOT_TG_ID + 10)
    async with session_scope() as session:
        foreign = await product_service.create_product(session, other_shop_bot_id, "محصولِ فروشگاهِ دیگه", None, 10_000, None)
    foreign_id = foreign.id

    operations = [
        {"action": "add", "product_id": foreign_id, "quantity": 5},  # شناسه‌ی واقعی، ولی مالِ این فروشگاه نیست
        {"action": "add", "product_id": 987654, "quantity": 1},  # شناسه‌ی ساختگی
    ]
    ai = _set_ai(_FakeAi(cart_json=_edit_json(*operations)))

    await _send(shop.shop_bot_id, bot, main_bot, "یه چیزی بذار تو سبدم")

    assert await _cart_contents(shop.shop_bot_id) == {"برنج": 2}, "هیچ‌کدوم از اون دو شناسه نباید به سبد راه پیدا کنه"
    sent = _sent(bot)
    assert len(sent) == 1 and sent[0]["text"] == shop_texts.CART_AI_CLARIFY_GENERIC
    assert ai.chat_calls == 0

    print("✅ test_foreign_and_invented_product_ids_are_rejected PASSED")


async def test_partial_validity_applies_only_valid_operations(main_bot) -> None:
    shop = await _seed_shop({"برنج": 2, "چای": 1})
    bot = _new_bot()
    operations = [
        {"action": "remove", "product_id": shop.tea, "quantity": None},
        {"action": "add", "product_id": 987654, "quantity": 1},
    ]
    _set_ai(_FakeAi(cart_json=_edit_json(*operations)))

    await _send(shop.shop_bot_id, bot, main_bot, "چای رو حذف کن و یه چیزِ دیگه هم بذار")

    assert await _cart_contents(shop.shop_bot_id) == {"برنج": 2, "چای": 1}, "تا تایید چیزی عوض نمی‌شه"
    text = _sent(bot)[0]["text"]
    assert "حذف بشه" in text
    assert "۱ مورد" in text and "متوجه نشدم" in text, "به مشتری گفته بشه یه موردش فهمیده نشد"
    edited = await _apply(bot)
    assert await _cart_contents(shop.shop_bot_id) == {"برنج": 2}, "عملیاتِ معتبر با تایید اعمال می‌شه"
    assert "حذف شد" in (edited or "")

    print("✅ test_partial_validity_applies_only_valid_operations PASSED")


# =============================================================================
# ۷. سقفِ موجودی صادقانه گزارش می‌شه
# =============================================================================
async def test_stock_limits_are_reported_honestly(main_bot) -> None:
    shop = await _seed_shop({"برنج": 4})  # موجودیِ برنج ۵ تاست
    bot = _new_bot()
    operations = [
        {"action": "add", "product_id": shop.rice, "quantity": 3},
        {"action": "add", "product_id": shop.cake, "quantity": 1},  # موجودیِ کیک صفره
    ]
    _set_ai(_FakeAi(cart_json=_edit_json(*operations)))

    await _send(shop.shop_bot_id, bot, main_bot, "سه تا برنج و یه کیک هم بذار")

    assert await _cart_contents(shop.shop_bot_id) == {"برنج": 4}, "تا تایید چیزی عوض نمی‌شه"
    text = await _apply(bot) or ""
    assert await _cart_contents(shop.shop_bot_id) == {"برنج": 5}, "برنج فقط تا سقفِ موجودی (۵) بالا می‌ره و کیک اصلاً اضافه نمی‌شه"
    assert "فقط ۱ عدد موجود بود" in text, "باید صادقانه بگه فقط ۱ عدد اضافه شد"
    assert "موجودی نداره" in text, "باید بگه کیک موجودی نداره"

    print("✅ test_stock_limits_are_reported_honestly PASSED")


# =============================================================================
# ۸. خالی‌کردنِ کلِ سبد فقط با تاییدِ دکمه‌ای
# =============================================================================
async def test_clear_requires_confirmation_and_rejects_stale_buttons(shop_dp, main_bot) -> None:
    shop = await _seed_shop({"برنج": 2, "چای": 1})
    bot = _new_bot()
    ai = _set_ai(_FakeAi(cart_json=_edit_json({"action": "clear", "product_id": None, "quantity": None})))

    await _send(shop.shop_bot_id, bot, main_bot, "سبدمو کلاً خالی کن")

    assert await _cart_contents(shop.shop_bot_id) == {"برنج": 2, "چای": 1}, "بدونِ تاییدِ مشتری نباید چیزی پاک بشه"
    sent = _sent(bot)
    assert len(sent) == 1 and shop_texts.CART_AI_CLEAR_PROMPT in sent[0]["text"]
    datas = _callback_datas(sent[0]["reply_markup"])
    clear_data = next(data for data in datas if data.startswith("cart_ai_clear:"))
    assert "cart_ai_keep" in datas
    assert ai.chat_calls == 0

    # «نه، نگهش دار»
    await shop_dp.feed_update(bot, make_callback_update(_uid(), data="cart_ai_keep", user_id=CUSTOMER_TG_ID))
    assert await _cart_contents(shop.shop_bot_id) == {"برنج": 2, "چای": 1}

    # سبد عوض می‌شه؛ دکمه‌ی قدیمیِ «خالی کن» دیگه نباید کار کنه
    await _put_in_cart(shop.shop_bot_id, shop.tea, 1)
    await shop_dp.feed_update(bot, make_callback_update(_uid(), data=clear_data, user_id=CUSTOMER_TG_ID))
    assert await _cart_contents(shop.shop_bot_id) == {"برنج": 2, "چای": 2}, "دکمه‌ی کهنه نباید سبدِ عوض‌شده رو پاک کنه"
    last_answer = _answered(bot)[-1]
    assert last_answer["text"] == shop_texts.CART_AI_CLEAR_STALE and last_answer["show_alert"]

    # دوباره دستورِ خالی‌کردن → دکمه‌ی تازه (اثرانگشتِ جدید) → تایید
    await _send(shop.shop_bot_id, bot, main_bot, "سبدمو خالی کن")
    new_clear_data = next(data for data in _callback_datas(_sent(bot)[-1]["reply_markup"]) if data.startswith("cart_ai_clear:"))
    assert new_clear_data != clear_data, "اثرانگشتِ سبدِ عوض‌شده باید فرق کنه"
    await shop_dp.feed_update(bot, make_callback_update(_uid(), data=new_clear_data, user_id=CUSTOMER_TG_ID))
    assert await _cart_contents(shop.shop_bot_id) == {}, "با تاییدِ معتبر، سبد خالی می‌شه"

    # روی سبدِ خالی، دکمه‌ی قدیمی هم فقط هشدارِ «خالیه» می‌ده
    await shop_dp.feed_update(bot, make_callback_update(_uid(), data=new_clear_data, user_id=CUSTOMER_TG_ID))
    assert _answered(bot)[-1]["text"] == shop_texts.CART_EMPTY

    print("✅ test_clear_requires_confirmation_and_rejects_stale_buttons PASSED")


async def test_show_cart_command(main_bot) -> None:
    shop = await _seed_shop({"برنج": 1})
    bot = _new_bot()
    ai = _set_ai(_FakeAi(cart_json='{"status": "show_cart"}'))

    await _send(shop.shop_bot_id, bot, main_bot, "الان تو سبدم چی دارم؟")

    sent = _sent(bot)
    assert len(sent) == 1 and "برنج" in sent[0]["text"] and "جمعِ کل" in sent[0]["text"]
    assert "cart_checkout_start" in _callback_datas(sent[0]["reply_markup"]), "دکمه‌ی نهایی‌کردن باید باشه (AI خودش سفارش ثبت نمی‌کنه)"
    assert ai.chat_calls == 0
    assert await _cart_contents(shop.shop_bot_id) == {"برنج": 1}
    assert await _orders(shop.shop_bot_id) == []

    print("✅ test_show_cart_command PASSED")


# =============================================================================
# ۹. شکستِ AI → بدونِ هزینه، و پیام به چتِ عادی می‌ره
# =============================================================================
async def test_ai_failure_falls_back_to_normal_chat_without_charge(main_bot) -> None:
    shop = await _seed_shop({"چای": 1})
    bot = _new_bot()
    ai = _set_ai(_FakeAi(cart_raises=True))

    await _send(shop.shop_bot_id, bot, main_bot, "چای رو حذف کن")
    await asyncio.sleep(0.6)

    assert await _cart_contents(shop.shop_bot_id) == {"چای": 1}, "وقتی AI شکست می‌خوره هیچ تغییری اعمال نمی‌شه"
    assert len(ai.cart_calls) == 1 and ai.chat_calls == 1
    assert await _reason_total(WalletTransactionReason.CART_EDIT) == 0, "فراخوانیِ شکست‌خورده هزینه‌ای نداره"
    assert _sent(bot)[0]["text"] == "CHAT_REPLY"

    print("✅ test_ai_failure_falls_back_to_normal_chat_without_charge PASSED")


async def _checkout_to_preview(shop_dp, bot, has_saved_addresses: bool = False) -> None:
    """از «نهایی‌کردن» تا پیش‌نمایشِ نهایی با جریانِ مرحله‌ایِ W5/C3 (helperِ مشترکِ tests_manual/checkout_helpers.py)."""

    async def tap(data: str) -> None:
        await shop_dp.feed_update(bot, make_callback_update(_uid(), data=data, user_id=CUSTOMER_TG_ID))

    async def say(text: str) -> None:
        await shop_dp.feed_update(bot, make_message_update(_uid(), text=text, user_id=CUSTOMER_TG_ID))

    await run_checkout(tap, say, has_saved_addresses=has_saved_addresses)


# =============================================================================
# ۱۰. پیش‌نمایشِ چک‌اوت بعد از ویرایشِ سبد کهنه می‌شه
# =============================================================================
async def test_checkout_refuses_stale_preview_after_cart_edit(shop_dp, main_bot) -> None:
    shop = await _seed_shop()
    bot = _new_bot()
    main_bot.session.sent_messages.clear()

    for product_id in (shop.rice, shop.tea):
        await shop_dp.feed_update(bot, make_callback_update(_uid(), data=f"cart_add:{product_id}", user_id=CUSTOMER_TG_ID))
    await _checkout_to_preview(shop_dp, bot)  # W5/C3: چک‌اوتِ مرحله‌ایِ جدید
    assert "۲۵۰٬۰۰۰" in _sent(bot)[-1]["text"], "پیش‌نمایشِ نهایی باید نشون داده شده باشه"

    # مشتری بعد از دیدنِ پیش‌نمایش، با یه پیامِ متنی سبد رو عوض می‌کنه
    _set_ai(_FakeAi(cart_json=_edit_json({"action": "remove", "product_id": shop.tea, "quantity": None})))
    await _send(shop.shop_bot_id, bot, main_bot, "چای رو از سبدم حذف کن")
    await _apply(bot)  # W5/C2: ویرایش با تاییدِ مشتری اعمال می‌شه
    assert await _cart_contents(shop.shop_bot_id) == {"برنج": 1}

    await shop_dp.feed_update(bot, make_callback_update(_uid(), data="cart_checkout_confirm", user_id=CUSTOMER_TG_ID))

    assert await _orders(shop.shop_bot_id) == [], "چیزی که مشتری دیده با چیزی که ثبت می‌شد یکی نیست؛ نباید ثبت بشه"
    assert await _cart_contents(shop.shop_bot_id) == {"برنج": 1}, "سبد نباید خالی بشه"
    assert len(main_bot.session.sent_messages) == 0, "فروشگاه‌دار نباید خبردار بشه"
    async with session_scope() as session:
        rice = await product_service.get_by_id(session, shop.rice)
        assert rice.reserved_quantity == 0, "هیچ موجودی‌ای نباید رزرو شده باشه"

    # شاهدِ مثبت: چک‌اوتِ تازه با سبدِ فعلی بدونِ مشکل ثبت می‌شه
    await _checkout_to_preview(shop_dp, bot, has_saved_addresses=True)  # W5/C3: چک‌اوتِ مرحله‌ایِ جدید
    await shop_dp.feed_update(bot, make_callback_update(_uid(), data="cart_checkout_confirm", user_id=CUSTOMER_TG_ID))
    orders = await _orders(shop.shop_bot_id)
    assert len(orders) == 1 and orders[0].product_id == shop.rice, "چک‌اوتِ دوم (با پیش‌نمایشِ تازه) باید ثبت بشه"

    print("✅ test_checkout_refuses_stale_preview_after_cart_edit PASSED")


# =============================================================================
# ۱۱. دو دستورِ همزمانِ یه مشتری به ترتیب اجرا می‌شن
# =============================================================================
async def test_concurrent_commands_are_serialized(main_bot) -> None:
    """W5/C2: دو دستورِ هم‌زمان به ترتیب اجرا می‌شن؛ پیشنهادِ دوم، پیشنهادِ اول رو منسوخ می‌کنه
    (فقط آخرین پیشنهاد قابلِ اعمال است) و اعمالِ پیشنهادِ منسوخ اثری ندارد."""
    shop = await _seed_shop()
    bot = _new_bot()

    def responder(system_prompt: str, user_message: str) -> str:
        if "MARK_ADD" in user_message:
            return _edit_json({"action": "add", "product_id": shop.rice, "quantity": 2})
        return _edit_json({"action": "add", "product_id": shop.tea, "quantity": 1})

    ai = _set_ai(_FakeAi(cart_json=responder, cart_delay=0.4))

    first = asyncio.create_task(_send(shop.shop_bot_id, bot, main_bot, "MARK_ADD دوتا برنج اضافه کن به سبدم"))
    for _ in range(100):
        if ai.cart_calls:
            break
        await asyncio.sleep(0.05)
    assert ai.cart_calls, "پیامِ اول باید به کلاسیفایر رسیده باشه"
    second = asyncio.create_task(_send(shop.shop_bot_id, bot, main_bot, "MARK_TEA یه چای هم به سبدم اضافه کن"))
    await asyncio.gather(first, second)

    assert len(ai.cart_calls) == 2
    assert await _cart_contents(shop.shop_bot_id) == {}, "هیچ پیشنهادی بدونِ تایید اعمال نمی‌شه"
    sent = _sent(bot)
    assert len(sent) == 2
    first_apply = next(d for d in _callback_datas(sent[0]["reply_markup"]) if d.startswith("cart_ai_apply:"))
    second_apply = next(d for d in _callback_datas(sent[1]["reply_markup"]) if d.startswith("cart_ai_apply:"))
    assert first_apply != second_apply

    await _SHOP_DP.feed_update(bot, make_callback_update(_uid(), data=first_apply, user_id=CUSTOMER_TG_ID))
    assert await _cart_contents(shop.shop_bot_id) == {}, "پیشنهادِ منسوخ اثری ندارد"
    assert _answered(bot)[-1]["show_alert"] is True

    await _SHOP_DP.feed_update(bot, make_callback_update(_uid(), data=second_apply, user_id=CUSTOMER_TG_ID))
    assert await _cart_contents(shop.shop_bot_id) == {"چای": 1}
    await _SHOP_DP.feed_update(bot, make_callback_update(_uid(), data=second_apply, user_id=CUSTOMER_TG_ID))  # دابل‌تپ
    assert await _cart_contents(shop.shop_bot_id) == {"چای": 1}, "دابل‌تپِ «اعمال» = یک اثر"
    assert await _reason_total(WalletTransactionReason.CART_EDIT) == -2 * await _expected_cart_edit_cost()

    print("✅ test_concurrent_commands_are_serialized PASSED")


# =============================================================================
# ۱۲. مسیرِ کاملِ dispatcher: پیامِ متنی → debounce → pipeline → ویرایشِ سبد
# =============================================================================
async def test_full_dispatcher_path_with_debounce(shop_dp, main_bot) -> None:
    shop = await _seed_shop({"برنج": 3})
    bot = _new_bot()
    ai = _set_ai(_FakeAi(cart_json=_edit_json({"action": "remove", "product_id": shop.rice, "quantity": None})))

    original_debounce = customer_handlers.DEBOUNCE_SECONDS
    customer_handlers.DEBOUNCE_SECONDS = 0.3  # برایِ سرعتِ تست (مقدارِ واقعی ۳ ثانیه‌ست)
    try:
        await shop_dp.feed_update(bot, make_message_update(_uid(), text="برنج رو حذف کن", user_id=CUSTOMER_TG_ID))
        await asyncio.sleep(1.5)
    finally:
        customer_handlers.DEBOUNCE_SECONDS = original_debounce

    assert await _cart_contents(shop.shop_bot_id) == {"برنج": 3}, "پیامِ متنیِ واقعی پیشنهاد می‌سازه، نه تغییرِ مستقیم"
    assert ai.chat_calls == 0
    sent = _sent(bot)
    assert len(sent) == 1 and "حذف بشه" in sent[0]["text"]
    edited = await _apply(bot)
    assert await _cart_contents(shop.shop_bot_id) == {}, "با تاییدِ مشتری سبد عوض می‌شه"
    assert "حذف شد" in (edited or "")

    print("✅ test_full_dispatcher_path_with_debounce PASSED")


async def test_cart_view_shows_hint_only_when_cart_has_items(shop_dp, main_bot) -> None:
    shop = await _seed_shop()
    bot = _new_bot()

    await shop_dp.feed_update(bot, make_message_update(_uid(), text="🛒 سبدِ خرید", user_id=CUSTOMER_TG_ID))
    assert shop_texts.CART_AI_HINT not in _sent(bot)[-1]["text"], "سبدِ خالی نیازی به راهنما نداره"

    await _put_in_cart(shop.shop_bot_id, shop.tea, 1)
    await shop_dp.feed_update(bot, make_message_update(_uid(), text="🛒 سبدِ خرید", user_id=CUSTOMER_TG_ID))
    assert shop_texts.CART_AI_HINT in _sent(bot)[-1]["text"], "سبدِ پر باید راهنمای ویرایش با متن رو نشون بده"

    print("✅ test_cart_view_shows_hint_only_when_cart_has_items PASSED")


async def main() -> None:
    original_get_ai_service = ai_service.get_ai_service
    ai_service.get_ai_service = _patched_get_ai_service
    global _SHOP_DP
    _main_dp, shop_dp, _bot_manager, main_bot = build_test_dispatchers()
    _SHOP_DP = shop_dp
    try:
        await test_pure_validation_rules()
        await test_edit_applies_changes_and_skips_normal_chat(main_bot)
        await test_classifier_none_falls_through_to_normal_chat(main_bot)
        await test_no_cart_and_no_mention_never_calls_classifier(main_bot)
        await test_empty_cart_with_cart_mention_adds_item(main_bot)
        await test_unsure_asks_question_and_keeps_context(main_bot)
        await test_foreign_and_invented_product_ids_are_rejected(main_bot)
        await test_partial_validity_applies_only_valid_operations(main_bot)
        await test_stock_limits_are_reported_honestly(main_bot)
        await test_clear_requires_confirmation_and_rejects_stale_buttons(shop_dp, main_bot)
        await test_show_cart_command(main_bot)
        await test_ai_failure_falls_back_to_normal_chat_without_charge(main_bot)
        await test_checkout_refuses_stale_preview_after_cart_edit(shop_dp, main_bot)
        await test_concurrent_commands_are_serialized(main_bot)
        await test_full_dispatcher_path_with_debounce(shop_dp, main_bot)
        await test_cart_view_shows_hint_only_when_cart_has_items(shop_dp, main_bot)
    finally:
        ai_service.get_ai_service = original_get_ai_service


if __name__ == "__main__":
    asyncio.run(main())
