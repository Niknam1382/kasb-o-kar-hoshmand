from __future__ import annotations

import json
import logging
import re

from app.database.models import OrderType, Product
from app.services.ai_service import AiServiceError, BaseAiService

logger = logging.getLogger(__name__)

_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)

_CLASSIFIER_SYSTEM_PROMPT_TEMPLATE = (
    "تو یک تحلیل‌گر مکالمه‌ی فروش هستی. مکالمه‌ی زیر بین یک دستیار فروش و یک "
    "مشتری رو بررسی کن و مشخص کن آیا در همین آخرین رد بدل‌ِ پیام، یک سفارش یا "
    "مشاوره‌ی کامل *تازه* نهایی شده یا نه (نه چیزی که قبلاً در همین مکالمه "
    "نهایی شده بود و الان فقط دوباره ذکر می‌شه).\n\n"
    "{products_block}"
    "فقط و فقط یک JSON با این ساختار دقیق برگردون، بدون هیچ متن یا توضیح اضافه "
    "و بدون Markdown:\n"
    '{{"completed": true یا false, "type": "order" یا "consultation", '
    '"summary": "خلاصه‌ی کوتاه فارسیِ سفارش/مشاوره شامل نام محصول/موضوع", '
    '"estimated_value_toman": عدد یا null, '
    '"product_id": عددِ شناسه‌ی محصول از لیستِ بالا اگر منطبق بود، وگرنه null، '
    '"quantity": عدد یا null, '
    '"customer_phone": "شماره تلفن مشتری اگر در مکالمه ذکر شده، وگرنه null", '
    '"customer_address": "آدرس مشتری اگر در مکالمه ذکر شده، وگرنه null"}}\n\n'
    'اگر چیز تازه‌ای نهایی نشده، فقط {{"completed": false}} برگردون.'
)

_CONSULTATION_CLASSIFIER_SYSTEM_PROMPT_TEMPLATE = (
    "تو یک تحلیل‌گر مکالمه‌ای هستی. مکالمه‌ی زیر بین یک دستیارِ مشاوره و یک مراجعه‌کننده رو بررسی کن و مشخص کن "
    "آیا در همین آخرین رد‌وبدلِ پیام، یک درخواستِ مشاوره/وقتِ ملاقات *تازه* نهایی شده یا نه (نه چیزی که قبلاً در "
    "همین مکالمه نهایی شده بود و الان فقط دوباره ذکر می‌شه). این کسب‌وکار محصولی نمی‌فروشه؛ فقط مشاوره/خدمت می‌ده.\n\n"
    "{products_block}"
    "فقط و فقط یک JSON با این ساختار دقیق برگردون، بدون هیچ متن یا توضیح اضافه و بدون Markdown:\n"
    '{{"completed": true یا false, "type": "consultation", '
    '"summary": "خلاصه‌ی کوتاهِ فارسیِ درخواستِ مشاوره شامل موضوع", '
    '"estimated_value_toman": null, '
    '"product_id": عددِ شناسه‌ی خدمت/بسته از لیستِ بالا اگر منطبق بود، وگرنه null، '
    '"quantity": null, '
    '"customer_phone": "شماره تلفن مراجعه‌کننده اگر در مکالمه ذکر شده، وگرنه null", '
    '"customer_address": "آدرس مراجعه‌کننده اگر در مکالمه ذکر شده، وگرنه null"}}\n\n'
    'اگر چیز تازه‌ای نهایی نشده، فقط {{"completed": false}} برگردون.'
)

_CLASSIFIER_USER_PROMPT = "بر اساس مکالمه‌ی بالا، تحلیلت رو دقیقاً طبق فرمت خواسته‌شده برگردون."


def _build_classifier_system_prompt(products: list[Product], is_consultation: bool = False) -> str:
    if products:
        label = "لیستِ خدمات/بسته‌های این کسب‌وکار (شناسه | نام):" if is_consultation else "لیستِ محصولاتِ فروشگاه (شناسه | نام):"
        lines = [label]
        lines.extend(f"{p.id} | {p.name}" for p in products)
        products_block = "\n".join(lines) + "\n\n"
    elif is_consultation:
        products_block = "این کسب‌وکار خدمت/بسته‌ی ثبت‌شده‌ای نداره؛ product_id همیشه null باشه.\n\n"
    else:
        products_block = "این فروشگاه فعلاً محصولی ثبت نکرده؛ product_id همیشه null باشه.\n\n"

    template = _CONSULTATION_CLASSIFIER_SYSTEM_PROMPT_TEMPLATE if is_consultation else _CLASSIFIER_SYSTEM_PROMPT_TEMPLATE
    return template.format(products_block=products_block)


