from __future__ import annotations

import asyncio
import logging
from collections import OrderedDict

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramAPIError, TelegramUnauthorizedError

from app.config import RunMode, settings
from app.database.models import ShopBot
from app.database.session import session_scope
from app.services import bale_bot_service, platform_service
from app.utils.encryption import decrypt_token

logger = logging.getLogger(__name__)


class _SharedAiohttpSession:
    """استخرِ اشتراکیِ HTTP برایِ ربات‌هایی که در حالتِ webhook lazily ساخته می‌شوند (P45).

    هر `Bot` در aiogram یک `AiohttpSession` با `TCPConnector`ِ خودش می‌سازد؛ با ۱٬۵۰۰ فروشگاه
    یعنی ۱٬۵۰۰ استخرِ اتصال و ~۰٫۵ مگابایت رم به‌ازایِ هر اتصال (MEASURED در scale_probe). این
    پوششِ نازک همان `close()` را برایِ همهٔ ربات‌ها به یکِ connector برمی‌گرداند، پس ساختنِ ربات
    تقریباً رایگان است و بستنِ یکی، بقیه را نمی‌شکند. (استخرِ polling عمداً دست‌نخورده ماند:
    درخواستِ ۲۰ ثانیه‌ایِ بلندِ `getUpdates` رویِ connector مشترک، سقفِ اتصالِ کلِ پروسه را می‌بلعد.)
    """

    def __init__(self, inner) -> None:
        self._inner = inner
        self._refs = 0

    def __getattr__(self, item):
        return getattr(self._inner, item)

    async def close(self) -> None:
        return None

    async def dispose(self) -> None:
        await self._inner.close()


