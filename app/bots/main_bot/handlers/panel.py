from __future__ import annotations

import asyncio
import logging
import secrets

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.main_bot import keyboards, texts
from app.bots.shop_bot import texts as shop_texts
from app.bots.main_bot.states import (
    AiInstructionsStates,
    BaleProviderTokenStates,
    BaleShopBotStates,
    ChannelKnowledgeStates,
    CheckoutQuestionsStates,
    CustomerBroadcastStates,
    PaymentStates,
    PreviewStates,
    ShopBotTokenStates,
)
from app.config import settings
from app.database.models import Customer, DiscountCode, OrderConsultation, PaymentPurpose, PaymentStatus, TenantMode
from app.services import (
    admin_role_service,
    ai_context,
    ai_pool_service,
    ai_service,
    bale_bot_service,
    bale_credentials_service,
    bale_service,
    bot_branding_service,
    channel_knowledge_service,
    customer_service,
    digital_service,
    discount_service,
    excel_export_service,
    knowledge_service,
    order_service,
    order_payment_service,
    order_transition_service,
    payment_service,
    payment_settings_service,
    prompt_defaults,
    product_service,
    referral_service,
    shop_bot_service,
    shop_owner_service,
    shop_prefs_service,
    stats_service,
    wallet_service,
    zarinpal_service,
)
from app.services.admin_settings_service import get_admin_settings
from app.utils.encryption import decrypt_token

logger = logging.getLogger(__name__)

router = Router(name="panel")


def _chat_id_arg(channel_id: str) -> str | int:
    stripped = channel_id.strip()
    if stripped.lstrip("-").isdecimal():
        return int(stripped)
    return stripped


async def _current_owner(message_or_callback, session: AsyncSession):
    return await shop_owner_service.get_by_telegram_id(session, message_or_callback.from_user.id)


async def _get_discount_or_none(session: AsyncSession, discount_code_id: int | None) -> DiscountCode | None:
    if discount_code_id is None:
        return None
    return await session.get(DiscountCode, discount_code_id)


# =============================================================================
# لغو عمومی (این‌جلسه — بخشی از رفع گیرکردن FSM)
# =============================================================================
@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    owner = await _current_owner(message, session)
    is_super_admin = message.from_user.id in settings.admin_ids
    is_admin = is_super_admin or await admin_role_service.is_operator(session, message.from_user.id)
    if is_admin:
        keyboard = keyboards.admin_panel_keyboard(is_super_admin)
    else:
        keyboard = keyboards.shop_owner_panel_keyboard(owner.business_mode if owner else None, bale_visible=await bale_bot_service.visible_for(session))
    await message.answer(texts.OPERATION_CANCELLED, reply_markup=keyboard)


# =============================================================================
# ثبت/ویرایش توکن ربات فروشگاهی
# =============================================================================
@router.message(F.text == "🔑 ثبت/ویرایش توکن ربات")
async def open_shop_bot_token(message: Message, state: FSMContext) -> None:
    await state.set_state(ShopBotTokenStates.waiting_token)
    await message.answer(texts.ASK_SHOP_BOT_TOKEN)


@router.message(ShopBotTokenStates.waiting_token, F.text)
async def save_shop_bot_token(message: Message, state: FSMContext, session: AsyncSession, bot_manager) -> None:
    raw_token = message.text.strip()

    try:
        temp_bot = Bot(token=raw_token)
        me = await temp_bot.get_me()
        await temp_bot.session.close()
    except Exception:
        logger.info("توکن نامعتبر برای ربات فروشگاهی وارد شد.")
        await message.answer(texts.INVALID_BOT_TOKEN)
        return

    owner = await _current_owner(message, session)
    existing = await shop_bot_service.get_by_bot_telegram_id(session, me.id)
    if existing is not None and existing.shop_owner_id != owner.id:
        await message.answer(texts.BOT_TOKEN_ALREADY_USED)
        return

    shop_bot = await shop_bot_service.upsert_shop_bot(session, owner, raw_token, me.id, me.username)
    await state.clear()
    await message.answer(texts.shop_bot_token_saved(me.username))

    try:
        await bot_manager.register(shop_bot)
    except Exception:
        logger.exception("ثبتِ ربات فروشگاهی %s در ShopBotManager ناموفق بود.", shop_bot.id)

    # A2: به‌محضِ وصل شدنِ یک رباتِ فروشگاهی، بیوگرافیِ اجباری رویِ خودش اعمال می‌شود.
    try:
        await bot_branding_service.apply_for_shop_bot(bot_manager, session, shop_bot)
    except Exception:
        logger.warning("اعمالِ بیوگرافی رویِ رباتِ تازه ثبت‌شده ناموفق بود.", exc_info=True)



# =============================================================================
# P19: رباتِ بله‌یِ خودِ فروشگاه (هوشمند روی بله، با همان کیف‌پول)
# =============================================================================
async def _own_shop_bot_cb(callback: CallbackQuery, session: AsyncSession):
    """رباتِ فروشگاهِ *همین* کاربر؛ None ⇒ پیامِ مودبانه و پاسخِ بی‌صدایِ کال‌بک."""
    owner = await _current_owner(callback, session)
    shop_bot = await shop_bot_service.get_by_owner(session, owner)
    if shop_bot is None:
        await callback.answer(texts.SHOP_BOT_NOT_SET_UP, show_alert=True)
        return None
    return shop_bot


async def _bale_screen(target, shop_bot) -> None:
    text = texts.bale_shop_bot_status_text(shop_bot)
    markup = keyboards.bale_shop_bot_keyboard(shop_bot)
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=markup)
    else:
        await target.answer(text, reply_markup=markup)


