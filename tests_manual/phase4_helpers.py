"""
کمک‌کننده‌هایِ مشترکِ تست‌هایِ فازِ ۴ (این فایل خودش تست *نیست* و توی run_all_tests ثبت نشده).

- Chat: یه گفتگوی تستی با ربات اصلی (همون الگویِ test_campaign_owner_flow).
- FakeAi + patched_ai: هوش مصنوعیِ جعلی که ورودی‌هایِ هر فراخوانی رو ثبت می‌کنه.
- add_customer / add_order / wallet_transactions: ساختِ دیتایِ تست با زمان‌هایِ کنترل‌شده.
"""
from __future__ import annotations

import asyncio
import contextlib
import datetime
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402
from sqlalchemy import select  # noqa: E402

from harness import FakeSession, make_callback_update, make_message_update  # noqa: E402

from app.database.models import (  # noqa: E402
    Customer,
    OrderConsultation,
    OrderStatus,
    OrderType,
    ShopOwner,
    WalletTransaction,
    WalletTransactionReason,
)
from app.database.session import session_scope  # noqa: E402
from app.services import ai_service  # noqa: E402
from app.services.ai_service import AiCallResult  # noqa: E402
from app.services.order_detection_service import _CLASSIFIER_USER_PROMPT  # noqa: E402

UTC = datetime.timezone.utc


class Chat:
    """یه گفتگوی تستی با ربات اصلی: شمارنده‌ی update_id + میان‌برهایِ فرستادنِ متن/دکمه."""

    def __init__(self, dp, user_id: int) -> None:
        self.dp = dp
        self.user_id = user_id
        self.bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())
        self.session: FakeSession = self.bot.session  # type: ignore[assignment]
        # پ۶۴: این گفتگو شناسهٔ کال‌بک را خودش می‌شمارد (`_n`) ⇒ نگهبانِ «پاسخِ دوباره» روشن است.
        self.session.strict_callback_answers = True
        self._n = 0
        # پ۶۵: برخی جریان‌ها هندلرشان یکِ وابستگیِ تزریق‌شده می‌خواهد (مثلاً `bot_manager`).
        # پیش‌فرضِ خالی یعنی «هیچ» ⇒ هیچ تستِ قدیمی نباید چیزی حس کند.
        self.extra: dict = {}

    async def say(self, text: str) -> None:
        self._n += 1
        await self.dp.feed_update(self.bot, make_message_update(self._n, text=text, user_id=self.user_id), **self.extra)

    async def tap(self, data: str) -> None:
        self._n += 1
        await self.dp.feed_update(self.bot, make_callback_update(self._n, data=data, user_id=self.user_id), **self.extra)

    @property
    def sent(self) -> list[dict]:
        return self.session.sent_messages

    @property
    def last_text(self) -> str:
        return self.session.sent_messages[-1]["text"]

    @property
    def last_markup(self):
        return self.session.sent_messages[-1]["reply_markup"]

    @property
    def last_toast(self) -> dict:
        return self.session.answered_callbacks[-1]

    @property
    def documents(self) -> list[dict]:
        return self.session.sent_documents

    @property
    def edits(self) -> list[dict]:
        return self.session.edited_texts

    @property
    def last_edit_text(self) -> str:
        return self.session.edited_texts[-1]["text"]

    @property
    def last_edit_markup(self):
        return self.session.edited_texts[-1]["reply_markup"]


def callbacks(markup) -> list[str]:
    if markup is None:
        return []
    return [button.callback_data for row in markup.inline_keyboard for button in row if button.callback_data]


def reply_keyboard_texts(markup) -> set[str]:
    return {button.text for row in markup.keyboard for button in row}


# =============================================================================
# هوش مصنوعیِ جعلی
# =============================================================================
class FakeAi:
    """
    chat_reply: رشته، یا تابعِ (system_prompt, history, user_message) -> رشته.
    فراخوانی‌هایِ کلاسیفایرِ تشخیصِ سفارش (user_message == _CLASSIFIER_USER_PROMPT) جدا شمرده می‌شن
    و همیشه «هیچ سفارشی» برمی‌گردونن؛ بقیه‌یِ فراخوانی‌ها توی chat_calls ثبت می‌شن.
    """

    def __init__(self, chat_reply="CHAT_REPLY", *, raises: bool = False, delay: float = 0.0, tokens: int = 1000) -> None:
        self.chat_reply = chat_reply
        self.raises = raises
        self.delay = delay
        self.tokens = tokens
        self.chat_calls: list[tuple[str, list[dict[str, str]], str]] = []
        self.classifier_calls = 0

    async def get_reply(self, system_prompt: str, history: list[dict[str, str]], user_message: str) -> AiCallResult:
        if user_message == _CLASSIFIER_USER_PROMPT:
            self.classifier_calls += 1
            return AiCallResult(text='{"status": "none"}', total_tokens=77)
        self.chat_calls.append((system_prompt, list(history), user_message))
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.raises:
            raise ai_service.AiServiceError("شکستِ شبیه‌سازی‌شده")
        text = self.chat_reply(system_prompt, history, user_message) if callable(self.chat_reply) else self.chat_reply
        return AiCallResult(text=text, total_tokens=self.tokens)

    async def analyze_image(self, prompt: str, image_bytes: bytes, mime_type: str = "image/jpeg") -> AiCallResult:
        return AiCallResult(text="")

    async def transcribe_audio(self, audio_bytes: bytes, filename: str = "voice.ogg") -> str:
        return ""


