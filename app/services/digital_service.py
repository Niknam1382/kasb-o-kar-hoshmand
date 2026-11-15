"""محصولِ دیجیتال (فازِ ۱ · P1-S3 / B2): استخرِ کد، اختصاصِ امن، تحویل و «دریافتِ دوباره».

اصول:
* کدها رمزنگاری‌شده ذخیره می‌شن (`encrypt_token`)؛ تکراری‌بودن با `code_hash` سنجیده می‌شه.
* اختصاصِ کد به سفارش فقط با `SELECT … FOR UPDATE SKIP LOCKED` و داخلِ همون تراکنشی که
  `digital_delivered_at` رو می‌نویسه ⇒ دوبار-تحویل ممکن نیست (حتی با دابل‌تپ/هم‌زمانی).
* ارسال به مشتری *بعد از commit* انجام می‌شه (فراخوان commit می‌کنه، بعد `send_delivery`).
* اختصاص هیچ‌وقت نصفه نیست: اگه کدِ کافی نباشه هیچ کدی عوض نمی‌شه (`insufficient`).
* در W1 «پرداخت‌شده» = تاییدِ فروشگاه‌دار (CONFIRMED به بعد)؛ در W2/W3 که `paid` اضافه می‌شه،
  همین `prepare_delivery` از مسیرِ پرداخت هم صدا زده می‌شه.
"""

from __future__ import annotations

import datetime
import hashlib
import logging
from dataclasses import dataclass, field

from aiogram import Bot
from aiogram.types import BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import DigitalCode, OrderConsultation, OrderStatus, Product
from app.services import order_state
from app.utils.encryption import decrypt_token, encrypt_token
from app.utils.text_limits import TELEGRAM_CAPTION_LIMIT, clip

logger = logging.getLogger(__name__)

KIND_PHYSICAL = "physical"
KIND_DIGITAL = "digital"
DELIVERY_MODES = ("file", "link", "text", "code_pool")
# پ۷۸ · موردِ ۲۵ (مالکِ محصول): ساختنِ محصولِ دیجیتالِ *تازه* متوقف شد. مدل، انبارِ کد و مسیرِ
# تحویل عمداً سالم مانده‌اند تا محصول‌ها و سفارش‌هایِ موجودِ مشتری‌ها نه گم شوند نه بی‌پاسخ بمانند؛
# فقط درِ ساختنِ تازه و دکمه‌اش بسته شده (برگشت = همین یکِ True).
NEW_DIGITAL_ALLOWED = False

MAX_CODE_LEN = 255
MAX_CODES_PER_BATCH = 5000
MAX_DIGITAL_FILE_BYTES = 20 * 1024 * 1024  # سقفِ getFileِ تلگرام
PRODUCT_AI_INSTRUCTIONS_PROMPT_LEN = 300  # مصرفِ توکن (H1)

# وضعیت‌هایی که «پرداخت/تاییدِ سفارش انجام شده» حساب می‌شن (W2 این‌ها رو به order_state.py وصل می‌کنه)
DELIVERABLE_STATUSES = tuple(OrderStatus(v) for v in order_state.DISPLAY_ORDER if v in order_state.DELIVERABLE)


# ---------------------------------------------------------------------------
# منطقِ خالص
# ---------------------------------------------------------------------------
def is_digital(product: Product | None) -> bool:
    return product is not None and product.kind == KIND_DIGITAL


def is_code_pool(product: Product | None) -> bool:
    return is_digital(product) and product.digital_delivery == "code_pool"


def code_hash(code: str) -> str:
    return hashlib.sha256(code.strip().encode("utf-8")).hexdigest()


