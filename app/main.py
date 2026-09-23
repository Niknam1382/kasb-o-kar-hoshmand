from __future__ import annotations

import asyncio
import logging
import time
from collections import OrderedDict

from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import select

from app.bots.common.channel_knowledge import create_channel_knowledge_router
from app.bots.common.middlewares import DbSessionMiddleware
from app.bots.main_bot import texts as main_texts
from app.bots.main_bot.router import build_main_router
from app.bots.shop_bot.router import build_shop_router
from app.config import RunMode, settings
from app.database.models import PaymentPurpose, PaymentStatus
from app.database.session import session_scope
from app.services import ai_service, bale_service, payment_service, scheduler, shop_bot_service, shop_owner_service, zarinpal_service
from app.services.admin_settings_service import get_admin_settings
from app.services.bot_manager import ShopBotManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_main_dispatcher(bot_manager: ShopBotManager) -> Dispatcher:
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.update.middleware(DbSessionMiddleware())
    dispatcher["bot_manager"] = bot_manager
    dispatcher.include_router(build_main_router())
    dispatcher.include_router(create_channel_knowledge_router("main_channel_knowledge"))
    return dispatcher


def create_shop_dispatcher(main_bot: Bot) -> Dispatcher:
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.update.middleware(DbSessionMiddleware())
    dispatcher["main_bot"] = main_bot
    dispatcher.include_router(build_shop_router())
    dispatcher.include_router(create_channel_knowledge_router("shop_channel_knowledge"))
    return dispatcher


async def _load_active_shop_bots(bot_manager: ShopBotManager) -> None:
    async with session_scope() as session:
        shop_bots = await shop_bot_service.get_all_active(session)
    await bot_manager.load_all(shop_bots)
    logger.info("%d ربات فروشگاهی‌ِ فعال بارگذاری شد.", len(shop_bots))


async def _notify_payment_result(main_bot: Bot, owner_telegram_id: int, is_topup: bool, wallet_amount_toman: int | None, reward_info: dict | None) -> None:
    try:
        await main_bot.send_message(owner_telegram_id, main_texts.payment_approved_notification(is_topup, wallet_amount_toman))
    except TelegramAPIError:
        logger.exception("اطلاع‌رسانیِ تاییدِ پرداختِ زرین‌پال به فروشگاه‌دار %s ناموفق بود.", owner_telegram_id)

    if not reward_info:
        return

    try:
        await main_bot.send_message(
            reward_info["referrer_telegram_id"], main_texts.referrer_reward_notification(reward_info["amount_toman"])
        )
    except TelegramAPIError:
        logger.exception("اطلاع‌رسانیِ پاداشِ معرف به %s ناموفق بود.", reward_info["referrer_telegram_id"])
    try:
        await main_bot.send_message(
            reward_info["referred_telegram_id"], main_texts.referred_reward_notification(reward_info["amount_toman"])
        )
    except TelegramAPIError:
        logger.exception("اطلاع‌رسانیِ پاداشِ معرفی‌شده به %s ناموفق بود.", reward_info["referred_telegram_id"])


# =============================================================================
# حالت polling (RUN_MODE=polling)
# =============================================================================
async def run_polling() -> None:
    main_bot = Bot(token=settings.main_bot_token)
    shop_dispatcher = create_shop_dispatcher(main_bot)
    bot_manager = ShopBotManager(shop_dispatcher)
    main_dispatcher = create_main_dispatcher(bot_manager)

    await _load_active_shop_bots(bot_manager)

    stop_event = asyncio.Event()
    scheduler_task = asyncio.create_task(scheduler.run_periodic_tasks(main_bot, stop_event))

    try:
        await main_bot.delete_webhook(drop_pending_updates=True)
        await main_dispatcher.start_polling(main_bot)
    finally:
        stop_event.set()
        await scheduler_task
        await ai_service.close_http_session()
        await main_bot.session.close()


# =============================================================================
# حالت webhook + مسیرِ برگشتِ پرداخت زرین‌پال (همیشه فعال، صرف‌نظر از RUN_MODE)
# =============================================================================
app = FastAPI(title="کسب‌وکار هوشمند")

_state: dict = {}

