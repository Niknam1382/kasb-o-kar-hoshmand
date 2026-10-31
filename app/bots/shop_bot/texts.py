from __future__ import annotations

from app.services import cart_edit_service
from app.utils.validators import format_toman

SHOP_WELCOME = "سلام! خوش اومدی 👋 هر سوالی درباره‌ی محصولات یا خدمات داری بپرس، یا از دکمه‌ی «🛍 محصولات» برای دیدنِ مستقیمِ فهرست استفاده کن."

# --- برچسبِ دکمه‌هایِ منوی مشتری: منبعِ حقیقتِ واحد؛ کیبورد، هندلرها و میدل‌ورِ escape همه از همین‌ها می‌خونن (C1)
BTN_PRODUCTS = "🛍 محصولات"
BTN_CART = "🛒 سبدِ خرید"
BTN_SERVICES = "🗂 خدمات و بسته‌ها"
BTN_SUPPORT = "📞 ارتباط با پشتیبانی"
BTN_MY_ORDERS = "📦 سفارش‌هایِ من"
CUSTOMER_MENU_BUTTONS = {BTN_PRODUCTS, BTN_CART, BTN_SERVICES, BTN_SUPPORT, BTN_MY_ORDERS}

SHOP_WELCOME_CONSULTATION = "سلام! خوش اومدی 👋 هر سوالی داری بپرس؛ برایِ دیدنِ خدمات و بسته‌ها از دکمه‌یِ «🗂 خدمات و بسته‌ها» استفاده کن."
MENU_REPLY = "منوی فروشگاه 👇"
STALE_BUTTON_REPLY = "این دکمه مالِ نسخه‌یِ قبلیِ منو بود. منویِ تازه رو برات فرستادم 👇"
SERVICES_EMPTY = "این کسب‌وکار فعلاً خدمات یا بسته‌ای ثبت نکرده. سوالت رو همین‌جا بپرس."
SUPPORT_UNAVAILABLE = "پشتیبانیِ مستقیم برایِ این فروشگاه فعال نیست. سوالت رو همین‌جا بپرس."


def services_list_text(products) -> str:
    lines = ["🗂 خدمات و بسته‌ها:\n"]
    for product in products:
        price = f" — {format_toman(product.price_toman)}" if getattr(product, "price_toman", None) else ""
        lines.append(f"• {product.name}{price}")
    lines.append("\nبرایِ جزئیاتِ هر مورد همین‌جا بپرس.")
    return "\n".join(lines)


def support_contact_text(shop_bot) -> str:
    """تماسِ فروشگاه (حالتِ direct): @یوزرنیم / تلفن / متنِ توضیح (ساعتِ پاسخ‌گویی و…)."""
    lines = ["📞 ارتباط با پشتیبانی"]
    if shop_bot.support_contact_username:
        lines.append(f"تلگرام: @{shop_bot.support_contact_username}")
    if shop_bot.support_contact_phone:
        lines.append(f"تلفن: {shop_bot.support_contact_phone}")
    if shop_bot.support_contact_text:
        lines.append(f"\n{shop_bot.support_contact_text}")
    return "\n".join(lines)


SHOP_UNAVAILABLE = "این فروشگاه فعلاً در دسترس نیست. لطفاً بعداً دوباره امتحان کن."
PLATFORM_MAINTENANCE_REPLY = "این سرویس فعلاً برای مدتِ کوتاهی در حالِ به‌روزرسانیه. لطفاً چند دقیقه‌ی دیگه دوباره امتحان کن 🙏"
MODERATION_BLOCKED_REPLY = "متاسفانه نمی‌تونم به این پیام پاسخ بدم. اگه سوالِ دیگه‌ای داری، خوشحال می‌شم کمک کنم."

RATE_LIMITED = "لطفاً کمی آروم‌تر پیام بده 🙏 چند لحظه صبر کن و دوباره امتحان کن."

AI_NOT_CONFIGURED = "این فروشگاه هنوز کامل راه‌اندازی نشده. لطفاً بعداً دوباره امتحان کن."

