from __future__ import annotations

import asyncio
import hmac
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
from app.bots.shop_bot import texts as shop_texts
from app.bots.shop_bot.router import build_shop_router
from app.config import RunMode, settings
from app.database.models import OrderPayment, PaymentPurpose, PaymentStatus
from app.database.session import session_scope
from app.services import (
    admin_alert_service,
    ai_service,
    bale_credentials_service,
    bale_service,
    customer_service,
    order_payment_service,
    order_service,
    order_state,
    bale_updates_service,
    order_transition_service,
    payment_event_service,
    payment_notify_service,
    payment_service,
    payment_settings_service,
    scheduler,
    shop_bot_service,
    shop_owner_service,
    zarinpal_service,
)
from app.services.admin_settings_service import get_admin_settings
from app.services.bot_manager import ShopBotManager

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logging.getLogger("aiogram.event").setLevel(logging.WARNING)  # هر آپدیت یک خطِ INFO می‌ساخت؛ لاگِ اصلی را می‌پوشاند
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


async def _refresh_bale_credentials() -> str:
    """A1: توکنِ رباتِ بله و رازِ وب‌هوک از پنلِ ادمین (رمزنگاری‌شده) ← `.env`.
    در startup و در هر گردشِ حلقه‌یِ getUpdates صدا زده می‌شود ⇒ تغییر بدونِ ری‌استارت."""
    try:
        async with session_scope() as session:
            return await bale_credentials_service.refresh(session)
    except Exception:  # noqa: BLE001 — نبودِ DB نباید دریافتِ رویدادِ پرداخت را متوقف کند
        logger.warning("تازه‌کردنِ اعتبارهایِ بله از دیتابیس ناموفق بود؛ مقدارِ .env استفاده می‌شود.", exc_info=True)
        return bale_credentials_service.bot_token()


def validate_runtime_config() -> None:
    """د(الف): در حالتِ webhook بدونِ رازِ وب‌هوک برنامه بالا نمی‌آید — وگرنه هر کسی می‌تواند آپدیتِ جعلی
    (حتی با هویتِ ادمین) به `/webhook/main` بفرستد. در حالتِ polling (پیش‌فرض) رازی لازم نیست."""
    if settings.run_mode == RunMode.WEBHOOK and not (settings.main_bot_webhook_secret or "").strip():
        raise RuntimeError(
            "RUN_MODE=webhook است ولی MAIN_BOT_WEBHOOK_SECRET خالی است. یا یک رشته‌ی تصادفیِ بلند برایِ "
            "MAIN_BOT_WEBHOOK_SECRET در .env بگذار، یا RUN_MODE=polling بگذار."
        )


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
    admin_alert_service.install()
    main_bot = Bot(token=settings.main_bot_token)
    shop_dispatcher = create_shop_dispatcher(main_bot)
    bot_manager = ShopBotManager(shop_dispatcher)
    main_dispatcher = create_main_dispatcher(bot_manager)

    await _load_active_shop_bots(bot_manager)

    stop_event = asyncio.Event()
    scheduler_task = asyncio.create_task(scheduler.run_periodic_tasks(main_bot, stop_event))
    payment_expiry_task = asyncio.create_task(scheduler.run_payment_expiry_loop(main_bot, bot_manager, stop_event))
    bale_updates_task = await _start_bale_updates_polling(stop_event)  # B6: بدونِ سرورِ HTTP هم پرداختِ بله‌پی دریافت می‌شه

    try:
        await main_bot.delete_webhook(drop_pending_updates=True)
        await main_dispatcher.start_polling(main_bot)
    finally:
        stop_event.set()
        await scheduler_task
        await payment_expiry_task
        if bale_updates_task is not None:
            await bale_updates_task
        await ai_service.close_http_session()
        await admin_alert_service.shutdown()
        await main_bot.session.close()


