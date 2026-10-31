from __future__ import annotations

import asyncio
import logging
import secrets
import time
import weakref

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.main_bot import texts as main_texts
from app.bots.shop_bot import cart_proposal_ui as proposal_ui
from app.bots.shop_bot import keyboards, texts
from app.config import settings
from app.database.models import AuditEventType, ModerationAction, OrderType, TenantMode, WalletTransactionReason
from app.database.session import session_scope
from app.services import (
    ai_context,
    ai_pool_service,
    ai_service,
    audit_log_service,
    bale_credentials_service,
    bale_service,
    bot_error_service,
    cart_edit_service,
    cart_proposal_service,
    cart_service,
    cart_suggest_service,
    channel_knowledge_service,
    conversation_service,
    customer_service,
    digital_service,
    knowledge_service,
    moderation_service,
    prompt_defaults,
    order_detection_service,
    order_service,
    product_service,
    payment_settings_service,
    shop_bot_service,
    shop_owner_service,
    wallet_service,
)
from app.bots.shop_bot.handlers import payments as payment_handlers
from app.bots.shop_bot.handlers import product_photos as product_photo_handlers
from app.services.admin_settings_service import get_admin_settings
from app.services.rate_limiter import rate_limiter

logger = logging.getLogger(__name__)

router = Router(name="shop_customer")

ORDER_DEDUP_WINDOW_MINUTES = 10

# چند پیامِ پشت‌سرهمِ مشتری رو با هم جمع می‌کنیم و یه‌جا پردازش می‌کنیم، تا اگه
# مشتری ۳ تا پیامِ جدا فرستاد، ربات ۳ بار جدا جواب نده (مثلاً ۳ بار سلام نکنه).
DEBOUNCE_SECONDS = float(shop_bot_service.DEFAULT_MESSAGE_BATCH_SECONDS)
MAX_BUFFER_WAIT_SECONDS = 10.0

_pending_buffers: dict[tuple[int, int], list[str]] = {}
_pending_tasks: dict[tuple[int, int], asyncio.Task] = {}
_pending_started_at: dict[tuple[int, int], float] = {}

# فازِ ۶-الف: برایِ هر (فروشگاه، مشتری) *فقط یه پردازش* هم‌زمان اجرا می‌شه. بدونِ این قفل، پیامی که وسطِ پردازشِ
# دسته‌یِ قبلی (فراخوانیِ AI چند ثانیه‌ای) می‌رسید یه چرخه‌یِ debounceِ جدا شروع می‌کرد و هم‌زمان با اولی
# جواب می‌داد («چند پیامِ پشتِ‌هم = چند جواب»). حالا پیام‌هایِ این فاصله جمع می‌شن و بعدِ اتمامِ پردازشِ قبلی
# با هم و با یه جواب پردازش می‌شن. (مثلِ _cart_edit_locks: WeakValueDictionary تا قفلِ بی‌استفاده پاک بشه.)
_customer_locks: "weakref.WeakValueDictionary[tuple[int, int], asyncio.Lock]" = weakref.WeakValueDictionary()


def _get_customer_lock(key: tuple[int, int]) -> asyncio.Lock:
    lock = _customer_locks.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _customer_locks[key] = lock
    return lock


def _batch_window(shop_bot) -> float:
    """مدتِ تجمیعِ پیام‌ها (ثانیه) برایِ این فروشگاه؛ تنظیمِ فروشگاه‌دار (۲..۶۰) یا پیش‌فرضِ سیستم."""
    seconds = getattr(shop_bot, "message_batch_seconds", None)
    if (
        isinstance(seconds, int)
        and shop_bot_service.MESSAGE_BATCH_MIN_SECONDS <= seconds <= shop_bot_service.MESSAGE_BATCH_MAX_SECONDS
    ):
        return float(seconds)
    return DEBOUNCE_SECONDS

# ویرایشِ سبد با AI: یه قفلِ درون‌پردازه‌ای به ازای هر (فروشگاه، مشتری)، تا دو دستورِ
# پشتِ‌سرهم که همزمان پردازش می‌شن («دوتا برنج اضافه کن» و بعدش «بکنش ۳ تا») همیشه به
# ترتیب اعمال بشن و دومی سبدِ commit‌شده‌ی اولی رو ببینه. WeakValueDictionary: قفلِ
# مشتری‌هایی که دیگه کاری ندارن خودبه‌خود از حافظه پاک می‌شه.
_cart_edit_locks: "weakref.WeakValueDictionary[tuple[int, int], asyncio.Lock]" = weakref.WeakValueDictionary()


def _is_consultation(shop_bot) -> bool:
    return shop_bot is not None and shop_bot.tenant_mode == TenantMode.CONSULTATION


def _menu_keyboard(shop_bot):
    return keyboards.customer_main_keyboard(shop_bot.tenant_mode if shop_bot else None, bool(shop_bot and shop_bot.support_enabled))


async def _stale_button_reply(message: Message, shop_bot) -> None:
    """دکمه‌یِ کهنه (برچسبِ مودِ دیگه/نسخه‌یِ قبل) ← پیامِ مودبانه + کیبوردِ مودِ جاری."""
    await message.answer(texts.STALE_BUTTON_REPLY, reply_markup=_menu_keyboard(shop_bot))


