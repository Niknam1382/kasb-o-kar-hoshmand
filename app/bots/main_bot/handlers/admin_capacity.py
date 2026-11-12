"""پ۶۱ · خواستهٔ مالکِ محصول (۲۰۲۶-۱۱-۱۲): «یکِ قسمت در پنلِ ادمین برایِ بررسیِ وضعیتِ ظرفیت
API‌ها و فشارِ سرور به‌صورتِ درصدی و آمارِ دقیق».

سه ستونِ زنده در یکِ صفحه:
۱. ظرفیتِ AI: برایِ هرِ کلیدِ استخر «چند درخواستِ همانِ کلید همین حالا درِ حالِ اجراست» نسبت به
   سقفِ *خودِ آن کلید*، و جمعِ سقفِ کلیدها در برابرِ سقفِ پلتفرم ⇒ «گلوگاهِ فعلی کجاست».
۲. فشارِ سرور: بارِ میانگینِ ۱ دقیقه به‌ازایِ هر هسته، درصدِ رمِ استفاده‌شده و درصدِ دیسک.
۳. استخرِ دیتابیس: چند اتصالِ هم‌زمان درِ کار از چند اتصالِ مجاز (گلوگاهِ واقعیِ «چند فروشگاهِ
   هم‌زمان» معمولاً همین‌جاست، نه CPU) + شمارنده‌هایِ رویدادِ وب‌هوک و کیف‌پول.

صداقتِ عددی (قاعدهٔ ۱۰): همهٔ اعداد *اندازه‌گیریِ زندهٔ همین پروسه*‌اند؛ سقفِ واقعیِ سرویسِ
ارائه‌دهندهٔ AI هنوز سنجیده نشده و ادعا نمی‌شود، پس رویِ صفحه هم نوشته می‌شود.

دسترسی و جانبی: فقط سوپرادمین، فقط‌خواندنی — هیچ دکمه‌ای که چیزی را تغییر دهد یا هزینه‌ای
بسازد وجود ندارد؛ کوئریِ این صفحه (یکِ SELECT رویِ استخرِ کلیدها) فقط با زدنِ دکمه یا «تازه‌سازی»
اجرا می‌شود و به مسیرِ پیامِ مشتری ربطی ندارد.
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.main_bot import keyboards, texts
from app.bots.main_bot.filters import IsSuperAdmin
from app.bots.main_bot.handlers.owner_common import safe_edit
from app.services import capacity_service

logger = logging.getLogger(__name__)

router = Router(name="admin_capacity")
router.message.filter(IsSuperAdmin())
router.callback_query.filter(IsSuperAdmin())


async def _screen(session: AsyncSession) -> tuple[str, object]:
    snapshot = await capacity_service.snapshot(session)
    await session.commit()
    return texts.capacity_text(snapshot), keyboards.capacity_keyboard()


@router.message(F.text == texts.CAPACITY_BUTTON)
async def open_capacity(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    body, markup = await _screen(session)
    await message.answer(body, reply_markup=markup)


@router.callback_query(F.data == "capacity_refresh")
async def cb_capacity_refresh(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    body, markup = await _screen(session)
    await safe_edit(callback, body, markup)
