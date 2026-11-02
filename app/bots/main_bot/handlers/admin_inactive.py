"""پنلِ ادمین — دستهٔ «🧹 کاربرانِ غیرفعال» و حذفِ حسابِ فروشگاه‌دار (P22 · مشکلِ ۸).

چرا این صفحه: «چه کسانی یک ماه است سراغِ ربات نیامده‌اند؟» و «حسابِ فلانی را ببند» بدونِ
دسترسیِ مستقیم به دیتابیس پاسخ‌دادنی نبود. دو سطحِ حذف عمداً جداست:

- **غیرفعال‌کردنِ حساب (نرم)** پیش‌فرضِ همهٔ کلیک‌هاست: از فهرست‌ها، آمار و ورودِ کاربر بیرون
  می‌ماند، ولی ردیفِ حساب، پول، سفارش‌ها و دفتری که روزی لازم شود می‌ماند. برگشت‌پذیر است.
- **حذفِ قطعیِ داده** فقط برایِ حسابی که *ازپیش* غیرفعال شده، فقط با نوشتنِ عبارتِ
  «حذفِ قطعی»، و فقط برایِ سوپرادمین. باز هم پوسته و ردیف‌هایِ ممیزی می‌مانند اگر به آن‌ها
  ارجاعی باشد (زنجیرهٔ هشِ ممیزی پاک‌شدنی نیست) — صفحه دقیقاً همان را گزارش می‌دهد.

دامنه: ادمینِ عملیاتی فقط حساب‌هایِ دامنهٔ خودش را می‌بیند و فقط سوپرادمین می‌تواند حسابی
را ببندد/بازگرداند/پاک کند. هر سه عمل ممیزی می‌شوند.
"""

from __future__ import annotations

import datetime
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.main_bot import keyboards, texts
from app.bots.main_bot.filters import IsAdmin
from app.bots.main_bot.handlers.owner_common import safe_edit
from app.bots.main_bot.states import InactiveOwnerStates
from app.config import settings
from app.database.models import AuditEventType, ShopBot, ShopOwner
from app.services import admin_role_service, audit_log_service, owner_activity_service, shop_purge_service
from app.services.identity_service import display_name
from app.utils.jalali import format_jalali_datetime
from app.utils.validators import fa_number, format_toman

logger = logging.getLogger(__name__)

router = Router(name="admin_inactive")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


def _is_super(user_id: int) -> bool:
    return user_id in settings.admin_ids


def _since_label(item: owner_activity_service.InactiveOwner) -> str:
    if item.never_seen:
        return texts.INACTIVE_NO_HISTORY
    return texts.INACTIVE_DAYS_AGO.format(days=fa_number(item.since_days))


async def _scope(session: AsyncSession, user_id: int):
    return await admin_role_service.scope_for(session, user_id)