# =============================================================================
# حالت webhook + مسیرِ برگشتِ پرداخت زرین‌پال (همیشه فعال، صرف‌نظر از RUN_MODE)
# =============================================================================
# مستندات/OpenAPI عمداً غیرفعال: ساختارِ endpointها برایِ بیرون لازم نیست (کاهشِ سطحِ حمله).
app = FastAPI(title="کسب‌وکار هوشمند", docs_url=None, redoc_url=None, openapi_url=None)

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


def _forbidden(reason: str) -> Response:
    """د(و): ۴۰۳ مکررِ وب‌هوک نشانه‌یِ تلاش برایِ تزریقِ آپدیتِ جعلی است ⇒ هشدارِ نرخ‌محدود به ادمین."""
    admin_alert_service.record_event(admin_alert_service.KIND_FORBIDDEN, reason)
    return Response(status_code=403)


@app.on_event("startup")
async def on_startup() -> None:
    validate_runtime_config()
    admin_alert_service.install()
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
    await _refresh_bale_credentials()
    if settings.bale_updates_mode == "polling":
        _state["bale_updates_task"] = await _start_bale_updates_polling(_state["stop_event"])
    elif bale_credentials_service.bot_token():
        # B5: بله هدرِ secret نمی‌فرسته؛ پس رازِ وب‌هوک (اگه تنظیم شده) توی خودِ مسیره
        bale_webhook_url = f"{settings.webhook_base_url.rstrip('/')}/webhook/bale" + (f"/{bale_credentials_service.webhook_secret()}" if bale_credentials_service.webhook_secret() else "")
        try:
            await bale_service.set_webhook(bale_credentials_service.bot_token(), bale_webhook_url)
            logger.info("وب‌هوکِ بله‌پی روی %s تنظیم شد.", bale_webhook_url)
        except bale_service.BaleError:
            logger.exception(
                "تنظیمِ وب‌هوکِ بله‌پی ناموفق بود — Bale Pay غیرفعال می‌مونه تا این مشکل برطرف بشه."
            )

    _state["scheduler_task"] = asyncio.create_task(scheduler.run_periodic_tasks(main_bot, _state["stop_event"]))
    _state["payment_expiry_task"] = asyncio.create_task(
        scheduler.run_payment_expiry_loop(main_bot, bot_manager, _state["stop_event"])
    )


@app.on_event("shutdown")
async def on_shutdown() -> None:
    _state["stop_event"].set()
    await _state["scheduler_task"]
    await _state["payment_expiry_task"]
    bale_updates_task = _state.get("bale_updates_task")
    if bale_updates_task is not None:
        await bale_updates_task

    polling_task = _state.get("polling_task")
    if polling_task is not None:
        polling_task.cancel()

    for shop_bot_id in _state["bot_manager"].registered_shop_bot_ids():
        await _state["bot_manager"].unregister(shop_bot_id, disable_in_db=False)

    # جلسه‌ی HTTP مشترکِ سرویسِ هوش مصنوعی رو هم می‌بندیم تا سوکت باز نمونه
    await ai_service.close_http_session()
    await admin_alert_service.shutdown()
    await _state["main_bot"].session.close()


def _secrets_equal(provided: str | None, expected: str | None) -> bool:
    """مقایسه‌یِ زمان‌ثابت (در برابرِ timing attack). None فقط با None برابر است؛ رشته‌هایِ غیرِ ASCII هم امن مقایسه می‌شن."""
    if provided is None or expected is None:
        return provided is expected
    return hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8"))


def _is_valid_webhook_secret(provided_secret: str | None) -> bool:
    """
    مشابهِ رمزِ وب‌هوکِ ربات‌های فروشگاهی (پایینِ همین فایل)، ولی برای ربات اصلی
    از تنظیماتِ ثابتِ .env استفاده می‌کنیم چون فقط یه ربات اصلی داریم، نه یکی
    به‌ازای هر فروشگاه. شاخه‌یِ «رازِ خالی = پذیرش» فقط برایِ سازگاریِ تست/توسعه
    باقی مانده: در استقرارِ واقعی `validate_runtime_config()` در حالتِ webhook
    بدونِ راز اجازه‌یِ بالاآمدن نمی‌دهد (د-الف)، پس این شاخه هرگز به کار نمی‌افتد.
    """
    if not settings.main_bot_webhook_secret:
        return True
    return _secrets_equal(provided_secret, settings.main_bot_webhook_secret)


