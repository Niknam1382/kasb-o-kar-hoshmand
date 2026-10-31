from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from app.bots.main_bot import texts

PAGE_SIZE = 10


def _paginate(items: list, page: int) -> tuple[list, int, int]:
    """
    یه صفحه از items رو برمی‌گردونه: (زیرلیستِ همون صفحه، شماره‌ی صفحه‌ی
    نرمال‌شده (اگه از بازه بیرون بود snap می‌شه)، تعدادِ کلِ صفحات — حداقل ۱).
    """
    total_pages = max(1, (len(items) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    start = page * PAGE_SIZE
    return items[start : start + PAGE_SIZE], page, total_pages


def _pagination_row(page: int, total_pages: int, callback_prefix: str) -> list[InlineKeyboardButton]:
    if total_pages <= 1:
        return []
    row = []
    if page > 0:
        row.append(InlineKeyboardButton(text="◀️ قبلی", callback_data=f"{callback_prefix}:{page - 1}"))
    row.append(InlineKeyboardButton(text=f"صفحه‌ی {page + 1} از {total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        row.append(InlineKeyboardButton(text="بعدی ▶️", callback_data=f"{callback_prefix}:{page + 1}"))
    return row


def admin_prompt_default_keyboard(mode: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📥 بارگذاریِ متنِ پیش‌فرض", callback_data=f"admin_prompt_default:{mode}")]])


def reg_mode_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛍 فروشگاهی (محصول و سفارش)", callback_data="reg_mode:sales")],
            [InlineKeyboardButton(text="💬 مشاوره‌ای (گفتگو و راهنمایی، بدونِ فروش)", callback_data="reg_mode:consultation")],
            [InlineKeyboardButton(text=texts.REG_CANCEL_BUTTON, callback_data="reg_cancel")],
        ]
    )


def reg_nav_keyboard(with_contact: bool = False) -> ReplyKeyboardMarkup:
    """کیبوردِ قدم‌هایِ متنیِ ویزارد: (اختیاری: اشتراکِ مخاطب) + برگشت/انصراف."""
    rows = []
    if with_contact:
        rows.append([KeyboardButton(text="📱 ارسال شماره تماس", request_contact=True)])
    rows.append([KeyboardButton(text=texts.REG_BACK_BUTTON), KeyboardButton(text=texts.REG_CANCEL_BUTTON)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def reg_first_name_choice_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ نامِ کوچکم همینه", callback_data="reg_fn_keep")],
            [InlineKeyboardButton(text="✂️ کلمه‌یِ آخر نامِ خانوادگیمه", callback_data="reg_fn_split")],
            [InlineKeyboardButton(text="✏️ ویرایش", callback_data="reg_fn_edit")],
        ]
    )


def reg_review_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ نام", callback_data="reg_edit:first_name"), InlineKeyboardButton(text="✏️ نامِ خانوادگی", callback_data="reg_edit:last_name")],
            [InlineKeyboardButton(text="✏️ موبایل", callback_data="reg_edit:phone"), InlineKeyboardButton(text="✏️ ایمیل", callback_data="reg_edit:email")],
            [InlineKeyboardButton(text="✏️ نوعِ کسب‌وکار", callback_data="reg_edit:mode")],
            [InlineKeyboardButton(text="✅ تایید و شروع", callback_data="reg_confirm")],
            [InlineKeyboardButton(text=texts.REG_CANCEL_BUTTON, callback_data="reg_cancel")],
        ]
    )


def reg_cancel_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ بله، انصراف", callback_data="reg_cancel_yes")],
            [InlineKeyboardButton(text="↩️ ادامه می‌دم", callback_data="reg_cancel_no")],
        ]
    )


def request_phone_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 ارسال شماره تماس", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def channels_gate_keyboard(channels, check_callback_data: str) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=ch.name, url=ch.invite_link or f"https://t.me/{str(ch.channel_id).lstrip('@')}")] for ch in channels]
    rows.append([InlineKeyboardButton(text="✅ عضو شدم", callback_data=check_callback_data)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def offer_trial_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎁 فعال‌سازی اعتبار آزمایشی", callback_data="activate_trial")]])


def shop_owner_panel_keyboard(tenant_mode=None) -> ReplyKeyboardMarkup:
    """منویِ فروشگاه‌دار (A4): مشاوره‌ای = بدونِ پرداختِ آنلاین/چک‌اوتِ سبد/کمپین (چیزهایِ مخصوصِ فروش)."""
    mode_value = tenant_mode.value if hasattr(tenant_mode, "value") else tenant_mode
    consultation = mode_value == "consultation"
    products_label = "🗂 خدمات و بسته‌ها" if consultation else "📦 محصولات"
    rows = [
        ["🔑 ثبت/ویرایش توکن ربات", products_label],
    ]
    if not consultation:
        rows.append(["🧾 مدیریتِ سفارش‌ها (جاری)"])  # W5: سفارش‌هایِ باز یک‌جا (اعلان‌ها دیگه گم نمی‌شن)
    rows += [
        ["🧠 دستور هوشمندسازی", "📢 کانال دانش‌افزایی"],
        ["👀 پیش‌نمایش ربات", "📊 آمار"],
        ["💰 کیف‌پول", "🎁 کد معرف"],
        ["🧾 تاریخچه‌ی پرداخت", "📤 خروجی اکسل"],
        ["👤 پروفایل من", "📞 پشتیبانی"],
        ["📣 پیام به مشتری‌ها"] + ([] if consultation else ["💳 پرداختِ آنلاینِ سفارش‌ها"]),
    ]
    if not consultation:
        rows.append(["📝 سوال‌هایِ چک‌اوتِ سبد"])
        rows.append(["🎯 کمپین‌ها", "👥 مشتری‌ها"])
    else:
        rows.append(["👥 مشتری‌ها"])
    rows += [
        ["🧩 سوال‌هایِ بی‌جواب", "📚 پرسش‌وپاسخ‌هایِ تاییدشده"],
        ["🧮 حسابداری", "💬 دستیارِ مدیریتی"],
        ["⚙️ تنظیماتِ ربات فروشگاه"],
    ]
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=label) for label in row] for row in rows], resize_keyboard=True)

