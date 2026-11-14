"""پ۶۱ و پ۶۲ · خواستهٔ مالکِ محصول (۲۰۲۶-۱۱-۱۲): «یکِ قسمت در پنلِ ادمین برایِ بررسیِ وضعیتِ
ظرفیت API‌ها و فشارِ سرور به‌صورتِ درصدی و آمارِ دقیق» + «ایجنتی در محیطِ سرور برایِ لاگ‌ها و
بررسیِ مشکلات».

سه ستونِ زنده در یکِ صفحه:
۱. ظرفیتِ AI: برایِ هرِ کلیدِ استخر «چند درخواستِ همانِ کلید همین حالا درِ حالِ اجراست» نسبت به
   سقفِ *خودِ آن کلید*، و جمعِ سقفِ کلیدها در برابرِ سقفِ پلتفرم ⇒ «گلوگاهِ فعلی کجاست».
۲. فشارِ سرور: بارِ میانگینِ ۱ دقیقه به‌ازایِ هر هسته، درصدِ رمِ استفاده‌شده و درصدِ دیسک.
۳. استخرِ دیتابیس: چند اتصالِ هم‌زمان درِ کار از چند اتصالِ مجاز (گلوگاهِ واقعیِ «چند فروشگاهِ
   هم‌زمان» معمولاً همین‌جاست، نه CPU) + شمارنده‌هایِ رویدادِ وب‌هوک و کیف‌پول.

صداقتِ عددی (قاعدهٔ ۱۰): همهٔ اعداد *اندازه‌گیریِ زندهٔ همین پروسه*‌اند؛ سقفِ واقعیِ سرویسِ
ارائه‌دهندهٔ AI هنوز سنجیده نشده و ادعا نمی‌شود، پس رویِ صفحه هم نوشته می‌شود.

دسترسی و جانبی: فقط سوپرادمین. صفحه‌هایِ ظرفیت و عیب‌یاب فقط‌خواندنی‌اند و هیچ هزینه‌ای
نمی‌سازند؛ کوئریِ آن‌ها (یکِ SELECT رویِ استخرِ کلیدها) فقط با زدنِ دکمه یا «تازه‌سازی» اجرا می‌شود
و به مسیرِ پیامِ مشتری ربطی ندارد. تنها استثنا پ۷۲ است: «⚖️ آستانه‌هایِ عیب‌یاب» یکِ ستونِ تنظیماتی
رویِ `admin_settings` را عوض می‌کند (کراندار، ممیزی‌شده) و باز هم هیچ رفتارِ ربات یا مبلغی را تغییر
نمی‌دهد — فقط حساسیتِ *تشخیص* را عوض می‌کند.
"""

from __future__ import annotations

import datetime
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.main_bot import keyboards, texts
from app.bots.main_bot.filters import IsSuperAdmin
from app.bots.main_bot.handlers.owner_common import safe_edit
from app.bots.main_bot.states import DoctorThresholdStates
from app.database.models import AuditEventType
from app.services import audit_log_service, capacity_service, server_doctor
from app.services.admin_settings_service import get_admin_settings

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


async def _doctor_screen(session: AsyncSession) -> tuple[str, object]:
    findings = await server_doctor.inspect(session)
    await session.commit()
    return (
        texts.doctor_screen_text(findings, datetime.datetime.now(datetime.timezone.utc)),
        keyboards.doctor_keyboard(),
    )