AI_ERROR_REPLY = "الان نتونستم جوابت رو بدم 🙏 لطفاً چند لحظه‌ی دیگه دوباره پیام بده."
# فازِ ۴: اگه AI فقط نشانه‌یِ «سوالِ بی‌جواب» رو فرستاده بود و بعدِ حذفِ نشانه متنی نمونده.
GAP_FALLBACK_REPLY = "این سوالت رو برای فروشگاه‌دار ثبت کردم تا جوابش رو بده 🙏 تا اون موقع اگه سوالِ دیگه‌ای داری بپرس."

NON_TEXT_MESSAGE = "فعلاً فقط پیام متنی رو می‌تونم بخونم 🙂 لطفاً سوالت رو بنویس."

RECEIPT_ANALYSIS_PROMPT = (
    "این عکس رو بررسی کن و بگو آیا شبیه یه رسید یا فیش پرداخت بانکی هست یا نه. "
    "اگه هست، مبلغ، تاریخ و ساعت (اگه مشخص بود)، و شماره‌ی پیگیری یا مرجع رو استخراج کن. "
    "خروجی رو در چند خط کوتاه و خوانا بنویس، نه JSON."
)

PHOTO_RECEIVED_ACK = "📸 عکست دریافت شد و برای بررسی فرستاده شد."

VOICE_TRANSCRIBE_ERROR = "متاسفانه نتونستم پیامِ صوتیت رو تشخیص بدم 🙏 می‌شه لطفاً به‌صورت نوشتاری هم بفرستیش؟"


def customer_photo_forward_caption(customer_name: str, caption_note: str, analysis_note: str) -> str:
    return f"📸 مشتری «{customer_name}» یه عکس فرستاد.{caption_note}{analysis_note}"


# =============================================================================
# تاییدِ سفارش توسطِ مشتری (بازطراحیِ سفارش‌گیری)
# =============================================================================
def order_confirmation_prompt(order) -> str:
    """
    قبل از این‌که یه سفارش/مشاوره‌ی تشخیص‌داده‌شده واقعاً ثبت بشه و به
    فروشگاه‌دار برسه، همین پیام (با دکمه‌ی تاییدِ order_customer_confirmation_keyboard)
    به خودِ مشتری نشون داده می‌شه — چون قبلاً این کارِ کاملاً پشتِ‌صحنه انجام
    می‌شد و مشتری هیچ‌وقت نمی‌دید چی ثبت شده.
    """
    order_type_value = order.type.value if hasattr(order.type, "value") else order.type
    title = "🛒 این چیزیه که برات به‌عنوانِ سفارش ثبت می‌کنم" if order_type_value == "order" else "💬 این چیزیه که برات به‌عنوانِ درخواستِ مشاوره ثبت می‌کنم"

    lines = [title, "", f"خلاصه: {order.summary}"]
    if order.quantity:
        lines.append(f"تعداد: {order.quantity}")
    if order.estimated_value_toman:
        lines.append(f"ارزش تخمینی: {format_toman(order.estimated_value_toman)}")
    if order.customer_phone:
        lines.append(f"📞 تلفن: {order.customer_phone}")
    if order.customer_address:
        lines.append(f"📍 آدرس: {order.customer_address}")
    lines.append("")
    lines.append("درسته؟ لطفاً تایید کن تا برای فروشگاه‌دار ارسال بشه.")
    return "\n".join(lines)


ORDER_CUSTOMER_CONFIRMED_ACK = "✅ ثبت شد! به‌زودی فروشگاه‌دار باهات هماهنگ می‌کنه."
ORDER_CUSTOMER_CANCELLED_ACK = "باشه، لغوش کردم 🙏 اگه خواستی دوباره سفارش بدی، کافیه دوباره بگی."
ORDER_CONFIRMATION_NO_LONGER_VALID = "این درخواست دیگه معتبر نیست (شاید قبلاً جواب داده شده یا منقضی شده)."


# =============================================================================
# پرداختِ آنلاینِ سفارش از طریقِ بله‌پی (فازِ ۳)
# =============================================================================
def online_payment_offer(amount_toman: int) -> str:
    return (
        f"می‌تونی هزینه‌ی این سفارش ({format_toman(amount_toman)}) رو همین الان آنلاین پرداخت کنی، "
        "یا صبر کنی فروشگاه‌دار خودش باهات هماهنگ کنه — کاملاً اختیاریه:"
    )


