from __future__ import annotations

import asyncio
import logging
import time

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import CommandStart
from aiogram.types import BufferedInputFile, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.main_bot import texts as main_texts
from app.bots.shop_bot import texts
from app.database.models import AuditEventType, ModerationAction, TenantMode, WalletTransactionReason
from app.database.session import session_scope
from app.services import (
    ai_context,
    ai_pool_service,
    ai_service,
    audit_log_service,
    bot_error_service,
    channel_knowledge_service,
    conversation_service,
    customer_service,
    moderation_service,
    order_detection_service,
    order_service,
    product_service,
    shop_bot_service,
    shop_owner_service,
    wallet_service,
)
from app.services.admin_settings_service import get_admin_settings
from app.services.rate_limiter import rate_limiter

logger = logging.getLogger(__name__)

router = Router(name="shop_customer")

ORDER_DEDUP_WINDOW_MINUTES = 10

# چند پیامِ پشت‌سرهمِ مشتری رو با هم جمع می‌کنیم و یه‌جا پردازش می‌کنیم، تا اگه
# مشتری ۳ تا پیامِ جدا فرستاد، ربات ۳ بار جدا جواب نده (مثلاً ۳ بار سلام نکنه).
DEBOUNCE_SECONDS = 3.0
MAX_BUFFER_WAIT_SECONDS = 10.0

_pending_buffers: dict[tuple[int, int], list[str]] = {}
_pending_tasks: dict[tuple[int, int], asyncio.Task] = {}
_pending_started_at: dict[tuple[int, int], float] = {}


@router.message(CommandStart())
async def customer_start(message: Message, session: AsyncSession) -> None:
    shop_bot = await shop_bot_service.get_by_bot_telegram_id(session, message.bot.id)
    if shop_bot is not None:
        await customer_service.get_or_create_customer(
            session, shop_bot.id, message.from_user.id, message.from_user.first_name, message.from_user.username
        )
    await message.answer(texts.SHOP_WELCOME)


async def _check_access(message: Message, session: AsyncSession, shop_bot, main_bot: Bot) -> bool:
    """چک‌های مشترکِ همه‌ی انواعِ پیام (متن/عکس/صدا): حالتِ تعمیر + موجودیِ کیف‌پول + محدودیتِ نرخ."""
    admin_settings = await get_admin_settings(session)
    if admin_settings.maintenance_mode:
        await message.answer(texts.PLATFORM_MAINTENANCE_REPLY)
        return False

    owner = await shop_owner_service.get_by_id(session, shop_bot.shop_owner_id)
    if owner is None or owner.wallet_balance_toman <= 0:
        await message.answer(texts.SHOP_UNAVAILABLE)
        if owner is not None and await wallet_service.try_claim_empty_notification(session, owner):
            try:
                await main_bot.send_message(owner.telegram_id, main_texts.wallet_empty_notification())
            except TelegramAPIError:
                logger.exception("اطلاع‌رسانیِ اتمامِ کیف‌پول به فروشگاه‌دار %s ناموفق بود.", owner.telegram_id)
        return False

    if not rate_limiter.check_and_record(
        shop_bot.id, message.from_user.id, admin_settings.rate_limit_max_messages, admin_settings.rate_limit_window_seconds
    ):
        await message.answer(texts.RATE_LIMITED)
        return False

    return True


