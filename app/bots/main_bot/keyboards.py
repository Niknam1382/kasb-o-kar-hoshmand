from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from app.bots.common.wizard_nav import page_label
from app.bots.main_bot import texts
from app.utils.text_limits import clip
from app.utils.validators import fa_grouped, fa_number

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
    row.append(InlineKeyboardButton(text=page_label(page, total_pages), callback_data="noop"))
    if page < total_pages - 1:
        row.append(InlineKeyboardButton(text="بعدی ▶️", callback_data=f"{callback_prefix}:{page + 1}"))
    return row


def grid(buttons: list, per_row: int = 2, max_label: int = 0) -> list[list]:
    """چینشِ دونفره (P22): همان ترتیب، `per_row` دکمه در هر ردیف، باقی‌مانده تنها.

    چرا: منوهایِ این پنل سال‌ها «هر دکمه یکِ ردیفِ تمام‌عرض» بودند ⇒ منویِ بی‌نظم و بلند؛
    کاربر هم دقیقاً همین را گفت (سه ردیفِ تک، چند ردیفِ دونفره، یکِ ردیفِ سه‌تایی).
    `max_label` برایِ کیبوردهایِ inline لازم است: تلگرام برچسبِ بلند را در نصفِ عرض با «…»
    می‌بُرد، پس آن دکمه تمام‌عرض می‌ماند. کیبوردهایِ reply (منویِ اصلی) این مشکل را ندارند
    چون متن را می‌شکنند (wrap).
    """
    rows: list[list] = []
    pending: list = []
    for button in buttons:
        if len(pending) == per_row:
            rows.append(pending)
            pending = []
        if max_label and len(getattr(button, "text", "") or "") > max_label:
            if pending:
                rows.append(pending)
                pending = []
            rows.append([button])
        else:
            pending.append(button)
    if pending:
        rows.append(pending)
    return rows


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


def shop_owner_panel_keyboard(tenant_mode=None, knowledge_gap: bool = True, instagram: bool = False) -> ReplyKeyboardMarkup:
    """منویِ فروشگاه‌دار (A4): مشاوره‌ای = بدونِ پرداختِ آنلاین/چک‌اوتِ سبد/کمپین (چیزهایِ مخصوصِ فروش).
    P42 · موردِ ۱: «🟢 هوشمندسازیِ بله» دیگر دکمهٔ منو نیست — داخلِ «🔑 ثبت/ویرایش توکن ربات»
    انتخاب می‌شود؛ آن دکمهٔ سبز ردیفِ اول را از دو به یک می‌انداخت و چینشِ دونفره را می‌شکست.
    P42 · موردِ ۳۵: سوئیچِ ادمینِ «تشخیصِ سوال‌هایِ بی‌جواب» هر دو دکمه‌یِ دانش (بی‌جواب‌ها و
    تاییدشده‌ها) را از *هر دو* پنل می‌برد؛ تا پیشِ این فقط تشخیصِ پشتِ صحنه خاموش می‌شد و
    دکمه‌ها سرِ جای خود بودند.
    P42 · موردِ ۳۳: در مودِ مشاوره‌ای مخاطبِ «پیام به مشتری‌ها»، کاربرِ همان جلسه است نه خریدار.
    P49-الف: «🟣 اینستاگرام» فقط وقتی در می‌آید که ادمین کانال را رونمایی کرده باشد (مثلِ سوئیچِ
    «سوال‌هایِ بی‌جواب»؛ خودِ اتصال یا نبودش تاثیری در دیدنی‌بودنِ دکمه ندارد).
    """
    mode_value = tenant_mode.value if hasattr(tenant_mode, "value") else tenant_mode
    consultation = mode_value == "consultation"
    # C1: مودِ مشاوره‌ای کاتالوگِ محصول/خدمت ندارد (افزودنِ محصول در مشاوره معنا ندارد).
    rows = [["🔑 ثبت/ویرایش توکن ربات"]] if consultation else [["🔑 ثبت/ویرایش توکن ربات"], ["📦 محصولات"]]
    if not consultation:
        rows.append(["🧾 مدیریتِ سفارش‌ها (جاری)"])  # W5: سفارش‌هایِ باز یک‌جا (اعلان‌ها دیگه گم نمی‌شن)
    rows += [
        ["🧠 دستور هوشمندسازی", "📢 کانال دانش‌افزایی"],
        # P43 · موردِ ۳۰: در *هر دو* پنل (فروشگاهی و مشاوره‌ای) ورودیِ نگهبانِ محتوا لازم است.
        [texts.MODERATION_GUARD_BUTTON],
        ["👀 پیش‌نمایش ربات", "📊 آمار"],
        ["💰 کیف‌پول", "🎁 کد معرف"],
        ["🧾 تاریخچه‌ی پرداخت", "📤 خروجی اکسل"],
        ["👤 پروفایل من", "📞 پشتیبانی"],
        [(texts.BROADCAST_CONSULT_BUTTON if consultation else texts.BROADCAST_SALES_BUTTON), texts.SCHEDULED_LIST_BUTTON]
        + ([] if consultation else ["💳 پرداختِ آنلاینِ سفارش‌ها"]),
    ]
    if consultation:
        # C2: CRMِ فروشگاهی جای خود را به «💬 گفتگوها و کاربران» می‌دهد؛ C3: حسابداری هم نیست.
        rows.append(["💬 گفتگوها و کاربران"])
    else:
        rows.append(["📝 سوال‌هایِ چک‌اوتِ سبد"])
        rows.append(["🎯 کمپین‌ها", "👥 مشتری‌ها"])
    if knowledge_gap:
        rows.append(["🧩 سوال‌هایِ بی‌جواب", "📚 پرسش‌وپاسخ‌هایِ تاییدشده"])
    rows.append(["💬 دستیارِ مدیریتی"] if consultation else ["🧮 حسابداری", "💬 دستیارِ مدیریتی"])
    if instagram:
        rows.append([texts.INSTAGRAM_BUTTON])
    rows.append(["⚙️ تنظیماتِ ربات فروشگاه"])
    # P22: چینشِ دونفره. قبلاً ردیف‌ها قاطی بود (سه ردیفِ تک، بعد دونفره، بعد یکِ سه‌تایی) و
    # همین منو را بی‌نظم نشان می‌داد. ترتیبِ خطیِ دکمه‌ها دست‌نخورده است ⇒ هندلرها و تست‌ها سالم‌اند.
    labels = [label for row in rows for label in row]
    return ReplyKeyboardMarkup(keyboard=grid([KeyboardButton(text=label) for label in labels]), resize_keyboard=True)

def profile_keyboard() -> InlineKeyboardMarkup:
    """P22: شش فعلِ این صفحه در سه ردیفِ دونفره (قبلاً دو ردیفِ تک در آخر داشت)."""
    return InlineKeyboardMarkup(
        inline_keyboard=grid(
            [
                InlineKeyboardButton(text="✏️ نام", callback_data="pf_edit:first_name"),
                InlineKeyboardButton(text="✏️ نامِ خانوادگی", callback_data="pf_edit:last_name"),
                InlineKeyboardButton(text="✏️ موبایل", callback_data="pf_edit:phone"),
                InlineKeyboardButton(text="✏️ ایمیل", callback_data="pf_edit:email"),
                InlineKeyboardButton(text="🔀 نوعِ کسب‌وکار", callback_data="pf_mode"),
                InlineKeyboardButton(text="📞 پشتیبانیِ پلتفرم", callback_data="pf_support"),
            ],
            max_label=26,
        )
    )


def tenant_mode_ask_keyboard(target: str) -> InlineKeyboardMarkup:
    label = "🛍 تغییر به فروشگاهی" if target == "sales" else "💬 تغییر به مشاوره‌ای"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=label, callback_data=f"tenant_mode_ask:{target}")],
            [InlineKeyboardButton(text="⬅️ انصراف", callback_data="pf_back")],
        ]
    )


def tenant_mode_confirm_keyboard(target: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ بله، تغییر بده", callback_data=f"set_tenant_mode:{target}")],
            [InlineKeyboardButton(text="⬅️ نه", callback_data="pf_back")],
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
    # C1: افزودنِ محصول (تکی و گروهی) فقط مودِ فروشگاهی — مشاوره نباید «محصول» بسازد.
    if sales_mode:
        # P22: چهار فعلِ این صفحه دونادونه شد (قبلاً چهار ردیفِ تک). ردیفِ نامِ محصولات تک می‌ماند
        # چون نامِ محصول متنِ صاحبِ فروشگاه است و در نصفِ عرض با «…» بریده می‌شود.
        rows.extend(
            grid(
                [
                    InlineKeyboardButton(text="➕ افزودن محصول جدید", callback_data="product_add"),
                    InlineKeyboardButton(text="💾 افزودنِ محصولِ دیجیتال", callback_data="product_add_digital"),
                    InlineKeyboardButton(text="🚚 روش‌هایِ ارسال", callback_data="shipping_list"),
                    InlineKeyboardButton(text="📥 افزودن گروهی از اکسل", callback_data="product_bulk_import"),
                ],
                max_label=26,
            )
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def product_import_confirm_keyboard(valid_count: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"✅ بله، {fa_number(valid_count)} محصول اضافه کن", callback_data="product_bulk_import_confirm")],
            [InlineKeyboardButton(text="❌ انصراف", callback_data="product_bulk_import_cancel")],
        ]
    )


