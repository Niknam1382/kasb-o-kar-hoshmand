from __future__ import annotations

import time
from collections import defaultdict, deque

# محدودکننده‌ی نرخ در حافظه، بر اساس ترکیب (shop_bot_id, customer_telegram_id).
# چون این پروژه تک‌پردازه اجرا می‌شود کافی است؛ اگر روزی چندپردازه‌ای شد باید
# به یک استور مشترک مثل Redis منتقل شود.
_windows: dict[tuple[int, int], deque[float]] = defaultdict(deque)


class InMemoryRateLimiter:
    def check_and_record(self, shop_bot_id: int, customer_telegram_id: int, max_messages: int, window_seconds: int) -> bool:
        key = (shop_bot_id, customer_telegram_id)
        now = time.monotonic()
        window = _windows[key]
        while window and now - window[0] > window_seconds:
            window.popleft()
        if len(window) >= max_messages:
            return False
        window.append(now)
        return True


rate_limiter = InMemoryRateLimiter()