# محافظت در برابرِ ارسالِ دوباره‌ی همون آپدیت توسطِ تلگرام (نادر ولی ممکنه،
# مخصوصاً اگه پاسخِ وب‌هوک کند باشه) — بدونِ این، یه پیامِ تکراری می‌تونست
# باعثِ کسرِ دوباره‌ی کیف‌پول برای همون یه پیامِ واقعی بشه. فقط برای وب‌هوک
# لازمه؛ حالتِ polling خودِ aiogram با آفست جلوی تکرار رو می‌گیره. حافظه‌ی
# داخلی (نه دیتابیس/Redis) کافیه چون پنجره‌ی تکرارِ تلگرام کوتاهه (ثانیه‌ها
# تا چند دقیقه)، نه چیزی که نیاز به ماندگاریِ بینِ ری‌استارت داشته باشه.
_MAX_SEEN_UPDATES = 2000
_seen_update_ids: OrderedDict[tuple[int, int], float] = OrderedDict()


def _is_duplicate_update(bot_id: int, update_id: int) -> bool:
    key = (bot_id, update_id)
    if key in _seen_update_ids:
        return True
    _seen_update_ids[key] = time.monotonic()
    if len(_seen_update_ids) > _MAX_SEEN_UPDATES:
        _seen_update_ids.popitem(last=False)
    return False


@app.on_event("startup")
async def on_startup() -> None:
    main_bot = Bot(token=settings.main_bot_token)
    shop_dispatcher = create_shop_dispatcher(main_bot)
    bot_manager = ShopBotManager(shop_dispatcher)
    main_dispatcher = create_main_dispatcher(bot_manager)

    _state["main_bot"] = main_bot
    _state["shop_dispatcher"] = shop_dispatcher
    _state["main_dispatcher"] = main_dispatcher
    _state["bot_manager"] = bot_manager
    _state["stop_event"] = asyncio.Event()

    await _load_active_shop_bots(bot_manager)

    if settings.run_mode == RunMode.WEBHOOK:
        webhook_url = f"{settings.webhook_base_url.rstrip('/')}/webhook/main"
        if not settings.main_bot_webhook_secret:
            logger.warning(
                "main_bot_webhook_secret در .env تنظیم نشده — وب‌هوکِ ربات اصلی بدونِ تاییدِ رمز کار "
                "می‌کنه (یعنی هرکسی که آدرسِ وب‌هوک رو حدس بزنه می‌تونه آپدیتِ جعلی بفرسته). قبل از "
                "production حتمًا یه رشته‌ی تصادفیِ بلند براش ست کنید."
            )
        await main_bot.set_webhook(
            webhook_url,
            secret_token=settings.main_bot_webhook_secret or None,
            drop_pending_updates=True,
        )
        logger.info("وب‌هوکِ ربات اصلی روی %s تنظیم شد.", webhook_url)
    else:
        await main_bot.delete_webhook(drop_pending_updates=True)
        _state["polling_task"] = asyncio.create_task(main_dispatcher.start_polling(main_bot))

    # وب‌هوکِ بله‌پی مستقل از run_mode ـه (چون فقط برای پرداخته، نه برای چت
    # کردن با مشتری) — اگه توکن ست شده باشه، همیشه ثبتش می‌کنیم.
    if settings.bale_bot_token:
        bale_webhook_url = f"{settings.webhook_base_url.rstrip('/')}/webhook/bale"
        try:
            await bale_service.set_webhook(settings.bale_bot_token, bale_webhook_url, settings.bale_webhook_secret or None)
            logger.info("وب‌هوکِ بله‌پی روی %s تنظیم شد.", bale_webhook_url)
        except bale_service.BaleError:
            logger.exception(
                "تنظیمِ وب‌هوکِ بله‌پی ناموفق بود — Bale Pay غیرفعال می‌مونه تا این مشکل برطرف بشه."
            )

    _state["scheduler_task"] = asyncio.create_task(scheduler.run_periodic_tasks(main_bot, _state["stop_event"]))


@app.on_event("shutdown")
async def on_shutdown() -> None:
    _state["stop_event"].set()
    await _state["scheduler_task"]

    polling_task = _state.get("polling_task")
    if polling_task is not None:
        polling_task.cancel()

    for shop_bot_id in _state["bot_manager"].registered_shop_bot_ids():
        await _state["bot_manager"].unregister(shop_bot_id, disable_in_db=False)

    # جلسه‌ی HTTP مشترکِ سرویسِ هوش مصنوعی رو هم می‌بندیم تا سوکت باز نمونه
    await ai_service.close_http_session()
    await _state["main_bot"].session.close()


