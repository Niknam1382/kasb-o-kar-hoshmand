"""کاتالوگِ فیزیکی/دیجیتال (فازِ ۱ · P1-S3 / B2): افزودنِ محصولِ دیجیتال + روش‌هایِ ارسال.

* ورودِ جداگانه (`product_add_digital`) تا جریانِ قدیمیِ «➕ افزودن محصول جدید» (فیزیکی) و تست‌هاش
  بایت‌به‌بایت دست‌نخورده بمونن.
* هر مرحله‌یِ اختیاری «⏭ رد کردن» و «❌ انصراف» داره؛ دکمه‌یِ کهنه = پیامِ مودبانه.
* `state.clear()` قبل از هر I/Oِ ساخت‌ساز ⇒ دابل‌تپ = یک محصول/یک روشِ ارسال.
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.main_bot import keyboards, texts
from app.bots.main_bot.handlers.owner_common import require_shop_bot_cb, safe_edit
from app.bots.main_bot.states import DigitalProductStates, ShippingStates
from app.database.models import ShopBot, TenantMode
from app.services import digital_service, product_service, shipping_service
from app.utils.validators import fa_number, parse_nonneg_int, parse_price_toman

logger = logging.getLogger(__name__)

router = Router(name="catalog_b2")

MAX_CODES_FILE_BYTES = 1024 * 1024
MAX_DOWNLOADS_CAP = 1000


def _sales(shop_bot: ShopBot) -> bool:
    return shop_bot.tenant_mode == TenantMode.SALES


async def _show_products(callback_or_message, session: AsyncSession, shop_bot: ShopBot) -> None:
    products = await product_service.get_active_by_shop_bot(session, shop_bot.id)
    text = texts.PRODUCTS_LIST_INTRO if products else texts.PRODUCTS_EMPTY
    target = callback_or_message.message if isinstance(callback_or_message, CallbackQuery) else callback_or_message
    await target.answer(text, reply_markup=keyboards.products_list_keyboard(products, sales_mode=_sales(shop_bot)))


# ===========================================================================
# ===========================================================================
# پ۹۷ · بایگانیِ نرمِ محصول‌هایِ دیجیتال (صفر حذفِ داده، برگشت‌پذیر)
# ===========================================================================
@router.callback_query(F.data == "product_archive_digital")
async def cb_archive_digital(callback: CallbackQuery, session: AsyncSession) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    if not _sales(shop_bot):
        await callback.answer(texts.DG_ONLY_SALES, show_alert=True)
        return
    pending = await product_service.count_digital(session, shop_bot.id, retired=False)
    archived = await product_service.count_digital(session, shop_bot.id, retired=True)
    await session.commit()
    if not pending:
        if not archived:
            await callback.answer(texts.DG_ARCHIVE_NONE, show_alert=True)
            return
        # همه بایگانی‌اند ⇒ «بله» کاری ندارد؛ صفحه فقط راهِ برگشت را نشان می‌دهد (وگرنه undo دیدنی نمی‌شد).
        await callback.answer()
        await callback.message.answer(
            texts.DG_ARCHIVE_ALL.format(count=fa_number(archived)),
            reply_markup=keyboards.dg_archive_confirm_keyboard(archived, pending=0),
        )
        return
    await callback.answer()
    await callback.message.answer(
        chr(10).join((texts.DG_ARCHIVE_ASK.format(count=fa_number(pending)), texts.DG_ARCHIVE_UNDO_NOTE)),
        reply_markup=keyboards.dg_archive_confirm_keyboard(archived),
    )


@router.callback_query(F.data == "product_archive_digital_yes")
async def cb_archive_digital_yes(callback: CallbackQuery, session: AsyncSession) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    count = await product_service.retire_digital(session, shop_bot.id)
    await session.commit()
    await callback.answer(
        texts.DG_ARCHIVE_DONE.format(count=fa_number(count)) if count else texts.DG_ARCHIVE_NONE, show_alert=True
    )


@router.callback_query(F.data == "product_archive_digital_no")
async def cb_archive_digital_no(callback: CallbackQuery, session: AsyncSession) -> None:
    if await require_shop_bot_cb(callback, session) is None:
        return
    await callback.answer(texts.DG_ARCHIVE_CONFIRM_NO.replace("⬅️ ", ""))


@router.callback_query(F.data == "product_archive_digital_undo")
async def cb_archive_digital_undo(callback: CallbackQuery, session: AsyncSession) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    count = await product_service.unretire_digital(session, shop_bot.id)
    await session.commit()
    await callback.answer(texts.DG_UNARCHIVE_DONE.format(count=fa_number(count)) if count else texts.DG_UNARCHIVE_NONE, show_alert=True)


# افزودنِ محصولِ دیجیتال
# ===========================================================================
@router.callback_query(F.data == "product_add_digital")
async def cb_product_add_digital(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    if not digital_service.NEW_DIGITAL_ALLOWED:
        # پ۷۸ · درِ ساختنِ تازه بسته است (دکمه هم از کیبورد رفته). تحویلِ محصولاتِ موجود کار می‌کند.
        await callback.answer(texts.DG_RETIRED, show_alert=True)
        return
    if not _sales(shop_bot):
        await callback.answer(texts.DG_ONLY_SALES, show_alert=True)
        return
    await callback.answer()
    await state.clear()
    await state.set_state(DigitalProductStates.waiting_name)
    await callback.message.answer(texts.DG_ASK_NAME, reply_markup=keyboards.dg_cancel_keyboard())


@router.callback_query(F.data == "dg_cancel")
async def cb_dg_cancel(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    await callback.answer("❌ انصراف داده شد.")
    await _show_products(callback, session, shop_bot)


@router.message(DigitalProductStates.waiting_name, F.text)
async def dg_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if not name or len(name) > 255:
        await message.answer(texts.DG_ASK_NAME, reply_markup=keyboards.dg_cancel_keyboard())
        return
    await state.update_data(name=name)
    await state.set_state(DigitalProductStates.waiting_description)
    await message.answer(texts.ASK_PRODUCT_DESCRIPTION, reply_markup=keyboards.dg_skip_keyboard("description"))


async def _ask_price(target: Message, state: FSMContext) -> None:
    await state.set_state(DigitalProductStates.waiting_price)
    await target.answer(texts.ASK_PRODUCT_PRICE, reply_markup=keyboards.dg_cancel_keyboard())


@router.message(DigitalProductStates.waiting_description, F.text)
async def dg_description(message: Message, state: FSMContext) -> None:
    await state.update_data(description=message.text.strip() or None)
    await _ask_price(message, state)


@router.callback_query(DigitalProductStates.waiting_description, F.data == "dg_skip:description")
async def dg_skip_description(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.update_data(description=None)
    await _ask_price(callback.message, state)


@router.message(DigitalProductStates.waiting_price, F.text)
async def dg_price(message: Message, state: FSMContext) -> None:
    price = parse_price_toman(message.text)
    if price is None:
        await message.answer(texts.INVALID_PRICE, reply_markup=keyboards.dg_cancel_keyboard())
        return
    await state.update_data(price_toman=price)
    await state.set_state(DigitalProductStates.waiting_photo)
    await message.answer(texts.ASK_PRODUCT_PHOTO, reply_markup=keyboards.dg_skip_keyboard("photo"))


async def _ask_mode(target: Message, state: FSMContext) -> None:
    await state.set_state(DigitalProductStates.choosing_mode)
    await target.answer(texts.DG_ASK_MODE, reply_markup=keyboards.digital_mode_keyboard())


@router.message(DigitalProductStates.waiting_photo, F.photo)
async def dg_photo(message: Message, state: FSMContext) -> None:
    await state.update_data(photo_file_id=message.photo[-1].file_id)
    await _ask_mode(message, state)


@router.callback_query(DigitalProductStates.waiting_photo, F.data == "dg_skip:photo")
async def dg_skip_photo(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.update_data(photo_file_id=None)
    await _ask_mode(callback.message, state)


@router.message(DigitalProductStates.waiting_photo)
async def dg_photo_wrong(message: Message) -> None:
    await message.answer(texts.ASK_PRODUCT_PHOTO, reply_markup=keyboards.dg_skip_keyboard("photo"))


@router.callback_query(DigitalProductStates.choosing_mode, F.data.startswith("dg_mode:"))
async def dg_choose_mode(callback: CallbackQuery, state: FSMContext) -> None:
    mode = callback.data.split(":", 1)[1]
    if mode not in digital_service.DELIVERY_MODES:
        await callback.answer(texts.DG_STALE, show_alert=True)
        return
    await callback.answer()
    await state.update_data(delivery=mode)
    if mode == "file":
        await state.set_state(DigitalProductStates.waiting_file)
        await callback.message.answer(texts.DG_ASK_FILE, reply_markup=keyboards.dg_cancel_keyboard())
    elif mode == "link":
        await state.set_state(DigitalProductStates.waiting_link)
        await callback.message.answer(texts.DG_ASK_LINK, reply_markup=keyboards.dg_cancel_keyboard())
    elif mode == "text":
        await state.set_state(DigitalProductStates.waiting_text)
        await callback.message.answer(texts.DG_ASK_TEXT, reply_markup=keyboards.dg_cancel_keyboard())
    else:
        await _ask_instructions(callback.message, state)


@router.message(DigitalProductStates.waiting_file, F.document)
async def dg_file(message: Message, state: FSMContext) -> None:
    if (message.document.file_size or 0) > digital_service.MAX_DIGITAL_FILE_BYTES:
        await message.answer(texts.DG_FILE_TOO_BIG, reply_markup=keyboards.dg_cancel_keyboard())
        return
    await state.update_data(file_id=message.document.file_id, file_name=(message.document.file_name or "file")[:255])
    await _ask_instructions(message, state)


@router.message(DigitalProductStates.waiting_file)
async def dg_file_wrong(message: Message) -> None:
    await message.answer(texts.DG_NEED_DOCUMENT, reply_markup=keyboards.dg_cancel_keyboard())


@router.message(DigitalProductStates.waiting_link, F.text)
async def dg_link(message: Message, state: FSMContext) -> None:
    link = digital_service.validate_link(message.text)
    if link is None:
        await message.answer(texts.DG_INVALID_LINK, reply_markup=keyboards.dg_cancel_keyboard())
        return
    await state.update_data(link=link)
    await _ask_instructions(message, state)


@router.message(DigitalProductStates.waiting_text, F.text)
async def dg_text(message: Message, state: FSMContext) -> None:
    content = message.text.strip()
    if not content:
        await message.answer(texts.DG_TEXT_CANNOT_BE_EMPTY, reply_markup=keyboards.dg_cancel_keyboard())
        return
    await state.update_data(instructions=content)  # در حالتِ «متن»، خودِ متنِ تحویل = digital_instructions
    await _ask_max_downloads(message, state)


async def _ask_instructions(target: Message, state: FSMContext) -> None:
    await state.set_state(DigitalProductStates.waiting_instructions)
    await target.answer(texts.DG_ASK_INSTRUCTIONS, reply_markup=keyboards.dg_skip_keyboard("instructions"))


@router.message(DigitalProductStates.waiting_instructions, F.text)
async def dg_instructions(message: Message, state: FSMContext) -> None:
    await state.update_data(instructions=message.text.strip() or None)
    await _ask_max_downloads(message, state)


@router.callback_query(DigitalProductStates.waiting_instructions, F.data == "dg_skip:instructions")
async def dg_skip_instructions(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.update_data(instructions=None)
    await _ask_max_downloads(callback.message, state)


async def _ask_max_downloads(target: Message, state: FSMContext) -> None:
    await state.set_state(DigitalProductStates.waiting_max_downloads)
    await target.answer(texts.DG_ASK_MAX_DOWNLOADS, reply_markup=keyboards.dg_skip_keyboard("max"))


async def _after_max_downloads(target: Message, state: FSMContext, session: AsyncSession, shop_bot: ShopBot | None) -> None:
    data = await state.get_data()
    if data.get("delivery") == "code_pool":
        await state.set_state(DigitalProductStates.waiting_codes)
        await target.answer(texts.DG_ASK_CODES, reply_markup=keyboards.dg_skip_keyboard("codes"))
        return
    await _finalize(target, state, session, shop_bot, codes=[])


@router.message(DigitalProductStates.waiting_max_downloads, F.text)
async def dg_max_downloads(message: Message, state: FSMContext, session: AsyncSession) -> None:
    value = parse_nonneg_int(message.text, allow_zero=False, max_value=MAX_DOWNLOADS_CAP)
    if value is None:
        await message.answer(texts.DG_INVALID_MAX, reply_markup=keyboards.dg_skip_keyboard("max"))
        return
    await state.update_data(max_downloads=value)
    await _after_max_downloads(message, state, session, None)


@router.callback_query(DigitalProductStates.waiting_max_downloads, F.data == "dg_skip:max")
async def dg_skip_max(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await callback.answer()
    await state.update_data(max_downloads=None)
    await _after_max_downloads(callback.message, state, session, None)


async def _read_codes_document(message: Message) -> str | None:
    document = message.document
    if document is None or (document.file_size or 0) > MAX_CODES_FILE_BYTES:
        return None
    name = (document.file_name or "").lower()
    if not name.endswith(".txt"):
        return None
    try:
        buffer = await message.bot.download(document.file_id)
        return buffer.read().decode("utf-8-sig", errors="replace")
    except Exception:  # noqa: BLE001
        logger.exception("دانلودِ فایلِ کدها ناموفق بود.")
        return None


@router.message(DigitalProductStates.waiting_codes, F.text)
async def dg_codes_text(message: Message, state: FSMContext, session: AsyncSession) -> None:
    codes, _ignored = digital_service.parse_codes(message.text)
    if not codes:
        await message.answer(texts.DG_CODES_EMPTY, reply_markup=keyboards.dg_skip_keyboard("codes"))
        return
    await _finalize(message, state, session, None, codes=codes)


@router.message(DigitalProductStates.waiting_codes, F.document)
async def dg_codes_document(message: Message, state: FSMContext, session: AsyncSession) -> None:
    content = await _read_codes_document(message)
    if content is None:
        await message.answer(texts.DG_CODES_BAD_FILE, reply_markup=keyboards.dg_skip_keyboard("codes"))
        return
    codes, _ignored = digital_service.parse_codes(content)
    if not codes:
        await message.answer(texts.DG_CODES_EMPTY, reply_markup=keyboards.dg_skip_keyboard("codes"))
        return
    await _finalize(message, state, session, None, codes=codes)


@router.callback_query(DigitalProductStates.waiting_codes, F.data == "dg_skip:codes")
async def dg_skip_codes(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        await state.clear()
        return
    await callback.answer()
    await _finalize(callback.message, state, session, shop_bot, codes=[])


async def _finalize(target: Message, state: FSMContext, session: AsyncSession, shop_bot: ShopBot | None, codes: list[str]) -> None:
    """ساختِ محصول. `state.clear()` *قبل* از I/O (دابل‌تپ = یک محصول)."""
    data = await state.get_data()
    await state.clear()
    if shop_bot is None:
        # چتِ خصوصی: target.chat.id همیشه تلگرام‌آیدیِ مالکه (چه پیامِ خودش، چه callback.message)
        shop_bot = await _shop_bot_for(target, session)
    if shop_bot is None:
        return
    if not _sales(shop_bot) or "name" not in data or "price_toman" not in data or data.get("delivery") not in digital_service.DELIVERY_MODES:
        await target.answer(texts.DG_STALE)
        return

    delivery = data["delivery"]
    product = await product_service.create_digital_product(
        session,
        shop_bot.id,
        data["name"],
        data.get("description"),
        data["price_toman"],
        data.get("photo_file_id"),
        delivery,
        file_id=data.get("file_id"),
        file_name=data.get("file_name"),
        link=data.get("link"),
        instructions=data.get("instructions"),
        max_downloads=data.get("max_downloads"),
    )
    added = 0
    if delivery == "code_pool":
        added, _dups = await digital_service.add_codes(session, product, codes)
        await digital_service.sync_pool_stock(session, product)
    await target.answer(texts.digital_product_added(product.name, delivery, added if delivery == "code_pool" else None))
    await _show_products(target, session, shop_bot)


async def _shop_bot_for(target: Message, session: AsyncSession) -> ShopBot | None:
    from app.services import shop_bot_service, shop_owner_service

    owner = await shop_owner_service.get_by_telegram_id(session, target.chat.id)
    shop_bot = await shop_bot_service.get_by_owner(session, owner) if owner else None
    if shop_bot is None:
        await target.answer(texts.SHOP_BOT_NOT_SET_UP)
    return shop_bot


@router.callback_query(F.data.startswith("dg_mode:"))
@router.callback_query(F.data.startswith("dg_skip:"))
async def cb_dg_stale(callback: CallbackQuery) -> None:
    """دکمه‌یِ کهنه (بعد از /cancel، ری‌استارتِ ربات یا انصراف)."""
    await callback.answer(texts.DG_STALE, show_alert=True)


# ===========================================================================
# روش‌هایِ ارسال
# ===========================================================================
async def _render_shipping(callback: CallbackQuery, session: AsyncSession, shop_bot: ShopBot) -> None:
    methods = await shipping_service.list_methods(session, shop_bot.id)
    await safe_edit(callback, texts.shipping_list_text(methods), keyboards.shipping_list_keyboard(methods))


@router.callback_query(F.data == "shipping_list")
async def cb_shipping_list(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    if not _sales(shop_bot):
        await callback.answer(texts.DG_ONLY_SALES, show_alert=True)
        return
    await callback.answer()
    await _render_shipping(callback, session, shop_bot)


@router.callback_query(F.data.startswith("ship_toggle:"))
async def cb_ship_toggle(callback: CallbackQuery, session: AsyncSession) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    try:
        method_id = int(callback.data.split(":", 1)[1])
    except ValueError:
        await callback.answer(texts.SHIP_STALE, show_alert=True)
        return
    method = await shipping_service.get_owned(session, method_id, shop_bot.id)
    if method is None:
        await callback.answer(texts.SHIP_STALE, show_alert=True)
        return
    now_active = await shipping_service.toggle_active(session, method)
    await callback.answer(texts.switch_toast(f"ارسالِ «{method.name}»", now_active))
    await _render_shipping(callback, session, shop_bot)


@router.callback_query(F.data.startswith("ship_del:"))
async def cb_ship_delete(callback: CallbackQuery, session: AsyncSession) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    try:
        method_id = int(callback.data.split(":", 1)[1])
    except ValueError:
        await callback.answer(texts.SHIP_STALE, show_alert=True)
        return
    method = await shipping_service.get_owned(session, method_id, shop_bot.id)
    if method is None:
        await callback.answer(texts.SHIP_STALE, show_alert=True)
        return
    await shipping_service.delete_method(session, method)
    await callback.answer("🗑 حذف شد.")
    await _render_shipping(callback, session, shop_bot)


@router.callback_query(F.data == "ship_add")
async def cb_ship_add(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    if not _sales(shop_bot):
        await callback.answer(texts.DG_ONLY_SALES, show_alert=True)
        return
    methods = await shipping_service.list_methods(session, shop_bot.id)
    if len(methods) >= shipping_service.MAX_METHODS_PER_SHOP:
        await callback.answer(texts.SHIP_LIMIT_REACHED, show_alert=True)
        return
    await callback.answer()
    await state.clear()
    await state.set_state(ShippingStates.waiting_name)
    await callback.message.answer(texts.ASK_SHIP_NAME, reply_markup=keyboards.ship_cancel_keyboard())


@router.callback_query(F.data == "ship_cancel")
async def cb_ship_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer("❌ انصراف داده شد.")


@router.message(ShippingStates.waiting_name, F.text)
async def ship_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if not name or len(name) > shipping_service.MAX_NAME_LEN:
        await message.answer(texts.INVALID_SHIP_NAME, reply_markup=keyboards.ship_cancel_keyboard())
        return
    await state.update_data(name=name)
    await state.set_state(ShippingStates.waiting_fee)
    await message.answer(texts.ASK_SHIP_FEE, reply_markup=keyboards.ship_cancel_keyboard())


@router.message(ShippingStates.waiting_fee, F.text)
async def ship_fee(message: Message, state: FSMContext) -> None:
    fee = parse_nonneg_int(message.text, allow_zero=True)
    if fee is None:
        await message.answer(texts.INVALID_SHIP_FEE, reply_markup=keyboards.ship_cancel_keyboard())
        return
    await state.update_data(fee_toman=fee)
    await state.set_state(ShippingStates.waiting_free_over)
    await message.answer(texts.ASK_SHIP_FREE_OVER, reply_markup=keyboards.ship_skip_keyboard("free_over"))


async def _ask_eta(target: Message, state: FSMContext) -> None:
    await state.set_state(ShippingStates.waiting_eta)
    await target.answer(texts.ASK_SHIP_ETA, reply_markup=keyboards.ship_skip_keyboard("eta"))


@router.message(ShippingStates.waiting_free_over, F.text)
async def ship_free_over(message: Message, state: FSMContext) -> None:
    value = parse_nonneg_int(message.text, allow_zero=False)
    if value is None:
        await message.answer(texts.INVALID_SHIP_FEE, reply_markup=keyboards.ship_skip_keyboard("free_over"))
        return
    await state.update_data(free_over_toman=value)
    await _ask_eta(message, state)


@router.callback_query(ShippingStates.waiting_free_over, F.data == "ship_skip:free_over")
async def ship_skip_free_over(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.update_data(free_over_toman=None)
    await _ask_eta(callback.message, state)


async def _create_shipping(target: Message, state: FSMContext, session: AsyncSession, shop_bot: ShopBot, eta: str | None) -> None:
    data = await state.get_data()
    await state.clear()  # قبل از I/O: دابل‌تپ = یک روش
    if "name" not in data or "fee_toman" not in data:
        await target.answer(texts.SHIP_STALE)
        return
    method = await shipping_service.create_method(
        session, shop_bot.id, data["name"], data["fee_toman"], data.get("free_over_toman"), eta
    )
    if method is None:
        await target.answer(texts.SHIP_LIMIT_REACHED)
        return
    await target.answer(texts.shipping_added(method.name))
    methods = await shipping_service.list_methods(session, shop_bot.id)
    await target.answer(texts.shipping_list_text(methods), reply_markup=keyboards.shipping_list_keyboard(methods))


@router.message(ShippingStates.waiting_eta, F.text)
async def ship_eta(message: Message, state: FSMContext, session: AsyncSession) -> None:
    shop_bot = await _shop_bot_for(message, session)
    if shop_bot is None:
        await state.clear()
        return
    await _create_shipping(message, state, session, shop_bot, message.text.strip())


@router.callback_query(ShippingStates.waiting_eta, F.data == "ship_skip:eta")
async def ship_skip_eta(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        await state.clear()
        return
    await callback.answer()
    await _create_shipping(callback.message, state, session, shop_bot, None)


@router.callback_query(F.data.startswith("ship_skip:"))
async def cb_ship_stale(callback: CallbackQuery) -> None:
    await callback.answer(texts.SHIP_STALE, show_alert=True)
