from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

_PAGE_SIZE = 8


def _paginate(items: list, page: int) -> tuple[list, int, int]:
    total_pages = max(1, (len(items) + _PAGE_SIZE - 1) // _PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    start = page * _PAGE_SIZE
    return items[start : start + _PAGE_SIZE], page, total_pages


def customer_main_keyboard(tenant_mode=None, support_enabled: bool = False) -> ReplyKeyboardMarkup:
    """کیبوردِ منوی مشتری (C1)، مود-آگاه: فروشگاهی = محصولات/سبد؛ مشاوره‌ای = خدمات (بدونِ سبد/خرید).
    «📞 ارتباط با پشتیبانی» فقط وقتی فروشگاه‌دار فعالش کرده."""
    from app.bots.shop_bot import texts  # لازیم؛ texts به cart_edit_service وابسته‌ست

    value = tenant_mode.value if hasattr(tenant_mode, "value") else tenant_mode
    if value == "consultation":
        # P21-D (F5): پیگیریِ وضعیتِ درخواست‌ها برایِ مشاوره هم معنا دارد («مراجعه‌ام تایید شد؟»)
        rows = [[KeyboardButton(text=texts.BTN_SERVICES)], [KeyboardButton(text=texts.BTN_MY_ORDERS)]]
    else:
        rows = [[KeyboardButton(text=texts.BTN_PRODUCTS), KeyboardButton(text=texts.BTN_CART)], [KeyboardButton(text=texts.BTN_MY_ORDERS)]]
    if support_enabled:
        rows.append([KeyboardButton(text=texts.BTN_SUPPORT)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def support_link_keyboard(username: str | None) -> InlineKeyboardMarkup | None:
    if not username:
        return None
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💬 پیام در تلگرام", url=f"https://t.me/{username}")]])

def order_customer_confirmation_keyboard(order_id: int) -> InlineKeyboardMarkup:
    """
    زیرِ پیامِ «این چیزیه که برات ثبت می‌کنم» به خودِ مشتری نشون داده می‌شه
    (بازطراحیِ سفارش‌گیری) — نه فروشگاه‌دار. کاملاً جدا از کیبوردِ
    order_notification_keyboardِ main_bot (که برای فروشگاه‌دار و بعدِ تاییدِ
    همین مشتریه)، هم از نظرِ callback_data (پیشوندِ cust_) هم چون توی
    دیسپچرِ متفاوتی (شاپ‌بات) هندل می‌شه.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ بله، درسته", callback_data=f"cust_confirm_order:{order_id}")],
            [InlineKeyboardButton(text="❌ نه، اشتباهه", callback_data=f"cust_cancel_order:{order_id}")],
        ]
    )


def online_payment_keyboard(pay_url: str) -> InlineKeyboardMarkup:
    """فازِ ۳: زیرِ پیامِ پیشنهادِ پرداختِ آنلاین به مشتری، بعدِ تاییدِ سفارش —
    فقط وقتی فروشگاه bale_provider_tokenِ خودش رو تنظیم کرده باشه نشون داده
    می‌شه. مشابهِ bale_pay_keyboardِ main_bot ولی جدا، چون توی ماژولِ
    keyboardsِ متفاوتی (شاپ‌بات) هست."""
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💳 پرداختِ آنلاین", url=pay_url)]])


# =============================================================================
# سبدِ خریدِ واقعی (فازِ ۳)
# =============================================================================
def products_browse_keyboard(products, page: int = 0) -> InlineKeyboardMarkup:
    page_items, page, total_pages = _paginate(list(products), page)
    rows = []
    for p in page_items:
        row = [InlineKeyboardButton(text=f"{p.name} — {p.price_toman:,} تومان", callback_data=f"cart_add:{p.id}")]
        if getattr(p, "photo_file_id", None):  # W5: محصولِ عکس‌دار دکمه‌یِ «🖼» دارد
            row.append(InlineKeyboardButton(text="🖼", callback_data=f"cart_photo:{p.id}"))
        rows.append(row)
    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="◀️ قبلی", callback_data=f"cart_browse:{page - 1}"))
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton(text="بعدی ▶️", callback_data=f"cart_browse:{page + 1}"))
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="🛒 دیدنِ سبدِ خرید", callback_data="cart_view")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cart_view_keyboard(items_with_products) -> InlineKeyboardMarkup:
    """items_with_products: لیستی از (CartItem, Product). هر ردیف یه آیتمه، با
    دکمه‌هایِ ➖/➕/🗑 کنارش."""
    rows = []
    for item, product in items_with_products:
        rows.append(
            [
                InlineKeyboardButton(text=f"{product.name} × {item.quantity}", callback_data="noop"),
                InlineKeyboardButton(text="➖", callback_data=f"cart_dec:{item.id}"),
                InlineKeyboardButton(text="➕", callback_data=f"cart_inc:{item.id}"),
                InlineKeyboardButton(text="🗑", callback_data=f"cart_remove:{item.id}"),
            ]
        )
    if items_with_products:
        rows.append([InlineKeyboardButton(text="🛍 افزودنِ محصولِ دیگه", callback_data="cart_browse:0")])
        rows.append([InlineKeyboardButton(text="✅ نهایی‌کردنِ سفارش", callback_data="cart_checkout_start")])
    else:
        rows.append([InlineKeyboardButton(text="🛍 مرورِ محصولات", callback_data="cart_browse:0")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def checkout_confirm_keyboard(show_code_button: bool = False, code_applied: bool = False) -> InlineKeyboardMarkup:
    """بدونِ آرگومان دقیقاً مثلِ قبله. show_code_button: فروشگاه یه کمپینِ کددارِ فعال
    داره؛ code_applied: مشتری قبلاً یه کدِ معتبر زده (دکمه می‌شه «تغییر/حذف»)."""
    rows = [[InlineKeyboardButton(text="✅ ثبتِ نهایی", callback_data="cart_checkout_confirm")]]
    if show_code_button or code_applied:
        label = "🎟 تغییر/حذفِ کدِ تخفیف" if code_applied else "🎟 کد تخفیف دارم"
        rows.append([InlineKeyboardButton(text=label, callback_data="cart_discount_code")])
    rows.append([InlineKeyboardButton(text="❌ انصراف", callback_data="cart_checkout_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cart_ai_clear_confirm_keyboard(cart_fingerprint: str) -> InlineKeyboardMarkup:
    """تاییدِ خالی‌کردنِ کلِ سبد (که AI ازش تشخیص داده). اثرانگشتِ سبد توی callback_data
    هست تا اگه مشتری ساعتی بعد روی یه پیامِ قدیمی بزنه و سبدش از اون موقع عوض شده باشه،
    سبدِ تازه‌اش ناخواسته پاک نشه."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🗑 آره، خالی کن", callback_data=f"cart_ai_clear:{cart_fingerprint}"),
                InlineKeyboardButton(text="↩️ نه، نگهش دار", callback_data="cart_ai_keep"),
            ]
        ]
    )


