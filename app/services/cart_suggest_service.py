"""پیشنهادِ دکمه‌یِ «➕ افزودن به سبد» از روی جوابِ AI (C2) — **خالص، رایگان و بی‌خطا**.

شناسه‌یِ محصول هرگز از متنِ AI خوانده نمی‌شود (توهم/تزریق)؛ فقط نامِ محصولاتِ *فعالِ همین فروشگاه*
در متنِ جواب پیدا می‌شود (با نرمال‌سازیِ ی/ک، ارقام، ZWNJ و فاصله) و دکمه با شناسه‌یِ واقعیِ همان محصول ساخته می‌شود.
"""

from __future__ import annotations

import re

MAX_SUGGESTIONS = 3

_DIGIT_MAP = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_MARKS_RE = re.compile("[\u064B-\u0652\u0640]")
_SPACE_RE = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    s = (text or "").translate(_DIGIT_MAP)
    s = s.replace("ي", "ی").replace("ى", "ی").replace("ك", "ک")
    s = s.replace("\u200c", " ").replace("\u200d", "")
    s = _MARKS_RE.sub("", s)
    return _SPACE_RE.sub(" ", s).strip().lower()


def _in_stock(product) -> bool:
    stock = getattr(product, "stock_quantity", None)
    if stock is None:
        return True
    return stock - (getattr(product, "reserved_quantity", 0) or 0) > 0


def suggest_cart_products(reply_text: str, products: list, limit: int = MAX_SUGGESTIONS) -> list:
    """حداکثر `limit` محصولِ فعال و موجود که نامشان در جواب آمده؛ به ترتیبِ اولین ظهور."""
    reply_norm = normalize_text(reply_text)
    if not reply_norm:
        return []
    found = []
    for product in products:
        if not getattr(product, "is_active", True) or not _in_stock(product):
            continue
        name = normalize_text(getattr(product, "name", ""))
        if len(name) < 2:
            continue
        pos = reply_norm.find(name)
        if pos >= 0:
            found.append((pos, -len(name), product.id, product))
    found.sort(key=lambda t: t[:3])
    return [t[3] for t in found[:limit]]