def _extract_json(raw: str) -> dict | None:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.removeprefix("json").strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # بعضی مدل‌های ارزان‌تر (برخلاف Grok) همیشه JSON خالص برنمی‌گردونن — ممکنه
    # قبل/بعدش متن اضافه بذارن. به‌عنوان راه‌حل جایگزین، اولین بلوکِ {...} رو
    # با regex پیدا می‌کنیم.
    match = _JSON_OBJECT_RE.search(cleaned)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    logger.warning("خروجی تحلیل سفارش، JSON معتبر نبود: %s", raw[:200])
    return None


async def detect_order(
    ai: BaseAiService,
    history_with_latest_turn: list[dict[str, str]],
    products: list[Product] | None = None,
    is_consultation: bool = False,
) -> tuple[dict | None, int | None]:
    """
    خروجی: تاپلِ (نتیجه‌ی سفارش یا None، تعدادِ توکنِ مصرف‌شده یا None).

    توکن فقط وقتی None برمی‌گرده که خودِ فراخوانیِ هوش مصنوعی ناموفق بوده (چون
    اون‌وقت هیچ هزینه‌ای متوجهِ فروشگاه‌دار نشده). در غیرِ این صورت، حتی اگه
    سفارش/مشاوره‌ای هم تشخیص داده نشده باشه (رایج‌ترین حالت، چون اکثرِ ردوبدل‌های
    مکالمه به نتیجه‌ی نهایی ختم نمی‌شن)، توکنِ واقعیِ مصرف‌شده برگردونده می‌شه تا
    فراخوان بتونه بابتش از کیف‌پول کسر کنه.

    is_consultation: برای کسب‌وکارهای حالتِ مشاوره، طبقه‌بندی‌کننده اصلاً وارد
    بحثِ «سفارش در برابرِ مشاوره» نمی‌شه — همیشه consultation برمی‌گردونه، چون
    این کسب‌وکار اصلاً محصولی نمی‌فروشه.
    """
    products = products or []
    system_prompt = _build_classifier_system_prompt(products, is_consultation)

    try:
        ai_result = await ai.get_reply(system_prompt, history_with_latest_turn, _CLASSIFIER_USER_PROMPT)
    except AiServiceError:
        logger.exception("تحلیل سفارش/مشاوره (فراخوانی هوش مصنوعی) ناموفق بود.")
        return None, None

    tokens_used = ai_result.total_tokens

    data = _extract_json(ai_result.text)
    if not isinstance(data, dict) or not data.get("completed"):
        return None, tokens_used

    raw_type = data.get("type")
    order_type = OrderType.CONSULTATION if is_consultation else (OrderType.ORDER if raw_type == "order" else OrderType.CONSULTATION)

    summary = str(data.get("summary") or "").strip()[:2000]
    if not summary:
        return None, tokens_used

    estimated_value = data.get("estimated_value_toman")
    if not isinstance(estimated_value, (int, float)):
        estimated_value = None

    # مستقیم شناسه‌ی محصول رو از هوش مصنوعی می‌گیریم (نه اسمِ آزاد که نیاز به
    # تطبیقِ فازی داشت و باعثِ عدمِ کسرِ گاه‌به‌گاهِ موجودی می‌شد). با این حال،
    # چون هوش مصنوعی ممکنه یه عددِ اشتباه/ساختگی برگردونه، حتماً باید تاییدش
    # کنیم که این شناسه واقعاً توی لیستِ محصولاتِ همین فروشگاه هست.
    valid_product_ids = {p.id for p in products}
    raw_product_id = data.get("product_id")
    product_id: int | None = None
    if isinstance(raw_product_id, (int, float)) and int(raw_product_id) in valid_product_ids:
        product_id = int(raw_product_id)

    quantity = data.get("quantity")
    if not isinstance(quantity, (int, float)) or quantity <= 0:
        quantity = None
    else:
        quantity = int(quantity)

    extra_notes = []
    phone = data.get("customer_phone")
    if isinstance(phone, str) and phone.strip():
        extra_notes.append(f"📞 تلفن: {phone.strip()}")
    address = data.get("customer_address")
    if isinstance(address, str) and address.strip():
        extra_notes.append(f"📍 آدرس: {address.strip()}")
    if extra_notes:
        summary = summary + "\n" + "\n".join(extra_notes)
        summary = summary[:2000]

    return {
        "type": order_type,
        "summary": summary,
        "estimated_value_toman": int(estimated_value) if estimated_value is not None else None,
        "product_id": product_id,
        "quantity": quantity if product_id is not None else None,
    }, tokens_used
