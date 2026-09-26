from __future__ import annotations

import json
import logging
import re

from app.database.models import OrderType, Product
from app.services.ai_service import AiServiceError, BaseAiService

logger = logging.getLogger(__name__)

_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)

# بازطراحیِ سفارش‌گیری: کلاسیفایر به‌جایِ یه پرچمِ دوحالته‌ی completed true/false،
# حالا سه‌حالته‌ست («status»):
#   - none:      هیچ سفارش/مشاوره‌ی تازه‌ای در جریان نیست (رایج‌ترین حالت).
#   - unsure:    به‌نظر می‌رسه مشتری داره به سمتِ یه سفارش می‌ره ولی هنوز اطلاعاتِ
#                کافی/قطعیتِ کافی نیست؛ به‌جایِ حدس‌زدن، یه سوالِ روشن‌کننده برمی‌گرده.
#   - completed: سفارش/مشاوره با اطلاعاتِ کافی نهایی شده.
# «completed» دیگه به‌معنیِ ثبتِ قطعی نیست — قبل از ثبتِ نهایی، خودِ مشتری هم باید
# توی چت تاییدش کنه (این بخش توی customer.py/order_service.py پیاده‌سازی شده).
_CLASSIFIER_SYSTEM_PROMPT_TEMPLATE = (
    "تو یک تحلیل‌گر مکالمه‌ی فروش هستی. مکالمه‌ی زیر بین یک دستیار فروش و یک "
    "مشتری رو بررسی کن و بر اساسِ همین آخرین رد‌وبدلِ پیام (نه چیزی که قبلاً در "
    "همین مکالمه نهایی شده بود و الان فقط دوباره ذکر می‌شه)، وضعیت رو مشخص کن:\n\n"
    '- "none": هیچ سفارش/مشاوره‌ی تازه‌ای نه نهایی شده نه واقعاً در حالِ '
    "شکل‌گیریه — رایج‌ترین حالت.\n"
    '- "unsure": مشتری به‌نظر داره به‌سمتِ یه سفارش/مشاوره می‌ره، ولی هنوز مطمئن '
    "نیستی کامل شده یا نه، یا یه اطلاعاتِ ضروری (مثلاً دقیقاً کدوم محصول، چند "
    "تا، یا شماره‌تماس/آدرسی که برای تحویل لازمه) هنوز روشن نیست. این‌جا حدس "
    "نزن — یه سوالِ کوتاه و طبیعیِ فارسی بپرس که مستقیم خطاب به مشتریه. اگه "
    "توی همین مکالمه قبلاً دقیقاً همین ابهام رو پرسیدی و مشتری هنوز جوابِ "
    'روشنی نداده، دوباره "unsure" برنگردون (مگر چیزِ تازه‌ای اضافه شده باشه '
    'که ابهام رو واقعاً عوض کنه) — در این حالت "none" برگردون.\n'
    '- "completed": سفارش/مشاوره با اطلاعاتِ کافی همین الان نهایی شده (هنوز '
    "به‌معنیِ ثبتِ قطعی نیست؛ خودِ مشتری جداگانه برای تاییدِ نهایی پرسیده می‌شه).\n\n"
    "{products_block}"
    "فقط و فقط یک JSON برگردون، بدون هیچ متن یا توضیحِ اضافه و بدون Markdown.\n\n"
    'اگه status «none» بود، فقط: {{"status": "none"}}\n\n'
    'اگه status «unsure» بود: {{"status": "unsure", "clarifying_question": '
    '"یه سوالِ کوتاهِ فارسی که مستقیم به مشتری گفته می‌شه"}}\n\n'
    'اگه status «completed» بود: {{"status": "completed", "type": "order" یا '
    '"consultation", "summary": "خلاصه‌ی کوتاه فارسیِ سفارش/مشاوره شامل نام '
    'محصول/موضوع", "estimated_value_toman": عدد یا null, "product_id": '
    "عددِ شناسه‌ی محصول از لیستِ بالا اگر منطبق بود، وگرنه null، "
    '"quantity": عدد یا null, "customer_phone": "شماره تلفن مشتری اگر در '
    'مکالمه ذکر شده، وگرنه null", "customer_address": "آدرس مشتری اگر در '
    'مکالمه ذکر شده، وگرنه null"}}'
)