ONLINE_PAYMENT_CONFIRMED = "✅ پرداختت با موفقیت دریافت شد. فروشگاه‌دار مطلعه و به‌زودی سفارشت رو پردازش می‌کنه."


# =============================================================================
# سبدِ خریدِ واقعی (فازِ ۳) — مسیرِ جدا و اختیاری، کنارِ چتِ آزادِ AI که
# دست‌نخورده می‌مونه. برایِ چند-محصولی؛ چتِ AI همچنان تک‌محصولیه.
# =============================================================================
NO_PRODUCTS_AVAILABLE = "این فروشگاه فعلاً محصولی برایِ نمایش نداره."
PRODUCTS_BROWSE_TITLE = "🛍 محصولات — رویِ هرکدوم بزن تا به سبدت اضافه بشه:"
CART_EMPTY = "سبدِ خریدت الان خالیه."
ITEM_OUT_OF_STOCK = "متاسفانه این محصول الان موجودی نداره."
ITEM_ADDED_PARTIAL_STOCK = "فقط {added} تا از این محصول موجود بود — همون تعداد به سبدت اضافه شد."


def item_added_to_cart(product_name: str) -> str:
    return f"✅ «{product_name}» به سبدت اضافه شد."


def cart_summary(items_with_products) -> str:
    """items_with_products: لیستی از (CartItem, Product)."""
    if not items_with_products:
        return CART_EMPTY
    lines = ["🛒 سبدِ خریدت:\n"]
    total = 0
    for item, product in items_with_products:
        subtotal = product.price_toman * item.quantity
        total += subtotal
        lines.append(f"• {product.name} × {item.quantity} = {format_toman(subtotal)}")
    lines.append(f"\nجمعِ کل: {format_toman(total)}")
    return "\n".join(lines)


ASK_CHECKOUT_ANSWER_PREFIX = "برایِ تکمیلِ سفارش:\n"


def checkout_question_prompt(question: str, step: int, total_steps: int) -> str:
    prefix = f"({step}/{total_steps}) " if total_steps > 1 else ""
    return f"{ASK_CHECKOUT_ANSWER_PREFIX}{prefix}{question}"


def checkout_final_confirmation(items_with_products, answers: list[tuple[str, str]], offer=None) -> str:
    """offer: یه campaign_service.Offer (یا None). وقتی تخفیف هست، زیرِ «جمعِ کل»
    خطِ تخفیف و «مبلغِ نهایی» اضافه می‌شه؛ بدونِ تخفیف خروجی دقیقاً مثلِ قبله."""
    lines = [cart_summary(items_with_products)]
    if offer is not None:
        lines.append(discount_block(offer))
    lines.append("")
    for question, answer in answers:
        lines.append(f"❔ {question}\n✏️ {answer}")
    lines.append("\nثبت بشه؟")
    return "\n".join(lines)


def discount_block(offer) -> str:
    """دو خطِ «تخفیف» و «مبلغِ نهایی» برایِ پیش‌نمایش/تاییدیه. offer: campaign_service.Offer."""
    label = f"«{offer.campaign_name}»" + (f" (کدِ {offer.code})" if offer.code else "")
    return f"🎁 تخفیفِ {label}: {format_toman(offer.discount_toman)}\n💰 مبلغِ نهایی: {format_toman(offer.final_total_toman)}"


def checkout_completed_ack_with_discount(offer) -> str:
    return (
        f"{CHECKOUT_COMPLETED_ACK}\n"
        f"🎁 تخفیفِ «{offer.campaign_name}»: {format_toman(offer.discount_toman)} — "
        f"مبلغِ نهایی: {format_toman(offer.final_total_toman)}"
    )