@router.message(F.text == texts.BALE_SHOP_BOT_BUTTON)
async def open_bale_shop_bot(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if not await bale_bot_service.visible_for(session):
        await message.answer(texts.BALE_SHOP_BOT_UNAVAILABLE)
        return
    owner = await _current_owner(message, session)
    shop_bot = await shop_bot_service.get_by_owner(session, owner)
    if shop_bot is None:
        await message.answer(texts.SHOP_BOT_NOT_SET_UP)
        return
    await state.clear()
    await _bale_screen(message, shop_bot)


@router.callback_query(F.data == "bale_edit")
async def bale_edit_token(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    shop_bot = await _own_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    await state.clear()
    await state.set_state(BaleShopBotStates.waiting_token)
    await callback.answer()
    await callback.message.answer(texts.ASK_BALE_SHOP_BOT_TOKEN)


@router.callback_query(F.data == "bale_back")
async def bale_back(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    owner = await _current_owner(callback, session)
    await callback.message.answer(
        texts.PANEL_WELCOME_BACK,
        reply_markup=keyboards.shop_owner_panel_keyboard(
            owner.business_mode if owner else None, bale_visible=await bale_bot_service.visible_for(session)
        ),
    )


@router.callback_query(F.data == "bale_on")
async def bale_turn_on(callback: CallbackQuery, session: AsyncSession, bot_manager) -> None:
    shop_bot = await _own_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    shop_bot.bale_bot_enabled = True
    await session.flush()
    try:
        await bot_manager.register_bale(shop_bot)
    except Exception:
        logger.exception("روشن‌کردنِ اتصالِ بله‌یِ فروشگاه %s ناموفق بود.", shop_bot.id)
        await callback.answer(texts.BALE_SHOP_BOT_NO_TRANSPORT, show_alert=True)
        return
    await callback.answer(texts.BALE_SHOP_BOT_ENABLED_AGAIN)
    await _bale_screen(callback.message, shop_bot)


@router.callback_query(F.data == "bale_off")
async def bale_turn_off(callback: CallbackQuery, session: AsyncSession, bot_manager) -> None:
    shop_bot = await _own_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    shop_bot.bale_bot_enabled = False
    await session.flush()
    await bot_manager.unregister_bale(shop_bot.id)
    await callback.answer(texts.BALE_SHOP_BOT_DISABLED_BY_OWNER)
    await _bale_screen(callback.message, shop_bot)


@router.callback_query(F.data == "bale_clear")
async def bale_clear_token(callback: CallbackQuery, session: AsyncSession, bot_manager) -> None:
    shop_bot = await _own_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    await bale_bot_service.clear_token(session, shop_bot)
    await bot_manager.unregister_bale(shop_bot.id)
    await callback.answer(texts.BALE_SHOP_BOT_REMOVED)
    await _bale_screen(callback.message, shop_bot)


@router.message(BaleShopBotStates.waiting_token, F.text)
async def save_bale_shop_bot_token(message: Message, state: FSMContext, session: AsyncSession, bot_manager) -> None:
    owner = await _current_owner(message, session)
    shop_bot = await shop_bot_service.get_by_owner(session, owner)
    if shop_bot is None:
        await state.clear()
        await message.answer(texts.SHOP_BOT_NOT_SET_UP)
        return

    raw_token = message.text.strip()
    if not bale_bot_service.valid_token_input(raw_token):
        await message.answer(texts.BALE_SHOP_BOT_TOKEN_INVALID_FORMAT)  # state می‌ماند تا درستش را بفرستد
        return
    try:
        identity = await bale_bot_service.fetch_identity(raw_token)
    except Exception:  # noqa: BLE001 — جزئیاتِ پاسخِ بله فقط در لاگ؛ توکن هرگز چاپ نمی‌شود
        logger.info("توکنِ بله‌یِ نامعتبر یا سرویسِ در دسترس نبود (owner=%s).", owner.id)
        await message.answer(texts.INVALID_BALE_SHOP_BOT_TOKEN)
        return

    holder = await bale_bot_service.get_by_bale_bot_id(session, int(identity["id"]))
    if holder is not None and holder.shop_owner_id != owner.id:
        await message.answer(texts.BALE_SHOP_BOT_ALREADY_USED)
        return

    await bale_bot_service.apply_token(session, shop_bot, raw_token, identity)
    await state.clear()
    await message.answer(texts.BALE_SHOP_BOT_SAVED)
    try:
        await bot_manager.register_bale(shop_bot)
    except Exception:
        logger.exception("ثبتِ اتصالِ بله‌یِ فروشگاه %s در ShopBotManager ناموفق بود.", shop_bot.id)
    await _bale_screen(message, shop_bot)


# =============================================================================
# دستور هوشمندسازی
# =============================================================================
@router.message(F.text == "🧠 دستور هوشمندسازی")
async def open_ai_instructions(message: Message, session: AsyncSession, state: FSMContext) -> None:
    owner = await _current_owner(message, session)
    shop_bot = await shop_bot_service.get_by_owner(session, owner)
    if shop_bot is None:
        await message.answer(texts.SHOP_BOT_NOT_SET_UP)
        return

    await message.answer(texts.ai_instructions_current(shop_bot.ai_instructions))
    await state.set_state(AiInstructionsStates.waiting_instructions)
    await message.answer(texts.ASK_AI_INSTRUCTIONS)


@router.message(AiInstructionsStates.waiting_instructions, F.text)
async def save_ai_instructions(message: Message, state: FSMContext, session: AsyncSession) -> None:
    owner = await _current_owner(message, session)
    shop_bot = await shop_bot_service.get_by_owner(session, owner)
    shop_bot.ai_instructions = message.text.strip()
    await session.flush()
    await state.clear()
    await message.answer(texts.AI_INSTRUCTIONS_SAVED)


# =============================================================================
# پیش‌نمایش ربات
# =============================================================================
@router.message(F.text == "👀 پیش‌نمایش ربات")
async def start_preview(message: Message, session: AsyncSession, state: FSMContext) -> None:
    owner = await _current_owner(message, session)
    shop_bot = await shop_bot_service.get_by_owner(session, owner)
    if shop_bot is None:
        await message.answer(texts.SHOP_BOT_NOT_SET_UP)
        return

    await state.set_state(PreviewStates.active)
    await message.answer(texts.PREVIEW_START_INTRO, reply_markup=keyboards.end_preview_keyboard())


@router.message(PreviewStates.active, F.text == "🔚 پایان پیش‌نمایش")
async def end_preview(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    owner = await _current_owner(message, session)
    shop_bot = await shop_bot_service.get_by_owner(session, owner)
    tenant_mode = shop_bot.tenant_mode if shop_bot else None
    await message.answer(texts.PREVIEW_END_TEXT, reply_markup=keyboards.shop_owner_panel_keyboard(tenant_mode, bale_visible=await bale_bot_service.visible_for(session)))


@router.message(PreviewStates.active, F.text)
async def preview_message(message: Message, session: AsyncSession) -> None:
    owner = await _current_owner(message, session)
    shop_bot = await shop_bot_service.get_by_owner(session, owner)
    products = await product_service.get_active_by_shop_bot(session, shop_bot.id)

    admin_settings = await get_admin_settings(session)
    # A5: حافظه‌یِ کانالِ دانش‌افزایی per-shop است؛ NULL یعنی همان پیش‌فرضِ سراسری.
    knowledge_limit = shop_prefs_service.resolve(shop_prefs_service.KNOWLEDGE_ITEMS, shop_bot, admin_settings)
    knowledge = await channel_knowledge_service.get_recent_knowledge(session, shop_bot.id, knowledge_limit)
    learned_answers = await knowledge_service.get_active_for_prompt(session, shop_bot.id)
    system_prompt = ai_context.build_system_prompt(
        shop_bot,
        products,
        knowledge,
        prompt_defaults.resolve_global_prompt(admin_settings, shop_bot.tenant_mode),
        learned_answers=learned_answers,
        gap_detection=admin_settings.knowledge_gap_enabled,
        bot_tools=prompt_defaults.build_bot_tools(shop_bot.tenant_mode, bool(shop_bot.support_enabled), shop_texts),
    )
    ai = await ai_pool_service.build_ai_service(session, admin_settings, "chat")
    if ai is None:
        await message.answer(texts.GENERIC_ERROR)
        return
    try:
        await session.commit()  # آزاد کردنِ اتصالِ دیتابیس قبل از انتظارِ AI (ظرفیت؛ فازِ ۶-الف)
        ai_result = await ai.get_reply(system_prompt, [], message.text)
    except ai_service.AiServiceError:
        logger.exception("فراخوانیِ هوش مصنوعی در حالت پیش‌نمایش ناموفق بود.")
        await message.answer(texts.GENERIC_ERROR)
        return

    # پیش‌نمایش: نشانه‌یِ خلأ حذف می‌شه ولی هیچ‌وقت *ثبت* نمی‌شه (سوالِ تستیِ خودِ فروشگاه‌دار نباید
    # توی «سوال‌هایِ بی‌جواب» قاطی بشه).
    preview_reply, gap_flagged = knowledge_service.strip_gap_marker(ai_result.text)
    if gap_flagged:
        preview_reply = f"{preview_reply}\n\n{texts.PREVIEW_GAP_NOTE}".strip()
    await message.answer(preview_reply or texts.PREVIEW_GAP_NOTE)


# =============================================================================
# کانال دانش‌افزایی
# =============================================================================
@router.message(F.text == "📢 کانال دانش‌افزایی")
async def open_channel_knowledge(message: Message, session: AsyncSession) -> None:
    owner = await _current_owner(message, session)
    shop_bot = await shop_bot_service.get_by_owner(session, owner)
    if shop_bot is None:
        await message.answer(texts.SHOP_BOT_NOT_SET_UP)
        return

    await message.answer(texts.channel_knowledge_current(shop_bot.knowledge_channel_id))
    await message.answer(texts.CHOOSE_KNOWLEDGE_BOT if hasattr(texts, "CHOOSE_KNOWLEDGE_BOT") else "کدوم ربات توی کانالت ادمین می‌شه؟", reply_markup=keyboards.choose_knowledge_bot_keyboard())


@router.callback_query(F.data.startswith("knowledge_bot:"))
async def cb_choose_knowledge_bot(callback: CallbackQuery, state: FSMContext) -> None:
    choice = callback.data.split(":")[1]
    await state.update_data(knowledge_bot=choice)
    await state.set_state(ChannelKnowledgeStates.waiting_channel_proof)
    await callback.answer()
    await callback.message.answer(texts.ASK_CHANNEL_FORWARD_OR_USERNAME)


async def _resolve_target_bot(choice: str, message: Message, session: AsyncSession) -> tuple[Bot, int] | None:
    if choice == "main":
        me = await message.bot.get_me()
        return message.bot, me.id

    owner = await _current_owner(message, session)
    shop_bot = await shop_bot_service.get_by_owner(session, owner)
    if shop_bot is None:
        return None
    temp_bot = Bot(token=decrypt_token(shop_bot.encrypted_token))
    return temp_bot, shop_bot.bot_telegram_id


@router.message(ChannelKnowledgeStates.waiting_channel_proof)
async def channel_knowledge_proof(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    target = await _resolve_target_bot(data["knowledge_bot"], message, session)
    if target is None:
        await message.answer(texts.SHOP_BOT_NOT_SET_UP)
        await state.clear()
        return
    target_bot, target_bot_id = target

    channel_id: str | None = None
    channel_title: str | None = None
    try:
        if message.forward_from_chat is not None:
            channel_id = str(message.forward_from_chat.id)
            channel_title = message.forward_from_chat.title
        elif message.text and message.text.strip().startswith("@"):
            chat = await target_bot.get_chat(message.text.strip())
            channel_id = str(chat.id)
            channel_title = chat.title

        if channel_id is None:
            await message.answer(texts.CHANNEL_KNOWLEDGE_NOT_FOUND)
            return

        member = await target_bot.get_chat_member(_chat_id_arg(channel_id), target_bot_id)
        if member.status not in ("administrator", "creator"):
            await message.answer(texts.CHANNEL_KNOWLEDGE_NOT_FOUND)
            return
    except TelegramAPIError:
        logger.info("بررسیِ عضویتِ ادمین برای کانال دانش‌افزایی ناموفق بود.")
        await message.answer(texts.CHANNEL_KNOWLEDGE_NOT_FOUND)
        return
    finally:
        if data["knowledge_bot"] == "shop":
            await target_bot.session.close()

    owner = await _current_owner(message, session)
    shop_bot = await shop_bot_service.get_by_owner(session, owner)
    shop_bot.knowledge_channel_id = channel_id
    shop_bot.knowledge_channel_bot = data["knowledge_bot"]
    await session.flush()

    await state.clear()
    await message.answer(texts.channel_knowledge_linked(channel_title or channel_id))


def _is_consultation(shop_bot) -> bool:
    """C1/C2/C3: مشاوره‌ای = بدونِ محصول، بدونِ CRMِ فروشگاهی، بدونِ حسابداری و بدونِ واژه‌یِ «سفارش»."""
    return shop_bot is not None and shop_bot.tenant_mode == TenantMode.CONSULTATION


# =============================================================================
# آمار
# =============================================================================
@router.message(F.text == "📊 آمار")
async def open_stats(message: Message, session: AsyncSession) -> None:
    owner = await _current_owner(message, session)
    shop_bot = await shop_bot_service.get_by_owner(session, owner)
    if shop_bot is None:
        await message.answer(texts.SHOP_BOT_NOT_SET_UP)
        return

    stats = await stats_service.get_shop_stats(session, shop_bot.id)
    await message.answer(texts.shop_stats_text(stats, consultation=_is_consultation(shop_bot)))


# =============================================================================
# =============================================================================
# کیف‌پول و پرداخت
# =============================================================================
async def _wallet_status_line(session: AsyncSession, owner) -> str:
    """موجودی + «چقدرش واقعاً قابلِ خرج است» + «چقدرش دارد منقضی می‌شود»."""
    usable, expiring_toman, expiring_days = await wallet_service.credit_summary(session, owner)
    return texts.wallet_status_text(
        owner.wallet_balance_toman, usable_toman=usable, expiring_toman=expiring_toman, expiring_days=expiring_days
    )


@router.message(F.text == "💰 کیف‌پول")
async def open_wallet(message: Message, session: AsyncSession) -> None:
    owner = await _current_owner(message, session)
    await message.answer(await _wallet_status_line(session, owner), reply_markup=keyboards.wallet_topup_action_keyboard())


@router.callback_query(F.data == "wallet_history")
async def cb_wallet_history(callback: CallbackQuery, session: AsyncSession) -> None:
    owner = await _current_owner(callback, session)
    transactions = await wallet_service.get_recent_transactions(session, owner.id)
    await callback.answer()
    if not transactions:
        await callback.message.answer(texts.WALLET_HISTORY_EMPTY)
        return
    lines = [texts.WALLET_HISTORY_INTRO, ""]
    lines.extend(texts.wallet_transaction_line(t) for t in transactions)
    await callback.message.answer("\n".join(lines))


@router.callback_query(F.data == "topup_start")
async def cb_topup_start(callback: CallbackQuery, session: AsyncSession) -> None:
    admin_settings = await get_admin_settings(session)
    if not admin_settings.allow_wallet_topups:
        await callback.answer(texts.WALLET_TOPUPS_DISABLED, show_alert=True)
        return
    await callback.answer()
    # PHASE 5A: همان عددی که در سرویس چک می‌شود به UI هم داده می‌شود تا هرگز جدا نیفتند.
    await callback.message.answer(
        texts.ASK_TOPUP_AMOUNT,
        reply_markup=keyboards.topup_amount_keyboard(await payment_service.minimum_recharge_toman(session)),
    )


@router.callback_query(F.data == "cost_calc_start")
async def cb_cost_calc_start(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.answer(texts.ASK_COST_CALC_VOLUME, reply_markup=keyboards.cost_calc_volume_keyboard())


@router.callback_query(F.data.startswith("cost_calc_volume:"))
async def cb_cost_calc_volume(callback: CallbackQuery, session: AsyncSession) -> None:
    volume_key = callback.data.split(":", 1)[1]
    admin_settings = await get_admin_settings(session)
    cost_per_message = wallet_service.estimate_chat_cost(admin_settings, None)  # None → همون فرضِ ۸۰۰ توکنِ پیش‌فرض
    await callback.answer()
    await callback.message.answer(texts.cost_calc_result_text(volume_key, cost_per_message), reply_markup=keyboards.wallet_topup_action_keyboard())


@router.callback_query(F.data.startswith("topup_amount:"))
async def cb_topup_amount(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    choice = callback.data.split(":", 1)[1]
    if choice == "custom":
        await state.set_state(PaymentStates.waiting_topup_amount)
        await callback.answer()
        await callback.message.answer(texts.custom_topup_prompt(await payment_service.minimum_recharge_toman(session)))
        return

    # PHASE 5A: دکمه‌یِ کهنه/دستکاری‌شده (topup_amount:1) باید همان حداقلِ سرویس را رد کند،
    # وگرنه UI فقط «پیش‌فرض‌هایِ درست» را نشان می‌دهد و callback جعلی از آن رد می‌شود.
    try:
        amount = int(choice)
    except ValueError:
        await callback.answer(texts.INVALID_TOPUP_AMOUNT_FALLBACK, show_alert=True)
        return
    minimum = await payment_service.minimum_recharge_toman(session)
    if amount < minimum:
        await callback.answer(texts.topup_below_minimum_toast(minimum), show_alert=True)
        await callback.message.edit_reply_markup(reply_markup=keyboards.topup_amount_keyboard(minimum))
        return

    await state.update_data(
        duration_months=None,
        purpose=PaymentPurpose.WALLET_TOPUP.value,
        base_amount=amount,
        discount_code_id=None,
        final_amount=amount,
    )
    await state.set_state(PaymentStates.waiting_discount_code)
    await callback.answer()
    await callback.message.answer(texts.ASK_DISCOUNT_CODE, reply_markup=keyboards.skip_discount_keyboard())


@router.message(PaymentStates.waiting_topup_amount, F.text)
async def topup_custom_amount_received(message: Message, state: FSMContext, session: AsyncSession) -> None:
    minimum = await payment_service.minimum_recharge_toman(session)
    try:
        amount = int(message.text.strip())
        await payment_service.ensure_recharge_amount_allowed(
            session, amount, PaymentPurpose.WALLET_TOPUP
        )  # PHASE 5A: همان گاردِ سرویس، نه یک عددِ دوباره‌نویسه‌شده در UI
    except (ValueError, payment_service.MinRechargeAmountError):
        await message.answer(texts.invalid_topup_amount(minimum))
        return

    await state.update_data(
        duration_months=None,
        purpose=PaymentPurpose.WALLET_TOPUP.value,
        base_amount=amount,
        discount_code_id=None,
        final_amount=amount,
    )
    await state.set_state(PaymentStates.waiting_discount_code)
    await message.answer(texts.ASK_DISCOUNT_CODE, reply_markup=keyboards.skip_discount_keyboard())


@router.message(PaymentStates.waiting_discount_code, F.text)
async def payment_discount_code(message: Message, state: FSMContext, session: AsyncSession) -> None:
    owner = await _current_owner(message, session)
    data = await state.get_data()

    discount = await discount_service.validate_code(session, message.text.strip(), owner.id)
    if discount is None:
        await message.answer(texts.INVALID_DISCOUNT_CODE)
        return

    # نکته: final_amount اینجا فقط برای نمایشِ پیش‌نمایش به فروشگاه‌دار محاسبه
    # می‌شه؛ مبلغِ واقعی هنگام ساختِ پرداخت، دوباره و به‌صورت داخلی توسط
    # payment_service از روی base_amount محاسبه می‌شه (نه از این مقدار).
    final_amount = discount_service.apply_discount(data["base_amount"], discount)
    await state.update_data(discount_code_id=discount.id, final_amount=final_amount)
    await message.answer(texts.discount_applied_text(discount, final_amount))
    admin_settings = await get_admin_settings(session)
    await message.answer(texts.ASK_PAYMENT_METHOD, reply_markup=keyboards.payment_method_keyboard(admin_settings.zarinpal_enabled, admin_settings.bale_pay_enabled))


@router.callback_query(PaymentStates.waiting_discount_code, F.data == "skip_discount")
async def cb_skip_discount(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await callback.answer()
    admin_settings = await get_admin_settings(session)
    await callback.message.answer(texts.ASK_PAYMENT_METHOD, reply_markup=keyboards.payment_method_keyboard(admin_settings.zarinpal_enabled, admin_settings.bale_pay_enabled))


@router.callback_query(F.data == "payment_method:card")
async def cb_payment_method_card(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    owner = await _current_owner(callback, session)
    data = await state.get_data()
    purpose = PaymentPurpose(data.get("purpose", PaymentPurpose.WALLET_TOPUP.value))

    # نکته‌ی مهم (اصلاح‌شده): همیشه base_amount (مبلغِ واقعیِ پیش از تخفیف) رو
    # پاس می‌دیم، نه final_amount؛ چون create_card_to_card_payment خودش تخفیف رو
    # به‌صورت داخلی روی base_amount اعمال می‌کنه. اگه اینجا مبلغِ از‌قبل‌تخفیف‌خورده
    # پاس داده بشه، تخفیف دوبار اعمال می‌شه.
    payment = await payment_service.create_card_to_card_payment(
        session, owner, data["base_amount"],
        await _get_discount_or_none(session, data.get("discount_code_id")),
        duration_months=data.get("duration_months"),
        purpose=purpose,
    )
    await state.update_data(payment_id=payment.id)
    await state.set_state(PaymentStates.waiting_receipt)

    admin_settings = await get_admin_settings(session)
    await callback.answer()
    await callback.message.answer(
        texts.card_to_card_payment_instructions(
            admin_settings.platform_card_number or "—", admin_settings.platform_card_holder_name or "—", payment.final_amount
        ),
        parse_mode="HTML",
    )
    # A7: رسیدِ عکسی یا متنی پذیرفته می‌شود و «⬅️ برگشت» پرداخت را از بین نمی‌برد.
    await callback.message.answer(texts.ASK_TOPUP_RECEIPT, reply_markup=keyboards.topup_receipt_keyboard(payment.id))


async def _notify_admins_new_payment(message: Message, payment, owner) -> None:
    """A7: رسید (عکس یا متن) + پرچمِ تکراری برایِ ادمین؛ شکستِ ارسال فقط لاگ می‌شود."""
    notification = texts.admin_new_payment_notification(payment, owner)
    reply_markup = keyboards.admin_payment_approval_keyboard(payment.id)
    for admin_id in settings.admin_ids:
        try:
            if payment.receipt_file_id:
                await message.bot.send_photo(admin_id, payment.receipt_file_id, caption=notification, reply_markup=reply_markup)
            else:
                await message.bot.send_message(admin_id, notification, reply_markup=reply_markup)
        except TelegramAPIError:
            logger.exception("اطلاع‌رسانیِ پرداختِ جدید به ادمین %s ناموفق بود.", admin_id)


@router.message(PaymentStates.waiting_receipt, F.photo)
async def payment_receipt_received(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    owner = await _current_owner(message, session)
    payment = await _owned_topup_payment(session, owner, data.get("payment_id"))
    if payment is None:
        await state.clear()
        await message.answer(texts.TOPUP_PAYMENT_GONE)
        return
    await payment_service.attach_receipt(session, payment, message.photo[-1].file_id)
    await state.clear()
    await message.answer(texts.RECEIPT_RECEIVED_PENDING_APPROVAL)
    await _notify_admins_new_payment(message, payment, owner)


@router.message(PaymentStates.waiting_receipt, F.text)
async def payment_receipt_text_received(message: Message, state: FSMContext, session: AsyncSession) -> None:
    """A7: رسیدِ متنیِ شارژِ اعتبار (مثلِ سمتِ فروشگاه): متنِ آزادِ اپِ بانک/پیامک یا فقط شماره‌یِ پیگیری.
    تکراری بودن فقط پرچم می‌خورد و تصمیم با ادمین است."""
    raw = (message.text or "").strip()
    tracking = order_payment_service.extract_tracking_ref(raw)
    parsed = None if tracking is not None else order_payment_service.parse_receipt_text(raw)
    if tracking is None and parsed is None:
        await message.answer(texts.TOPUP_RECEIPT_TEXT_INVALID)
        return
    receipt_text = raw if tracking is not None else parsed[0]
    tracking_ref = tracking if tracking is not None else parsed[1]

    data = await state.get_data()
    owner = await _current_owner(message, session)
    payment = await _owned_topup_payment(session, owner, data.get("payment_id"))
    if payment is None:
        await state.clear()
        await message.answer(texts.TOPUP_PAYMENT_GONE)
        return
    await payment_service.attach_text_receipt(session, payment, receipt_text, tracking_ref)
    await state.clear()
    await message.answer(texts.RECEIPT_RECEIVED_PENDING_APPROVAL)
    await _notify_admins_new_payment(message, payment, owner)


async def _owned_topup_payment(session: AsyncSession, owner, payment_id):
    """مالکیت: فقط پرداختِ در انتظارِ رسیدِ خودِ این فروشگاه‌دار (IDOR بسته)."""
    if not isinstance(payment_id, int):
        return None
    payment = await payment_service.get_by_id(session, payment_id)
    if payment is None or payment.shop_owner_id != owner.id or payment.status != PaymentStatus.PENDING:
        return None
    if payment.receipt_file_id or payment.receipt_text:
        return None  # رسید قبلاً ثبت شده ⇒ دابل‌تپ/کیبوردِ کهنه
    return payment


@router.callback_query(F.data.startswith("topup_pay_back:"))
async def cb_topup_pay_back(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """A7: «⬅️ برگشت» در انتظارِ رسید — state پاک می‌شود ولی ردیفِ پرداخت می‌ماند و بعداً قابلِ ادامه است."""
    raw = callback.data.split(":", 1)[1]
    payment_id = int(raw) if raw.isascii() and raw.isdecimal() else None
    owner = await _current_owner(callback, session)
    payment = await payment_service.get_by_id(session, payment_id) if payment_id else None
    await callback.answer()
    await state.clear()
    if payment is None or payment.shop_owner_id != owner.id:
        await callback.message.answer(texts.TOPUP_PAYMENT_GONE)
        return
    await callback.message.answer(texts.topup_receipt_back_text(payment), reply_markup=keyboards.wallet_topup_action_keyboard())


@router.callback_query(F.data == "topup_open_list")
async def cb_topup_open_list(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    owner = await _current_owner(callback, session)
    await state.clear()
    payments = await payment_service.get_open_receipt_payments(session, owner.id)
    await callback.answer()
    await callback.message.answer(
        texts.open_topup_payments_text(payments), reply_markup=keyboards.open_topup_payments_keyboard(payments)
    )


@router.callback_query(F.data.startswith("topup_pay_resume:"))
async def cb_topup_pay_resume(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    raw = callback.data.split(":", 1)[1]
    payment_id = int(raw) if raw.isascii() and raw.isdecimal() else None
    owner = await _current_owner(callback, session)
    payment = await _owned_topup_payment(session, owner, payment_id)
    if payment is None:
        await callback.answer()
        await state.clear()
        await callback.message.answer(texts.TOPUP_PAYMENT_GONE)
        return
    # ستونِ purpose از نوعِ String است، پس مقدارِ خوانده‌شده از دیتابیس رشته‌یِ خام است نه عضوِ Enum.
    purpose = payment.purpose
    await state.update_data(
        payment_id=payment.id,
        purpose=purpose.value if isinstance(purpose, PaymentPurpose) else purpose,
    )
    await state.set_state(PaymentStates.waiting_receipt)
    await callback.answer()
    await callback.message.answer(texts.topup_receipt_resume_text(payment), reply_markup=keyboards.topup_receipt_keyboard(payment.id))


@router.callback_query(F.data == "wallet_status")
async def cb_wallet_status(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    owner = await _current_owner(callback, session)
    await state.clear()
    await callback.answer()
    await callback.message.answer(
        await _wallet_status_line(session, owner), reply_markup=keyboards.wallet_topup_action_keyboard()
    )


@router.callback_query(F.data == "payment_method:zarinpal")
async def cb_payment_method_zarinpal(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    owner = await _current_owner(callback, session)
    data = await state.get_data()
    admin_settings = await get_admin_settings(session)

    if not admin_settings.zarinpal_enabled:
        await callback.answer()
        await callback.message.answer(texts.ZARINPAL_ERROR)
        return

    if not admin_settings.zarinpal_merchant_id:
        await callback.answer()
        await callback.message.answer(texts.ZARINPAL_ERROR)
        return

    # همون مبلغِ نهاییِ تخفیف‌خورده رو باید از زرین‌پال درخواست کنیم (چون کاربر
    # قراره دقیقاً همین رو پرداخت کنه)، ولی به create_zarinpal_payment باز هم
    # base_amount ِ واقعی رو پاس می‌دیم چون خودش تخفیف رو دوباره محاسبه می‌کنه.
    callback_url = f"{settings.webhook_base_url.rstrip('/')}/payment/zarinpal/callback"
    purpose = PaymentPurpose(data.get("purpose", PaymentPurpose.WALLET_TOPUP.value))
    description = "شارژ کیف‌پول کسب‌وکار هوشمند" if purpose == PaymentPurpose.WALLET_TOPUP else "خرید اشتراک کسب‌وکار هوشمند"
    try:
        authority, pay_url = await zarinpal_service.request_payment(
            admin_settings.zarinpal_merchant_id, data["final_amount"], callback_url, description
        )
    except zarinpal_service.ZarinpalError:
        logger.exception("درخواستِ پرداختِ زرین‌پال ناموفق بود.")
        await callback.answer()
        await callback.message.answer(texts.ZARINPAL_ERROR)
        return

    await payment_service.create_zarinpal_payment(
        session, owner, data["base_amount"], await _get_discount_or_none(session, data.get("discount_code_id")), authority,
        duration_months=data.get("duration_months"),
        purpose=purpose,
    )
    await state.clear()
    await callback.answer()
    await callback.message.answer(texts.ZARINPAL_REDIRECT_TEXT, reply_markup=keyboards.zarinpal_pay_keyboard(pay_url))


@router.callback_query(F.data == "payment_method:bale")
async def cb_payment_method_bale(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    owner = await _current_owner(callback, session)
    data = await state.get_data()
    admin_settings = await get_admin_settings(session)

    _platform_ok, missing = bale_credentials_service.platform_status(admin_settings)
    if missing:
        await callback.answer()
        await callback.message.answer(texts.bale_platform_not_ready(missing))
        return

    purpose = PaymentPurpose(data.get("purpose", PaymentPurpose.WALLET_TOPUP.value))
    description = "شارژ کیف‌پول کسب‌وکار هوشمند" if purpose == PaymentPurpose.WALLET_TOPUP else "خرید اشتراک کسب‌وکار هوشمند"
    invoice_payload = f"payment-{owner.id}-{secrets.token_hex(8)}"
    # مبلغ‌های داخلیِ ما همیشه تومانن؛ بله‌پی طبقِ فایلِ ارائه‌شده ریال می‌خواد (۱ تومان = ۱۰ ریال).
    amount_rial = bale_service.toman_to_rial(data["final_amount"])
    try:
        pay_url = await bale_service.create_invoice_link(
            bale_credentials_service.bot_token(),
            admin_settings.bale_provider_token,
            title="شارژ کیف‌پول" if purpose == PaymentPurpose.WALLET_TOPUP else "خرید اشتراک",
            description=description,
            payload=invoice_payload,
            amount_rial=amount_rial,
        )
    except bale_service.BaleError:
        logger.exception("درخواستِ ساختِ لینکِ بله‌پی ناموفق بود.")
        await callback.answer()
        await callback.message.answer(texts.BALE_PAY_ERROR)
        return

    await payment_service.create_bale_payment(
        session, owner, data["base_amount"], await _get_discount_or_none(session, data.get("discount_code_id")), invoice_payload,
        duration_months=data.get("duration_months"),
        purpose=purpose,
    )
    await state.clear()
    await callback.answer()
    await callback.message.answer(texts.BALE_PAY_REDIRECT_TEXT, reply_markup=keyboards.bale_pay_keyboard(pay_url))


# =============================================================================
# کد معرف
# =============================================================================
@router.message(F.text == "🎁 کد معرف")
async def open_referral(message: Message, session: AsyncSession) -> None:
    owner = await _current_owner(message, session)
    stats = await referral_service.get_referral_stats(session, owner.id)
    me = await message.bot.get_me()
    admin_settings = await get_admin_settings(session)
    await message.answer(texts.referral_code_text(owner.referral_code, stats, me.username, admin_settings.referral_reward_wallet_toman))


# =============================================================================
# تاریخچه‌ی پرداخت
# =============================================================================
@router.message(F.text == "🧾 تاریخچه‌ی پرداخت")
async def open_payment_history(message: Message, session: AsyncSession) -> None:
    owner = await _current_owner(message, session)
    payments = await payment_service.get_history_by_owner(session, owner.id)
    if not payments:
        await message.answer(texts.PAYMENT_HISTORY_EMPTY)
        return
    await message.answer("\n".join(texts.payment_history_item(p) for p in payments))


# =============================================================================
# خروجی اکسل
# =============================================================================
@router.message(F.text == "📤 خروجی اکسل")
async def open_excel_export(message: Message, session: AsyncSession) -> None:
    owner = await _current_owner(message, session)
    shop_bot = await shop_bot_service.get_by_owner(session, owner)
    if shop_bot is None:
        await message.answer(texts.SHOP_BOT_NOT_SET_UP)
        return
    await message.answer(
        texts.CHOOSE_EXCEL_EXPORT, reply_markup=keyboards.excel_export_choice_keyboard(_is_consultation(shop_bot))
    )


@router.callback_query(F.data.startswith("export_excel:"))
async def cb_export_excel(callback: CallbackQuery, session: AsyncSession) -> None:
    kind = callback.data.split(":")[1]
    owner = await _current_owner(callback, session)
    shop_bot = await shop_bot_service.get_by_owner(session, owner)
    await callback.answer()

    if kind == "customers":
        count = await session.scalar(select(func.count()).select_from(Customer).where(Customer.shop_bot_id == shop_bot.id))
        if not count:
            await callback.message.answer(texts.EXCEL_EXPORT_EMPTY)
            return
        content = await excel_export_service.build_customers_workbook(session, shop_bot.id, consultation=_is_consultation(shop_bot))
        filename = "customers.xlsx"
    else:
        count = await session.scalar(select(func.count()).select_from(OrderConsultation).where(OrderConsultation.shop_bot_id == shop_bot.id))
        if not count:
            await callback.message.answer(texts.EXCEL_EXPORT_EMPTY)
            return
        content = await excel_export_service.build_orders_workbook(session, shop_bot.id, consultation=_is_consultation(shop_bot))
        filename = "orders.xlsx"

    await callback.message.answer_document(BufferedInputFile(content, filename=filename), caption=texts.EXCEL_EXPORT_READY)


# =============================================================================
# پیامِ فروشگاه‌دار به مشتری‌ها (فازِ ۳) — جدا از پیامِ همگانیِ ادمین (admin.py)
# =============================================================================
# فاصله‌ی کوچیک بینِ ارسالِ هر پیام، تا با سرعتِ خیلی بالا به Rate limit تلگرام
# نخوریم (حدِ تلگرام تقریباً ۳۰ پیام/ثانیه‌ست؛ با ۰.۰۵ ثانیه فاصله می‌شیم ~۲۰
# پیام/ثانیه — با حاشیه‌ی امنِ کافی).
CUSTOMER_BROADCAST_PACE_SECONDS = 0.05


@router.message(F.text == "📣 پیام به مشتری‌ها")
async def open_customer_broadcast(message: Message, session: AsyncSession, state: FSMContext) -> None:
    owner = await _current_owner(message, session)
    shop_bot = await shop_bot_service.get_by_owner(session, owner)
    if shop_bot is None:
        await message.answer(texts.SHOP_BOT_NOT_SET_UP)
        return

    count = await customer_service.count_by_shop_bot(session, shop_bot.id)
    if count == 0:
        await message.answer(texts.CUSTOMER_BROADCAST_NO_CUSTOMERS)
        return

    # فازِ ۴: پیام به «همه» همیشه از صفر شروع می‌شه تا فهرستِ گیرنده‌هایِ یه بخشِ CRM (که توی FSM
    # data می‌مونه) هیچ‌وقت به یه ارسالِ همگانیِ تازه نشت نکنه.
    await state.clear()
    await state.set_state(CustomerBroadcastStates.waiting_message)
    await message.answer(texts.ASK_CUSTOMER_BROADCAST_MESSAGE)


@router.message(CustomerBroadcastStates.waiting_message, F.text)
async def customer_broadcast_message_entered(message: Message, state: FSMContext, session: AsyncSession) -> None:
    owner = await _current_owner(message, session)
    shop_bot = await shop_bot_service.get_by_owner(session, owner)
    # فازِ ۴: اگه از «📣 پیام به این بخش»ِ CRM اومده باشیم، گیرنده‌ها فقط همون بخش‌ان.
    segment_ids = (await state.get_data()).get("broadcast_customer_ids")
    if segment_ids is not None:
        count = len(segment_ids)
    else:
        count = await customer_service.count_by_shop_bot(session, shop_bot.id)

    await state.update_data(broadcast_text=message.text)
    await state.set_state(CustomerBroadcastStates.waiting_confirmation)
    await message.answer(texts.customer_broadcast_preview(message.text, count), reply_markup=keyboards.confirm_customer_broadcast_keyboard())


async def _run_customer_broadcast(
    bot_manager, shop_bot_id: int, recipients: list[tuple[int, str]], text: str, main_bot: Bot, owner_telegram_id: int
) -> None:
    """تسکِ پس‌زمینه: پیام رو یکی‌یکی برایِ مشتری‌ها می‌فرسته (نه داخلِ خودِ
    هندلرِ کال‌بک، تا جلوگیریِ ارسالِ همزمانِ همه‌ی آپدیت‌هایِ دیگه‌ی همین ربات
    برایِ چند ثانیه/دقیقه گرفته نشه) و در پایان یه خلاصه به خودِ فروشگاه‌دار
    (از طریقِ ربات اصلی) می‌فرسته.

    گیرنده (شناسه، پلتفرم) است: فرستادنِ شناسه‌یِ مشتریِ بله از رباتِ تلگرام
    می‌تواند به آدمِ غریبه‌یِ دیگری برسد که همان عدد را دارد."""
    sent = 0
    for telegram_id, platform in recipients:
        bot = bot_manager.customer_bot(shop_bot_id, platform)
        if bot is None:
            logger.info("پیامِ همگانی به مشتری %s رها شد: اتصالِ %s فعال نیست.", telegram_id, platform)
            continue
        try:
            await bot.send_message(telegram_id, text)
            sent += 1
        except TelegramRetryAfter as exc:
            await asyncio.sleep(exc.retry_after)
            try:
                await bot.send_message(telegram_id, text)
                sent += 1
            except TelegramAPIError:
                logger.info("ارسالِ پیام به مشتری %s (حتی بعدِ retry) ناموفق بود.", telegram_id)
        except TelegramAPIError:
            logger.info("ارسالِ پیام به مشتری %s ناموفق بود (احتمالاً ربات رو بلاک کرده).", telegram_id)
        await asyncio.sleep(CUSTOMER_BROADCAST_PACE_SECONDS)

    try:
        await main_bot.send_message(owner_telegram_id, texts.customer_broadcast_sent_confirmation(sent, len(recipients)))
    except TelegramAPIError:
        logger.exception("اطلاع‌رسانیِ نتیجه‌ی پیامِ همگانی به فروشگاه‌دار %s ناموفق بود.", owner_telegram_id)


@router.callback_query(CustomerBroadcastStates.waiting_confirmation, F.data == "customer_broadcast_confirm")
async def customer_broadcast_confirmed(callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot_manager) -> None:
    owner = await _current_owner(callback, session)
    shop_bot = await shop_bot_service.get_by_owner(session, owner)
    data = await state.get_data()
    await state.clear()
    await callback.answer()

    if shop_bot is None:
        await callback.message.edit_text(texts.SHOP_BOT_NOT_SET_UP)
        return

    if bot_manager.get_bot(shop_bot.id) is None and bot_manager.get_bale_bot(shop_bot.id) is None:
        await callback.message.edit_text(texts.CUSTOMER_BROADCAST_BOT_OFFLINE)
        return

    segment_ids = data.get("broadcast_customer_ids")
    if segment_ids is not None:
        recipients = await customer_service.recipients_by_ids(session, shop_bot.id, [int(pk) for pk in segment_ids])
    else:
        recipients = await customer_service.recipients_by_shop_bot(session, shop_bot.id)
    await callback.message.edit_text(texts.customer_broadcast_started(len(recipients)))

    asyncio.create_task(
        _run_customer_broadcast(bot_manager, shop_bot.id, recipients, data["broadcast_text"], callback.bot, owner.telegram_id)
    )


@router.callback_query(CustomerBroadcastStates.waiting_confirmation, F.data == "customer_broadcast_cancel")
async def customer_broadcast_cancelled(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await callback.message.edit_text(texts.CUSTOMER_BROADCAST_CANCELLED)


# =============================================================================
# پرداختِ آنلاینِ سفارش از طریقِ بله‌پیِ خودِ فروشگاه (فازِ ۳)
# =============================================================================
@router.message(F.text == "💳 پرداختِ آنلاینِ سفارش‌ها")
async def open_bale_provider_token(message: Message, session: AsyncSession, state: FSMContext) -> None:
    owner = await _current_owner(message, session)
    shop_bot = await shop_bot_service.get_by_owner(session, owner)
    if shop_bot is None:
        await message.answer(texts.SHOP_BOT_NOT_SET_UP)
        return

    row = await payment_settings_service.get(session, shop_bot.id)
    status = await bale_credentials_service.shop_status(session, shop_bot, row)
    # B11: قبلاً دو پیامِ پشتِ‌هم می‌رفت (وضعیت + «کد را بفرست») که «پیامِ اضافه» به نظر می‌رسید؛
    # حالا یک پیامِ واحد، با وضعیتِ واقعی و آنچه کم است.
    await state.set_state(BaleProviderTokenStates.waiting_token)
    await message.answer(
        texts.bale_provider_token_current(shop_bot, status.missing), reply_markup=keyboards.payments_entry_keyboard()
    )


@router.message(BaleProviderTokenStates.waiting_token, F.text)
async def save_bale_provider_token(message: Message, state: FSMContext, session: AsyncSession) -> None:
    owner = await _current_owner(message, session)
    shop_bot = await shop_bot_service.get_by_owner(session, owner)
    raw = message.text.strip()
    if raw == "حذف":
        await state.clear()
        shop_bot.bale_provider_token = None
        await session.flush()
        await message.answer(texts.BALE_PROVIDER_TOKEN_REMOVED)
        return

    if not bale_credentials_service.valid_token_input(raw):
        await message.answer(texts.BALE_PROVIDER_TOKEN_INVALID)  # state می‌ماند تا دوباره بفرستد
        return

    await state.clear()
    shop_bot.bale_provider_token = raw
    await session.flush()
    await message.answer(texts.BALE_PROVIDER_TOKEN_SAVED)


# =============================================================================
# سوال‌هایِ چک‌اوتِ سبدِ خرید (فازِ ۳) — فروشگاه‌دار تعریف می‌کنه
# =============================================================================
@router.message(F.text == "📝 سوال‌هایِ چک‌اوتِ سبد")
async def open_checkout_questions(message: Message, session: AsyncSession, state: FSMContext) -> None:
    owner = await _current_owner(message, session)
    shop_bot = await shop_bot_service.get_by_owner(session, owner)
    if shop_bot is None:
        await message.answer(texts.SHOP_BOT_NOT_SET_UP)
        return

    await message.answer(texts.checkout_questions_current(shop_bot))
    await state.set_state(CheckoutQuestionsStates.waiting_questions)
    await message.answer(texts.ASK_CHECKOUT_QUESTIONS, reply_markup=keyboards.checkout_questions_keyboard())


@router.message(CheckoutQuestionsStates.waiting_questions, F.text)
async def save_checkout_questions(message: Message, state: FSMContext, session: AsyncSession) -> None:
    owner = await _current_owner(message, session)
    shop_bot = await shop_bot_service.get_by_owner(session, owner)
    await state.clear()

    raw = message.text.strip()
    if raw == "حذف":
        shop_bot.checkout_questions = None
        await session.flush()
        await message.answer(texts.CHECKOUT_QUESTIONS_RESET)
        return

    shop_bot.checkout_questions = raw
    await session.flush()
    await message.answer(texts.CHECKOUT_QUESTIONS_SAVED)


# =============================================================================
# تایید سفارش و کسر موجودی (این‌جلسه — feature #7)
# =============================================================================
async def _notify_manual_decision(session: AsyncSession, shop_bot, rows: list[OrderConsultation], to_status: str, bot_manager) -> None:
    """اعلانِ خودکار به مشتری روی تایید/ردِ دستیِ قدیمی (W5 · 1.4). شکستِ ارسال فقط لاگ می‌شه.
    تاییدِ سفارشِ *دیجیتال* اعلانِ جدا نداره (خودِ پیامِ تحویل، اعلان است)؛ ردّ همیشه اعلان می‌شه."""
    if bot_manager is None or not rows:
        return
    if to_status == "confirmed":
        has_physical = False
        for row in rows:
            product = await product_service.get_by_id(session, row.product_id) if row.product_id is not None else None
            if product is None or not digital_service.is_digital(product):
                has_physical = True
                break
        if not has_physical:
            return
    customer = await session.get(Customer, rows[0].customer_id)
    if customer is None:
        return
    customer_bot = bot_manager.customer_bot(shop_bot.id, customer.platform)
    if customer_bot is None:
        return
    try:
        await customer_bot.send_message(customer.telegram_id, shop_texts.order_status_customer_message(to_status, rows))
    except TelegramAPIError:
        logger.warning("اعلانِ تایید/ردِ دستیِ سفارش به مشتری نرسید (shop_bot=%s).", shop_bot.id)


async def _deliver_digital_after_confirm(session: AsyncSession, order: OrderConsultation, shop_bot, bot_manager, main_bot: Bot) -> str | None:
    """P1-S3 (B2): بعد از تاییدِ فروشگاه‌دار (= «پرداخت‌شده» تا W2/W3)، اگه محصولِ سفارش دیجیتاله، تحویلِ
    ایدمپوتنت انجام می‌شه (کد با SKIP LOCKED، commit، بعد ارسال). برایِ سفارشِ فیزیکی None برمی‌گردونه
    (هیچ تغییری در رفتارِ قبلی). نتیجه: status ∈ delivered|insufficient|send_failed|already."""
    if order.product_id is None:
        return None
    product = await product_service.get_by_id(session, order.product_id)
    if not digital_service.is_digital(product):
        return None
    customer = await session.get(Customer, order.customer_id)
    if customer is None:
        return None
    shop_bot_instance = bot_manager.customer_bot(shop_bot.id, customer.platform) if bot_manager is not None else None
    return await digital_service.deliver_order(session, order, customer.telegram_id, shop_bot_instance, main_bot)


@router.callback_query(F.data.startswith("confirm_order:"))
async def cb_confirm_order(callback: CallbackQuery, session: AsyncSession, bot_manager=None) -> None:
    owner = await _current_owner(callback, session)
    shop_bot = await shop_bot_service.get_by_owner(session, owner) if owner else None
    if shop_bot is None:
        await callback.answer(texts.GENERIC_ERROR, show_alert=True)
        return

    order_id = int(callback.data.split(":")[1])
    order = await order_service.get_owned_by_id(session, order_id, shop_bot.id)
    if order is None:
        await callback.answer(texts.GENERIC_ERROR, show_alert=True)
        return

    if order.confirmed:
        await callback.answer(texts.ORDER_ALREADY_CONFIRMED, show_alert=True)
        return

    prev_status = order.status
    confirmed = await order_service.confirm_order(session, order)
    if not confirmed:
        # یک `answer()` دوباره مجاز نیست و باعثِ «دکمه مرده» شدنِ اخطار می‌شد؛ اینک
        # تنها یک بار پاسخ داده می‌شود و اخطارِ «قبلاً تایید شده» واقعاً نمایش داده می‌شود.
        await callback.answer(texts.ORDER_ALREADY_CONFIRMED, show_alert=True)
        return
    await order_transition_service.record_event(session, order, prev_status, order.status, actor_type="owner")
    await callback.answer()

    delivery_status = await _deliver_digital_after_confirm(session, order, shop_bot, bot_manager, callback.bot)
    delivery_note = texts.digital_delivery_owner_note(delivery_status) if delivery_status else ""
    await _notify_manual_decision(session, shop_bot, [order], "confirmed", bot_manager)

    if order.product_id is not None:
        product = await product_service.get_by_id(session, order.product_id)
        if product is not None:
            remaining = product.stock_quantity if product.stock_quantity is not None else 0
            new_caption = (callback.message.caption or callback.message.text or "") + f"\n\n{texts.order_confirmed_stock_notification(product.name, remaining)}"
            if delivery_note:
                new_caption += f"\n\n{delivery_note}"
            next_label = texts.order_next_status_button_label(order.status)
            keyboard = keyboards.order_advance_status_keyboard(order.id, next_label) if next_label else None
            if callback.message.photo:
                await callback.message.edit_caption(caption=new_caption, reply_markup=keyboard)
            else:
                await callback.message.edit_text(new_caption, reply_markup=keyboard)
            return

    # اگه به محصولی وصل نبود (یا محصول پیدا نشد)، دکمه‌ی پیشروی وضعیت رو نشون می‌دیم
    next_label = texts.order_next_status_button_label(order.status)
    keyboard = keyboards.order_advance_status_keyboard(order.id, next_label) if next_label else None
    if callback.message.photo:
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    else:
        await callback.message.edit_reply_markup(reply_markup=keyboard)


@router.callback_query(F.data.startswith("reject_order:"))
async def cb_reject_order(callback: CallbackQuery, session: AsyncSession, bot_manager=None) -> None:
    owner = await _current_owner(callback, session)
    shop_bot = await shop_bot_service.get_by_owner(session, owner) if owner else None
    if shop_bot is None:
        await callback.answer(texts.GENERIC_ERROR, show_alert=True)
        return

    order_id = int(callback.data.split(":")[1])
    order = await order_service.get_owned_by_id(session, order_id, shop_bot.id)
    if order is None:
        await callback.answer(texts.GENERIC_ERROR, show_alert=True)
        return

    prev_status = order.status
    rejected = await order_service.reject_order(session, order)
    if rejected:
        await order_transition_service.record_event(session, order, prev_status, order.status, actor_type="owner")
    if not rejected:
        await callback.answer(texts.ORDER_CANNOT_REJECT, show_alert=True)
        return

    await _notify_manual_decision(session, shop_bot, [order], "rejected", bot_manager)
    await callback.answer(texts.ORDER_REJECTED_CONFIRMATION)
    new_caption = (callback.message.caption or callback.message.text or "") + f"\n\n{texts.ORDER_REJECTED_CONFIRMATION}"
    if callback.message.photo:
        await callback.message.edit_caption(caption=new_caption, reply_markup=None)
    else:
        await callback.message.edit_text(new_caption, reply_markup=None)


# -----------------------------------------------------------------------------
# تاییدِ/ردِ گروهیِ سفارشِ سبدِ خرید (فازِ ۳) — همه‌ی اقلامِ یه چک‌اوت با یه
# دکمه. عمداً منطقِ تکی (order_service.confirm_order/reject_order) رو دست
# نمی‌زنیم؛ فقط برایِ هر ردیفِ گروه صداش می‌زنیم. پیشروی‌کردنِ وضعیتِ هر قلم
# (پردازش/ارسال/تکمیل) هنوز فقط در سطحِ سرویس هست، نه دکمه‌ی گروهی — نگاه کنید
# به «باقی‌مانده» در docs/changelog-phase3.md.
# -----------------------------------------------------------------------------
@router.callback_query(F.data.startswith("confirm_cart_group:"))
async def cb_confirm_cart_group(callback: CallbackQuery, session: AsyncSession, bot_manager=None) -> None:
    owner = await _current_owner(callback, session)
    shop_bot = await shop_bot_service.get_by_owner(session, owner) if owner else None
    if shop_bot is None:
        await callback.answer(texts.GENERIC_ERROR, show_alert=True)
        return

    group_id = callback.data.split(":", 1)[1]
    orders = await order_service.get_by_cart_checkout_group(session, group_id, shop_bot.id)
    if not orders:
        await callback.answer(texts.GENERIC_ERROR, show_alert=True)
        return

    confirmed_any = False
    delivery_notes: list[str] = []
    for order in orders:
        prev_status = order.status
        if await order_service.confirm_order(session, order):
            if not confirmed_any:
                await order_transition_service.record_event(session, order, prev_status, order.status, actor_type="owner")
            confirmed_any = True
            status = await _deliver_digital_after_confirm(session, order, shop_bot, bot_manager, callback.bot)
            if status and status != "already":
                note = texts.digital_delivery_owner_note(status)
                if note and note not in delivery_notes:
                    delivery_notes.append(note)
    if not confirmed_any:
        await callback.answer(texts.ORDER_ALREADY_CONFIRMED, show_alert=True)
        return

    await _notify_manual_decision(session, shop_bot, orders, "confirmed", bot_manager)
    await callback.answer()
    suffix = "".join(f"\n\n{note}" for note in delivery_notes)
    await callback.message.edit_text(
        (callback.message.text or "") + f"\n\n{texts.CART_GROUP_CONFIRMED}" + suffix,
        reply_markup=keyboards.order_group_actions_keyboard(group_id, orders[0].status),
    )


@router.callback_query(F.data.startswith("reject_cart_group:"))
async def cb_reject_cart_group(callback: CallbackQuery, session: AsyncSession, bot_manager=None) -> None:
    owner = await _current_owner(callback, session)
    shop_bot = await shop_bot_service.get_by_owner(session, owner) if owner else None
    if shop_bot is None:
        await callback.answer(texts.GENERIC_ERROR, show_alert=True)
        return

    group_id = callback.data.split(":", 1)[1]
    orders = await order_service.get_by_cart_checkout_group(session, group_id, shop_bot.id)
    if not orders:
        await callback.answer(texts.GENERIC_ERROR, show_alert=True)
        return

    rejected_any = False
    for order in orders:
        prev_status = order.status
        if await order_service.reject_order(session, order):
            if not rejected_any:
                await order_transition_service.record_event(session, order, prev_status, order.status, actor_type="owner")
            rejected_any = True
    if not rejected_any:
        await callback.answer(texts.ORDER_CANNOT_REJECT, show_alert=True)
        return

    await _notify_manual_decision(session, shop_bot, orders, "rejected", bot_manager)
    await callback.answer(texts.CART_GROUP_REJECTED)
    await callback.message.edit_text((callback.message.text or "") + f"\n\n{texts.CART_GROUP_REJECTED}", reply_markup=None)


@router.callback_query(F.data.startswith("advance_order:"))
async def cb_advance_order(callback: CallbackQuery, session: AsyncSession) -> None:
    """
    پیش‌بردنِ دستیِ وضعیتِ یه سفارشِ تاییدشده (در حالِ آماده‌سازی → ارسال‌شده
    → تکمیل‌شده). این دکمه از صفحه‌ی جزئیاتِ سفارش (در آینده) یا مستقیم از
    پیامِ اطلاع‌رسانی صدا زده می‌شه.
    """
    owner = await _current_owner(callback, session)
    shop_bot = await shop_bot_service.get_by_owner(session, owner) if owner else None
    if shop_bot is None:
        await callback.answer(texts.GENERIC_ERROR, show_alert=True)
        return

    order_id = int(callback.data.split(":")[1])
    order = await order_service.get_owned_by_id(session, order_id, shop_bot.id)
    if order is None:
        await callback.answer(texts.GENERIC_ERROR, show_alert=True)
        return

    prev_status = order.status
    new_status = await order_service.advance_status(session, order)
    if new_status is not None:
        await order_transition_service.record_event(session, order, prev_status, new_status, actor_type="owner")
    if new_status is None:
        await callback.answer(texts.ORDER_CANNOT_ADVANCE, show_alert=True)
        return

    await callback.answer(texts.order_status_advanced_notification(new_status))
    next_label = texts.order_next_status_button_label(new_status)
    keyboard = keyboards.order_advance_status_keyboard(order.id, next_label) if next_label else None
    new_text = f"{texts.order_status_advanced_notification(new_status)}\n\nخلاصه: {order.summary}"
    if callback.message.photo:
        await callback.message.edit_caption(caption=new_text, reply_markup=keyboard)
    else:
        await callback.message.edit_text(new_text, reply_markup=keyboard)
