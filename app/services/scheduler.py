from __future__ import annotations

import asyncio
import logging
import time

from aiogram import Bot

from app.database.session import session_scope
from app.services import (
    admin_alert_service,
    commission_receivable_service,
    conversation_service,
    grace_period_service,
    job_gate_service,
    order_expiry_service,
    payment_expiry_service,
    bot_branding_service,
    notification_service,
    report_service,
    shop_prefs_service,
    time_freeze_service,
    wallet_expiry_service,
    wallet_service,
)
from app.services.admin_settings_service import get_admin_settings

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 30 * 60
# PHASE 5E: همسنجیِ دفتر گران‌تر از بقیه است؛ ساعتی یک‌بار کافی است تا یک اختلافِ
# حسابداری حداکثر یک ساعت بعد به ادمین بگوید، بدونِ اینکه کوئریِ گروهی در هر دورِ جاب بزنیم.
RECONCILE_INTERVAL_SECONDS = 60 * 60
_last_reconcile_at = 0.0


def reset_reconcile_clock_for_tests() -> None:
    """فقط برایِ تست: دوربعدِ همسنجی بلافاصله مجاز باشد."""
    global _last_reconcile_at
    _last_reconcile_at = 0.0


async def run_periodic_pass(main_bot: Bot, bot_manager=None) -> None:
    """یک دورِ کاملِ جاب‌هایِ دوره‌ای (قابلِ تست). K3: ازسرگیریِ خودکارِ توقفِ زمان؛ K4: هر گروه جدا قابلِ توقف است (فقط رد می‌شه)."""
    async with session_scope() as session:
        await time_freeze_service.auto_resume_due(session)  # حتی با جاب‌هایِ متوقف؛ تاریخ‌ها باید جبران بشن
    async with session_scope() as session:
        admin_settings = await get_admin_settings(session)
    if not job_gate_service.is_paused(admin_settings, "grace"):
        async with session_scope() as session:
            await grace_period_service.process_grace_transitions(session, main_bot)
    if not job_gate_service.is_paused(admin_settings, "reports"):
        async with session_scope() as session:
            await report_service.send_due_reports(session, main_bot)
        async with session_scope() as session:
            await report_service.send_due_nightly_reports(session, main_bot)
    if not job_gate_service.is_paused(admin_settings, "wallet"):
        async with session_scope() as session:
            await wallet_expiry_service.process_wallet_expiry_and_reminders(session, main_bot)
        await reconcile_wallet_ledgers()
        # P21-C (F4): کمیسیونِ نگرفته‌شده با اولین شارژِ کافی جمع می‌شود (جابِ جدا نیست؛ همین گروه).
        async with session_scope() as session:
            collected = await commission_receivable_service.collect_due(session)
        if collected["settled"]:
            logger.info("جمعِ طلبِ کمیسیون: %s ردیف تسویه شد (از %s فروشگاهِ بدهکار).", collected["settled"], collected["owners"])
    if not job_gate_service.is_paused(admin_settings, "orders"):
        async with session_scope() as session:
            await order_expiry_service.process_order_expiry(session, main_bot)
    # A2 + P21-A: بازرسیِ دوره‌ایِ بیوگرافی — نوبتِ *هر ربات* در خودش ثبت می‌شود
    # (branding_next_check_at)، پس این فراخوانی در هر لوپ بی‌هزینه است و یکِ رباتِ خراب،
    # بقیه را درگیرِ درخواستِ API مجدد نمی‌کند. بی‌خطر اگر bot_manager نباشد.
    if bot_manager is not None and not job_gate_service.is_paused(admin_settings, "branding"):
        async with session_scope() as session:
            await bot_branding_service.sync_all(session, bot_manager, main_bot)
    # P20 · صندوقِ اعلان‌ها: خبری که تلگرام/بله نپذیرفت، تا ۶ بار با backoff دوباره تلاش می‌شود.
    if bot_manager is not None and not job_gate_service.is_paused(admin_settings, "notifications"):
        async with session_scope() as session:
            queued = await notification_service.send_due(session, bot_manager, main_bot)
        if queued["sent"] or queued["failed"]:
            logger.info(
                "تلاشِ دوبارهٔ اعلان‌ها: ارسال‌شده=%s ناموفقِ قطعی=%s در انتظارِ دورِ بعد=%s",
                queued["sent"], queued["failed"], queued["retrying"],
            )
    if not job_gate_service.is_paused(admin_settings, "prune"):
        async with session_scope() as session:
            # A5: مدتِ نگهداریِ مکالمه per-shop است؛ نگاشتِ همه‌یِ فروشگاه‌ها یک‌بار ساخته می‌شود.
            default_days = shop_prefs_service.resolve(shop_prefs_service.CONVERSATION_RETENTION, None, admin_settings)
            retention_by_shop = await shop_prefs_service.retention_by_shop(session, admin_settings)
            await conversation_service.prune_old_messages_for_shops(session, retention_by_shop, default_days)
            # P21-B (O3): خودِ صفِ اعلان هم باید پاک‌سازی شود (در P20 ساخته شد و هیچ مهلتی نداشت).
            pruned = await notification_service.prune_aged(session)
        if pruned:
            logger.info("پاک‌سازیِ صفِ اعلان‌ها: %s ردیفِ کهنه حذف شد.", pruned)


