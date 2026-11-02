from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from app.utils.validators import fa_grouped

from app.bots.common.wizard_nav import page_label

_PAGE_SIZE = 8


def _chunks(items: list, size: int = 2, max_label: int = 0) -> list[list]:
    """چینشِ دونادونه (P22): همان ترتیب، دو دکمه در هر ردیف، باقی‌مانده تنها.

    چرا ردیف‌هایِ تک‌دکمه‌ای بد است: در تلگرام هر ردیفِ تمام‌عرض یکِ خطِ کامل می‌گیرد و منو
    بلند و بی‌نظم می‌شود؛ دو دکمه در هر خط کوتاه‌تر و قابل‌پیداکردن‌تر است.
    `max_label` ⇒ برچسبِ بلندتر از آن تنها می‌ماند، چون تلگرام دکمهٔ تنگ را با «…» می‌بُرد
    (مثلاً «🤝 پرداختِ دستی/هماهنگی با فروشگاه»).
    """
    rows: list[list] = []
    pending: list = []
    for item in items:
        if len(pending) == size:
            rows.append(pending)
            pending = []
        if max_label and len(getattr(item, "text", "") or "") > max_label:
            if pending:
                rows.append(pending)
                pending = []
            rows.append([item])
        else:
            pending.append(item)
    if pending:
        rows.append(pending)
    return rows


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
        # P21-D (F6): پیگیریِ وضعیتِ درخواست‌ها برایِ مشاوره هم معنا دارد («مراجعه‌ام تایید شد؟»)
        buttons = [KeyboardButton(text=texts.BTN_SERVICES), KeyboardButton(text=texts.BTN_MY_ORDERS)]
    else:
        buttons = [
            KeyboardButton(text=texts.BTN_PRODUCTS),
            KeyboardButton(text=texts.BTN_CART),
            KeyboardButton(text=texts.BTN_MY_ORDERS),
        ]
    if support_enabled:
        buttons.append(KeyboardButton(text=texts.BTN_SUPPORT))
    return ReplyKeyboardMarkup(keyboard=_chunks(buttons), resize_keyboard=True)


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
            [
                InlineKeyboardButton(text="✅ بله، درسته", callback_data=f"cust_confirm_order:{order_id}"),
                InlineKeyboardButton(text="❌ نه، اشتباهه", callback_data=f"cust_cancel_order:{order_id}"),
            ]
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
        row = [InlineKeyboardButton(text=f"{p.name} — {fa_grouped(p.price_toman)} تومان", callback_data=f"cart_add:{p.id}")]
        if getattr(p, "photo_file_id", None):  # W5: محصولِ عکس‌دار دکمه‌یِ «🖼» دارد
            row.append(InlineKeyboardButton(text="🖼", callback_data=f"cart_photo:{p.id}"))
        rows.append(row)
    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="◀️ قبلی", callback_data=f"cart_browse:{page - 1}"))
        nav.append(InlineKeyboardButton(text=page_label(page, total_pages), callback_data="noop"))
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
    داره؛ code_applied: مشتری قبلاً یه کدِ معتبر زده (دکمه می‌شه «تغییر/حذف»).
    «❌ انصراف» تنها می‌ماند تا کنارِ «ثبتِ نهایی» جا نباشد."""
    rows = [
        InlineKeyboardButton(text="✅ ثبتِ نهایی", callback_data="cart_checkout_confirm"),
    ]
    if show_code_button or code_applied:
        label = "🎟 تغییر/حذفِ کدِ تخفیف" if code_applied else "🎟 کد تخفیف دارم"
        rows.append(InlineKeyboardButton(text=label, callback_data="cart_discount_code"))
    markup_rows = _chunks(rows)
    markup_rows.append([InlineKeyboardButton(text="❌ انصراف", callback_data="cart_checkout_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=markup_rows)


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
    rows = _chunks([InlineKeyboardButton(text=f"🔎 سفارشِ {first_index + i}", callback_data=f"myord_view:{key}") for i, key in enumerate(keys)])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️ قبلی", callback_data=f"myord_page:{page - 1}"))
    if (page + 1) * page_size < total_groups:
        nav.append(InlineKeyboardButton(text="بعدی ➡️", callback_data=f"myord_page:{page + 1}"))
    if nav:
        rows.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def my_order_card_keyboard(key: str, *, can_invoice: bool, can_cancel: bool, digital_order_ids: list[int], page: int = 0, can_pay: bool = False) -> InlineKeyboardMarkup:
    """دکمه‌هایِ کارتِ سفارش. لغو عمداً آخر و تنهاست: همین‌جا تاییدیهٔ دوم ندارد و یکِ کلیکِ
    اشتباه در ردیفِ دونفره یعنی سفارشی که مشتری منظورش را نداشت، می‌رود."""
    rows = []
    actions = []
    if can_pay:
        actions.append(InlineKeyboardButton(text="💳 پرداخت", callback_data=f"pm_menu:{key}"))
    if can_invoice:
        actions.append(InlineKeyboardButton(text="📄 فاکتور", callback_data=f"myord_inv:{key}"))
    rows.extend(_chunks(actions))
    rows.extend(
        _chunks([
            InlineKeyboardButton(text="📥 دریافتِ دوباره", callback_data=f"dl_again:{order_id}")
            for order_id in digital_order_ids[:5]
        ])
    )
    rows.append([InlineKeyboardButton(text="⬅️ برگشت به فهرست", callback_data=f"myord_page:{page}")])
    if can_cancel:
        rows.append([InlineKeyboardButton(text="❌ لغوِ سفارش", callback_data=f"myord_cancel:{key}")])
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

    rows = _chunks(
        [InlineKeyboardButton(text=PAY_METHOD_LABELS[m], callback_data=f"pm_{m}:{key}") for m in methods if m in PAY_METHOD_LABELS],
        max_label=26,
    )
    rows.append([InlineKeyboardButton(text="❌ لغوِ سفارش", callback_data=f"myord_cancel:{key}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def receipt_keyboard(key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📎 ارسالِ رسید", callback_data=f"pay_receipt:{key}"),
                InlineKeyboardButton(text="⬅️ روشِ دیگه", callback_data=f"pm_menu:{key}"),
            ],
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