def parse_codes(text: str | None) -> tuple[list[str], int]:
    """متنِ چندخطی (یک کد در هر خط) → (کدهایِ یکتا به ترتیبِ ورود، تعدادِ ردشده‌ها).
    خط‌هایِ خالی نادیده؛ کدِ بلندتر از MAX_CODE_LEN یا تکراریِ داخلِ همین ورودی رد می‌شه؛
    بیشتر از MAX_CODES_PER_BATCH کد در یک بار پذیرفته نمی‌شه (بقیه جزوِ ردشده‌ها)."""
    if not text:
        return [], 0
    seen: set[str] = set()
    codes: list[str] = []
    ignored = 0
    for raw in text.replace("\r", "\n").split("\n"):
        code = raw.strip().strip("\u200c\u200f\u200e\ufeff").strip()
        if not code:
            continue
        if len(code) > MAX_CODE_LEN or code in seen or len(codes) >= MAX_CODES_PER_BATCH:
            ignored += 1
            continue
        seen.add(code)
        codes.append(code)
    return codes, ignored


def validate_link(raw: str | None) -> str | None:
    """فقط http/https و بدونِ فاصله؛ وگرنه None."""
    value = (raw or "").strip()
    if not value or " " in value or "\n" in value or len(value) > 1000:
        return None
    lowered = value.lower()
    if not (lowered.startswith("https://") or lowered.startswith("http://")):
        return None
    if len(value) <= len("https://x"):
        return None
    return value


def truncate_for_prompt(text: str | None, max_len: int = PRODUCT_AI_INSTRUCTIONS_PROMPT_LEN) -> str | None:
    if not text:
        return None
    flat = " ".join(text.split())
    if not flat:
        return None
    return flat if len(flat) <= max_len else flat[: max_len - 1] + "…"


def can_download_again(product: Product, download_count: int) -> bool:
    if product.digital_max_downloads is None:
        return True
    return download_count < product.digital_max_downloads


def build_delivery_text(product: Product, codes: list[str], again: bool = False) -> str:
    """متنِ پیامِ تحویل (بدونِ parse_mode). برایِ حالتِ file، خودِ فایل جدا (با همین متن به‌عنوانِ caption) می‌ره.

    خروجی همیشه زیرِ سقفِ کپشنِ تلگرام (۱۰۲۴) برمی‌گردد: `digital_instructions` متنِ آزادِ
    فروشگاه‌دار است و بدونِ برش، پیامِ تحویلِ یک محصولِ *فایلی* برایِ همیشه BadRequest می‌داد —
    و چون تحویل پیش ازِ ارسال در DB ثبت شده بود، «دریافتِ دوباره» هم دقیقاً همان‌طور شکست
    می‌خورد و مشتری هرگز فایل را نمی‌گرفت.
    """
    head = "📥 دریافتِ دوباره" if again else "✅ سفارشِ شما آماده‌ست"
    lines = [f"{head}: {clip(product.name, 120)}"]
    mode = product.digital_delivery
    # راهنما حداکثر ۴۰۰ نویسه بریده می‌شود تا همیشه جایِ کافی برایِ خودِ کدها بماند
    # (کد، چیزی است که مشتری باید کامل ببیند؛ راهنما نه).
    instructions = clip(product.digital_instructions, 400)
    if mode == "link" and product.digital_link:
        lines.append(f"🔗 لینک: {product.digital_link}")
    elif mode == "text" and instructions:
        lines.append(instructions)
    elif mode == "code_pool" and codes:
        lines.append("🔑 " + ("کدِ شما:" if len(codes) == 1 else "کدهایِ شما:"))
        lines.extend(codes)
    if mode != "text" and instructions:
        lines.append(f"\nℹ️ راهنما:\n{instructions}")
    return clip("\n".join(lines), TELEGRAM_CAPTION_LIMIT)


def again_keyboard(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="📥 دریافتِ دوباره", callback_data=f"dl_again:{order_id}")]]
    )


# ---------------------------------------------------------------------------
# دیتابیس: کدها
# ---------------------------------------------------------------------------
async def count_available_codes(session: AsyncSession, product_id: int) -> int:
    result = await session.execute(
        select(func.count()).select_from(DigitalCode).where(DigitalCode.product_id == product_id, DigitalCode.status == "available")
    )
    return int(result.scalar_one())