@app.post("/webhook/main")
async def webhook_main(request: Request) -> Response:
    if not _is_valid_webhook_secret(request.headers.get("X-Telegram-Bot-Api-Secret-Token")):
        return _forbidden("webhook/main: رازِ وب‌هوکِ نامعتبر")

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
    if not _secrets_equal(secret, bot_manager.get_secret(shop_bot_id)):
        return _forbidden(f"webhook/shop/{shop_bot_id}: رازِ وب‌هوکِ نامعتبر")

    data = await request.json()
    update = Update.model_validate(data)
    if _is_duplicate_update(bot.id, update.update_id):
        return Response(status_code=200)
    await _state["shop_dispatcher"].feed_update(bot, update)
    return Response(status_code=200)


async def _bale_outcome_ok(
    transaction: dict, expected_toman: int | None, context: str, shop_bot_id: int | None = None, group_ref: str | None = None
) -> bool:
    """B3: فقط وضعیتِ «موفق» (شاملِ succeed) و مبلغِ هم‌خوان اجازه‌یِ اعتباردهی می‌ده؛ همه‌یِ نتایج در payment_event_logs ثبت می‌شن.
    `shop_bot_id`/`group_ref` شناسه‌یِ همبستگی‌اند (د-ز)."""
    outcome = bale_service.classify_transaction_status(transaction)
    await payment_event_service.log_event(
        "bale", "in", f"inquire_result:{context}", status=outcome, raw=transaction,
        shop_bot_id=shop_bot_id, group_ref=group_ref,
    )
    if outcome != "success":
        logger.error("استعلامِ تراکنشِ بله موفق نبود (%s، %s): %r", outcome, context, transaction)
        return False
    if expected_toman is not None and bale_service.verify_transaction_amount(transaction, bale_service.toman_to_rial(expected_toman)) is False:
        logger.error("مبلغِ تراکنشِ بله با مبلغِ مورد انتظار نمی‌خونه (%s): %r", context, transaction)
        return False
    return True


@app.post("/webhook/bale/{path_secret}")
async def webhook_bale_with_secret(path_secret: str, request: Request) -> Response:
    """B5: رازِ وب‌هوک توی مسیره (بله هدرِ secret نمی‌فرسته)."""
    if not bale_credentials_service.bot_token():
        return Response(status_code=404)
    if not bale_credentials_service.webhook_secret() or not _secrets_equal(path_secret, bale_credentials_service.webhook_secret()):
        return _forbidden("webhook/bale: رازِ وب‌هوکِ نامعتبر")
    return await _process_bale_update(request)


@app.post("/webhook/bale")
async def webhook_bale(request: Request) -> Response:
    if not bale_credentials_service.bot_token():
        return Response(status_code=404)
    if bale_credentials_service.webhook_secret():
        secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if not _secrets_equal(secret, bale_credentials_service.webhook_secret()):
            return _forbidden("webhook/bale: رازِ وب‌هوکِ نامعتبر")
    return await _process_bale_update(request)


async def _process_bale_update(request: Request) -> Response:
    try:
        data = await request.json()
    except Exception:
        return Response(status_code=200)  # بدنه‌ی نامعتبر رو نادیده می‌گیریم، نه که با 4xx باعثِ retry بشیم
    await _dispatch_bale_update(data)
    return Response(status_code=200)


async def _dispatch_bale_update(data: dict) -> None:
    """مسیرِ مشترکِ webhook و getUpdates (B6): pre_checkout و successful_payment؛ بقیه نادیده."""
    if not isinstance(data, dict):
        return
    pre_checkout = data.get("pre_checkout_query")
    if pre_checkout:
        await payment_event_service.log_event(
            "bale", "in", "pre_checkout_query", reference=pre_checkout.get("id"), raw=pre_checkout,
            group_ref=pre_checkout.get("invoice_payload"),
        )
        await _handle_bale_pre_checkout(pre_checkout)
        return

    successful_payment = (data.get("message") or {}).get("successful_payment")
    if successful_payment:
        await payment_event_service.log_event(
            "bale", "in", "successful_payment", reference=successful_payment.get("telegram_payment_charge_id"),
            raw=successful_payment, group_ref=successful_payment.get("invoice_payload"),
        )
        await _handle_bale_successful_payment(successful_payment)