# =============================================================================
# کمپین/کدِ تخفیف (فازِ ۳) — مشتری موقعِ چک‌اوتِ سبد کد وارد می‌کنه؛ تخفیفِ
# خودکار هم تویِ همون پیش‌نمایش اعمال می‌شه. منطقش توی campaign_service ـه.
# =============================================================================
CHECKOUT_ASK_DISCOUNT_CODE = (
    "🎟 کدِ تخفیفت رو بفرست.\n\n"
    "برایِ برداشتنِ کدی که قبلاً زدی بنویس «حذف»، و برایِ برگشت به پیش‌نمایش بنویس «برگشت»."
)
DISCOUNT_CODE_APPLIED = "✅ کدِ تخفیف اعمال شد."
DISCOUNT_CODE_REMOVED = "کدِ تخفیف برداشته شد."
DISCOUNT_CODE_NO_LONGER_VALID = "کدِ تخفیفی که زده بودی دیگه معتبر نیست و برداشته شد."
DISCOUNT_CODE_RETRY_HINT = "\n\nدوباره امتحان کن، یا «برگشت» رو بنویس."
DISCOUNT_CODE_TOO_MANY_ATTEMPTS = "چند بار پشتِ‌هم کدِ اشتباه زدی 🙏 چند دقیقه صبر کن و دوباره امتحان کن."
CHECKOUT_PRICE_CHANGED = (
    "مبلغِ سفارشت از لحظه‌ی نمایشِ پیش‌نمایش تغییر کرده (ممکنه کمپین تمام شده یا قیمتی عوض شده باشه)، "
    "برای همین هنوز ثبت نشد. مبلغِ جدید پایینه؛ اگه موافقی دوباره «ثبتِ نهایی» رو بزن:"
)

_DISCOUNT_PROBLEM_TEXTS = {
    "not_found": "این کدِ تخفیف معتبر نیست.",
    "inactive": "این کدِ تخفیف فعلاً فعال نیست.",
    "not_started": "این کدِ تخفیف هنوز شروع نشده.",
    "ended": "مدتِ این کدِ تخفیف تموم شده.",
    "total_limit": "ظرفیتِ این کدِ تخفیف تموم شده.",
    "customer_limit": "تو قبلاً از این کدِ تخفیف استفاده کردی.",
    "no_discount": "این کد برایِ سبدِ فعلیِ تو تخفیفی نداره.",
}


def discount_code_problem(reason: str, min_cart_toman: int | None = None) -> str:
    """reason: مقدارِ campaign_service.RejectReason (رشته)."""
    if reason == "min_cart" and min_cart_toman:
        return f"این کدِ تخفیف برایِ سبدهایِ حداقل {format_toman(min_cart_toman)} معتبره."
    return _DISCOUNT_PROBLEM_TEXTS.get(reason, _DISCOUNT_PROBLEM_TEXTS["not_found"])


def discount_code_outranked(offer) -> str:
    return f"کدِ تخفیفت معتبره، ولی کمپینِ «{offer.campaign_name}» تخفیفِ بیشتری می‌ده؛ همون اعمال شد."


CHECKOUT_CANCELLED = "باشه، سفارش ثبت نشد. سبدت دست‌نخورده موند، هروقت خواستی می‌تونی ادامه بدی."
CHECKOUT_COMPLETED_ACK = "✅ سفارشت با موفقیت ثبت شد! به‌زودی فروشگاه‌دار باهات هماهنگ می‌کنه."
CART_ITEM_NOT_FOUND = "این آیتم دیگه تو سبدت نیست (شاید قبلاً حذف شده)."


