"""عکسِ محصول برایِ مشتریِ رباتِ فروشگاه (W5): دکمه‌یِ «🖼» کنارِ محصولاتِ عکس‌دار در مرورِ محصولات (`cart_photo:<id>`) و درخواستِ
متنیِ «عکسِ X رو بفرست» (بدونِ AI و بدونِ هزینه). شناسه‌یِ محصول از callback می‌آید ⇒ همیشه با shop_bot همین ربات راستی‌آزمایی
می‌شه (محصولِ فروشگاهِ دیگر/غیرفعال دیده نمی‌شه)."""

from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Product, TenantMode
from app.services import product_photo_service, product_service, shop_bot_service
from app.utils.validators import format_toman

router = Router(name="shop_product_photos")

UNAVAILABLE = "این محصول دیگه موجود نیست."
NO_PHOTO = "برایِ این محصول عکسی ثبت نشده."
PHOTO_FAILED = "الان نتونستم عکس رو بفرستم؛ چند لحظه دیگه دوباره امتحان کن 🙏"
ASK_WHICH = "عکسِ کدوم محصول رو می‌خوای؟"


def card_caption(product: Product) -> str:
    lines = [f"🛍 {product.name}", f"💰 {format_toman(product.price_toman)}"]
    if product.description:
        lines.append(product.description[:600])
    available = product.stock_quantity is None or (product.stock_quantity - (product.reserved_quantity or 0)) > 0
    lines.append("✅ موجود" if available else "❌ ناموجود")
    return "\n".join(lines)


def card_keyboard(product: Product) -> InlineKeyboardMarkup:
    buttons = []
    if product.is_active:
        buttons.append(InlineKeyboardButton(text="➕ افزودن به سبد", callback_data=f"cart_add:{product.id}"))
    buttons.append(InlineKeyboardButton(text="🛒 دیدنِ سبدِ خرید", callback_data="cart_view"))
    return InlineKeyboardMarkup(inline_keyboard=[buttons])  # P22: دونادونه، نه دو ردیفِ بلند


def which_keyboard(products: list[Product]) -> InlineKeyboardMarkup:
    buttons = [InlineKeyboardButton(text=f"🖼 {p.name}"[:60], callback_data=f"cart_photo:{p.id}") for p in products[:8]]
    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]  # P22: نگارستان دونادونه
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _send_card(bot: Bot, main_bot: Bot, product: Product, chat_id: int) -> bool:
    sent = await product_photo_service.send_product_photo(
        bot, main_bot, product, chat_id, caption=card_caption(product), reply_markup=card_keyboard(product)
    )
    if not sent:
        await bot.send_message(chat_id, f"{card_caption(product)}\n\n{PHOTO_FAILED}", reply_markup=card_keyboard(product))
    return sent


@router.callback_query(F.data.startswith("cart_photo:"))
async def product_photo_button(callback: CallbackQuery, session: AsyncSession, main_bot: Bot) -> None:
    raw = (callback.data or "").split(":", 1)[1]
    shop_bot = await shop_bot_service.get_by_bot(session, callback.bot)
    product = None
    if shop_bot is not None and raw.isascii() and raw.isdecimal():
        candidate = await product_service.get_by_id(session, int(raw))
        if candidate is not None and candidate.shop_bot_id == shop_bot.id and candidate.is_active:
            product = candidate
    if product is None:
        await callback.answer(UNAVAILABLE, show_alert=True)
        return
    if not product.photo_file_id:
        await callback.answer(NO_PHOTO, show_alert=True)
        return
    await callback.answer()
    await _send_card(callback.bot, main_bot, product, callback.from_user.id)


async def maybe_handle_photo_request(message: Message, session: AsyncSession, shop_bot, main_bot: Bot) -> bool:
    """«عکسِ برنج رو بفرست» ⇒ کارتِ محصول با عکس (هزینه ۰، بدونِ AI). True یعنی پیام مصرف شد؛ در غیرِ این صورت AI جواب می‌ده."""
    if shop_bot.tenant_mode == TenantMode.CONSULTATION or not product_photo_service.looks_like_photo_request(message.text):
        return False
    products = await product_service.get_active_by_shop_bot(session, shop_bot.id)
    with_photos = product_photo_service.with_photo(products)
    if not with_photos:
        return False  # هیچ محصولی عکس ندارد ⇒ AI با اطلاعاتِ موجود جواب بده
    matched = product_photo_service.match_products(message.text or "", with_photos)
    if matched:
        for product in matched:
            await _send_card(message.bot, main_bot, product, message.chat.id)
        return True
    await message.answer(ASK_WHICH, reply_markup=which_keyboard(with_photos))
    return True
