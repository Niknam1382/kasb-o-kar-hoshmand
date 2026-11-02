from __future__ import annotations

import time
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.config import settings
from app.database.session import async_session_factory


class DbSessionMiddleware(BaseMiddleware):
    async def __call__(
        self, handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]], event: TelegramObject, data: dict[str, Any]
    ) -> Any:
        async with async_session_factory() as session:
            data["session"] = session
            try:
                result = await handler(event, data)
                await session.commit()
                return result
            except Exception:
                await session.rollback()
                raise


class MenuButtonEscapeMiddleware(BaseMiddleware):
    """
    اگه کاربر وسطِ یه FSM state (مثلاً «منتظرِ توکن ربات» یا «منتظرِ نامِ کانال» باشه
    ولی روی یکی از دکمه‌های شناخته‌شده‌ی منو (پنل فروشگاه‌دار یا پنل ادمین) بزنه،
    اول state رو پاک می‌کنه تا این دکمه به‌جای گیرافتادن توی handlerِ «منتظرِ متن»،
    درست به handlerِ خودش برسه. PreviewStates.active عمداً استثناست، چون قرار
    *هست* هر متنی (حتی اگه شبیهِ متنِ یه دکمه باشه) عیناً به‌عنوانِ پیامِ مشتری در
    نظر گرفته بشه.
    """

    _EXEMPT_STATES = {"PreviewStates:active"}

    def __init__(self, known_button_texts: set[str]) -> None:
        self._known_button_texts = known_button_texts

    async def __call__(
        self, handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]], event: TelegramObject, data: dict[str, Any]
    ) -> Any:
        if isinstance(event, Message) and event.text and event.text in self._known_button_texts:
            state = data.get("state")
            if state is not None:
                current = data.get("raw_state")
                if current is not None and current not in self._EXEMPT_STATES:
                    await state.clear()
                    # StateFilter مقدارِ state رو زنده کوئری نمی‌کنه، از همین raw_state
                    # کش‌شده توی data می‌خونه؛ برای همین باید خودمون هم آپدیتش کنیم،
                    # وگرنه handlerِ قدیمی (بر اساسِ state ی که دیگه پاک شده) صدا زده می‌شه.
                    data["raw_state"] = None
        return await handler(event, data)


class ChannelGateMiddleware(BaseMiddleware):
    """
    عضویتِ کانال‌های اجباری رو روی هر تعاملِ فروشگاه‌دار (نه فقط /start) چک می‌کنه.
    این یعنی اگه ادمین یه کانال رو *بعد از* ثبت‌نامِ یه فروشگاه‌دار اضافه کنه، همون
    فروشگاه‌دار هم دفعه‌ی بعدی که از پنل استفاده کنه گیر می‌شه، نه فقط کاربرهای تازه.
    فقط روی روترهایی که عمداً بهش وصل می‌شن اعمال می‌شه (پنل و محصولات)؛ ادمین‌ها
    و مسیرِ خودِ /start (که گیتِ خودشو داره) رو دست‌نخورده می‌ذاره.

    برای جلوگیری از زدنِ یه درخواستِ get_chat_member به تلگرام به‌ازای *هر* پیام
    (که مصرفِ شبکه رو بی‌جهت بالا می‌بره)، نتیجه‌ی «عبورِ موفق» رو چند دقیقه کش
    می‌کنیم. نتیجه‌ی «رد» رو کش نمی‌کنیم، تا همون لحظه‌ای که کاربر واقعاً عضو شد،
    بدونِ تاخیر رد بشه.
    """

    _PASS_CACHE_TTL_SECONDS = 300

    def __init__(self) -> None:
        self._pass_cache: dict[int, float] = {}

    async def __call__(
        self, handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]], event: TelegramObject, data: dict[str, Any]
    ) -> Any:
        user = getattr(event, "from_user", None)
        session = data.get("session")
        bot = data.get("bot")

        if user is None or session is None or bot is None or user.id in settings.admin_ids:
            return await handler(event, data)

        cached_at = self._pass_cache.get(user.id)
        if cached_at is not None and (time.monotonic() - cached_at) < self._PASS_CACHE_TTL_SECONDS:
            return await handler(event, data)

        # لازیم ایمپورت می‌کنیم که از importِ دایره‌ای بینِ middlewares و channel_service جلوگیری بشه
        from app.bots.main_bot import keyboards, texts
        from app.services import channel_service

        channels = await channel_service.get_mandatory_channels(session)
        if not channels:
            return await handler(event, data)

        missing = await channel_service.get_missing_channels(bot, channels, user.id)
        if not missing:
            self._pass_cache[user.id] = time.monotonic()
            return await handler(event, data)

        if isinstance(event, CallbackQuery):
            await event.answer(texts.CHANNELS_GATE_STILL_NOT_MEMBER, show_alert=True)
        else:
            await bot.send_message(
                user.id, texts.channels_gate_intro(missing), reply_markup=keyboards.channels_gate_keyboard(missing, "check_channels_membership")
            )
        return None