# =============================================================================
# ویرایشِ سبد با هوش مصنوعی (فازِ ۳، زیربخشِ ۴) — مشتری تویِ همون چتِ آزاد دستورِ
# سبد می‌ده («دوتا از برنج کم کن»). منطقِ تصمیم‌گیری توی cart_edit_service ـه؛
# اینجا فقط متن‌هایی هست که به مشتری نشون داده می‌شه.
# =============================================================================
CART_AI_HINT = "💡 می‌تونی همین‌جا بنویسی هم؛ بگو کدوم محصول اضافه یا کم بشه، یا کدوم رو حذف کنم."
CART_AI_CLARIFY_GENERIC = (
    "دقیق نفهمیدم کدوم محصول رو و چندتا ازش رو می‌خوای تغییر بدم 🙏 اسمِ محصول و تعداد رو بگو، "
    "یا از دکمه‌هایِ «🛒 سبدِ خرید» استفاده کن."
)
CART_AI_PARTLY_UNDERSTOOD = "⚠️ {count} مورد از درخواستت رو متوجه نشدم؛ اگه لازمه، دوباره و واضح‌تر بگو."
CART_AI_CLEAR_PROMPT = "مطمئنی می‌خوای کلِ سبدِ خریدت خالی بشه؟"
CART_AI_CLEARED = "🗑 سبدِ خریدت خالی شد."
CART_AI_KEPT = "باشه، سبدت دست‌نخورده موند 🙂"
CART_AI_CLEAR_STALE = "سبدت از اون موقع تغییر کرده؛ اگه هنوز می‌خوای خالی بشه، دوباره بگو."
CHECKOUT_CART_CHANGED = (
    "سبدت بعد از نمایشِ اون پیش‌نمایش تغییر کرده، برای همین سفارش ثبت نشد. "
    "لطفاً دوباره از «🛒 سبدِ خرید» نهایی‌کردن رو بزن تا همون چیزی که می‌بینی ثبت بشه."
)


def cart_ai_outcome_line(outcome) -> str:
    """outcome: یه cart_edit_service.OperationOutcome."""
    name = f"«{outcome.product_name}»"
    kind = outcome.outcome
    new = outcome.new_quantity
    applied = outcome.applied_quantity
    if kind == cart_edit_service.ADDED:
        return f"➕ {name}: {applied} عدد اضافه شد (الان {new} تا تو سبدته)"
    if kind == cart_edit_service.ADDED_PARTIAL:
        return f"➕ {name}: فقط {applied} عدد موجود بود و همون اضافه شد (الان {new} تا تو سبدته)"
    if kind == cart_edit_service.AT_STOCK_LIMIT:
        return f"⚠️ {name}: موجودیِ بیشتری نیست؛ همون {new} تا تو سبدت می‌مونه"
    if kind == cart_edit_service.OUT_OF_STOCK:
        return f"⚠️ {name}: الان موجودی نداره و به سبدت اضافه نشد"
    if kind == cart_edit_service.UNAVAILABLE:
        return f"⚠️ {name}: دیگه در دسترس نیست"
    if kind == cart_edit_service.DECREASED:
        return f"➖ {name}: {applied} عدد کم شد (الان {new} تا تو سبدته)"
    if kind == cart_edit_service.REMOVED:
        return f"🗑 {name} از سبدت حذف شد"
    if kind == cart_edit_service.SET:
        return f"✏️ {name}: تعدادش شد {new}"
    if kind == cart_edit_service.SET_CAPPED:
        return f"✏️ {name}: فقط تا {new} تا موجوده و همون‌قدر تنظیم شد"
    if kind == cart_edit_service.UNCHANGED:
        return f"{name}: از قبل {new} تا تو سبدت بود"
    if kind == cart_edit_service.NOT_IN_CART:
        return f"⚠️ {name} تو سبدت نیست"
    return f"{name}: انجام نشد"


def cart_ai_edit_reply(outcomes, rejected_count: int, items_with_products) -> str:
    """پاسخِ نهایی به مشتری: یک خط برایِ هر عملیات + خلاصه‌ی سبدِ به‌روز شده (تا مشتری
    دقیقاً ببینه چی عوض شده و اگه AI اشتباه فهمیده بود بتونه سریع اصلاح کنه)."""
    lines = [cart_ai_outcome_line(outcome) for outcome in outcomes]
    if rejected_count:
        lines.append(CART_AI_PARTLY_UNDERSTOOD.format(count=rejected_count))
    return "\n".join(lines) + "\n\n" + cart_summary(items_with_products)


# فازِ ۱ · P1-S3 (B2): «📥 دریافتِ دوباره»ِ محصولِ دیجیتال
DL_AGAIN_NOT_FOUND = "این سفارش پیدا نشد یا دیجیتال نیست."
DL_AGAIN_NOT_READY = "این سفارش هنوز تحویل داده نشده؛ بعد از تاییدِ سفارش برات فرستاده می‌شه."
DL_AGAIN_LIMIT = "به سقفِ دفعاتِ دریافتِ این محصول رسیدی. اگه مشکلی داری با فروشگاه هماهنگ کن."
DL_AGAIN_FAILED = "ارسال ناموفق بود؛ چند لحظه بعد دوباره امتحان کن."