async def _start_bale_updates_polling(stop_event: asyncio.Event) -> asyncio.Task | None:
    """B6: اگه mode=polling، webhook رو حذف و حلقه‌یِ getUpdates رو شروع می‌کنه.
    A1: توکن از پنلِ ادمین (رمزنگاری‌شده) ← `.env` و در هر گردش تازه می‌شود ⇒ تغییرِ توکن بدونِ ری‌استارت.
    حلقه حتی بدونِ توکن شروع می‌شود و منتظر می‌ماند تا ادمین توکن را در پنل بگذارد."""
    if settings.bale_updates_mode != "polling":
        return None
    token = await _refresh_bale_credentials()
    if token:
        try:
            await bale_service.delete_webhook(token)
        except bale_service.BaleError:
            logger.exception("حذفِ webhookِ بله ناموفق بود؛ getUpdates ممکنه خطا بده (حلقه با backoff ادامه می‌ده).")
    return asyncio.create_task(
        bale_updates_service.run_loop(
            token, _dispatch_bale_update, stop_event, bale_service.get_updates, _refresh_bale_credentials
        )
    )


def _extract_cart_group_id(invoice_payload: str) -> str | None:
    """payloadِ پرداختِ سبد به‌شکلِ 'cartgroup-{group_id}-{nonce}' ساخته می‌شه
    (customer.py). group_id و nonce هر دو خروجیِ secrets.token_hex ـن، یعنی فقط
    ارقامِ هگز — هیچ‌وقت خط‌تیره ندارن، پس split روی '-' امنه."""
    parts = invoice_payload.split("-")
    if len(parts) != 3 or parts[0] != "cartgroup" or not parts[1]:
        return None
    return parts[1]


async def _handle_bale_pre_checkout(pre_checkout: dict) -> None:
    query_id = pre_checkout.get("id")
    invoice_payload = pre_checkout.get("invoice_payload")
    if not query_id:
        logger.error("pre_checkout_query بدونِ id از بله رسید: %r", pre_checkout)
        return

    # فازِ ۳: پرداختِ سفارشِ محصول (پیشوندِ payload = 'order-') یه مسیرِ کاملاً
    # جدا از پرداختِ فروشگاه‌دار به پلتفرم (پیشوندِ 'payment-') داره — دو جدولِ
    # متفاوت، دو تعریفِ متفاوت از «هنوز معتبره». پرداختِ کلِ یه سبدِ خرید هم
    # پیشوندِ سومِ 'cartgroup-' داره.
    if invoice_payload and invoice_payload.startswith("cartgroup-"):
        group_id = _extract_cart_group_id(invoice_payload)
        async with session_scope() as session:
            orders = await order_service.get_by_cart_checkout_group(session, group_id) if group_id else []
        async with session_scope() as session:
            new_payment = (
                await order_payment_service.get_latest_payment(session, orders[0].shop_bot_id, group_id, "bale") if orders else None
            )
        if new_payment is not None:
            # جریانِ تازه (W4): پرداختِ فعال + سفارش هنوز منتظرِ پرداخت (یا تازه منقضی ⇒ پرداختِ دیرهنگام قابلِ پذیرش)
            ok = new_payment.status != order_payment_service.P_PAID and all(
                order_state.value_of(o.status)
                in (order_state.AWAITING_PAYMENT, order_state.RECEIPT_SUBMITTED, order_state.EXPIRED)
                for o in orders
            )
        else:
            ok = bool(orders) and all(o.bale_paid_at is None for o in orders)
        error_message = None if ok else "این سفارش دیگه معتبر نیست یا قبلاً پرداخت شده."
    elif invoice_payload and invoice_payload.startswith("order-"):
        async with session_scope() as session:
            order = await order_service.get_by_bale_payload(session, invoice_payload)
        ok = order is not None and order.bale_paid_at is None
        error_message = None if ok else "این سفارش دیگه معتبر نیست یا قبلاً پرداخت شده."
    else:
        async with session_scope() as session:
            payment = await payment_service.get_by_bale_payload(session, invoice_payload) if invoice_payload else None
        ok = payment is not None and payment.status == PaymentStatus.PENDING
        error_message = None if ok else "این سفارش دیگه معتبر نیست یا قبلاً پردازش شده."

    try:
        await bale_service.answer_pre_checkout_query(bale_credentials_service.bot_token(), query_id, ok=ok, error_message=error_message)
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

    if invoice_payload.startswith("cartgroup-"):
        await _handle_bale_cartgroup_payment(invoice_payload, transaction_id)
        return

    if invoice_payload.startswith("order-"):
        await _handle_bale_order_payment(invoice_payload, transaction_id)
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
            transaction = await bale_service.inquire_transaction(bale_credentials_service.bot_token(), transaction_id)
        except bale_service.BaleError:
            logger.exception("استعلامِ تراکنشِ بله ناموفق بود (transaction_id=%s) — کیف‌پول شارژ نشد.", transaction_id)
            return

        if not await _bale_outcome_ok(transaction, payment.final_amount, "wallet/subscription", group_ref=invoice_payload):
            return

        _effect, reward_info = await payment_service.approve_bale_payment(session, payment, transaction_id)
        owner = await shop_owner_service.get_by_id(session, payment.shop_owner_id)
        owner_telegram_id = owner.telegram_id
        is_topup = payment.purpose == PaymentPurpose.WALLET_TOPUP
        wallet_amount_toman = payment.final_amount if is_topup else None

    await _notify_payment_result(_state["main_bot"], owner_telegram_id, is_topup, wallet_amount_toman, reward_info)