async def _deduct_and_notify(
    session: AsyncSession, owner, admin_settings, amount_toman: int, reason: WalletTransactionReason, main_bot: Bot
) -> None:
    """بعدِ فراخوانیِ موفقِ هوش مصنوعی، هزینه رو از کیف‌پول کم می‌کنه و در صورتِ لزوم به فروشگاه‌دار خبر می‌ده.
    این تابع هیچ‌وقت به مشتری خطا نشون نمی‌ده؛ فقط خودِ فروشگاه‌دار (از طریقِ ربات اصلی) مطلع می‌شه."""
    success = await wallet_service.deduct(session, owner, amount_toman, reason)
    if not success:
        # موجودی در لحظه‌ی کسر کافی نبوده (مثلاً دقیقاً همین چند تومنِ آخر رو یه پیامِ هم‌زمانِ دیگه مصرف کرده).
        # چون جوابِ هوش مصنوعی از قبل تولید و برای مشتری فرستاده شده، این کمبودِ جزئی رو نادیده می‌گیریم
        # و اجازه نمی‌دیم تجربه‌ی مشتری خراب بشه؛ فقط لاگ می‌کنیم.
        logger.warning("کسرِ کیف‌پول برای فروشگاه‌دار %s ناموفق بود (موجودیِ ناکافی در لحظه‌ی کسر).", owner.id)

    if owner.wallet_balance_toman <= 0:
        if await wallet_service.try_claim_empty_notification(session, owner):
            try:
                await main_bot.send_message(owner.telegram_id, main_texts.wallet_empty_notification())
            except TelegramAPIError:
                logger.exception("اطلاع‌رسانیِ اتمامِ کیف‌پول به فروشگاه‌دار %s ناموفق بود.", owner.telegram_id)
    elif owner.wallet_balance_toman < admin_settings.wallet_low_balance_warning_toman:
        if await wallet_service.try_claim_low_balance_notification(session, owner):
            try:
                await main_bot.send_message(
                    owner.telegram_id, main_texts.wallet_low_balance_notification(owner.wallet_balance_toman)
                )
            except TelegramAPIError:
                logger.exception("اطلاع‌رسانیِ کمبودِ موجودیِ کیف‌پول به فروشگاه‌دار %s ناموفق بود.", owner.telegram_id)


@router.message(F.text)
async def customer_message(message: Message, session: AsyncSession, main_bot: Bot) -> None:
    shop_bot = await shop_bot_service.get_by_bot_telegram_id(session, message.bot.id)
    if shop_bot is None:
        return
    if not await _check_access(message, session, shop_bot, main_bot):
        return

    await customer_service.get_or_create_customer(
        session, shop_bot.id, message.from_user.id, message.from_user.first_name, message.from_user.username
    )

    _schedule_debounced_processing(shop_bot.id, message.from_user.id, message.text, message.bot, main_bot)


def _schedule_debounced_processing(shop_bot_id: int, customer_tg_id: int, text: str, shop_bot_instance: Bot, main_bot: Bot) -> None:
    key = (shop_bot_id, customer_tg_id)
    _pending_buffers.setdefault(key, []).append(text)

    now = time.monotonic()
    started_at = _pending_started_at.setdefault(key, now)

    existing_task = _pending_tasks.get(key)
    if existing_task is not None and not existing_task.done():
        existing_task.cancel()

    elapsed = now - started_at
    delay = min(DEBOUNCE_SECONDS, max(0.3, MAX_BUFFER_WAIT_SECONDS - elapsed))

    task = asyncio.create_task(_wait_then_process(key, delay, shop_bot_instance, main_bot))
    _pending_tasks[key] = task


async def _wait_then_process(key: tuple[int, int], delay: float, shop_bot_instance: Bot, main_bot: Bot) -> None:
    try:
        await asyncio.sleep(delay)
    except asyncio.CancelledError:
        return  # یه پیامِ تازه رسید و این تسک لغو شد؛ تسکِ جدید مسئولیت رو به عهده گرفته

    messages = _pending_buffers.pop(key, [])
    _pending_started_at.pop(key, None)
    _pending_tasks.pop(key, None)
    if not messages:
        return

    combined_text = "\n".join(messages)
    shop_bot_id, customer_tg_id = key

    try:
        async with session_scope() as session:
            await _generate_and_send_reply(session, shop_bot_id, customer_tg_id, combined_text, shop_bot_instance, main_bot)
    except Exception:
        logger.exception("پردازشِ پیام‌های جمع‌شده‌ی مشتری %s در فروشگاه %s با خطا مواجه شد.", customer_tg_id, shop_bot_id)