# =============================================================================
# فازِ ۱ · W2 — «📦 سفارش‌هایِ من»، اعلان‌هایِ وضعیت، فاکتور (C4/C8/C9)
# =============================================================================
_CUSTOMER_STATUS_LABELS = {
    "awaiting_customer_confirmation": "🕓 منتظرِ تاییدِ شما",
    "pending": "⏳ در انتظارِ تاییدِ فروشگاه",
    "awaiting_payment": "💳 منتظرِ پرداخت",
    "receipt_submitted": "🧾 رسید در حالِ بررسی",
    "paid": "💰 پرداخت‌شده",
    "confirmed": "✅ تاییدشده",
    "processing": "📦 در حالِ آماده‌سازی",
    "shipped": "🚚 ارسال‌شده",
    "completed": "🏁 تکمیل‌شده",
    "refund_pending": "↩️ در انتظارِ استرداد",
    "refunded": "↩️ استردادشده",
    "cancelled": "🚫 لغوشده",
    "rejected": "❌ ردشده",
    "expired": "⌛️ منقضی‌شده",
}

MY_ORDERS_EMPTY = "هنوز سفارشی ثبت نکردی. از «🛍 محصولات» شروع کن 🙂"
MY_ORDERS_TITLE = "📦 سفارش‌هایِ من (تازه‌ترین اول):"
MY_ORDER_STALE = "این سفارش پیدا نشد یا دیگه در دسترس نیست. دوباره از «📦 سفارش‌هایِ من» وارد شو."
MY_ORDER_CANNOT_CANCEL = "این سفارش دیگه قابلِ لغو نیست (فقط قبل از پرداخت می‌شه لغو کرد)."
MY_ORDER_CANCELLED = "🚫 سفارش لغو شد و رزروِ کالا آزاد شد."
MY_ORDER_INVOICE_UNAVAILABLE = "برایِ این سفارش فاکتوری صادر نمی‌شه."
MY_ORDER_DIGITAL_AGAIN = "📥 دریافتِ دوباره"


def customer_status_label(status) -> str:
    key = status.value if hasattr(status, "value") else status
    return _CUSTOMER_STATUS_LABELS.get(key, key)


def order_code(rows) -> str:
    """کدِ نمایشیِ سفارش برایِ مشتری/فروشگاه‌دار (شناسه‌یِ سفارش؛ نه آیدیِ تلگرام)."""
    return "#" + "-".join(str(r.id) for r in rows[:3]) + ("…" if len(rows) > 3 else "")


def _group_names(rows, products: dict) -> str:
    names = []
    for r in rows:
        product = products.get(r.product_id) if r.product_id is not None else None
        label = product.name if product is not None else r.summary
        names.append(f"{label} × {r.quantity or 1}")
    return "، ".join(names)


def my_orders_list_text(groups, products: dict, totals: list[int], page: int, total_groups: int) -> str:
    from app.utils.validators import format_toman

    lines = [MY_ORDERS_TITLE, ""]
    for index, (rows, total) in enumerate(zip(groups, totals), start=page * 5 + 1):
        lines.append(f"{index}. {customer_status_label(rows[0].status)} — {_group_names(rows, products)} — {format_toman(total)}")
    if total_groups > len(groups):
        lines.append(f"\n(صفحه‌یِ {page + 1} از {(total_groups + 4) // 5})")
    return "\n".join(lines)


