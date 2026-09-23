from __future__ import annotations

import logging
import secrets

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.main_bot import keyboards, texts
from app.bots.main_bot.states import (
    AiInstructionsStates,
    ChannelKnowledgeStates,
    PaymentStates,
    PreviewStates,
    ShopBotTokenStates,
)
from app.config import settings
from app.database.models import Customer, DiscountCode, OrderConsultation, PaymentPurpose, TenantMode
from app.services import (
    admin_role_service,
    ai_context,
    ai_pool_service,
    ai_service,
    bale_service,
    channel_knowledge_service,
    discount_service,
    excel_export_service,
    order_service,
    payment_service,
    product_service,
    referral_service,
    shop_bot_service,
    shop_owner_service,
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
    if stripped.lstrip("-").isdigit():
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
        shop_bot = await shop_bot_service.get_by_owner(session, owner)
        keyboard = keyboards.shop_owner_panel_keyboard(shop_bot.tenant_mode if shop_bot else None)
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

    is_brand_new = await shop_bot_service.get_by_owner(session, owner) is None
    shop_bot = await shop_bot_service.upsert_shop_bot(session, owner, raw_token, me.id, me.username)
    await state.clear()
    await message.answer(texts.shop_bot_token_saved(me.username))

    try:
        await bot_manager.register(shop_bot)
    except Exception:
        logger.exception("ثبتِ ربات فروشگاهی %s در ShopBotManager ناموفق بود.", shop_bot.id)

    if is_brand_new:
        await message.answer(texts.ASK_TENANT_MODE, reply_markup=keyboards.tenant_mode_keyboard())


@router.callback_query(F.data.startswith("set_tenant_mode:"))
async def cb_set_tenant_mode(callback: CallbackQuery, session: AsyncSession) -> None:
    owner = await _current_owner(callback, session)
    shop_bot = await shop_bot_service.get_by_owner(session, owner) if owner else None
    if shop_bot is None:
        await callback.answer(texts.SHOP_BOT_NOT_SET_UP, show_alert=True)
        return

    mode_value = callback.data.split(":")[1]
    shop_bot.tenant_mode = TenantMode.CONSULTATION if mode_value == "consultation" else TenantMode.SALES
    await callback.answer()
    await callback.message.edit_text(texts.tenant_mode_saved_confirmation(shop_bot.tenant_mode))


@router.message(F.text == "🔀 نوعِ کسب‌وکار")
async def open_tenant_mode(message: Message, session: AsyncSession) -> None:
    owner = await _current_owner(message, session)
    shop_bot = await shop_bot_service.get_by_owner(session, owner)
    if shop_bot is None:
        await message.answer(texts.SHOP_BOT_NOT_SET_UP)
        return
    await message.answer(texts.tenant_mode_current(shop_bot.tenant_mode), reply_markup=keyboards.tenant_mode_keyboard())


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
    await message.answer(texts.PREVIEW_END_TEXT, reply_markup=keyboards.shop_owner_panel_keyboard(tenant_mode))


@router.message(PreviewStates.active, F.text)
async def preview_message(message: Message, session: AsyncSession) -> None:
    owner = await _current_owner(message, session)
    shop_bot = await shop_bot_service.get_by_owner(session, owner)
    products = await product_service.get_active_by_shop_bot(session, shop_bot.id)

    admin_settings = await get_admin_settings(session)
    knowledge = await channel_knowledge_service.get_recent_knowledge(session, shop_bot.id, admin_settings.knowledge_items_limit)
    system_prompt = ai_context.build_system_prompt(shop_bot, products, knowledge, admin_settings.global_ai_system_prompt)
    ai = await ai_pool_service.build_ai_service(session, admin_settings, "chat")
    if ai is None:
        await message.answer(texts.GENERIC_ERROR)
        return
    try:
        ai_result = await ai.get_reply(system_prompt, [], message.text)
    except ai_service.AiServiceError:
        logger.exception("فراخوانیِ هوش مصنوعی در حالت پیش‌نمایش ناموفق بود.")
        await message.answer(texts.GENERIC_ERROR)
        return

    await message.answer(ai_result.text)


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
    await message.answer(texts.shop_stats_text(stats))


# =============================================================================
# =============================================================================
# کیف‌پول و پرداخت
# =============================================================================
@router.message(F.text == "💰 کیف‌پول")
async def open_wallet(message: Message, session: AsyncSession) -> None:
    owner = await _current_owner(message, session)
    await message.answer(texts.wallet_status_text(owner.wallet_balance_toman), reply_markup=keyboards.wallet_topup_action_keyboard())


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
    await callback.message.answer(texts.ASK_TOPUP_AMOUNT, reply_markup=keyboards.topup_amount_keyboard())


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
async def cb_topup_amount(callback: CallbackQuery, state: FSMContext) -> None:
    choice = callback.data.split(":", 1)[1]
    if choice == "custom":
        await state.set_state(PaymentStates.waiting_topup_amount)
        await callback.answer()
        await callback.message.answer(texts.ASK_CUSTOM_TOPUP_AMOUNT)
        return

    amount = int(choice)
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
async def topup_custom_amount_received(message: Message, state: FSMContext) -> None:
    try:
        amount = int(message.text.strip())
        if amount < 10_000:
            raise ValueError
    except ValueError:
        await message.answer(texts.INVALID_TOPUP_AMOUNT)
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


@router.message(PaymentStates.waiting_receipt, F.text)
async def payment_receipt_wrong_type(message: Message) -> None:
    await message.answer(texts.ASK_RECEIPT_PHOTO_NOT_TEXT)


@router.message(PaymentStates.waiting_receipt, F.photo)
async def payment_receipt_received(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    payment = await payment_service.get_by_id(session, data["payment_id"])
    await payment_service.attach_receipt(session, payment, message.photo[-1].file_id)

    owner = await _current_owner(message, session)
    await state.clear()
    await message.answer(texts.RECEIPT_RECEIVED_PENDING_APPROVAL)

    for admin_id in settings.admin_ids:
        try:
            await message.bot.send_photo(
                admin_id,
                message.photo[-1].file_id,
                caption=texts.admin_new_payment_notification(payment, owner),
                reply_markup=keyboards.admin_payment_approval_keyboard(payment.id),
            )
        except TelegramAPIError:
            logger.exception("اطلاع‌رسانیِ پرداختِ جدید به ادمین %s ناموفق بود.", admin_id)


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

    if not admin_settings.bale_pay_enabled or not admin_settings.bale_provider_token or not settings.bale_bot_token:
        await callback.answer()
        await callback.message.answer(texts.BALE_PAY_ERROR)
        return

    purpose = PaymentPurpose(data.get("purpose", PaymentPurpose.WALLET_TOPUP.value))
    description = "شارژ کیف‌پول کسب‌وکار هوشمند" if purpose == PaymentPurpose.WALLET_TOPUP else "خرید اشتراک کسب‌وکار هوشمند"
    invoice_payload = f"payment-{owner.id}-{secrets.token_hex(8)}"
    # مبلغ‌های داخلیِ ما همیشه تومانن؛ بله‌پی طبقِ فایلِ ارائه‌شده ریال می‌خواد (۱ تومان = ۱۰ ریال).
    amount_rial = data["final_amount"] * 10
    try:
        pay_url = await bale_service.create_invoice_link(
            settings.bale_bot_token,
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
    await message.answer(texts.CHOOSE_EXCEL_EXPORT, reply_markup=keyboards.excel_export_choice_keyboard())


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
        content = await excel_export_service.build_customers_workbook(session, shop_bot.id)
        filename = "customers.xlsx"
    else:
        count = await session.scalar(select(func.count()).select_from(OrderConsultation).where(OrderConsultation.shop_bot_id == shop_bot.id))
        if not count:
            await callback.message.answer(texts.EXCEL_EXPORT_EMPTY)
            return
        content = await excel_export_service.build_orders_workbook(session, shop_bot.id)
        filename = "orders.xlsx"

    await callback.message.answer_document(BufferedInputFile(content, filename=filename), caption=texts.EXCEL_EXPORT_READY)


# =============================================================================
# ویرایش اطلاعات (استاب — هنوز پیاده‌سازی نشده)
# =============================================================================
@router.message(F.text == "✏️ ویرایش اطلاعات")
async def open_edit_info_stub(message: Message) -> None:
    await message.answer(texts.EDIT_INFO_COMING_SOON)


# =============================================================================
# پروفایل فروشگاه‌دار (این‌جلسه)
# =============================================================================
@router.message(F.text == "👤 پروفایل من")
async def open_profile(message: Message, session: AsyncSession) -> None:
    owner = await _current_owner(message, session)
    shop_bot = await shop_bot_service.get_by_owner(session, owner)
    await message.answer(texts.owner_profile_text(owner, shop_bot, owner.wallet_balance_toman))


# =============================================================================
# تایید سفارش و کسر موجودی (این‌جلسه — feature #7)
# =============================================================================
@router.callback_query(F.data.startswith("confirm_order:"))
async def cb_confirm_order(callback: CallbackQuery, session: AsyncSession) -> None:
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

    confirmed = await order_service.confirm_order(session, order)
    await callback.answer()
    if not confirmed:
        await callback.answer(texts.ORDER_ALREADY_CONFIRMED, show_alert=True)
        return

    if order.product_id is not None:
        product = await product_service.get_by_id(session, order.product_id)
        if product is not None:
            remaining = product.stock_quantity if product.stock_quantity is not None else 0
            new_caption = (callback.message.caption or callback.message.text or "") + f"\n\n{texts.order_confirmed_stock_notification(product.name, remaining)}"
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
async def cb_reject_order(callback: CallbackQuery, session: AsyncSession) -> None:
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

    rejected = await order_service.reject_order(session, order)
    if not rejected:
        await callback.answer(texts.ORDER_CANNOT_REJECT, show_alert=True)
        return

    await callback.answer(texts.ORDER_REJECTED_CONFIRMATION)
    new_caption = (callback.message.caption or callback.message.text or "") + f"\n\n{texts.ORDER_REJECTED_CONFIRMATION}"
    if callback.message.photo:
        await callback.message.edit_caption(caption=new_caption, reply_markup=None)
    else:
        await callback.message.edit_text(new_caption, reply_markup=None)


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

    new_status = await order_service.advance_status(session, order)
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