@router.message(CommandStart())
async def customer_start(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()  # اگه وسطِ چک‌اوتِ سبد بود، رها می‌شه (سبد دست‌نخورده می‌مونه)
    shop_bot = await shop_bot_service.get_by_bot_telegram_id(session, message.bot.id)
    if shop_bot is not None:
        await customer_service.get_or_create_customer(
            session, shop_bot.id, message.from_user.id, message.from_user.first_name, message.from_user.username,
            last_name=message.from_user.last_name,
        )
    welcome = texts.SHOP_WELCOME_CONSULTATION if _is_consultation(shop_bot) else texts.SHOP_WELCOME
    await message.answer(welcome, reply_markup=_menu_keyboard(shop_bot))


@router.message(Command("menu"))
async def customer_menu(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    shop_bot = await shop_bot_service.get_by_bot_telegram_id(session, message.bot.id)
    await message.answer(texts.MENU_REPLY, reply_markup=_menu_keyboard(shop_bot))


async def _check_access(message: Message, session: AsyncSession, shop_bot, main_bot: Bot) -> bool:
    """چک‌های مشترکِ همه‌ی انواعِ پیام (متن/عکس/صدا): حالتِ تعمیر + موجودیِ کیف‌پول + محدودیتِ نرخ."""
    admin_settings = await get_admin_settings(session)
    if admin_settings.maintenance_mode:
        await message.answer(texts.PLATFORM_MAINTENANCE_REPLY)
        return False

    owner = await shop_owner_service.get_by_id(session, shop_bot.shop_owner_id)
    if owner is None or owner.wallet_balance_toman <= 0:
        await message.answer(texts.SHOP_UNAVAILABLE)
        if owner is not None and await wallet_service.try_claim_empty_notification(session, owner):
            try:
                await main_bot.send_message(owner.telegram_id, main_texts.wallet_empty_notification())
            except TelegramAPIError:
                logger.exception("اطلاع‌رسانیِ اتمامِ کیف‌پول به فروشگاه‌دار %s ناموفق بود.", owner.telegram_id)
        return False

    if not rate_limiter.check_and_record(
        shop_bot.id, message.from_user.id, admin_settings.rate_limit_max_messages, admin_settings.rate_limit_window_seconds,
    ):
        await message.answer(texts.RATE_LIMITED)
        return False

    return True


async def _deduct_and_notify(
    session: AsyncSession, owner, admin_settings, amount_toman: int, reason: WalletTransactionReason, main_bot: Bot
) -> None:
    """بعدِ فراخوانیِ موفقِ هوش مصنوعی، هزینه رو از کیف‌پول کم می‌کنه و در صورتِ لزوم به فروشگاه‌دار خبر می‌ده.
    این تابع هیچ‌وقت به مشتری خطا نشون نمی‌ده؛ فقط خودِ فروشگاه‌دار (از طریقِ ربات اصلی) مطلع می‌شه."""
    success = await wallet_service.deduct(session, owner, amount_toman, reason)
    if not success:
        # موجودی در لحظه‌ی کسر کافی نبوده (مثلاً دقیقاً همین چند تومنِ آخر رو یه پیامِ هم‌زمانِ دیگه مصرف کرده).
        # چون جوابِ هوش مصنوعی از قبل تولید و برای مشتری فرستاده شده، این کمبودِ جزئی رو نادیده می‌گیریم
        # و اجازه نمی‌دیم تجربه‌ی مشتری خراب بشه؛ فقط لاگ می‌کنیم.
        logger.warning("کسرِ کیف‌پول برای فروشگاه‌دار %s ناموفق بود (موجودیِ ناکافی در لحظه‌ی کسر).", owner.id)

    if owner.wallet_balance_toman <= 0:
        if await wallet_service.try_claim_empty_notification(session, owner):
            try:
                await main_bot.send_message(owner.telegram_id, main_texts.wallet_empty_notification())
            except TelegramAPIError:
                logger.exception("اطلاع‌رسانیِ اتمامِ کیف‌پول به فروشگاه‌دار %s ناموفق بود.", owner.telegram_id)
    elif owner.wallet_balance_toman < admin_settings.wallet_low_balance_warning_toman:
        if await wallet_service.try_claim_low_balance_notification(session, owner):
            try:
                await main_bot.send_message(
                    owner.telegram_id, main_texts.wallet_low_balance_notification(owner.wallet_balance_toman)
                )
            except TelegramAPIError:
                logger.exception("اطلاع‌رسانیِ کمبودِ موجودیِ کیف‌پول به فروشگاه‌دار %s ناموفق بود.", owner.telegram_id)


def _split_checkout_questions(raw: str | None, digital_only: bool = False) -> list[str]:
    if raw and raw.strip():
        questions = [line.strip() for line in raw.splitlines() if line.strip()]
        if questions:
            return questions
    # P1-S3 (B2): سبدِ فقط‌دیجیتال آدرس لازم نداره (سوال‌هایِ سفارشیِ فروشگاه‌دار همون‌طور که هست می‌مونه)
    if digital_only:
        return ["شماره تماس"]
    return ["شماره تماس", "آدرس"]


async def _safe_edit(callback: CallbackQuery, text: str, reply_markup=None) -> None:
    """edit_text ـی که «message is not modified» رو بی‌صدا نادیده می‌گیره — یه
    دابل‌تپِ سریع (یا دو کلیکِ پشتِ‌هم رویِ یه دکمه‌ی کهنه) می‌تونه همون محتوای
    فعلی رو دوباره ویرایش کنه و تلگرام برایِ این حالت خطا می‌ده، که برایِ ما
    اصلاً خطا نیست."""
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            raise


async def _render_cart(session: AsyncSession, shop_bot_id: int, customer_id: int):
    cart = await cart_service.get_or_create_cart(session, shop_bot_id, customer_id)
    items = await cart_service.get_items_with_products(session, cart.id)
    return cart, items, texts.cart_summary(items), keyboards.cart_view_keyboard(items)


# =============================================================================
# سبدِ خریدِ واقعی (فازِ ۳) — مسیرِ جدا و اختیاری کنارِ چتِ آزادِ AI بالا (که
# دست‌نخورده می‌مونه). این هندلرها عمداً قبل از customer_messageِ کچ‌آل زیر
# اومدن — هم برایِ تطبیقِ دقیقِ متنِ دکمه‌ها، هم چون بدونِ این ترتیب، جواب‌هایِ
# مرحله‌ی چک‌اوت (CheckoutStates) به‌جایِ ثبت‌شدن، به‌عنوانِ چتِ AI تفسیر می‌شدن.
# =============================================================================
@router.message(F.text == texts.BTN_PRODUCTS)
async def cart_open_products(message: Message, session: AsyncSession) -> None:
    shop_bot = await shop_bot_service.get_by_bot_telegram_id(session, message.bot.id)
    if shop_bot is None:
        return
    if _is_consultation(shop_bot):
        await _stale_button_reply(message, shop_bot)
        return
    admin_settings = await get_admin_settings(session)
    if admin_settings.maintenance_mode:
        await message.answer(texts.PLATFORM_MAINTENANCE_REPLY)
        return

    products = await product_service.get_active_by_shop_bot(session, shop_bot.id)
    if not products:
        await message.answer(texts.NO_PRODUCTS_AVAILABLE)
        return
    await message.answer(texts.PRODUCTS_BROWSE_TITLE, reply_markup=keyboards.products_browse_keyboard(products))


@router.message(F.text == texts.BTN_CART)
async def cart_open_view(message: Message, session: AsyncSession) -> None:
    shop_bot = await shop_bot_service.get_by_bot_telegram_id(session, message.bot.id)
    if shop_bot is None:
        return
    if _is_consultation(shop_bot):
        await _stale_button_reply(message, shop_bot)
        return
    customer = await customer_service.get_or_create_customer(
        session, shop_bot.id, message.from_user.id, message.from_user.first_name, message.from_user.username,
        last_name=message.from_user.last_name,
    )
    _cart, items, text, keyboard = await _render_cart(session, shop_bot.id, customer.id)
    if items:
        text = f"{text}\n\n{texts.CART_AI_HINT}"
    await message.answer(text, reply_markup=keyboard)


@router.message(F.text == texts.BTN_SERVICES)
async def open_services(message: Message, session: AsyncSession) -> None:
    """مشاوره‌ای: فهرستِ فقط‌خواندنیِ خدمات/بسته‌ها (بدونِ سبد/خرید)."""
    shop_bot = await shop_bot_service.get_by_bot_telegram_id(session, message.bot.id)
    if shop_bot is None:
        return
    if not _is_consultation(shop_bot):
        await _stale_button_reply(message, shop_bot)
        return
    products = await product_service.get_active_by_shop_bot(session, shop_bot.id)
    await message.answer(texts.services_list_text(products) if products else texts.SERVICES_EMPTY)


@router.message(F.text == texts.BTN_SUPPORT)
async def open_support(message: Message, session: AsyncSession) -> None:
    """D1 (direct): تماسِ فروشگاه + دکمه‌یِ لینکِ t.me. فقط وقتی فروشگاه‌دار فعالش کرده (وگرنه پیامِ مودبانه)."""
    shop_bot = await shop_bot_service.get_by_bot_telegram_id(session, message.bot.id)
    if shop_bot is None:
        return
    if not shop_bot.support_enabled:
        await message.answer(texts.SUPPORT_UNAVAILABLE, reply_markup=_menu_keyboard(shop_bot))
        return
    await message.answer(texts.support_contact_text(shop_bot), reply_markup=keyboards.support_link_keyboard(shop_bot.support_contact_username))


@router.callback_query(F.data == "noop")
async def cart_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data.startswith("cart_browse:"))
async def cart_browse_page(callback: CallbackQuery, session: AsyncSession) -> None:
    shop_bot = await shop_bot_service.get_by_bot_telegram_id(session, callback.bot.id)
    await callback.answer()
    if shop_bot is None:
        return
    page = int(callback.data.split(":")[1])
    products = await product_service.get_active_by_shop_bot(session, shop_bot.id)
    if not products:
        await _safe_edit(callback, texts.NO_PRODUCTS_AVAILABLE)
        return
    await _safe_edit(callback, texts.PRODUCTS_BROWSE_TITLE, keyboards.products_browse_keyboard(products, page))


@router.callback_query(F.data.startswith("cart_add:"))
async def cart_add_product(callback: CallbackQuery, session: AsyncSession) -> None:
    shop_bot = await shop_bot_service.get_by_bot_telegram_id(session, callback.bot.id)
    if shop_bot is None:
        await callback.answer()
        return
    product_id = int(callback.data.split(":")[1])
    product = await product_service.get_owned_by_id(session, product_id, shop_bot.id)
    if product is None:
        await callback.answer(texts.CART_ITEM_NOT_FOUND, show_alert=True)
        return

    customer = await customer_service.get_or_create_customer(
        session, shop_bot.id, callback.from_user.id, callback.from_user.first_name, callback.from_user.username,
        last_name=callback.from_user.last_name,
    )
    cart = await cart_service.get_or_create_cart(session, shop_bot.id, customer.id)
    item, added = await cart_service.add_item(session, cart, product, quantity=1)

    if item is None:
        await callback.answer(texts.ITEM_OUT_OF_STOCK, show_alert=True)
        return
    if added == 0:
        await callback.answer(texts.ITEM_OUT_OF_STOCK, show_alert=True)
        return
    await callback.answer(texts.item_added_to_cart(product.name))


@router.callback_query(F.data == "cart_view")
async def cart_view_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    shop_bot = await shop_bot_service.get_by_bot_telegram_id(session, callback.bot.id)
    await callback.answer()
    if shop_bot is None:
        return
    customer = await customer_service.get_or_create_customer(
        session, shop_bot.id, callback.from_user.id, callback.from_user.first_name, callback.from_user.username,
        last_name=callback.from_user.last_name,
    )
    _cart, _items, text, keyboard = await _render_cart(session, shop_bot.id, customer.id)
    await _safe_edit(callback, text, keyboard)


async def _refresh_cart_message(callback: CallbackQuery, session: AsyncSession, shop_bot_id: int, customer_id: int) -> None:
    _cart, _items, text, keyboard = await _render_cart(session, shop_bot_id, customer_id)
    await _safe_edit(callback, text, keyboard)


@router.callback_query(F.data.startswith("cart_inc:"))
async def cart_increment(callback: CallbackQuery, session: AsyncSession) -> None:
    shop_bot = await shop_bot_service.get_by_bot_telegram_id(session, callback.bot.id)
    if shop_bot is None:
        await callback.answer()
        return
    customer = await customer_service.get_by_shop_bot_and_telegram_id(session, shop_bot.id, callback.from_user.id)
    cart = await cart_service.get_or_create_cart(session, shop_bot.id, customer.id) if customer else None
    item_id = int(callback.data.split(":")[1])
    cart_item = await cart_service.get_cart_item_owned(session, item_id, cart.id) if cart else None
    if cart_item is None:
        await callback.answer(texts.CART_ITEM_NOT_FOUND, show_alert=True)
        return

    product = await product_service.get_by_id(session, cart_item.product_id)
    cap = cart_service.available_stock(product) if product else None
    if cap is not None and cart_item.quantity >= cap:
        await callback.answer(texts.ITEM_OUT_OF_STOCK, show_alert=True)
        return

    await cart_service.set_quantity(session, cart_item, cart_item.quantity + 1)
    await callback.answer()
    await _refresh_cart_message(callback, session, shop_bot.id, customer.id)


@router.callback_query(F.data.startswith("cart_dec:"))
async def cart_decrement(callback: CallbackQuery, session: AsyncSession) -> None:
    shop_bot = await shop_bot_service.get_by_bot_telegram_id(session, callback.bot.id)
    if shop_bot is None:
        await callback.answer()
        return
    customer = await customer_service.get_by_shop_bot_and_telegram_id(session, shop_bot.id, callback.from_user.id)
    cart = await cart_service.get_or_create_cart(session, shop_bot.id, customer.id) if customer else None
    item_id = int(callback.data.split(":")[1])
    cart_item = await cart_service.get_cart_item_owned(session, item_id, cart.id) if cart else None
    if cart_item is None:
        await callback.answer(texts.CART_ITEM_NOT_FOUND, show_alert=True)
        return

    await cart_service.set_quantity(session, cart_item, cart_item.quantity - 1)
    await callback.answer()
    await _refresh_cart_message(callback, session, shop_bot.id, customer.id)


@router.callback_query(F.data.startswith("cart_remove:"))
async def cart_remove(callback: CallbackQuery, session: AsyncSession) -> None:
    shop_bot = await shop_bot_service.get_by_bot_telegram_id(session, callback.bot.id)
    if shop_bot is None:
        await callback.answer()
        return
    customer = await customer_service.get_by_shop_bot_and_telegram_id(session, shop_bot.id, callback.from_user.id)
    cart = await cart_service.get_or_create_cart(session, shop_bot.id, customer.id) if customer else None
    item_id = int(callback.data.split(":")[1])
    cart_item = await cart_service.get_cart_item_owned(session, item_id, cart.id) if cart else None
    if cart_item is None:
        await callback.answer(texts.CART_ITEM_NOT_FOUND, show_alert=True)
        return

    await cart_service.remove_item(session, cart_item)
    await callback.answer()
    await _refresh_cart_message(callback, session, shop_bot.id, customer.id)


@router.callback_query(F.data.startswith("cart_ai_clear:"))
async def cart_ai_clear_confirm(callback: CallbackQuery, session: AsyncSession) -> None:
    shop_bot = await shop_bot_service.get_by_bot_telegram_id(session, callback.bot.id)
    if shop_bot is None:
        await callback.answer()
        return
    customer = await customer_service.get_by_shop_bot_and_telegram_id(session, shop_bot.id, callback.from_user.id)
    cart = await cart_service.get_cart(session, shop_bot.id, customer.id) if customer else None
    items = await cart_service.get_items_with_products(session, cart.id) if cart else []
    if not items:
        await callback.answer(texts.CART_EMPTY, show_alert=True)
        return

    expected_fingerprint = callback.data.split(":", 1)[1]
    if cart_service.cart_fingerprint(items) != expected_fingerprint:
        # سبد از لحظه‌ی نمایشِ این دکمه عوض شده؛ سبدِ تازه رو بدونِ اجازه‌ی صریح پاک نمی‌کنیم.
        await callback.answer(texts.CART_AI_CLEAR_STALE, show_alert=True)
        return

    await cart_service.clear_cart(session, cart.id)
    await callback.answer()
    await callback.message.edit_text(texts.CART_AI_CLEARED)


@router.callback_query(F.data == "cart_ai_keep")
async def cart_ai_keep(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.edit_text(texts.CART_AI_KEPT)


# چک‌اوتِ سبد (مرحله‌ای: نام ← موبایل ← آدرس ← ارسال ← سوال‌ها ← پیش‌نمایش) به handlers/checkout.py منتقل شد (W5/C3).


@router.message(F.text)
async def customer_message(message: Message, session: AsyncSession, main_bot: Bot) -> None:
    shop_bot = await shop_bot_service.get_by_bot_telegram_id(session, message.bot.id)
    if shop_bot is None:
        return
    if not await _check_access(message, session, shop_bot, main_bot):
        return

    customer = await customer_service.get_or_create_customer(
        session, shop_bot.id, message.from_user.id, message.from_user.first_name, message.from_user.username,
        last_name=message.from_user.last_name,
    )
    if await product_photo_handlers.maybe_handle_photo_request(message, session, shop_bot, main_bot):  # W5: «عکسِ X رو بفرست»
        return
    if await payment_handlers.maybe_handle_payment_claim(message, session, shop_bot, customer):
        return

    _schedule_debounced_processing(
        shop_bot.id, message.from_user.id, message.text, message.bot, main_bot, window=_batch_window(shop_bot)
    )


def _schedule_debounced_processing(
    shop_bot_id: int, customer_tg_id: int, text: str, shop_bot_instance: Bot, main_bot: Bot, window: float | None = None
) -> None:
    key = (shop_bot_id, customer_tg_id)
    window = DEBOUNCE_SECONDS if window is None else window
    _pending_buffers.setdefault(key, []).append(text)

    now = time.monotonic()
    started_at = _pending_started_at.setdefault(key, now)

    existing_task = _pending_tasks.get(key)
    if existing_task is not None and not existing_task.done():
        existing_task.cancel()

    # سقفِ کلِ انتظار با بزرگ‌شدنِ پنجره بزرگ می‌شه (وگرنه پنجره‌یِ ۱۵ ثانیه‌ای با سقفِ ۱۰ ثانیه بی‌اثر بود).
    max_wait = max(MAX_BUFFER_WAIT_SECONDS, window * 3)
    elapsed = now - started_at
    delay = min(window, max(0.3, max_wait - elapsed))

    task = asyncio.create_task(_wait_then_process(key, delay, shop_bot_instance, main_bot))
    _pending_tasks[key] = task


async def _sleep_with_typing(bot: Bot, chat_id: int, delay: float) -> None:
    """E2: حینِ انتظارِ تجمیع هر ~۴ ثانیه «typing…» می‌فرسته تا مشتری فکر نکنه ربات گیر کرده (بهترین‌تلاش؛ خطا نادیده).
    پنجره‌هایِ کوتاه (<۲ثانیه) بدونِ typing می‌خوابن."""
    if delay < 2.0:
        await asyncio.sleep(delay)
        return
    loop = asyncio.get_running_loop()
    end = loop.time() + delay
    while True:
        remaining = end - loop.time()
        if remaining <= 0:
            return
        try:
            await bot.send_chat_action(chat_id, "typing")
        except Exception:  # noqa: BLE001 — فقط یه نشانه‌یِ ظاهریه
            logger.debug("ارسالِ typing ناموفق بود.", exc_info=True)
        await asyncio.sleep(min(4.0, remaining))


async def _wait_then_process(key: tuple[int, int], delay: float, shop_bot_instance: Bot, main_bot: Bot) -> None:
    try:
        await _sleep_with_typing(shop_bot_instance, key[1], delay)  # key = (shop_bot_id, customer_tg_id)
        # اگه پردازشِ قبلیِ همین مشتری هنوز در جریانه، اینجا منتظر می‌مونیم. اگه وسطِ انتظار پیامِ تازه برسه، این تسک
        # لغو می‌شه و تسکِ جدید (با پنجره‌یِ از اول) مسئولیت رو می‌گیره؛ پس همه‌یِ پیام‌هایِ این فاصله یه‌جا جمع می‌شن.
        async with _get_customer_lock(key):
            messages = _pending_buffers.pop(key, [])
            _pending_started_at.pop(key, None)
            if _pending_tasks.get(key) is asyncio.current_task():
                _pending_tasks.pop(key, None)  # از اینجا به بعد پیامِ تازه نباید این تسکِ در حالِ پردازش رو لغو کنه
            if not messages:
                return

            combined_text = "\n".join(messages)
            shop_bot_id, customer_tg_id = key
            try:
                async with session_scope() as session:
                    await _generate_and_send_reply(session, shop_bot_id, customer_tg_id, combined_text, shop_bot_instance, main_bot)
            except Exception:
                logger.exception("پردازشِ پیام‌هایِ جمع‌شده‌یِ مشتری %s در فروشگاه %s با خطا مواجه شد.", customer_tg_id, shop_bot_id)
    except asyncio.CancelledError:
        return  # یه پیامِ تازه رسید و این تسک لغو شد؛ تسکِ جدید مسئولیت رو به عهده گرفته


async def _generate_and_send_reply(
    session: AsyncSession, shop_bot_id: int, customer_tg_id: int, combined_text: str, shop_bot_instance: Bot, main_bot: Bot
) -> None:
    shop_bot = await shop_bot_service.get_by_id(session, shop_bot_id)
    if shop_bot is None or not shop_bot.is_active:
        return

    admin_settings = await get_admin_settings(session)

    matched_rule = await moderation_service.check_text(session, combined_text)
    if matched_rule is not None and matched_rule.action != ModerationAction.WARN:
        await audit_log_service.log(
            session,
            AuditEventType.MODERATION_MATCH,
            shop_bot_id=shop_bot_id,
            actor_telegram_id=customer_tg_id,
            details=f"الگو: {matched_rule.pattern} | اکشن: {matched_rule.action} | دسته: {matched_rule.category or '-'}",
        )
        await shop_bot_instance.send_message(customer_tg_id, texts.MODERATION_BLOCKED_REPLY)
        if matched_rule.action == ModerationAction.REVIEW:
            owner_for_review = await shop_owner_service.get_by_id(session, shop_bot.shop_owner_id)
            if owner_for_review is not None:
                try:
                    await main_bot.send_message(
                        owner_for_review.telegram_id, main_texts.moderation_review_notification(matched_rule.category)
                    )
                except TelegramAPIError:
                    logger.exception("اطلاع‌رسانیِ نیازِ بازبینیِ محتوا به فروشگاه‌دار %s ناموفق بود.", owner_for_review.telegram_id)
        return
    if matched_rule is not None:
        # WARN: فقط ثبت می‌شه، مکالمه به‌طورِ عادی ادامه پیدا می‌کنه.
        await audit_log_service.log(
            session,
            AuditEventType.MODERATION_MATCH,
            shop_bot_id=shop_bot_id,
            actor_telegram_id=customer_tg_id,
            details=f"الگو: {matched_rule.pattern} | اکشن: warn | دسته: {matched_rule.category or '-'}",
        )

    customer = await customer_service.get_or_create_customer(session, shop_bot_id, customer_tg_id, None, None)
    owner = await shop_owner_service.get_by_id(session, shop_bot.shop_owner_id)

    if owner is None or owner.wallet_balance_toman <= 0:
        # موجودیِ کیف‌پول توی فاصله‌ی جمع‌آوریِ پیام‌ها (debounce) به صفر رسیده؛
        # از فراخوانیِ هوش مصنوعی صرف‌نظر می‌کنیم تا هزینه‌ی بی‌فایده به فروشگاه‌دار تحمیل نشه.
        await shop_bot_instance.send_message(customer_tg_id, texts.SHOP_UNAVAILABLE)
        return

    if not admin_settings.ai_api_key:
        logger.warning("کلید API هوش مصنوعی هنوز تنظیم نشده؛ پاسخ‌گویی به مشتری ممکن نیست.")
        await shop_bot_instance.send_message(customer_tg_id, texts.AI_ERROR_REPLY)
        await bot_error_service.log_error(session, shop_bot_id)
        return

    products = await product_service.get_active_by_shop_bot(session, shop_bot_id)
    knowledge = await channel_knowledge_service.get_recent_knowledge(session, shop_bot_id, admin_settings.knowledge_items_limit)
    # فازِ ۴: پرسش‌وپاسخ‌هایِ تاییدشده‌ی فروشگاه‌دار (حداکثر ۲۰ مورد) + دستورِ تشخیصِ خلأ (فقط
    # وقتی کلیدِ سراسریِ ادمین روشنه). بدونِ مورد/با کلیدِ خاموش، پرامپت دقیقاً مثلِ قبله.
    learned_answers = await knowledge_service.get_active_for_prompt(session, shop_bot_id)
    system_prompt = ai_context.build_system_prompt(
        shop_bot,
        products,
        knowledge,
        prompt_defaults.resolve_global_prompt(admin_settings, shop_bot.tenant_mode),
        learned_answers=learned_answers,
        gap_detection=admin_settings.knowledge_gap_enabled,
        bot_tools=prompt_defaults.build_bot_tools(shop_bot.tenant_mode, bool(shop_bot.support_enabled), texts),
    )
    history = await conversation_service.get_recent_history(session, customer.id, admin_settings.conversation_history_limit)

    ai = await ai_pool_service.build_ai_service(session, admin_settings, "chat")
    if ai is None:
        logger.error("هیچ کلیدِ AI‌ای (نه استخر، نه تنظیماتِ قدیمی) برای فروشگاه %s تنظیم نشده.", shop_bot_id)
        await shop_bot_instance.send_message(customer_tg_id, texts.AI_ERROR_REPLY)
        return

    # ویرایشِ سبد با AI (فازِ ۳): فقط وقتی فعال می‌شه که مشتری سبدِ غیرخالی داشته باشه یا
    # صراحتاً از «سبد» حرف زده باشه؛ در غیرِ این صورت (و همچنین وقتی پیام دستورِ سبد
    # نبود) همین خطِ چتِ عادیِ زیر بدونِ هیچ تغییری اجرا می‌شه.
    if await _maybe_handle_cart_edit(
        session, shop_bot, customer, owner, admin_settings, ai, products, combined_text, shop_bot_instance, main_bot
    ):
        return

    try:
        await session.commit()  # آزاد کردنِ اتصالِ دیتابیس قبل از انتظارِ AI (ظرفیت؛ فازِ ۶-الف)
        ai_result = await ai.get_reply(system_prompt, history, combined_text)
    except ai_service.AiServiceError:
        logger.exception("فراخوانیِ هوش مصنوعی برای مشتری %s در فروشگاه %s ناموفق بود.", customer_tg_id, shop_bot_id)
        await shop_bot_instance.send_message(customer_tg_id, texts.AI_ERROR_REPLY)
        await bot_error_service.log_error(session, shop_bot_id)
        return
    # نشانه‌یِ خلأِ دانش *قبل از* ذخیره و ارسال حذف می‌شه (وگرنه به مشتری می‌رسید و توی تاریخچه
    # می‌رفت و AI تقلیدش می‌کرد). حذف همیشه انجام می‌شه؛ ثبتِ سوال فقط وقتی کلید روشنه.
    reply, gap_flagged = knowledge_service.strip_gap_marker(ai_result.text)
    if not reply:
        reply = texts.GAP_FALLBACK_REPLY

    await conversation_service.save_turn(session, customer.id, combined_text, reply)
    if gap_flagged and admin_settings.knowledge_gap_enabled:
        await knowledge_service.record_gap(session, shop_bot_id, combined_text)
    suggest_markup = None
    if not _is_consultation(shop_bot):
        suggested = cart_suggest_service.suggest_cart_products(reply, products)
        if suggested:
            cart = await cart_service.get_cart(session, shop_bot.id, customer.id)
            cart_items = await cart_service.get_items_with_products(session, cart.id) if cart else []
            suggest_markup = keyboards.cart_suggest_keyboard(suggested, show_cart_row=bool(cart_items))
    await shop_bot_instance.send_message(customer_tg_id, reply, reply_markup=suggest_markup)

    cost = wallet_service.estimate_chat_cost(admin_settings, ai_result.total_tokens)
    await _deduct_and_notify(session, owner, admin_settings, cost, WalletTransactionReason.CHAT_MESSAGE, main_bot)

    full_history = history + [{"role": "user", "content": combined_text}, {"role": "assistant", "content": reply}]
    asyncio.create_task(_detect_and_notify_order(shop_bot_id, customer.id, full_history, shop_bot_instance, main_bot))


def _get_cart_edit_lock(key: tuple[int, int]) -> asyncio.Lock:
    lock = _cart_edit_locks.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _cart_edit_locks[key] = lock
    return lock


async def _maybe_handle_cart_edit(
    session: AsyncSession,
    shop_bot,
    customer,
    owner,
    admin_settings,
    ai,
    products: list,
    combined_text: str,
    shop_bot_instance: Bot,
    main_bot: Bot,
) -> bool:
    """
    ویرایشِ سبدِ خرید با زبانِ طبیعی (فازِ ۳، زیربخشِ ۴). True یعنی این پیام یه دستورِ سبد
    بود و کاملاً همین‌جا جواب داده شد (چتِ عادی و تشخیصِ سفارشِ بعدیش اجرا نمی‌شن)؛
    False یعنی «مالِ من نیست» و پیام باید مثلِ همیشه توسطِ چتِ عادی پردازش بشه.

    ترتیب عمداً اینه: اول تحلیلِ دستورِ سبد، بعد (فقط اگه دستور نبود) چتِ عادی. اگه
    برعکس بود، چتِ عادی (که از سبد خبر نداره) ممکن بود بگه «باشه، حذفش کردم» بدونِ اینکه
    چیزی واقعاً عوض شده باشه.

    هزینه‌ی کنترل‌شده: کلاسیفایر فقط وقتی صدا زده می‌شه که مشتری سبدِ غیرخالی داره یا
    کلمه‌ی «سبد» رو گفته؛ مشتری‌ای که اصلاً از سبد استفاده نمی‌کنه هیچ هزینه‌ی اضافه‌ای نداره.

    تغییرِ سبد *قبل* از فرستادنِ پیام commit می‌شه (و توی همون قفلِ per-customer) تا
    پیامِ بعدیِ همون مشتری همیشه سبدِ قطعی‌شده رو ببینه. خروجیِ AI هیچ‌وقت مستقیم اعمال
    نمی‌شه؛ cart_edit_service شناسه‌ها/تعدادها رو اعتبارسنجی می‌کنه.
    """
    async with _get_cart_edit_lock((shop_bot.id, customer.id)):
        cart = await cart_service.get_cart(session, shop_bot.id, customer.id)
        items = await cart_service.get_items_with_products(session, cart.id) if cart else []
        if not items and not cart_edit_service.mentions_cart(combined_text):
            return False

        # تاریخچه بعد از گرفتنِ قفل خونده می‌شه تا دستورِ قبلیِ همین مشتری (که ممکنه همین
        # الان commit شده باشه) هم توش باشه.
        history = await conversation_service.get_recent_history(session, customer.id, cart_edit_service.CLASSIFIER_HISTORY_LIMIT)
        is_consultation = shop_bot.tenant_mode == TenantMode.CONSULTATION
        await session.commit()  # آزاد کردنِ اتصالِ دیتابیس قبل از انتظارِ AI (ظرفیت؛ commit باید در فراخوان باشه چون سرویس session نداره)
        result, tokens_used = await cart_edit_service.classify(ai, history, combined_text, products, items, is_consultation)

        if tokens_used is not None:
            cost = wallet_service.estimate_cart_edit_cost(admin_settings, tokens_used)
            await _deduct_and_notify(session, owner, admin_settings, cost, WalletTransactionReason.CART_EDIT, main_bot)

        if result is None:
            return False

        keyboard = None
        if result.status == "show_cart":
            reply = texts.cart_summary(items)
            keyboard = keyboards.cart_view_keyboard(items)
        elif result.status == "unsure":
            reply = result.clarifying_question or texts.CART_AI_CLARIFY_GENERIC
        elif result.wants_clear:
            # خالی‌کردنِ کلِ سبد مخرب‌ترین عملیاته؛ هیچ‌وقت مستقیم از روی خروجیِ AI اعمال
            # نمی‌شه و اول یه تاییدِ دکمه‌ای از خودِ مشتری لازمه (بقیه‌ی عملیاتِ همون پیام
            # عمداً نادیده گرفته می‌شن؛ مشتری بعد از تایید می‌تونه دوباره بگه).
            if items:
                reply = f"{texts.CART_AI_CLEAR_PROMPT}\n\n{texts.cart_summary(items)}"
                keyboard = keyboards.cart_ai_clear_confirm_keyboard(cart_service.cart_fingerprint(items))
            else:
                reply = texts.CART_EMPTY
                keyboard = keyboards.cart_view_keyboard([])
        else:
            # W5/C2: AI فقط پیشنهاد می‌ده؛ تغییر با دکمه‌یِ «✅ اعمال» (یک‌بارمصرف، ۱۰ دقیقه، با اثرانگشتِ سبد) انجام می‌شه.
            applicable = [op for op in result.operations if op.action != "clear" and op.product_id is not None]
            if applicable:
                if cart is None:
                    cart = await cart_service.get_or_create_cart(session, shop_bot.id, customer.id)
                names = {product.id: product.name for product in products}
                names.update({product.id: product.name for _item, product in items})
                lines = [cart_proposal_service.describe_op(op, names.get(op.product_id, "؟")) for op in applicable]
                proposal = await cart_proposal_service.create(session, cart.id, applicable, cart_service.cart_fingerprint(items))
                reply = proposal_ui.proposal_text(lines, result.rejected_count)
                keyboard = proposal_ui.proposal_keyboard(proposal.id)
            else:
                reply = texts.CART_AI_CLARIFY_GENERIC

        await conversation_service.save_turn(session, customer.id, combined_text, reply)
        await session.commit()

        try:
            await shop_bot_instance.send_message(customer.telegram_id, reply, reply_markup=keyboard)
        except TelegramAPIError:
            # تغییرِ سبد از قبل commit شده؛ مشتری با دکمه‌ی «🛒 سبدِ خرید» وضعیتِ واقعی رو می‌بینه.
            logger.exception("فرستادنِ پاسخِ ویرایشِ سبد به مشتری %s ناموفق بود.", customer.telegram_id)
        return True


@router.message(F.photo)
async def customer_photo(message: Message, session: AsyncSession, main_bot: Bot) -> None:
    shop_bot = await shop_bot_service.get_by_bot_telegram_id(session, message.bot.id)
    if shop_bot is None:
        return
    if not await _check_access(message, session, shop_bot, main_bot):
        return

    await customer_service.get_or_create_customer(
        session, shop_bot.id, message.from_user.id, message.from_user.first_name, message.from_user.username,
        last_name=message.from_user.last_name,
    )
    owner = await shop_owner_service.get_by_id(session, shop_bot.shop_owner_id)
    admin_settings = await get_admin_settings(session)

    customer_name = message.from_user.first_name or (f"@{message.from_user.username}" if message.from_user.username else str(message.from_user.id))
    caption_note = f"\n\nمتنِ همراهِ عکس: {message.caption}" if message.caption else ""

    # نکته‌ی مهم: file_id عکس فقط برای بات‌اینستنسِ *همون* رباتی معتبره که عکس رو
    # دریافت کرده (اینجا ربات فروشگاهی). برای فرستادنِ همون عکس به فروشگاه‌دار از
    # طریقِ ربات اصلی (main_bot)، اول باید بایت‌های عکس رو با ربات فروشگاهی دانلود
    # کنیم و بعد به‌عنوانِ یه فایلِ تازه (BufferedInputFile) با main_bot آپلودش کنیم؛
    # همون file_id رو مستقیم به main_bot دادن کار نمی‌کنه.
    image_bytes: bytes | None = None
    try:
        file_io = await message.bot.download(message.photo[-1].file_id)
        image_bytes = file_io.read()
    except Exception:
        logger.exception("دانلودِ عکسِ مشتری %s ناموفق بود.", message.from_user.id)

    analysis_note = ""
    if image_bytes is not None and owner is not None and owner.wallet_balance_toman > 0:
        try:
            ai = await ai_pool_service.build_ai_service(session, admin_settings, "vision")
            if ai is None:
                raise ai_service.AiServiceError("هیچ کلیدِ AI‌ای با قابلیتِ vision تنظیم نشده.")
            await session.commit()  # آزاد کردنِ اتصالِ دیتابیس قبل از انتظارِ AI (ظرفیت؛ فازِ ۶-الف)
            image_analysis_result = await ai.analyze_image(texts.RECEIPT_ANALYSIS_PROMPT, image_bytes)
            analysis_note = f"\n\n🔎 بررسیِ خودکارِ تصویر:\n{image_analysis_result.text}"
            cost = wallet_service.estimate_photo_cost(admin_settings)
            await _deduct_and_notify(session, owner, admin_settings, cost, WalletTransactionReason.PHOTO_ANALYSIS, main_bot)
        except ai_service.AiServiceError:
            logger.exception("بررسیِ هوشمندِ تصویرِ ارسالی توسطِ مشتری %s ناموفق بود.", message.from_user.id)
        except Exception:
            logger.exception("تحلیلِ عکسِ مشتری %s ناموفق بود.", message.from_user.id)

    if image_bytes is not None:
        try:
            await main_bot.send_photo(
                owner.telegram_id,
                BufferedInputFile(image_bytes, filename="customer_photo.jpg"),
                caption=texts.customer_photo_forward_caption(customer_name, caption_note, analysis_note),
            )
        except TelegramAPIError:
            logger.exception("فوروارد کردنِ عکسِ مشتری به فروشگاه‌دار %s ناموفق بود.", owner.telegram_id)

    await message.answer(texts.PHOTO_RECEIVED_ACK)


@router.message(F.voice)
async def customer_voice(message: Message, session: AsyncSession, main_bot: Bot) -> None:
    shop_bot = await shop_bot_service.get_by_bot_telegram_id(session, message.bot.id)
    if shop_bot is None:
        return
    if not await _check_access(message, session, shop_bot, main_bot):
        return

    await customer_service.get_or_create_customer(
        session, shop_bot.id, message.from_user.id, message.from_user.first_name, message.from_user.username,
        last_name=message.from_user.last_name,
    )

    admin_settings = await get_admin_settings(session)
    owner = await shop_owner_service.get_by_id(session, shop_bot.shop_owner_id)
    if owner is None or owner.wallet_balance_toman <= 0:
        await message.answer(texts.SHOP_UNAVAILABLE)
        return

    ai = await ai_pool_service.build_ai_service(session, admin_settings, "chat")
    if ai is None:
        await message.answer(texts.AI_ERROR_REPLY)
        return

    try:
        file_io = await message.bot.download(message.voice.file_id)
        audio_bytes = file_io.read()
        await session.commit()  # آزاد کردنِ اتصالِ دیتابیس قبل از انتظارِ AI (ظرفیت؛ فازِ ۶-الف)
        transcript = await ai.transcribe_audio(audio_bytes, filename="voice.ogg")
    except ai_service.AiServiceError:
        logger.exception("رونویسیِ پیامِ صوتیِ مشتری %s ناموفق بود.", message.from_user.id)
        await message.answer(texts.VOICE_TRANSCRIBE_ERROR)
        return
    except Exception:
        logger.exception("دانلودِ پیامِ صوتیِ مشتری %s ناموفق بود.", message.from_user.id)
        await message.answer(texts.VOICE_TRANSCRIBE_ERROR)
        return

    transcript = transcript.strip()
    if not transcript:
        await message.answer(texts.VOICE_TRANSCRIBE_ERROR)
        return

    cost = wallet_service.estimate_voice_cost(admin_settings)
    await _deduct_and_notify(session, owner, admin_settings, cost, WalletTransactionReason.VOICE_TRANSCRIPTION, main_bot)

    _schedule_debounced_processing(
        shop_bot.id, message.from_user.id, transcript, message.bot, main_bot, window=_batch_window(shop_bot)
    )


async def _detect_and_notify_order(
    shop_bot_id: int,
    customer_id: int,
    full_history: list[dict[str, str]],
    shop_bot_instance: Bot,
    main_bot: Bot,
) -> None:
    """
    بازطراحیِ سفارش‌گیری: قبلاً این تابع (اگه کلاسیفایر «completed» تشخیص
    می‌داد) مستقیم سفارش رو می‌ساخت و فقط به فروشگاه‌دار خبر می‌داد — مشتری
    هیچ‌وقت نمی‌دید چی ثبت شده. حالا سه حالت داره:
      - هیچی (status=None): مثلِ قبل، کاری انجام نمی‌شه.
      - "unsure": حدس نمی‌زنیم؛ سوالِ روشن‌کننده‌ی خودِ هوش مصنوعی مستقیم به
        مشتری فرستاده می‌شه (و توی تاریخچه‌ی مکالمه ذخیره می‌شه تا دفعه‌ی بعد
        بدونه قبلاً پرسیده)، بدونِ ساختنِ هیچ سفارشی.
      - "completed": یه سفارش/مشاوره‌ی *کاندید* (AWAITING_CUSTOMER_CONFIRMATION)
        ساخته می‌شه و یه پیامِ تاییدِ صریح (خلاصه + فیلدهای ساختاریافته‌ی
        تلفن/آدرس + دکمه‌ی تایید/رد) به خودِ مشتری فرستاده می‌شه. فروشگاه‌دار
        فقط *بعدِ* تاییدِ واقعیِ مشتری خبردار می‌شه (توی cb_customer_confirm_order).
    """
    try:
        async with session_scope() as session:
            shop_bot = await shop_bot_service.get_by_id(session, shop_bot_id)
            if shop_bot is None:
                return
            if not shop_bot.legacy_ai_order_detection:
                # C2: AI راهنماست، ثبت‌کننده نیست؛ سفارش فقط از مسیرِ سبد ← چک‌اوت. هزینه‌یِ ORDER_DETECTION صفر.
                return
            owner = await shop_owner_service.get_by_id(session, shop_bot.shop_owner_id)
            if owner is None or owner.wallet_balance_toman <= 0:
                # موجودی خالیه؛ از فراخوانیِ کلاسیفایر (که خودش هزینه داره) صرف‌نظر می‌کنیم.
                # مشتری همین الان جوابِ اصلیِ چت رو گرفته، این فقط یه قابلیتِ جانبیِ تشخیصِ سفارشه.
                return

            admin_settings = await get_admin_settings(session)
            products = await product_service.get_active_by_shop_bot(session, shop_bot_id)

            ai = await ai_pool_service.build_ai_service(session, admin_settings, "chat")
            if ai is None:
                return
            is_consultation = shop_bot.tenant_mode == TenantMode.CONSULTATION
            await session.commit()  # آزاد کردنِ اتصالِ دیتابیس قبل از انتظارِ AI (commit در فراخوانه؛ سرویس session نداره)
            result, tokens_used = await order_detection_service.detect_order(ai, full_history, products, is_consultation)

            if tokens_used is not None:
                cost = wallet_service.estimate_order_detection_cost(admin_settings, tokens_used)
                await _deduct_and_notify(session, owner, admin_settings, cost, WalletTransactionReason.ORDER_DETECTION, main_bot)

            if result is None:
                return

            customer = await customer_service.get_by_id(session, customer_id)
            if customer is None:
                return

            if result["status"] == "unsure":
                question = result["clarifying_question"]
                try:
                    await shop_bot_instance.send_message(customer.telegram_id, question)
                    # توی تاریخچه هم ذخیره می‌شه تا فراخوانیِ بعدیِ کلاسیفایر (که کلِ
                    # تاریخچه رو می‌بینه) بفهمه این سوال قبلاً پرسیده شده، و دوباره
                    # unsureِ تکراری برنگردونه.
                    await conversation_service.save_turn(session, customer_id, "", question)
                except TelegramAPIError:
                    logger.exception("فرستادنِ سوالِ روشن‌کننده به مشتری %s ناموفق بود.", customer.telegram_id)
                return

            # از اینجا به بعد: result["status"] == "completed"
            recent = await order_service.get_recent_duplicate(
                session, customer_id, result["type"], result.get("product_id"), minutes=ORDER_DEDUP_WINDOW_MINUTES
            )
            if recent is not None:
                # یا همین الان یه کاندیدِ حل‌نشده برای همین محصول/نوع داریم (پس دوباره
                # مزاحمِ مشتری نمی‌شیم)، یا یه سفارشِ قبلاً حل‌شده برای همینه.
                return

            order = await order_service.create_order_awaiting_confirmation(
                session,
                shop_bot_id,
                customer_id,
                result["type"],
                result["summary"],
                result["estimated_value_toman"],
                result.get("product_id"),
                result.get("quantity"),
                result.get("customer_phone"),
                result.get("customer_address"),
            )

            try:
                await shop_bot_instance.send_message(
                    customer.telegram_id,
                    texts.order_confirmation_prompt(order),
                    reply_markup=keyboards.order_customer_confirmation_keyboard(order.id),
                )
            except TelegramAPIError:
                logger.exception("فرستادنِ پیامِ تاییدِ سفارش به مشتری %s ناموفق بود.", customer.telegram_id)
    except Exception:
        logger.exception("تسکِ پس‌زمینه‌ی تشخیصِ سفارش/مشاوره با خطا مواجه شد.")


async def _resolve_awaiting_order_for_callback(callback: CallbackQuery, session: AsyncSession):
    """کمک‌کننده‌ی مشترکِ دو هندلرِ زیر: shop_bot و customer و سفارشِ کاندید رو
    از روی callback.bot.id/callback.from_user.id/callback.data پیدا می‌کنه، و
    مالکیت رو چک می‌کنه. اگه هرجا namatch بود، None برمی‌گردونه (و خودش پیامِ
    «دیگه معتبر نیست» رو جواب می‌ده) — فراخوان فقط کافیه چک کنه None هست یا نه."""
    shop_bot = await shop_bot_service.get_by_bot_telegram_id(session, callback.bot.id)
    if shop_bot is None:
        await callback.answer(texts.ORDER_CONFIRMATION_NO_LONGER_VALID, show_alert=True)
        return None

    customer = await customer_service.get_by_shop_bot_and_telegram_id(session, shop_bot.id, callback.from_user.id)
    if customer is None:
        await callback.answer(texts.ORDER_CONFIRMATION_NO_LONGER_VALID, show_alert=True)
        return None

    order_id = int(callback.data.split(":")[1])
    order = await order_service.get_awaiting_confirmation_for_customer(session, order_id, customer.id)
    if order is None:
        # یا شناسه‌ی جعلی/حدسی بوده (مالِ یه مشتریِ دیگه)، یا این کاندید از قبل
        # تایید/لغو/منقضی شده (مثلاً کاربر روی یه پیامِ قدیمی دوباره زده).
        await callback.answer(texts.ORDER_CONFIRMATION_NO_LONGER_VALID, show_alert=True)
        return None

    return shop_bot, customer, order


@router.callback_query(F.data.startswith("dl_again:"))
async def cb_digital_download_again(callback: CallbackQuery, session: AsyncSession, main_bot: Bot) -> None:
    """«📥 دریافتِ دوباره»ِ محصولِ دیجیتال: فقط سفارشِ خودِ مشتری، بعد از تحویلِ اول، تا سقفِ digital_max_downloads."""
    shop_bot = await shop_bot_service.get_by_bot_telegram_id(session, callback.bot.id)
    if shop_bot is None:
        await callback.answer()
        return
    customer = await customer_service.get_by_shop_bot_and_telegram_id(session, shop_bot.id, callback.from_user.id)
    try:
        order_id = int(callback.data.split(":", 1)[1])
    except ValueError:
        order_id = 0
    if customer is None or order_id <= 0:
        await callback.answer(texts.DL_AGAIN_NOT_FOUND, show_alert=True)
        return

    result = await digital_service.prepare_redelivery(session, order_id, customer.id)
    if result.status == "not_found":
        await callback.answer(texts.DL_AGAIN_NOT_FOUND, show_alert=True)
        return
    if result.status == "not_delivered":
        await callback.answer(texts.DL_AGAIN_NOT_READY, show_alert=True)
        return
    if result.status == "limit":
        await callback.answer(texts.DL_AGAIN_LIMIT, show_alert=True)
        return

    await session.commit()  # اول شمارنده ثبت می‌شه، بعد ارسال
    await callback.answer()
    ok, new_file_id = await digital_service.send_delivery(
        callback.bot, main_bot, callback.from_user.id, result.product, result.codes, result.order_id, result.download_count, again=True
    )
    if new_file_id:
        result.product.digital_file_shop_file_id = new_file_id
    if not ok:
        await callback.message.answer(texts.DL_AGAIN_FAILED)


@router.callback_query(F.data.startswith("cust_confirm_order:"))
async def cb_customer_confirm_order(callback: CallbackQuery, session: AsyncSession, main_bot: Bot) -> None:
    resolved = await _resolve_awaiting_order_for_callback(callback, session)
    if resolved is None:
        return
    shop_bot, customer, order = resolved

    await order_service.customer_confirm_order(session, order)
    await callback.answer()
    await callback.message.edit_text(texts.ORDER_CUSTOMER_CONFIRMED_ACK)

    # فقط از همین لحظه به بعد فروشگاه‌دار خبردار می‌شه — دقیقاً همون چیزی که
    # این بازطراحی قرار بود عوض کنه: قبلاً این اطلاع‌رسانی بلافاصله بعدِ تشخیصِ
    # هوش مصنوعی می‌رفت، بدونِ اینکه خودِ مشتری چیزی تایید کرده باشه.
    owner = await shop_owner_service.get_by_id(session, shop_bot.shop_owner_id)
    if owner is not None:
        from app.bots.main_bot import keyboards as main_keyboards

        keyboard = main_keyboards.order_notification_keyboard(order.id) if order.product_id is not None else None
        try:
            await main_bot.send_message(
                owner.telegram_id, main_texts.order_detected_notification(order, customer), reply_markup=keyboard
            )
        except TelegramAPIError:
            logger.exception("اطلاع‌رسانیِ سفارش/مشاوره‌ی تاییدشده به فروشگاه‌دار %s ناموفق بود.", owner.telegram_id)

    await _maybe_offer_online_payment(callback.bot, session, shop_bot, order, customer.telegram_id)


async def _maybe_offer_online_payment(
    shop_bot_instance: Bot, session: AsyncSession, shop_bot, order, customer_telegram_id: int
) -> None:
    """فازِ ۳: اگه پیکربندیِ بله‌پیِ فروشگاه کامل باشه، یه
    پیامِ جداگانه با دکمه‌ی «پرداختِ آنلاین» به مشتری می‌فرسته. کاملاً اختیاری
    و additive: منطقِ بالا (owner-notification) کاملاً دست‌نخورده می‌مونه —
    فروشگاه‌دار همچنان از همون مسیرِ همیشگی سفارش رو تایید/پردازش می‌کنه؛ این
    فقط یه گزینه‌ی اضافه‌ست، نه جایگزینِ چیزی.

    B11: ملاک همان `bale_credentials_service.shop_status` است (توکنِ ربات + توکنِ درگاهِ فروشگاه یا سراسری
    + کلیدِ ادمین + کلیدِ فروشگاه) ⇒ پیکربندیِ ناقص هیچ پیامِ اضافه‌ای برایِ مشتری نمی‌سازد."""
    if order.type != OrderType.ORDER or not order.estimated_value_toman or order.estimated_value_toman <= 0:
        return
    status = await bale_credentials_service.shop_status(
        session, shop_bot, await payment_settings_service.get(session, shop_bot.id)
    )
    if not status.available:
        return

    invoice_payload = f"order-{order.id}-{secrets.token_hex(8)}"
    amount_rial = bale_service.toman_to_rial(order.estimated_value_toman)  # مبلغ‌های داخلیِ ما تومانن؛ بله‌پی ریال می‌خواد.
    try:
        pay_url = await bale_service.create_invoice_link(
            status.bot_token,
            status.provider_token,
            title="پرداخت سفارش",
            description=(order.summary or "پرداخت سفارش")[:255],
            payload=invoice_payload,
            amount_rial=amount_rial,
        )
    except bale_service.BaleError:
        logger.exception("درخواستِ ساختِ لینکِ بله‌پی برایِ سفارشِ %s ناموفق بود؛ گزینه‌ی پرداختِ آنلاین نشون داده نمی‌شه.", order.id)
        return

    order.bale_invoice_payload = invoice_payload
    await session.flush()

    try:
        await shop_bot_instance.send_message(
            customer_telegram_id,
            texts.online_payment_offer(order.estimated_value_toman),
            reply_markup=keyboards.online_payment_keyboard(pay_url),
        )
    except TelegramAPIError:
        logger.exception("ارسالِ پیشنهادِ پرداختِ آنلاین به مشتری %s ناموفق بود.", customer_telegram_id)


@router.callback_query(F.data.startswith("cust_cancel_order:"))
async def cb_customer_cancel_order(callback: CallbackQuery, session: AsyncSession) -> None:
    resolved = await _resolve_awaiting_order_for_callback(callback, session)
    if resolved is None:
        return
    _shop_bot, _customer, order = resolved

    await order_service.customer_cancel_order(session, order)
    await callback.answer()
    await callback.message.edit_text(texts.ORDER_CUSTOMER_CANCELLED_ACK)


@router.message()
async def customer_unsupported_message(message: Message) -> None:
    await message.answer(texts.NON_TEXT_MESSAGE)