async def add_codes(session: AsyncSession, product: Product, codes: list[str]) -> tuple[int, int]:
    """کدهایِ تازه رو (رمزنگاری‌شده) به استخرِ محصول اضافه می‌کنه؛ کدِ تکراریِ همون محصول نادیده.
    برمی‌گردونه: (تعدادِ افزوده‌شده، تعدادِ تکراری). موجودیِ محصول بعدِ تحویلِ سفارش‌هایِ منتظر
    توسطِ `sync_pool_stock` درست می‌شه (فراخوان)."""
    if not is_code_pool(product) or not codes:
        return 0, 0
    hashes = {code_hash(code): code for code in codes}
    existing = await session.execute(
        select(DigitalCode.code_hash).where(DigitalCode.product_id == product.id, DigitalCode.code_hash.in_(list(hashes.keys())))
    )
    existing_hashes = set(existing.scalars().all())
    added = 0
    for h, code in hashes.items():
        if h in existing_hashes:
            continue
        session.add(DigitalCode(product_id=product.id, code=encrypt_token(code), code_hash=h, status="available"))
        added += 1
    await session.flush()
    return added, len(hashes) - added


async def sync_pool_stock(session: AsyncSession, product: Product) -> int:
    """برایِ code_pool: موجودیِ قابل‌فروش = تعدادِ کدهایِ available (ناوردایِ پروژه؛
    confirm_order موقعِ تاییدِ سفارش به همون اندازه از stock_quantity کم کرده بود)."""
    count = await count_available_codes(session, product.id)
    product.stock_quantity = count
    await session.flush()
    return count


