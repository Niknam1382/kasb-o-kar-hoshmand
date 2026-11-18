from __future__ import annotations

import time
from collections import defaultdict, deque

# محدودکننده‌ی نرخ در حافظه، بر اساس ترکیب (shop_bot_id, customer_telegram_id).
# چون این پروژه تک‌پردازه اجرا می‌شود کافی است؛ اگر روزی چندپردازه‌ای شد باید
# به یک استور مشترک مثل Redis منتقل شود.
_windows: dict[tuple[int, int], deque[float]] = defaultdict(deque)

# پ۱۱۸ (یافتهٔ ۱۲): کلیدِ این جدول (فروشگاه، مشتری) است و در سرویسِ شلوغ بی‌سقف رشد می‌کرد —
# هر مشتریِ تازه یکِ deque. سقفِ زیر قدیمی‌ترین‌ها را بیرون می‌کند؛ پیامدِ امنیتی ندارد
# (بیرون‌رفتن یعنی «آن مشتری از نو در پنجرهٔ خودش حساب می‌شود») ولی رم را ثابت نگه می‌دارد.
MAX_TRACKED_KEYS = 50_000


def _prune(now: float, window_seconds: int) -> None:
    if len(_windows) <= MAX_TRACKED_KEYS:
        return
    for key in [k for k, window in _windows.items() if not window]:
        del _windows[key]
    while len(_windows) > MAX_TRACKED_KEYS:
        oldest = next(iter(_windows), None)
        if oldest is None:
            return
        del _windows[oldest]


class InMemoryRateLimiter:
    def check_and_record(self, shop_bot_id: int, customer_telegram_id: int, max_messages: int, window_seconds: int) -> bool:
        key = (shop_bot_id, customer_telegram_id)
        now = time.monotonic()
        window = _windows[key]
        while window and now - window[0] > window_seconds:
            window.popleft()
        _prune(now, window_seconds)
        if len(window) >= max_messages:
            return False
        window.append(now)
        return True


rate_limiter = InMemoryRateLimiter()
