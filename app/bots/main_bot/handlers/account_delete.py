"""پنلِ فروشگاه‌دار — «🗑 حذفِ حسابِ من» (پ۶۵ · نیمهٔ دومِ موردِ ۲۷/۴۱).

چرا این صفحه: تا پ۶۵ فقط ادمین می‌توانست حسابی را ببندد (`admin_inactive.py`)؛ مالکِ محصول خواست
خودِ فروشگاه‌دار هم بتواند. دو سطحِ حذف عمداً از هم دورند — ادمین «حذفِ قطعیِ داده» می‌کند
(همه‌چیز، از جمله دفترِ مالی)، کاربر «بستنِ حساب + بی‌نام‌سازیِ هویت» (اسنادِ مالیِ خودش و پلتفرم
می‌مانند؛ دلیلش در سرِصفحهٔ `account_deletion_service` است).

سه چیزی که این فایل نگه می‌دارد:
• تاییدِ *دومرحله‌ای*: صفحهٔ پیش‌نمایش ⇒ دکمه ⇒ نوشتنِ عبارتِ «حذفِ حساب». هیچ‌کدام با یکِ تپ انجام
  نمی‌شود و میانِ دو مرحله هیچ ردیفی عوض نمی‌شود.
• گیتِ پول: با موجودیِ یا کمیسیونِ قفل‌شده هیچ ردیفی عوض نمی‌شود؛ سرویسِ کلیدِ مانع را می‌دهد و
  اینجا فقط توضیح می‌دهد.
• دروازهٔ کانالِ اجباری عمداً رویِ این روتر نیست: بستنِ حساب نباید مشروطِ عضویتِ کانالِ بازاریابی باشد.
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.main_bot import keyboards, texts
from app.bots.main_bot.handlers.owner_common import safe_edit
from app.bots.main_bot.states import AccountDeletionStates
from app.database.models import ShopOwner
from app.services import account_deletion_service, shop_owner_service
from app.utils.validators import fa_number, format_toman

logger = logging.getLogger(__name__)

router = Router(name="account_delete")


async def _owner(session: AsyncSession, user_id: int) -> ShopOwner | None:
    owner = await shop_owner_service.get_by_telegram_id(session, user_id)
    return owner if owner is not None and owner.registration_completed else None


def _blocked_text(data: account_deletion_service.DeletionPreview) -> str:
    lines = []
    if account_deletion_service.BLOCK_WALLET in data.blockers:
        lines.append(texts.ACCOUNT_DELETE_BLOCKED_WALLET.format(wallet=format_toman(data.wallet_toman)))
    if account_deletion_service.BLOCK_RESERVED in data.blockers:
        lines.append(texts.ACCOUNT_DELETE_BLOCKED_RESERVED.format(reserved=format_toman(data.reserved_toman)))
    return "\n\n".join(lines)


@router.callback_query(F.data == "acc_delete")
async def cb_preview(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    owner = await _owner(session, callback.from_user.id)
    if owner is None:
        await callback.answer(texts.ACCOUNT_DELETE_NOT_REGISTERED, show_alert=True)
        return
    if owner.is_deleted:
        await callback.answer(texts.ACCOUNT_DELETE_ALREADY, show_alert=True)
        return
    data = await account_deletion_service.preview(session, owner)
    await callback.answer()
    if data.blocked:
        await safe_edit(callback, _blocked_text(data), keyboards.account_delete_blocked_keyboard())
        return
    await safe_edit(
        callback,
        texts.account_delete_preview_text(
            customers=data.customers,
            messages=data.messages,
            addresses=data.addresses,
            documents=data.orders,
            open_orders=data.open_orders,
            bot_count=data.bot_count,
            instagram_accounts=data.instagram_accounts,
            bale_bots=data.bale_bots,
            pending_messages=data.pending_notifications + data.pending_broadcasts,
        ),
        keyboards.account_delete_keyboard(),
    )


@router.callback_query(F.data == "acc_delete_yes")
async def cb_confirm(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """تاییدِ نخست: شرطِ پول *همین‌جا* دوباره سنجیده می‌شود (میانِ دو صفحه ممکن است عوض شده باشد)."""
    owner = await _owner(session, callback.from_user.id)
    if owner is None or owner.is_deleted:
        await callback.answer(texts.ACCOUNT_DELETE_STALE, show_alert=True)
        return
    data = await account_deletion_service.preview(session, owner)
    if data.blocked:
        await callback.answer()
        await safe_edit(callback, _blocked_text(data), keyboards.account_delete_blocked_keyboard())
        return
    await state.set_state(AccountDeletionStates.waiting_word)
    await state.update_data(account_delete_owner=owner.id)
    await callback.answer()
    await callback.message.answer(texts.ACCOUNT_DELETE_ASK.format(word=texts.ACCOUNT_DELETE_WORD))


@router.message(AccountDeletionStates.waiting_word, F.text, ~F.text.startswith("/"))
async def cb_word(message: Message, state: FSMContext, session: AsyncSession, bot_manager=None) -> None:
    """`/cancel` عمداً از این هندلر بیرون است تا هندلرِ مرکزیِ لغو (پنل) حالت را پاک کند."""
    if (message.text or "").strip() != texts.ACCOUNT_DELETE_WORD:
        await message.answer(texts.ACCOUNT_DELETE_BAD_WORD.format(word=texts.ACCOUNT_DELETE_WORD))
        return
    owner = await _owner(session, message.from_user.id)
    data = await state.get_data()
    if owner is None or owner.is_deleted or int(data.get("account_delete_owner") or -1) != owner.id:
        await state.clear()
        await message.answer(texts.ACCOUNT_DELETE_STALE)
        return

    try:
        result = await account_deletion_service.delete_account(session, owner, actor_telegram_id=message.from_user.id)
    except Exception as exc:  # noqa: BLE001 - دامنهٔ خطایِ حذف نامعلوم است؛ نصفه‌کاره نگذار
        logger.exception("حذفِ حسابِ خودخدمت ناموفق بود (owner=%s)", owner.id)
        await session.rollback()
        await state.clear()
        await message.answer(texts.ACCOUNT_DELETE_FAILED.format(error=type(exc).__name__))
        return
    if result["blocked"]:
        # مسابقهٔ نادر: میانِ تاییدِ نخست و نوشتنِ واژه، شارژِ تازه‌ای آمده است ⇒ بی‌اثر می‌ماند.
        await state.clear()
        await message.answer(_blocked_text(result["preview"]))
        return

    # قاعدهٔ ۷: اول قطعی‌کردنِ حذف (که دروازهٔ ورود را می‌بندد)، بعدِ کارِ شبکه برایِ خاموش‌کردنِ ربات.
    await session.commit()
    await state.clear()
    await _stop_live_bots(bot_manager, result["bot_ids"])

    erased = result["erased"]
    await message.answer(
        texts.ACCOUNT_DELETE_DONE.format(
            summary=texts.ACCOUNT_DELETE_DONE_SUMMARY.format(
                erased=fa_number(sum(int(value) for value in erased.values())),
                customers=fa_number(erased.get("customers_anonymized", 0)),
                documents=fa_number(result["preview"].orders),
            )
        )
    )


async def _stop_live_bots(bot_manager, bot_ids: list[int]) -> None:
    """رباتِ زنده را از سرویس بیرون می‌اندازد؛ پ۲۲ این کار را نمی‌کرد و ربات تا ری‌استارت زنده می‌ماند."""
    if bot_manager is None:
        return
    for bot_id in bot_ids:
        # هر دو «بی‌اثر»ند اگر شناسه در این پروسه ثبت نشده باشد، و هیچ داده‌ای را در دیتابیس عوض
        # نمی‌کنند (`disable_in_db=False`): وضعیتِ نهاییِ حساب کارِ سرویسِ حذف است، نه این‌جا.
        try:
            await bot_manager.unregister(bot_id, disable_in_db=False)
        except Exception:  # noqa: BLE001 - حذفِ حساب نباید به‌خاطرِ بستنِ یکِ اتصالِ شبکه شکست بخورد
            logger.exception("خاموش‌کردنِ رباتِ %s پس ازِ حذفِ حساب ناموفق بود", bot_id)
        try:
            await bot_manager.unregister_bale(bot_id)
        except Exception:  # noqa: BLE001
            logger.exception("خاموش‌کردنِ رباتِ بله‌یِ %s پس ازِ حذفِ حساب ناموفق بود", bot_id)