def profile_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ نام", callback_data="pf_edit:first_name"), InlineKeyboardButton(text="✏️ نامِ خانوادگی", callback_data="pf_edit:last_name")],
            [InlineKeyboardButton(text="✏️ موبایل", callback_data="pf_edit:phone"), InlineKeyboardButton(text="✏️ ایمیل", callback_data="pf_edit:email")],
            [InlineKeyboardButton(text="🔀 نوعِ کسب‌وکار", callback_data="pf_mode")],
            [InlineKeyboardButton(text="📞 پشتیبانیِ پلتفرم", callback_data="pf_support")],
        ]
    )


def tenant_mode_ask_keyboard(target: str) -> InlineKeyboardMarkup:
    label = "🛍 تغییر به فروشگاهی" if target == "sales" else "💬 تغییر به مشاوره‌ای"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=label, callback_data=f"tenant_mode_ask:{target}")],
            [InlineKeyboardButton(text="↩️ انصراف", callback_data="pf_back")],
        ]
    )


def tenant_mode_confirm_keyboard(target: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ بله، تغییر بده", callback_data=f"set_tenant_mode:{target}")],
            [InlineKeyboardButton(text="↩️ نه", callback_data="pf_back")],
        ]
    )

def end_preview_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🔚 پایان پیش‌نمایش")]], resize_keyboard=True)


def products_list_keyboard(products, page: int = 0, sales_mode: bool = True) -> InlineKeyboardMarkup:
    page_items, page, total_pages = _paginate(list(products), page)
    rows = [[InlineKeyboardButton(text=p.name, callback_data=f"product_view:{p.id}")] for p in page_items]
    nav = _pagination_row(page, total_pages, "product_list")
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="➕ افزودن محصول جدید", callback_data="product_add")])
    if sales_mode:
        # فازِ ۱ · P1-S3 (B2): فقط در مودِ فروشگاهی (مشاوره = بدونِ کالایِ دیجیتال/ارسال)
        rows.append([InlineKeyboardButton(text="💾 افزودنِ محصولِ دیجیتال", callback_data="product_add_digital")])
        rows.append([InlineKeyboardButton(text="🚚 روش‌هایِ ارسال", callback_data="shipping_list")])
    rows.append([InlineKeyboardButton(text="📥 افزودن گروهی از اکسل", callback_data="product_bulk_import")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def product_import_confirm_keyboard(valid_count: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"✅ بله، {valid_count} محصول اضافه کن", callback_data="product_bulk_import_confirm")],
            [InlineKeyboardButton(text="❌ انصراف", callback_data="product_bulk_import_cancel")],
        ]
    )


def product_detail_keyboard(product_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ ویرایش", callback_data=f"product_edit:{product_id}"), InlineKeyboardButton(text="🗑 حذف", callback_data=f"product_delete:{product_id}")],
            [InlineKeyboardButton(text="🔙 بازگشت به فهرست", callback_data="product_list")],
        ]
    )


def confirm_delete_product_keyboard(product_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ بله، حذف کن", callback_data=f"product_delete_confirm:{product_id}"), InlineKeyboardButton(text="❌ بی‌خیال", callback_data=f"product_view:{product_id}")],
        ]
    )


def edit_product_field_keyboard(product_id: int, kind: str = "physical", delivery: str | None = None) -> InlineKeyboardMarkup:
    def _btn(label: str, field: str) -> InlineKeyboardButton:
        return InlineKeyboardButton(text=label, callback_data=f"product_edit_field:{product_id}:{field}")

    rows = [
        [_btn("نام", "name"), _btn("توضیحات", "description")],
        [_btn("قیمت", "price"), _btn("عکس", "photo")],
    ]
    if kind == "digital":
        if delivery == "code_pool":
            rows.append([_btn("🔑 افزودنِ کد", "codes")])
        elif delivery == "file":
            rows.append([_btn("📎 فایل", "dfile")])
        elif delivery == "link":
            rows.append([_btn("🔗 لینک", "dlink")])
        rows.append([_btn("راهنما/متنِ تحویل", "dinstr"), _btn("سقفِ دریافت", "dmax")])
        rows.append([_btn("دستورِ AI", "ai")])
    else:
        rows.append([_btn("موجودی", "stock")])
        rows.append([_btn("وزن", "weight"), _btn("زمانِ تحویل", "delivery")])
        rows.append([_btn("مرجوعی", "returns"), _btn("دستورِ AI", "ai")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def digital_mode_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📎 فایل", callback_data="dg_mode:file"), InlineKeyboardButton(text="🔗 لینک", callback_data="dg_mode:link")],
            [InlineKeyboardButton(text="📝 متن", callback_data="dg_mode:text"), InlineKeyboardButton(text="🔑 کدِ یکتا", callback_data="dg_mode:code_pool")],
            [InlineKeyboardButton(text="❌ انصراف", callback_data="dg_cancel")],
        ]
    )