async def _generate_and_send_reply(
    session: AsyncSession, shop_bot_id: int, customer_tg_id: int, combined_text: str, shop_bot_instance: Bot, main_bot: Bot
) -> None:
    shop_bot = await shop_bot_service.get_by_id(session, shop_bot_id)
    if shop_bot is None or not shop_bot.is_active:
        return

    admin_settings = await get_admin_settings(session)

    matched_rule = await moderation_service.check_text(session, combined_text)
    if matched_rule is not None and matched_rule.action != ModerationAction.WARN:
        await audit_log_service.log(
            session,
            AuditEventType.MODERATION_MATCH,
            shop_bot_id=shop_bot_id,
            actor_telegram_id=customer_tg_id,
            details=f"الگو: {matched_rule.pattern} | اکشن: {matched_rule.action} | دسته: {matched_rule.category or '-'}",
        )
        await shop_bot_instance.send_message(customer_tg_id, texts.MODERATION_BLOCKED_REPLY)
        if matched_rule.action == ModerationAction.REVIEW:
            owner_for_review = await shop_owner_service.get_by_id(session, shop_bot.shop_owner_id)
            if owner_for_review is not None:
                try:
                    await main_bot.send_message(
                        owner_for_review.telegram_id, main_texts.moderation_review_notification(matched_rule.category)
                    )
                except TelegramAPIError:
                    logger.exception("اطلاع‌رسانیِ نیازِ بازبینیِ محتوا به فروشگاه‌دار %s ناموفق بود.", owner_for_review.telegram_id)
        return
    if matched_rule is not None:
        # WARN: فقط ثبت می‌شه، مکالمه به‌طورِ عادی ادامه پیدا می‌کنه.
        await audit_log_service.log(
            session,
            AuditEventType.MODERATION_MATCH,
            shop_bot_id=shop_bot_id,
            actor_telegram_id=customer_tg_id,
            details=f"الگو: {matched_rule.pattern} | اکشن: warn | دسته: {matched_rule.category or '-'}",
        )

    customer = await customer_service.get_or_create_customer(session, shop_bot_id, customer_tg_id, None, None)
    owner = await shop_owner_service.get_by_id(session, shop_bot.shop_owner_id)

    if owner is None or owner.wallet_balance_toman <= 0:
        # موجودیِ کیف‌پول توی فاصله‌ی جمع‌آوریِ پیام‌ها (debounce) به صفر رسیده؛
        # از فراخوانیِ هوش مصنوعی صرف‌نظر می‌کنیم تا هزینه‌ی بی‌فایده به فروشگاه‌دار تحمیل نشه.
        await shop_bot_instance.send_message(customer_tg_id, texts.SHOP_UNAVAILABLE)
        return

    if not admin_settings.ai_api_key:
        logger.warning("کلید API هوش مصنوعی هنوز تنظیم نشده؛ پاسخ‌گویی به مشتری ممکن نیست.")
        await shop_bot_instance.send_message(customer_tg_id, texts.AI_ERROR_REPLY)
        await bot_error_service.log_error(session, shop_bot_id)
        return

    products = await product_service.get_active_by_shop_bot(session, shop_bot_id)
    knowledge = await channel_knowledge_service.get_recent_knowledge(session, shop_bot_id, admin_settings.knowledge_items_limit)
    system_prompt = ai_context.build_system_prompt(shop_bot, products, knowledge, admin_settings.global_ai_system_prompt)
    history = await conversation_service.get_recent_history(session, customer.id, admin_settings.conversation_history_limit)

    ai = await ai_pool_service.build_ai_service(session, admin_settings, "chat")
    if ai is None:
        logger.error("هیچ کلیدِ AI‌ای (نه استخر، نه تنظیماتِ قدیمی) برای فروشگاه %s تنظیم نشده.", shop_bot_id)
        await shop_bot_instance.send_message(customer_tg_id, texts.AI_ERROR_REPLY)
        return
    try:
        ai_result = await ai.get_reply(system_prompt, history, combined_text)
    except ai_service.AiServiceError:
        logger.exception("فراخوانیِ هوش مصنوعی برای مشتری %s در فروشگاه %s ناموفق بود.", customer_tg_id, shop_bot_id)
        await shop_bot_instance.send_message(customer_tg_id, texts.AI_ERROR_REPLY)
        await bot_error_service.log_error(session, shop_bot_id)
        return
    reply = ai_result.text

    await conversation_service.save_turn(session, customer.id, combined_text, reply)
    await shop_bot_instance.send_message(customer_tg_id, reply)

    cost = wallet_service.estimate_chat_cost(admin_settings, ai_result.total_tokens)
    await _deduct_and_notify(session, owner, admin_settings, cost, WalletTransactionReason.CHAT_MESSAGE, main_bot)

    full_history = history + [{"role": "user", "content": combined_text}, {"role": "assistant", "content": reply}]
    asyncio.create_task(_detect_and_notify_order(shop_bot_id, customer.id, full_history, main_bot))