_BALE_RETRY_DELAYS = (5, 20, 60, 180)  # B3: استعلامِ «در انتظار» با backoff دوباره تلاش می‌شه


async def _handle_bale_new_flow(payment_id: int, shop_bot_id: int, transaction_id: str, attempt: int = 0) -> None:
    """W4 (C7): پرداختِ بله‌پیِ جریانِ تازه. فقط بعد از استعلامِ سمتِ سرور + تطبیقِ مبلغ ⇒ `paid`؛
    وضعیتِ «در انتظار» با backoff دوباره پرسیده می‌شه؛ نامشخص/ناموفق ⇒ هیچ تغییری (لاگ در payment_event_logs)."""
    notify = None
    async with session_scope() as session:
        payment = await session.get(OrderPayment, payment_id)
        if payment is None or payment.status == order_payment_service.P_PAID:
            return
        try:
            transaction = await bale_service.inquire_transaction(bale_credentials_service.bot_token(), transaction_id)
        except bale_service.BaleError:
            logger.exception("استعلامِ تراکنشِ بله ناموفق بود (transaction_id=%s) — سفارش پرداخت‌شده علامت نخورد.", transaction_id)
            return
        if bale_service.classify_transaction_status(transaction) == "pending":
            await payment_event_service.log_event(
                "bale", "in", "inquire_result:cart", status="pending", raw=transaction,
                shop_bot_id=shop_bot_id, group_ref=payment.provider_ref,
            )
            if attempt < len(_BALE_RETRY_DELAYS):
                asyncio.create_task(_retry_bale_new_flow(payment_id, shop_bot_id, transaction_id, attempt))
            return
        if not await _bale_outcome_ok(
            transaction, payment.amount_toman, "cart", shop_bot_id=shop_bot_id, group_ref=payment.provider_ref
        ):
            return
        settings_row = await payment_settings_service.get_or_create(session, shop_bot_id)
        result = await order_payment_service.apply_verified_online_payment(
            session, payment_id, shop_bot_id, transaction_ref=transaction_id, auto_accept=settings_row.auto_accept_online
        )
        if result.ok and result.changed:
            notify = (
                [r.id for r in result.rows], result.late, result.needs_review, result.oversold, result.final_status or "paid",
            )
    if notify is not None:
        await payment_notify_service.notify_online_payment(
            _state["main_bot"], _state["bot_manager"], shop_bot_id, notify[0],
            method="bale", late=notify[1], needs_review=notify[2], oversold=notify[3], final_status=notify[4],
        )