def dg_skip_keyboard(step: str) -> InlineKeyboardMarkup:
    """«⏭ رد کردن»/«❌ انصراف»ِ مرحله‌هایِ اختیاریِ افزودنِ محصولِ دیجیتال (step: description / photo / instructions / max / codes)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⏭ رد کردن", callback_data=f"dg_skip:{step}")],
            [InlineKeyboardButton(text="❌ انصراف", callback_data="dg_cancel")],
        ]
    )


def dg_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ انصراف", callback_data="dg_cancel")]])


def shipping_list_keyboard(methods) -> InlineKeyboardMarkup:
    rows = []
    for method in methods:
        toggle = "⏸ غیرفعال" if method.is_active else "▶️ فعال"
        rows.append(
            [
                InlineKeyboardButton(text=f"{toggle}: {method.name}"[:60], callback_data=f"ship_toggle:{method.id}"),
                InlineKeyboardButton(text="🗑", callback_data=f"ship_del:{method.id}"),
            ]
        )
    rows.append([InlineKeyboardButton(text="➕ افزودنِ روشِ ارسال", callback_data="ship_add")])
    rows.append([InlineKeyboardButton(text="🔙 بازگشت به فهرستِ محصولات", callback_data="product_list")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def ship_skip_keyboard(step: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⏭ رد کردن", callback_data=f"ship_skip:{step}")],
            [InlineKeyboardButton(text="❌ انصراف", callback_data="ship_cancel")],
        ]
    )


def ship_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ انصراف", callback_data="ship_cancel")]])


def choose_knowledge_bot_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="ربات فروشگاهی من", callback_data="knowledge_bot:shop")],
            [InlineKeyboardButton(text="ربات اصلی پلتفرم", callback_data="knowledge_bot:main")],
        ]
    )


def wallet_topup_action_keyboard() -> InlineKeyboardMarkup:
    from app.bots.main_bot.texts import wallet_topup_action_label

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=wallet_topup_action_label(), callback_data="topup_start")],
            [InlineKeyboardButton(text="📂 پرداخت‌هایِ باز", callback_data="topup_open_list")],
            [InlineKeyboardButton(text="🧮 محاسبه‌گرِ هزینه‌ی ماهانه", callback_data="cost_calc_start")],
            [InlineKeyboardButton(text="📜 تاریخچه‌ی تراکنش‌ها", callback_data="wallet_history")],
        ]
    )


def topup_receipt_keyboard(payment_id: int) -> InlineKeyboardMarkup:
    """A7: «⬅️ برگشت» در حالتِ انتظارِ رسید — state پاک می‌شود ولی ردیفِ پرداخت می‌ماند."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ برگشت", callback_data=f"topup_pay_back:{payment_id}")]]
    )


def open_topup_payments_keyboard(payments) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"📎 رسیدِ پرداختِ {payment.id}", callback_data=f"topup_pay_resume:{payment.id}")]
        for payment in payments
    ]
    rows.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="wallet_status")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cost_calc_volume_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="کمتر از ۲۰ پیام در روز", callback_data="cost_calc_volume:low")],
            [InlineKeyboardButton(text="۲۰ تا ۱۰۰ پیام در روز", callback_data="cost_calc_volume:medium")],
            [InlineKeyboardButton(text="۱۰۰ تا ۵۰۰ پیام در روز", callback_data="cost_calc_volume:high")],
            [InlineKeyboardButton(text="بیشتر از ۵۰۰ پیام در روز", callback_data="cost_calc_volume:very_high")],
        ]
    )


def topup_amount_keyboard() -> InlineKeyboardMarkup:
    from app.bots.main_bot.texts import TOPUP_AMOUNT_PRESETS_TOMAN, topup_amount_button_label

    rows = [
        [InlineKeyboardButton(text=topup_amount_button_label(amount), callback_data=f"topup_amount:{amount}")]
        for amount in TOPUP_AMOUNT_PRESETS_TOMAN
    ]
    rows.append([InlineKeyboardButton(text="✏️ مبلغ دلخواه", callback_data="topup_amount:custom")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def skip_discount_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⏭ رد شدن از کد تخفیف", callback_data="skip_discount")]])


def payment_method_keyboard(zarinpal_enabled: bool = True, bale_pay_enabled: bool = False) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="💳 پرداخت با کارت (کارت‌به‌کارت)", callback_data="payment_method:card")]]
    if zarinpal_enabled:
        rows.append([InlineKeyboardButton(text="⚡️ پرداخت آنی با زرین‌پال", callback_data="payment_method:zarinpal")])
    if bale_pay_enabled:
        rows.append([InlineKeyboardButton(text="🔵 پرداخت با بله‌پی", callback_data="payment_method:bale")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def zarinpal_pay_keyboard(pay_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔗 رفتن به درگاه پرداخت", url=pay_url)]])


def bale_pay_keyboard(pay_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔗 رفتن به بله‌پی", url=pay_url)]])


def admin_payment_approval_keyboard(payment_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ تایید", callback_data=f"admin_approve_payment:{payment_id}"), InlineKeyboardButton(text="❌ رد", callback_data=f"admin_reject_payment:{payment_id}")],
        ]
    )


def excel_export_choice_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👥 فهرست مشتریان", callback_data="export_excel:customers")],
            [InlineKeyboardButton(text="🧾 سفارش‌ها و مشاوره‌ها", callback_data="export_excel:orders")],
        ]
    )


def confirm_broadcast_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ بله، بفرست", callback_data="broadcast_confirm"), InlineKeyboardButton(text="❌ لغو", callback_data="broadcast_cancel")],
        ]
    )


def confirm_customer_broadcast_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ بله، بفرست", callback_data="customer_broadcast_confirm"),
                InlineKeyboardButton(text="❌ لغو", callback_data="customer_broadcast_cancel"),
            ],
        ]
    )


