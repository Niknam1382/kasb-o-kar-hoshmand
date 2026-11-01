"""سقفِ نرخِ in-process برایِ endpointهایِ عمومیِ HTTP (P20 · بلاکرِ B3).

`/webhook/main`، `/webhook/shop/{id}`، `/webhook/bale*` و `/payment/zarinpal/callback` همه از بیرون
قابلِ زددن‌اند. بدونِ سقف، یک IP می‌تواند: (الف) با تلاشِ رازِ وب‌هوک، CPU/دیتابیسِ سرویس را بخواباند
(هر ۴۰۳ الان به ادمین هشدار هم می‌فرستد!)، (۲) صفحهٔ بازگشتِ زرین‌پال را بمباران کند.

چرا در حافظه و نه Redis: همین‌که برایِ تک‌نسخه‌ای که پروژه امروز روی آن است کار می‌کند، و افزودنِ
Redis یعنی یکِ سرویسِ جدیدِ پولی/نگهداری (قاعدهٔ پروژه: زیرساختِ تازه اضافه نکن). اگر چند نسخه
شد، سقفِ هر نسخه جدا اعمال می‌شود ⇒ مجموعاً شل‌تر ولی همچنان مفید.

کلید = (IP, مسیرِ نرمال‌شده). پنجره sliding با deque، همان الگویِ `rate_limiter`ِ پیام‌هایِ مشتری.
"""

from __future__ import annotations

import time
from collections import deque

MAX_TRACKED_KEYS = 20_000
_windows: dict[tuple[str, str], deque[float]] = {}


def _prune_if_needed(now: float) -> None:
    if len(_windows) <= MAX_TRACKED_KEYS:
        return
    # اگر IPها عوض شوند (اسکنِ تصادفیِ carrierها) فهرست نباید بی‌حد رشد کند
    for key in [k for k, q in _windows.items() if not q or now - q[-1] > 120]:
        _windows.pop(key, None)


def allow(key: tuple[str, str], limit_per_minute: int, now: float | None = None) -> bool:
    """True ⇒ مجاز. False ⇒ سقفِ یک دقیقه رد شده (caller باید ۴۲۹ بدهد)."""
    if limit_per_minute <= 0:
        return True
    now = time.monotonic() if now is None else now
    window = _windows.get(key)
    if window is None:
        window = _windows[key] = deque()
    while window and now - window[0] > 60:
        window.popleft()
    if len(window) >= limit_per_minute:
        return False
    window.append(now)
    _prune_if_needed(now)
    return True


def reset() -> None:
    """فقط برایِ تست."""
    _windows.clear()
