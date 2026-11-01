from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.main_bot import keyboards, texts
from app.bots.main_bot.states import ProductImportStates, ProductStates
from app.database.models import ShopBot, TenantMode
from app.services import digital_service, excel_import_service, product_service, shop_bot_service, shop_owner_service
from app.utils.validators import parse_nonneg_int, parse_price_toman

logger = logging.getLogger(__name__)

router = Router(name="products")


def _sales(shop_bot: ShopBot) -> bool:
    """دکمه‌هایِ «محصولِ دیجیتال/روشِ ارسال» فقط در مودِ فروشگاهی (مشاوره = بدونِ کالا) — P1-S3."""
    return shop_bot.tenant_mode == TenantMode.SALES


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
    # C1: مودِ مشاوره‌ای کاتالوگِ محصول/خدمت ندارد — دکمه از منو حذف شده؛ این محافظِ متن/دکمه‌یِ کهنه است.
    if not _sales(shop_bot):
        await message.answer(texts.CONSULT_NO_CATALOG)
        return

    products = await product_service.get_active_by_shop_bot(session, shop_bot.id)
    if not products:
        await message.answer(texts.PRODUCTS_EMPTY, reply_markup=keyboards.products_list_keyboard([], sales_mode=_sales(shop_bot)))
        return

    await message.answer(texts.PRODUCTS_LIST_INTRO, reply_markup=keyboards.products_list_keyboard(products, sales_mode=_sales(shop_bot)))


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
    await callback.message.edit_text(text, reply_markup=keyboards.products_list_keyboard(products, page, sales_mode=_sales(shop_bot)))


@router.callback_query(F.data.startswith("product_view:"))
async def cb_product_view(callback: CallbackQuery, session: AsyncSession) -> None:
    shop_bot = await _require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return

    product_id = int(callback.data.split(":")[1])
    product = await product_service.get_owned_by_id(session, product_id, shop_bot.id)
    await callback.answer()
    if product is None:
        await callback.message.edit_text(texts.PRODUCTS_EMPTY, reply_markup=keyboards.products_list_keyboard([], sales_mode=_sales(shop_bot)))
        return
    await callback.message.edit_text(texts.product_detail_text(product), reply_markup=keyboards.product_detail_keyboard(product.id))


