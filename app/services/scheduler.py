from __future__ import annotations

import asyncio
import logging
import time

from aiogram import Bot
from sqlalchemy import text as sql_text

from app.database.session import session_scope
from app.utils.validators import fa_number
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
    scheduled_broadcast_service,
    shop_prefs_service,
    stock_alert_service,
    time_freeze_service,
    wallet_expiry_service,
    wallet_service,
)
from app.services.admin_settings_service import cached_admin_settings

logger = logging.getLogger(__name__)

# P21-E (O4): کلیدِ قفلِ advisoryِ جاب — یک عددِ ثابتِ قرارداد؛ تغییرش یعنی دو قفلِ جدا.
SCHEDULER_LOCK_KEY = 72_530_311
CHECK_INTERVAL_SECONDS = 30 * 60
# PHASE 5E: همسنجیِ دفتر گران‌تر از بقیه است؛ ساعتی یک‌بار کافی است تا یک اختلافِ
# حسابداری حداکثر یک ساعت بعد به ادمین بگوید، بدونِ اینکه کوئریِ گروهی در هر دورِ جاب بزنیم.
RECONCILE_INTERVAL_SECONDS = 60 * 60
# P37 (باگِ تولیدی): «۰.۰» یعنی «آخرین همسنجی در مبدأِ زمانِ یکتا». چون `time.monotonic()` رویِ
# لینوکس از بوتِ ماشین می‌شمارد، رویِ سرور/کانتینرِ تازه‌بوت‌شده شرطِ «یک ساعت گذشته» تا یک ساعت
# اول برقرار نیست و همسنجیِ دفتر — تنها نگهبانِ اختلافِ حسابداری — در همان ساعتِ اول اجرا
# نمی‌شد. «هنوز اجرا نشده» باید None باشد.
_last_reconcile_at: float | None = None


def reset_reconcile_clock_for_tests() -> None:
    """فقط برایِ تست: دوربعدِ همسنجی بلافاصله مجاز باشد."""
    global _last_reconcile_at
    _last_reconcile_at = None


async def run_periodic_pass(main_bot: Bot, bot_manager=None) -> None:
    """یک دورِ کاملِ جاب‌هایِ دوره‌ای (قابلِ تست). K3: ازسرگیریِ خودکارِ توقفِ زمان؛ K4: هر گروه جدا قابلِ توقف است (فقط رد می‌شه).

    P21-E (O4): کلِ دور داخلِ یکِ قفلِ advisoryِ دیتابیس می‌چرخد. تا پیش‌ازاین «دو نسخهٔ اپ»
    یعنی دو scheduler مستقل ⇒ گزارش/انقضا/یادآوریِ دوباره. با `pg_try_advisory_lock` نسخهٔ
    دوم همان لحظه رد می‌شود (تلاشِ مجدد در لوپِ بعدی) و لازم نیست تک‌نسخه باشد.
    """
    async with session_scope() as session:
        if not await job_lock_acquired(session):
            logger.debug("نسخهٔ دیگری از اپ در حالِ اجرای جاب‌هاست؛ این دور رد شد.")
            return
        try:
            await _run_periodic_pass_locked(main_bot, bot_manager)
        finally:
            await release_job_lock(session)


async def job_lock_acquired(session) -> bool:
    """قفلِ سراسریِ جاب (کلیدِ ثابت؛ شماره‌اش بخشی از قرارداد است، تغییرش = دو قفلِ جدا)."""
    value = (await session.execute(sql_text("SELECT pg_try_advisory_lock(:key)"), {"key": SCHEDULER_LOCK_KEY})).scalar_one()
    return bool(value)


async def release_job_lock(session) -> None:
    await session.execute(sql_text("SELECT pg_advisory_unlock(:key)"), {"key": SCHEDULER_LOCK_KEY})