def admin_panel_keyboard(is_super_admin: bool) -> ReplyKeyboardMarkup:
    """
    ادمینِ عملیاتی (is_super_admin=False) دکمه‌هایِ حساس رو اصلاً نمی‌بینه:
    تنظیماتِ قیمت/تخفیف، تنظیماتِ کلیدها، استخرِ کلیدهایِ AI، و مدیریتِ
    ادمین‌ها. اگه is_super_admin=True باشه، دقیقاً همونِ کیبوردِ قبل از
    RBAC رو می‌بینه (به‌علاوه‌ی دکمه‌ی جدیدِ مدیریتِ ادمین‌ها).
    """
    rows = [
        [KeyboardButton(text="📢 مدیریت کانال‌های اجباری"), KeyboardButton(text="🧾 صف تایید پرداخت‌ها")],
    ]
    if is_super_admin:
        rows.append([KeyboardButton(text="💰 تنظیمات قیمت و تخفیف"), KeyboardButton(text="🔑 تنظیمات کلیدها")])
    rows.append([KeyboardButton(text="📊 آمار سراسری"), KeyboardButton(text="📣 پیام همگانی")])
    rows.append([KeyboardButton(text="👥 مدیریت فروشگاه‌دارها"), KeyboardButton(text="🛡 نگهبانِ محتوا")])
    rows.append([KeyboardButton(text="⏱ اعتبار و زمان")])  # W5 · K1–K4
    if is_super_admin:
        rows.append([KeyboardButton(text="📜 گزارشِ ممیزی"), KeyboardButton(text="🔑 استخرِ کلیدهایِ AI")])
        rows.append([KeyboardButton(text="👑 مدیریتِ ادمین‌ها"), KeyboardButton(text="📤 دفترِ کیف‌پول (اکسل)")])
    else:
        rows.append([KeyboardButton(text="📜 گزارشِ ممیزی")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def mandatory_channels_list_keyboard(channels) -> InlineKeyboardMarkup:
    from app.bots.main_bot.texts import channel_list_item_label

    rows = [
        [InlineKeyboardButton(text=channel_list_item_label(ch), callback_data="noop"), InlineKeyboardButton(text="🗑", callback_data=f"admin_channel_delete:{ch.id}")]
        for ch in channels
    ]
    rows.append([InlineKeyboardButton(text="➕ افزودن کانال جدید", callback_data="admin_channel_add")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def yes_no_keyboard(yes_data: str, no_data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ بله", callback_data=yes_data), InlineKeyboardButton(text="❌ نه", callback_data=no_data)]])


def confirm_delete_channel_keyboard(channel_pk: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ بله، حذف کن", callback_data=f"admin_channel_delete_confirm:{channel_pk}"), InlineKeyboardButton(text="❌ بی‌خیال", callback_data="admin_channel_list")],
        ]
    )


def admin_pricing_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📅 طرح‌های اشتراک", callback_data="admin_pricing_plans")],
            [InlineKeyboardButton(text="🏷 کدهای تخفیف", callback_data="admin_pricing_discounts")],
        ]
    )


def admin_plans_list_keyboard(plans) -> InlineKeyboardMarkup:
    from app.utils.validators import format_toman

    rows = []
    for p in plans:
        status = "✅" if p.is_active else "❌"
        rows.append(
            [InlineKeyboardButton(text=f"{status} {p.duration_months} ماهه — {format_toman(p.price_toman)}", callback_data=f"admin_plan_toggle:{p.id}")]
        )
    rows.append([InlineKeyboardButton(text="➕ افزودن طرح جدید", callback_data="admin_plan_add")])
    rows.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_pricing_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_discounts_list_keyboard(codes) -> InlineKeyboardMarkup:
    rows = []
    for c in codes:
        status = "✅" if c.is_active else "❌"
        value_label = f"{float(c.value):g}٪" if c.type.value == "percent" else f"{int(c.value)} تومان"
        rows.append([InlineKeyboardButton(text=f"{status} {c.code} ({value_label})", callback_data=f"admin_discount_toggle:{c.id}")])
    rows.append([InlineKeyboardButton(text="➕ افزودن کد جدید", callback_data="admin_discount_add")])
    rows.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_pricing_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def discount_type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="درصدی", callback_data="discount_type:percent"), InlineKeyboardButton(text="مبلغ ثابت", callback_data="discount_type:fixed")],
        ]
    )


