"""سقف‌هایِ متنِ سرویسِ پیام‌رسان و برشِ امن.

تلگرام (و بله، که با همان طرح کار می‌کند) رویِ طولِ کپشن/متی سخت‌گیرند: بیشتر از سقف ⇒
`BadRequest` و پیام **نمی‌رود**. اکثرِ مسیرهایِ این پروژه شکستِ ارسال را فقط لاگ می‌کنند، پس
نتیجهٔ کاربردی‌اش این است که فروشگاه‌دار عکسِ رسید را نمی‌گیرد یا مشتری فایلِ خریداری‌شده‌اش را
هرگز نمی‌بیند. یک جایِ مشترک برایِ برش، همه را می‌پوشاند.
"""

from __future__ import annotations

TELEGRAM_TEXT_LIMIT = 4096
TELEGRAM_CAPTION_LIMIT = 1024
TELEGRAM_ALERT_TEXT_LIMIT = 200  # متنِ toastِ کال‌بک (answer)


def clip(value: str | None, limit: int) -> str:
    """برشِ بی‌خطر با برچسبِ «…» وقتی واقعاً چیزی کوتاه شده (تا کاربر بفهمد ناقص است)."""
    text = (value or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"