class ShopBotManager:
    """
    ثبت/حذفِ پویایِ ربات‌های فروشگاهی در زمانِ اجرا (بدون نیاز به ری‌استارتِ
    کل برنامه). هر ربات یا یه تسکِ polling مجزا داره (حالت polling) یا از
    طریق روتِ webhook مشترک /webhook/shop/{shop_bot_id} فید می‌شه.

    هر فروشگاه می‌تونه *دو* اتصال داشته باشد: رباتِ تلگرام (همان مسیرِ بالا) و
    رباتِ بله‌یِ خودش (`_bale_bots`). اتصالِ بله همیشه polling است، چون بله
    رازِ وب‌هوک نمی‌فرستد و مسیرِ وب‌هوکِ مشترکِ تلگرام به آن نمی‌خورد.
    """

    def __init__(self, dispatcher: Dispatcher) -> None:
        self._dispatcher = dispatcher
        self._bots: dict[int, Bot] = {}
        self._polling_tasks: dict[int, asyncio.Task] = {}
        self._secrets: dict[int, str] = {}
        self._bale_bots: dict[int, Bot] = {}
        self._bale_polling_tasks: dict[int, asyncio.Task] = {}
        # P42 · موردِ ۲: «توکنِ بله» دو مصرفِ جدا دارد — پرداخت (با توکنِ درگاهِ خودِ فروشگاه) و
        # هوشمندسازی (پاسخِ AI به مشتریِ بله‌ای). این جدولِ درِ حافظه می‌گوید هر اتصالِ بله به
        # روترهایِ گفت‌وگو feed شود یا فقط آپدیت‌هایِ پرداخت مصرف شوند.
        self._bale_smarten: dict[int, bool] = {}
        # P29 (MEASURED): با ۵۰۰ فروشگاه، راه‌اندازیِ قبلی همهٔ delete_webhook را در یکِ لحظه
        # می‌فرستد (اوجِ هم‌زمانی = ۵۰۰ اندازه‌گرفته‌شده) و در حالتِ webhook ترتیبی می‌ماند
        # (۲۰ ربات = ۵٫۰ ثانیه ⇒ ۵۰۰ ربات ≈ ۱۲۵ ثانیه). این درِ نیمه‌باز هر دو را به
        # N/limit × RTT می‌رساند و هیچ رباتی را جا نمی‌اندازد.
        self._start_gate = asyncio.Semaphore(max(1, settings.bot_register_concurrency))
        # P45 · ظرفیت: ربات‌هایِ ساخته‌شده برایِ webhook (استخرِ HTTP مشترک + LRU) و رازِ همان‌ها.
        self._webhook_bots: OrderedDict[int, Bot] = OrderedDict()
        self._webhook_secrets: dict[int, str | None] = {}
        self._shared_session: _SharedAiohttpSession | None = None

    def get_bot(self, shop_bot_id: int) -> Bot | None:
        return self._bots.get(shop_bot_id)

    def get_bale_bot(self, shop_bot_id: int) -> Bot | None:
        return self._bale_bots.get(shop_bot_id)

    def customer_bot(self, shop_bot_id: int, platform: str | None) -> Bot | None:
        """رباتِ *همان پلتفرمی* که مشتری روی آن است.

        فرستادنِ شناسه‌یِ عددیِ یک مشتریِ بله‌ای از روی رباتِ تلگرام می‌تونه به آدمِ
        غریبه‌یِ دیگری برسد که تصادفاً همان عدد را دارد — پس پلتفرم همیشه باید بپرسیم.
        """
        if platform == platform_service.BALE:
            return self.get_bale_bot(shop_bot_id)
        return self.get_bot(shop_bot_id)

    def registered_shop_bot_ids(self) -> list[int]:
        return list(self._bots.keys())

    def registered_bale_bot_ids(self) -> list[int]:
        return list(self._bale_bots.keys())

    def get_secret(self, shop_bot_id: int) -> str | None:
        return self._secrets.get(shop_bot_id)

    @staticmethod
    def owns_shard(shop_bot_id: int) -> bool:
        """P45: آیا این پروسه صاحبِ pollingِ این فروشگاه است؟

        فقط برایِ حالتِ polling معنا دارد؛ در حالتِ webhook هر پروسهٔ دریافت می‌تواند به هر
        فروشگاه جواب بدهد (پراکسی round-robin می‌کند) و آنجا شارد نمی‌شناسیم."""
        count = max(1, int(settings.shard_count or 1))
        if count == 1:
            return True
        index = int(settings.shard_index or 0) % count
        return int(shop_bot_id) % count == index

    async def webhook_entry(self, shop_bot_id: int) -> tuple[Bot, str | None] | None:
        """(ربات، رازِ وب‌هوک) برایِ `/webhook/shop/{id}` — بدونِ آن‌که این پروسه لازم باشد همهٔ
        ربات‌ها را از لحظهٔ بوت ثبت کرده باشد (P45). None ⇒ وجود ندارد یا غیرفعال است.

        ربات‌هایِ تازه رویِ یکِ استخرِ HTTPِ مشترکی ساخته و در یکِ LRU نگه‌داشته می‌شوند، پس رمِ
        هر پروسه با فروشگاه‌هایِ *پرمصرف* رشد می‌کند نه با تعدادِ کلِ فروشگاه‌ها. هیچ‌چیز از
        دیتابیس پاک یا نوشته نمی‌شود؛ فقط خواندن."""
        bot = self._bots.get(shop_bot_id)
        if bot is not None:
            return bot, self._secrets.get(shop_bot_id)
        cached = self._webhook_bots.get(shop_bot_id)
        if cached is not None:
            self._webhook_bots.move_to_end(shop_bot_id)
            self._trim_webhook_cache()
            return cached, self._webhook_secrets.get(shop_bot_id)

        async with session_scope() as session:
            shop_bot = await session.get(ShopBot, int(shop_bot_id))
        if shop_bot is None or not shop_bot.is_active:
            return None
        built = self._build_shared_bot(shop_bot)
        if built is None:
            return None
        self._webhook_bots[shop_bot_id] = built[0]
        self._webhook_secrets[shop_bot_id] = built[1]
        self._trim_webhook_cache()
        return built

    def _trim_webhook_cache(self) -> None:
        """سقفِ LRU همیشه برقرار می‌ماند، حتی اگر ادمین عدد را پایین بیاورد."""
        while len(self._webhook_bots) > max(1, int(settings.webhook_bot_cache_size)):
            evicted_id, _evicted = self._webhook_bots.popitem(last=False)
            self._webhook_secrets.pop(evicted_id, None)

    def _build_shared_bot(self, shop_bot: ShopBot) -> tuple[Bot, str | None] | None:
        if self._shared_session is None:
            self._shared_session = _SharedAiohttpSession(AiohttpSession())
        try:
            bot = Bot(token=decrypt_token(shop_bot.encrypted_token), session=self._shared_session)
        except Exception:  # noqa: BLE001 - توکنِ خراب/ناخوانا نباید مسیرِ webhook را پایین بیاورد
            logger.exception("ساختنِ رباتِ webhook برایِ فروشگاه %s ناموفق بود.", shop_bot.id)
            return None
        self._shared_session._refs += 1
        return bot, shop_bot.webhook_secret_token

    async def register(self, shop_bot: ShopBot) -> None:
        raw_token = decrypt_token(shop_bot.encrypted_token)
        bot = Bot(token=raw_token)

        if shop_bot.id in self._bots:
            await self.unregister(shop_bot.id, disable_in_db=False)

        self._bots[shop_bot.id] = bot
        self._secrets[shop_bot.id] = shop_bot.webhook_secret_token

        if settings.run_mode == RunMode.WEBHOOK:
            webhook_url = f"{settings.webhook_base_url.rstrip('/')}/webhook/shop/{shop_bot.id}"
            await bot.set_webhook(webhook_url, secret_token=shop_bot.webhook_secret_token, drop_pending_updates=True)
        else:
            task = asyncio.create_task(self._poll(shop_bot.id, bot))
            self._polling_tasks[shop_bot.id] = task

    async def register_bale(self, shop_bot: ShopBot) -> None:
        """اتصالِ بله‌یِ این فروشگاه، فقط با *وجودِ توکن* باز می‌شود (P42 · موردِ ۲).

        توکنِ رباتِ بله هم مقصدِ پرداخت است و هم مقصدِ هوشمندسازی؛ تا پیشِ این `connectable`
        (توکن + سوییچِ هوشمندسازی) ملاک بود، پس ثبتِ توکن از صفحهٔ «پرداختِ آنلاینِ سفارش‌ها»
        ربات را هوشمند می‌کرد و برعکس، خاموش‌کردنِ هوشمندسازی پرداخت را هم می‌کشت. حالا polling
        با توکن باز می‌ماند و `_bale_smarten` تعیین می‌کند گفت‌وگو به روتر برود یا نه.
        """
        if not bale_bot_service.has_token(shop_bot):
            await self.unregister_bale(shop_bot.id)
            return
        token = bale_bot_service.raw_token(shop_bot)
        bot = bale_bot_service.build_bot(token)
        if shop_bot.id in self._bale_bots:
            await self.unregister_bale(shop_bot.id)
        self._bale_bots[shop_bot.id] = bot
        self._bale_smarten[shop_bot.id] = bool(shop_bot.bale_bot_enabled)
        self._bale_polling_tasks[shop_bot.id] = asyncio.create_task(self._poll(shop_bot.id, bot, bale=True))

    async def unregister_bale(self, shop_bot_id: int) -> None:
        self._bale_smarten.pop(shop_bot_id, None)
        bot = self._bale_bots.pop(shop_bot_id, None)
        task = self._bale_polling_tasks.pop(shop_bot_id, None)
        if task is not None:
            task.cancel()
        if bot is not None:
            try:
                await bot.delete_webhook(drop_pending_updates=False)
            except TelegramAPIError:
                pass
            await bot.session.close()

    async def _mark_disabled(self, shop_bot_id: int, reason: str) -> None:
        async with session_scope() as session:
            shop_bot = await session.get(ShopBot, shop_bot_id)
            if shop_bot is not None:
                shop_bot.is_active = False
                shop_bot.disabled_reason = reason

    async def _mark_bale_disabled(self, shop_bot_id: int, reason: str) -> None:
        """توکنِ بله مرده ⇒ فقط همان اتصال خاموش می‌شود؛ رباتِ تلگرامِ فروشگاه به کارش ادامه می‌دهد."""
        async with session_scope() as session:
            shop_bot = await session.get(ShopBot, shop_bot_id)
            if shop_bot is not None:
                shop_bot.bale_bot_enabled = False
                logger.warning("اتصالِ بله‌یِ فروشگاه %s خاموش شد: %s", shop_bot_id, reason)

    async def _poll(self, shop_bot_id: int, bot: Bot, *, bale: bool = False) -> None:
        label = "بله" if bale else "تلگرام"
        async with self._start_gate:
            try:
                await bot.delete_webhook(drop_pending_updates=True)
            except TelegramAPIError:
                logger.exception("حذف وب‌هوکِ ربات %s فروشگاهی %s ناموفق بود.", label, shop_bot_id)

        offset = None
        # فهرستِ نوعِ آپدیت‌هایِ مصرف‌شونده یک‌بار حساب می‌شود: این کوئری رویِ گرافِ روترهاست
        # و در هر گردشِ حلقه (یعنی هر ~۲۰ ثانیه به‌ازایِ هر ربات) همان نتیجه را می‌دهد.
        used_updates = self._dispatcher.resolve_used_update_types()
        if bale:
            # P34: اگر فروشگاه هر دو ورودیِ بله‌اش را گذاشته باشد، صورتحسابِ سفارش در چتِ *همین*
            # ربات باز می‌شود، پس `pre_checkout_query` هم باید به ما برسد. هیچ روترِ فروشگاهی
            # آن را هندل نمی‌کند، بنابراین `resolve_used_update_types` بیرونش می‌گذارد و بله
            # هرگز می‌فرستدش ⇒ پرداختِ بی‌صاحب. اینجا صریح اضافه‌اش می‌کنیم.
            used_updates = list(dict.fromkeys([*used_updates, "pre_checkout_query"]))
        while True:
            try:
                updates = await bot.get_updates(offset=offset, timeout=20, allowed_updates=used_updates)
            except TelegramUnauthorizedError:
                if bale:
                    logger.warning("توکنِ رباتِ بله‌یِ فروشگاه %s معتبر نیست؛ همان اتصال خاموش می‌شود.", shop_bot_id)
                    await self._mark_bale_disabled(shop_bot_id, "توکنِ بله دیگر معتبر نیست")
                    await self.unregister_bale(shop_bot_id)
                    return
                logger.warning("توکنِ ربات فروشگاهی %s دیگه معتبر نیست؛ غیرفعالش می‌کنیم.", shop_bot_id)
                await self._mark_disabled(shop_bot_id, "توکن نامعتبر شد (احتمالاً توسط فروشگاه‌دار revoke شده)")
                return
            except asyncio.CancelledError:
                raise
            except TelegramAPIError:
                logger.exception("دریافتِ آپدیت برای ربات %s فروشگاهی %s ناموفق بود؛ بعد از کمی مکث دوباره امتحان می‌کنیم.", label, shop_bot_id)
                await asyncio.sleep(5)
                continue
            except Exception:
                logger.exception("خطای غیرمنتظره در polling ربات %s فروشگاهی %s.", label, shop_bot_id)
                await asyncio.sleep(5)
                continue

            for update in updates:
                offset = update.update_id + 1
                if bale and await self._handle_bale_payment_update(bot, update):
                    continue
                if bale and not self._bale_smarten.get(shop_bot_id, False):
                    # P42 · موردِ ۲: توکن فقط برایِ پرداخت ثبت شده ⇒ گفت‌وگویِ بله‌ای به روترِ AI
                    # نمی‌رود (نه هزینه‌ای از کیف‌پول، نه پاسخِ هوشمندی). آپدیتِ پرداخت بالا مصرف شد.
                    continue
                try:
                    await self._dispatcher.feed_update(bot, update)
                except Exception:
                    logger.exception("پردازشِ یک آپدیت برای ربات %s فروشگاهی %s با خطا مواجه شد.", label, shop_bot_id)

    async def _handle_bale_payment_update(self, bot: Bot, update) -> bool:
        """P34: آپدیتِ پرداختِ بله در رباتِ بلهٔ *خودِ فروشگاه*.

        تا پیش از این، صورتحسابِ سفارش همیشه با رباتِ پلتفرم ساخته می‌شد؛ حالا که فروشگاه
        می‌تواند توکنِ رباتِ بله و توکنِ درگاهِ خودش را با هم ثبت کند، `/start`،
        `pre_checkout_query` و `successful_payment`ِ همان پرداخت در چتِ این ربات می‌آید و باید
        به همان هندلرهایِ پرداختِ `app/main.py` برود — با توکنِ همین ربات، وگرنه استعلامِ
        تراکنش و جوابِ pre_checkout رد می‌شوند.

        `True` یعنی آپدیت مصرف شد و به روترهایِ گفت‌وگو نمی‌رود (پیش‌فرضِ `customer_message`
        هر پیامِ متنی را به هوشِ مصنوعی می‌دهد؛ `/start order-…` نباید پاسخِ AI بگیرد).
        """
        try:
            raw = update.model_dump(mode="json", exclude_none=True)
        except Exception:  # noqa: BLE001 — آپدیتِ غیرمنتظره ⇒ همان مسیرِ قبل، نه خوابیدنِ حلقه
            return False

        pre_checkout = raw.get("pre_checkout_query")
        message = raw.get("message") or {}
        payload = ""
        if isinstance(pre_checkout, dict):
            payload = pre_checkout.get("invoice_payload") or ""
        elif isinstance(message.get("successful_payment"), dict):
            payload = message["successful_payment"].get("invoice_payload") or ""
        else:
            text = (message.get("text") or "").strip()
            if text.startswith("/start"):
                parts = text.split(" ", 1)
                payload = parts[1].strip() if len(parts) == 2 else ""

        # فقط پرداخت‌هایِ «مشتری ← فروشگاه». شارژِ کیف‌پولِ فروشگاه‌دار (`payment-`) همیشه با
        # رباتِ پلتفرم است؛ لینکش اینجا باز نمی‌شود، پس دست‌نخورده به روترها می‌ماند.
        if not payload.startswith(("order-", "cartgroup-")):
            return False

        from app import main as app_main  # import محلی: `app.main` خودِ این ماژول را وارد می‌کند

        try:
            await app_main._dispatch_bale_update(raw, token=bot.token)
        except Exception:
            logger.exception("پردازشِ آپدیتِ پرداختِ بله در رباتِ بلهٔ فروشگاه ناموفق بود (payload=%s).", payload[:40])
        return True

    async def load_all(self, shop_bots: list[ShopBot], *, bale_enabled: bool = False) -> None:
        """ثبتِ همهٔ ربات‌ها، با حداکثر `BOT_REGISTER_CONCURRENCY` فروشگاه هم‌زمان (P29).

        هیچ رفتاری عوض نمی‌شود: هر ربات همچنان یکِ تسکِ polling خودش را دارد، همان
        `delete_webhook(drop_pending_updates=True)` قبل از اولین `getUpdates` زده می‌شود، و همان
        لاگِ خطا برایِ رباتِ شکست‌خورده می‌ماند (پس از آن، بقیه ربات‌ها ثبت می‌شوند). فقط
        «چندتا هم‌زمان» به‌جای «همه با هم» یا «یکی‌یکی» است.
        """

        async def _one(shop_bot: ShopBot) -> None:
            # P45 · شارد: در حالتِ polling هر پروسه فقط شاردِ خودش را نگه می‌دارد ⇒ سوکت‌ها و رمِ
            # هر پروسه با تعدادِ پروسه‌ها تقسیم می‌شود. در حالتِ webhook هیچ socketِ بازِ بلندمدتی
            # نداریم، پس همه ثبت می‌شوند (set_webhook) و ترافیک بینِ پروسه‌ها تقسیم می‌شود.
            if settings.run_mode != RunMode.WEBHOOK and not self.owns_shard(shop_bot.id):
                return
            async with self._start_gate:
                try:
                    await self.register(shop_bot)
                except Exception:
                    logger.exception("بارگذاریِ ربات فروشگاهی %s در راه‌اندازی ناموفق بود.", shop_bot.id)
                if bale_enabled:
                    try:
                        await self.register_bale(shop_bot)
                    except Exception:
                        logger.exception("بارگذاریِ اتصالِ بله‌یِ فروشگاه %s ناموفق بود.", shop_bot.id)

        if shop_bots:
            await asyncio.gather(*(_one(shop_bot) for shop_bot in shop_bots))

    async def unregister(self, shop_bot_id: int, disable_in_db: bool = True) -> None:
        bot = self._bots.pop(shop_bot_id, None)
        task = self._polling_tasks.pop(shop_bot_id, None)
        self._secrets.pop(shop_bot_id, None)
        if task is not None:
            task.cancel()
        if bot is not None:
            try:
                await bot.delete_webhook(drop_pending_updates=False)
            except TelegramAPIError:
                pass
            await bot.session.close()

    async def shutdown(self) -> None:
        """بستنِ همهٔ اتصال‌ها با همان سقفِ همزمانیِ راه‌اندازی (P29).

        چرا لازم است: `unregister` یکِ `delete_webhook` شبکه‌ای منتظر می‌گیرد. در حالتِ ترتیبی،
        ۵۰۰ فروشگاه ≈ ۵۰۰ × RTT خاموش‌شدن می‌ساخت — بیشتر از `stop_grace_period` داکر ⇒ هر دیپلوی
        با SIGKILL تمام می‌شد. اینجا همان کار با `BOT_REGISTER_CONCURRENCY` درِ هم‌زمان انجام می‌شود
        و ترتیبِ عمومی (اولِ تلگرام، بعدِ بله) مثلِ قبل است.
        """
        gate = asyncio.Semaphore(max(1, settings.bot_register_concurrency))

        async def _close_telegram(shop_bot_id: int) -> None:
            async with gate:
                await self.unregister(shop_bot_id, disable_in_db=False)

        async def _close_bale(shop_bot_id: int) -> None:
            async with gate:
                await self.unregister_bale(shop_bot_id)

        telegram_ids = self.registered_shop_bot_ids()
        if telegram_ids:
            await asyncio.gather(*(_close_telegram(shop_bot_id) for shop_bot_id in telegram_ids))
        bale_ids = self.registered_bale_bot_ids()
        if bale_ids:
            await asyncio.gather(*(_close_bale(shop_bot_id) for shop_bot_id in bale_ids))
        # P45: استخرِ مشترکِ webhook یک‌بار و در پایان بسته می‌شود (بستنِ هر رباتِ تنها، بقیه را
        # از کار می‌انداخت).
        if self._shared_session is not None:
            await self._shared_session.dispose()
            self._shared_session = None
        self._webhook_bots.clear()
        self._webhook_secrets.clear()