async def _run_periodic_pass_locked(main_bot: Bot, bot_manager) -> None:
    async with session_scope() as session:
        await time_freeze_service.auto_resume_due(session)  # حتی با جاب‌هایِ متوقف؛ تاریخ‌ها باید جبران بشن
    async with session_scope() as session:
        admin_settings = await cached_admin_settings(session)
    if not job_gate_service.is_paused(admin_settings, "grace"):
        async with session_scope() as session:
            await grace_period_service.process_grace_transitions(session, main_bot)
    if not job_gate_service.is_paused(admin_settings, "reports"):
        async with session_scope() as session:
            await report_service.send_due_reports(session, main_bot)
        async with session_scope() as session:
            await report_service.send_due_nightly_reports(session, main_bot)
        # P21-D (F7): اخطارِ کمبودِ موجودی — فقط برایِ فروشگاه‌هایی که آستانه تعیین کرده‌اند
        async with session_scope() as session:
            await stock_alert_service.run(session, main_bot)
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
    # P21-F: حلقهٔ ۶۰ثانیه‌ایِ `run_notification_loop` کارِ اصلی را انجام می‌دهد؛ این فراخوانی
    # عمداً مانده (a) اگر کسی آن حلقه را خاموش/متوقف کند صف باز هم تخلیه شود، (b) تستِ سیم‌کشیِ
    # `run_periodic_pass` همچنان واقعی بماند. تکرارِ اجرا بی‌ضرر است: `send_due` ردیف‌ها را
    # `FOR UPDATE SKIP LOCKED` برمی‌دارد و dedupe_key صفِ دوتایی نمی‌سازد.
    if bot_manager is not None and not job_gate_service.is_paused(admin_settings, "notifications"):
        async with session_scope() as session:
            # P21-D (F2): اول ارسال‌هایِ زمان‌بندی‌شده به صف می‌روند، بعد صف تخلیه می‌شود
            queued_broadcast = await scheduled_broadcast_service.queue_due(session)
        if queued_broadcast["scheduled"]:
            logger.info("پخشِ زمان‌بندی‌شده: %s ارسال در صفِ اعلان نشست (%s گیرنده).", queued_broadcast["scheduled"], queued_broadcast["queued"])
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
            # P32: حالت‌هایِ FSMِ رهاشده (مشتری که چک‌اوت را نیمه‌کاره گذاشت) هم باید پاک شوند؛
            # فقط وقتی مسیرِ postgres روشن باشد ردیفی وجود دارد، وگرنه صفر برمی‌گردد.
            from app.services import fsm_storage

            fsm_pruned = await fsm_storage.purge_stale_states(session)
            if fsm_pruned:
                logger.info("پاک‌سازیِ FSM: %s حالتِ کهنه حذف شد.", fsm_pruned)
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
    if _last_reconcile_at is not None and now - _last_reconcile_at < RECONCILE_INTERVAL_SECONDS:
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
        f"{len(gaps)} فروشگاه‌دار اختلافِ دفتر دارد (نمونهٔ id={worst['owner_id']}، {fa_number(worst['ledger_delta_toman'])} تومان)",
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


NOTIFICATION_INTERVAL_SECONDS = 60
PAYMENT_EXPIRY_INTERVAL_SECONDS = 60


async def run_notification_loop(
    main_bot: Bot, bot_manager, stop_event: asyncio.Event, interval_seconds: int = NOTIFICATION_INTERVAL_SECONDS
) -> None:
    """P21-F: تخلیهٔ صندوقِ اعلان هر ۶۰ ثانیه، نه هر ۳۰ دقیقه.

    خبرِ «سفارشت پرداخت شد» نباید تا سه‌نیم‌ساعتِ بعد رویِ صفحه بماند؛ جابِ ۳۰دقیقه‌ایِ کلی
    برایِ این کار too-knees بود. همان backoffِ six-stage سرِ جایش است و `queue_due` (پخشِ
    زمان‌بندی‌شده) هم از همین حلقه تغذیه می‌شود تا پیامِ «امشب ۲۱:۳۰» سرِ وقت برسد.
    """
    while not stop_event.is_set():
        try:
            async with session_scope() as session:
                paused = job_gate_service.is_paused(await cached_admin_settings(session), "notifications")
            if not paused:
                async with session_scope() as session:
                    queued_broadcast = await scheduled_broadcast_service.queue_due(session)
                async with session_scope() as session:
                    result = await notification_service.send_due(session, bot_manager, main_bot)
                if queued_broadcast["scheduled"] or result["sent"] or result["failed"]:
                    logger.info(
                        "تخلیهٔ صفِ اعلان: ارسال=%s درانتظار=%s قطعی=%s (پخشِ زمان‌بندی‌شده: %s)",
                        result["sent"], result["retrying"], result["failed"], queued_broadcast["scheduled"],
                    )
        except Exception:
            logger.exception("حلقهٔ ارسالِ اعلان‌ها با خطا مواجه شد.")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            pass


async def run_payment_expiry_loop(
    main_bot: Bot, bot_manager, stop_event: asyncio.Event, interval_seconds: int = PAYMENT_EXPIRY_INTERVAL_SECONDS
) -> None:
    """جابِ جدایِ ~۶۰ثانیه‌ایِ انقضایِ مهلتِ پرداخت (مهلت‌ها دقیقه‌ای‌اند؛ تسکِ ۳۰دقیقه‌ای کافی نیست)."""
    while not stop_event.is_set():
        try:
            async with session_scope() as session:
                paused = job_gate_service.is_paused(await cached_admin_settings(session), "orders")  # K4
            if not paused:
                await payment_expiry_service.process_payment_expiry(main_bot, bot_manager)
        except Exception:
            logger.exception("جابِ انقضایِ پرداخت با خطا مواجه شد.")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            pass