def product_detail_keyboard(product_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ ویرایش", callback_data=f"product_edit:{product_id}"), InlineKeyboardButton(text="🗑 حذف", callback_data=f"product_delete:{product_id}")],
            [InlineKeyboardButton(text="⬅️ بازگشت به فهرست", callback_data="product_list")],
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
        toggle = "✅" if method.is_active else "⏸"  # نشانِ وضعیتِ فعلی؛ با زدنش عوض می‌شود
        rows.append(
            [
                InlineKeyboardButton(text=clip(f"{toggle} · {method.name}", 26), callback_data=f"ship_toggle:{method.id}"),
                InlineKeyboardButton(text="🗑", callback_data=f"ship_del:{method.id}"),
            ]
        )
    rows.append([InlineKeyboardButton(text="➕ افزودنِ روشِ ارسال", callback_data="ship_add")])
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت به فهرستِ محصولات", callback_data="product_list")])
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

    # P22: چهار ردیفِ تک ⇒ دو ردیفِ دونفره
    return InlineKeyboardMarkup(
        inline_keyboard=grid(
            [
                InlineKeyboardButton(text=wallet_topup_action_label(), callback_data="topup_start"),
                InlineKeyboardButton(text="📂 پرداخت‌هایِ باز", callback_data="topup_open_list"),
                InlineKeyboardButton(text="🧮 محاسبه‌گرِ هزینه‌ی ماهانه", callback_data="cost_calc_start"),
                InlineKeyboardButton(text="📜 تاریخچه‌ی تراکنش‌ها", callback_data="wallet_history"),
            ],
            max_label=26,
        )
    )


def wallet_history_keyboard(
    *,
    newer_cursor: int | None = None,
    older_cursor: int | None = None,
    next_cursor: int | None = None,
) -> InlineKeyboardMarkup:
    rows = []
    navigation = []
    if newer_cursor is not None:
        navigation.append(InlineKeyboardButton(text=texts.WALLET_HISTORY_NEWER, callback_data=f"wallet_history_page:newer:{newer_cursor}"))
    if older_cursor is not None:
        navigation.append(InlineKeyboardButton(text=texts.WALLET_HISTORY_OLDER, callback_data=f"wallet_history_page:older:{older_cursor}"))
    if navigation:
        rows.append(navigation)
    rows.append([InlineKeyboardButton(text=texts.WALLET_HISTORY_EXPORT, callback_data="wallet_history_export")])
    if next_cursor is not None:
        rows.append([InlineKeyboardButton(text=texts.WALLET_HISTORY_EXPORT_NEXT, callback_data=f"wallet_history_export:{next_cursor}")])
    rows.append([InlineKeyboardButton(text=texts.WALLET_HISTORY_START, callback_data="wallet_history")])
    rows.append([InlineKeyboardButton(text="بازگشت به پنل", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


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
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data="wallet_status")])
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


def topup_amount_keyboard(minimum_toman: int = 0) -> InlineKeyboardMarkup:
    from app.bots.main_bot import texts

    rows = [
        [InlineKeyboardButton(text=texts.topup_amount_button_label(amount), callback_data=f"topup_amount:{amount}")]
        for amount in texts.topup_presets_for(minimum_toman)
    ]
    rows.append([InlineKeyboardButton(text="✏️ مبلغ دلخواه", callback_data="topup_amount:custom")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def wallet_ledger_keyboard() -> InlineKeyboardMarkup:
    """PHASE 5E: همسنجیِ دفتر از همان پیامی که اکسلِ دفتر را می‌فرستد (فقط سوپرادمین)."""
    from app.bots.main_bot import texts

    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=texts.ADMIN_WALLET_RECONCILE_LABEL, callback_data="admin_reconcile_wallets")]])


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
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔵 باز کردنِ پرداخت در اپِ بله", url=pay_url)]])


def admin_payment_approval_keyboard(payment_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ تایید", callback_data=f"admin_approve_payment:{payment_id}"), InlineKeyboardButton(text="❌ رد", callback_data=f"admin_reject_payment:{payment_id}")],
        ]
    )


def admin_payment_queue_keyboard(payments, owners, page: int, total_pages: int) -> InlineKeyboardMarkup:
    """پ۵۴ · موردِ ۱۲: هر پرداخت یکِ دکمه (شماره‌دار، به همان ترتیبِ متن) + صفحه‌گردانی.

    شمارهٔ صفحه داخلِ callback می‌آید تا کارتِ جزئیات بتواند به همان صفحه برگردد؛ این
    حالتِ بی‌حالت، جایِ نگه‌داشتنِ صفحه در FSM است (و با stateهایِ دیگرِ پنلِ ادمین قاطی نمی‌شود).
    """
    rows = [
        [InlineKeyboardButton(
            text=texts.admin_payment_queue_button(payment, owners.get(payment.shop_owner_id), index),
            callback_data=f"pay_queue_view:{page}:{payment.id}",
        )]
        for index, payment in enumerate(payments, start=1)
    ]
    pagination = _pagination_row(page, total_pages, "pay_queue")
    if pagination:
        rows.append(pagination)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_payment_detail_keyboard(payment_id: int, page: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ تایید", callback_data=f"admin_approve_payment:{payment_id}"), InlineKeyboardButton(text="❌ رد", callback_data=f"admin_reject_payment:{payment_id}")],
            [InlineKeyboardButton(text="🧾 بازگشت به صف", callback_data=f"pay_queue:{page}")],
        ]
    )


def _ai_usage_window_row(window: str) -> list[InlineKeyboardButton]:
    """یکِ ردیفِ تعویضِ پنجره (۲۴ ساعت/۷ روز/۳۰ روز) با تیکِ پنجرهٔ فعال."""
    return [
        InlineKeyboardButton(text=("✅ " if key == window else "") + label, callback_data=f"ai_usage:{key}:0")
        for key, label in texts.AI_USAGE_WINDOWS
    ]


def ai_usage_windows_keyboard(window: str) -> InlineKeyboardMarkup:
    """نمایِ خالی: فقط پنجره‌ها و بازگشت (صفحه‌گردانیِ بی‌مورد نیست)."""
    return InlineKeyboardMarkup(inline_keyboard=[_ai_usage_window_row(window), [InlineKeyboardButton(text="⬅️ بازگشت به پنل", callback_data="main_menu")]])


def ai_usage_keyboard(items, window: str, page: int, total_pages: int) -> InlineKeyboardMarkup:
    """items = [(customer_id, index, name)] — همان ترتیبِ خطوطِ متن، تا شماره‌ها جفت بمانند.

    ردیفِ پنجره‌ها همیشه می‌آید، ولی ردیفِ صفحه‌گردانی فقط وقتی بیش از یکِ صفحه هست.
    """
    rows = [_ai_usage_window_row(window)]
    rows += [
        [InlineKeyboardButton(text=f"{fa_number(index)} · {clip(name, 26)}", callback_data=f"ai_usage_view:{window}:{page}:{customer_id}")]
        for customer_id, index, name in items
    ]
    pagination = _pagination_row(page, total_pages, f"ai_usage:{window}")
    if pagination:
        rows.append(pagination)
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت به پنل", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def ai_usage_detail_keyboard(customer_id: int, window: str, page: int, *, paused: bool, blocked: bool) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔢 سقفِ ۲۴ ساعت", callback_data=f"ai_usage_limit:{customer_id}:{window}:{page}"),
                InlineKeyboardButton(
                    text=("▶️ آزادکردنِ پاسخ" if paused else "⏸ توقفِ ۲۴ ساعت"),
                    callback_data=f"ai_usage_pause:{customer_id}:{0 if paused else 24}:{window}:{page}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=("✅ رفعِ بلاک" if blocked else "🚫 بلاکِ کاربر"),
                    callback_data=f"ai_usage_block:{customer_id}:{1 if blocked else 0}:{window}:{page}",
                ),
                InlineKeyboardButton(text="📊 بازگشت به فهرست", callback_data=f"ai_usage:{window}:{page}"),
            ],
        ]
    )


def excel_export_choice_keyboard(consultation: bool = False) -> InlineKeyboardMarkup:
    # C1: در مودِ مشاوره‌ای برچسبِ خروجی هم نباید «سفارش» بگوید.
    first = "👥 فهرست مخاطبان" if consultation else "👥 فهرست مشتریان"
    second = "🧾 فهرست مشاوره‌ها" if consultation else "🧾 سفارش‌ها و مشاوره‌ها"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=first, callback_data="export_excel:customers")],
            [InlineKeyboardButton(text=second, callback_data="export_excel:orders")],
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
                InlineKeyboardButton(text=texts.SCHEDULE_BROADCAST_BUTTON, callback_data="customer_broadcast_schedule"),
            ],
            [InlineKeyboardButton(text="❌ لغو", callback_data="customer_broadcast_cancel")],
        ]
    )