@router.message(F.text == texts.DOCTOR_BUTTON)
async def open_doctor(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    body, markup = await _doctor_screen(session)
    await message.answer(body, reply_markup=markup)


@router.callback_query(F.data == "doctor_refresh")
async def cb_doctor_refresh(callback: CallbackQuery, session: AsyncSession) -> None:
    """بازرسیِ دوباره از همان پروسه: خنک‌کردنِ هشدارهایِ جاب دست‌نخورده می‌ماند (این‌جا فقط خواندن)."""
    await callback.answer()
    body, markup = await _doctor_screen(session)
    await safe_edit(callback, body, markup)


# ------------------------------------------------------------------ پ۷۲ · آستانه‌هایِ عیب‌یاب
CANCEL_WORDS = ("انصراف", "لغو", "/cancel")


async def _thresholds_screen(session: AsyncSession) -> tuple[str, object]:
    limits = await server_doctor.thresholds(session)
    return (
        texts.doctor_thresholds_text(limits, server_doctor.THRESHOLD_SPECS),
        keyboards.doctor_thresholds_keyboard(limits),
    )


@router.callback_query(F.data == "doctor_thr_open")
async def cb_doctor_thresholds(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    await callback.answer()
    body, markup = await _thresholds_screen(session)
    await safe_edit(callback, body, markup)


@router.callback_query(F.data == "doctor_thr_reset")
async def cb_doctor_threshold_reset(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    admin_settings = await get_admin_settings(session)
    admin_settings.doctor_thresholds = None
    await session.flush()
    await audit_log_service.log(
        session,
        AuditEventType.ADMIN_SETTING_CHANGED,
        actor_telegram_id=callback.from_user.id,
        details="بازگشتِ همهٔ آستانه‌هایِ عیب‌یاب به پیش‌فرضِ نسخه (پنلِ ادمین)",
    )
    await session.commit()
    await callback.answer(texts.DOCTOR_THRESH_RESET_DONE)
    body, markup = await _thresholds_screen(session)
    await safe_edit(callback, body, markup)


@router.callback_query(F.data.startswith("doctor_thr:"))
async def cb_doctor_threshold_edit(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    key = (callback.data or "").split(":", 1)[1]
    spec = server_doctor.THRESHOLD_SPECS.get(key)
    if spec is None:
        await callback.answer(texts.DOCTOR_THRESH_STALE, show_alert=True)
        return
    limits = await server_doctor.thresholds(session)
    await state.clear()
    await state.set_state(DoctorThresholdStates.waiting_value)
    await state.update_data(doctor_threshold_key=key)
    await callback.answer()
    await callback.message.answer(
        f"{texts.doctor_threshold_value_text(key, limits[key], spec)}\n\n{texts.doctor_threshold_ask_text(spec)}"
    )


@router.message(DoctorThresholdStates.waiting_value, F.text)
async def cb_doctor_threshold_received(message: Message, state: FSMContext, session: AsyncSession) -> None:
    raw = (message.text or "").strip()
    data = await state.get_data()
    if raw in CANCEL_WORDS:
        await state.clear()
        await message.answer(texts.OPERATION_CANCELLED)
        return
    key = str(data.get("doctor_threshold_key") or "")
    spec = server_doctor.THRESHOLD_SPECS.get(key)
    if spec is None:
        await state.clear()
        await message.answer(texts.DOCTOR_THRESH_STALE)
        return
    value = server_doctor.parse_input(key, raw)
    if value is None:
        await message.answer(texts.doctor_threshold_invalid_text(spec))  # state می‌ماند تا درست بنویسد
        return
    limits = await server_doctor.thresholds(session)
    limits[key] = value
    admin_settings = await get_admin_settings(session)
    admin_settings.doctor_thresholds = server_doctor.dump_thresholds(limits)
    await session.flush()
    _default, _low, _high, kind, label = spec
    shown = texts.fa_percent(value) if kind == "percent" else texts.fa_number(int(value))
    await audit_log_service.log(
        session,
        AuditEventType.ADMIN_SETTING_CHANGED,
        actor_telegram_id=message.from_user.id,
        details=f"آستانهٔ عیب‌یاب «{label}» ⇒ {shown} (پنلِ ادمین؛ فقط حساسیتِ تشخیص)",
    )
    await session.commit()
    await state.clear()
    await message.answer(texts.DOCTOR_THRESH_SAVED.format(label=label, value=shown))
    body, markup = await _thresholds_screen(session)
    await message.answer(body, reply_markup=markup)