def my_order_card_text(rows, products: dict, total: int, timeline: list) -> str:
    from app.utils.jalali import format_jalali_datetime, to_tehran
    from app.utils.validators import format_toman

    first = rows[0]
    lines = [f"📦 سفارش {order_code(rows)}", f"وضعیت: {customer_status_label(first.status)}", ""]
    for r in rows:
        product = products.get(r.product_id) if r.product_id is not None else None
        label = product.name if product is not None else r.summary
        lines.append(f"• {label} × {r.quantity or 1} — {format_toman(r.estimated_value_toman or 0)}")
    shipping = max((r.shipping_fee_toman or 0) for r in rows)
    if shipping:
        lines.append(f"🚚 هزینه‌یِ ارسال: {format_toman(shipping)}")
    lines.append(f"💰 جمع: {format_toman(total)}")
    if first.tracking_code:
        carrier = f" ({first.carrier_name})" if first.carrier_name else ""
        lines.append(f"🔎 کدِ رهگیری{carrier}: {first.tracking_code}")
    if timeline:
        lines.append("\n🕒 خط‌زمان:")
        for ev in timeline:
            when = format_jalali_datetime(to_tehran(ev.created_at)) if ev.created_at else ""
            lines.append(f"• {when} — {customer_status_label(ev.to_status)}")
    return "\n".join(lines)


def order_status_customer_message(to_status, rows, *, tracking_code: str | None = None, carrier_name: str | None = None, reason: str | None = None) -> str:
    key = to_status.value if hasattr(to_status, "value") else to_status
    code = order_code(rows)
    if key == "processing":
        return f"📦 سفارشِ {code} در حالِ آماده‌سازیه."
    if key == "shipped":
        extra = f"\n🔎 کدِ رهگیری{f' ({carrier_name})' if carrier_name else ''}: {tracking_code}" if tracking_code else ""
        return f"🚚 سفارشِ {code} ارسال شد.{extra}"
    if key == "completed":
        return f"🏁 سفارشِ {code} تکمیل شد. ممنون از خریدت 🙏"
    if key == "rejected":
        why = f"\nدلیل: {reason}" if reason else ""
        return (
            f"❌ متأسفانه فروشگاه سفارشِ {code} رو نتونست بپذیره.{why}\n"
            "می‌تونی دوباره از «🛍 محصولات» سفارش بدی یا با فروشگاه هماهنگ کنی."
        )
    if key == "refund_pending":
        why = f"\nدلیل: {reason}" if reason else ""
        return f"↩️ برایِ سفارشِ {code} استرداد ثبت شد؛ فروشگاه برایِ بازگرداندنِ وجه با تو هماهنگ می‌کنه.{why}"
    if key == "refunded":
        return f"↩️ استردادِ سفارشِ {code} انجام شد."
    if key == "confirmed":
        return f"✅ سفارشِ {code} تایید شد."
    if key == "paid":
        return f"💰 پرداختِ سفارشِ {code} ثبت شد."
    return f"وضعیتِ سفارشِ {code}: {customer_status_label(key)}"


DIRECT_MESSAGE_PREFIX = "✉️ پیام از فروشگاه:\n\n"


# =============================================================================
# W3 — پرداخت (روش‌ها، کارت‌به‌کارت، رسید)
# =============================================================================
PAY_METHOD_LABELS = {
    "card": "💳 کارت‌به‌کارت",
    "bale": "🔵 بله‌پی",
    "zarinpal": "🟡 زرین‌پال",
    "manual": "🤝 پرداختِ دستی/هماهنگی با فروشگاه",
}
PAY_STALE = "این سفارش دیگه منتظرِ پرداخت نیست (شاید پرداخت شده، لغو یا منقضی شده). از «📦 سفارش‌هایِ من» وضعیتش رو ببین."
PAY_METHOD_UNAVAILABLE = "این روشِ پرداخت الان در دسترس نیست؛ روشِ دیگه‌ای رو انتخاب کن."
PAY_MANUAL_CHOSEN = "🤝 سفارشت برایِ فروشگاه ارسال شد؛ فروشگاه برایِ پرداخت و هماهنگی با تو در تماسه."
PAY_ASK_RECEIPT = (
    "📎 رسیدِ واریز رو بفرست: عکسِ رسید، یا فایلِ تصویری، یا «شماره‌پیگیری» (حداقل ۶ رقم)، یا متنِ رسید (کپی‌شده از اپِ بانک یا پیامک).\n"
    "برایِ انصراف /cancel"
)
PAY_RECEIPT_INVALID = "این پیام رسید نیست. عکسِ رسید، فایلِ تصویری، شماره‌پیگیری (حداقل ۶ رقم) یا متنِ رسید (شاملِ مبلغ/تاریخ/شماره‌پیگیری، حداقل ۸ حرف) بفرست."
PAY_RECEIPT_TOO_BIG = "فایل خیلی بزرگه (حداکثر ۵ مگابایت). عکسِ کم‌حجم‌تری بفرست."
PAY_RECEIPT_DOWNLOAD_FAILED = "دریافتِ فایل ناموفق بود؛ دوباره بفرست."
PAY_RECEIPT_RECEIVED = "✅ رسیدت برایِ فروشگاه ارسال شد. بعد از بررسی خبرت می‌کنیم. می‌تونی وضعیت رو از «📦 سفارش‌هایِ من» ببینی."
PAY_TOO_MANY_ATTEMPTS = "سقفِ دفعاتِ ارسالِ رسید برایِ این سفارش پر شده. با فروشگاه هماهنگ کن."
PAY_CANCELLED_FLOW = "انصراف داده شد."
PAY_CLAIM_GUIDE = (
    "برایِ ثبتِ پرداختت رسید لازمه 🙏\n"
    "دکمه‌یِ «📎 ارسالِ رسید» رو بزن و عکسِ رسید، شماره‌پیگیری یا متنِ رسید رو بفرست."
)


