"""سقف‌هایِ متنِ سرویسِ پیام‌رسان و برشِ امن.

تلگرام (و بله، که با همان طرح کار می‌کند) رویِ طولِ کپشن/متی سخت‌گیرند: بیشتر از سقف ⇒
`BadRequest` و پیام **نمی‌رود**. اکثرِ مسیرهایِ این پروژه شکستِ ارسال را فقط لاگ می‌کنند، پس
نتیجهٔ کاربردی‌اش این است که فروشگاه‌دار عکسِ رسید را نمی‌گیرد یا مشتری فایلِ خریداری‌شده‌اش را
هرگز نمی‌بیند. یک جایِ مشترک برایِ برش، همه را می‌پوشاند.
"""

from __future__ import annotations

import re

TELEGRAM_TEXT_LIMIT = 4096
TELEGRAM_CAPTION_LIMIT = 1024
TELEGRAM_ALERT_TEXT_LIMIT = 200  # متنِ toastِ کال‌بک (answer)
# P49-الف: دایرکتِ اینستاگرام کوتاه‌تر است؛ پاسخِ AI پیش ازِ ارسال به همین سقف می‌رسد تا
# متا پیام را رد نکند (همان دلیلِ TELEGRAM_TEXT_LIMIT در بالایِ همین فایل).
INSTAGRAM_DM_LIMIT = 1000


def clip(value: str | None, limit: int) -> str:
    """برشِ بی‌خطر با برچسبِ «…» وقتی واقعاً چیزی کوتاه شده (تا کاربر بفهمد ناقص است)."""
    text = (value or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


# هیچ پیامی در این پروژه با parse_mode فرستاده نمی‌شود ⇒ نشانه‌هایِ Markdown که مدلِ زبانی
# می‌نویسد (مثلِ «**قیمت**») عیناً در چتِ مشتری نمایش داده می‌شود. فقط نشانه حذف می‌شود، نه
# محتوا؛ زیرِ خطِ داخلِ شناسه (callback_data) و ستارهٔ وسطِ کلمه دست‌نخورده می‌مانند.
_MD_PAIR_RE = re.compile(r"(?<!\w)(\*{1,3}|_{2,3}|~{2,3}|`{1,3})(?=\S)(.+?)(?<=\S)\1(?!\w)", re.DOTALL)
_MD_OPEN_RE = re.compile(r"\*{2,}")
_MD_BULLET_RE = re.compile(r"^[ \t]*[*+-][ \t]+", re.MULTILINE)
_MD_HEADING_RE = re.compile(r"^[ \t]*#{1,6}[ \t]*", re.MULTILINE)


def strip_markdown(value: str | None) -> str:
    """نشانه‌هایِ Markdown را از متنِ خروجیِ مدل می‌زداید (محتوا دست‌نخورده)."""
    text = value or ""
    if not text:
        return ""
    text = _MD_BULLET_RE.sub("• ", text)
    text = _MD_HEADING_RE.sub("", text)
    for _ in range(3):
        cleaned = _MD_PAIR_RE.sub(lambda m: m.group(2), text)
        if cleaned == text:
            break
        text = cleaned
    text = _MD_OPEN_RE.sub("", text)
    return "\n".join(line.rstrip() for line in text.splitlines()).strip()