async def _retry_bale_new_flow(payment_id: int, shop_bot_id: int, transaction_id: str, attempt: int) -> None:
    await asyncio.sleep(_BALE_RETRY_DELAYS[attempt])
    try:
        await _handle_bale_new_flow(payment_id, shop_bot_id, transaction_id, attempt + 1)
    except Exception:
        logger.exception("تلاشِ مجددِ استعلامِ بله ناموفق بود (transaction_id=%s).", transaction_id)


async def _handle_bale_cartgroup_payment(invoice_payload: str, transaction_id: str) -> None:
    """فازِ ۳: پرداختِ آنلاینِ کلِ یه سبدِ خرید (مشتری → فروشگاه‌دار). مثلِ
    _handle_bale_order_payment پایین، ولی رویِ همه‌ی ردیف‌هایِ یه گروه: همه رو
    با هم پرداخت‌شده علامت می‌زنه و یه اطلاع‌رسانیِ ترکیبی (نه یکی به‌ازایِ هر
    قلم) به هر دو طرف می‌فرسته. همون محافظتِ اصلی: قبل از هر تغییری، استعلامِ
    مستقل از سرورِ بله."""
    group_id = _extract_cart_group_id(invoice_payload)
    if group_id is None:
        logger.error("successful_payment (سبد) با payloadِ نامعتبر رسید: %s", invoice_payload)
        return

    async with session_scope() as session:
        orders = await order_service.get_by_cart_checkout_group(session, group_id)
        if not orders:
            logger.error("successful_payment (سبد) برای گروهِ ناشناس رسید: %s", group_id)
            return
        new_payment = await order_payment_service.get_latest_payment(session, orders[0].shop_bot_id, group_id, "bale")
        if new_payment is not None:
            new_flow = (new_payment.id, new_payment.shop_bot_id)
        else:
            new_flow = None
            if all(o.bale_paid_at is not None for o in orders):
                # وب‌هوکِ تکراری — قبلاً پردازش شده.
                return
    if new_flow is not None:
        await _handle_bale_new_flow(new_flow[0], new_flow[1], transaction_id)
        return

    async with session_scope() as session:
        orders = await order_service.get_by_cart_checkout_group(session, group_id)

        try:
            transaction = await bale_service.inquire_transaction(bale_credentials_service.bot_token(), transaction_id)
        except bale_service.BaleError:
            logger.exception("استعلامِ تراکنشِ بله ناموفق بود (transaction_id=%s) — سبد پرداخت‌شده علامت نخورد.", transaction_id)
            return

        if not await _bale_outcome_ok(  # اقلام + ارسال
            transaction, order_transition_service.group_total_toman(orders), "cart",
            shop_bot_id=orders[0].shop_bot_id, group_ref=group_id,
        ):
            return

        # B10: بعد از استعلامِ شبکه، ردیف‌ها قفل و تازه خونده می‌شن؛ فقط برنده‌یِ رقابت (webhook/getUpdates/تکراری) علامت می‌زنه و خبر می‌ده.
        orders = await order_service.get_by_cart_checkout_group(session, group_id, lock=True)
        pending = [o for o in orders if o.bale_paid_at is None]
        if not pending:
            return
        if await order_service.bale_transaction_used_elsewhere(session, transaction_id, [o.id for o in orders]):
            logger.error("تراکنشِ بله (%s) قبلاً روی سفارشِ دیگری ثبت شده؛ سبدِ %s پرداخت‌شده علامت نخورد.", transaction_id, group_id)
            return
        for order in pending:
            await order_service.mark_bale_paid(session, order, transaction_id)

        shop_bot = await shop_bot_service.get_by_id(session, orders[0].shop_bot_id)
        customer = await customer_service.get_by_id(session, orders[0].customer_id)
        owner = await shop_owner_service.get_by_id(session, shop_bot.shop_owner_id)
        order_count = len(orders)
        total_toman = order_transition_service.group_total_toman(orders)
        shop_bot_id = shop_bot.id
        owner_telegram_id = owner.telegram_id
        customer_telegram_id = customer.telegram_id if customer is not None else None

    try:
        await _state["main_bot"].send_message(owner_telegram_id, main_texts.cart_paid_online_notification(order_count, total_toman))
    except TelegramAPIError:
        logger.exception("اطلاع‌رسانیِ پرداختِ آنلاینِ سبد به فروشگاه‌دار %s ناموفق بود.", owner_telegram_id)

    shop_bot_instance = _state["bot_manager"].get_bot(shop_bot_id)
    if shop_bot_instance is not None and customer_telegram_id is not None:
        try:
            await shop_bot_instance.send_message(customer_telegram_id, shop_texts.ONLINE_PAYMENT_CONFIRMED)
        except TelegramAPIError:
            logger.exception("اطلاع‌رسانیِ تاییدِ پرداخت به مشتری %s ناموفق بود.", customer_telegram_id)


