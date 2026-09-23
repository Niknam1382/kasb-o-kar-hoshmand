from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

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
    mode_value = tenant_mode.value if hasattr(tenant_mode, "value") else tenant_mode
    products_label = "🗂 خدمات و بسته‌ها" if mode_value == "consultation" else "📦 محصولات"
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔑 ثبت/ویرایش توکن ربات"), KeyboardButton(text=products_label)],
            [KeyboardButton(text="🧠 دستور هوشمندسازی"), KeyboardButton(text="📢 کانال دانش‌افزایی")],
            [KeyboardButton(text="👀 پیش‌نمایش ربات"), KeyboardButton(text="📊 آمار")],
            [KeyboardButton(text="💰 کیف‌پول"), KeyboardButton(text="🎁 کد معرف")],
            [KeyboardButton(text="🧾 تاریخچه‌ی پرداخت"), KeyboardButton(text="📤 خروجی اکسل")],
            [KeyboardButton(text="✏️ ویرایش اطلاعات"), KeyboardButton(text="👤 پروفایل من")],
            [KeyboardButton(text="🔀 نوعِ کسب‌وکار")],
        ],
        resize_keyboard=True,
    )


def tenant_mode_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛍 فروشِ محصول (فروشگاه)", callback_data="set_tenant_mode:sales")],
            [InlineKeyboardButton(text="💬 مشاوره و خدمات (بدون فروشِ محصول)", callback_data="set_tenant_mode:consultation")],
        ]
    )


def end_preview_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🔚 پایان پیش‌نمایش")]], resize_keyboard=True)


def products_list_keyboard(products, page: int = 0) -> InlineKeyboardMarkup:
    page_items, page, total_pages = _paginate(list(products), page)
    rows = [[InlineKeyboardButton(text=p.name, callback_data=f"product_view:{p.id}")] for p in page_items]
    nav = _pagination_row(page, total_pages, "product_list")
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="➕ افزودن محصول جدید", callback_data="product_add")])
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


def edit_product_field_keyboard(product_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="نام", callback_data=f"product_edit_field:{product_id}:name"), InlineKeyboardButton(text="توضیحات", callback_data=f"product_edit_field:{product_id}:description")],
            [InlineKeyboardButton(text="قیمت", callback_data=f"product_edit_field:{product_id}:price"), InlineKeyboardButton(text="عکس", callback_data=f"product_edit_field:{product_id}:photo")],
            [InlineKeyboardButton(text="موجودی", callback_data=f"product_edit_field:{product_id}:stock")],
        ]
    )


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
            [InlineKeyboardButton(text="🧮 محاسبه‌گرِ هزینه‌ی ماهانه", callback_data="cost_calc_start")],
            [InlineKeyboardButton(text="📜 تاریخچه‌ی تراکنش‌ها", callback_data="wallet_history")],
        ]
    )


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
    if is_super_admin:
        rows.append([KeyboardButton(text="📜 گزارشِ ممیزی"), KeyboardButton(text="🔑 استخرِ کلیدهایِ AI")])
        rows.append([KeyboardButton(text="👑 مدیریتِ ادمین‌ها")])
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
    rows = [
        [InlineKeyboardButton(text=zarinpal_label, callback_data="admin_toggle_zarinpal")],
        [InlineKeyboardButton(text=bale_pay_label, callback_data="admin_toggle_bale_pay")],
        [InlineKeyboardButton(text="🧮 محاسبه‌ی خودکارِ هزینه از فرمول", callback_data="admin_recalc_wallet_cost")],
        [InlineKeyboardButton(text=registrations_label, callback_data="admin_toggle_registrations")],
        [InlineKeyboardButton(text=topups_label, callback_data="admin_toggle_topups")],
        [InlineKeyboardButton(text=maintenance_label, callback_data="admin_toggle_maintenance")],
    ]
    rows += [[InlineKeyboardButton(text=label, callback_data=f"admin_setting_edit:{key}")] for key, label in admin_settings_button_labels(admin_settings)]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_owners_list_keyboard(owners, page: int = 0) -> InlineKeyboardMarkup:
    from app.bots.main_bot.texts import admin_owner_list_item_label

    page_items, page, total_pages = _paginate(list(owners), page)
    rows = [[InlineKeyboardButton(text=admin_owner_list_item_label(o), callback_data=f"admin_owner_view:{o.id}")] for o in page_items]
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


def admin_roles_list_keyboard(roles) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=f"👤 {role.telegram_id}", callback_data=f"admin_role_view:{role.id}")] for role in roles]
    rows.append([InlineKeyboardButton(text="➕ افزودنِ ادمینِ عملیاتیِ جدید", callback_data="admin_role_add")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_role_detail_keyboard(role_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🗑 حذفِ این ادمین", callback_data=f"admin_role_revoke:{role_id}")],
            [InlineKeyboardButton(text="🔙 بازگشت به فهرست", callback_data="admin_role_list")],
        ]
    )
