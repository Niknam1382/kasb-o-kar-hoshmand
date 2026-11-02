"""«⏱ اعتبار و زمان» در پنلِ ادمین (W5 · K1–K4): هدیه‌یِ گروهی، تمدیدِ روز، توقفِ زمان، توقفِ جاب‌ها.
هدیه/تمدید برایِ هر ادمین؛ توقفِ زمان و توقفِ جاب‌ها فقط سوپرادمین (ADMIN_TELEGRAM_IDS). هر عملِ گروهیِ پولی/زمانی
پیش‌نمایش + تاییدِ صریح دارد و ایدمپوتنت است (credit_batch_service)."""

from __future__ import annotations

import asyncio
import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.common.wizard_nav import with_nav
from app.bots.main_bot.filters import IsAdmin, IsSuperAdmin
from app.bots.main_bot.states import AdminTimeStates
from app.config import settings
from app.database.models import AuditEventType
from app.services import (
    admin_role_service,
    audit_log_service,
    credit_batch_service,
    job_gate_service,
    shop_owner_service,
    time_freeze_service,
)
from app.services.admin_settings_service import get_admin_settings
from app.utils.jalali import format_jalali_datetime
from app.utils.validators import fa_number, format_toman, parse_positive_int_text

logger = logging.getLogger(__name__)

BTN_ADMIN_TIME = "⏱ اعتبار و زمان"

router = Router(name="admin_time")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())
super_router = Router(name="admin_time_super")
super_router.message.filter(IsSuperAdmin())
super_router.callback_query.filter(IsSuperAdmin())

INTRO = "⏱ اعتبار و زمان — چه کاری انجام بدم؟"
STALE = "این مرحله منقضی شده؛ از «⏱ اعتبار و زمان» دوباره شروع کن."
INVALID_NUMBER = "یک عددِ معتبر در بازه‌یِ مجاز بفرست."
CANCELLED = "لغو شد؛ هیچ تغییری اعمال نشد."
SUPER_ONLY = "این بخش فقط برایِ سوپرادمین است."


def _is_super(user_id: int) -> bool:
    return user_id in settings.admin_ids


def menu_keyboard(is_super: bool) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="🎁 هدیه‌یِ اعتبار (گروهی)", callback_data="at_gift")],
        [InlineKeyboardButton(text="➕ تمدیدِ روزِ اشتراک (گروهی)", callback_data="at_ext")],
    ]
    if is_super:
        rows.append([InlineKeyboardButton(text="❄️ توقفِ زمان", callback_data="at_frz")])
        rows.append([InlineKeyboardButton(text="⏸ توقفِ جاب‌هایِ زمان‌بندی", callback_data="at_jobs")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def filter_keyboard(prefix: str) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=label, callback_data=f"{prefix}:{key}")] for key, label in credit_batch_service.FILTERS.items()]
    return with_nav(rows, cancel_cb="at_cancel")


def confirm_keyboard(batch_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ تایید و اجرا", callback_data=f"at_go:{batch_id}"),
                InlineKeyboardButton(text="❌ انصراف", callback_data=f"at_no:{batch_id}"),
            ]
        ]
    )


def _preview_text(batch) -> str:
    params = credit_batch_service.params_of(batch)
    target = credit_batch_service.FILTERS.get(params.get("filter", ""), "—")
    if batch.kind == "gift":
        amount = int(params.get("amount", 0))
        return (
            f"🎁 پیش‌نمایشِ هدیه\nگیرندگان: {fa_number(batch.target_count)} نفر ({target})\n"
            f"مبلغِ هر نفر: {format_toman(amount)}\nجمعِ کل: {format_toman(amount * batch.target_count)}\n\nاجرا بشه؟"
        )
    return (
        f"➕ پیش‌نمایشِ تمدید\nهدف: {fa_number(batch.target_count)} نفر ({target})\n"
        f"افزایش: {params.get('days')} روز به پایانِ اشتراک (اشتراکِ تمام‌شده یا بدونِ اشتراک رد می‌شه)\n\nاجرا بشه؟"
    )