async def reconcile_wallet_ledgers() -> int:
    """
    PHASE 5E — همسنجیِ «موجودیِ کش‌شده ↔ دفتر ↔ بسته‌هایِ شارژ».

    عمداً هر دورِ جاب اجرا نمی‌شود (RECONCILE_INTERVAL_SECONDS) تا کوئریِ گروهیِ سنگینِ
    رویِ دفترِ رو‌به‌رشد مسیرِ داغِ برنامه نشود. اختلاف فقط لاگ/هشدار می‌شود و هیچ داده‌ای
    را «اصلاح» نمی‌کند: اصلاحِ حسابداری باید تصمیمِ ادمین با ردیفِ معکوسِ جدید باشد، نه
    بازنویسیِ تاریخچه.
    """
    global _last_reconcile_at
    now = time.monotonic()
    if now - _last_reconcile_at < RECONCILE_INTERVAL_SECONDS:
        return 0
    _last_reconcile_at = now
    try:
        async with session_scope() as session:
            gaps = await wallet_service.reconcile_balances(session)
    except Exception:
        logger.exception("همسنجیِ دفترِ کیف‌پول اجرا نشد (برنامه نباید بخوابد).")
        return 0
    if not gaps:
        return 0
    worst = gaps[0]
    logger.error(
        "اختلافِ همسنجیِ کیف‌پول: %s فروشگاه‌دار؛ نمونه owner_id=%s کشیده=%s دفتر=%s بسته‌ها=%s",
        len(gaps),
        worst["owner_id"],
        worst["cached_toman"],
        worst["ledger_toman"],
        worst["lots_toman"],
    )
    admin_alert_service.record_event(
        admin_alert_service.KIND_LEDGER,
        f"{len(gaps)} فروشگاه‌دار اختلافِ دفتر دارد (نمونهٔ id={worst['owner_id']}، {worst['ledger_delta_toman']} تومان)",
    )
    return len(gaps)


async def run_periodic_tasks(
    main_bot: Bot, stop_event: asyncio.Event, bot_manager=None, interval_seconds: int = CHECK_INTERVAL_SECONDS
) -> None:
    while not stop_event.is_set():
        try:
            # bot_manager باید پاس شود: بدونِ آن پاسِ بازرسیِ بیوگرافی عملاً هرگز اجرا نمی‌شود
            # (دست‌کاریِ بیو فقط در همان پاس برگردانده و به فروشگاه‌دار خبر داده می‌شود).
            await run_periodic_pass(main_bot, bot_manager)
        except Exception:
            logger.exception("اجرای تسک‌های دوره‌ای با خطا مواجه شد.")

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            pass


PAYMENT_EXPIRY_INTERVAL_SECONDS = 60


async def run_payment_expiry_loop(
    main_bot: Bot, bot_manager, stop_event: asyncio.Event, interval_seconds: int = PAYMENT_EXPIRY_INTERVAL_SECONDS
) -> None:
    """جابِ جدایِ ~۶۰ثانیه‌ایِ انقضایِ مهلتِ پرداخت (مهلت‌ها دقیقه‌ای‌اند؛ تسکِ ۳۰دقیقه‌ای کافی نیست)."""
    while not stop_event.is_set():
        try:
            async with session_scope() as session:
                paused = job_gate_service.is_paused(await get_admin_settings(session), "orders")  # K4
            if not paused:
                await payment_expiry_service.process_payment_expiry(main_bot, bot_manager)
        except Exception:
            logger.exception("جابِ انقضایِ پرداخت با خطا مواجه شد.")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            pass