def pay_choose_method_text(total_toman: int) -> str:
    from app.utils.validators import format_toman

    return f"💳 مبلغِ قابلِ پرداخت: {format_toman(total_toman)}\nروشِ پرداخت رو انتخاب کن:"


def card_payment_instructions(card_number: str, holder: str | None, bank: str | None, total_toman: int, code: str, expires_text: str) -> str:
    from app.services.payment_settings_service import format_card
    from app.utils.validators import format_toman

    lines = [
        "💳 کارت‌به‌کارت",
        f"مبلغ: {format_toman(total_toman)}  (دقیقاً همین مبلغ)",
        "",
        f"شماره‌کارت:\n{format_card(card_number)}",
    ]
    if holder:
        lines.append(f"به‌نامِ: {holder}")
    if bank:
        lines.append(f"بانک: {bank}")
    lines += ["", f"شماره‌یِ سفارش: {code}", f"⏳ مهلتِ پرداخت تا: {expires_text}", "", "بعد از واریز، «📎 ارسالِ رسید» رو بزن."]
    return "\n".join(lines)


def payment_approved_message(code: str) -> str:
    return f"✅ پرداختِ سفارشِ {code} تایید شد. ممنون! فاکتورِ سفارش براتون ارسال می‌شه."


def payment_rejected_message(code: str, reason: str, can_retry: bool) -> str:
    base = f"❌ رسیدِ سفارشِ {code} تایید نشد.\nدلیل: {reason}"
    if can_retry:
        return base + "\nمی‌تونی رسیدِ جدید بفرستی یا سفارش رو لغو کنی."
    return base + "\nسقفِ دفعاتِ ارسالِ رسید پر شده؛ سفارش بسته شد. با فروشگاه هماهنگ کن."


def payment_expired_message(code: str) -> str:
    return f"⌛️ مهلتِ پرداختِ سفارشِ {code} تموم شد و رزرو آزاد شد. اگه هنوز می‌خوای، دوباره سفارش بده."


def online_pay_offer(method: str, total_toman: int, expires_text: str) -> str:
    from app.utils.validators import format_toman

    extra = "\nبرایِ پرداختِ بله‌پی باید حسابِ «بله» داشته باشی؛ لینک داخلِ بله باز می‌شه." if method == "bale" else ""
    return (
        f"💳 پرداختِ آنلاین ({PAY_METHOD_LABELS.get(method, method)})\n"
        f"مبلغ: {format_toman(total_toman)}\n"
        f"⏳ مهلتِ پرداخت تا: {expires_text}{extra}\n\n"
        "بعد از پرداخت، خودکار خبرت می‌کنیم؛ چیزی لازم نیست بفرستی."
    )


PAY_ONLINE_LINK_FAILED = "ساختِ لینکِ پرداخت الان ممکن نشد؛ چند لحظه بعد دوباره امتحان کن یا روشِ دیگه‌ای انتخاب کن."

