from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings


class IsSuperAdmin(BaseFilter):
    """
    برای بخش‌هایی از پنلِ ادمین که فقط سوپرادمین‌ها (همون لیستِ ثابتِ
    ADMIN_TELEGRAM_IDS در .env) باید بهشون دسترسی داشته باشن — تنظیماتِ
    قیمت/تخفیف، تنظیماتِ کلیدها، استخرِ کلیدهایِ AI، و خودِ مدیریتِ
    ادمین‌هایِ عملیاتی. برخلافِ IsAdmin نیازی به session/دیتابیس نداره.
    """

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        return event.from_user is not None and event.from_user.id in settings.admin_ids


class IsAdmin(BaseFilter):
    """
    برای اعمال روی کل یک روتر (مثل admin.py) با router.message.filter(IsAdmin())
    و router.callback_query.filter(IsAdmin())، تا لازم نباشه توی تک‌تک
    هندلرها چک تکراری بنویسیم.

    هم سوپرادمین‌هایِ .env و هم ادمین‌هایِ عملیاتیِ ثبت‌شده توی جدولِ
    admin_roles رو قبول می‌کنه (RBAC). session از طریقِ DbSessionMiddleware
    (که سرتاسری، رویِ dispatcher.update ثبت شده) تزریق می‌شه؛ اگه به هر
    دلیلی session نبود، محافظه‌کارانه فقط سوپرادمین رو قبول می‌کنیم —
    یعنی نبودِ session هیچ‌وقت باعثِ دسترسیِ غیرمجاز نمی‌شه.
    """

    async def __call__(self, event: Message | CallbackQuery, session: AsyncSession | None = None) -> bool:
        if event.from_user is None:
            return False
        if event.from_user.id in settings.admin_ids:
            return True
        if session is None:
            return False
        from app.services import admin_role_service

        return await admin_role_service.is_operator(session, event.from_user.id)
