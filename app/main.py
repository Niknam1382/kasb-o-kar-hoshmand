from __future__ import annotations

import asyncio
import hmac
import logging
import time
from collections import OrderedDict

from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramAPIError
from app.services.fsm_storage import build_storage as build_fsm_storage  # P32: memory|postgres (FSM_STORAGE)
from aiogram.types import Update
from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from sqlalchemy import select

from app.bots.common.channel_knowledge import create_channel_knowledge_router
from app.bots.common.middlewares import DbSessionMiddleware
from app.bots.main_bot import texts as main_texts
from app.bots.main_bot.router import build_main_router
from app.bots.shop_bot import texts as shop_texts
from app.bots.shop_bot.router import build_shop_router
from app.config import RunMode, settings
from app import observability
from app.services import http_guard
from app.database.models import OrderPayment, PaymentPurpose, PaymentStatus, ShopBot
from app.database.session import session_scope
from app.services import (
    admin_alert_service,
    bot_branding_service,
    ai_service,
    bale_bot_service,
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

# P20 · PHASE 20: لاگ با scrubberِ رازها و correlation-id (JSON اختیاری با JSON_LOGS=true).
observability.install(level=settings.log_level, as_json=settings.json_logs)
logging.getLogger("aiogram.event").setLevel(logging.WARNING)  # هر آپدیت یک خطِ INFO می‌ساخت؛ لاگِ اصلی را می‌پوشاند
# B6: fpdf2 هنگامِ امبدکردنِ فونت، ده‌ها خطِ INFO از fontTools.subset می‌سازد (هر فاکتور).
# این لاگ‌ها هیچ اطلاعاتِ عملیاتی ندارند و حجمِ لاگِ Docker را بالا می‌برند ⇒ فقط هشدارها.
logging.getLogger("fontTools").setLevel(logging.WARNING)
logging.getLogger("fontTools.subset").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def create_main_dispatcher(bot_manager: ShopBotManager) -> Dispatcher:
    dispatcher = Dispatcher(storage=build_fsm_storage())
    dispatcher.update.middleware(DbSessionMiddleware())
    dispatcher["bot_manager"] = bot_manager
    dispatcher.include_router(build_main_router())
    dispatcher.include_router(create_channel_knowledge_router("main_channel_knowledge"))
    return dispatcher


def create_shop_dispatcher(main_bot: Bot) -> Dispatcher:
    dispatcher = Dispatcher(storage=build_fsm_storage())
    dispatcher.update.middleware(DbSessionMiddleware())
    dispatcher["main_bot"] = main_bot
    dispatcher.include_router(build_shop_router())
    dispatcher.include_router(create_channel_knowledge_router("shop_channel_knowledge"))
    return dispatcher


async def _load_active_shop_bots(
    bot_manager: ShopBotManager, main_bot: Bot, *, bale_polling_owner: bool = True
) -> None:
    async with session_scope() as session:
        shop_bots = await shop_bot_service.get_all_active(session)
        # P19: اتصالِ بله فقط وقتی شروع می‌شود که ادمین ویژگی را رونمایی کرده باشد (پیش‌فرض پنهان).
        bale_enabled = bale_bot_service.enabled(await get_admin_settings(session))
    if bale_enabled and not bale_polling_owner:
        # P36: در حالتِ webhook هر رونوشت این‌جا را اجرا می‌کند، ولی pollingِ بله فقط باید رویِ
        # یکی باشد؛ وگرنه پاسخِ AI دوبار می‌رود و کیف‌پول دوبار کم می‌شود.
        logger.warning(
            "اتصالِ بله‌یِ فروشگاه‌ها در این رونوشت شروع نمی‌شود؛ رونوشتِ دیگری قفلِ pollingِ بله را دارد."
        )
        bale_enabled = False
    # P20 · B2: رازِ وب‌هوکِ هر رباتِ فروشگاهی باید رمزنگاری‌شده در دیتابیس بماند؛ ردیف‌هایِ
    # قدیمیِ خام یک‌بار در بوت‌آپ بازنویسی می‌شوند (کلیدِ رمزنگاری فقط این‌جا در دسترس است، نه در مایگریشن).
    try:
        async with session_scope() as session:
            reencrypted = await shop_bot_service.reencrypt_secrets(session)
        if reencrypted:
            logger.info("%d رازِ وب‌هوکِ خام در دیتابیس رمزنگاری شد.", reencrypted)
    except Exception:
        logger.exception("بازنویسیِ رمزنگاری‌شدهٔ رازهایِ وب‌هوک ناموفق بود (ربات‌ها کار می‌کنند).")
    await bot_manager.load_all(shop_bots, bale_enabled=bale_enabled)
    logger.info(
        "%d ربات فروشگاهی‌ِ فعال بارگذاری شد (اتصالِ بله: %s، ربات‌هایِ بله‌دار: %d).",
        len(shop_bots),
        "روشن" if bale_enabled else "خاموش",
        len(bot_manager.registered_bale_bot_ids()),
    )
    # A2: بیوگرافی/برندینگِ اجباری موقعِ بالا آمدنِ هر ربات فروشگاهی اعمال می‌شود.
    try:
        async with session_scope() as session:
            await bot_branding_service.sync_all(session, bot_manager, main_bot)
    except Exception:
        logger.warning("همگام‌سازیِ بیوگرافیِ ربات‌ها در بالا آمدن ناموفق بود.", exc_info=True)


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

    # P35: پاداشِ معرفی **فقط به معرف** می‌رسد (`referral_service`). این مسیر قبلاً سعی می‌کرد
    # پیامِ دومی به «معرفی‌شده» هم بفرستد و کلیدِ `referred_telegram_id` را از همان dict
    # می‌خواند که هیچ‌وقت ساخته نمی‌شد ⇒ هر پاداشِ واقعی با KeyErrorِ بی‌لاگ تمام می‌شد.
    try:
        await main_bot.send_message(
            reward_info["referrer_telegram_id"],
            main_texts.referrer_reward_notification(reward_info["amount_toman"], reward_info["percent"]),
        )
    except TelegramAPIError:
        logger.exception("اطلاع‌رسانیِ پاداشِ معرف به %s ناموفق بود.", reward_info["referrer_telegram_id"])


# =============================================================================
# حالت polling (RUN_MODE=polling)
# =============================================================================
POLLING_LOCK_KEY = 20261103  # جدا از قفلِ جابها؛ شماره‌اش بخشی از قرارداد است
# P36: pollingِ رباتِ بلهٔ هر فروشگاه *مستقل از* run_mode است (بله رازِ وب‌هوک نمی‌فرستد)،
# پس در حالتِ webhook هم هر رونوشت آن را شروع می‌کند. دو رونوشت ⇒ یکِ پیامِ بله‌ای دو بار به
# هوشِ مصنوعی و **دو بار کسرِ کیف‌پول**. این قفلِ جدا مالکیتِ آن polling را به یکِ رونوشت می‌دهد
# بدونِ آن‌که به قفلِ pollingِ اصلی (که فقط تلگرام را نگه می‌دارد) دست ببرد.
BALE_POLLING_LOCK_KEY = 20261104


async def acquire_polling_lock(key: int = POLLING_LOCK_KEY):
    """دی(دیپلوی): نگهبانِ «فقط یکِ نسخه polling».

    دو نسخة هم‌زمان (`--scale bot=2`، یا deployِ تازه‌ای که بالا آمد ولی قدیمی نمُرده) هر دو
    `getUpdates` می‌گیرند ⇒ یکِ پیامِ مشتری دو بار به هوش مصنوعی می‌رود و **دو بار از کیف‌پول
    کم می‌شود**، اعلان‌ها دوباره می‌روند و FSM در `MemoryStorage` بینِ دو پروسه نصفه می‌ماند.
    قفلِ advisoryِ session-scoped رویِ یکِ اتصالِ نگه‌داشته‌شده_atomیک‌ترین راهِ دیتابیس-محور است:
    پروسه که بمیرد اتصال بسته و قفل آزاد می‌شود ⇒ ری‌استارتِ خودکارِ compose کار می‌کند.
    """
    from sqlalchemy import text as sql_text

    from app.database.session import engine

    connection = await engine.connect()
    try:
        held = bool(
            (await connection.execute(sql_text("SELECT pg_try_advisory_lock(:key)"), {"key": key})).scalar()
        )
    except Exception:  # noqa: BLE001 - نبودِ قفل نباید جلویِ بالا آمدنِ ربات را بگیرد
        await connection.close()
        raise
    if not held:
        await connection.close()
        return None
    return connection


async def release_polling_lock(connection, key: int = POLLING_LOCK_KEY) -> None:
    from sqlalchemy import text as sql_text

    if connection is None:
        return
    try:
        await connection.execute(sql_text("SELECT pg_advisory_unlock(:key)"), {"key": key})
    except Exception:  # noqa: BLE001 - بستنِ اتصال قفل را هم آزاد می‌کند
        logger.warning("آزادکردنِ قفلِ polling ناموفق بود؛ با بستنِ اتصال آزاد می‌شود.")
    await connection.close()


async def run_polling() -> None:
    admin_alert_service.install()
    try:
        lock_connection = await acquire_polling_lock()
    except Exception:  # noqa: BLE001 - اگر دیتابیس قفل را نشناسد، مثلِ قبل کار کن (به‌جایِ توقفِ ربات)
        logger.exception("قفلِ anti-double-polling خوانده نشد؛ ربات بدونِ آن بالا می‌آید.")
        lock_connection = None
    if lock_connection is None:
        logger.error(
            "نسخهٔ دیگری از این ربات در حالِ polling است (قفلِ دیتابیس آزاد نیست). "
            "اینِ دومین هیچ getUpdates‌ای شروع نمی‌کند تا پیام‌ها دوباره پاسخ نگیرند و کیف‌پول دوباره کم نشود."
        )
        await admin_alert_service.shutdown()
        return
    main_bot = Bot(token=settings.main_bot_token)
    shop_dispatcher = create_shop_dispatcher(main_bot)
    bot_manager = ShopBotManager(shop_dispatcher)
    main_dispatcher = create_main_dispatcher(bot_manager)

    await _load_active_shop_bots(bot_manager, main_bot)

    stop_event = asyncio.Event()
    # O2: /health و /metrics در حالتِ polling هم در دسترس‌اند (اپِ سلامت، بدونِ مسیرِ وب‌هوک)
    _state["main_bot"] = main_bot
    _state["bot_manager"] = bot_manager
    _state["stop_event"] = stop_event
    health = _start_health_server()
    scheduler_task = asyncio.create_task(scheduler.run_periodic_tasks(main_bot, stop_event, bot_manager))
    payment_expiry_task = asyncio.create_task(scheduler.run_payment_expiry_loop(main_bot, bot_manager, stop_event))
    notification_task = asyncio.create_task(scheduler.run_notification_loop(main_bot, bot_manager, stop_event))
    bale_updates_task = await _start_bale_updates_polling(stop_event)  # B6: بدونِ سرورِ HTTP هم پرداختِ بله‌پی دریافت می‌شه

    try:
        await main_bot.delete_webhook(drop_pending_updates=True)
        await main_dispatcher.start_polling(main_bot)
    finally:
        stop_event.set()
        await scheduler_task
        await payment_expiry_task
        notification_task.cancel()
        if bale_updates_task is not None:
            await bale_updates_task
        _stop_health_server(health)
        await ai_service.close_http_session()
        await bale_service.close_http_session()
        await admin_alert_service.shutdown()
        await main_bot.session.close()
        await release_polling_lock(lock_connection)


# =============================================================================
# حالت webhook + مسیرِ برگشتِ پرداخت زرین‌پال (همیشه فعال، صرف‌نظر از RUN_MODE)
# =============================================================================
# مستندات/OpenAPI عمداً غیرفعال: ساختارِ endpointها برایِ بیرون لازم نیست (کاهشِ سطحِ حمله).
app = FastAPI(title="کسب‌وکار هوشمند", docs_url=None, redoc_url=None, openapi_url=None)

# O2 (P21-B): `/health` و `/metrics` رویِ یک روترِ جدا نشسته‌اند تا در حالتِ polling هم
# بشود آن‌ها را سرو کرد — بدونِ اینکه حتی یک مسیرِ webhook از بیرون باز شود.
observability_router = APIRouter()

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
    observability.count("webhook.rejected")
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

    # P36: pollingِ رباتِ بلهٔ فروشگاه‌ها مستقل از run_mode است، پس مالکیتش را با قفلِ جدا نگه
    # می‌داریم تا در دیپلویِ چندرونشتی یکِ پیامِ بله‌ای دو بار پاسخ نگیرد و دو بار کم نشود.
    try:
        _state["bale_polling_lock"] = await acquire_polling_lock(BALE_POLLING_LOCK_KEY)
    except Exception:  # noqa: BLE001 - اگر دیتابیس قفل را نشناسد، این رونوشت را صاحب بدان
        logger.exception("قفلِ pollingِ بله خوانده نشد؛ این رونوشت صاحبِ pollingِ بله در نظر گرفته می‌شود.")
        _state["bale_polling_lock"] = None
    await _load_active_shop_bots(bot_manager, main_bot, bale_polling_owner=_state["bale_polling_lock"] is not None)

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

    _state["scheduler_task"] = asyncio.create_task(scheduler.run_periodic_tasks(main_bot, _state["stop_event"], bot_manager))
    _state["payment_expiry_task"] = asyncio.create_task(
        scheduler.run_payment_expiry_loop(main_bot, bot_manager, _state["stop_event"])
    )
    # P21-F: تخلیهٔ صندوقِ اعلان هر ۶۰ ثانیه (خبرِ پرداخت نباید تا ۳۰ دقیقه معطل بماند)
    _state["notification_task"] = asyncio.create_task(
        scheduler.run_notification_loop(main_bot, bot_manager, _state["stop_event"])
    )


@app.on_event("shutdown")
async def on_shutdown() -> None:
    _state["stop_event"].set()
    await _state["scheduler_task"]
    await _state["payment_expiry_task"]
    # حلقه‌ها با stop_event خودشان بیرون می‌آیند (wait_for رویِ event بیدار می‌شود) ⇒ await امن است
    notification_task = _state.get("notification_task")
    if notification_task is not None:
        await notification_task
    bale_updates_task = _state.get("bale_updates_task")
    if bale_updates_task is not None:
        await bale_updates_task

    polling_task = _state.get("polling_task")
    if polling_task is not None:
        polling_task.cancel()

    # P29: بستنِ اتصال‌ها با همان سقفِ همزمانیِ راه‌اندازی (قبلاً ترتیبی بود ⇒ ۵۰۰ فروشگاه ≈ ۵۰۰ × RTT
    # خاموش‌شدن، بیشتر از stop_grace_period داکر ⇒ هر دیپلوی با SIGKILL تمام می‌شد).
    await _state["bot_manager"].shutdown()

    # P36: قفلِ مالکیتِ pollingِ بله هم آزاد می‌شود (رونوشتِ بعدی بلافاصله می‌تواند صاحب شود).
    await release_polling_lock(_state.get("bale_polling_lock"), BALE_POLLING_LOCK_KEY)
    _state["bale_polling_lock"] = None

    # جلسه‌ی HTTP مشترکِ سرویسِ هوش مصنوعی رو هم می‌بندیم تا سوکت باز نمونه
    await ai_service.close_http_session()
    await bale_service.close_http_session()
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
    limited = _too_many_requests(request, "main")
    if limited is not None:
        return limited
    if not _is_valid_webhook_secret(request.headers.get("X-Telegram-Bot-Api-Secret-Token")):
        return _forbidden("webhook/main: رازِ وب‌هوکِ نامعتبر")

    data = await request.json()
    update = Update.model_validate(data)
    observability.bind_correlation(observability.correlate("wh", "main", update.update_id))
    observability.count("webhook.main")
    if _is_duplicate_update(_state["main_bot"].id, update.update_id):
        observability.count("webhook.duplicate")
        return Response(status_code=200)
    await _state["main_dispatcher"].feed_update(_state["main_bot"], update)
    return Response(status_code=200)


@observability_router.get("/health")
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
    limited = _too_many_requests(request, f"shop:{shop_bot_id}")
    if limited is not None:
        return limited
    bot_manager: ShopBotManager = _state["bot_manager"]
    bot = bot_manager.get_bot(shop_bot_id)
    if bot is None:
        return Response(status_code=404)

    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if not _secrets_equal(secret, bot_manager.get_secret(shop_bot_id)):
        return _forbidden(f"webhook/shop/{shop_bot_id}: رازِ وب‌هوکِ نامعتبر")

    data = await request.json()
    update = Update.model_validate(data)
    observability.bind_correlation(observability.correlate("wh", "shop", shop_bot_id, update.update_id))
    observability.count("webhook.shop")
    if _is_duplicate_update(bot.id, update.update_id):
        return Response(status_code=200)
    await _state["shop_dispatcher"].feed_update(bot, update)
    return Response(status_code=200)



def _client_ip(request: Request) -> str:
    """IPِ واقعیِ فرستنده. پشتِ reverse-proxy باید TRUST_PROXY_HEADERS=true شود، وگرنه
    IPِ هر درخواست همانِ پراکسی است و سقفِ مشترک همه را با هم رد می‌کند."""
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for") or ""
        first = forwarded.split(",")[0].strip()
        if first:
            return first[:64]
    client = getattr(request, "client", None)
    return (getattr(client, "host", None) or "unknown")[:64]


def _too_many_requests(request: Request, path: str) -> Response | None:
    """۴۲۹ وقتی یک IP از سقفِ دقیقه‌ایِ همان endpoint رد شود (بلاکرِ امنیتیِ B3)."""
    if http_guard.allow((_client_ip(request), path), settings.webhook_rate_limit_per_minute):
        return None
    observability.count("webhook.rate_limited")
    logger.warning("سقفِ نرخِ endpoint=%s از IP=%s رد شد.", path, _client_ip(request))
    return Response(status_code=429, headers={"Retry-After": "60"})


def _denied() -> Response:
    """۴۰۳ بی‌صدایِ رازِ نامعتبر برایِ endpointهایِ نظارتی (بدونِ هشدارِ مکرر به ادمین)."""
    observability.count("metrics.denied")
    return Response(status_code=403)


@observability_router.get("/metrics")
async def metrics_endpoint(request: Request) -> Response:
    """شمارنده‌هایِ in-process به شکلِ متنِ Prometheus. با METRICS_TOKEN="" اصلاً وجود ندارد."""
    if not settings.metrics_token:
        return Response(status_code=404)
    provided = request.headers.get("x-metrics-token") or ""
    if not _secrets_equal(provided, settings.metrics_token):
        return _denied()
    return PlainTextResponse(observability.render_prometheus(), media_type="text/plain; version=0.0.4")


app.include_router(observability_router)


def build_health_app() -> FastAPI:
    """O2: اپِ کوچکِ سلامت برایِ حالتِ polling — **فقط** `/health` و `/metrics`.

    چرا این‌طور: در `RUN_MODE=polling` هیچ سرورِ HTTP بالا نمی‌آمد، یعنی مانیتورینگِ
    لودبالانسر/داکر و `/metrics` عملاً ناممکن بود. راهِ ساده‌تر — بالا آوردنِ اپ اصلی در هر
    دو حالت — مسیرهایِ `/webhook/*` را هم در حالتی باز می‌کرد که رازِ وب‌هوک لازم نیست
    (`validate_runtime_config` فقط در webhook آن را الزامی می‌کند) ⇒ هر کسی رویِ شبکهٔ داخلی
    می‌توانست آپدیتِ جعلی بفرستد. این اپ آن مسیرها را اصلاً ندارد.
    """
    health_app = FastAPI(title="کسب‌وکار هوشمند — سلامت", docs_url=None, redoc_url=None, openapi_url=None)
    health_app.include_router(observability_router)
    return health_app


def _start_health_server():
    """اپِ سلامت را کنارِ polling بالا می‌آورد. None ⇒ غیرفعال (`HEALTH_ENABLED=false`)."""
    if not settings.health_enabled:
        return None
    import uvicorn

    config = uvicorn.Config(
        build_health_app(),
        host=settings.webhook_listen_host,
        port=settings.webhook_listen_port,
        log_level="warning",
        access_log=False,
        lifespan="off",
    )
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    logger.info("اپِ سلامت روی %s:%s بالا آمد (فقط /health و /metrics).", config.host, config.port)
    return server, task


def _stop_health_server(health) -> None:
    if health is None:
        return
    server, task = health
    server.should_exit = True
    try:
        task.cancel()
    except Exception:  # noqa: BLE001 — بستنِ سرورِ سلامت هرگز نباید shutdown را بشکند
        logger.warning("بستنِ اپِ سلامت ناموفق بود.", exc_info=True)


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
    limited = _too_many_requests(request, "bale")
    if limited is not None:
        return limited
    """B5: رازِ وب‌هوک توی مسیره (بله هدرِ secret نمی‌فرسته)."""
    if not bale_credentials_service.bot_token():
        return Response(status_code=404)
    if not bale_credentials_service.webhook_secret() or not _secrets_equal(path_secret, bale_credentials_service.webhook_secret()):
        return _forbidden("webhook/bale: رازِ وب‌هوکِ نامعتبر")
    return await _process_bale_update(request)


@app.post("/webhook/bale")
async def webhook_bale(request: Request) -> Response:
    limited = _too_many_requests(request, "bale")
    if limited is not None:
        return limited
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


async def _dispatch_bale_update(data: dict, token: str | None = None) -> None:
    """مسیرِ مشترکِ webhook و getUpdates (B6): pre_checkout، successful_payment و P26 `/start`.

    P34: `token` توکنِ رباتی است که این آپدیت را دریافت کرده. خالی ⇒ رباتِ پرداختِ پلتفرم
    (رفتارِ همیشگی، و همان چیزی که تست‌هایِ P18/P25/P26 با آن صدا می‌زنند). وقتی مشتری لینکِ
    پرداخت را در چتِ **رباتِ بلهٔ خودِ فروشگاه** باز می‌کند، آپدیت از `bot_manager` با توکنِ همان
    ربات اینجا می‌آید و صورتحساب/استعلام هم با همان توکن انجام می‌شود — چون توکنِ درگاه برایِ
    همان ربات صادر شده و جفتِ سازگار باید بماند.
    """
    if not isinstance(data, dict):
        return
    pre_checkout = data.get("pre_checkout_query")
    if pre_checkout:
        await payment_event_service.log_event(
            "bale", "in", "pre_checkout_query", reference=pre_checkout.get("id"), raw=pre_checkout,
            group_ref=pre_checkout.get("invoice_payload"),
        )
        await _handle_bale_pre_checkout(pre_checkout, token)
        return

    message = data.get("message")
    if isinstance(message, dict) and isinstance(message.get("successful_payment"), dict):
        successful_payment = message["successful_payment"]
        await payment_event_service.log_event(
            "bale", "in", "successful_payment", reference=successful_payment.get("telegram_payment_charge_id"),
            raw=successful_payment, group_ref=successful_payment.get("invoice_payload"),
        )
        await _handle_bale_successful_payment(successful_payment, token)
        return

    if isinstance(message, dict):
        text = (message.get("text") or "").strip()
        if text.startswith("/start"):
            await _handle_bale_payment_handoff(message, text, token)


def _bale_surface_token(token: str | None) -> str:
    """توکنِ رباتی که باید صورتِ مالی را بفرستد/استعلام کند؛ نداده ⇒ رباتِ پلتفرم (مثلِ قبل)."""
    return token or bale_credentials_service.bot_token()


async def _handle_bale_payment_handoff(message: dict, text: str, token: str | None = None) -> None:
    """P26: کاربر لینکِ `https://ble.ir/<ربات>?start=<payload>` را باز کرده است.

    بله هیچ آدرسِ پرداختی ندارد (MEASURED: `ble.ir/pay/…` ⇒ ۴۰۴) و خروجیِ `createInvoiceLink`
    فقط شناسهٔ مینی‌اپ است؛ پس این‌جا صورتحسابِ **بومیِ** بله را با `sendInvoice` به همان چت
    می‌فرستیم: کاربر دکمهٔ «پرداخت» خودِ بله را می‌بیند، `pre_checkout_query` (که هندلرش همین
    فایل است) جواب می‌گیرد و بعدِ موفقیت، همان `invoice_payload` مسیرِ شارژِ کیف‌پول/سفارش را
    پیدا می‌کند. `payload` خودش رمزِ غیرقابل‌حدس است (nonce) و هیچ هویتِ دیگری لازم نیست.

    P34: برایِ پرداختِ **سفارش** دیگر توکنِ پلتفرم فرض نمی‌شود؛ جفتِ سازگار از
    `bale_credentials_service.shop_status` خوانده می‌شود. اگر آن جفت با رباتی که این `/start`
    را دریافت کرده فرق داشت، لینکِ کهنه است و به‌جایِ فرستادنِ صورتحسابِ اشتباه (که پول را به
    کیفِ دیگری می‌برد) به کاربر گفته می‌شود لینکِ تازه بگیرد.
    """
    parts = text.split(" ", 1)
    payload = parts[1].strip() if len(parts) == 2 else ""
    chat_id = ((message.get("chat") or {}).get("id")) or ((message.get("from") or {}).get("id"))
    token = _bale_surface_token(token)
    if not token or not isinstance(chat_id, int):
        return
    if not payload:
        # کسی که خودش /start می‌زند (نه از لینکِ پرداخت) نباید با سکوت روبه‌رو شود:
        # از P26 این ربات درِ پرداخت است و کاربر حق دارد بداند اینجا کجاست.
        try:
            await bale_service.send_text(token, chat_id, main_texts.BALE_PAY_BOT_IDLE)
        except bale_service.BaleError:
            logger.exception("خوشامدِ رباتِ پرداخت (chat %s) ناموفق بود.", chat_id)
        return
    await payment_event_service.log_event("bale", "in", "start_handoff", reference=payload[:128], raw={"text": text, "chat_id": chat_id})

    title = description = ""
    amount_toman: int | None = None
    provider_token: str | None = None
    surface_token: str | None = None
    note = ""

    async with session_scope() as session:
        admin_settings = await get_admin_settings(session)
        if payload.startswith("payment-"):
            payment = await payment_service.get_by_bale_payload(session, payload)
            if payment is not None and payment.status == PaymentStatus.PENDING:
                amount_toman = int(payment.final_amount)
                title = "اشتراکِ سرویس" if payment.purpose == PaymentPurpose.SUBSCRIPTION else "شارژِ کیف‌پول"
                description = f"{title} — کسب‌وکار هوشمند"
                # این مسیر «فروشگاه‌دار به پلتفرم» است: جفتِ سراسریِ خودِ پلتفرم، هیچ‌وقت درگاهِ فروشگاه.
                provider_token = (admin_settings.bale_provider_token or "").strip()
                surface_token = bale_credentials_service.bot_token()
            elif payment is not None:
                note = main_texts.BALE_PAY_ALREADY_SETTLED
            else:
                note = main_texts.BALE_PAY_LINK_UNKNOWN
        elif payload.startswith(("cartgroup-", "order-")):
            shop_bot = None
            found = False
            settled = False
            if payload.startswith("cartgroup-"):
                group_payment = await order_payment_service.get_by_provider_ref(
                    session, payload, payment_settings_service.METHOD_BALE
                )
                if group_payment is not None:
                    found = True
                    if group_payment.status in (
                        order_payment_service.P_INITIATED,
                        order_payment_service.P_EXPIRED,
                    ):
                        rows = await order_payment_service.group_rows(session, group_payment.shop_bot_id, group_payment.group_id)
                        amount_toman = order_transition_service.group_total_toman(rows)
                        shop_bot = await session.get(ShopBot, group_payment.shop_bot_id)
                    else:
                        settled = True
            else:
                order = await order_service.get_by_bale_payload(session, payload)
                if order is not None:
                    found = True
                    if order.bale_paid_at is None:
                        # P34 (باگِ لو‌رفته در همین فاز): این ستونِ سفارش `estimated_value_toman`
                        # است؛ `total_toman` رویِ این مدل وجود ندارد و خواندنش وسطِ صورتحساب
                        # AttributeError می‌داد، یعنی لینکِ پرداختِ تک‌سفارش مرده بود.
                        amount_toman = int(order.estimated_value_toman or 0)
                        shop_bot = await session.get(ShopBot, order.shop_bot_id)
                    else:
                        settled = True
            if amount_toman:
                title = "پرداختِ سفارش"
                description = "سفارش از فروشگاه کسب‌وکار هوشمند"
                pay_settings_row = await payment_settings_service.get_or_create(session, shop_bot.id)
                status = await bale_credentials_service.shop_status(session, shop_bot, pay_settings_row)
                if status.available:
                    provider_token = status.provider_token
                    surface_token = status.bot_token
                else:
                    # تنظیماتِ فروشگاه وسطِ کار عوض/ناقص شده (کلیدِ بله خاموش، درگاه حذف‌شده):
                    # به‌جایِ ساختنِ صورتحسابی که پول را جایِ دیگری می‌برد، صادقانه می‌گوییم.
                    amount_toman = None
                    note = main_texts.BALE_PAY_NOT_CONFIGURED
            elif settled:
                note = main_texts.BALE_PAY_ALREADY_SETTLED
            elif found:
                # ردیف هست ولی مبلغی برایِ گرفتن نمی‌ماند (تسویه/انقضایِ مهلتِ پرداخت).
                note = "این سفارش دیگر مهلتِ پرداخت ندارد؛ از پنلِ فروشگاه دوباره «پرداخت» را بزن."
            else:
                note = main_texts.BALE_PAY_LINK_UNKNOWN
        else:
            note = "این لینک برایِ پرداخت نیست."

    if not amount_toman or not provider_token:
        if note:
            try:
                await bale_service.send_text(token, chat_id, note)
            except bale_service.BaleError:
                logger.exception("پاسخِ لینکِ پرداخت (chat %s) ناموفق بود.", chat_id)
        return

    if surface_token != token:
        # لینکِ این پرداخت برایِ رباتِ دیگری ساخته شده است. فرستادنِ صورتحسابِ این ربات با
        # توکنِ درگاهِ آن ربات یعنی «قاطی‌شدنِ جفت» و مقصدِ پول عوض می‌شود — همان باگِ
        # گزارش‌شده. پس لینکِ تازه می‌خواهیم، نه پرداختِ به حسابِ اشتباه.
        logger.warning("لینکِ پرداختِ %s با رباتِ دریافت‌کننده نمی‌خواند؛ صورتحساب ساخته نشد.", payload[:40])
        try:
            await bale_service.send_text(token, chat_id, main_texts.BALE_PAY_LINK_STALE)
        except bale_service.BaleError:
            logger.exception("پاسخِ لینکِ کهنه (chat %s) ناموفق بود.", chat_id)
        return

    try:
        await bale_service.send_invoice(
            token, chat_id, provider_token, title=title, description=description,
            payload=payload, amount_rial=bale_service.toman_to_rial(amount_toman),
        )
    except bale_service.BaleError:
        logger.exception("فرستادنِ صورتحسابِ بله برایِ %s ناموفق بود.", payload[:40])
        try:
            await bale_service.send_text(token, chat_id, main_texts.BALE_PAY_ERROR)
        except bale_service.BaleError:
            logger.exception("پاسخِ خطایِ صورتحساب هم ناموفق بود (chat %s).", chat_id)


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


async def _handle_bale_pre_checkout(pre_checkout: dict, token: str | None = None) -> None:
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
        await bale_service.answer_pre_checkout_query(_bale_surface_token(token), query_id, ok=ok, error_message=error_message)
    except bale_service.BaleError:
        logger.exception("پاسخ‌دادن به pre_checkout_query بله ناموفق بود (query_id=%s).", query_id)


async def _handle_bale_successful_payment(successful_payment: dict, token: str | None = None) -> None:
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
        await _handle_bale_cartgroup_payment(invoice_payload, transaction_id, token)
        return

    if invoice_payload.startswith("order-"):
        await _handle_bale_order_payment(invoice_payload, transaction_id, token)
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
            transaction = await bale_service.inquire_transaction(_bale_surface_token(token), transaction_id)
        except bale_service.BaleError:
            logger.exception("استعلامِ تراکنشِ بله ناموفق بود (transaction_id=%s) — کیف‌پول شارژ نشد.", transaction_id)
            return

        if not await _bale_outcome_ok(transaction, payment.final_amount, "wallet/subscription", group_ref=invoice_payload):
            return

        _effect, reward_info = await payment_service.approve_bale_payment(session, payment, transaction_id)
        if _effect is None:
            # وب‌هوکِ تکراریِ همان تراکنش (بله گاهی دو بار می‌فرستد) ⇒ بدونِ شارژِ دوباره و بدونِ پیامِ تکراری.
            logger.info("پرداختِ بله (%s) پیش‌تر تایید شده بود؛ شارژِ دوباره انجام نشد.", transaction_id)
            return
        owner = await shop_owner_service.get_by_id(session, payment.shop_owner_id)
        owner_telegram_id = owner.telegram_id
        is_topup = payment.purpose == PaymentPurpose.WALLET_TOPUP
        wallet_amount_toman = payment.final_amount if is_topup else None

    await _notify_payment_result(_state["main_bot"], owner_telegram_id, is_topup, wallet_amount_toman, reward_info)


_BALE_RETRY_DELAYS = (5, 20, 60, 180)  # B3: استعلامِ «در انتظار» با backoff دوباره تلاش می‌شه


async def _handle_bale_new_flow(payment_id: int, shop_bot_id: int, transaction_id: str, attempt: int = 0, token: str | None = None) -> None:
    """W4 (C7): پرداختِ بله‌پیِ جریانِ تازه. فقط بعد از استعلامِ سمتِ سرور + تطبیقِ مبلغ ⇒ `paid`؛
    وضعیتِ «در انتظار» با backoff دوباره پرسیده می‌شه؛ نامشخص/ناموفق ⇒ هیچ تغییری (لاگ در payment_event_logs)."""
    notify = None
    async with session_scope() as session:
        payment = await session.get(OrderPayment, payment_id)
        if payment is None or payment.status == order_payment_service.P_PAID:
            return
        try:
            transaction = await bale_service.inquire_transaction(_bale_surface_token(token), transaction_id)
        except bale_service.BaleError:
            logger.exception("استعلامِ تراکنشِ بله ناموفق بود (transaction_id=%s) — سفارش پرداخت‌شده علامت نخورد.", transaction_id)
            return
        if bale_service.classify_transaction_status(transaction) == "pending":
            await payment_event_service.log_event(
                "bale", "in", "inquire_result:cart", status="pending", raw=transaction,
                shop_bot_id=shop_bot_id, group_ref=payment.provider_ref,
            )
            if attempt < len(_BALE_RETRY_DELAYS):
                asyncio.create_task(_retry_bale_new_flow(payment_id, shop_bot_id, transaction_id, attempt, token))
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


async def _retry_bale_new_flow(payment_id: int, shop_bot_id: int, transaction_id: str, attempt: int, token: str | None = None) -> None:
    await asyncio.sleep(_BALE_RETRY_DELAYS[attempt])
    try:
        await _handle_bale_new_flow(payment_id, shop_bot_id, transaction_id, attempt + 1, token)
    except Exception:
        logger.exception("تلاشِ مجددِ استعلامِ بله ناموفق بود (transaction_id=%s).", transaction_id)


async def _handle_bale_cartgroup_payment(invoice_payload: str, transaction_id: str, token: str | None = None) -> None:
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
        await _handle_bale_new_flow(new_flow[0], new_flow[1], transaction_id, token=token)
        return

    async with session_scope() as session:
        orders = await order_service.get_by_cart_checkout_group(session, group_id)

        try:
            transaction = await bale_service.inquire_transaction(_bale_surface_token(token), transaction_id)
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
        customer_platform = customer.platform if customer is not None else None

    try:
        await _state["main_bot"].send_message(owner_telegram_id, main_texts.cart_paid_online_notification(order_count, total_toman))
    except TelegramAPIError:
        logger.exception("اطلاع‌رسانیِ پرداختِ آنلاینِ سبد به فروشگاه‌دار %s ناموفق بود.", owner_telegram_id)

    shop_bot_instance = _state["bot_manager"].customer_bot(shop_bot_id, customer_platform)
    if shop_bot_instance is not None and customer_telegram_id is not None:
        try:
            await shop_bot_instance.send_message(customer_telegram_id, shop_texts.ONLINE_PAYMENT_CONFIRMED)
        except TelegramAPIError:
            logger.exception("اطلاع‌رسانیِ تاییدِ پرداخت به مشتری %s ناموفق بود.", customer_telegram_id)


async def _handle_bale_order_payment(invoice_payload: str, transaction_id: str, token: str | None = None) -> None:
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
            transaction = await bale_service.inquire_transaction(_bale_surface_token(token), transaction_id)
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
        order_id = order.id
        customer_platform = customer.platform if customer is not None else None

    try:
        await _state["main_bot"].send_message(owner.telegram_id, main_texts.order_paid_online_notification(order))
    except TelegramAPIError:
        logger.exception("اطلاع‌رسانیِ پرداختِ آنلاینِ سفارشِ %s به فروشگاه‌دار %s ناموفق بود.", order_id, owner.telegram_id)

    shop_bot_instance = _state["bot_manager"].customer_bot(shop_bot.id, customer_platform)
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
async def zarinpal_callback(Authority: str, Status: str, request: Request) -> HTMLResponse:
    limited = _too_many_requests(request, "zarinpal-callback")
    if limited is not None:
        return HTMLResponse("درخواست‌ها بیش از حد معمول شده. لطفاً یک دقیقه دیگر دوباره امتحان کن.")
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
        if _effect is None:
            # رفرشِ صفحهٔ بازگشت ⇒ همان پرداخت یک بارِ دیگر تایید می‌شد؛ صفحهٔ موفق را می‌دهیم ولی شارژِ دوباره نه.
            logger.info("پرداختِ زرین‌پال (authority=%s) پیش‌تر تایید شده بود.", Authority)
            return HTMLResponse(main_texts.ZARINPAL_PAYMENT_SUCCESSFUL_PAGE)
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