@router.message(F.photo)
async def customer_photo(message: Message, session: AsyncSession, main_bot: Bot) -> None:
    shop_bot = await shop_bot_service.get_by_bot_telegram_id(session, message.bot.id)
    if shop_bot is None:
        return
    if not await _check_access(message, session, shop_bot, main_bot):
        return

    await customer_service.get_or_create_customer(
        session, shop_bot.id, message.from_user.id, message.from_user.first_name, message.from_user.username
    )
    owner = await shop_owner_service.get_by_id(session, shop_bot.shop_owner_id)
    admin_settings = await get_admin_settings(session)

    customer_name = message.from_user.first_name or (f"@{message.from_user.username}" if message.from_user.username else str(message.from_user.id))
    caption_note = f"\n\nمتنِ همراهِ عکس: {message.caption}" if message.caption else ""

    # نکته‌ی مهم: file_id عکس فقط برای بات‌اینستنسِ *همون* رباتی معتبره که عکس رو
    # دریافت کرده (اینجا ربات فروشگاهی). برای فرستادنِ همون عکس به فروشگاه‌دار از
    # طریقِ ربات اصلی (main_bot)، اول باید بایت‌های عکس رو با ربات فروشگاهی دانلود
    # کنیم و بعد به‌عنوانِ یه فایلِ تازه (BufferedInputFile) با main_bot آپلودش کنیم؛
    # همون file_id رو مستقیم به main_bot دادن کار نمی‌کنه.
    image_bytes: bytes | None = None
    try:
        file_io = await message.bot.download(message.photo[-1].file_id)
        image_bytes = file_io.read()
    except Exception:
        logger.exception("دانلودِ عکسِ مشتری %s ناموفق بود.", message.from_user.id)

    analysis_note = ""
    if image_bytes is not None and owner is not None and owner.wallet_balance_toman > 0:
        try:
            ai = await ai_pool_service.build_ai_service(session, admin_settings, "vision")
            if ai is None:
                raise ai_service.AiServiceError("هیچ کلیدِ AI‌ای با قابلیتِ vision تنظیم نشده.")
            image_analysis_result = await ai.analyze_image(texts.RECEIPT_ANALYSIS_PROMPT, image_bytes)
            analysis_note = f"\n\n🔎 بررسیِ خودکارِ تصویر:\n{image_analysis_result.text}"
            cost = wallet_service.estimate_photo_cost(admin_settings)
            await _deduct_and_notify(session, owner, admin_settings, cost, WalletTransactionReason.PHOTO_ANALYSIS, main_bot)
        except ai_service.AiServiceError:
            logger.exception("بررسیِ هوشمندِ تصویرِ ارسالی توسطِ مشتری %s ناموفق بود.", message.from_user.id)
        except Exception:
            logger.exception("تحلیلِ عکسِ مشتری %s ناموفق بود.", message.from_user.id)

    if image_bytes is not None:
        try:
            await main_bot.send_photo(
                owner.telegram_id,
                BufferedInputFile(image_bytes, filename="customer_photo.jpg"),
                caption=texts.customer_photo_forward_caption(customer_name, caption_note, analysis_note),
            )
        except TelegramAPIError:
            logger.exception("فوروارد کردنِ عکسِ مشتری به فروشگاه‌دار %s ناموفق بود.", owner.telegram_id)

    await message.answer(texts.PHOTO_RECEIVED_ACK)


