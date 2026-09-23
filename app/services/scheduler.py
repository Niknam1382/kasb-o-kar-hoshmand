from __future__ import annotations

import asyncio
import logging

from aiogram import Bot

from app.database.session import session_scope
from app.services import conversation_service, grace_period_service, order_expiry_service, report_service, wallet_expiry_service
from app.services.admin_settings_service import get_admin_settings

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 30 * 60


async def run_periodic_tasks(main_bot: Bot, stop_event: asyncio.Event, interval_seconds: int = CHECK_INTERVAL_SECONDS) -> None:
    while not stop_event.is_set():
        try:
            async with session_scope() as session:
                await grace_period_service.process_grace_transitions(session, main_bot)
            async with session_scope() as session:
                await report_service.send_due_reports(session, main_bot)
            async with session_scope() as session:
                await wallet_expiry_service.process_wallet_expiry_and_reminders(session, main_bot)
            async with session_scope() as session:
                await order_expiry_service.process_order_expiry(session, main_bot)
            async with session_scope() as session:
                admin_settings = await get_admin_settings(session)
                await conversation_service.prune_old_messages(session, admin_settings.conversation_retention_days)
        except Exception:
            logger.exception("اجرای تسک‌های دوره‌ای با خطا مواجه شد.")

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            pass
