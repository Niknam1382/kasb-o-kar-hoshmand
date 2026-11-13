"""پنلِ ادمین — «🧾 پروندهٔ کاملِ کاربر» (پ۶۷ · نیمهٔ بازِ موردِ ۲۷/۴۱).

چرا: اطلاعاتِ یکِ فروشگاه‌دار در چهار صفحه پخش بود (مدیریتِ فروشگاه‌دارها / مصرفِ کاربران / کاربرانِ
غیرفعال / اعتبار و زمان) و ادمین برایِ یکِ تصمیم مجبور بود آن‌ها را در ذهن جمع کند. این صفحه همان‌ها
را در یکِ نما می‌آورد و **فعل‌ها را از نو نمی‌سازد**: تعلیق، هدیهٔ اعتبار، اصلاحِ کیف‌پول، غیرفعال‌کردن،
بازگرداندن و حذفِ قطعی همه همان کال‌بک‌هایِ موجودند که چکِ دامنه و ممیزیِ خودشان را دارند.

تنها فعلِ تازه «➕ تمدیدِ روزِ اشتراک» است: تا پیشِ این تمدید فقط *گروهی* وجود داشت
(`admin_time.py` · K2) و برایِ تمدیدِ یکِ نفر باید دسته‌ای می‌ساختی. همان `extend_by_days` با همان
سقف‌هایِ `credit_batch_service` صدا زده می‌شود و یکِ رویدادِ ممیزیِ تازه ثبت می‌کند.

دامنه: ادمینِ عملیاتی فقط حسابِ دامنهٔ خودش را می‌بیند (`admin_role_service.scope_for`) — همان
قراردادِ «🧹 کاربرانِ غیرفعال». فعل‌هایِ سوپرادمینی (حذفِ قطعی، بازگرداندن) برایِ ادمینِ عملیاتی
نشان داده *نمی‌شوند*؛ خودِ آن هندلرها هم `INACTIVE_SUPER_ONLY` را می‌دهند، پس این فقط حذفِ شلوغی است.
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.main_bot import keyboards, texts
from app.bots.main_bot.filters import IsAdmin
from app.bots.main_bot.states import OwnerDossierStates
from app.config import settings
from app.database.models import AuditEventType, ShopOwner
from app.services import (
    admin_role_service,
    audit_log_service,
    credit_batch_service,
    owner_dossier_service,
    shop_bot_service,
    subscription_service,
)
from app.utils.validators import fa_number, parse_positive_int_text

logger = logging.getLogger(__name__)

router = Router(name="admin_dossier")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

_MAX_ID = 10**12


def _is_super(user_id: int) -> bool:
    return user_id in settings.admin_ids


def _owner_id(data: str | None, prefix: str) -> int | None:
    raw = (data or "")[len(prefix) :]
    if not raw.isascii() or not raw.isdecimal():
        return None
    value = int(raw)
    return value if 0 < value <= _MAX_ID else None


async def _scoped_owner(session: AsyncSession, user_id: int, owner_id: int | None) -> ShopOwner | None:
    if owner_id is None:
        return None
    scope = await admin_role_service.scope_for(session, user_id)
    if not admin_role_service.is_in_scope(scope, owner_id):
        return None
    return await session.get(ShopOwner, owner_id)


async def _render(message: Message, session: AsyncSession, owner: ShopOwner, actor_id: int) -> None:
    data = await owner_dossier_service.build(session, owner.id)
    if data is None:
        await message.edit_text(texts.OWNER_DOSSIER_NOT_FOUND)
        return
    bot = data.get("shop_bot")
    recent = await owner_dossier_service.recent_audit(session, bot["id"] if bot else None)
    labels = [(texts.audit_event_label(event), when) for event, when in recent]
    await message.edit_text(
        texts.owner_dossier_text(data, labels),
        reply_markup=keyboards.owner_dossier_keyboard(owner.id, data, is_super=_is_super(actor_id)),
    )


@router.callback_query(F.data.startswith("owner_dossier:"))
async def cb_dossier(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    owner = await _scoped_owner(session, callback.from_user.id, _owner_id(callback.data, "owner_dossier:"))
    if owner is None:
        await callback.answer(texts.OWNER_DOSSIER_STALE, show_alert=True)
        return
    await callback.answer()
    await _render(callback.message, session, owner, callback.from_user.id)


@router.callback_query(F.data.startswith("owner_dossier_refresh:"))
async def cb_refresh(callback: CallbackQuery, session: AsyncSession) -> None:
    owner = await _scoped_owner(session, callback.from_user.id, _owner_id(callback.data, "owner_dossier_refresh:"))
    if owner is None:
        await callback.answer(texts.OWNER_DOSSIER_STALE, show_alert=True)
        return
    await callback.answer()
    await _render(callback.message, session, owner, callback.from_user.id)


@router.callback_query(F.data.startswith("owner_dossier_extend:"))
async def cb_extend_ask(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    owner = await _scoped_owner(session, callback.from_user.id, _owner_id(callback.data, "owner_dossier_extend:"))
    if owner is None:
        await callback.answer(texts.OWNER_DOSSIER_STALE, show_alert=True)
        return
    if owner.is_deleted:
        await callback.answer(texts.OWNER_DOSSIER_EXTEND_DELETED, show_alert=True)
        return
    await state.set_state(OwnerDossierStates.waiting_days)
    await state.update_data(dossier_owner=owner.id)
    await callback.answer()
    await callback.message.answer(
        texts.OWNER_DOSSIER_EXTEND_ASK.format(name=owner.first_name or f"@{owner.telegram_id}")
        + f"\n(بینِ {fa_number(credit_batch_service.EXTEND_MIN_DAYS)} تا {fa_number(credit_batch_service.EXTEND_MAX_DAYS)} روز)"
    )


@router.message(OwnerDossierStates.waiting_days, F.text, ~F.text.startswith("/"))
async def cb_extend_days(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    owner = await _scoped_owner(session, message.from_user.id, int(data.get("dossier_owner") or -1))
    if owner is None or owner.is_deleted:
        await state.clear()
        await message.answer(texts.OWNER_DOSSIER_STALE)
        return
    days = parse_positive_int_text(message.text, credit_batch_service.EXTEND_MIN_DAYS, credit_batch_service.EXTEND_MAX_DAYS)
    if days is None:
        await message.answer(texts.OWNER_DOSSIER_EXTEND_BAD_DAYS)
        return
    subscription = await subscription_service.extend_by_days(session, owner.id, days)
    await session.flush()
    bot = await shop_bot_service.get_by_owner(session, owner)
    await audit_log_service.log(
        session,
        AuditEventType.SUBSCRIPTION_EXTENDED,
        shop_bot_id=bot.id if bot is not None else None,
        actor_telegram_id=message.from_user.id,
        details=(
            f"تمدیدِ {fa_number(days)} روزِ اشتراک برایِ حسابِ {owner.id} "
            f"تا {subscription.end_date.isoformat()[:10]} (از پروندهٔ کاملِ کاربر)"
        ),
    )
    await session.commit()
    await state.clear()
    await message.answer(texts.OWNER_DOSSIER_EXTEND_DONE.format(days=fa_number(days)))
