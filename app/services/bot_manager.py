from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramAPIError, TelegramUnauthorizedError

from app.config import RunMode, settings
from app.database.models import ShopBot
from app.database.session import session_scope
from app.utils.encryption import decrypt_token

logger = logging.getLogger(__name__)


class ShopBotManager:
    """
    ثبت/حذفِ پویایِ ربات‌های فروشگاهی در زمانِ اجرا (بدون نیاز به ری‌استارتِ
    کل برنامه). هر ربات یا یه تسکِ polling مجزا داره (حالت polling) یا از
    طریق روتِ webhook مشترک /webhook/shop/{shop_bot_id} فید می‌شه.
    """

    def __init__(self, dispatcher: Dispatcher) -> None:
        self._dispatcher = dispatcher
        self._bots: dict[int, Bot] = {}
        self._polling_tasks: dict[int, asyncio.Task] = {}
        self._secrets: dict[int, str] = {}

    def get_bot(self, shop_bot_id: int) -> Bot | None:
        return self._bots.get(shop_bot_id)

    def registered_shop_bot_ids(self) -> list[int]:
        return list(self._bots.keys())

    def get_secret(self, shop_bot_id: int) -> str | None:
        return self._secrets.get(shop_bot_id)

    async def register(self, shop_bot: ShopBot) -> None:
        raw_token = decrypt_token(shop_bot.encrypted_token)
        bot = Bot(token=raw_token)

        if shop_bot.id in self._bots:
            await self.unregister(shop_bot.id, disable_in_db=False)

        self._bots[shop_bot.id] = bot
        self._secrets[shop_bot.id] = shop_bot.webhook_secret_token

        if settings.run_mode == RunMode.WEBHOOK:
            webhook_url = f"{settings.webhook_base_url.rstrip('/')}/webhook/shop/{shop_bot.id}"
            await bot.set_webhook(webhook_url, secret_token=shop_bot.webhook_secret_token, drop_pending_updates=True)
        else:
            task = asyncio.create_task(self._poll(shop_bot.id, bot))
            self._polling_tasks[shop_bot.id] = task

    async def unregister(self, shop_bot_id: int, disable_in_db: bool = True) -> None:
        bot = self._bots.pop(shop_bot_id, None)
        task = self._polling_tasks.pop(shop_bot_id, None)
        self._secrets.pop(shop_bot_id, None)
        if task is not None:
            task.cancel()
        if bot is not None:
            try:
                await bot.delete_webhook(drop_pending_updates=False)
            except TelegramAPIError:
                pass
            await bot.session.close()

    async def _mark_disabled(self, shop_bot_id: int, reason: str) -> None:
        async with session_scope() as session:
            shop_bot = await session.get(ShopBot, shop_bot_id)
            if shop_bot is not None:
                shop_bot.is_active = False
                shop_bot.disabled_reason = reason

    async def _poll(self, shop_bot_id: int, bot: Bot) -> None:
        try:
            await bot.delete_webhook(drop_pending_updates=True)
        except TelegramAPIError:
            logger.exception("حذف وب‌هوکِ ربات فروشگاهی %s ناموفق بود.", shop_bot_id)

        offset = None
        while True:
            try:
                updates = await bot.get_updates(offset=offset, timeout=20, allowed_updates=self._dispatcher.resolve_used_update_types())
            except TelegramUnauthorizedError:
                logger.warning("توکنِ ربات فروشگاهی %s دیگه معتبر نیست؛ غیرفعالش می‌کنیم.", shop_bot_id)
                await self._mark_disabled(shop_bot_id, "توکن نامعتبر شد (احتمالاً توسط فروشگاه‌دار revoke شده)")
                return
            except asyncio.CancelledError:
                raise
            except TelegramAPIError:
                logger.exception("دریافتِ آپدیت برای ربات فروشگاهی %s ناموفق بود؛ بعد از کمی مکث دوباره امتحان می‌کنیم.", shop_bot_id)
                await asyncio.sleep(5)
                continue
            except Exception:
                logger.exception("خطای غیرمنتظره در polling ربات فروشگاهی %s.", shop_bot_id)
                await asyncio.sleep(5)
                continue

            for update in updates:
                offset = update.update_id + 1
                try:
                    await self._dispatcher.feed_update(bot, update)
                except Exception:
                    logger.exception("پردازشِ یک آپدیت برای ربات فروشگاهی %s با خطا مواجه شد.", shop_bot_id)

    async def load_all(self, shop_bots: list[ShopBot]) -> None:
        for shop_bot in shop_bots:
            try:
                await self.register(shop_bot)
            except Exception:
                logger.exception("بارگذاریِ ربات فروشگاهی %s در راه‌اندازی ناموفق بود.", shop_bot.id)