_current_ai: FakeAi | None = None


def set_ai(ai: FakeAi) -> FakeAi:
    global _current_ai
    _current_ai = ai
    return ai


def _patched_get_ai_service(*args, **kwargs):
    assert _current_ai is not None, "تست فراموش کرده AIِ جعلی رو با set_ai تنظیم کنه"
    return _current_ai


@contextlib.contextmanager
def patched_ai():
    original = ai_service.get_ai_service
    ai_service.get_ai_service = _patched_get_ai_service
    try:
        yield
    finally:
        ai_service.get_ai_service = original


# =============================================================================
# ساختِ دیتایِ تست
# =============================================================================
async def add_customer(
    shop_bot_id: int,
    telegram_id: int,
    first_name: str | None = None,
    username: str | None = None,
    first_seen_at: datetime.datetime | None = None,
    last_message_at: datetime.datetime | None = None,
    crm_notes: str | None = None,
    crm_tags: str | None = None,
) -> int:
    """مشتری می‌سازه و شناسه‌اش رو برمی‌گردونه؛ زمان‌ها قابلِ کنترل ان."""
    async with session_scope() as session:
        customer = Customer(
            shop_bot_id=shop_bot_id,
            telegram_id=telegram_id,
            first_name=first_name,
            username=username,
            last_message_at=last_message_at,
            crm_notes=crm_notes,
            crm_tags=crm_tags,
        )
        if first_seen_at is not None:
            customer.first_seen_at = first_seen_at
        session.add(customer)
        await session.flush()
        return customer.id


async def add_order(
    shop_bot_id: int,
    customer_id: int,
    *,
    status: OrderStatus = OrderStatus.PENDING,
    value: int | None = 100_000,
    created_at: datetime.datetime | None = None,
    confirmed: bool | None = None,
    confirmed_at: datetime.datetime | None = None,
    discount: int | None = None,
    product_id: int | None = None,
    quantity: int | None = 1,
    campaign_id: int | None = None,
    group_id: str | None = None,
    bale_paid_at: datetime.datetime | None = None,
    summary: str = "سفارشِ تست",
    order_type: OrderType = OrderType.ORDER,
    phone: str | None = None,
    address: str | None = None,
) -> int:
    """سفارش می‌سازه. confirmed پیش‌فرض = (وضعیت جزو «موفق»ها باشه)؛ confirmed_at پیش‌فرضش = created_at."""
    if confirmed is None:
        confirmed = status in (OrderStatus.CONFIRMED, OrderStatus.PROCESSING, OrderStatus.SHIPPED, OrderStatus.COMPLETED)
    async with session_scope() as session:
        order = OrderConsultation(
            shop_bot_id=shop_bot_id,
            customer_id=customer_id,
            type=order_type,
            summary=summary,
            estimated_value_toman=value,
            product_id=product_id,
            quantity=quantity,
            customer_phone=phone,
            customer_address=address,
            confirmed=confirmed,
            status=status,
            campaign_id=campaign_id,
            discount_toman=discount,
            cart_checkout_group_id=group_id,
            bale_paid_at=bale_paid_at,
        )
        if created_at is not None:
            order.created_at = created_at
        if confirmed:
            order.confirmed_at = confirmed_at if confirmed_at is not None else (created_at or datetime.datetime.now(UTC))
        session.add(order)
        await session.flush()
        return order.id


async def wallet_transactions(reason: WalletTransactionReason | None = None) -> list[WalletTransaction]:
    async with session_scope() as session:
        query = select(WalletTransaction).order_by(WalletTransaction.id)
        if reason is not None:
            query = query.where(WalletTransaction.reason == reason)
        return list((await session.execute(query)).scalars().all())


async def owner_balance(owner_telegram_id: int) -> int:
    async with session_scope() as session:
        owner = (await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == owner_telegram_id))).scalar_one()
        return int(owner.wallet_balance_toman)
