from __future__ import annotations

from app.utils.validators import format_toman

SHOP_WELCOME = "سلام! خوش اومدی 👋 هر سوالی درباره‌ی محصولات یا خدمات داری بپرس."

SHOP_UNAVAILABLE = "این فروشگاه فعلاً در دسترس نیست. لطفاً بعداً دوباره امتحان کن."
PLATFORM_MAINTENANCE_REPLY = "این سرویس فعلاً برای مدتِ کوتاهی در حالِ به‌روزرسانیه. لطفاً چند دقیقه‌ی دیگه دوباره امتحان کن 🙏"
MODERATION_BLOCKED_REPLY = "متاسفانه نمی‌تونم به این پیام پاسخ بدم. اگه سوالِ دیگه‌ای داری، خوشحال می‌شم کمک کنم."

RATE_LIMITED = "لطفاً کمی آروم‌تر پیام بده 🙏 چند لحظه صبر کن و دوباره امتحان کن."

AI_NOT_CONFIGURED = "این فروشگاه هنوز کامل راه‌اندازی نشده. لطفاً بعداً دوباره امتحان کن."

AI_ERROR_REPLY = "الان نتونستم جوابت رو بدم 🙏 لطفاً چند لحظه‌ی دیگه دوباره پیام بده."

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