def audit_filter_keyboard(group: str | None, window: str | None, has_range: bool = False) -> InlineKeyboardMarkup:
    """P21-E (F9): دسته‌بندی + بازهٔ زمانی + خروجیِ CSV در همان صفحهٔ گزارشِ ممیزی.
    P22: همه در ردیف‌هایِ دونفره (قبلاً سه‌تا/چهارتا در هر خط).
    P48 (موردِ ۳۹): «🗓 بازهٔ دلخواه» و، فقط وقتی بازه‌ای ذخیره شده, «✖️ حذفِ بازه»."""
    from app.bots.main_bot import texts

    group_buttons = [
        InlineKeyboardButton(
            text=("✅ " if (group or "all") == code else "") + label, callback_data=f"audit_filter:{code}"
        )
        for code, label in texts.AUDIT_FILTER_GROUPS
    ]
    window_buttons = [
        InlineKeyboardButton(
            text=("✅ " if (window or "all") == code else "") + label, callback_data=f"audit_window:{code}"
        )
        for code, label in texts.AUDIT_FILTER_WINDOWS
    ]
    range_buttons = [InlineKeyboardButton(text=texts.AUDIT_RANGE_BUTTON, callback_data="audit_range_from")]
    if has_range:
        range_buttons.append(InlineKeyboardButton(text=texts.AUDIT_RANGE_CLEAR_BUTTON, callback_data="audit_range_clear"))
    rows = grid(group_buttons) + grid(window_buttons) + grid(range_buttons)
    rows.append([InlineKeyboardButton(text=texts.AUDIT_CSV_BUTTON, callback_data="audit_csv")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def server_log_keyboard(view: str) -> InlineKeyboardMarkup:
    """P48 (موردِ ۱۳): دو نمایِ هشدار/خطا + تازه‌کردن + بازگشت به پنلِ سوپرادمین."""
    def marked(code: str, label: str) -> InlineKeyboardButton:
        return InlineKeyboardButton(text=("✅ " if view == code else "") + label, callback_data=f"logs_view:{code}")

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [marked("warnings", texts.LOGS_VIEW_WARNINGS_BUTTON), marked("errors", texts.LOGS_VIEW_ERRORS_BUTTON)],
            [InlineKeyboardButton(text=texts.LOGS_REFRESH_BUTTON, callback_data="logs_refresh")],
            [InlineKeyboardButton(text=texts.LOGS_BACK_BUTTON, callback_data="main_menu")],
        ]
    )


def scheduled_cancel_keyboard(rows) -> InlineKeyboardMarkup:
    """دکمهٔ لغوِ هر ارسالِ زمان‌بندی‌شده.

    برچسب شمارهٔ *صفحه‌ای* (۱..N) را نشان می‌دهد نه `row.id` — قراردادِ پروژه: شناسهٔ داخلیِ
    دیتابیس در متنِ کاربر نیاید (شناسه فقط در callback_data می‌نشیند و سمتِ سرور با
    `shop_bot_id` محدود می‌شود). قبلاً همین تابع برخلافِ docstring خودش شمارهٔ ردیف را لو می‌داد.
    """
    buttons = [
        InlineKeyboardButton(text=texts.schedule_cancel_button_label(position), callback_data=f"sched_cancel:{row.id}")
        for position, row in enumerate(rows, start=1)
    ]
    buttons.append(InlineKeyboardButton(text=texts.SCHEDULE_NEW_BUTTON, callback_data="sched_new"))
    buttons.append(InlineKeyboardButton(text="⬅️ بازگشت به پنل", callback_data="main_menu"))
    return InlineKeyboardMarkup(inline_keyboard=grid(buttons, max_label=26))


