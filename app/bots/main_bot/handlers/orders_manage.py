"""«🧾 مدیریتِ سفارش‌ها (جاری)» در پنلِ فروشگاه‌دار (W5): یک‌جا دیدنِ همه‌یِ سفارش‌هایِ باز (اولویت: چیزهایی که تصمیم می‌خوان)،
با فیلترِ «نیازمندِ اقدام»، صفحه‌بندی و باز کردنِ هر سفارش با *همان دکمه‌هایِ اقدامِ* اعلانِ اصلی (تایید/رد رسید، شروعِ پردازش،
ارسال، استرداد، پیام به مشتری…). هیچ منطقِ تصمیمِ تازه‌ای اینجا نیست؛ همه‌یِ اقدام‌ها از هندلرهایِ موجود (با قفل/ایدمپوتنسی/
کنترلِ مالکیت) می‌گذرن. شناسه‌ها از callback_data می‌آیند ⇒ همیشه با `_load_rows` (محدود به همین فروشگاه) راستی‌آزمایی می‌شن."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.common.wizard_nav import page_label
from app.bots.main_bot import keyboards, texts
from app.bots.main_bot.handlers import order_ops
from app.bots.main_bot.handlers.owner_common import require_shop_bot, require_shop_bot_cb, safe_edit
from app.bots.shop_bot import texts as shop_texts
from app.database.models import Customer
from app.services import order_payment_service, order_state, order_transition_service, orders_manage_service as oms
from app.services.identity_service import display_user
from app.utils.jalali import format_jalali_datetime
from app.utils.validators import fa_number, format_phone_display, format_toman

BTN_ORDERS_MANAGE = "🧾 مدیریتِ سفارش‌ها (جاری)"

router = Router(name="orders_manage")

EMPTY_ALL = "🎉 الان هیچ سفارشِ جاری‌ای نداری. هر سفارشِ تازه که بیاد، همین‌جا هم دیده می‌شه."
EMPTY_ACTION = "✅ هیچ سفارشی منتظرِ اقدامِ تو نیست."
STALE = "این سفارش دیگه جاری نیست یا پیدا نشد؛ فهرست رو تازه کن."

_STATUS_ICON = {
    order_state.RECEIPT_SUBMITTED: "🧾",
    order_state.PENDING: "⏳",
    order_state.REFUND_PENDING: "↩️",
    order_state.PAID: "💰",
    order_state.CONFIRMED: "✅",
    order_state.PROCESSING: "📦",
    order_state.SHIPPED: "🚚",
    order_state.AWAITING_PAYMENT: "💳",
}


def list_text(groups_all: list, flt: str, page: int, total_pages: int, shown_count: int) -> str:
    counts = oms.status_counts(groups_all)
    action = sum(n for s, n in counts.items() if s in oms.NEEDS_ACTION)
    lines = [f"🧾 سفارش‌هایِ جاری: {fa_number(len(groups_all))} مورد — منتظرِ اقدامِ تو: {fa_number(action)} مورد"]
    breakdown = [
        f"{_STATUS_ICON.get(s, '•')} {texts.order_status_label(s)}: {fa_number(counts[s])}" for s in oms.CURRENT_STATUSES if counts.get(s)
    ]
    if breakdown:
        lines.append("\n".join(breakdown))
    if flt == oms.FILTER_ACTION:
        lines.append("\n🔎 فیلتر: فقط منتظرِ اقدام")
    if total_pages > 1:
        lines.append(f"\n{page_label(page - 1, total_pages)}")
    lines.append("\nبرایِ مدیریتِ هر سفارش رویش بزن 👇")
    return "\n".join(lines)


def _customer_names(customers: dict[int, Customer], rows: list) -> str:
    customer = customers.get(rows[0].customer_id)
    return display_user(customer) if customer is not None else "بی‌نام"


def list_keyboard(groups_page: list, customers: dict[int, Customer], flt: str, page: int, total_pages: int) -> InlineKeyboardMarkup:
    rows_kb: list[list[InlineKeyboardButton]] = []
    for rows in groups_page:
        status = oms.group_status(rows)
        total = order_transition_service.group_total_toman(rows)
        label = f"{_STATUS_ICON.get(status, '•')} {shop_texts.order_code(rows)} · {format_toman(total)} · {_customer_names(customers, rows)}"
        rows_kb.append([InlineKeyboardButton(text=label[:60], callback_data=f"om_v:{oms.group_key_of(rows[0])}")])
    nav: list[InlineKeyboardButton] = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="◀️ قبلی", callback_data=f"om_l:{flt}:{page - 1}"))
    if page < total_pages:
        nav.append(InlineKeyboardButton(text="بعدی ▶️", callback_data=f"om_l:{flt}:{page + 1}"))
    if nav:
        rows_kb.append(nav)
    other = oms.FILTER_ALL if flt == oms.FILTER_ACTION else oms.FILTER_ACTION
    other_label = "📋 نمایشِ همه" if flt == oms.FILTER_ACTION else "🔔 فقط منتظرِ اقدام"
    rows_kb.append(
        [
            InlineKeyboardButton(text=other_label, callback_data=f"om_l:{other}:1"),
            InlineKeyboardButton(text="🔄 تازه‌سازی", callback_data=f"om_l:{flt}:{page}"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows_kb)


async def _list_payload(session: AsyncSession, shop_bot, flt: str, page: int) -> tuple[str, InlineKeyboardMarkup | None]:
    groups_all = await oms.load_current_groups(session, shop_bot.id)
    shown = oms.apply_filter(groups_all, flt)
    if not groups_all:
        return EMPTY_ALL, keyboards.empty_screen_keyboard()
    page_groups, page, total_pages = oms.paginate(shown, page)
    customer_ids = {rows[0].customer_id for rows in page_groups}
    customers = {cid: await session.get(Customer, cid) for cid in customer_ids}
    if not shown:
        text = f"{list_text(groups_all, flt, 1, 1, 0)}\n\n{EMPTY_ACTION}"
    else:
        text = list_text(groups_all, flt, page, total_pages, len(shown))
    return text, list_keyboard(page_groups, {k: v for k, v in customers.items() if v is not None}, flt, page, total_pages)


@router.message(F.text == BTN_ORDERS_MANAGE)
async def open_orders_manage(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    shop_bot = await require_shop_bot(message, session)
    if shop_bot is None:
        return
    text, keyboard = await _list_payload(session, shop_bot, oms.FILTER_ALL, 1)
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("om_l:"))
async def orders_list_page(callback: CallbackQuery, session: AsyncSession) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    parsed = oms.parse_list_callback(callback.data)
    if parsed is None:
        await callback.answer(STALE, show_alert=True)
        return
    flt, page = parsed
    text, keyboard = await _list_payload(session, shop_bot, flt, page)
    await callback.answer()
    await safe_edit(callback, text, keyboard)


def _detail_text(rows: list, customer: Customer | None) -> str:
    status = oms.group_status(rows)
    first = rows[0]
    lines = [f"🧾 سفارش {shop_texts.order_code(rows)} — {texts.order_status_label(status)}"]
    if customer is not None:
        lines.append(f"👤 مشتری: {display_user(customer)}")
    if first.created_at is not None:
        lines.append(f"🕒 ثبت: {format_jalali_datetime(first.created_at)}")
    lines.append("")
    lines.append("🛒 اقلام:")
    for row in rows:
        lines.append(f"• {(row.summary or '').replace(' (از سبدِ خرید)', '')}")
    if first.shipping_method_name:
        fee = first.shipping_fee_toman or 0
        lines.append(f"🚚 ارسال ({first.shipping_method_name}): {'رایگان' if fee == 0 else format_toman(fee)}")
    lines.append(f"💰 جمعِ کل: {format_toman(order_transition_service.group_total_toman(rows))}")
    if first.checkout_answers:
        lines.append(f"\n📝 اطلاعاتِ مشتری:\n{first.checkout_answers[:900]}")
    else:
        if first.customer_phone:
            lines.append(f"📞 {format_phone_display(first.customer_phone) or first.customer_phone}")
        if first.customer_address:
            lines.append(f"📍 {first.customer_address[:400]}")
    if first.tracking_code:
        lines.append(f"📮 کدِ رهگیری: {first.tracking_code}")
    return "\n".join(lines)[:3900]


async def _action_keyboard(session: AsyncSession, shop_bot, key: str, rows: list) -> InlineKeyboardMarkup:
    """همان دکمه‌هایِ اعلانِ اصلیِ هر وضعیت؛ هیچ منطقِ تازه‌ای نیست."""
    status = oms.group_status(rows)
    keyboard: InlineKeyboardMarkup | None = None
    if status == order_state.RECEIPT_SUBMITTED:
        payment = await order_payment_service.get_active_payment(session, shop_bot.id, key)
        if payment is not None and payment.status == order_payment_service.P_SUBMITTED:
            keyboard = keyboards.receipt_review_keyboard(payment.id, key)
    elif status == order_state.PENDING:
        keyboard = keyboards.order_notification_keyboard(rows[0].id) if len(rows) == 1 and key.startswith("o") else keyboards.cart_group_notification_keyboard(key)
    if keyboard is None:
        keyboard = keyboards.order_group_actions_keyboard(key, status)
    markup_rows = [list(r) for r in keyboard.inline_keyboard] if keyboard is not None else []
    markup_rows.append([InlineKeyboardButton(text="⬅️ بازگشت به فهرست", callback_data=f"om_l:{oms.FILTER_ALL}:1")])
    return InlineKeyboardMarkup(inline_keyboard=markup_rows)


@router.callback_query(F.data.startswith("om_v:"))
async def order_open(callback: CallbackQuery, session: AsyncSession) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    key = (callback.data or "").split(":", 1)[1] if ":" in (callback.data or "") else ""
    rows = await order_ops._load_rows(session, shop_bot, key) if key else []
    if not oms.is_current_group(rows):
        await callback.answer(STALE, show_alert=True)
        return
    customer = await session.get(Customer, rows[0].customer_id)
    keyboard = await _action_keyboard(session, shop_bot, key, rows)
    await callback.answer()
    # پیامِ تازه (نه edit): فهرست سرجاش می‌مونه و دکمه‌هایِ اقدامِ اعلانِ اصلی هم همین‌جا در دسترسه
    await callback.message.answer(_detail_text(rows, customer), reply_markup=keyboard)