def _is_valid_webhook_secret(provided_secret: str | None) -> bool:
    """
    مشابهِ رمزِ وب‌هوکِ ربات‌های فروشگاهی (پایینِ همین فایل)، ولی برای ربات اصلی
    از تنظیماتِ ثابتِ .env استفاده می‌کنیم چون فقط یه ربات اصلی داریم، نه یکی
    به‌ازای هر فروشگاه. اگه main_bot_webhook_secret ست نشده باشه (لاگِ هشدار
    موقعِ startup)، این چک رد می‌شه تا رفتارِ قبلی (ناامن ولی کارکردن) خراب نشه.
    """
    if not settings.main_bot_webhook_secret:
        return True
    return provided_secret == settings.main_bot_webhook_secret


@app.post("/webhook/main")
async def webhook_main(request: Request) -> Response:
    if not _is_valid_webhook_secret(request.headers.get("X-Telegram-Bot-Api-Secret-Token")):
        return Response(status_code=403)

    data = await request.json()
    update = Update.model_validate(data)
    if _is_duplicate_update(_state["main_bot"].id, update.update_id):
        return Response(status_code=200)
    await _state["main_dispatcher"].feed_update(_state["main_bot"], update)
    return Response(status_code=200)


@app.get("/health")
async def health_check() -> JSONResponse:
    """
    بررسیِ سلامت برای مانیتورینگ/لودبالانسر/داکر: اتصالِ دیتابیس رو با یه کوئریِ
    سبک تست می‌کنه و مطمئن می‌شه ربات‌ها موقعِ startup مقداردهی شدن. ۲۰۰ یعنی
    سالم؛ ۵۰۳ یعنی مشکل (تا لودبالانسر/داکر بفهمه نباید ترافیک بفرسته).
    """
    try:
        async with session_scope() as session:
            await session.execute(select(1))
    except Exception:
        logger.exception("بررسیِ سلامت: اتصال به دیتابیس ناموفق بود.")
        return JSONResponse(status_code=503, content={"status": "unhealthy", "database": "down"})

    if _state.get("main_bot") is None:
        return JSONResponse(status_code=503, content={"status": "unhealthy", "bot": "not_initialized"})

    return JSONResponse(status_code=200, content={"status": "ok"})


@app.post("/webhook/shop/{shop_bot_id}")
async def webhook_shop(shop_bot_id: int, request: Request) -> Response:
    bot_manager: ShopBotManager = _state["bot_manager"]
    bot = bot_manager.get_bot(shop_bot_id)
    if bot is None:
        return Response(status_code=404)

    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if secret != bot_manager.get_secret(shop_bot_id):
        return Response(status_code=403)

    data = await request.json()
    update = Update.model_validate(data)
    if _is_duplicate_update(bot.id, update.update_id):
        return Response(status_code=200)
    await _state["shop_dispatcher"].feed_update(bot, update)
    return Response(status_code=200)


@app.post("/webhook/bale")
async def webhook_bale(request: Request) -> Response:
    if not settings.bale_bot_token:
        return Response(status_code=404)
    if settings.bale_webhook_secret:
        secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if secret != settings.bale_webhook_secret:
            return Response(status_code=403)

    try:
        data = await request.json()
    except Exception:
        return Response(status_code=200)  # بدنه‌ی نامعتبر رو نادیده می‌گیریم، نه که با 4xx باعثِ retry بشیم

    pre_checkout = data.get("pre_checkout_query")
    if pre_checkout:
        await _handle_bale_pre_checkout(pre_checkout)
        return Response(status_code=200)

    successful_payment = (data.get("message") or {}).get("successful_payment")
    if successful_payment:
        await _handle_bale_successful_payment(successful_payment)
        return Response(status_code=200)

    return Response(status_code=200)


async def _handle_bale_pre_checkout(pre_checkout: dict) -> None:
    query_id = pre_checkout.get("id")
    invoice_payload = pre_checkout.get("invoice_payload")
    if not query_id:
        logger.error("pre_checkout_query بدونِ id از بله رسید: %r", pre_checkout)
        return

    async with session_scope() as session:
        payment = await payment_service.get_by_bale_payload(session, invoice_payload) if invoice_payload else None

    ok = payment is not None and payment.status == PaymentStatus.PENDING
    try:
        await bale_service.answer_pre_checkout_query(
            settings.bale_bot_token,
            query_id,
            ok=ok,
            error_message=None if ok else "این سفارش دیگه معتبر نیست یا قبلاً پردازش شده.",
        )
    except bale_service.BaleError:
        logger.exception("پاسخ‌دادن به pre_checkout_query بله ناموفق بود (query_id=%s).", query_id)


