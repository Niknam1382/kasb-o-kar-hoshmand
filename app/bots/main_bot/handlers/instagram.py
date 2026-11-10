"""P49-الف — صفحهٔ «🟣 اینستاگرام» در پنلِ فروشگاه‌دار.

چهار چیز را یک‌جا نگه می‌دارد تا کانالِ سوم مثلِ دو کانالِ قبلی از یکِ مسیر اداره شود:

• وضعیتِ اتصال (وصل است با @نامِ کاربری، یا «متصل نشده» + چک‌لیستِ چهارمرحله‌ایِ همان‌جایی که
  فروشگاه‌دار باید خودش انجام دهد). قاعدهٔ ۲۴ ساعت و «پرداخت با همان مسیرِ قبلی» هم در همین
  صفحه نوشته می‌شود؛ راهنمایِ بلندِ تصویری در P49-پ می‌آید.
• لینکِ اتصال از متا ساخته می‌شود؛ اگر ادمین App ID/Secret را نگذاشته باشد یا آدرسِ عمومیِ
  HTTPSِ سرویس وارد نشده باشد، به‌جایِ لینکِ بی‌اعتبار یکِ پیامِ صادقانه می‌بیند (قاعدهٔ B11).
• هر فعلِ این صفحه اول مالکیتِ فروشگاه را با `require_shop_bot_cb` چک می‌کند ⇒ کال‌بکِ دستکاری‌شده
  یا فروشگاهِ دیگری به هیچ ردیفی نمی‌رسد.
• هیچ رازی در این صفحه نیست: نه توکنِ اکانت، نه App Secret. فقط `last_error` (که خودش
  ماسک‌شده تولید می‌شود) نمایش داده می‌شود.
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.main_bot import keyboards, texts
from app.bots.main_bot.handlers.owner_common import panel_keyboard, require_shop_bot, require_shop_bot_cb, safe_edit
from app.bots.main_bot.states import InstagramStates
from app.database.models import ShopBot
from app.services import instagram_service, shop_bot_service, shop_owner_service
from app.services.admin_settings_service import get_admin_settings
from app.utils.text_limits import clip

logger = logging.getLogger(__name__)

router = Router(name="main_instagram")

GREETING_LIMIT = 500  # سقفِ خودِ محصول (متنِ خوشآمد کوتاه می‌ماند؛ اینستاگرام هم ۱۰۰۰ را بیشتر نمی‌گیرد)
CLEAR_WORDS = frozenset({"خالی", "پاک کن", "پاکش کن", "-"})


async def _current_owner(message_or_callback, session: AsyncSession):
    return await shop_owner_service.get_by_telegram_id(session, message_or_callback.from_user.id)


async def _screen(target, shop_bot: ShopBot, session: AsyncSession) -> None:
    """متن + کیبوردِ صفحه؛ برایِ CallbackQuery ویرایش می‌شود و برایِ Message تازه فرستاده می‌شود.

    درِ سراسری *این‌جا هم* چک می‌شود (نه فقط در دکمهٔ منو): پیامِ کهنهٔ «🟣 اینستاگرام» هنوز
    کال‌بک‌هایِ `ig_*` را دارد و ادمین می‌تواند کانال را وسطِ کار خاموش کرده باشد.
    """
    admin_settings = await get_admin_settings(session)
    if not instagram_service.enabled(admin_settings):
        if isinstance(target, CallbackQuery):
            await target.answer(texts.INSTAGRAM_TOGGLED_OFF, show_alert=True)
        else:
            await target.answer(texts.INSTAGRAM_TOGGLED_OFF)
        return
    account = await instagram_service.account_for_shop(session, shop_bot.id)
    text = texts.instagram_status_text(account, admin_settings)
    markup = keyboards.instagram_panel_keyboard(account)
    if isinstance(target, CallbackQuery):
        await safe_edit(target, text, markup)
    else:
        await target.answer(text, reply_markup=markup)


@router.message(F.text == texts.INSTAGRAM_BUTTON)
async def open_instagram_panel(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    shop_bot = await require_shop_bot(message, session)
    if shop_bot is None:
        return
    admin_settings = await get_admin_settings(session)
    if not instagram_service.enabled(admin_settings):
        await message.answer(texts.INSTAGRAM_TOGGLED_OFF)
        return
    await _screen(message, shop_bot, session)


# P49-ب: چهار کال‌بکِ یک‌شکل برایِ دو سوییچِ کامنت (سوییچِ دایرکت هندلرِ اختصاصیِ خودش را دارد).
_FLAG_ACTIONS: dict[str, tuple[str, bool, str]] = {
    "ig_comments_on": ("auto_reply_comments", True, "💬 پاسخِ خودکار به کامنت‌ها روشن شد."),
    "ig_comments_off": ("auto_reply_comments", False, "💬 پاسخِ خودکار به کامنت‌ها خاموش شد."),
    "ig_private_on": ("private_reply_enabled", True, "🔒 پاسخِ خصوصی به کامنت‌کننده روشن شد."),
    "ig_private_off": ("private_reply_enabled", False, "🔒 پاسخِ خصوصی خاموش شد (فقط جوابِ عمومی زیرِ کامنت)."),
}


@router.callback_query(F.data.in_(set(_FLAG_ACTIONS)))
async def cb_toggle_flag(callback: CallbackQuery, session: AsyncSession) -> None:
    """روشن/خاموش‌کردنِ یکِ سوییچِ کانال برایِ همین فروشگاه (مالکیت با require_shop_bot_cb)."""
    field, value, toast = _FLAG_ACTIONS[callback.data]
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        await callback.answer()
        return
    account = await instagram_service.account_for_shop(session, shop_bot.id)
    if account is None:
        await callback.answer(texts.INSTAGRAM_NOT_CONNECTED, show_alert=True)
        return
    setattr(account, field, value)
    await session.flush()
    await callback.answer(toast)
    await _screen(callback, shop_bot, session)


@router.callback_query(F.data == "ig_back")
async def cb_back(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    owner = await _current_owner(callback, session)
    await callback.message.answer(
        texts.PANEL_WELCOME_BACK,
        reply_markup=await panel_keyboard(session, owner.business_mode if owner else None),
    )


@router.callback_query(F.data == "ig_connect")
async def cb_connect(callback: CallbackQuery, session: AsyncSession) -> None:
    """لینکِ «Instagram Login for Business» — هیچ رازی داخلش نیست و فقط برایِ خودِ همین فروشگاه است."""
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    admin_settings = await get_admin_settings(session)
    if not instagram_service.enabled(admin_settings):
        await callback.answer(texts.INSTAGRAM_TOGGLED_OFF, show_alert=True)
        return
    redirect = instagram_service.redirect_uri()
    if not instagram_service.configured(admin_settings):
        await callback.answer(texts.INSTAGRAM_NO_APP_ID, show_alert=True)
        return
    if redirect is None:
        await callback.answer(texts.INSTAGRAM_NO_PUBLIC_URL, show_alert=True)
        return
    link = instagram_service.build_oauth_url(admin_settings.instagram_app_id, redirect, instagram_service.make_state(shop_bot.id))
    await callback.answer()
    await callback.message.answer(texts.instagram_connect_page_link(link))


@router.callback_query(F.data == "ig_reply_on")
async def cb_reply_on(callback: CallbackQuery, session: AsyncSession) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    account = await instagram_service.account_for_shop(session, shop_bot.id)
    if account is None:
        await callback.answer(texts.INSTAGRAM_NOT_CONNECTED, show_alert=True)
        return
    account.auto_reply_dm = True
    await session.flush()
    await callback.answer(texts.INSTAGRAM_REPLY_ON_TOAST)
    await _screen(callback, shop_bot, session)


@router.callback_query(F.data == "ig_reply_off")
async def cb_reply_off(callback: CallbackQuery, session: AsyncSession) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    account = await instagram_service.account_for_shop(session, shop_bot.id)
    if account is None:
        await callback.answer(texts.INSTAGRAM_NOT_CONNECTED, show_alert=True)
        return
    account.auto_reply_dm = False
    await session.flush()
    await callback.answer(texts.INSTAGRAM_REPLY_OFF_TOAST)
    await _screen(callback, shop_bot, session)


@router.callback_query(F.data == "ig_greeting")
async def cb_greeting(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    account = await instagram_service.account_for_shop(session, shop_bot.id)
    if account is None:
        await callback.answer(texts.INSTAGRAM_NOT_CONNECTED, show_alert=True)
        return
    await state.clear()
    await state.set_state(InstagramStates.waiting_greeting)
    await callback.answer()
    current = (account.greeting_text or "").strip()
    await callback.message.answer(
        texts.INSTAGRAM_GREETING_ASK if not current else f"{texts.INSTAGRAM_GREETING_ASK}\n\nمتنِ فعلی:\n{current}"
    )


@router.message(InstagramStates.waiting_greeting, F.text)
async def save_greeting(message: Message, state: FSMContext, session: AsyncSession) -> None:
    owner = await _current_owner(message, session)
    shop_bot = await shop_bot_service.get_by_owner(session, owner) if owner else None
    if shop_bot is None:
        await state.clear()
        await message.answer(texts.SHOP_BOT_NOT_SET_UP)
        return
    account = await instagram_service.account_for_shop(session, shop_bot.id)
    await state.clear()
    if account is None:
        await message.answer(texts.INSTAGRAM_NOT_CONNECTED)
        return
    raw = (message.text or "").strip()
    account.greeting_text = None if raw in CLEAR_WORDS else clip(raw, GREETING_LIMIT)
    await session.flush()
    await message.answer(texts.INSTAGRAM_GREETING_CLEARED if account.greeting_text is None else texts.INSTAGRAM_GREETING_SAVED)
    await _screen(message, shop_bot, session)


@router.callback_query(F.data == "ig_test")
async def cb_test(callback: CallbackQuery, session: AsyncSession) -> None:
    """یکِ ارسالِ واقعی به متا، تا فروشگاه‌دار ببیند توکن و تنظیمات کار می‌کنند یا نه.

    گیرنده، شناسهٔ خودِ اکانتِ اتصال‌داده‌شده است (همان عددی که رویدادها با آن می‌رسند)؛ متا
    ممکن است آن را رد کند — دلیلش همان‌جا در «آخرین خطا» دیدنی می‌شود، پس پیامِ صادقانه می‌دهیم.
    """
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    account = await instagram_service.account_for_shop(session, shop_bot.id)
    if account is None:
        await callback.answer(texts.INSTAGRAM_NOT_CONNECTED, show_alert=True)
        return
    body = (account.greeting_text or "").strip()
    if not body:
        await callback.answer(texts.INSTAGRAM_GREETING_MISSING, show_alert=True)
        return
    ok = await instagram_service.send_message(session, account, account.ig_account_id, body, reply_type="human_agent")
    await session.commit()
    await callback.answer(texts.INSTAGRAM_TEST_SENT if ok else texts.INSTAGRAM_TEST_REJECTED, show_alert=True)
    await _screen(callback, shop_bot, session)


@router.callback_query(F.data == "ig_unbind")
async def cb_unbind(callback: CallbackQuery, session: AsyncSession) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    account = await instagram_service.account_for_shop(session, shop_bot.id)
    if account is None:
        await callback.answer(texts.INSTAGRAM_NOT_CONNECTED, show_alert=True)
        return
    await instagram_service.unbind(session, account)
    await callback.answer(texts.INSTAGRAM_UNBOUND_TOAST)
    await _screen(callback, shop_bot, session)


@router.callback_query(F.data == "ig_guide")
async def cb_guide(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    await callback.message.answer(texts.INSTAGRAM_GUIDE_INTRO)