def admin_settings_menu_keyboard(admin_settings) -> InlineKeyboardMarkup:
    from app.bots.main_bot.texts import admin_settings_button_labels

    zarinpal_label = "🙈 پنهان‌کردنِ زرین‌پال از فروشگاه‌دارها" if admin_settings.zarinpal_enabled else "👁 نمایشِ دوباره‌ی زرین‌پال"
    bale_pay_label = "🙈 پنهان‌کردنِ بله‌پی از فروشگاه‌دارها" if admin_settings.bale_pay_enabled else "👁 فعال‌کردنِ بله‌پی"
    registrations_label = "⛔️ بستنِ ثبت‌نامِ کاربرانِ جدید" if admin_settings.allow_new_registrations else "✅ بازکردنِ ثبت‌نامِ کاربرانِ جدید"
    topups_label = "⛔️ غیرفعال‌کردنِ شارژِ کیف‌پول" if admin_settings.allow_wallet_topups else "✅ فعال‌کردنِ شارژِ کیف‌پول"
    maintenance_label = "🚧 فعال‌کردنِ حالتِ تعمیر (کلِ پلتفرم)" if not admin_settings.maintenance_mode else "✅ خروج از حالتِ تعمیر"
    nightly_report_label = "🙈 خاموش‌کردنِ گزارشِ شبانه" if admin_settings.nightly_report_enabled else "🌙 روشن‌کردنِ گزارشِ شبانه"
    knowledge_gap_label = (
        "🧩 خاموش‌کردنِ تشخیصِ سوال‌هایِ بی‌جواب"
        if admin_settings.knowledge_gap_enabled
        else "🧩 روشن‌کردنِ تشخیصِ سوال‌هایِ بی‌جواب"
    )
    rows = [
        [InlineKeyboardButton(text=zarinpal_label, callback_data="admin_toggle_zarinpal")],
        [InlineKeyboardButton(text=bale_pay_label, callback_data="admin_toggle_bale_pay")],
        [InlineKeyboardButton(text="🧮 محاسبه‌ی خودکارِ هزینه از فرمول", callback_data="admin_recalc_wallet_cost")],
        [InlineKeyboardButton(text=registrations_label, callback_data="admin_toggle_registrations")],
        [InlineKeyboardButton(text=topups_label, callback_data="admin_toggle_topups")],
        [InlineKeyboardButton(text=maintenance_label, callback_data="admin_toggle_maintenance")],
        [InlineKeyboardButton(text=nightly_report_label, callback_data="admin_toggle_nightly_report")],
        [InlineKeyboardButton(text=knowledge_gap_label, callback_data="admin_toggle_knowledge_gap")],
        [InlineKeyboardButton(text="🧪 آزمایشِ بله‌پی", callback_data="admin_bale_selftest")],
        [InlineKeyboardButton(text="🔎 آخرین رویدادهایِ پرداخت", callback_data="admin_payment_events")],
    ]
    rows += [[InlineKeyboardButton(text=label, callback_data=f"admin_setting_edit:{key}")] for key, label in admin_settings_button_labels(admin_settings)]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_owners_list_keyboard(owners, page: int = 0, shop_bots_by_owner: dict | None = None) -> InlineKeyboardMarkup:
    """shop_bots_by_owner: {شناسه‌یِ فروشگاه‌دار: ShopBot | None}؛ اگه داده بشه برچسبِ هر دکمه «وضعیت + نام + @ربات» می‌شه."""
    from app.bots.main_bot import texts

    page_items, page, total_pages = _paginate(list(owners), page)
    rows = []
    for owner in page_items:
        if shop_bots_by_owner is None:
            label = texts.admin_owner_list_item_label(owner)
        else:
            label = texts.admin_owner_list_item_label(owner, shop_bots_by_owner.get(owner.id))
        rows.append([InlineKeyboardButton(text=label, callback_data=f"admin_owner_view:{owner.id}")])
    nav = _pagination_row(page, total_pages, "admin_owners_list")
    if nav:
        rows.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_owner_detail_keyboard(owner_id: int, shop_bot) -> InlineKeyboardMarkup:
    rows = []
    if shop_bot is not None:
        if shop_bot.is_active:
            rows.append([InlineKeyboardButton(text="⛔️ معلق کردن ربات", callback_data=f"admin_owner_suspend:{owner_id}")])
        else:
            rows.append([InlineKeyboardButton(text="✅ فعال‌سازی دوباره", callback_data=f"admin_owner_unsuspend:{owner_id}")])
    rows.append([InlineKeyboardButton(text="🎁 اعطای اعتبارِ هدیه", callback_data=f"admin_owner_gift:{owner_id}")])
    rows.append([InlineKeyboardButton(text="🧾 استرداد/اصلاحِ کیف‌پول", callback_data=f"admin_owner_wallet_correction:{owner_id}")])
    rows.append([InlineKeyboardButton(text="🔙 بازگشت به فهرست", callback_data="admin_owners_list")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def order_notification_keyboard(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ تایید و کسر از موجودی", callback_data=f"confirm_order:{order_id}")],
            [InlineKeyboardButton(text="❌ رد کردن سفارش", callback_data=f"reject_order:{order_id}")],
            [InlineKeyboardButton(text="✉️ پیام به مشتری", callback_data=f"og_msg:o{order_id}")],  # W5/1.5: کلیدِ تک‌سفارشی «o<id>»
        ]
    )


def cart_group_notification_keyboard(group_id: str) -> InlineKeyboardMarkup:
    """فازِ ۳ — سبدِ خرید: مثلِ order_notification_keyboard بالا، ولی برایِ
    تاییدِ/ردِ همه‌ی اقلامِ یه چک‌اوتِ سبد با یه دکمه (نه هر آیتم جدا)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ تایید و کسر از موجودی (کلِ سفارش)", callback_data=f"confirm_cart_group:{group_id}")],
            [InlineKeyboardButton(text="❌ رد کردنِ کلِ سفارش", callback_data=f"og_rej:{group_id}")],
            [InlineKeyboardButton(text="✉️ پیام به این مشتری", callback_data=f"og_msg:{group_id}")],
        ]
    )


def order_advance_status_keyboard(order_id: int, next_label: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=next_label, callback_data=f"advance_order:{order_id}")]])


def moderation_rules_list_keyboard(rules) -> InlineKeyboardMarkup:
    rows = []
    for rule in rules:
        status_icon = "🟢" if rule.is_active else "⚪️"
        action_value = rule.action.value if hasattr(rule.action, "value") else rule.action
        label = f"{status_icon} «{rule.pattern}» ({action_value})"
        rows.append([InlineKeyboardButton(text=label[:60], callback_data=f"mod_rule_view:{rule.id}")])
    rows.append([InlineKeyboardButton(text="➕ افزودنِ قانونِ جدید", callback_data="mod_rule_add")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def moderation_rule_action_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⚠️ فقط هشدار/ثبت (WARN)", callback_data="mod_rule_action:warn")],
            [InlineKeyboardButton(text="⛔️ مسدودکردنِ پاسخ (BLOCK)", callback_data="mod_rule_action:block")],
            [InlineKeyboardButton(text="🔍 مسدود + نیازِ بازبینی (REVIEW)", callback_data="mod_rule_action:review")],
        ]
    )


def moderation_rule_detail_keyboard(rule_id: int, is_active: bool) -> InlineKeyboardMarkup:
    toggle_label = "⏸ غیرفعال‌کردن" if is_active else "▶️ فعال‌کردن"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=toggle_label, callback_data=f"mod_rule_toggle:{rule_id}")],
            [InlineKeyboardButton(text="🗑 حذف", callback_data=f"mod_rule_delete:{rule_id}")],
            [InlineKeyboardButton(text="🔙 بازگشت به فهرست", callback_data="mod_rules_list")],
        ]
    )


def ai_pool_list_keyboard(entries) -> InlineKeyboardMarkup:
    rows = []
    for entry in entries:
        status_icon = "🟢" if entry.is_active else "⚪️"
        cap = entry.capability.value if hasattr(entry.capability, "value") else entry.capability
        label = f"{status_icon} {entry.label} ({cap})"
        rows.append([InlineKeyboardButton(text=label[:60], callback_data=f"ai_pool_view:{entry.id}")])
    rows.append([InlineKeyboardButton(text="➕ افزودنِ کلیدِ جدید", callback_data="ai_pool_add")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def ai_pool_entry_detail_keyboard(entry_id: int, is_active: bool) -> InlineKeyboardMarkup:
    toggle_label = "⏸ غیرفعال‌کردن" if is_active else "▶️ فعال‌کردن"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=toggle_label, callback_data=f"ai_pool_toggle:{entry_id}")],
            [InlineKeyboardButton(text="🗑 حذف", callback_data=f"ai_pool_delete:{entry_id}")],
            [InlineKeyboardButton(text="🔙 بازگشت به فهرست", callback_data="ai_pool_list")],
        ]
    )


def admin_roles_list_keyboard(roles, labels: dict[int, str] | None = None) -> InlineKeyboardMarkup:
    labels = labels or {}
    rows = [[InlineKeyboardButton(text=f"👤 {labels.get(role.telegram_id, 'ادمین')}", callback_data=f"admin_role_view:{role.id}")] for role in roles]
    rows.append([InlineKeyboardButton(text="➕ افزودنِ ادمینِ عملیاتیِ جدید", callback_data="admin_role_add")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_role_detail_keyboard(role_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🗑 حذفِ این ادمین", callback_data=f"admin_role_revoke:{role_id}")],
            [InlineKeyboardButton(text="🔙 بازگشت به فهرست", callback_data="admin_role_list")],
        ]
    )


# =============================================================================
# کمپین‌ها (تخفیفِ مخصوصِ مشتری، فازِ ۳)
# =============================================================================
_CAMPAIGN_STATUS_EMOJI = {"active": "🟢", "paused": "⏸", "scheduled": "🕓", "ended": "⏹"}


def campaigns_list_keyboard(items_with_status) -> InlineKeyboardMarkup:
    """items_with_status: لیستی از (Campaign, status) — status از campaign_service.campaign_status."""
    rows = []
    for campaign, status in items_with_status:
        type_value = campaign.discount_type.value if hasattr(campaign.discount_type, "value") else campaign.discount_type
        short = f"{campaign.discount_value}%" if type_value == "percent" else f"{campaign.discount_value:,}"
        label = f"{_CAMPAIGN_STATUS_EMOJI.get(status, '')} {campaign.name[:30]} · {short}"
        rows.append([InlineKeyboardButton(text=label, callback_data=f"campaign_view:{campaign.id}")])
    rows.append([InlineKeyboardButton(text="➕ ساختِ کمپینِ جدید", callback_data="campaign_new")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def campaign_detail_keyboard(campaign, status: str) -> InlineKeyboardMarkup:
    rows = []
    if status in ("active", "scheduled"):
        rows.append([InlineKeyboardButton(text="⏸ توقف", callback_data=f"campaign_toggle:{campaign.id}")])
    elif status == "paused":
        rows.append([InlineKeyboardButton(text="▶️ ادامه", callback_data=f"campaign_toggle:{campaign.id}")])
    if status == "active":
        rows.append([InlineKeyboardButton(text="📣 اعلام به مشتری‌ها", callback_data=f"campaign_announce:{campaign.id}")])
    rows.append([InlineKeyboardButton(text="🗑 حذف", callback_data=f"campaign_delete:{campaign.id}")])
    rows.append([InlineKeyboardButton(text="↩️ برگشت به فهرست", callback_data="campaign_list")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def campaign_created_keyboard(campaign_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📣 اعلام به مشتری‌ها", callback_data=f"campaign_announce:{campaign_id}")],
            [InlineKeyboardButton(text="🎯 دیدنِ کمپین", callback_data=f"campaign_view:{campaign_id}")],
        ]
    )


def campaign_type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="٪ درصدی", callback_data="campaign_type:percent")],
            [InlineKeyboardButton(text="💵 مبلغِ ثابت (تومان)", callback_data="campaign_type:fixed")],
        ]
    )


def campaign_skip_keyboard(label: str, callback_data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=label, callback_data=callback_data)]])


def campaign_code_choice_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎟 با کد", callback_data="campaign_code_choice:code")],
            [InlineKeyboardButton(text="⚡ خودکار (بدونِ کد)", callback_data="campaign_code_choice:auto")],
        ]
    )


def campaign_duration_keyboard() -> InlineKeyboardMarkup:
    options = [(1, "۱ روز"), (3, "۳ روز"), (7, "۷ روز"), (14, "۱۴ روز"), (30, "۳۰ روز")]
    buttons = [InlineKeyboardButton(text=label, callback_data=f"campaign_duration:{days}") for days, label in options]
    return InlineKeyboardMarkup(inline_keyboard=[buttons[:3], buttons[3:]])


def campaign_per_customer_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="۱ بار", callback_data="campaign_percustomer:1"),
                InlineKeyboardButton(text="۲ بار", callback_data="campaign_percustomer:2"),
                InlineKeyboardButton(text="۳ بار", callback_data="campaign_percustomer:3"),
            ],
            [InlineKeyboardButton(text="♾ نامحدود", callback_data="campaign_percustomer:0")],
        ]
    )


def campaign_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ ساخت و فعال‌سازی", callback_data="campaign_create_confirm")],
            [InlineKeyboardButton(text="❌ لغو", callback_data="campaign_create_cancel")],
        ]
    )


# =============================================================================
# فازِ ۴-الف/ب — سوال‌هایِ بی‌جواب و پرسش‌وپاسخ‌هایِ تاییدشده
# =============================================================================
def _page_count(total: int, page_size: int) -> int:
    return max(1, (total + page_size - 1) // page_size)


def gaps_list_keyboard(gaps, page: int, total: int, page_size: int) -> InlineKeyboardMarkup:
    rows = []
    for index, gap in enumerate(gaps, start=page * page_size + 1):
        rows.append(
            [
                InlineKeyboardButton(text=f"✍️ پاسخ بده ({index})", callback_data=f"gap_answer:{gap.id}"),
                InlineKeyboardButton(text=f"🙈 نادیده بگیر ({index})", callback_data=f"gap_dismiss:{gap.id}"),
            ]
        )
    nav = _pagination_row(page, _page_count(total, page_size), "gap_list")
    if nav:
        rows.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def gap_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ ذخیره کن", callback_data="gap_save_confirm"),
                InlineKeyboardButton(text="❌ لغو", callback_data="gap_save_cancel"),
            ]
        ]
    )


def learned_list_keyboard(items, page: int, total: int, page_size: int) -> InlineKeyboardMarkup:
    rows = []
    for item in items:
        mark = "✅" if item.is_active else "⏸"
        label = item.question if len(item.question) <= 40 else item.question[:39] + "…"
        rows.append([InlineKeyboardButton(text=f"{mark} {label}", callback_data=f"learned_view:{item.id}")])
    nav = _pagination_row(page, _page_count(total, page_size), "learned_list")
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="➕ افزودنِ دستی", callback_data="learned_add")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def learned_detail_keyboard(item) -> InlineKeyboardMarkup:
    toggle_label = "⏸ غیرفعال کن" if item.is_active else "▶️ فعال کن"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ ویرایشِ جواب", callback_data=f"learned_edit:{item.id}")],
            [InlineKeyboardButton(text=toggle_label, callback_data=f"learned_toggle:{item.id}")],
            [InlineKeyboardButton(text="🗑 حذف", callback_data=f"learned_delete:{item.id}")],
            [InlineKeyboardButton(text="↩️ برگشت به فهرست", callback_data="learned_list:0")],
        ]
    )


def learned_delete_confirm_keyboard(item_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🗑 بله، حذف کن", callback_data=f"learned_delete_yes:{item_id}"),
                InlineKeyboardButton(text="↩️ نه، برگرد", callback_data=f"learned_view:{item_id}"),
            ]
        ]
    )


def learned_manual_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ ذخیره کن", callback_data="learned_manual_confirm"),
                InlineKeyboardButton(text="❌ لغو", callback_data="learned_manual_cancel"),
            ]
        ]
    )


# =============================================================================
# فازِ ۴-ه — حسابداری
# =============================================================================
_ACCOUNTING_BUTTONS = (("today", "امروز"), ("week", "۷ روز"), ("month30", "۳۰ روز"), ("jmonth", "ماهِ شمسی"))


def accounting_keyboard(current_key: str) -> InlineKeyboardMarkup:
    period_row = [
        InlineKeyboardButton(text=("✅ " if key == current_key else "") + label, callback_data=f"acct:{key}")
        for key, label in _ACCOUNTING_BUTTONS
    ]
    return InlineKeyboardMarkup(
        inline_keyboard=[period_row, [InlineKeyboardButton(text="📤 اکسلِ این بازه", callback_data=f"acct_xlsx:{current_key}")]]
    )


# =============================================================================
# فازِ ۴-ج — CRM
# =============================================================================
def crm_overview_keyboard(counts: dict) -> InlineKeyboardMarkup:
    from app.bots.main_bot import texts

    rows = [
        [InlineKeyboardButton(text=f"{label} ({counts.get(key, 0)})", callback_data=f"crm_seg:{key}:0")]
        for key, label in texts.CRM_SEGMENT_LABELS.items()
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def crm_segment_keyboard(segment_key: str, members, page: int, total_pages: int, page_size: int) -> InlineKeyboardMarkup:
    from app.bots.main_bot import texts

    rows = []
    for index, stat in enumerate(members, start=page * page_size + 1):
        label = f"{index}. {texts.crm_customer_name(stat)}"[:60]
        rows.append([InlineKeyboardButton(text=label, callback_data=f"crm_card:{stat.customer_id}")])
    nav = _pagination_row(page, total_pages, f"crm_seg:{segment_key}")
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="📣 پیام به این بخش", callback_data=f"crm_bcast:{segment_key}")])
    rows.append([InlineKeyboardButton(text="↩️ بخش‌ها", callback_data="crm_home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def crm_card_keyboard(customer_id: int, segment_key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✍️ یادداشت", callback_data=f"crm_note:{customer_id}"),
                InlineKeyboardButton(text="🏷 برچسب‌ها", callback_data=f"crm_tags:{customer_id}"),
            ],
            [InlineKeyboardButton(text="🧠 خلاصه‌یِ هوشمند", callback_data=f"crm_sum:{customer_id}")],
            [InlineKeyboardButton(text="↩️ برگشت به فهرست", callback_data=f"crm_seg:{segment_key}:0")],
        ]
    )


def crm_clear_keyboard(kind: str, customer_id: int) -> InlineKeyboardMarkup:
    """kind: 'note' یا 'tags'."""
    label = "🗑 پاک‌کردنِ یادداشت" if kind == "note" else "🗑 پاک‌کردنِ برچسب‌ها"
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=label, callback_data=f"crm_{kind}_clear:{customer_id}")]])


def crm_summary_confirm_keyboard(customer_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ بله، بساز", callback_data=f"crm_sum_go:{customer_id}"),
                InlineKeyboardButton(text="↩️ برگشت", callback_data=f"crm_card:{customer_id}"),
            ]
        ]
    )


def crm_back_to_card_keyboard(customer_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="↩️ برگشت به مشتری", callback_data=f"crm_card:{customer_id}")]])


# =============================================================================
# فازِ ۴-د — دستیارِ مدیریتی
# =============================================================================
def assistant_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🔚 پایان")]], resize_keyboard=True)


# =============================================================================
# فازِ ۶-الف — تنظیماتِ رباتِ فروشگاه
# =============================================================================
def shop_settings_keyboard(shop_bot) -> InlineKeyboardMarkup:
    from app.bots.main_bot import texts

    current = shop_bot.message_batch_seconds
    preset_row = [
        InlineKeyboardButton(text=("✅ " if current == seconds else "") + label, callback_data=f"bs_batch:{seconds}")
        for seconds, label in texts.BATCH_PRESETS
    ]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            preset_row,
            [InlineKeyboardButton(text="✍️ مقدارِ دلخواه (۲ تا ۶۰ ثانیه)", callback_data="bs_batch_custom")],
            [InlineKeyboardButton(text="↩️ پیش‌فرضِ سیستم", callback_data="bs_batch_reset")],
            [InlineKeyboardButton(text="📞 پشتیبانیِ مشتری‌ها", callback_data="sp_open")],
        ]
    )


def shop_support_keyboard(shop_bot) -> InlineKeyboardMarkup:
    toggle = "⛔️ خاموش‌کردن" if shop_bot.support_enabled else "✅ فعال‌کردن"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=toggle, callback_data="sp_toggle")],
            [InlineKeyboardButton(text="✏️ یوزرنیم", callback_data="sp_edit:username"), InlineKeyboardButton(text="✏️ تلفن", callback_data="sp_edit:phone")],
            [InlineKeyboardButton(text="✏️ متن", callback_data="sp_edit:text")],
            [InlineKeyboardButton(text="↩️ برگشت", callback_data="sp_back")],
        ]
    )


def skip_step_keyboard(step: str) -> InlineKeyboardMarkup:
    """دکمه‌یِ «⏭ رد کردن» برایِ مرحله‌هایِ اختیاریِ افزودنِ محصول (step: description / photo / stock)."""
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⏭ رد کردن", callback_data=f"product_skip:{step}")]])


# =============================================================================
# عملیاتِ گروهیِ سفارش (W2 · C4/C9/D5) — callbackها با پیشوندِ og_ ؛ key = o<id> یا شناسه‌یِ گروه
# =============================================================================
def order_group_actions_keyboard(key: str, status) -> InlineKeyboardMarkup | None:
    from app.services import order_state

    s = order_state.value_of(status)
    rows: list[list[InlineKeyboardButton]] = []
    if s in (order_state.PAID, order_state.CONFIRMED):
        rows.append([InlineKeyboardButton(text="▶️ شروعِ پردازش", callback_data=f"og_start:{key}")])
    elif s == order_state.PROCESSING:
        rows.append([InlineKeyboardButton(text="🚚 ارسال شد (ثبتِ کدِ رهگیری)", callback_data=f"og_ship:{key}")])
    elif s == order_state.SHIPPED:
        rows.append([InlineKeyboardButton(text="✅ تکمیل شد", callback_data=f"og_done:{key}")])
    if s in order_state.REJECTABLE:
        rows.append([InlineKeyboardButton(text="❌ ردِ سفارش", callback_data=f"og_rej:{key}")])
    elif s in order_state.REFUNDABLE:
        rows.append([InlineKeyboardButton(text="↩️ استرداد", callback_data=f"og_rej:{key}")])
    if s == order_state.REFUND_PENDING:
        rows.append([InlineKeyboardButton(text="✅ استرداد انجام شد", callback_data=f"og_refunded:{key}")])
    if s == order_state.REFUNDED:  # W5 · 2.2: گزینه‌یِ فروشگاه‌دار برایِ برگشتِ موجودی
        rows.append([InlineKeyboardButton(text="📦 برگردانِ موجودی به انبار", callback_data=f"og_restock:{key}")])
    rows.append([InlineKeyboardButton(text="✉️ پیام به این مشتری", callback_data=f"og_msg:{key}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def order_reject_reasons_keyboard(key: str, reasons: tuple[str, ...]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=reason, callback_data=f"og_rr:{i}:{key}")] for i, reason in enumerate(reasons)]
    rows.append([InlineKeyboardButton(text="✍️ دلیلِ دیگه (می‌نویسم)", callback_data=f"og_rr:t:{key}")])
    rows.append([InlineKeyboardButton(text="⬅️ برگشت", callback_data=f"og_back:{key}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# =============================================================================
# W3 — پرداخت
# =============================================================================
def receipt_review_keyboard(payment_id: int, key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ تایید", callback_data=f"rcpt_ok:{payment_id}"),
                InlineKeyboardButton(text="❌ رد (دلیل)", callback_data=f"rcpt_no:{payment_id}"),
            ],
            [InlineKeyboardButton(text="✉️ پیام به مشتری", callback_data=f"og_msg:{key}")],
        ]
    )


def receipt_reject_reasons_keyboard(payment_id: int, reasons: tuple[str, ...]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=reason, callback_data=f"rcpt_nr:{i}:{payment_id}")] for i, reason in enumerate(reasons)]
    rows.append([InlineKeyboardButton(text="✍️ دلیلِ دیگه (می‌نویسم)", callback_data=f"rcpt_nr:t:{payment_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def payments_menu_keyboard(row, shop_bot) -> InlineKeyboardMarkup:
    def tog(label: str, enabled: bool, code: str) -> list[InlineKeyboardButton]:
        return [InlineKeyboardButton(text=f"{'✅' if enabled else '⛔️'} {label}", callback_data=f"pays_tog:{code}")]

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 تنظیمِ کارت (شماره/نام/بانک)", callback_data="pays_card")],
            tog("کارت‌به‌کارت", row.card_enabled, "card"),
            tog("بله‌پی", row.bale_enabled, "bale"),
            tog("زرین‌پال", row.zarinpal_enabled, "zarinpal"),
            tog("پرداختِ دستی/هماهنگی", row.manual_enabled, "manual"),
            tog("تاییدِ خودکارِ آنلاین", row.auto_accept_online, "auto"),
            [InlineKeyboardButton(text="⏱ مهلتِ کارت", callback_data="pays_dl:card"), InlineKeyboardButton(text="⏱ مهلتِ بله‌پی", callback_data="pays_dl:bale")],
            [InlineKeyboardButton(text="⏱ مهلتِ زرین‌پال", callback_data="pays_dl:zarinpal"), InlineKeyboardButton(text="🕒 مهلتِ بررسیِ رسید", callback_data="pays_hold")],
            [InlineKeyboardButton(text="🔑 مرچنتِ زرین‌پال", callback_data="pays_zp")],
        ]
    )


def payments_entry_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⚙️ روش‌هایِ پرداختِ مشتری", callback_data="pays_menu")]])