@router.callback_query(F.data == "product_add")
async def cb_product_add(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    # C1: دکمه از کیبوردِ مشاوره حذف شده؛ این هم محافظِ کالبکِ کهنه/دستکاری‌شده است.
    shop_bot = await _require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    if not _sales(shop_bot):
        await callback.answer(texts.CONSULT_NO_CATALOG, show_alert=True)
        return
    await callback.answer()
    await state.set_state(ProductStates.waiting_name)
    await callback.message.answer(texts.ASK_PRODUCT_NAME)


@router.message(ProductStates.waiting_name, F.text)
async def add_product_name(message: Message, state: FSMContext) -> None:
    await state.update_data(name=message.text.strip())
    await state.set_state(ProductStates.waiting_description)
    await message.answer(texts.ASK_PRODUCT_DESCRIPTION, reply_markup=keyboards.skip_step_keyboard("description"))


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
    await message.answer(texts.ASK_PRODUCT_PHOTO, reply_markup=keyboards.skip_step_keyboard("photo"))


@router.message(ProductStates.waiting_photo, F.photo)
async def add_product_photo(message: Message, state: FSMContext) -> None:
    await state.update_data(photo_file_id=message.photo[-1].file_id)
    await state.set_state(ProductStates.waiting_stock)
    await message.answer(texts.ASK_PRODUCT_STOCK, reply_markup=keyboards.skip_step_keyboard("stock"))


@router.message(ProductStates.waiting_photo, F.text == "رد شدن")
async def add_product_skip_photo(message: Message, state: FSMContext) -> None:
    await state.update_data(photo_file_id=None)
    await state.set_state(ProductStates.waiting_stock)
    await message.answer(texts.ASK_PRODUCT_STOCK, reply_markup=keyboards.skip_step_keyboard("stock"))


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


@router.callback_query(ProductStates.waiting_description, F.data == "product_skip:description")
async def cb_skip_description(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.update_data(description=None)
    await state.set_state(ProductStates.waiting_price)
    await callback.message.answer(texts.ASK_PRODUCT_PRICE)


@router.callback_query(ProductStates.waiting_photo, F.data == "product_skip:photo")
async def cb_skip_photo(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.update_data(photo_file_id=None)
    await state.set_state(ProductStates.waiting_stock)
    await callback.message.answer(texts.ASK_PRODUCT_STOCK, reply_markup=keyboards.skip_step_keyboard("stock"))


@router.callback_query(ProductStates.waiting_stock, F.data == "product_skip:stock")
async def cb_skip_stock(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    shop_bot = await _require_shop_bot_cb(callback, session)
    if shop_bot is None:
        await state.clear()
        return
    await callback.answer()
    await _finalize_new_product(callback.message, state, session, stock_quantity=None, shop_bot=shop_bot)


@router.callback_query(F.data.startswith("product_skip:"))
async def cb_skip_stale(callback: CallbackQuery) -> None:
    """دکمه‌یِ «رد کردن»ِ کهنه (بعد از /cancel یا ری‌استارت)."""
    await callback.answer(texts.PRODUCT_SKIP_STALE, show_alert=True)


async def _finalize_new_product(
    message: Message, state: FSMContext, session: AsyncSession, stock_quantity: int | None, shop_bot=None
) -> None:
    data = await state.get_data()
    if shop_bot is None:
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
    await message.answer(texts.PRODUCTS_LIST_INTRO, reply_markup=keyboards.products_list_keyboard(products, sales_mode=_sales(shop_bot)))


@router.callback_query(F.data == "product_bulk_import")
async def cb_product_bulk_import(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    shop_bot = await _require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    if not _sales(shop_bot):  # C1
        await callback.answer(texts.CONSULT_NO_CATALOG, show_alert=True)
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
    await callback.message.edit_text(text, reply_markup=keyboards.products_list_keyboard(products, sales_mode=_sales(shop_bot)))


@router.callback_query(ProductImportStates.waiting_confirmation, F.data == "product_bulk_import_cancel")
async def cb_product_bulk_import_cancel(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    shop_bot = await _require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return

    await callback.answer(texts.PRODUCT_IMPORT_CANCELLED)
    products = await product_service.get_active_by_shop_bot(session, shop_bot.id)
    text = texts.PRODUCTS_LIST_INTRO if products else texts.PRODUCTS_EMPTY
    await callback.message.edit_text(text, reply_markup=keyboards.products_list_keyboard(products, sales_mode=_sales(shop_bot)))


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
    await callback.message.edit_text(text, reply_markup=keyboards.products_list_keyboard(products, sales_mode=_sales(shop_bot)))


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
    await callback.message.edit_text(
        texts.ASK_EDIT_PRODUCT_FIELD,
        reply_markup=keyboards.edit_product_field_keyboard(product_id, product.kind, product.digital_delivery),
    )


def _field_prompts() -> dict[str, str]:
    return {
        "name": texts.ASK_NEW_PRODUCT_NAME,
        "description": texts.ASK_NEW_PRODUCT_DESCRIPTION,
        "price": texts.ASK_NEW_PRODUCT_PRICE,
        "photo": texts.ASK_NEW_PRODUCT_PHOTO,
        "stock": texts.ASK_NEW_PRODUCT_STOCK,
        "weight": texts.ASK_NEW_WEIGHT,
        "delivery": texts.ASK_NEW_DELIVERY_NOTE,
        "returns": texts.ASK_NEW_RETURN_POLICY,
        "ai": texts.ASK_NEW_PRODUCT_AI,
        "dlink": texts.ASK_NEW_DG_LINK,
        "dinstr": texts.ASK_NEW_DG_INSTRUCTIONS,
        "dmax": texts.ASK_NEW_DG_MAX,
        "dfile": texts.ASK_NEW_DG_FILE,
        "codes": texts.ASK_NEW_DG_CODES,
    }


_COMMON_EDIT_FIELDS = {"name", "description", "price", "photo", "ai"}
_PHYSICAL_EDIT_FIELDS = {"stock", "weight", "delivery", "returns"}
_DIGITAL_EDIT_FIELDS = {"dinstr", "dmax"}


def _allowed_edit_fields(product) -> set[str]:
    """فیلدهایِ قابلِ ویرایش بر اساسِ نوعِ محصول (callbackِ جعلی/کهنه برایِ نوعِ دیگه رد می‌شه)."""
    if product.kind == "digital":
        fields = _COMMON_EDIT_FIELDS | _DIGITAL_EDIT_FIELDS
        extra = {"code_pool": {"codes"}, "file": {"dfile"}, "link": {"dlink"}}.get(product.digital_delivery or "", set())
        return fields | extra
    return _COMMON_EDIT_FIELDS | _PHYSICAL_EDIT_FIELDS


@router.callback_query(F.data.startswith("product_edit_field:"))
async def cb_product_edit_field(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    shop_bot = await _require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return

    _, product_id, field = callback.data.split(":")
    product = await product_service.get_owned_by_id(session, int(product_id), shop_bot.id)
    if product is None or field not in _field_prompts():
        await callback.answer(texts.GENERIC_ERROR, show_alert=True)
        return
    if field not in _allowed_edit_fields(product):
        await callback.answer(texts.EDIT_NOT_FOR_KIND, show_alert=True)
        return

    await callback.answer()
    await state.update_data(edit_product_id=int(product_id), edit_field=field)
    await state.set_state(ProductStates.waiting_edit_field_value)
    await callback.message.answer(_field_prompts()[field])


@router.message(ProductStates.waiting_edit_field_value, F.photo)
async def edit_product_value_photo(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    if data.get("edit_field") != "photo":
        await message.answer(_field_prompts().get(data.get("edit_field"), texts.GENERIC_ERROR))
        return
    await _apply_field_edit(message, state, session, message.photo[-1].file_id)


_SKIP_WORD = "رد شدن"
_NULLABLE_TEXT_FIELDS = {"delivery", "returns", "ai", "dinstr"}


@router.message(ProductStates.waiting_edit_field_value, F.text)
async def edit_product_value_text(message: Message, state: FSMContext, session: AsyncSession, bot_manager=None) -> None:
    data = await state.get_data()
    field = data["edit_field"]
    raw = message.text.strip()

    if field == "price":
        price = parse_price_toman(message.text)
        if price is None:
            await message.answer(texts.INVALID_PRICE)
            return
        await _apply_field_edit(message, state, session, price)
        return

    if field == "stock":
        if raw == _SKIP_WORD:
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

    if field == "weight":
        if raw == _SKIP_WORD:
            await _apply_field_edit(message, state, session, None)
            return
        weight = parse_nonneg_int(raw, allow_zero=False, max_value=10_000_000)
        if weight is None:
            await message.answer(texts.INVALID_WEIGHT)
            return
        await _apply_field_edit(message, state, session, weight)
        return

    if field == "dmax":
        if raw == _SKIP_WORD:
            await _apply_field_edit(message, state, session, None)
            return
        limit = parse_nonneg_int(raw, allow_zero=False, max_value=1000)
        if limit is None:
            await message.answer(texts.DG_INVALID_MAX)
            return
        await _apply_field_edit(message, state, session, limit)
        return

    if field == "dlink":
        link = digital_service.validate_link(raw)
        if link is None:
            await message.answer(texts.DG_INVALID_LINK)
            return
        await _apply_field_edit(message, state, session, link)
        return

    if field in _NULLABLE_TEXT_FIELDS:
        await _apply_field_edit(message, state, session, None if raw == _SKIP_WORD else raw)
        return

    if field == "codes":
        await _apply_codes_edit(message, state, session, bot_manager, message.text)
        return

    if field in ("photo", "dfile"):
        await message.answer(_field_prompts()[field])
        return

    await _apply_field_edit(message, state, session, raw)


@router.message(ProductStates.waiting_edit_field_value, F.document)
async def edit_product_value_document(message: Message, state: FSMContext, session: AsyncSession, bot_manager=None) -> None:
    data = await state.get_data()
    field = data.get("edit_field")
    if field == "dfile":
        if (message.document.file_size or 0) > digital_service.MAX_DIGITAL_FILE_BYTES:
            await message.answer(texts.DG_FILE_TOO_BIG)
            return
        await _apply_field_edit(message, state, session, (message.document.file_id, (message.document.file_name or "file")[:255]))
        return
    if field == "codes":
        document = message.document
        name = (document.file_name or "").lower()
        if (document.file_size or 0) > 1024 * 1024 or not name.endswith(".txt"):
            await message.answer(texts.DG_CODES_BAD_FILE)
            return
        try:
            buffer = await message.bot.download(document.file_id)
            content = buffer.read().decode("utf-8-sig", errors="replace")
        except Exception:
            logger.exception("دانلودِ فایلِ کدها ناموفق بود.")
            await message.answer(texts.DG_CODES_BAD_FILE)
            return
        await _apply_codes_edit(message, state, session, bot_manager, content)
        return
    await message.answer(_field_prompts().get(field, texts.GENERIC_ERROR))


async def _apply_codes_edit(message: Message, state: FSMContext, session: AsyncSession, bot_manager, content: str) -> None:
    """افزودنِ کد به استخرِ یه محصولِ code_pool؛ بعدش سفارش‌هایِ تاییدشده‌یِ منتظر (کدِ کم بود) تحویل داده می‌شن."""
    shop_bot = await _require_shop_bot(message, session)
    if shop_bot is None:
        await state.clear()
        return
    data = await state.get_data()
    product = await product_service.get_owned_by_id(session, data["edit_product_id"], shop_bot.id)
    if product is None or not digital_service.is_code_pool(product):
        await state.clear()
        await message.answer(texts.EDIT_NOT_FOR_KIND)
        return
    codes, ignored = digital_service.parse_codes(content)
    if not codes:
        await message.answer(texts.DG_CODES_EMPTY)
        return

    await state.clear()  # قبل از I/O: دابل‌ارسال = یک بار (و کدِ تکراری هم به‌هرحال نادیده‌ست)
    added, duplicates = await digital_service.add_codes(session, product, codes)
    delivered = waiting = 0
    if added:
        delivered, waiting = await digital_service.deliver_pending_for_product(session, product, bot_manager, shop_bot.id, message.bot)
    available = await digital_service.sync_pool_stock(session, product)
    await message.answer(texts.dg_codes_result(added, duplicates, ignored, available))
    note = texts.digital_pending_delivered_note(delivered, waiting)
    if note:
        await message.answer(note)
    await message.answer(texts.product_detail_text(product), reply_markup=keyboards.product_detail_keyboard(product.id))


_FIELD_ATTR = {
    "name": "name",
    "description": "description",
    "price": "price_toman",
    "photo": "photo_file_id",
    "stock": "stock_quantity",
    "weight": "weight_grams",
    "delivery": "delivery_note",
    "returns": "return_policy",
    "ai": "ai_instructions",
    "dlink": "digital_link",
    "dinstr": "digital_instructions",
    "dmax": "digital_max_downloads",
}


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
    if field not in _allowed_edit_fields(product):
        await state.clear()
        await message.answer(texts.EDIT_NOT_FOR_KIND)
        return
    if field == "dinstr" and product.digital_delivery == "text" and not value:
        await message.answer(texts.DG_TEXT_CANNOT_BE_EMPTY)
        return

    if field == "dfile":
        file_id, file_name = value
        product.digital_file_id = file_id
        product.digital_file_name = file_name
        product.digital_file_shop_file_id = None  # file_idِ قدیمیِ رباتِ فروشگاه دیگه معتبر نیست
    else:
        setattr(product, _FIELD_ATTR[field], value)
    await session.flush()

    await state.clear()
    await message.answer(texts.product_field_updated(field))
    await message.answer(texts.product_detail_text(product), reply_markup=keyboards.product_detail_keyboard(product.id))