async def _handle_bale_order_payment(invoice_payload: str, transaction_id: str) -> None:
    """فازِ ۳: پرداختِ آنلاینِ یه سفارشِ محصول (مشتری → فروشگاه‌دار، نه
    فروشگاه‌دار → پلتفرم). عمداً از payment_service استفاده نمی‌کنه چون اون
    سرویس کاملاً حولِ Payment (پرداختِ فروشگاه‌دار به پلتفرم — تخفیف، پاداشِ
    معرف، اشتراک/کیف‌پول) ساخته شده و هیچ‌کدومش برایِ این مسیر معنی نداره؛
    اینجا فقط سفارش رو «پرداخت‌شده» علامت می‌زنیم و به هر دو طرف خبر می‌دیم."""
    async with session_scope() as session:
        order = await order_service.get_by_bale_payload(session, invoice_payload)
        if order is None:
            logger.error("successful_payment (سفارش) برای payloadِ ناشناس رسید: %s", invoice_payload)
            return
        if order.bale_paid_at is not None:
            # وب‌هوکِ تکراری — قبلاً پردازش شده.
            return

        # همینجا هم، دقیقاً مثلِ مسیرِ بالا، مستقل از خودِ سرورِ بله استعلام
        # می‌گیریم — این مهم‌ترین محافظت در برابرِ یه وب‌هوکِ جعلیه.
        try:
            transaction = await bale_service.inquire_transaction(bale_credentials_service.bot_token(), transaction_id)
        except bale_service.BaleError:
            logger.exception("استعلامِ تراکنشِ بله ناموفق بود (transaction_id=%s) — سفارش پرداخت‌شده علامت نخورد.", transaction_id)
            return

        if not await _bale_outcome_ok(
            transaction, order.estimated_value_toman, "order", shop_bot_id=order.shop_bot_id, group_ref=str(order.id)
        ):
            return

        # B10: قفل + خوانشِ تازه؛ بازنده‌یِ رقابت (یا تراکنشِ بازپخش‌شده) هیچ اثری نداره.
        order = await order_service.lock_order(session, order.id)
        if order is None or order.bale_paid_at is not None:
            return
        if await order_service.bale_transaction_used_elsewhere(session, transaction_id, [order.id]):
            logger.error("تراکنشِ بله (%s) قبلاً روی سفارشِ دیگری ثبت شده؛ سفارشِ %s پرداخت‌شده علامت نخورد.", transaction_id, order.id)
            return
        await order_service.mark_bale_paid(session, order, transaction_id)
        shop_bot = await shop_bot_service.get_by_id(session, order.shop_bot_id)
        customer = await customer_service.get_by_id(session, order.customer_id)
        owner = await shop_owner_service.get_by_id(session, shop_bot.shop_owner_id)
        order_id, order_estimated_value = order.id, order.estimated_value_toman

    try:
        await _state["main_bot"].send_message(owner.telegram_id, main_texts.order_paid_online_notification(order))
    except TelegramAPIError:
        logger.exception("اطلاع‌رسانیِ پرداختِ آنلاینِ سفارشِ %s به فروشگاه‌دار %s ناموفق بود.", order_id, owner.telegram_id)

    shop_bot_instance = _state["bot_manager"].get_bot(shop_bot.id)
    if shop_bot_instance is not None and customer is not None:
        try:
            await shop_bot_instance.send_message(customer.telegram_id, shop_texts.ONLINE_PAYMENT_CONFIRMED)
        except TelegramAPIError:
            logger.exception("اطلاع‌رسانیِ تاییدِ پرداخت به مشتری %s ناموفق بود.", customer.telegram_id)