async def _list_payload(session: AsyncSession, user_id: int, days: int, page: int, *, deleted: bool = False):
    scope = await _scope(session, user_id)
    allowed = None if scope is None else sorted(scope)
    if deleted:
        query = select(ShopOwner).where(ShopOwner.is_deleted.is_(True)).order_by(ShopOwner.deleted_at.desc())
        if allowed is not None:
            query = query.where(ShopOwner.id.in_(allowed))
        owners = list((await session.execute(query.limit(owner_activity_service.LIST_LIMIT))).scalars().all())
        if not owners:
            return texts.INACTIVE_DELETED_NONE, keyboards.inactive_windows_keyboard(days, 0, 1)
        items = [
            (
                owner.id,
                display_name(owner),
                format_jalali_datetime(owner.deleted_at) if owner.deleted_at else texts.INACTIVE_NO_HISTORY,
            )
            for owner in owners
        ]
        intro = texts.INACTIVE_DELETED_INTRO.format(count=fa_number(len(owners)))
        return intro, keyboards.inactive_list_keyboard(items, days, 0, 1)

    rows = await owner_activity_service.list_inactive(session, days, allowed_owner_ids=allowed)
    total = await owner_activity_service.count_inactive(session, days, allowed_owner_ids=allowed)
    if not rows:
        return texts.INACTIVE_EMPTY + (texts.INACTIVE_SCOPED_NOTE if allowed is not None else ""), keyboards.inactive_windows_keyboard(
            days, 0, 1
        )
    items = [(item.owner.id, display_name(item.owner), _since_label(item)) for item in rows]
    intro = texts.INACTIVE_LIST_INTRO.format(
        days=fa_number(days), count=fa_number(total), scoped=texts.INACTIVE_SCOPED_NOTE if allowed is not None else ""
    )
    hidden = max(0, total - len(rows))
    if hidden:
        intro += "\n" + texts.INACTIVE_LIST_HIDDEN.format(limit=fa_number(owner_activity_service.LIST_LIMIT), hidden=fa_number(hidden))
    total_pages = max(1, (total + owner_activity_service.LIST_LIMIT - 1) // owner_activity_service.LIST_LIMIT)
    return intro, keyboards.inactive_list_keyboard(items, days, min(page, total_pages - 1), total_pages)


async def _owner_in_scope(session: AsyncSession, user_id: int, owner_id: int) -> ShopOwner | None:
    scope = await _scope(session, user_id)
    if not admin_role_service.is_in_scope(scope, owner_id):
        return None
    return await session.get(ShopOwner, owner_id)


@router.message(F.text == texts.INACTIVE_BUTTON)
async def open_inactive(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.update_data(inactive_days=owner_activity_service.DEFAULT_WINDOW, inactive_page=0)
    intro, markup = await _list_payload(session, message.from_user.id, owner_activity_service.DEFAULT_WINDOW, 0)
    await message.answer(intro, reply_markup=markup)


@router.callback_query(F.data.startswith("inact_win:"))
async def cb_window(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    raw = callback.data.split(":", 1)[1]
    days = int(raw) if raw.isdecimal() and int(raw) in owner_activity_service.INACTIVE_WINDOWS else owner_activity_service.DEFAULT_WINDOW
    await state.update_data(inactive_days=days, inactive_page=0)
    intro, markup = await _list_payload(session, callback.from_user.id, days, 0)
    await callback.answer()
    await safe_edit(callback, intro, markup)


@router.callback_query(F.data == "inact_deleted")
async def cb_deleted_list(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    days = (await state.get_data()).get("inactive_days") or owner_activity_service.DEFAULT_WINDOW
    intro, markup = await _list_payload(session, callback.from_user.id, days, 0, deleted=True)
    await callback.answer()
    await safe_edit(callback, intro, markup)


@router.callback_query(F.data.startswith("inact_page:"))
async def cb_page(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    days = data.get("inactive_days") or owner_activity_service.DEFAULT_WINDOW
    raw = callback.data.split(":", 1)[1]
    page = int(raw) if raw.isdecimal() else 0
    await state.update_data(inactive_page=page)
    intro, markup = await _list_payload(session, callback.from_user.id, days, page)
    await callback.answer()
    await safe_edit(callback, intro, markup)


@router.callback_query(F.data.startswith("inact_back:"))
async def cb_back(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    days = data.get("inactive_days") or owner_activity_service.DEFAULT_WINDOW
    raw = callback.data.split(":", 1)[1]
    page = int(raw) if raw.isdecimal() else 0
    await state.clear()
    intro, markup = await _list_payload(session, callback.from_user.id, days, page)
    await callback.answer()
    await safe_edit(callback, intro, markup)


def _days_since(moment: datetime.datetime | None) -> str:
    if moment is None:
        return texts.INACTIVE_NO_HISTORY
    days = max(0, int((datetime.datetime.now(datetime.timezone.utc) - moment).total_seconds() // 86_400))
    return texts.INACTIVE_DAYS_AGO.format(days=fa_number(days))


async def _bot_username(session: AsyncSession, owner_id: int) -> str | None:
    return (await session.execute(select(ShopBot.bot_username).where(ShopBot.shop_owner_id == owner_id))).scalar_one_or_none()


async def _detail_body(session: AsyncSession, owner: ShopOwner) -> str:
    return texts.inactive_detail_text(
        name=display_name(owner),
        bot_username=await _bot_username(session, owner.id),
        last_seen=format_jalali_datetime(owner.last_seen_at) if owner.last_seen_at else texts.INACTIVE_NO_HISTORY,
        since_label=_days_since(owner.last_seen_at),
        wallet=format_toman(owner.wallet_balance_toman),
        is_deleted=owner.is_deleted,
    )


@router.callback_query(F.data.startswith("inact_view:"))
async def cb_view(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    raw = callback.data.split(":", 1)[1]
    owner_id = int(raw) if raw.isdecimal() else -1
    owner = await _owner_in_scope(session, callback.from_user.id, owner_id)
    if owner is None:
        await callback.answer(texts.INACTIVE_STALE, show_alert=True)
        return
    page = (await state.get_data()).get("inactive_page") or 0
    await state.update_data(inactive_view=owner.id)
    markup = keyboards.inactive_detail_keyboard(owner.id, page, is_deleted=owner.is_deleted, is_super=_is_super(callback.from_user.id))
    await callback.answer()
    await safe_edit(callback, await _detail_body(session, owner), markup)


@router.callback_query(F.data.startswith("inact_deactivate:"))
async def cb_deactivate_ask(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _is_super(callback.from_user.id):
        await callback.answer(texts.INACTIVE_SUPER_ONLY, show_alert=True)
        return
    raw = callback.data.split(":", 1)[1]
    owner = await _owner_in_scope(session, callback.from_user.id, int(raw) if raw.isdecimal() else -1)
    if owner is None:
        await callback.answer(texts.INACTIVE_STALE, show_alert=True)
        return
    await callback.answer()
    await safe_edit(callback, texts.INACTIVE_DELETE_CONFIRM.format(name=display_name(owner)), keyboards.inactive_deactivate_confirm_keyboard(owner.id))


@router.callback_query(F.data.startswith("inact_deactivate_yes:"))
async def cb_deactivate(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not _is_super(callback.from_user.id):
        await callback.answer(texts.INACTIVE_SUPER_ONLY, show_alert=True)
        return
    raw = callback.data.split(":", 1)[1]
    owner = await _owner_in_scope(session, callback.from_user.id, int(raw) if raw.isdecimal() else -1)
    if owner is None or owner.is_deleted:
        await callback.answer(texts.INACTIVE_STALE, show_alert=True)
        return
    name = display_name(owner)
    days = (await state.get_data()).get("inactive_days") or owner_activity_service.DEFAULT_WINDOW
    await owner_activity_service.soft_delete(session, owner)
    await audit_log_service.log(
        session,
        AuditEventType.OWNER_DEACTIVATED,
        actor_telegram_id=callback.from_user.id,
        details=f"tg={owner.telegram_id} · owner={owner.id} · {name}",
    )
    await session.flush()
    await state.clear()
    intro, markup = await _list_payload(session, callback.from_user.id, days, 0)
    await callback.answer(texts.INACTIVE_DEACTIVATED_DONE.format(name=name))
    await safe_edit(callback, intro, markup)


@router.callback_query(F.data.startswith("inact_restore:"))
async def cb_restore_ask(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _is_super(callback.from_user.id):
        await callback.answer(texts.INACTIVE_SUPER_ONLY, show_alert=True)
        return
    raw = callback.data.split(":", 1)[1]
    owner = await _owner_in_scope(session, callback.from_user.id, int(raw) if raw.isdecimal() else -1)
    if owner is None or not owner.is_deleted:
        await callback.answer(texts.INACTIVE_STALE, show_alert=True)
        return
    await callback.answer()
    await safe_edit(callback, texts.INACTIVE_RESTORE_CONFIRM.format(name=display_name(owner)), keyboards.inactive_restore_confirm_keyboard(owner.id))


@router.callback_query(F.data.startswith("inact_restore_yes:"))
async def cb_restore(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not _is_super(callback.from_user.id):
        await callback.answer(texts.INACTIVE_SUPER_ONLY, show_alert=True)
        return
    raw = callback.data.split(":", 1)[1]
    owner = await _owner_in_scope(session, callback.from_user.id, int(raw) if raw.isdecimal() else -1)
    if owner is None or not owner.is_deleted:
        await callback.answer(texts.INACTIVE_STALE, show_alert=True)
        return
    name = display_name(owner)
    await owner_activity_service.restore(session, owner)
    await audit_log_service.log(
        session,
        AuditEventType.OWNER_RESTORED,
        actor_telegram_id=callback.from_user.id,
        details=f"tg={owner.telegram_id} · owner={owner.id} · {name}",
    )
    await session.flush()
    await state.clear()
    await callback.answer(texts.INACTIVE_RESTORED_DONE.format(name=name))
    await safe_edit(
        callback, await _detail_body(session, owner), keyboards.inactive_detail_keyboard(owner.id, 0, is_deleted=False, is_super=True)
    )


@router.callback_query(F.data.startswith("inact_purge:"))
async def cb_purge_ask(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """حذفِ قطعی: تاییدِ نوشتاری می‌خواهد، چون برگشت ندارد و محتوا را (سفارش/مشتری/مالی) می‌بُرد."""
    if not _is_super(callback.from_user.id):
        await callback.answer(texts.INACTIVE_SUPER_ONLY, show_alert=True)
        return
    raw = callback.data.split(":", 1)[1]
    owner = await _owner_in_scope(session, callback.from_user.id, int(raw) if raw.isdecimal() else -1)
    if owner is None:
        await callback.answer(texts.INACTIVE_STALE, show_alert=True)
        return
    if not owner.is_deleted:
        await callback.answer(texts.INACTIVE_NOT_DELETED_FIRST, show_alert=True)
        return
    blockers = await shop_purge_service.blocking_references(session, owner)
    kept = texts.INACTIVE_PURGE_SHELL_KEPT if blockers else texts.INACTIVE_PURGE_SHELL_REMOVED
    await state.set_state(InactiveOwnerStates.waiting_word)
    await state.update_data(inactive_purge_owner=owner.id)
    await callback.answer()
    await callback.message.answer(
        texts.INACTIVE_PURGE_ASK.format(name=display_name(owner), word=texts.INACTIVE_PURGE_WORD) + "\n" + kept,
    )


@router.message(InactiveOwnerStates.waiting_word, F.text)
async def cb_purge_word(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not _is_super(message.from_user.id):
        await state.clear()
        await message.answer(texts.INACTIVE_SUPER_ONLY)
        return
    data = await state.get_data()
    owner_id = int(data.get("inactive_purge_owner") or -1)
    owner = await _owner_in_scope(session, message.from_user.id, owner_id)
    if owner is None or not owner.is_deleted:
        await state.clear()
        await message.answer(texts.INACTIVE_STALE)
        return
    if (message.text or "").strip() != texts.INACTIVE_PURGE_WORD:
        await message.answer(texts.INACTIVE_PURGE_BAD_WORD.format(word=texts.INACTIVE_PURGE_WORD))
        return
    name = display_name(owner)
    try:
        result = await shop_purge_service.purge_owner(session, owner)
    except Exception as exc:  # noqa: BLE001 - دامنهٔ خطایِ حذفِ قطعی نامعلوم است؛ هیچ‌چیز را نصفه نگذار
        logger.exception("حذفِ قطعیِ حسابِ %s ناموفق بود", owner_id)
        # تراکنشِ ردِشده را همین‌جا واگرد می‌کنیم؛ اگر نکنیم commitِ DbSessionMiddleware رویِ
        # تراکنشِ شکسته خطایِ دوم می‌دهد و نصفهٔ حذف در انتظارِ commit می‌ماند.
        await session.rollback()
        await state.clear()
        await message.answer(texts.INACTIVE_PURGE_FAILED.format(error=type(exc).__name__))
        return
    await audit_log_service.log(
        session,
        AuditEventType.OWNER_PURGED,
        actor_telegram_id=message.from_user.id,
        details=(
            f"tg={owner.telegram_id} · owner={owner_id} · {name} · ردیف‌ها={result['removed'].get('total', 0)} · "
            f"پوسته={'رفت' if result['shell_removed'] else 'ماند'} · مانع‌ها={result['blockers'] or '—'}"
        ),
    )
    await session.flush()
    await state.clear()
    await message.answer(
        texts.INACTIVE_PURGE_DONE.format(
            name=name,
            count=fa_number(int(result["removed"].get("total", 0))),
            tail=texts.INACTIVE_PURGE_SHELL_REMOVED if result["shell_removed"] else texts.INACTIVE_PURGE_SHELL_KEPT,
        )
    )