async def _handle_bale_successful_payment(successful_payment: dict) -> None:
    invoice_payload = successful_payment.get("invoice_payload")
    # طبقِ فایلِ ارائه‌شده این فیلد telegram_payment_charge_id نام داره؛ چون این
    # جزئیات مستقل تاییدنشده، هر دو نامِ محتمل رو امتحان می‌کنیم تا اگه بله
    # اسمِ دیگه‌ای گذاشته بود هم کار کنه.
    transaction_id = successful_payment.get("telegram_payment_charge_id") or successful_payment.get(
        "provider_payment_charge_id"
    )
    if not invoice_payload or not transaction_id:
        logger.error("successful_payment ناقص از بله رسید: %r", successful_payment)
        return

    async with session_scope() as session:
        payment = await payment_service.get_by_bale_payload(session, invoice_payload)
        if payment is None:
            logger.error("successful_payment برای payloadِ ناشناس رسید: %s", invoice_payload)
            return
        if payment.status != PaymentStatus.PENDING:
            # یعنی این وب‌هوک تکراریه (بله دوباره فرستاده) — قبلاً پردازش شده، پس کاری نمی‌کنیم.
            return

        # همیشه قبل از اعتبارکردنِ کیف‌پول، مستقل از خودِ سرورِ بله استعلام
        # می‌گیریم — این مهم‌ترین محافظت در برابرِ یه وب‌هوکِ جعلیه.
        try:
            transaction = await bale_service.inquire_transaction(settings.bale_bot_token, transaction_id)
        except bale_service.BaleError:
            logger.exception("استعلامِ تراکنشِ بله ناموفق بود (transaction_id=%s) — کیف‌پول شارژ نشد.", transaction_id)
            return

        status = str(transaction.get("status", "")).lower()
        if status not in ("successful", "success", "paid", "ok"):
            logger.error("استعلامِ تراکنشِ بله وضعیتِ نامعتبر برگردوند: %r", transaction)
            return

        _effect, reward_info = await payment_service.approve_bale_payment(session, payment, transaction_id)
        owner = await shop_owner_service.get_by_id(session, payment.shop_owner_id)
        owner_telegram_id = owner.telegram_id
        is_topup = payment.purpose == PaymentPurpose.WALLET_TOPUP
        wallet_amount_toman = payment.final_amount if is_topup else None

    await _notify_payment_result(_state["main_bot"], owner_telegram_id, is_topup, wallet_amount_toman, reward_info)


@app.get("/payment/zarinpal/callback")
async def zarinpal_callback(Authority: str, Status: str) -> HTMLResponse:
    if Status != "OK":
        return HTMLResponse(main_texts.ZARINPAL_PAYMENT_FAILED_PAGE)

    async with session_scope() as session:
        payment = await payment_service.get_by_zarinpal_authority(session, Authority)
        if payment is None or payment.status != PaymentStatus.PENDING:
            return HTMLResponse(main_texts.ZARINPAL_PAYMENT_FAILED_PAGE)

        admin_settings = await get_admin_settings(session)
        try:
            ref_id = await zarinpal_service.verify_payment(admin_settings.zarinpal_merchant_id, payment.final_amount, Authority)
        except zarinpal_service.ZarinpalError:
            logger.exception("تاییدِ پرداخت زرین‌پال با اتوریتیِ %s ناموفق بود.", Authority)
            return HTMLResponse(main_texts.ZARINPAL_PAYMENT_FAILED_PAGE)

        _effect, reward_info = await payment_service.approve_zarinpal_payment(session, payment, ref_id)
        owner = await shop_owner_service.get_by_id(session, payment.shop_owner_id)
        owner_telegram_id = owner.telegram_id
        is_topup = payment.purpose == PaymentPurpose.WALLET_TOPUP
        wallet_amount_toman = payment.final_amount if is_topup else None

    await _notify_payment_result(_state["main_bot"], owner_telegram_id, is_topup, wallet_amount_toman, reward_info)
    return HTMLResponse(main_texts.ZARINPAL_PAYMENT_SUCCESSFUL_PAGE)


if __name__ == "__main__":
    if settings.run_mode == RunMode.POLLING:
        asyncio.run(run_polling())
    else:
        import uvicorn

        uvicorn.run("app.main:app", host="0.0.0.0", port=8000)
