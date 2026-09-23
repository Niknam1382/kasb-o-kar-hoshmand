from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.main_bot import keyboards, texts
from app.bots.main_bot.states import ProductImportStates, ProductStates
from app.database.models import ShopBot
from app.services import excel_import_service, product_service, shop_bot_service, shop_owner_service
from app.utils.validators import parse_price_toman

logger = logging.getLogger(__name__)

router = Router(name="products")

# محافظت در برابرِ فایل‌هایِ بیش‌ازحد بزرگ، قبل از اینکه اصلاً تلاش کنیم بازش کنیم.
_MAX_IMPORT_FILE_BYTES = 5 * 1024 * 1024


async def _require_shop_bot(message: Message, session: AsyncSession) -> ShopBot | None:
    owner = await shop_owner_service.get_by_telegram_id(session, message.from_user.id)
    shop_bot = await shop_bot_service.get_by_owner(session, owner)
    if shop_bot is None:
        await message.answer(texts.SHOP_BOT_NOT_SET_UP)
        return None
    return shop_bot


async def _require_shop_bot_cb(callback: CallbackQuery, session: AsyncSession) -> ShopBot | None:
    """
    مثلِ _require_shop_bot ولی برای callback_query — چون اینجا پیامِ جدید
    نمی‌فرستیم، خطا رو با alert نشون می‌دیم و پیامِ فعلی رو دست‌نخورده ول
    می‌کنیم.
    """
    owner = await shop_owner_service.get_by_telegram_id(session, callback.from_user.id)
    shop_bot = await shop_bot_service.get_by_owner(session, owner) if owner else None
    if shop_bot is None:
        await callback.answer(texts.SHOP_BOT_NOT_SET_UP, show_alert=True)
        return None
    return shop_bot


