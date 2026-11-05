"""عکسِ محصول برایِ مشتری (W5). عکس را فروشگاه‌دار در *رباتِ اصلی* آپلود می‌کنه؛ file_idِ تلگرام فقط برایِ همان ربات معتبره،
پس برایِ رباتِ فروشگاه باید دوباره آپلود بشه (مثلِ فایلِ دیجیتال). file_idِ معتبرِ رباتِ فروشگاه روی
`Product.photo_shop_file_id` کش می‌شه با قالبِ «<برچسبِ منبع>|<پلتفرم>|<file_id>»؛ اگه فروشگاه‌دار عکس رو عوض کنه
برچسب نمی‌خونه و کش خودکار باطل می‌شه (بدونِ دست‌زدن به مسیرِ ویرایش). هیچ هزینه/AI ای اینجا نیست.

پلتفرم از P36 در کلیدِ کش نشسته: یکِ فروشگاه می‌تواند هم‌زمان رباتِ تلگرام و رباتِ بله داشته باشد، و
`file_id`هایِ دو سرویسِ متفاوت به‌هیچ‌وجه به‌دردِ هم نمی‌خورند. بدونِ آن، هر درخواستِ عکس بینِ دو
اتصال یکِ آپلودِ دوباره می‌ساخت (کشِ تلگرام رویِ بله رد می‌شد و برعکس، و هر بار کش بازنویسی می‌شد).
ردیف‌هایِ قدیمیِ دونسخه‌ای («<tag>|<file_id>») همان «تلگرام» خوانده می‌شوند.
"""

from __future__ import annotations

import hashlib
import logging
import re

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import BufferedInputFile, InlineKeyboardMarkup

from app.database.models import Product
from app.services import platform_service

logger = logging.getLogger(__name__)

_PHOTO_WORD_RE = re.compile(r"(عکس|تصویر|فوتو|پیکچر|عکسش|عکساش|picture|photo|image)", re.IGNORECASE)
MAX_REQUEST_LENGTH = 120
MAX_CARDS_PER_REQUEST = 3
_NORMALIZE_TABLE = str.maketrans({"ي": "ی", "ك": "ک", "\u200c": " ", "ـ": ""})


def source_tag(photo_file_id: str) -> str:
    return hashlib.sha1(photo_file_id.encode()).hexdigest()[:8]


def cached_shop_file_id(product: Product, platform: str | None = None) -> str | None:
    """file_idِ کش‌شده اگه هنوز مالِ همین عکس **و همین پیام‌رسان** باشه؛ وگرنه None.

    `platform=None` یعنی «هر پلتفرمی» — فقط برایِ خوانشِ سازگار با کد/تستِ قدیمی؛ مسیرِ واقعی
    همیشه پلتفرمِ رباتِ خودش را پاس می‌دهد.
    """
    raw = product.photo_shop_file_id
    if not raw or not product.photo_file_id:
        return None
    parts = raw.split("|")
    if len(parts) == 2:
        tag, stored_platform, file_id = parts[0], platform_service.TELEGRAM, parts[1]
    elif len(parts) == 3:
        tag, stored_platform, file_id = parts
    else:
        return None
    if tag != source_tag(product.photo_file_id) or not file_id:
        return None
    if platform is not None and stored_platform != platform:
        return None
    return file_id


def _normalize(text: str) -> str:
    return " ".join((text or "").translate(_NORMALIZE_TABLE).lower().split())


def looks_like_photo_request(text: str | None) -> bool:
    """«عکسِ برنج رو بفرست / تصویر X / عکس دارید؟» — کوتاه و حاویِ واژه‌یِ عکس."""
    clean = (text or "").strip()
    return 0 < len(clean) <= MAX_REQUEST_LENGTH and bool(_PHOTO_WORD_RE.search(_normalize(clean)))


def match_products(text: str, products: list[Product]) -> list[Product]:
    """محصولاتِ *عکس‌دارِ* فعالی که اسمشون در متن آمده (نامِ کامل، یا همه‌یِ کلماتِ ≥۲حرفیِ نام). حداکثر MAX_CARDS_PER_REQUEST."""
    haystack = _normalize(text)
    found: list[Product] = []
    for product in products:
        if not product.photo_file_id or not product.is_active:
            continue
        name = _normalize(product.name)
        words = [w for w in name.split() if len(w) >= 2]
        if name and (name in haystack or (words and all(w in haystack for w in words))):
            found.append(product)
    return found[:MAX_CARDS_PER_REQUEST]


def with_photo(products: list[Product]) -> list[Product]:
    return [p for p in products if p.photo_file_id and p.is_active]


async def send_product_photo(
    shop_bot_instance: Bot,
    main_bot: Bot,
    product: Product,
    chat_id: int,
    *,
    caption: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> bool:
    """True اگه عکس رفت. کش → (در صورتِ خطا) آپلودِ دوباره از رباتِ اصلی. هر شکستی فقط False (فراخوان متنِ ساده می‌فرسته)."""
    if not product.photo_file_id:
        return False
    platform = platform_service.platform_of(shop_bot_instance)
    cached = cached_shop_file_id(product, platform)
    if cached:
        try:
            await shop_bot_instance.send_photo(chat_id, cached, caption=caption[:1024], reply_markup=reply_markup)
            return True
        except TelegramAPIError:
            logger.info("file_idِ کش‌شده‌یِ عکسِ محصول %s معتبر نبود؛ دوباره آپلود می‌شه.", product.id)
    try:
        buffer = await main_bot.download(product.photo_file_id)
        data = buffer.read() if buffer is not None else b""
    except TelegramAPIError:
        data = b""
    if not data:
        logger.warning("دریافتِ عکسِ محصول %s از رباتِ اصلی ناموفق بود.", product.id)
        return False
    try:
        sent = await shop_bot_instance.send_photo(
            chat_id, BufferedInputFile(data, filename="product.jpg"), caption=caption[:1024], reply_markup=reply_markup
        )
    except TelegramAPIError:
        logger.exception("ارسالِ عکسِ محصول %s به رباتِ فروشگاه ناموفق بود.", product.id)
        return False
    if sent is not None and getattr(sent, "photo", None):
        product.photo_shop_file_id = f"{source_tag(product.photo_file_id)}|{platform}|{sent.photo[-1].file_id}"[:255]
    return True