async def _is_platform_admin(user_id: int, session) -> bool:
    """آیا این کاربر ادمینِ پلتفرم است (سوپرادمین یا ادمینِ عملیاتی)."""
    from app.services import admin_role_service  # لازیم: جلوگیری از importِ دایره‌ای

    if user_id in settings.admin_ids:
        return True
    return await admin_role_service.is_operator(session, user_id)


class IdentityRefreshMiddleware(BaseMiddleware):
    """H2: یوزرنیمِ فروشگاه‌دار رو (فقط وقتی عوض شده) از آپدیتِ تلگرام تازه می‌کنه تا هویتِ متنی همیشه به‌روز باشه.
    یک SELECTِ ایندکس‌دار به‌ازایِ آپدیت؛ تغییر با commitِ DbSessionMiddleware ذخیره می‌شه.

    P22 (مشکلِ ۸) دو کارِ دیگر رویِ همان یک SELECT:
    - `last_seen_at` را نو می‌کند (با میانه‌بندِ زمانی در خودِ کوئری).
    - اگر حساب حذفِ نرم شده باشد، آپدیت را همین‌جا می‌بلعد و فقط پیامِ «حساب غیرفعال است» را
      نشان می‌دهد. بیِ این دروازه، فروشگاه‌دارِ پاک‌شده به صفحه‌یِ «فروشگاه تنظیم نشده» می‌رفت و
      می‌توانست از نو ثبت‌نام کند؛ دروازه باید قبلِ هر هندلری باشد، پس همین‌جا نشسته است."""

    async def __call__(
        self, handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]], event: TelegramObject, data: dict[str, Any]
    ) -> Any:
        user = getattr(event, "from_user", None)
        session = data.get("session")
        if user is not None and session is not None and not user.is_bot:
            from app.services import identity_service, owner_activity_service, shop_owner_service  # لازیم: جلوگیری از importِ دایره‌ای

            owner = await shop_owner_service.get_by_telegram_id(session, user.id)
            if owner is not None:
                # ادمین‌ها (سوپر یا عملیاتی) با حذفِ حسابِ فروشگاهیشان از پنلِ ادمین بیرون نمی‌مانند —
                # وگرنه یک سوپرادمین که روزی فروشگاه داشته، با بستنِ همان فروشگاه قفل می‌شد.
                if owner.is_deleted and not await _is_platform_admin(user.id, session):
                    from app.bots.main_bot import texts as main_texts  # لازیم: این میدل‌ور برایِ هر دو ربات اجرا می‌شود

                    if isinstance(event, CallbackQuery):
                        await event.answer(main_texts.ACCOUNT_DELETED_NOTICE, show_alert=True)
                    else:
                        await event.answer(main_texts.ACCOUNT_DELETED_NOTICE)
                    return None
                identity_service.sync_from_telegram_user(owner, user)
                # P22 (مشکلِ ۸): «آخرین دیدار». خودِ کوئری شرطِ زمانی دارد ⇒ هر ۱۰ دقیقه یکِ UPDATE،
                # نه هر پیام؛ تغییر با commitِ DbSessionMiddleware ذخیره می‌شود.
                await owner_activity_service.touch(session, owner)
        return await handler(event, data)