@router.message(F.voice)
async def customer_voice(message: Message, session: AsyncSession, main_bot: Bot) -> None:
    shop_bot = await shop_bot_service.get_by_bot_telegram_id(session, message.bot.id)
    if shop_bot is None:
        return
    if not await _check_access(message, session, shop_bot, main_bot):
        return

    await customer_service.get_or_create_customer(
        session, shop_bot.id, message.from_user.id, message.from_user.first_name, message.from_user.username
    )

    admin_settings = await get_admin_settings(session)
    owner = await shop_owner_service.get_by_id(session, shop_bot.shop_owner_id)
    if owner is None or owner.wallet_balance_toman <= 0:
        await message.answer(texts.SHOP_UNAVAILABLE)
        return

    ai = await ai_pool_service.build_ai_service(session, admin_settings, "chat")
    if ai is None:
        await message.answer(texts.AI_ERROR_REPLY)
        return

    try:
        file_io = await message.bot.download(message.voice.file_id)
        audio_bytes = file_io.read()
        transcript = await ai.transcribe_audio(audio_bytes, filename="voice.ogg")
    except ai_service.AiServiceError:
        logger.exception("رونویسیِ پیامِ صوتیِ مشتری %s ناموفق بود.", message.from_user.id)
        await message.answer(texts.VOICE_TRANSCRIBE_ERROR)
        return
    except Exception:
        logger.exception("دانلودِ پیامِ صوتیِ مشتری %s ناموفق بود.", message.from_user.id)
        await message.answer(texts.VOICE_TRANSCRIBE_ERROR)
        return

    transcript = transcript.strip()
    if not transcript:
        await message.answer(texts.VOICE_TRANSCRIBE_ERROR)
        return

    cost = wallet_service.estimate_voice_cost(admin_settings)
    await _deduct_and_notify(session, owner, admin_settings, cost, WalletTransactionReason.VOICE_TRANSCRIPTION, main_bot)

    _schedule_debounced_processing(shop_bot.id, message.from_user.id, transcript, message.bot, main_bot)


async def _detect_and_notify_order(
    shop_bot_id: int,
    customer_id: int,
    full_history: list[dict[str, str]],
    main_bot: Bot,
) -> None:
    try:
        async with session_scope() as session:
            shop_bot = await shop_bot_service.get_by_id(session, shop_bot_id)
            if shop_bot is None:
                return
            owner = await shop_owner_service.get_by_id(session, shop_bot.shop_owner_id)
            if owner is None or owner.wallet_balance_toman <= 0:
                # موجودی خالیه؛ از فراخوانیِ کلاسیفایر (که خودش هزینه داره) صرف‌نظر می‌کنیم.
                # مشتری همین الان جوابِ اصلیِ چت رو گرفته، این فقط یه قابلیتِ جانبیِ تشخیصِ سفارشه.
                return

            admin_settings = await get_admin_settings(session)
            products = await product_service.get_active_by_shop_bot(session, shop_bot_id)

            ai = await ai_pool_service.build_ai_service(session, admin_settings, "chat")
            if ai is None:
                return
            is_consultation = shop_bot.tenant_mode == TenantMode.CONSULTATION
            result, tokens_used = await order_detection_service.detect_order(ai, full_history, products, is_consultation)

            if tokens_used is not None:
                cost = wallet_service.estimate_order_detection_cost(admin_settings, tokens_used)
                await _deduct_and_notify(session, owner, admin_settings, cost, WalletTransactionReason.ORDER_DETECTION, main_bot)

            if result is None:
                return

            recent = await order_service.get_recent_duplicate(
                session, customer_id, result["type"], result.get("product_id"), minutes=ORDER_DEDUP_WINDOW_MINUTES
            )
            if recent is not None:
                return

            order = await order_service.create_order(
                session,
                shop_bot_id,
                customer_id,
                result["type"],
                result["summary"],
                result["estimated_value_toman"],
                result.get("product_id"),
                result.get("quantity"),
            )

            customer = await customer_service.get_by_id(session, customer_id)

            from app.bots.main_bot import keyboards as main_keyboards

            keyboard = main_keyboards.order_notification_keyboard(order.id) if order.product_id is not None else None

            try:
                await main_bot.send_message(
                    owner.telegram_id, main_texts.order_detected_notification(order, customer), reply_markup=keyboard
                )
            except TelegramAPIError:
                logger.exception("اطلاع‌رسانیِ سفارش/مشاوره‌ی تشخیص‌داده‌شده به فروشگاه‌دار %s ناموفق بود.", owner.telegram_id)
    except Exception:
        logger.exception("تسکِ پس‌زمینه‌ی تشخیصِ سفارش/مشاوره با خطا مواجه شد.")


@router.message()
async def customer_unsupported_message(message: Message) -> None:
    await message.answer(texts.NON_TEXT_MESSAGE)