def scheduled_empty_keyboard() -> InlineKeyboardMarkup:
    """صفحهٔ خالیِ «ارسال‌های زمان‌بندی‌شده» نباید بن‌بست باشد (گزارشِ کاربر: «چیزی نداره که کار کنه»)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=texts.SCHEDULE_NEW_BUTTON, callback_data="sched_new")],
            [InlineKeyboardButton(text="⬅️ بازگشت به پنل", callback_data="main_menu")],
        ]
    )


def schedule_when_keyboard() -> InlineKeyboardMarkup:
    """P26: «کی ارسال شود؟» با پنج گزینهٔ آماده — نوشتنِ ساعت فقط یکِ انتخاب است، نه شرط."""
    buttons = [
        InlineKeyboardButton(text="+۱ ساعت", callback_data="sched_when:1h"),
        InlineKeyboardButton(text="+۳ ساعت", callback_data="sched_when:3h"),
        InlineKeyboardButton(text="امشب ۲۱:۰۰", callback_data="sched_when:tonight"),
        InlineKeyboardButton(text="فردا ۱۰:۰۰", callback_data="sched_when:tom10"),
        InlineKeyboardButton(text="فردا ۱۸:۰۰", callback_data="sched_when:tom18"),
        InlineKeyboardButton(text="✍️ ساعتِ دلخواه", callback_data="sched_when:custom"),
        InlineKeyboardButton(text="❌ لغو", callback_data="customer_broadcast_cancel"),
    ]
    return InlineKeyboardMarkup(inline_keyboard=grid(buttons, max_label=20))


def admin_panel_keyboard(is_super_admin: bool) -> ReplyKeyboardMarkup:
    """
    ادمینِ عملیاتی (is_super_admin=False) دکمه‌هایِ حساس رو اصلاً نمی‌بینه:
    تنظیماتِ قیمت/تخفیف، تنظیماتِ کلیدها، استخرِ کلیدهایِ AI، و مدیریتِ
    ادمین‌ها. اگه is_super_admin=True باشه، دقیقاً همونِ کیبوردِ قبل از
    RBAC رو می‌بینه (به‌علاوه‌ی دکمه‌ی جدیدِ مدیریتِ ادمین‌ها).

    P22: چینشِ دونفره با حفظِ ترتیب (قبلاً «⏱ اعتبار و زمان» و برایِ ادمینِ عملیاتی
    «📜 گزارشِ ممیزی» تنها در ردیفِ خودش بودند و منو دُم‌دار می‌شد).
    """
    buttons = [
        KeyboardButton(text="📢 مدیریت کانال‌های اجباری"),
        KeyboardButton(text="🧾 صف تایید پرداخت‌ها"),
    ]
    if is_super_admin:
        buttons += [KeyboardButton(text="💰 تنظیمات قیمت و تخفیف"), KeyboardButton(text="🔑 تنظیمات کلیدها")]
    buttons += [
        KeyboardButton(text="📊 آمار سراسری"),
        KeyboardButton(text="📈 وضعیتِ همزمانی و عملکرد"),  # P30
        KeyboardButton(text="📣 پیام همگانی"),
        KeyboardButton(text="👥 مدیریت فروشگاه‌دارها"),
        KeyboardButton(text="🧹 کاربرانِ غیرفعال"),  # P22 · مشکلِ ۸
        KeyboardButton(text="🛡 نگهبانِ محتوا"),
        KeyboardButton(text="⏱ اعتبار و زمان"),  # W5 · K1–K4
        KeyboardButton(text="📜 گزارشِ ممیزی"),
    ]
    if is_super_admin:
        buttons += [
            KeyboardButton(text="🔑 استخرِ کلیدهایِ AI"),
            KeyboardButton(text="👑 مدیریتِ ادمین‌ها"),
            KeyboardButton(text="📤 دفترِ کیف‌پول (اکسل)"),
            KeyboardButton(text=texts.SERVER_LOG_BUTTON),  # P48 · موردِ ۱۳ (فقط سوپرادمین)
            KeyboardButton(text=texts.AI_USAGE_BUTTON),  # P55 · موردِ ۲۳ (فقط سوپرادمین)
            KeyboardButton(text=texts.CAPACITY_BUTTON),  # P61 · خواستهٔ ۱۱-۱۲ (فقط سوپرادمین)
            KeyboardButton(text=texts.DOCTOR_BUTTON),  # P62 · خواستهٔ ۱۱-۱۲ (فقط سوپرادمین)
        ]
    return ReplyKeyboardMarkup(keyboard=grid(buttons), resize_keyboard=True)


def capacity_keyboard() -> InlineKeyboardMarkup:
    """پ۶۱: صفحهٔ ظرفیت فقط خواندنی است — «تازه‌سازی» و «بازگشت به پنل»، هیچ فعلِ مدیریتی دیگر."""
    from app.bots.main_bot import texts

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=texts.CAPACITY_REFRESH, callback_data="capacity_refresh")],
            [InlineKeyboardButton(text="⬅️ بازگشت به پنل", callback_data="main_menu")],
        ]
    )


def doctor_keyboard() -> InlineKeyboardMarkup:
    """پ۶۲: عیب‌یاب هم مثلِ ظرفیت فقط‌خواندنی است؛ اقدام‌ها در همان پنل‌هایِ موجود انجام می‌شوند."""
    from app.bots.main_bot import texts

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=texts.DOCTOR_REFRESH, callback_data="doctor_refresh")],
            [InlineKeyboardButton(text=texts.CAPACITY_REFRESH, callback_data="capacity_refresh")],
            [InlineKeyboardButton(text="⬅️ بازگشت به پنل", callback_data="main_menu")],
        ]
    )


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
    # A6: UIِ «طرح‌های اشتراک» حذف شد (جدول و سرویسِ داده دست‌نخورده ماندند).
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏷 کدهای تخفیف", callback_data="admin_pricing_discounts")],
        ]
    )


def admin_discounts_list_keyboard(codes) -> InlineKeyboardMarkup:
    rows = []
    for c in codes:
        status = "✅" if c.is_active else "❌"
        # `type` یا enum است یا رشتهٔ خامِ ستون (بسته به مسیرِ خواندن) — هر دو شکلِ قدیمی هم
        # هنوز نمایش داده می‌شوند؛ «مبلغ ثابت» از P25 فقط قابلِ ساخت نیست، نه قابلِ خواندن.
        type_value = c.type.value if hasattr(c.type, "value") else c.type
        if type_value == "percent":
            value_label = f"{fa_number(f'{float(c.value):g}')}٪"
        else:
            value_label = f"{fa_grouped(int(c.value))} تومان (قدیمی)"
        rows.append([InlineKeyboardButton(text=f"{status} {c.code} ({value_label})", callback_data=f"admin_discount_toggle:{c.id}")])
    rows.append([InlineKeyboardButton(text="➕ افزودن کد جدید", callback_data="admin_discount_add")])
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data="admin_pricing_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def switch_short_label(enabled: bool) -> str:
    """جفتِ استانداردِ سوییچ وقتی موضوع در متنِ همان صفحه نوشته شده است."""
    return "⏸ خاموش‌کردن" if enabled else "✅ روشن‌کردن"


def switch_label(subject: str, enabled: bool) -> str:
    """برچسبِ یکتایِ همهٔ سوییچ‌ها: «⏸ خاموش‌کردنِ …» وقتی روشن است، «✅ روشن‌کردنِ …» وقتی خاموش.

    تا پیشِ این یکِ مفهوم در این پنل پنج جور نوشته می‌شد («غیرفعال», «غیرفعال کن»,
    «غیرفعال‌کردن», «توقف», «معلق») و دو طرفِ یکِ جفت فعلِ مخالف نداشتند
    («پنهان‌کردنِ» ↔ «رونماییِ») — فروشگاه‌دار مجبور بود حدس بزند هر دکمه چه می‌کند."""
    return f"⏸ خاموش‌کردنِ {subject}" if enabled else f"✅ روشن‌کردنِ {subject}"


def perf_report_keyboard(range_key: str, has_range: bool = False) -> InlineKeyboardMarkup:
    rows = [[
        InlineKeyboardButton(
            text=("✅ " if key == range_key and not has_range else "") + label,
            callback_data=f"perf_range:{key}",
        )
        for key, label in texts.PERF_RANGE_BUTTONS
    ]]
    extra = [InlineKeyboardButton(text="🗓 بازهٔ دلخواه", callback_data="perf_range_from")]
    if has_range:
        extra.append(InlineKeyboardButton(text="✖️ حذفِ بازه", callback_data="perf_range_clear"))
    rows.append(extra)
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت به پنل", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_settings_menu_keyboard(admin_settings) -> InlineKeyboardMarkup:
    """صفحه‌یِ اصلیِ تنظیمات: فقط کلیدهایِ روشن/خاموشِ پلتفرم + دسته‌ها.

    چهلِ مقدارِ ویرایشی در یک صفحه‌یِ تخت گم می‌شدند؛ حالا هر مقدار داخلِ دسته‌یِ خودش
    ویرایش می‌شود (`admin_settings_group_keyboard`) و این صفحه فقط سوییچ‌هایِ کلِ پلتفرم را نشان می‌دهد."""
    from app.bots.main_bot import texts

    zarinpal_label = switch_label("زرین‌پال از فروشگاه‌دارها", admin_settings.zarinpal_enabled)
    bale_pay_label = switch_label("بله‌پی از فروشگاه‌دارها", admin_settings.bale_pay_enabled)
    bale_bots_label = switch_label("رباتِ بله‌یِ فروشگاه‌ها", admin_settings.bale_shop_bots_enabled)
    # P49-الف: سوییچِ کانالِ اینستاگرام (پیش‌فرض خاموش ⇒ دکمهٔ پنل نیست و رویدادی پاسخ نمی‌رود).
    instagram_label = switch_label("کانالِ اینستاگرام", admin_settings.instagram_enabled)
    sms_label = switch_label("پیامکِ احراز", admin_settings.sms_enabled)
    registrations_label = switch_label("ثبت‌نامِ کاربرانِ جدید", admin_settings.allow_new_registrations)
    topups_label = switch_label("شارژِ کیف‌پول", admin_settings.allow_wallet_topups)
    maintenance_label = switch_label("حالتِ تعمیر (کلِ پلتفرم)", admin_settings.maintenance_mode)
    nightly_report_label = switch_label("گزارشِ شبانه", admin_settings.nightly_report_enabled)
    knowledge_gap_label = switch_label("تشخیصِ سوال‌هایِ بی‌جواب", admin_settings.knowledge_gap_enabled)
    commission_label = switch_label("کمیسیونِ سفارش", admin_settings.commission_enabled)
    zero_credit_label = switch_label("ادامهٔ سفارش با اعتبارِ صفر", admin_settings.orders_allowed_when_wallet_empty)
    rows = [
        [InlineKeyboardButton(text=maintenance_label, callback_data="admin_toggle_maintenance")],
        [InlineKeyboardButton(text=registrations_label, callback_data="admin_toggle_registrations")],
        [InlineKeyboardButton(text=topups_label, callback_data="admin_toggle_topups")],
        [InlineKeyboardButton(text=zarinpal_label, callback_data="admin_toggle_zarinpal")],
        [InlineKeyboardButton(text=bale_pay_label, callback_data="admin_toggle_bale_pay")],
        [InlineKeyboardButton(text=bale_bots_label, callback_data="admin_toggle_bale_bots")],
        # P49-الف: همان شکلِ «admin_toggle_bale_bots» (صفحهٔ اصلی فقط سوییچ‌ها را نگه می‌دارد).
        [InlineKeyboardButton(text=instagram_label, callback_data="admin_toggle_instagram")],
        [InlineKeyboardButton(text=sms_label, callback_data="admin_toggle_sms")],
        [InlineKeyboardButton(text=commission_label, callback_data="admin_toggle_commission")],
        [InlineKeyboardButton(text=zero_credit_label, callback_data="admin_toggle_zero_credit_orders")],
        [InlineKeyboardButton(text=nightly_report_label, callback_data="admin_toggle_nightly_report")],
        [InlineKeyboardButton(text=knowledge_gap_label, callback_data="admin_toggle_knowledge_gap")],
    ]
    rows += [
        [
            InlineKeyboardButton(
                text=f"{label} ({len(texts.admin_settings_button_labels(admin_settings, group=key))} مورد)",
                callback_data=f"admin_settings_group:{key}",
            )
        ]
        for key, label in texts.ADMIN_SETTINGS_GROUPS
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_settings_group_keyboard(group: str, admin_settings) -> InlineKeyboardMarkup:
    """مقدارهایِ یک دسته + ابزارهایِ همان دسته + بازگشت به صفحه‌یِ اصلی."""
    from app.bots.main_bot import texts

    rows = [
        [InlineKeyboardButton(text=label, callback_data=f"admin_setting_edit:{key}")]
        for key, label in texts.admin_settings_button_labels(admin_settings, group=group)
    ]
    if group == "pricing":
        rows.append([InlineKeyboardButton(text="🧮 محاسبه‌ی خودکارِ هزینه از فرمول", callback_data="admin_recalc_wallet_cost")])
    if group == "bale":
        rows.append([InlineKeyboardButton(text="🧪 آزمایشِ بله‌پی", callback_data="admin_bale_selftest")])
        rows.append([InlineKeyboardButton(text="🔎 آخرین رویدادهایِ پرداخت", callback_data="admin_payment_events")])
    if group == "branding":
        rows.append([InlineKeyboardButton(text="🧴 همگام‌سازیِ بیوگرافیِ ربات‌ها", callback_data="admin_branding_sync")])
        rows.append([InlineKeyboardButton(text="📊 گزارشِ دستکاریِ بیوگرافی", callback_data="admin_branding_report")])
    if group == "shops":
        rows.append([InlineKeyboardButton(text="📮 صفِ اعلان‌هایِ ارسال‌نشده", callback_data="admin_notification_queue")])
    if group == "payments":
        rows.append([InlineKeyboardButton(text="🧾 طلبِ کمیسیونِ فروشگاه‌ها", callback_data="admin_commission_debt")])
    if group == "ops":
        # P44 · موردِ ۵۱: بکاپِ خودکار + دریافتِ دستیِ تازه‌ترین فایل
        rows.append(
            [
                InlineKeyboardButton(
                    text=switch_label("ارسالِ خودکارِ بکاپ به ادمین", admin_settings.nightly_backup_enabled),
                    callback_data="admin_toggle_nightly_backup",
                )
            ]
        )
        rows.append([InlineKeyboardButton(text="📦 ارسالِ دستیِ آخرین بکاپ", callback_data="admin_send_last_backup")])
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت به فهرستِ تنظیمات", callback_data="admin_settings_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def notification_queue_retry_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=texts.NOTIFICATION_QUEUE_RETRY_BUTTON, callback_data="admin_notification_retry")]]
    )


def admin_owners_list_keyboard(
    owners, page: int = 0, shop_bots_by_owner: dict | None = None, callback_prefix: str = "admin_owners_list",
    search_row: bool = False, total_pages: int | None = None, back_to_list_row: bool = False,
) -> InlineKeyboardMarkup:
    """shop_bots_by_owner: {شناسه‌یِ فروشگاه‌دار: ShopBot | None}؛ اگه داده بشه برچسبِ هر دکمه «وضعیت + نام + @ربات» می‌شه.

    P56 · موردِ ۲۷: `callback_prefix` باعث می‌شود همان فهرست برایِ «نتیجهٔ جست‌وجو» هم مصرف شود،
    بدونِ اینکه صفحه‌گردانیِ آن کاربر را به فهرستِ کامل برگرداند. `search_row` دکمهٔ جست‌وجو را
    فقط به فهرستِ اصلی اضافه می‌کند. `total_pages` وقتی داده می‌شود که صفحه‌بندی در SQL انجام
    شده است (جست‌وجو)؛ وگرنه دوبار صفحه‌بندی کردن، صفحهٔ دوم را بی‌دکمه می‌کرد.
    """
    from app.bots.main_bot import texts

    if total_pages is None:
        page_items, page, total_pages = _paginate(list(owners), page)
    else:
        page_items = list(owners)
        page = min(max(0, page), max(0, total_pages - 1))
    rows = []
    for owner in page_items:
        if shop_bots_by_owner is None:
            label = texts.admin_owner_list_item_label(owner)
        else:
            label = texts.admin_owner_list_item_label(owner, shop_bots_by_owner.get(owner.id))
        rows.append([InlineKeyboardButton(text=label, callback_data=f"admin_owner_view:{owner.id}")])
    nav = _pagination_row(page, total_pages, callback_prefix)
    if nav:
        rows.append(nav)
    if search_row:
        rows.append([InlineKeyboardButton(text=texts.ADMIN_OWNER_SEARCH_BUTTON, callback_data="admin_owner_search")])
    if back_to_list_row:
        rows.append([InlineKeyboardButton(text="👥 فهرستِ کاملِ فروشگاه‌دارها", callback_data="admin_owners_list:0")])
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
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت به فهرست", callback_data="admin_owners_list")])
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


def moderation_report_keyboard(
    report_id: int,
    *,
    blocked: bool,
    chat_cb: str | None = None,
    profile_cb: str | None = None,
    back_cb: str = "mod_list:0",
) -> InlineKeyboardMarkup:
    """P43 · موردِ ۱۰: رویِ هر گزارشِ نگهبانِ محتوا، «گفتگو» و «مشخصاتِ کاربر» هم هستند.

    دو دکمهٔ دیدنِ چت از بیرون پاس داده می‌شوند (`crm_conv:<id>:0` / `cc_card:<id>:0`) تا
    صفحهٔ تکراری ساخته نشود؛ اگر مشتری حذف شده باشد، `None` می‌آید و دکمه ساخته نمی‌شود
    (دکمهٔ مرده دقیقاً همان چیزی است که مالکِ محصول چند بار گزارش کرده).
    """
    rows = []
    pair = []
    if chat_cb:
        pair.append(InlineKeyboardButton(text="👁 گفتگو", callback_data=chat_cb))
    if profile_cb:
        pair.append(InlineKeyboardButton(text="👤 مشخصاتِ کاربر", callback_data=profile_cb))
    if pair:
        rows.append(pair)
    rows.append(
        [
            InlineKeyboardButton(
                text="✅ رفعِ بلاک" if blocked else "🚫 بلاکِ این کاربر",
                callback_data=f"mod_unblock:{report_id}" if blocked else f"mod_block:{report_id}",
            ),
            InlineKeyboardButton(text="✅ بررسی شد", callback_data=f"mod_done:{report_id}"),
        ]
    )
    rows.append([InlineKeyboardButton(text="⬅️ فهرستِ گزارش‌ها", callback_data=back_cb)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def moderation_reports_list_keyboard(reports, page: int, total_pages: int, *, list_cb: str = "mod_list") -> InlineKeyboardMarkup:
    """فهرستِ گزارش‌ها؛ هر گزارش یکِ دکمهٔ تمام‌عرض (برچسبِ بلند در نصفِ عرض با «…» می‌بُرد)."""
    from app.bots.main_bot import texts as _texts

    rows = [
        [InlineKeyboardButton(text=_texts.moderation_report_list_button(rep, index + 1)[:56], callback_data=f"mod_open:{rep.id}")]
        for index, rep in enumerate(reports)
    ]
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️ قبلی", callback_data=f"{list_cb}:{page - 1}"))
    if page + 1 < total_pages:
        nav.append(InlineKeyboardButton(text="بعدی ➡️", callback_data=f"{list_cb}:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت به پنل", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def moderation_rules_list_keyboard(rules) -> InlineKeyboardMarkup:
    rows = []
    for rule in rules:
        status_icon = "🟢" if rule.is_active else "⚪️"
        action_value = rule.action.value if hasattr(rule.action, "value") else rule.action
        label = f"{status_icon} «{rule.pattern}» ({action_value})"
        rows.append([InlineKeyboardButton(text=label[:60], callback_data=f"mod_rule_view:{rule.id}")])
    rows.append([InlineKeyboardButton(text="➕ افزودنِ قانونِ جدید", callback_data="mod_rule_add")])
    rows.append([InlineKeyboardButton(text="📋 گزارش‌هایِ بازِ فروشگاه‌ها", callback_data="mod_admin_list:0")])
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
    toggle_label = switch_short_label(is_active)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=toggle_label, callback_data=f"mod_rule_toggle:{rule_id}")],
            [InlineKeyboardButton(text="🗑 حذف", callback_data=f"mod_rule_delete:{rule_id}")],
            [InlineKeyboardButton(text="⬅️ بازگشت به فهرست", callback_data="mod_rules_list")],
        ]
    )


def ai_pool_list_keyboard(entries, can_import_legacy: bool = False) -> InlineKeyboardMarkup:
    """فهرستِ کلیدها با شمارهٔ ترتیبی (کلید ۱ … کلید ۱۰) + سهمِ همزمانیِ هرِ کلید."""
    rows = []
    for index, entry in enumerate(entries, start=1):
        status_icon = "🟢" if entry.is_active else "⚪️"
        cap = entry.capability.value if hasattr(entry.capability, "value") else entry.capability
        share = entry.max_concurrent if entry.max_concurrent else "مساوی"
        if share != "مساوی":
            share = fa_number(share)
        label = f"{status_icon} کلید {fa_number(index)} · {entry.label} ({cap}) · همزمان: {share}"
        rows.append([InlineKeyboardButton(text=label[:64], callback_data=f"ai_pool_view:{entry.id}")])
    rows.append([InlineKeyboardButton(text="➕ افزودنِ کلیدِ جدید", callback_data="ai_pool_add")])
    if can_import_legacy:
        rows.append([InlineKeyboardButton(text="⬆️ انتقالِ کلیدِ قدیمی به کلیدِ ۱", callback_data="ai_pool_import")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def ai_pool_entry_detail_keyboard(entry_id: int, is_active: bool) -> InlineKeyboardMarkup:
    toggle_label = "⏸ غیرفعال‌کردن" if is_active else "▶️ فعال‌کردن"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=toggle_label, callback_data=f"ai_pool_toggle:{entry_id}")],
            [InlineKeyboardButton(text="🔢 سقفِ همزمانیِ همینِ کلید", callback_data=f"ai_pool_cap:{entry_id}")],
            [InlineKeyboardButton(text="🧵 مدل‌هایِ پشتیبانِ همین کلید", callback_data=f"ai_pool_models:{entry_id}")],
            [InlineKeyboardButton(text="🗑 حذف", callback_data=f"ai_pool_delete:{entry_id}")],
            [InlineKeyboardButton(text="⬅️ بازگشت به فهرست", callback_data="ai_pool_list")],
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
            [InlineKeyboardButton(text=texts.ADMIN_ROLE_SCOPE_BUTTON, callback_data=f"admin_role_scope:{role_id}")],
            [InlineKeyboardButton(text="🗑 حذفِ این ادمین", callback_data=f"admin_role_revoke:{role_id}")],
            [InlineKeyboardButton(text="⬅️ بازگشت به فهرست", callback_data="admin_role_list")],
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
        short = f"{fa_number(campaign.discount_value)}٪" if type_value == "percent" else fa_grouped(campaign.discount_value)
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
    rows.append([InlineKeyboardButton(text="⬅️ برگشت به فهرست", callback_data="campaign_list")])
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
def empty_screen_keyboard(back_cb: str = "main_menu", back_label: str = "⬅️ بازگشت به پنل") -> InlineKeyboardMarkup:
    """صفحهٔ خالی نباید بی‌دکمه بماند: کاربر میانِ راه گیر می‌کند و باید خودش /start بزند."""
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=back_label, callback_data=back_cb)]])


def _page_count(total: int, page_size: int) -> int:
    return max(1, (total + page_size - 1) // page_size)


def gaps_list_keyboard(gaps, page: int, total: int, page_size: int) -> InlineKeyboardMarkup:
    rows = []
    for index, gap in enumerate(gaps, start=page * page_size + 1):
        rows.append(
            [
                InlineKeyboardButton(text=f"✍️ پاسخ بده ({fa_number(index)})", callback_data=f"gap_answer:{gap.id}"),
                InlineKeyboardButton(text=f"🙈 نادیده بگیر ({fa_number(index)})", callback_data=f"gap_dismiss:{gap.id}"),
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
    toggle_label = switch_short_label(item.is_active)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ ویرایشِ جواب", callback_data=f"learned_edit:{item.id}")],
            [InlineKeyboardButton(text=toggle_label, callback_data=f"learned_toggle:{item.id}")],
            [InlineKeyboardButton(text="🗑 حذف", callback_data=f"learned_delete:{item.id}")],
            [InlineKeyboardButton(text="⬅️ برگشت به فهرست", callback_data="learned_list:0")],
        ]
    )


def learned_delete_confirm_keyboard(item_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🗑 بله، حذف کن", callback_data=f"learned_delete_yes:{item_id}"),
                InlineKeyboardButton(text="⬅️ نه، برگرد", callback_data=f"learned_view:{item_id}"),
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
        [InlineKeyboardButton(text=f"{label} ({fa_number(counts.get(key, 0))})", callback_data=f"crm_seg:{key}:0")]
        for key, label in texts.CRM_SEGMENT_LABELS.items()
    ]
    # P56 · موردِ ۴۱: بخش‌ها «گروه» را نشان می‌دادند ولی «این مشتری کجاست؟» جواب نداشت.
    rows.append([InlineKeyboardButton(text=texts.CRM_SEARCH_BUTTON, callback_data="crm_search")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def crm_search_keyboard(customers, page: int, total_pages: int, page_size: int) -> InlineKeyboardMarkup:
    """نتیجهٔ جست‌وجو: همان دکمهٔ کارتِ مشتریِ بخش‌ها (`crm_card:`) + صفحه‌گردانیِ جدا.

    شماره‌ها از صفحهٔ قبل ادامه می‌یابند تا «۹.» در صفحهٔ دوم یعنی نهمین نتیجه، نه اولین.
    """
    from app.bots.main_bot import texts

    rows = [
        [
            InlineKeyboardButton(
                text=f"{fa_number(page * page_size + index)}. {texts.crm_customer_label(customer)}"[:60],
                callback_data=f"crm_card:{customer.id}",
            )
        ]
        for index, customer in enumerate(customers, start=1)
    ]
    nav = _pagination_row(page, total_pages, "crm_search_page")
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="🔍 جست‌وجویِ دیگر", callback_data="crm_search")])
    rows.append([InlineKeyboardButton(text="⬅️ بخش‌ها", callback_data="crm_home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def crm_segment_keyboard(segment_key: str, members, page: int, total_pages: int, page_size: int) -> InlineKeyboardMarkup:
    from app.bots.main_bot import texts

    rows = []
    for index, stat in enumerate(members, start=page * page_size + 1):
        label = f"{fa_number(index)}. {texts.crm_customer_name(stat)}"[:60]
        rows.append([InlineKeyboardButton(text=label, callback_data=f"crm_card:{stat.customer_id}")])
    nav = _pagination_row(page, total_pages, f"crm_seg:{segment_key}")
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="📣 پیام به این بخش", callback_data=f"crm_bcast:{segment_key}")])
    rows.append([InlineKeyboardButton(text="⬅️ بخش‌ها", callback_data="crm_home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def crm_card_keyboard(customer_id: int, segment_key: str, is_blocked: bool = False) -> InlineKeyboardMarkup:
    # P18 · B4: بلاک/رفعِ بلاک دو کالبکِ جدا دارند (نه یک تلگلِ کور) تا دابل‌تپ وضعیت را برنگرداند.
    block_row = (
        InlineKeyboardButton(text="✅ رفعِ بلاک", callback_data=f"crm_unblock:{customer_id}")
        if is_blocked
        else InlineKeyboardButton(text="🚫 بلاک", callback_data=f"crm_block:{customer_id}")
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✍️ یادداشت", callback_data=f"crm_note:{customer_id}"),
                InlineKeyboardButton(text="🏷 برچسب‌ها", callback_data=f"crm_tags:{customer_id}"),
            ],
            [
                InlineKeyboardButton(text="💬 دیدنِ گفتگو", callback_data=f"crm_conv:{customer_id}:0"),
                block_row,
            ],
            [InlineKeyboardButton(text="🧠 خلاصه‌یِ هوشمند", callback_data=f"crm_sum:{customer_id}")],
            [InlineKeyboardButton(text="⬅️ برگشت به فهرست", callback_data=f"crm_seg:{segment_key}:0")],
        ]
    )


def crm_conversation_keyboard(customer_id: int, page: int, total_pages: int) -> InlineKeyboardMarkup:
    """B4: صفحه‌بندیِ گفتگو با همان سبکِ `_pagination_row` بقیه‌یِ فهرست‌ها."""
    rows = []
    nav = _pagination_row(page, total_pages, f"crm_conv:{customer_id}")
    if nav:  # تک‌صفحه ⇒ `_pagination_row` خالی برمی‌گرداند و تلگرام ردیفِ خالی را قبول نمی‌کند
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="⬅️ برگشت به مشتری", callback_data=f"crm_card:{customer_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def crm_clear_keyboard(kind: str, customer_id: int) -> InlineKeyboardMarkup:
    """kind: 'note' یا 'tags'."""
    label = "🗑 پاک‌کردنِ یادداشت" if kind == "note" else "🗑 پاک‌کردنِ برچسب‌ها"
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=label, callback_data=f"crm_{kind}_clear:{customer_id}")]])


def crm_summary_confirm_keyboard(customer_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ بله، بساز", callback_data=f"crm_sum_go:{customer_id}"),
                InlineKeyboardButton(text="⬅️ برگشت", callback_data=f"crm_card:{customer_id}"),
            ]
        ]
    )


def crm_back_to_card_keyboard(customer_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ برگشت به مشتری", callback_data=f"crm_card:{customer_id}")]])


# =============================================================================
# فازِ ۴-د — دستیارِ مدیریتی
# =============================================================================
def assistant_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🔚 پایان")]], resize_keyboard=True)


# =============================================================================
# فازِ ۶-الف — تنظیماتِ رباتِ فروشگاه
# =============================================================================
def consult_contacts_keyboard(members, page: int, total_pages: int) -> InlineKeyboardMarkup:
    """C2: فهرستِ مخاطبانِ رباتِ مشاوره‌ای + صفحه‌بندی."""
    from app.bots.main_bot import texts

    rows = []
    for index, customer in enumerate(members, start=1):
        badge = " 🚫" if customer.is_blocked else ""
        rows.append([InlineKeyboardButton(text=f"{fa_number(index)}. {texts.crm_customer_label(customer)}{badge}", callback_data=f"cc_card:{customer.id}:0")])
    nav = _pagination_row(page, total_pages, "cc_list")
    if nav:
        rows.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def consult_contact_keyboard(customer_id: int, is_blocked: bool, page: int, total_pages: int) -> InlineKeyboardMarkup:
    """C2 + B4: گفتگویِ همان مخاطب + بلاک/رفعِ بلاک (دو کالبکِ جدا ⇒ دابل‌تپ بی‌اثر)."""
    from app.bots.main_bot import texts

    rows = []
    nav = _pagination_row(page, total_pages, f"cc_card:{customer_id}")
    if nav:
        rows.append(nav)
    rows.append(
        [
            InlineKeyboardButton(
                text="✅ رفعِ بلاک" if is_blocked else "🚫 بلاک",
                callback_data=f"cc_unblock:{customer_id}" if is_blocked else f"cc_block:{customer_id}",
            )
        ]
    )
    rows.append([InlineKeyboardButton(text=texts.CONSULT_CONTACT_BACK, callback_data="cc_list:0")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def shop_settings_keyboard(shop_bot) -> InlineKeyboardMarkup:
    from app.bots.main_bot import texts

    current = shop_bot.message_batch_seconds
    # پ۵۸ · موردِ ۲۴: اخطارِ موجودی بدونِ کاتالوگ معنا ندارد (مودِ مشاوره‌ای کالا ندارد).
    mode_value = shop_bot.tenant_mode.value if hasattr(shop_bot.tenant_mode, "value") else shop_bot.tenant_mode
    buttons = [
        InlineKeyboardButton(text=("✅ " if current == seconds else "") + label, callback_data=f"bs_batch:{seconds}")
        for seconds, label in texts.BATCH_PRESETS
    ]
    buttons += [
        InlineKeyboardButton(text="✍️ مقدارِ دلخواه (۲ تا ۶۰ ثانیه)", callback_data="bs_batch_custom"),
        InlineKeyboardButton(text="↩️ پیش‌فرضِ سیستم", callback_data="bs_batch_reset"),
        InlineKeyboardButton(text="📈 گزارشِ دوره‌ای", callback_data="rp_open"),
        InlineKeyboardButton(text="✏️ بیوگرافیِ ربات", callback_data="br_open"),
        InlineKeyboardButton(text="⏱ مهلت‌ها و حافظه", callback_data="sp_prefs_open"),
        InlineKeyboardButton(text="📞 پشتیبانیِ مشتری‌ها", callback_data="sp_open"),
    ]
    if mode_value != "consultation":
        buttons.insert(-1, InlineKeyboardButton(text=texts.stock_alert_button_label(shop_bot), callback_data="bs_stock"))
    # P22: چهار preset هم دونادونه شد (۲×۲)؛ قبلاً یکِ ردیفِ چهارتایی و هفت ردیفِ تک بود.
    return InlineKeyboardMarkup(inline_keyboard=grid(buttons, max_label=30))


def shop_prefs_menu_keyboard(shop_bot, admin_settings, prefs) -> InlineKeyboardMarkup:
    """A5: فهرستِ تنظیم‌هایِ per-shop با مقدارِ مؤثرِ فعلی رویِ برچسبِ هر دکمه."""
    from app.bots.main_bot import texts
    from app.services import shop_prefs_service

    rows = []
    for pref in prefs:
        label, unit, _help = texts.SHOP_PREF_LABELS[pref.key]
        effective = shop_prefs_service.resolve(pref, shop_bot, admin_settings)
        rows.append([InlineKeyboardButton(text=f"{label}: {effective} {unit}", callback_data=f"sp_pref:{pref.key}")])
    rows.append([InlineKeyboardButton(text=texts.SHOP_PREF_BACK_BUTTON, callback_data="sp_prefs_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def checkout_questions_keyboard() -> InlineKeyboardMarkup:
    """B9: از صفحه‌یِ «📝 سوال‌هایِ چک‌اوتِ سبد» به گام‌هایِ پیش‌فرض."""
    from app.bots.main_bot import texts

    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=texts.CHECKOUT_STEPS_BUTTON, callback_data="cs_open")]])


def checkout_steps_keyboard(steps) -> InlineKeyboardMarkup:
    """B9: برایِ هر گام دو دکمه — روشن/خاموش و ویرایشِ متنِ پرسش."""
    from app.bots.main_bot import texts
    from app.services import checkout_config_service

    rows = []
    for key in checkout_config_service.STEP_KEYS:
        enabled = steps[key].enabled
        # «✅ نامِ تحویل‌گیرنده» نه «⛔️ خاموش‌کردن · نامِ تحویل‌گیرنده»: دومی در ردیفِ دونفره
        # بریده می‌شد و صفحه‌یِ پر مصرفِ فروشگاه‌دار را بی‌نظم می‌کرد (P22 · لایهٔ برچسب‌ها).
        mark = texts.CHECKOUT_STEP_MARK_ON if enabled else texts.CHECKOUT_STEP_MARK_OFF
        name = texts.CHECKOUT_STEP_LABELS[key].split(" ", 1)[-1]
        rows.append(
            [
                InlineKeyboardButton(text=f"{mark} {name}", callback_data=f"cs_toggle:{key}"),
                InlineKeyboardButton(text=texts.CHECKOUT_STEP_QUESTION_BUTTON, callback_data=f"cs_ask:{key}"),
            ]
        )
    rows.append([InlineKeyboardButton(text=texts.CHECKOUT_STEPS_BACK_BUTTON, callback_data="cs_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def checkout_step_keyboard(key: str, enabled: bool) -> InlineKeyboardMarkup:
    from app.bots.main_bot import texts

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=(texts.CHECKOUT_STEP_ON if enabled else texts.CHECKOUT_STEP_OFF), callback_data=f"cs_toggle:{key}"
                )
            ],
            [InlineKeyboardButton(text=texts.CHECKOUT_STEPS_BACK_BUTTON, callback_data="cs_back")],
        ]
    )


def shop_pref_edit_keyboard(shop_bot, pref) -> InlineKeyboardMarkup:
    """A5: پیش‌فرض‌هایِ از-پیش‌تعیین‌شده + ورودیِ عددی + بازگشت به پیش‌فرضِ سراسری (فقط اگر تنظیم شده باشد)."""
    from app.bots.main_bot import texts

    _label, unit, _help = texts.SHOP_PREF_LABELS[pref.key]
    stored = getattr(shop_bot, pref.key, None)
    rows = [
        [
            InlineKeyboardButton(
                text=("✅ " if stored == value else "") + f"{value} {unit}",
                callback_data=f"sp_pref_set:{pref.key}:{value}",
            )
            for value in pref.presets
        ],
        [InlineKeyboardButton(text=texts.SHOP_PREF_CUSTOM_BUTTON, callback_data=f"sp_pref_custom:{pref.key}")],
    ]
    if stored is not None:
        rows.append([InlineKeyboardButton(text=texts.SHOP_PREF_RESET_BUTTON, callback_data=f"sp_pref_reset:{pref.key}")])
    rows.append([InlineKeyboardButton(text=texts.SHOP_PREF_BACK_BUTTON, callback_data="sp_pref_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def shop_branding_keyboard(shop_bot) -> InlineKeyboardMarkup:
    """A2: متنِ خودِ فروشگاه‌دار برایِ بیوگرافی + بازگشت."""
    from app.bots.main_bot import texts

    rows = [
        [InlineKeyboardButton(text="✏️ متنِ خودت", callback_data="br_edit")],
        [InlineKeyboardButton(text=texts.BRANDING_CHECK_NOW_BUTTON, callback_data="br_check")],
        [InlineKeyboardButton(text=texts.SHOP_PREF_BACK_BUTTON, callback_data="br_back")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def shop_bot_token_choice_keyboard(bale_visible: bool = False) -> InlineKeyboardMarkup:
    """P42 · موردِ ۱: «🔑 ثبت/ویرایش توکن ربات» اول *انتخابِ سرویس* را می‌پرسد.
    گزینهٔ بله فقط وقتی در می‌آید که ادمین ویژگی را رونمایی کرده باشد."""
    rows = [[InlineKeyboardButton(text="🤖 رباتِ تلگرام", callback_data="tok_telegram")]]
    if bale_visible:
        rows.append([InlineKeyboardButton(text=texts.BALE_SHOP_BOT_BUTTON, callback_data="tok_bale")])
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت به پنل", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def bale_entry_keyboard() -> InlineKeyboardMarkup:
    """P42 · موردِ ۲۹: درست بعد ازِ «رباتِ تلگرام وصل شد» — همان‌جا سراغِ بله می‌رویم،
    نه با ارجاع به صفحهٔ پرداخت."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=texts.BALE_SHOP_BOT_BUTTON, callback_data="bale_open"),
        InlineKeyboardButton(text="⬅️ بازگشت به پنل", callback_data="main_menu"),
    ]])


