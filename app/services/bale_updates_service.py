"""دریافتِ آپدیتِ بله با getUpdates (W5 · B6) — برایِ استقرار بدونِ HTTPSِ عمومی.

بله دو راهِ رسمیِ هم‌زمان‌ناپذیر دارد: webhook یا getUpdates. `BALE_UPDATES_MODE=polling` (پیش‌فرض) ⇒ این حلقه.
طراحی: `offset = آخرین update_id + ۱` (تایید = دریافتِ دوباره‌ی نکردنش)؛ خطایِ یک آپدیت حلقه رو نمی‌خوابونه
(offset همیشه جلو می‌ره؛ هندلرهایِ پرداخت ایدمپوتنت‌اند — B10)؛ خطایِ شبکه/API ⇒ backoffِ نمایی (حداکثر ۶۰ث)؛
توقف با `stop_event` فوری است (انتظارها stop-aware‌اند). حافظه‌یِ offset فقط درون‌پردازه‌ایه؛ بعد از ری‌استارت بله
آپدیت‌هایِ تاییدنشده رو دوباره می‌فرسته و ایدمپوتنسی جلویِ اثرِ دوم رو می‌گیره."""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

logger = logging.getLogger(__name__)

BACKOFF_BASE_SECONDS = 2.0
BACKOFF_MAX_SECONDS = 60.0
IDLE_SLEEP_SECONDS = 1.0

Handler = Callable[[dict], Awaitable[None]]
Fetcher = Callable[[str, int | None], Awaitable[list[dict]]]
TokenProvider = Callable[[], Awaitable[str]]


def backoff_seconds(consecutive_failures: int) -> float:
    """۲، ۴، ۸ … حداکثر ۶۰ ثانیه (failures ≤ 0 ⇒ ۰)."""
    if consecutive_failures <= 0:
        return 0.0
    return min(BACKOFF_MAX_SECONDS, BACKOFF_BASE_SECONDS * (2 ** (consecutive_failures - 1)))


def next_offset(current: int | None, updates: list[dict]) -> int | None:
    """offsetِ بعدی؛ آپدیتِ بدونِ update_id عددی نادیده گرفته می‌شه. بدونِ آپدیت ⇒ همان offsetِ فعلی."""
    ids = [u.get("update_id") for u in updates if isinstance(u, dict) and isinstance(u.get("update_id"), int) and not isinstance(u.get("update_id"), bool)]
    if not ids:
        return current
    return max(max(ids) + 1, current or 0)


async def poll_once(bot_token: str, offset: int | None, handler: Handler, fetch: Fetcher) -> tuple[int | None, int]:
    """یک دور: (offsetِ جدید, تعدادِ آپدیتِ پردازش‌شده). خطایِ fetch بالا می‌ره؛ خطایِ هندلر فقط لاگ می‌شه."""
    updates = await fetch(bot_token, offset)
    processed = 0
    for update in updates:
        if not isinstance(update, dict):
            continue
        try:
            await handler(update)
        except Exception:  # noqa: BLE001 — یک آپدیتِ خراب نباید صف رو قفل کنه
            logger.exception("پردازشِ آپدیتِ بله (update_id=%s) شکست خورد؛ رد می‌شه.", update.get("update_id"))
        processed += 1
    return next_offset(offset, updates), processed


async def _sleep_or_stop(stop_event: asyncio.Event, seconds: float) -> bool:
    """True یعنی stop خورده. خواب با stop قطع می‌شه."""
    if seconds <= 0:
        return stop_event.is_set()
    try:
        await asyncio.wait_for(stop_event.wait(), timeout=seconds)
        return True
    except asyncio.TimeoutError:
        return stop_event.is_set()


async def run_loop(
    bot_token: str,
    handler: Handler,
    stop_event: asyncio.Event,
    fetch: Fetcher,
    token_provider: TokenProvider | None = None,
) -> None:
    """`token_provider` (A1): در هر گردش توکنِ تازه از پنل/.env خوانده می‌شود ⇒ تغییرِ توکن بدونِ ری‌استارت اعمال
    می‌شود. چون offset به ازایِ هر ربات معنا دارد، با عوض‌شدنِ توکن offset صفر می‌شود (ایدمپوتنسیِ هندلرها جلویِ
    اثرِ آپدیتِ تکراری را می‌گیرد — B10)."""
    offset: int | None = None
    failures = 0
    current_token = bot_token
    while not stop_event.is_set():
        if token_provider is not None:
            try:
                fresh = await token_provider()
            except Exception:  # noqa: BLE001 — نبودِ DB نباید حلقه‌یِ دریافتِ پرداخت را بخواباند
                logger.warning("خواندنِ توکنِ تازه‌یِ بله ناموفق بود؛ همان توکنِ قبلی استفاده می‌شود.", exc_info=True)
                fresh = current_token
            if fresh and fresh != current_token:
                current_token = fresh
                offset = None
                logger.info("توکنِ رباتِ بله عوض شد؛ حلقه‌یِ getUpdates با توکنِ تازه و offsetِ صفر ادامه می‌دهد.")
        if not current_token:
            if await _sleep_or_stop(stop_event, BACKOFF_MAX_SECONDS):
                return
            continue
        try:
            offset, processed = await poll_once(current_token, offset, handler, fetch)
            failures = 0
            if processed == 0 and await _sleep_or_stop(stop_event, IDLE_SLEEP_SECONDS):
                return
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            failures += 1
            delay = backoff_seconds(failures)
            logger.warning("getUpdatesِ بله ناموفق بود (بار %s)؛ %.0f ثانیه بعد دوباره.", failures, delay)
            if await _sleep_or_stop(stop_event, delay):
                return