_CONSULTATION_CLASSIFIER_SYSTEM_PROMPT_TEMPLATE = (
    "تو یک تحلیل‌گر مکالمه‌ای هستی. مکالمه‌ی زیر بین یک دستیارِ مشاوره و یک مراجعه‌کننده رو بررسی کن و "
    "بر اساسِ همین آخرین رد‌وبدلِ پیام (نه چیزی که قبلاً در همین مکالمه نهایی شده بود و الان فقط دوباره "
    "ذکر می‌شه)، وضعیت رو مشخص کن. این کسب‌وکار محصولی نمی‌فروشه؛ فقط مشاوره/خدمت می‌ده.\n\n"
    '- "none": هیچ درخواستِ مشاوره/وقتِ ملاقاتِ تازه‌ای نه نهایی شده نه واقعاً در حالِ شکل‌گیریه.\n'
    '- "unsure": مراجعه‌کننده به‌نظر داره به‌سمتِ یه درخواستِ مشاوره می‌ره ولی هنوز مطمئن نیستی کامل '
    "شده یا نه، یا یه اطلاعاتِ ضروری (مثلاً موضوعِ دقیقِ مشاوره یا شماره‌تماسِ برگشت) هنوز روشن نیست. "
    "حدس نزن — یه سوالِ کوتاه و طبیعیِ فارسی بپرس. اگه قبلاً توی همین مکالمه دقیقاً همین ابهام رو "
    'پرسیدی و هنوز جوابِ روشنی نگرفتی، دوباره "unsure" برنگردون، مگر چیزِ تازه‌ای واقعاً ابهام رو عوض '
    'کرده باشه — در این حالت "none" برگردون.\n'
    '- "completed": درخواستِ مشاوره با اطلاعاتِ کافی همین الان نهایی شده (هنوز به‌معنیِ ثبتِ قطعی '
    "نیست؛ خودِ مراجعه‌کننده جداگانه برای تاییدِ نهایی پرسیده می‌شه).\n\n"
    "{products_block}"
    "فقط و فقط یک JSON برگردون، بدون هیچ متن یا توضیحِ اضافه و بدون Markdown.\n\n"
    'اگه status «none» بود، فقط: {{"status": "none"}}\n\n'
    'اگه status «unsure» بود: {{"status": "unsure", "clarifying_question": '
    '"یه سوالِ کوتاهِ فارسی که مستقیم به مراجعه‌کننده گفته می‌شه"}}\n\n'
    'اگه status «completed» بود: {{"status": "completed", "type": "consultation", '
    '"summary": "خلاصه‌ی کوتاهِ فارسیِ درخواستِ مشاوره شامل موضوع", '
    '"estimated_value_toman": null, "product_id": عددِ شناسه‌ی خدمت/بسته از لیستِ بالا اگر منطبق '
    'بود، وگرنه null، "quantity": null, "customer_phone": "شماره تلفن مراجعه‌کننده اگر در مکالمه '
    'ذکر شده، وگرنه null", "customer_address": "آدرس مراجعه‌کننده اگر در مکالمه ذکر شده، وگرنه '
    'null"}}'
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
    خروجی: تاپلِ (نتیجه یا None، تعدادِ توکنِ مصرف‌شده یا None).

    توکن فقط وقتی None برمی‌گرده که خودِ فراخوانیِ هوش مصنوعی ناموفق بوده (چون
    اون‌وقت هیچ هزینه‌ای متوجهِ فروشگاه‌دار نشده). در غیرِ این صورت، حتی اگه
    نتیجه «هیچی» باشه (رایج‌ترین حالت، چون اکثرِ ردوبدل‌های مکالمه به نتیجه‌ی
    نهایی ختم نمی‌شن)، توکنِ واقعیِ مصرف‌شده برگردونده می‌شه تا فراخوان بتونه
    بابتش از کیف‌پول کسر کنه.

    نتیجه (وقتی None نیست) یه دیکشنریِ با کلیدِ "status" ه:
      - {"status": "unsure", "clarifying_question": "..."} — باید این سوال
        مستقیماً به مشتری فرستاده بشه؛ هیچ سفارشی ساخته نمی‌شه.
      - {"status": "completed", "type": OrderType, "summary": ..., ...} —
        سفارش/مشاوره‌ی کاندید با اطلاعاتِ کامل (شاملِ customer_phone/
        customer_address به‌صورتِ فیلدِ جدا، نه چسبیده به summary).
    اگه status چیزِ دیگه‌ای بود (یا "none"، یا خروجیِ نامعتبر)، (None, tokens)
    برگردونده می‌شه — یعنی هیچ اقدامی لازم نیست.

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
    if not isinstance(data, dict):
        return None, tokens_used

    status = data.get("status")

    if status == "unsure":
        question = str(data.get("clarifying_question") or "").strip()[:1000]
        if not question:
            # اگه سوالی برنگردوند، چیزِ قابلِ‌اقدامی نداریم؛ عملاً همون «none» ه.
            return None, tokens_used
        return {"status": "unsure", "clarifying_question": question}, tokens_used

    if status != "completed":
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

    # فیلدهای ساختاریافته: برخلافِ قبل، اینجا دیگه به summary چسبونده نمی‌شن —
    # ستونِ جداگانه‌ی خودشون رو دارن (تا هم قابلِ‌کوئری باشن، هم توی پیامِ
    # تاییدِ مشتری/اطلاع‌رسانیِ فروشگاه‌دار جدا از خلاصه‌ی آزاد نشون داده بشن).
    phone = data.get("customer_phone")
    phone = phone.strip()[:32] if isinstance(phone, str) and phone.strip() else None
    address = data.get("customer_address")
    address = address.strip()[:1000] if isinstance(address, str) and address.strip() else None

    return {
        "status": "completed",
        "type": order_type,
        "summary": summary,
        "estimated_value_toman": int(estimated_value) if estimated_value is not None else None,
        "product_id": product_id,
        "quantity": quantity if product_id is not None else None,
        "customer_phone": phone,
        "customer_address": address,
    }, tokens_used