@router.message(F.text == BTN_ADMIN_TIME)
async def open_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(INTRO, reply_markup=menu_keyboard(_is_super(message.from_user.id)))


@router.callback_query(F.data == "at_cancel")
async def cancel_any(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await callback.message.edit_text(CANCELLED)


# ── K1/K2: هدیه و تمدیدِ گروهی ─────────────────────────────────────────────
@router.callback_query(F.data.in_({"at_gift", "at_ext"}))
async def pick_filter(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    prefix = "at_gf" if callback.data == "at_gift" else "at_ef"
    await callback.message.answer("هدف کی باشه؟", reply_markup=filter_keyboard(prefix))


@router.callback_query(F.data.startswith(("at_gf:", "at_ef:")))
async def filter_chosen(callback: CallbackQuery, state: FSMContext) -> None:
    kind_prefix, flt = callback.data.split(":", 1)
    if flt not in credit_batch_service.FILTERS:
        await callback.answer(STALE, show_alert=True)
        return
    await callback.answer()
    if kind_prefix == "at_gf":
        await state.set_state(AdminTimeStates.waiting_gift_amount)
        await state.update_data(at_filter=flt)
        await callback.message.answer(
            f"مبلغِ هدیه برایِ هر نفر (تومان، بینِ {credit_batch_service.GIFT_MIN_TOMAN} و {credit_batch_service.GIFT_MAX_TOMAN}):"
        )
    else:
        await state.set_state(AdminTimeStates.waiting_extend_days)
        await state.update_data(at_filter=flt)
        await callback.message.answer(
            f"چند روز اضافه بشه؟ (بینِ {credit_batch_service.EXTEND_MIN_DAYS} و {credit_batch_service.EXTEND_MAX_DAYS})"
        )


async def _make_preview(message: Message, state: FSMContext, session: AsyncSession, **kwargs) -> None:
    data = await state.get_data()
    flt = data.get("at_filter")
    # P21-F: دامنهٔ ادمینِ عملیاتی رویِ عملیاتِ گروهی هم اثر دارد — مجموعهٔ هدف از همین‌جا
    # منجمد می‌شود، پس اجرایِ بعدی هم نمی‌تواند بیرونِ دامنه چیزی بسازد.
    allowed = await admin_role_service.scope_for(session, message.from_user.id)
    batch = (
        await credit_batch_service.create_batch(
            session, flt=flt, by=str(message.from_user.id), allowed_owner_ids=allowed, **kwargs
        )
        if flt
        else None
    )
    if batch is None:
        await message.answer("هدفی پیدا نشد یا مقدار نامعتبر است (حداکثر ۲۰۰۰ نفر در هر دسته).")
        return
    await state.clear()
    await message.answer(_preview_text(batch), reply_markup=confirm_keyboard(batch.batch_id))


@router.message(AdminTimeStates.waiting_gift_amount, F.text)
async def gift_amount(message: Message, state: FSMContext, session: AsyncSession) -> None:
    amount = parse_positive_int_text(message.text, credit_batch_service.GIFT_MIN_TOMAN, credit_batch_service.GIFT_MAX_TOMAN)
    if amount is None:
        await message.answer(INVALID_NUMBER)
        return
    await _make_preview(message, state, session, kind="gift", amount=amount)


@router.message(AdminTimeStates.waiting_extend_days, F.text)
async def extend_days(message: Message, state: FSMContext, session: AsyncSession) -> None:
    days = parse_positive_int_text(message.text, credit_batch_service.EXTEND_MIN_DAYS, credit_batch_service.EXTEND_MAX_DAYS)
    if days is None:
        await message.answer(INVALID_NUMBER)
        return
    await _make_preview(message, state, session, kind="extend", days=days)


@router.callback_query(F.data.startswith("at_no:"))
async def batch_cancel(callback: CallbackQuery, session: AsyncSession) -> None:
    await credit_batch_service.cancel(session, callback.data.split(":", 1)[1])
    await callback.answer()
    await callback.message.edit_text(CANCELLED)


@router.callback_query(F.data.startswith("at_go:"))
async def batch_go(callback: CallbackQuery, session: AsyncSession) -> None:
    batch_id = callback.data.split(":", 1)[1]
    result = await credit_batch_service.execute(session, batch_id, by=str(callback.from_user.id))
    if result.batch is None:
        await callback.answer(STALE, show_alert=True)
        return
    if not result.changed:
        await callback.answer("این عملیات قبلاً اجرا یا لغو شده.", show_alert=True)  # دابل‌تپ ⇒ بدونِ اثرِ دوم
        return
    batch = result.batch
    await audit_log_service.log(
        session,
        AuditEventType.ADMIN_BATCH_EXECUTED,
        actor_telegram_id=callback.from_user.id,
        details=f"batch={batch.batch_id} kind={batch.kind} applied={batch.applied_count} skipped={batch.skipped_count}",
    )
    params = credit_batch_service.params_of(batch)
    recipients = []
    for owner_id in result.applied_owner_ids:
        owner = await shop_owner_service.get_by_id(session, owner_id)
        if owner is not None:
            recipients.append(owner.telegram_id)
    await session.commit()
    await callback.answer()
    await callback.message.edit_text(f"✅ انجام شد: {fa_number(batch.applied_count)} نفر اعمال، {fa_number(batch.skipped_count)} نفر رد شد.")
    text = (
        f"🎁 {format_toman(int(params.get('amount', 0)))} اعتبارِ هدیه به کیف‌پولت اضافه شد."
        if batch.kind == "gift"
        else f"➕ اشتراکت {params.get('days')} روز تمدید شد."
    )
    for telegram_id in recipients:
        try:
            await callback.bot.send_message(telegram_id, text)
        except TelegramAPIError:
            logger.warning("اعلانِ عملیاتِ گروهی به یک فروشگاه‌دار نرسید.")
        await asyncio.sleep(0.03)


# ── K3: توقفِ زمان (سوپرادمین) ─────────────────────────────────────────────
def _freeze_keyboard(freezes) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=f"▶️ ازسرگیریِ #{f.id} ({'همه' if f.scope == 'all' else 'یک نفر'})", callback_data=f"at_fr:{f.id}")] for f in freezes]
    rows.append([InlineKeyboardButton(text="❄️ شروعِ توقفِ همه", callback_data="at_fs:all")])
    rows.append([InlineKeyboardButton(text="❄️ شروعِ توقفِ یک فروشگاه‌دار", callback_data="at_fs:owner")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _freeze_text(freezes) -> str:
    if not freezes:
        return "❄️ توقفِ زمان: الان هیچ توقفی فعال نیست."
    lines = ["❄️ توقف‌هایِ فعال:"]
    for f in freezes:
        who = "همه" if f.scope == "all" else f"فروشگاه‌دارِ {f.shop_owner_id}"
        lines.append(f"#{f.id} — {who} — از {format_jalali_datetime(f.started_at)} (ازسرگیریِ خودکار تا {fa_number(f.max_days)} روز)")
    return "\n".join(lines)


@router.callback_query(F.data.in_({"at_frz", "at_jobs"}) | F.data.startswith(("at_fs:", "at_fr:", "at_jt:", "at_jg")))
async def super_guard(callback: CallbackQuery) -> None:
    # ادمینِ عملیاتی که به این دکمه‌ها می‌رسه (اینجا فقط می‌رسه چون super_router اول include می‌شه و رد کرده)
    await callback.answer(SUPER_ONLY, show_alert=True)


@super_router.callback_query(F.data == "at_frz")
async def freeze_menu(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    freezes = await time_freeze_service.active_freezes(session)
    await callback.answer()
    await callback.message.answer(_freeze_text(freezes), reply_markup=_freeze_keyboard(freezes))


@super_router.callback_query(F.data.startswith("at_fs:"))
async def freeze_start_pick(callback: CallbackQuery, state: FSMContext) -> None:
    scope = callback.data.split(":", 1)[1]
    if scope not in ("all", "owner"):
        await callback.answer(STALE, show_alert=True)
        return
    await callback.answer()
    await state.update_data(fz_scope=scope, fz_owner=None)
    if scope == "owner":
        await state.set_state(AdminTimeStates.waiting_freeze_owner)
        await callback.message.answer("آیدیِ عددیِ تلگرامِ فروشگاه‌دار رو بفرست:")
    else:
        await state.set_state(AdminTimeStates.waiting_freeze_days)
        await callback.message.answer(f"حداکثر چند روز؟ (بینِ {time_freeze_service.MIN_DAYS} و {time_freeze_service.MAX_DAYS}؛ بعدش خودکار ازسرگرفته می‌شه)")


@super_router.message(AdminTimeStates.waiting_freeze_owner, F.text)
async def freeze_owner(message: Message, state: FSMContext, session: AsyncSession) -> None:
    telegram_id = parse_positive_int_text(message.text, 1, 10**13)
    owner = await shop_owner_service.get_by_telegram_id(session, telegram_id) if telegram_id else None
    if owner is None:
        await message.answer("فروشگاه‌داری با این آیدی پیدا نشد.")
        return
    await state.update_data(fz_owner=owner.id)
    await state.set_state(AdminTimeStates.waiting_freeze_days)
    await message.answer(f"حداکثر چند روز؟ (بینِ {time_freeze_service.MIN_DAYS} و {time_freeze_service.MAX_DAYS})")


@super_router.message(AdminTimeStates.waiting_freeze_days, F.text)
async def freeze_days(message: Message, state: FSMContext) -> None:
    days = parse_positive_int_text(message.text, time_freeze_service.MIN_DAYS, time_freeze_service.MAX_DAYS)
    if days is None:
        await message.answer(INVALID_NUMBER)
        return
    await state.update_data(fz_days=days)
    await state.set_state(AdminTimeStates.waiting_freeze_reason)
    await message.answer("دلیلِ توقف (یک خط) — یا «-» برایِ بدونِ دلیل:")


@super_router.message(AdminTimeStates.waiting_freeze_reason, F.text)
async def freeze_reason(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    await state.clear()
    reason = None if (message.text or "").strip() in ("-", "—") else (message.text or "").strip()
    freeze = await time_freeze_service.start(
        session, scope=data.get("fz_scope", ""), owner_id=data.get("fz_owner"), max_days=int(data.get("fz_days") or 0),
        reason=reason, by=str(message.from_user.id),
    )
    if freeze is None:
        await message.answer("شروع نشد: ورودی نامعتبر یا همین دامنه قبلاً فریز است.")
        return
    await audit_log_service.log(
        session, AuditEventType.TIME_FREEZE_CHANGED, actor_telegram_id=message.from_user.id,
        details=f"start id={freeze.id} scope={freeze.scope} owner={freeze.shop_owner_id} days={freeze.max_days}",
    )
    await message.answer(f"❄️ توقفِ زمان #{freeze.id} شروع شد. تا ازسرگیری هیچ انقضا/یادآوری/مهلتی برایِ مشمولین اجرا نمی‌شه.")


@super_router.callback_query(F.data.startswith("at_fr:"))
async def freeze_resume(callback: CallbackQuery, session: AsyncSession) -> None:
    raw = callback.data.split(":", 1)[1]
    freeze, changed = await time_freeze_service.resume(session, int(raw), by=str(callback.from_user.id)) if raw.isdecimal() else (None, False)
    if freeze is None:
        await callback.answer(STALE, show_alert=True)
        return
    if not changed:
        await callback.answer("این توقف قبلاً ازسرگرفته شده.", show_alert=True)  # دابل‌تپ ⇒ جابه‌جاییِ دوم نداریم
        return
    await audit_log_service.log(
        session, AuditEventType.TIME_FREEZE_CHANGED, actor_telegram_id=callback.from_user.id,
        details=f"resume id={freeze.id} shifted_seconds={freeze.shifted_seconds} affected={freeze.affected_count}",
    )
    await callback.answer()
    await callback.message.answer(
        f"▶️ توقفِ #{freeze.id} ازسرگرفته شد: {freeze.affected_count} تاریخِ انقضا به‌اندازه‌یِ {round((freeze.shifted_seconds or 0) / 3600, 1)} ساعت جلو رفت."
    )


# ── K4: توقفِ جاب‌ها (سوپرادمین) ───────────────────────────────────────────
def _jobs_keyboard(admin_settings) -> InlineKeyboardMarkup:
    groups = job_gate_service.paused_groups(admin_settings)
    rows = [
        [InlineKeyboardButton(text=("▶️ ازسرگیریِ همه" if admin_settings.jobs_paused else "⏸ توقفِ همه‌یِ جاب‌ها"), callback_data="at_jg")]
    ]
    for key, label in job_gate_service.GROUPS.items():
        mark = "⏸" if key in groups else "▶️"
        rows.append([InlineKeyboardButton(text=f"{mark} {label}", callback_data=f"at_jt:{key}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _jobs_text(admin_settings) -> str:
    state = "⏸ همه متوقف‌اند" if admin_settings.jobs_paused else "▶️ فعال (مگر گروه‌هایِ علامت‌خورده)"
    since = f"\nاز {format_jalali_datetime(admin_settings.jobs_paused_at)} توسطِ {admin_settings.jobs_paused_by}" if admin_settings.jobs_paused_at else ""
    return f"⏸ جاب‌هایِ زمان‌بندی: {state}{since}\n(جاب‌ها فقط رد می‌شن؛ چیزی پاک نمی‌شه.)"


@super_router.callback_query(F.data == "at_jobs")
async def jobs_menu(callback: CallbackQuery, session: AsyncSession) -> None:
    admin_settings = await get_admin_settings(session)
    await callback.answer()
    await callback.message.answer(_jobs_text(admin_settings), reply_markup=_jobs_keyboard(admin_settings))


@super_router.callback_query(F.data == "at_jg")
async def jobs_toggle_global(callback: CallbackQuery, session: AsyncSession) -> None:
    admin_settings = await get_admin_settings(session)
    await job_gate_service.set_global(session, not admin_settings.jobs_paused, str(callback.from_user.id))
    await audit_log_service.log(
        session, AuditEventType.JOBS_PAUSE_CHANGED, actor_telegram_id=callback.from_user.id, details=f"global_paused={admin_settings.jobs_paused}"
    )
    await callback.answer()
    await callback.message.edit_text(_jobs_text(admin_settings), reply_markup=_jobs_keyboard(admin_settings))


@super_router.callback_query(F.data.startswith("at_jt:"))
async def jobs_toggle_group(callback: CallbackQuery, session: AsyncSession) -> None:
    group = callback.data.split(":", 1)[1]
    now_paused = await job_gate_service.toggle_group(session, group, str(callback.from_user.id))
    if now_paused is None:
        await callback.answer(STALE, show_alert=True)
        return
    await audit_log_service.log(
        session, AuditEventType.JOBS_PAUSE_CHANGED, actor_telegram_id=callback.from_user.id, details=f"group={group} paused={now_paused}"
    )
    admin_settings = await get_admin_settings(session)
    await callback.answer()
    await callback.message.edit_text(_jobs_text(admin_settings), reply_markup=_jobs_keyboard(admin_settings))
