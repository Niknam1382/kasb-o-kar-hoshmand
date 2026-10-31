"""متن‌ها و کیبوردهایِ چک‌اوتِ مرحله‌ایِ سبد (W5 · C3). منطقِ تصمیم در handlers/checkout.py است.

callback_dataها (همه ≤۶۴ بایت): ck_back، ck_skip، ck_name_ok، ck_phone_saved، ck_addr_sel:<id>، ck_addr_new،
ck_addr_mng، ck_addr_def:<id>، ck_addr_del:<id>، ck_addr_pick، ck_ship:<id>، ck_edit:<field>؛ انصراف همان cart_checkout_cancel."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bots.common.wizard_nav import with_nav
from app.bots.shop_bot import texts
from app.services import address_book_service
from app.utils.validators import format_toman

CANCEL_CB = "cart_checkout_cancel"
BACK_CB = "ck_back"
SKIP_CB = "ck_skip"

STALE_STEP = "این مرحله منقضی شده 🙏 لطفاً از «🛒 سبدِ خرید» دوباره شروع کن."
CHECKOUT_RESTART_HINT = "هنوز چیزی ثبت نشده؛ سبدت دست‌نخورده‌ست."
ASK_NAME_PLAIN = "👤 نامِ تحویل‌گیرنده رو بنویس (کسی که سفارش رو تحویل می‌گیره):"
NAME_INVALID = "نام باید ۲ تا ۶۰ حرف باشه و رقم/لینک/@ نداشته باشه 🙏 دوباره بنویس:"
ASK_PHONE = "📱 شماره‌یِ موبایلِ تحویل‌گیرنده رو بنویس (مثلاً 09121234567). می‌تونی «مخاطب» (Contact) هم بفرستی:"
PHONE_INVALID = "این شماره معتبر نیست 🙏 یه موبایلِ ایرانی بنویس (مثلاً 09121234567):"
CONTACT_NOT_YOURS = "فقط شماره‌یِ خودت رو می‌تونی با «مخاطب» بفرستی؛ یا شماره رو تایپ کن."
ASK_ADDRESS_PICK = "📍 آدرسِ تحویل رو انتخاب کن:"
ASK_PROVINCE = "🗺 استانِ محلِ تحویل؟"
ASK_CITY = "🏙 شهر؟"
ASK_ADDRESS_TEXT = "🏠 آدرسِ کامل رو بنویس (خیابان، کوچه، پلاک، واحد):"
ASK_POSTAL = "📮 کدپستیِ ۱۰رقمی (اختیاری):"
PLACE_INVALID = "این مورد باید ۲ تا ۴۰ حرف باشه و رقم/لینک/@ نداشته باشه 🙏 دوباره بنویس:"
ADDRESS_INVALID = "آدرس باید بینِ ۸ تا ۴۰۰ حرف باشه 🙏 کامل‌تر بنویس:"
POSTAL_INVALID = "کدپستی باید ۱۰ رقم باشه (مثلاً 1234567890) 🙏 دوباره بنویس یا «⏭ رد کردن» رو بزن:"
ADDRESS_LIMIT_REACHED = (
    f"حداکثر {address_book_service.MAX_ADDRESSES} آدرس می‌تونی ذخیره کنی. یکی رو از «⚙️ مدیریتِ آدرس‌ها» حذف کن، بعد آدرسِ تازه بساز."
)
ADDRESS_GONE = "این آدرس دیگه وجود نداره؛ یکی از فهرست رو انتخاب کن."
ADDRESS_DELETED = "🗑 آدرس حذف شد."
ADDRESS_DEFAULTED = "⭐ آدرسِ پیش‌فرض عوض شد."
ASK_SHIPPING = "🚚 روشِ ارسال رو انتخاب کن:"
SHIPPING_GONE = "این روشِ ارسال دیگه فعال نیست؛ یکی از فهرست رو انتخاب کن."
ASK_NOTE = "📝 اگه توضیحی برایِ سفارش داری بنویس (اختیاری):"
NOTE_TOO_LONG = "توضیح حداکثر ۳۰۰ حرف باشه 🙏 کوتاه‌ترش کن یا «⏭ رد کردن» رو بزن:"
ANSWER_TOO_LONG = "جواب حداکثر ۳۰۰ حرف باشه 🙏 کوتاه‌ترش کن:"
ADDRESS_NEEDS_PHONE_HINT = "ابتدا باید شماره‌ات رو بدی."
PHYSICAL_NO_ADDRESS = "برایِ ارسالِ کالایِ فیزیکی آدرس لازمه."


def name_prompt(prefilled: str | None) -> str:
    if prefilled:
        return f"👤 نامِ تحویل‌گیرنده «{prefilled}» درسته؟ اگه درسته دکمه‌یِ تایید رو بزن، وگرنه نامِ درست رو بنویس:"
    return ASK_NAME_PLAIN


def name_keyboard(prefilled: str | None) -> InlineKeyboardMarkup:
    rows = []
    if prefilled:
        rows.append([InlineKeyboardButton(text="✅ درسته", callback_data="ck_name_ok")])
    return with_nav(rows, cancel_cb=CANCEL_CB)


def phone_keyboard(saved_phone_display: str | None) -> InlineKeyboardMarkup:
    rows = []
    if saved_phone_display:
        rows.append([InlineKeyboardButton(text=f"✅ همین شماره: {saved_phone_display}", callback_data="ck_phone_saved")])
    return with_nav(rows, back_cb=BACK_CB, cancel_cb=CANCEL_CB)


def address_pick_keyboard(addresses) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=address_book_service.short_label(a), callback_data=f"ck_addr_sel:{a.id}")] for a in addresses
    ]
    rows.append([InlineKeyboardButton(text="➕ آدرسِ جدید", callback_data="ck_addr_new")])
    if addresses:
        rows.append([InlineKeyboardButton(text="⚙️ مدیریتِ آدرس‌ها", callback_data="ck_addr_mng")])
    return with_nav(rows, back_cb=BACK_CB, cancel_cb=CANCEL_CB)


def address_manage_text(addresses) -> str:
    if not addresses:
        return "هنوز آدرسی ذخیره نکردی."
    lines = ["⚙️ آدرس‌هایِ ذخیره‌شده:\n"]
    for index, a in enumerate(addresses, start=1):
        star = " ⭐ (پیش‌فرض)" if a.is_default else ""
        lines.append(f"{index}) {address_book_service.format_address(a)}{star}")
    return "\n".join(lines)


def address_manage_keyboard(addresses) -> InlineKeyboardMarkup:
    rows = []
    for index, a in enumerate(addresses, start=1):
        row = []
        if not a.is_default:
            row.append(InlineKeyboardButton(text=f"⭐ پیش‌فرضِ {index}", callback_data=f"ck_addr_def:{a.id}"))
        row.append(InlineKeyboardButton(text=f"🗑 حذفِ {index}", callback_data=f"ck_addr_del:{a.id}"))
        rows.append(row)
    rows.append([InlineKeyboardButton(text="⬅️ برگشت به انتخابِ آدرس", callback_data="ck_addr_pick")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def shipping_keyboard(options: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    """options: [(method_id, برچسبِ آماده)]."""
    rows = [[InlineKeyboardButton(text=label[:60], callback_data=f"ck_ship:{mid}")] for mid, label in options]
    return with_nav(rows, back_cb=BACK_CB, cancel_cb=CANCEL_CB)


def shipping_option_label(method, fee_toman: int) -> str:
    fee = "رایگان" if fee_toman == 0 else format_toman(fee_toman)
    eta = f" · {method.eta_text}" if method.eta_text else ""
    return f"{method.name} — {fee}{eta}"


def nav_keyboard(*, back: bool = True, skip: bool = False) -> InlineKeyboardMarkup:
    return with_nav(None, back_cb=BACK_CB if back else None, skip_cb=SKIP_CB if skip else None, cancel_cb=CANCEL_CB)


def preview_text(items, qa_pairs: list[tuple[str, str]], offer, ship_name: str | None, ship_fee: int, grand_total: int) -> str:
    lines = [texts.cart_summary(items)]
    if offer is not None:
        lines.append(texts.discount_block(offer))
    if ship_name:
        fee = "رایگان" if ship_fee == 0 else format_toman(ship_fee)
        lines.append(f"🚚 ارسال ({ship_name}): {fee}")
        lines.append(f"💳 مبلغِ قابلِ پرداخت: {format_toman(grand_total)}")
    lines.append("")
    for question, answer in qa_pairs:
        lines.append(f"❔ {question}\n✏️ {answer}")
    lines.append("\nثبت بشه؟")
    return "\n".join(lines)


def preview_keyboard(
    *, show_code_button: bool, code_applied: bool, physical: bool, ship_choice: bool
) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="✅ ثبتِ نهایی", callback_data="cart_checkout_confirm")]]
    edit = [
        InlineKeyboardButton(text="✏️ نام", callback_data="ck_edit:name"),
        InlineKeyboardButton(text="✏️ موبایل", callback_data="ck_edit:phone"),
    ]
    rows.append(edit)
    if physical:
        row = [InlineKeyboardButton(text="✏️ آدرس", callback_data="ck_edit:addr")]
        if ship_choice:
            row.append(InlineKeyboardButton(text="✏️ ارسال", callback_data="ck_edit:ship"))
        rows.append(row)
    if show_code_button or code_applied:
        label = "🎟 تغییر/حذفِ کدِ تخفیف" if code_applied else "🎟 کد تخفیف دارم"
        rows.append([InlineKeyboardButton(text=label, callback_data="cart_discount_code")])
    rows.append([InlineKeyboardButton(text="❌ انصراف", callback_data=CANCEL_CB)])
    return InlineKeyboardMarkup(inline_keyboard=rows)
