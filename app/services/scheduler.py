from __future__ import annotations

import asyncio
import logging

from aiogram import Bot

from app.database.session import session_scope
from app.services import (
    conversation_service,
    grace_period_service,
    job_gate_service,
    order_expiry_service,
    payment_expiry_service,
    report_service,
    shop_prefs_service,
    time_freeze_service,
    wallet_expiry_service,
)
from app.services.admin_settings_service import get_admin_settings

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 30 * 60


async def run_periodic_pass(main_bot: Bot) -> None:
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
    if not job_gate_service.is_paused(admin_settings, "orders"):
        async with session_scope() as session:
            await order_expiry_service.process_order_expiry(session, main_bot)
    if not job_gate_service.is_paused(admin_settings, "prune"):
        async with session_scope() as session:
            # A5: مدتِ نگهداریِ مکالمه per-shop است؛ نگاشتِ همه‌یِ فروشگاه‌ها یک‌بار ساخته می‌شود.
            default_days = shop_prefs_service.resolve(shop_prefs_service.CONVERSATION_RETENTION, None, admin_settings)
            retention_by_shop = await shop_prefs_service.retention_by_shop(session, admin_settings)
            await conversation_service.prune_old_messages_for_shops(session, retention_by_shop, default_days)


async def run_periodic_tasks(main_bot: Bot, stop_event: asyncio.Event, interval_seconds: int = CHECK_INTERVAL_SECONDS) -> None:
    while not stop_event.is_set():
        try:
            await run_periodic_pass(main_bot)
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