async def undelivered_orders_for_product(session: AsyncSession, product_id: int) -> list[OrderConsultation]:
    """سفارش‌هایِ تاییدشده‌یِ این محصول که هنوز تحویل نشدن (مثلاً کد تموم شده بود)، قدیمی‌ترین اول."""
    result = await session.execute(
        select(OrderConsultation)
        .where(
            OrderConsultation.product_id == product_id,
            OrderConsultation.status.in_(DELIVERABLE_STATUSES),
            OrderConsultation.digital_delivered_at.is_(None),
        )
        .order_by(OrderConsultation.id)
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# دیتابیس: تحویل
# ---------------------------------------------------------------------------
@dataclass
class PreparedDelivery:
    # ready | already | not_digital | not_ready | insufficient
    status: str
    product: Product | None = None
    codes: list[str] = field(default_factory=list)


async def _assign_codes(session: AsyncSession, order: OrderConsultation, product: Product) -> list[str] | None:
    qty = max(1, order.quantity or 1)
    result = await session.execute(
        select(DigitalCode)
        .where(DigitalCode.product_id == product.id, DigitalCode.status == "available")
        .order_by(DigitalCode.id)
        .limit(qty)
        .with_for_update(skip_locked=True)
    )
    rows = list(result.scalars().all())
    if len(rows) < qty:
        return None
    now = datetime.datetime.now(datetime.timezone.utc)
    for row in rows:
        row.status = "delivered"
        row.order_id = order.id
        row.delivered_at = now
    await session.flush()
    return [decrypt_token(row.code) for row in rows]


async def prepare_delivery(session: AsyncSession, order: OrderConsultation) -> PreparedDelivery:
    """بخشِ دیتابیسیِ تحویل (اتمی و ایدمپوتنت). بعدش فراخوان `await session.commit()` و سپس
    `send_delivery`. دوبار صدا زدنِ این تابع برایِ یک سفارش = فقط بارِ اول `ready` می‌ده."""
    if order.product_id is None:
        return PreparedDelivery("not_digital")
    locked = (
        await session.execute(
            select(OrderConsultation).where(OrderConsultation.id == order.id).with_for_update().execution_options(populate_existing=True)
        )
    ).scalar_one()
    product = await session.get(Product, locked.product_id)
    if not is_digital(product):
        return PreparedDelivery("not_digital", product)
    if locked.digital_delivered_at is not None:
        return PreparedDelivery("already", product)
    if locked.status not in DELIVERABLE_STATUSES:
        return PreparedDelivery("not_ready", product)

    codes: list[str] = []
    if product.digital_delivery == "code_pool":
        assigned = await _assign_codes(session, locked, product)
        if assigned is None:
            return PreparedDelivery("insufficient", product)
        codes = assigned
    locked.digital_delivered_at = datetime.datetime.now(datetime.timezone.utc)
    locked.digital_download_count = 1
    await session.flush()
    return PreparedDelivery("ready", product, codes)


@dataclass
class Redelivery:
    # ok | not_found | not_delivered | limit
    status: str
    product: Product | None = None
    codes: list[str] = field(default_factory=list)
    order_id: int | None = None
    download_count: int = 0


async def prepare_redelivery(session: AsyncSession, order_id: int, customer_id: int) -> Redelivery:
    """«📥 دریافتِ دوباره»: فقط برایِ سفارشِ خودِ مشتری، فقط بعد از تحویلِ اول و تا سقفِ
    `digital_max_downloads`. شمارنده زیرِ قفلِ سطری بالا می‌ره (دابل‌تپ = یک بار)."""
    result = await session.execute(
        select(OrderConsultation)
        .where(OrderConsultation.id == order_id, OrderConsultation.customer_id == customer_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    order = result.scalar_one_or_none()
    if order is None or order.product_id is None:
        return Redelivery("not_found")
    product = await session.get(Product, order.product_id)
    if not is_digital(product):
        return Redelivery("not_found")
    if order.digital_delivered_at is None:
        return Redelivery("not_delivered", product, order_id=order.id)
    if not can_download_again(product, order.digital_download_count):
        return Redelivery("limit", product, order_id=order.id)
    codes: list[str] = []
    if product.digital_delivery == "code_pool":
        rows = await session.execute(select(DigitalCode).where(DigitalCode.order_id == order.id).order_by(DigitalCode.id))
        codes = [decrypt_token(row.code) for row in rows.scalars().all()]
    order.digital_download_count += 1
    await session.flush()
    return Redelivery("ok", product, codes, order.id, order.digital_download_count)


# ---------------------------------------------------------------------------
# ارسال (بعد از commit)
# ---------------------------------------------------------------------------
async def send_delivery(
    shop_bot_instance: Bot | None,
    main_bot: Bot | None,
    chat_id: int,
    product: Product,
    codes: list[str],
    order_id: int,
    download_count: int,
    again: bool = False,
) -> tuple[bool, str | None]:
    """پیامِ تحویل رو با رباتِ فروشگاه می‌فرسته. برمی‌گردونه (موفق؟، file_idِ معتبر برایِ رباتِ فروشگاه
    اگه تازه ساخته شد). هیچ استثنایی به بیرون نشت نمی‌کنه (مشتری ممکنه رباتِ فروشگاه رو بلاک کرده باشه)."""
    if shop_bot_instance is None:
        return False, None
    text = build_delivery_text(product, codes, again=again)
    markup = again_keyboard(order_id) if can_download_again(product, download_count) and product.digital_max_downloads != 1 else None
    new_file_id: str | None = None
    try:
        if product.digital_delivery == "file":
            new_file_id = await _send_file(shop_bot_instance, main_bot, chat_id, product, text, markup)
        else:
            await shop_bot_instance.send_message(chat_id, text, reply_markup=markup)
        return True, new_file_id
    except Exception:  # noqa: BLE001 — فقط لاگ؛ تحویل در دیتابیس ثبت شده و مشتری با «دریافتِ دوباره» می‌گیره
        logger.exception("ارسالِ تحویلِ دیجیتالِ سفارشِ %s ناموفق بود.", order_id)
        return False, None


async def _send_file(shop_bot_instance: Bot, main_bot: Bot | None, chat_id: int, product: Product, caption: str, markup) -> str | None:
    """file_idها بینِ دو ربات قابلِ انتقال نیستن: اول file_idِ مخصوصِ رباتِ فروشگاه (اگه قبلاً ساخته شده)،
    وگرنه دانلود از رباتِ اصلی و آپلودِ مجدد؛ file_idِ تازه برایِ دفعاتِ بعد برمی‌گرده."""
    if product.digital_file_shop_file_id:
        try:
            await shop_bot_instance.send_document(chat_id, product.digital_file_shop_file_id, caption=caption, reply_markup=markup)
            return None
        except Exception:  # noqa: BLE001 — file_id کهنه/نامعتبر ⇒ آپلودِ مجدد
            logger.warning("file_idِ رباتِ فروشگاه برایِ محصولِ %s نامعتبر بود؛ آپلودِ مجدد.", product.id)
    if main_bot is None or not product.digital_file_id:
        raise RuntimeError("فایلِ محصولِ دیجیتال در دسترس نیست.")
    buffer = await main_bot.download(product.digital_file_id)
    data = buffer.read()
    message = await shop_bot_instance.send_document(
        chat_id, BufferedInputFile(data, filename=product.digital_file_name or "file"), caption=caption, reply_markup=markup
    )
    return message.document.file_id if getattr(message, "document", None) else None


async def deliver_order(
    session: AsyncSession,
    order: OrderConsultation,
    customer_telegram_id: int,
    shop_bot_instance: Bot | None,
    main_bot: Bot | None,
) -> str:
    """مسیرِ کاملِ تحویل برایِ یک سفارش: prepare → commit → send. برمی‌گردونه:
    `not_digital|already|not_ready|insufficient|delivered|send_failed`."""
    prepared = await prepare_delivery(session, order)
    if prepared.status != "ready":
        return prepared.status
    product = prepared.product
    await session.commit()  # اول ثبتِ تحویل، بعد ارسال (اگه ارسال شکست خورد، دوباره-تحویل ممکن نیست؛ «دریافتِ دوباره» هست)
    ok, new_file_id = await send_delivery(shop_bot_instance, main_bot, customer_telegram_id, product, prepared.codes, order.id, 1)
    if new_file_id:
        product.digital_file_shop_file_id = new_file_id
        await session.commit()
    return "delivered" if ok else "send_failed"


async def deliver_pending_for_product(
    session: AsyncSession,
    product: Product,
    bot_manager,
    shop_bot_id: int,
    main_bot: Bot | None,
) -> tuple[int, int]:
    """بعد از افزودنِ کد: سفارش‌هایِ تاییدشده‌یِ منتظر (قدیمی‌ترین اول) تحویل داده می‌شن.
    برمی‌گردونه (تعدادِ تحویل‌شده/پردازش‌شده، تعدادِ هنوزمنتظر). با اولین «insufficient» متوقف
    می‌شه (FIFO؛ سفارشِ بعدی جلو نمی‌افته).

    رباتِ هر تحویل از پلتفرمِ خودِ مشتری انتخاب می‌شود (بله/تلگرام) — فرستادنِ شناسه‌یِ مشتریِ
    بله‌ای از رباتِ تلگرام می‌تواند به آدمِ دیگری برسد."""
    from app.database.models import Customer  # import محلی: دایره‌ایِ احتمالی با modelها نداریم ولی سبک می‌مونه

    orders = await undelivered_orders_for_product(session, product.id)
    delivered = 0
    for index, order in enumerate(orders):
        customer = await session.get(Customer, order.customer_id)
        if customer is None:
            continue
        bot = bot_manager.customer_bot(shop_bot_id, customer.platform) if bot_manager is not None else None
        if bot is None:
            logger.info("تحویلِ سفارش %s رها شد: اتصالِ %s فعال نیست.", order.id, customer.platform)
            continue
        status = await deliver_order(session, order, customer.telegram_id, bot, main_bot)
        if status in ("delivered", "send_failed"):
            delivered += 1
        elif status == "insufficient":
            return delivered, len(orders) - index
    return delivered, 0