@router.message(F.text.in_({"📦 محصولات", "🗂 خدمات و بسته‌ها"}))
async def open_products(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    shop_bot = await _require_shop_bot(message, session)
    if shop_bot is None:
        return

    products = await product_service.get_active_by_shop_bot(session, shop_bot.id)
    if not products:
        await message.answer(texts.PRODUCTS_EMPTY, reply_markup=keyboards.products_list_keyboard([]))
        return

    await message.answer(texts.PRODUCTS_LIST_INTRO, reply_markup=keyboards.products_list_keyboard(products))


@router.callback_query(F.data.startswith("product_list"))
async def cb_product_list(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    shop_bot = await _require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return

    page = 0
    if ":" in callback.data:
        try:
            page = int(callback.data.split(":", 1)[1])
        except ValueError:
            page = 0

    products = await product_service.get_active_by_shop_bot(session, shop_bot.id)
    await callback.answer()
    text = texts.PRODUCTS_LIST_INTRO if products else texts.PRODUCTS_EMPTY
    await callback.message.edit_text(text, reply_markup=keyboards.products_list_keyboard(products, page))


@router.callback_query(F.data.startswith("product_view:"))
async def cb_product_view(callback: CallbackQuery, session: AsyncSession) -> None:
    shop_bot = await _require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return

    product_id = int(callback.data.split(":")[1])
    product = await product_service.get_owned_by_id(session, product_id, shop_bot.id)
    await callback.answer()
    if product is None:
        await callback.message.edit_text(texts.PRODUCTS_EMPTY, reply_markup=keyboards.products_list_keyboard([]))
        return
    await callback.message.edit_text(texts.product_detail_text(product), reply_markup=keyboards.product_detail_keyboard(product.id))


@router.callback_query(F.data == "product_add")
async def cb_product_add(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(ProductStates.waiting_name)
    await callback.message.answer(texts.ASK_PRODUCT_NAME)


@router.message(ProductStates.waiting_name, F.text)
async def add_product_name(message: Message, state: FSMContext) -> None:
    await state.update_data(name=message.text.strip())
    await state.set_state(ProductStates.waiting_description)
    await message.answer(texts.ASK_PRODUCT_DESCRIPTION)


@router.message(ProductStates.waiting_description, F.text)
async def add_product_description(message: Message, state: FSMContext) -> None:
    description = None if message.text.strip() == "رد شدن" else message.text.strip()
    await state.update_data(description=description)
    await state.set_state(ProductStates.waiting_price)
    await message.answer(texts.ASK_PRODUCT_PRICE)


@router.message(ProductStates.waiting_price, F.text)
async def add_product_price(message: Message, state: FSMContext) -> None:
    price = parse_price_toman(message.text)
    if price is None:
        await message.answer(texts.INVALID_PRICE)
        return
    await state.update_data(price_toman=price)
    await state.set_state(ProductStates.waiting_photo)
    await message.answer(texts.ASK_PRODUCT_PHOTO)


@router.message(ProductStates.waiting_photo, F.photo)
async def add_product_photo(message: Message, state: FSMContext) -> None:
    await state.update_data(photo_file_id=message.photo[-1].file_id)
    await state.set_state(ProductStates.waiting_stock)
    await message.answer(texts.ASK_PRODUCT_STOCK)


@router.message(ProductStates.waiting_photo, F.text == "رد شدن")
async def add_product_skip_photo(message: Message, state: FSMContext) -> None:
    await state.update_data(photo_file_id=None)
    await state.set_state(ProductStates.waiting_stock)
    await message.answer(texts.ASK_PRODUCT_STOCK)


@router.message(ProductStates.waiting_stock, F.text)
async def add_product_stock(message: Message, state: FSMContext, session: AsyncSession) -> None:
    raw = message.text.strip()
    stock: int | None
    if raw == "رد شدن":
        stock = None
    else:
        try:
            stock = int(raw)
            if stock < 0:
                raise ValueError
        except ValueError:
            await message.answer(texts.INVALID_STOCK)
            return

    await _finalize_new_product(message, state, session, stock_quantity=stock)


async def _finalize_new_product(message: Message, state: FSMContext, session: AsyncSession, stock_quantity: int | None) -> None:
    data = await state.get_data()
    shop_bot = await _require_shop_bot(message, session)
    if shop_bot is None:
        await state.clear()
        return

    product = await product_service.create_product(
        session, shop_bot.id, data["name"], data.get("description"), data["price_toman"], data.get("photo_file_id"), stock_quantity
    )
    await state.clear()
    await message.answer(texts.product_added_confirmation(product.name))

    products = await product_service.get_active_by_shop_bot(session, shop_bot.id)
    await message.answer(texts.PRODUCTS_LIST_INTRO, reply_markup=keyboards.products_list_keyboard(products))


@router.callback_query(F.data == "product_bulk_import")
async def cb_product_bulk_import(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    shop_bot = await _require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return

    await callback.answer()
    template_bytes = excel_import_service.build_template_workbook()
    await callback.message.answer_document(
        BufferedInputFile(template_bytes, filename="قالب-افزودن-محصولات.xlsx"),
        caption=texts.PRODUCT_IMPORT_TEMPLATE_CAPTION,
    )
    await state.set_state(ProductImportStates.waiting_file)
    await callback.message.answer(texts.PRODUCT_IMPORT_INSTRUCTIONS)


@router.message(ProductImportStates.waiting_file, F.document)
async def receive_import_file(message: Message, state: FSMContext, session: AsyncSession) -> None:
    shop_bot = await _require_shop_bot(message, session)
    if shop_bot is None:
        await state.clear()
        return

    file_name = message.document.file_name or ""
    if not file_name.lower().endswith(".xlsx"):
        await message.answer(texts.PRODUCT_IMPORT_WRONG_FILE_TYPE)
        return

    if (message.document.file_size or 0) > _MAX_IMPORT_FILE_BYTES:
        await message.answer(texts.PRODUCT_IMPORT_FILE_TOO_LARGE)
        return

    try:
        file_io = await message.bot.download(message.document.file_id)
        content = file_io.read()
    except Exception:
        logger.exception("دانلودِ فایلِ اکسلِ فروشگاه‌دار %s ناموفق بود.", message.from_user.id)
        await message.answer(texts.PRODUCT_IMPORT_DOWNLOAD_FAILED)
        return

    if len(content) > _MAX_IMPORT_FILE_BYTES:
        await message.answer(texts.PRODUCT_IMPORT_FILE_TOO_LARGE)
        return

    try:
        result = excel_import_service.parse_workbook(content)
    except excel_import_service.InvalidExcelFileError:
        await message.answer(texts.PRODUCT_IMPORT_INVALID_FILE)
        return

    if result.too_many_rows:
        await message.answer(texts.product_import_too_many_rows(excel_import_service.MAX_IMPORT_ROWS))
        return

    if not result.valid_rows and not result.errors:
        await message.answer(texts.PRODUCT_IMPORT_EMPTY_FILE)
        return

    if not result.valid_rows:
        await message.answer(texts.product_import_no_valid_rows(result.errors))
        return

    await state.update_data(rows=result.valid_rows)
    await state.set_state(ProductImportStates.waiting_confirmation)
    await message.answer(
        texts.product_import_preview(len(result.valid_rows), result.errors),
        reply_markup=keyboards.product_import_confirm_keyboard(len(result.valid_rows)),
    )


@router.message(ProductImportStates.waiting_file)
async def receive_import_file_wrong_type(message: Message) -> None:
    await message.answer(texts.PRODUCT_IMPORT_WRONG_FILE_TYPE)


@router.callback_query(ProductImportStates.waiting_confirmation, F.data == "product_bulk_import_confirm")
async def cb_product_bulk_import_confirm(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    shop_bot = await _require_shop_bot_cb(callback, session)
    if shop_bot is None:
        await state.clear()
        return

    data = await state.get_data()
    rows = data.get("rows", [])
    await excel_import_service.bulk_create(session, shop_bot.id, rows)
    await state.clear()

    products = await product_service.get_active_by_shop_bot(session, shop_bot.id)
    await callback.answer(texts.product_import_result_toast(len(rows)))
    text = texts.PRODUCTS_LIST_INTRO if products else texts.PRODUCTS_EMPTY
    await callback.message.edit_text(text, reply_markup=keyboards.products_list_keyboard(products))


@router.callback_query(ProductImportStates.waiting_confirmation, F.data == "product_bulk_import_cancel")
async def cb_product_bulk_import_cancel(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    shop_bot = await _require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return

    await callback.answer(texts.PRODUCT_IMPORT_CANCELLED)
    products = await product_service.get_active_by_shop_bot(session, shop_bot.id)
    text = texts.PRODUCTS_LIST_INTRO if products else texts.PRODUCTS_EMPTY
    await callback.message.edit_text(text, reply_markup=keyboards.products_list_keyboard(products))


@router.callback_query(F.data.startswith("product_delete:"))
async def cb_product_delete(callback: CallbackQuery, session: AsyncSession) -> None:
    shop_bot = await _require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return

    product_id = int(callback.data.split(":")[1])
    product = await product_service.get_owned_by_id(session, product_id, shop_bot.id)
    if product is None:
        await callback.answer(texts.GENERIC_ERROR, show_alert=True)
        return

    await callback.answer()
    await callback.message.edit_text(texts.CONFIRM_DELETE_PRODUCT, reply_markup=keyboards.confirm_delete_product_keyboard(product_id))


@router.callback_query(F.data.startswith("product_delete_confirm:"))
async def cb_product_delete_confirm(callback: CallbackQuery, session: AsyncSession) -> None:
    shop_bot = await _require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return

    product_id = int(callback.data.split(":")[1])
    product = await product_service.get_owned_by_id(session, product_id, shop_bot.id)
    if product is None:
        await callback.answer(texts.GENERIC_ERROR, show_alert=True)
        return

    name = product.name
    await product_service.soft_delete(session, product)
    await callback.answer(texts.product_deleted_confirmation(name))

    products = await product_service.get_active_by_shop_bot(session, shop_bot.id)
    text = texts.PRODUCTS_LIST_INTRO if products else texts.PRODUCTS_EMPTY
    await callback.message.edit_text(text, reply_markup=keyboards.products_list_keyboard(products))


@router.callback_query(F.data.startswith("product_edit:"))
async def cb_product_edit(callback: CallbackQuery, session: AsyncSession) -> None:
    shop_bot = await _require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return

    product_id = int(callback.data.split(":")[1])
    product = await product_service.get_owned_by_id(session, product_id, shop_bot.id)
    if product is None:
        await callback.answer(texts.GENERIC_ERROR, show_alert=True)
        return

    await callback.answer()
    await callback.message.edit_text(texts.ASK_EDIT_PRODUCT_FIELD, reply_markup=keyboards.edit_product_field_keyboard(product_id))


def _field_prompts() -> dict[str, str]:
    return {
        "name": texts.ASK_NEW_PRODUCT_NAME,
        "description": texts.ASK_NEW_PRODUCT_DESCRIPTION,
        "price": texts.ASK_NEW_PRODUCT_PRICE,
        "photo": texts.ASK_NEW_PRODUCT_PHOTO,
        "stock": texts.ASK_NEW_PRODUCT_STOCK,
    }


@router.callback_query(F.data.startswith("product_edit_field:"))
async def cb_product_edit_field(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    shop_bot = await _require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return

    _, product_id, field = callback.data.split(":")
    product = await product_service.get_owned_by_id(session, int(product_id), shop_bot.id)
    if product is None:
        await callback.answer(texts.GENERIC_ERROR, show_alert=True)
        return

    await callback.answer()
    await state.update_data(edit_product_id=int(product_id), edit_field=field)
    await state.set_state(ProductStates.waiting_edit_field_value)
    await callback.message.answer(_field_prompts()[field])


@router.message(ProductStates.waiting_edit_field_value, F.photo)
async def edit_product_value_photo(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await _apply_field_edit(message, state, session, message.photo[-1].file_id)


@router.message(ProductStates.waiting_edit_field_value, F.text)
async def edit_product_value_text(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    field = data["edit_field"]

    if field == "price":
        price = parse_price_toman(message.text)
        if price is None:
            await message.answer(texts.INVALID_PRICE)
            return
        await _apply_field_edit(message, state, session, price)
        return

    if field == "stock":
        raw = message.text.strip()
        if raw == "رد شدن":
            await _apply_field_edit(message, state, session, None)
            return
        try:
            stock = int(raw)
            if stock < 0:
                raise ValueError
        except ValueError:
            await message.answer(texts.INVALID_STOCK)
            return
        await _apply_field_edit(message, state, session, stock)
        return

    await _apply_field_edit(message, state, session, message.text.strip())


async def _apply_field_edit(message: Message, state: FSMContext, session: AsyncSession, value) -> None:
    shop_bot = await _require_shop_bot(message, session)
    if shop_bot is None:
        await state.clear()
        return

    data = await state.get_data()
    product = await product_service.get_owned_by_id(session, data["edit_product_id"], shop_bot.id)
    if product is None:
        await state.clear()
        await message.answer(texts.GENERIC_ERROR)
        return
    field = data["edit_field"]

    field_attr = {"name": "name", "description": "description", "price": "price_toman", "photo": "photo_file_id", "stock": "stock_quantity"}[field]
    setattr(product, field_attr, value)
    await session.flush()

    await state.clear()
    await message.answer(texts.product_field_updated(field))
    await message.answer(texts.product_detail_text(product), reply_markup=keyboards.product_detail_keyboard(product.id))