def bale_shop_bot_keyboard(shop_bot) -> InlineKeyboardMarkup:
    """P19: صفحه‌یِ مدیریتِ اتصالِ بله‌یِ همین فروشگاه (روشن/خاموش، توکن، حذف).
    P22: فعل‌ها دونادونه؛ «بازگشت» تمام‌عرض و آخر می‌ماند تا همیشه پیدا باشد.
    P42 · موردِ ۲: سوییچِ این صفحه «هوشمندسازی» است، نه پرداخت — توکنی که در صفحهٔ
    پرداخت نوشته می‌شود با همین سوییچ خاموش می‌ماند و فقط برایِ بله‌پی مصرف می‌شود."""
    has_token = bool(shop_bot.bale_encrypted_token)
    actions = []
    if has_token:
        toggle = switch_label("هوشمندسازیِ بله", shop_bot.bale_bot_enabled)
        actions.append(InlineKeyboardButton(text=toggle, callback_data="bale_off" if shop_bot.bale_bot_enabled else "bale_on"))
    actions.append(InlineKeyboardButton(text="🔑 توکنِ تازه" if has_token else "🔑 توکنِ ربات بله", callback_data="bale_edit"))
    if has_token:
        actions.append(InlineKeyboardButton(text="🗑 حذفِ اتصالِ بله", callback_data="bale_clear"))
    rows = grid(actions, max_label=26)
    rows.append([InlineKeyboardButton(text=texts.SHOP_PREF_BACK_BUTTON, callback_data="bale_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def instagram_panel_keyboard(account) -> InlineKeyboardMarkup:
    """P49-الف: صفحهٔ مدیریتِ اینستاگرامِ همین فروشگاه (account = ردیفِ اتصال یا None).

    «اتصال» و «راهنما» همیشه هستند (فروشگاه‌دار باید بدونِ اتصال هم راهنما را بخواند)؛
    فعل‌هایِ نیازمندِ اتصال (پاسخ‌گویی/خوشآمد/تست/لغو) فقط وقتی وصل است در می‌آیند.
    P22: فعل‌ها دونادونه و «بازگشت» تمام‌عرضِ آخر می‌ماند (همان قاعدهٔ بقیهٔ صفحه‌ها).
    """
    from app.bots.main_bot import texts

    connected = account is not None
    actions = [InlineKeyboardButton(text="🔗 اتصالِ اکانت اینستاگرام", callback_data="ig_connect")]
    if connected:
        actions.append(
            InlineKeyboardButton(
                text="⏸ قطعِ پاسخ‌گویی" if account.auto_reply_dm else "▶️ پاسخ‌گویی",
                callback_data="ig_reply_off" if account.auto_reply_dm else "ig_reply_on",
            )
        )
        comments_on = bool(getattr(account, "auto_reply_comments", False))
        private_on = bool(getattr(account, "private_reply_enabled", False))
        actions.append(
            InlineKeyboardButton(
                text="💬 کامنت: روشن" if comments_on else "💬 کامنت: خاموش",
                callback_data="ig_comments_off" if comments_on else "ig_comments_on",
            )
        )
        actions.append(
            InlineKeyboardButton(
                text="🔒 پاسخِ خصوصی: روشن" if private_on else "🔒 پاسخِ خصوصی: خاموش",
                callback_data="ig_private_off" if private_on else "ig_private_on",
            )
        )
        actions.append(InlineKeyboardButton(text="👋 متنِ خوشآمد", callback_data="ig_greeting"))
        actions.append(InlineKeyboardButton(text=texts.INSTAGRAM_INSTRUCTIONS_BUTTON, callback_data="ig_instructions"))
        actions.append(InlineKeyboardButton(text="🧪 تستِ ارسال", callback_data="ig_test"))
        actions.append(InlineKeyboardButton(text="🚫 لغوِ اتصال", callback_data="ig_unbind"))
    actions.append(InlineKeyboardButton(text="📖 راهنمایِ فعال‌سازی", callback_data="ig_guide"))
    rows = grid(actions, max_label=26)
    rows.append([InlineKeyboardButton(text=texts.SHOP_PREF_BACK_BUTTON, callback_data="ig_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_stats_keyboard(has_range: bool = False) -> InlineKeyboardMarkup:
    """P51 · موردِ ۴۴: دکمه‌هایِ نمودار و بازه رویِ همان صفحهٔ «📊 آمار سراسری»."""
    rows = [
        [
            InlineKeyboardButton(text=texts.ADMIN_STATS_CHART_BUTTON, callback_data="admin_stats_chart"),
            InlineKeyboardButton(text=texts.ADMIN_STATS_SUMMARY_BUTTON, callback_data="admin_stats_summary"),
        ]
    ]
    range_row = [
        InlineKeyboardButton(text=texts.ADMIN_STATS_RANGE_BUTTON, callback_data="admin_stats_range_from"),
    ]
    if has_range:
        range_row.append(InlineKeyboardButton(text=texts.ADMIN_STATS_RANGE_CLEAR_BUTTON, callback_data="admin_stats_range_clear"))
    rows.append(range_row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def shop_report_keyboard(shop_bot) -> InlineKeyboardMarkup:
    """P18 · B5: روزِ هفته + ساعتِ گزارشِ دوره‌ای، به وقتِ تهران."""
    from app.bots.main_bot import texts

    day_rows = [
        InlineKeyboardButton(
            text=("✅ " if index == int(shop_bot.weekly_report_weekday) else "") + name,
            callback_data=f"rp_day:{index}",
        )
        for index, name in enumerate(texts.REPORT_WEEKDAY_NAMES)
    ]
    hour_row = [
        InlineKeyboardButton(
            text=("✅ " if hour == int(shop_bot.weekly_report_hour) else "") + label, callback_data=f"rp_hour:{hour}"
        )
        for hour, label in texts.REPORT_HOUR_PRESETS
    ]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=switch_label("گزارشِ دوره‌ای", shop_bot.weekly_report_enabled), callback_data="rp_toggle")],
            hour_row,
            [InlineKeyboardButton(text="✍️ ساعتِ دلخواه (۰ تا ۲۳)", callback_data="rp_hour_custom")],
            day_rows[:4],
            day_rows[4:],
            [InlineKeyboardButton(text="⬅️ برگشت", callback_data="rp_back")],
        ]
    )


def shop_support_keyboard(shop_bot) -> InlineKeyboardMarkup:
    toggle = switch_label("پشتیبانیِ مستقیم", shop_bot.support_enabled)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=toggle, callback_data="sp_toggle")],
            [InlineKeyboardButton(text="✏️ یوزرنیم", callback_data="sp_edit:username"), InlineKeyboardButton(text="✏️ تلفن", callback_data="sp_edit:phone")],
            [InlineKeyboardButton(text="✏️ متن", callback_data="sp_edit:text")],
            [InlineKeyboardButton(text="⬅️ برگشت", callback_data="sp_back")],
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
    def tog(label: str, enabled: bool, code: str) -> InlineKeyboardButton:
        return InlineKeyboardButton(text=f"{'✅' if enabled else '⛔️'} {label}", callback_data=f"pays_tog:{code}")

    # P22: صفحه‌ای با ۱۱ فعل؛ قبلاً هفت ردیفِ تک داشت. دونادونه شد، با حفظِ همین ترتیب.
    buttons = [
        InlineKeyboardButton(text="💳 تنظیمِ کارت (شماره/نام/بانک)", callback_data="pays_card"),
        tog("کارت‌به‌کارت", row.card_enabled, "card"),
        tog("بله‌پی", row.bale_enabled, "bale"),
        tog("زرین‌پال", row.zarinpal_enabled, "zarinpal"),
        tog("پرداختِ دستی/هماهنگی", row.manual_enabled, "manual"),
        tog("تاییدِ خودکارِ آنلاین", row.auto_accept_online, "auto"),
        InlineKeyboardButton(text="🔵 بله‌پی: توکنِ ربات + درگاه", callback_data="pays_bale_token"),
        InlineKeyboardButton(text="⏱ مهلتِ کارت", callback_data="pays_dl:card"),
        InlineKeyboardButton(text="⏱ مهلتِ بله‌پی", callback_data="pays_dl:bale"),
        InlineKeyboardButton(text="⏱ مهلتِ زرین‌پال", callback_data="pays_dl:zarinpal"),
        InlineKeyboardButton(text="🕒 مهلتِ بررسیِ رسید", callback_data="pays_hold"),
        InlineKeyboardButton(text="🔑 مرچنتِ زرین‌پال", callback_data="pays_zp"),
    ]
    return InlineKeyboardMarkup(inline_keyboard=grid(buttons, max_label=30))


def payments_entry_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⚙️ روش‌هایِ پرداختِ مشتری", callback_data="pays_menu")]])



# =============================================================================
# P22 · مشکلِ ۸ — دستهٔ «کاربرانِ غیرفعال» و حذفِ حسابِ فروشگاه‌دار
# =============================================================================
def inactive_windows_keyboard(days: int, page: int, total_pages: int) -> InlineKeyboardMarkup:
    """پنجرهٔ بازه (۷/۳۰/۹۰ روز) + صفحه‌گردانی + بازگشت به پنل."""
    from app.services.owner_activity_service import INACTIVE_WINDOWS
    rows = [
        [
            InlineKeyboardButton(
                text=("✅ " if window == days else "") + f"🕓 {fa_number(window)} روز",
                callback_data=f"inact_win:{window}",
            )
            for window in INACTIVE_WINDOWS
        ]
    ]
    rows.append([InlineKeyboardButton(text=texts.INACTIVE_DELETED_LIST_BUTTON, callback_data="inact_deleted")])
    nav = _pagination_row(page, total_pages, "inact_page")
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت به پنل", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def inactive_list_keyboard(items, days: int, page: int, total_pages: int) -> InlineKeyboardMarkup:
    """هر حساب یکِ دکمه: «نام · ۳۴ روزِ پیش». ردیفِ بازه‌ها پایین می‌آید تا فهرست جا بگیرد."""
    from app.services.owner_activity_service import INACTIVE_WINDOWS
    rows = grid(
        [
            InlineKeyboardButton(text=f"{name} · {since}", callback_data=f"inact_view:{owner_id}")
            for owner_id, name, since in items
        ],
        per_row=2,
        max_label=26,
    )
    rows.append(
        [
            InlineKeyboardButton(
                text=("✅ " if window == days else "") + f"🕓 {fa_number(window)} روز",
                callback_data=f"inact_win:{window}",
            )
            for window in INACTIVE_WINDOWS
        ]
    )
    nav = _pagination_row(page, total_pages, "inact_page")
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت به پنل", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def inactive_detail_keyboard(owner_id: int, page: int, *, is_deleted: bool, is_super: bool) -> InlineKeyboardMarkup:
    rows = []
    if is_super:
        if is_deleted:
            rows.append(
                [
                    InlineKeyboardButton(text="♻️ بازگرداندنِ حساب", callback_data=f"inact_restore:{owner_id}"),
                    InlineKeyboardButton(text="🔥 حذفِ قطعیِ داده", callback_data=f"inact_purge:{owner_id}"),
                ]
            )
        else:
            rows.append([InlineKeyboardButton(text="🧊 غیرفعال‌کردنِ حساب", callback_data=f"inact_deactivate:{owner_id}")])
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت به فهرست", callback_data=f"inact_back:{page}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def inactive_deactivate_confirm_keyboard(owner_id: int) -> InlineKeyboardMarkup:
    return yes_no_keyboard(f"inact_deactivate_yes:{owner_id}", f"inact_view:{owner_id}")


def inactive_restore_confirm_keyboard(owner_id: int) -> InlineKeyboardMarkup:
    return yes_no_keyboard(f"inact_restore_yes:{owner_id}", f"inact_view:{owner_id}")