# =============================================================================
# «📦 سفارش‌هایِ من» (W2 · C4)
# =============================================================================
def my_orders_list_keyboard(keys: list[str], page: int, total_groups: int, page_size: int = 5, first_index: int = 1) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=f"🔎 سفارشِ {first_index + i}", callback_data=f"myord_view:{key}")] for i, key in enumerate(keys)]
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️ قبلی", callback_data=f"myord_page:{page - 1}"))
    if (page + 1) * page_size < total_groups:
        nav.append(InlineKeyboardButton(text="بعدی ➡️", callback_data=f"myord_page:{page + 1}"))
    if nav:
        rows.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def my_order_card_keyboard(key: str, *, can_invoice: bool, can_cancel: bool, digital_order_ids: list[int], page: int = 0, can_pay: bool = False) -> InlineKeyboardMarkup:
    rows = []
    if can_pay:
        rows.append([InlineKeyboardButton(text="💳 پرداخت", callback_data=f"pm_menu:{key}")])
    if can_invoice:
        rows.append([InlineKeyboardButton(text="📄 فاکتور", callback_data=f"myord_inv:{key}")])
    for order_id in digital_order_ids[:5]:
        rows.append([InlineKeyboardButton(text="📥 دریافتِ دوباره", callback_data=f"dl_again:{order_id}")])
    if can_cancel:
        rows.append([InlineKeyboardButton(text="❌ لغوِ سفارش", callback_data=f"myord_cancel:{key}")])
    rows.append([InlineKeyboardButton(text="⬅️ برگشت به فهرست", callback_data=f"myord_page:{page}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cart_suggest_keyboard(products: list, show_cart_row: bool = False) -> InlineKeyboardMarkup:
    """C2: دکمه‌هایِ زیرِ جوابِ AI — شناسه‌ها فقط از خودِ محصولاتِ فروشگاه‌اند (نه از متنِ AI)."""
    rows = [
        [InlineKeyboardButton(text=f"➕ افزودنِ {product.name[:28]} به سبد", callback_data=f"cart_add:{product.id}")]
        for product in products[:3]
    ]
    if show_cart_row:
        rows.append(
            [
                InlineKeyboardButton(text="🛒 سبد", callback_data="cart_view"),
                InlineKeyboardButton(text="💳 تسویه", callback_data="cart_checkout_start"),
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def payment_methods_keyboard(key: str, methods: list[str]) -> InlineKeyboardMarkup:
    from app.bots.shop_bot.texts import PAY_METHOD_LABELS

    rows = [[InlineKeyboardButton(text=PAY_METHOD_LABELS[m], callback_data=f"pm_{m}:{key}")] for m in methods if m in PAY_METHOD_LABELS]
    rows.append([InlineKeyboardButton(text="❌ لغوِ سفارش", callback_data=f"myord_cancel:{key}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def receipt_keyboard(key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📎 ارسالِ رسید", callback_data=f"pay_receipt:{key}")],
            [InlineKeyboardButton(text="⬅️ روشِ دیگه", callback_data=f"pm_menu:{key}")],
            [InlineKeyboardButton(text="❌ لغوِ سفارش", callback_data=f"myord_cancel:{key}")],
        ]
    )


def online_pay_keyboard(pay_url: str, key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 رفتن به صفحه‌یِ پرداخت", url=pay_url)],
            [InlineKeyboardButton(text="⬅️ روشِ دیگه", callback_data=f"pm_menu:{key}")],
            [InlineKeyboardButton(text="❌ لغوِ سفارش", callback_data=f"myord_cancel:{key}")],
        ]
    )