async def _zarinpal_shop_callback(Authority: str, Status: str) -> HTMLResponse | None:
    """W4 (M): پرداختِ سفارشِ مشتری با مرچنتِ خودِ فروشگاه. None ⇒ این authority مالِ جریانِ پلتفرم است."""
    notify = None
    async with session_scope() as session:
        payment = await order_payment_service.get_by_provider_ref(session, Authority, "zarinpal")
        if payment is None:
            return None
        if payment.status == order_payment_service.P_PAID:
            return HTMLResponse(main_texts.ZARINPAL_PAYMENT_SUCCESSFUL_PAGE)  # بازگشتِ تکراری
        if Status != "OK":
            return HTMLResponse(main_texts.ZARINPAL_PAYMENT_FAILED_PAGE)
        settings_row = await payment_settings_service.get_or_create(session, payment.shop_bot_id)
        if not settings_row.zarinpal_merchant_id_enc:
            return HTMLResponse(main_texts.ZARINPAL_PAYMENT_FAILED_PAGE)
        try:
            from app.utils.encryption import decrypt_token

            ref_id = await zarinpal_service.verify_payment(decrypt_token(settings_row.zarinpal_merchant_id_enc), payment.amount_toman, Authority)
        except Exception:  # noqa: BLE001 — ZarinpalError/رمزگشایی؛ جزئیات فقط در لاگ
            logger.exception("تاییدِ پرداختِ زرین‌پالِ سفارش با اتوریتیِ %s ناموفق بود.", Authority)
            return HTMLResponse(main_texts.ZARINPAL_PAYMENT_FAILED_PAGE)
        await payment_event_service.log_event(
            "zarinpal", "in", "verify:order", reference=Authority, status="ok" if ref_id else "no_ref",
            raw={"ref_id": ref_id}, shop_bot_id=payment.shop_bot_id, group_ref=str(payment.id),
        )
        if not ref_id:
            return HTMLResponse(main_texts.ZARINPAL_PAYMENT_FAILED_PAGE)
        result = await order_payment_service.apply_verified_online_payment(
            session, payment.id, payment.shop_bot_id, transaction_ref=f"zp-{ref_id}", auto_accept=settings_row.auto_accept_online
        )
        if result.ok and result.changed:
            notify = (
                payment.shop_bot_id, [r.id for r in result.rows], result.late, result.needs_review, result.oversold, result.final_status or "paid",
            )
    if notify is not None:
        await payment_notify_service.notify_online_payment(
            _state["main_bot"], _state["bot_manager"], notify[0], notify[1],
            method="zarinpal", late=notify[2], needs_review=notify[3], oversold=notify[4], final_status=notify[5],
        )
    return HTMLResponse(main_texts.ZARINPAL_PAYMENT_SUCCESSFUL_PAGE)


@app.get("/payment/zarinpal/callback")
async def zarinpal_callback(Authority: str, Status: str) -> HTMLResponse:
    shop_page = await _zarinpal_shop_callback(Authority, Status)
    if shop_page is not None:
        return shop_page
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
    validate_runtime_config()
    if settings.run_mode == RunMode.POLLING:
        asyncio.run(run_polling())
    else:
        import uvicorn

        uvicorn.run("app.main:app", host="0.0.0.0", port=8000)
