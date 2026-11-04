"""منبعِ واحدِ حقیقتِ اعتبارهایِ بله‌پی (P18 · A1 + B11).

سه مقدار برایِ پرداختِ بله‌پی لازم است و یکِ مقدار اختیاری (همه از پنلِ ادمین، بدونِ ری‌استارت):

۱) **توکنِ رباتِ بله** (`bale_bot_token`) — سراسری؛ همان چیزی که رباتِ بله با آن کار می‌کند
   (getUpdates / setWebhook / createInvoiceLink / inquireTransaction). اولویت: پنل ← `.env`.
۲) **توکنِ درگاه (provider_token)** — تعیین می‌کند پول در کیف‌پولِ چه کسی می‌نشیند.
   از P34 «سطحِ پرداخت» هم از همین خوانده می‌شود: توکنِ درگاه برایِ یک رباتِ خاص صادر می‌شود،
   پس فروشگاهِ هر دو را با هم ثبت کند ⇒ «رباتِ خودِ او + درگاهِ خودِ او» (پول به کیفِ خودش).
   فقط درگاه را ثبت کرده ⇒ مثلِ گذشته با رباتِ پلتفرم و یکِ هشدارِ روشن در پنل
   (`SHOP_HAS_PROVIDER_WITHOUT_BOT`).
۳) **رازِ وب‌هوک** — فقط در `BALE_UPDATES_MODE=webhook` لازم است و **خودکار** ساخته می‌شود؛
   هرگز از ادمین پرسیده نمی‌شود (در `polling` که پیش‌فرض است اصلاً لازم نیست).
۴) **نامِ کاربریِ رباتِ پرداخت** — از `getMe` خوانده و کش می‌شود (هیچ‌وقت از ادمین پرسیده نمی‌شود).
   لینکِ پرداختِ بله از همین ساخته می‌شود: `https://ble.ir/<username>?start=<payload>`.
   پیش‌فرض رباتِ پلتفرم است؛ از P34 اگر فروشگاه هر دو ورودیِ خودش را ثبت کرده باشد، لینک به
   چتِ **رباتِ بلهٔ خودِ فروشگاه** می‌رود و آپدیت‌هایِ آن را `bot_manager` می‌خواند
   (`ShopBaleStatus.username`).
   از P26 دیگر ستونی به‌نامِ «قالبِ لینک» مصرف نمی‌شود: بله هیچ آدرسِ پرداختی ندارد
   (`ble.ir/pay/…` و `bale.ai/pay/<id>` هر دو ۴۰۴ — MEASURED) و خروجیِ `createInvoiceLink` فقط
   شناسهٔ مینی‌اپ است. ستونِ `bale_pay_link_template` در دیتابیس می‌ماند (قاعدهٔ «حذفِ ستون نه»)
   ولی هیچ کدی آن را نمی‌خواند و در پنل هم نیست.

هیچ مقدارِ خامی در این ماژول لاگ یا برگردانده نمی‌شود؛ نمایش فقط ماسک‌شده (در `texts`).
ملاکِ `shop_status` *تنها* معیاری است که هم «نمایشِ دکمه به مشتری»، هم «شروعِ پرداخت» و هم
«سطحِ پرداخت» از آن خوانده می‌شوند، پس این سه هیچ‌وقت با هم اختلاف پیدا نمی‌کنند (علتِ ریشه‌یِ B11).
"""

from __future__ import annotations

import logging
import secrets

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.models import ShopBot, ShopPaymentSettings
from app.services import payment_settings_service
from app.services.admin_settings_service import get_admin_settings

logger = logging.getLogger(__name__)

# علت‌هایِ ناقص‌بودنِ پیکربندی (کدِ داخلی؛ متنِ کاربرپسند در texts.bale_missing_hint)
MISSING_BOT_TOKEN = "bot_token"
MISSING_PROVIDER_TOKEN = "provider_token"
MISSING_PAY_BOT_USERNAME = "pay_bot_username"
ADMIN_DISABLED = "admin_disabled"
SHOP_DISABLED = "shop_disabled"

# کشِ درون‌حافظه‌ایِ *فقط* مقدارِ پنل؛ مقدارِ .env همیشه زنده خوانده می‌شود تا تغییرِ پنل
# بدونِ ری‌استارت اثر کند و تست‌هایی که settings را جایگزین می‌کنند نشکنند.
_panel_bot_token: str = ""
_panel_bot_username: str = ""
_auto_webhook_secret: str = ""


def bot_token() -> str:
    """توکنِ رباتِ بله: پنلِ ادمین ← `.env`. خالی ⇒ بله‌پی غیرفعال."""
    return _panel_bot_token or (settings.bale_bot_token or "")


def bot_username() -> str:
    """نامِ کاربریِ رباتِ پرداخت (از `getMe`); خالی ⇒ لینکی نساز و صادقانه بگو."""
    return _panel_bot_username


def remember_pay_bot_username(username: str) -> None:
    """کشِ نامِ رباتِ پرداخت را می‌گذارد. در حالتِ عادی `refresh()` از `getMe` می‌خواندش؛ این
    نقطه‌یِ ورودِ تست‌ها است (تست نباید به شبکهٔ واقعیِ بله بزند)."""
    global _panel_bot_username
    _panel_bot_username = (username or "").strip().lstrip("@")


def pay_link_username() -> str:
    """نامِ رباتی که لینکِ پرداخت به چتش می‌رود — رباتِ پرداختِ پلتفرم، مگر اینکه خودِ
    فروشگاه هر دو ورودیِ خودش را ثبت کرده باشد (P34؛ آن‌وقت `ShopBaleStatus.username`).

    تا پیش از P34 این همیشه پلتفرم بود، چون آپدیت‌هایِ رباتِ بله‌یِ فروشگاه را نمی‌خواندیم و
    `/start`ِ لینک هرگز به ما نمی‌رسید. حالا همان آپدیت‌ها در `bot_manager` خوانده و به
    هندلرهایِ پرداخت می‌روند، پس پرداخت می‌تواند در چتِ رباتِ خودِ فروشگاه انجام شود.
    """
    return _panel_bot_username


def build_pay_link(username: str, payload: str) -> str | None:
    """لینکِ `ble.ir/<username>?start=<payload>` برایِ هر رباتِ داده‌شده (P34)."""
    from app.services import bale_service  # لازیم؛ چرخه‌یِ import را می‌شکند

    return bale_service.pay_chat_link(username, payload)


def pay_link_available() -> bool:
    """P26 (قاعدهٔ B11): دکمه فقط وقتی ساخته می‌شود که لینکِ پرداخت هم ساخته‌شدنی باشد."""
    return build_pay_link(pay_link_username(), "payment-0-0") is not None


def pay_link_for(payload: str, username: str | None = None) -> str | None:
    """لینکِ «برو به پرداختِ بله» برایِ این پرداخت. None ⇒ چیزی نساز و پیامِ صادقانه بده.

    `username` را `shop_status` می‌دهد تا لینک با همان جفتِ سازگارِ صورتحساب برود؛ خالی بماند
    مثلِ گذشته رباتِ پرداختِ پلتفرم است.
    """
    return build_pay_link((username or pay_link_username()), payload)


MAX_TOKEN_LENGTH = 512


def valid_token_input(raw: str | None) -> bool:
    """اعتبارسنجیِ فرمتِ توکنِ ورودیِ ادمین: بدونِ فاصله/خطِ جدید و با طولِ معقول.
    مقدارِ خام هرگز لاگ یا در پیامِ خطا برگردانده نمی‌شود."""
    text = (raw or "").strip()
    return 20 <= len(text) <= MAX_TOKEN_LENGTH and not any(ch.isspace() for ch in text)


def webhook_secret() -> str:
    """رازِ وب‌هوکِ بله: `.env` ← مقدارِ خودکارِ ذخیره‌شده در DB."""
    return (settings.bale_webhook_secret or "").strip() or _auto_webhook_secret


def reset_cache() -> None:
    """پاک‌کردنِ کش (تست / تغییرِ کلیدِ رمزنگاری)."""
    global _panel_bot_token, _panel_bot_username, _auto_webhook_secret
    _panel_bot_token = ""
    _panel_bot_username = ""
    _auto_webhook_secret = ""


async def refresh(session: AsyncSession) -> str:
    """کش را از `AdminSettings` تازه می‌کند. در startup، در هر گردشِ حلقه‌یِ getUpdates و بلافاصله
    بعدِ ذخیره‌یِ توکن در پنل صدا زده می‌شود ⇒ تغییر بدونِ ری‌استارت اعمال می‌گردد.

    نامِ کاربریِ ربات (برایِ لینکِ پرداخت) فقط یک‌بار در هر توکن از `getMe` خوانده می‌شود — این
    تابع هر ~۲۵ ثانیه هم صدا زده می‌شود و نباید هر بار درخواستِ شبکه بزند.
    """
    global _panel_bot_token, _panel_bot_username, _auto_webhook_secret
    row = await get_admin_settings(session)
    token = (row.bale_bot_token or "").strip()
    if token != _panel_bot_token:
        _panel_bot_token = token
        _panel_bot_username = ""
    effective = bot_token()
    if effective and not _panel_bot_username:
        from app.services import bale_service  # لازیم؛ چرخه‌یِ import را می‌شکند

        try:
            identity = await bale_service.get_me(effective)
            _panel_bot_username = (identity.get("username") or "").strip().lstrip("@")
            if not _panel_bot_username:
                logger.warning("بله در getMe نامِ کاربریِ رباتِ پرداخت را برنگرداند؛ لینکِ پرداخت ساخته نمی‌شود.")
        except bale_service.BaleError:
            logger.warning("خواندنِ getMe رباتِ پرداخت ناموفق بود؛ لینکِ پرداخت تا تلاشِ بعدی ساخته نمی‌شود.", exc_info=True)
    secret = (row.bale_webhook_secret_auto or "").strip()
    if not secret and settings.bale_updates_mode == "webhook" and not (settings.bale_webhook_secret or "").strip():
        # A1(ج): سکرتِ وب‌هوک هرگز پرسیده نمی‌شود — خودکار ساخته و ذخیره می‌کنیم و در پنل نشان می‌دهیم.
        secret = secrets.token_urlsafe(32)
        row.bale_webhook_secret_auto = secret
        await session.flush()
        logger.info("رازِ وب‌هوکِ بله خودکار ساخته و رمزنگاری‌شده ذخیره شد (در پنلِ ادمین قابلِ مشاهده است).")
    _auto_webhook_secret = secret
    return bot_token()


async def provider_token(session: AsyncSession, shop_bot: ShopBot | None) -> str | None:
    """توکنِ درگاهی که *در دسترس* است: اولِ خودِ فروشگاه، بعدِ پنلِ ادمین به‌عنوانِ پشتیبانِ سراسری.

    ⚠️ از P34 این دیگر برایِ ساختنِ صورتحساب استفاده **نمی‌شود** (جفتِ سازگارِ «ربات + درگاه» را
    فقط `shop_status` می‌دهد). اینجا مصرفش دیدنِ این است که «آیا اصلاً درگاهی وجود دارد» — برایِ
    متنِ وضعیت و هشدارها، نه برایِ فرستادنِ پول.
    """
    own = ((shop_bot.bale_provider_token if shop_bot is not None else None) or "").strip()
    if own:
        return own
    row = await get_admin_settings(session)
    return (row.bale_provider_token or "").strip() or None


class ShopBaleStatus:
    """نتیجه‌یِ بررسیِ پیش‌نیازهایِ بله‌پی برایِ یک فروشگاه.

    P34: این دیگر فقط «آیا بله‌پی فعال است» نیست، **سطحِ پرداخت** را هم تعیین می‌کند: با کدام
    توکنِ ربات صورتحساب ساخته می‌شود، پول به کدام کیف می‌رود و لینکِ پرداخت به چتِ کدام ربات
    می‌رود (`username`). توکنِ درگاه برایِ یک رباتِ خاص صادر می‌شود، پس وقتی فروشگاه هر دو
    ورودیِ خودش را دارد، جفتِ «رباتِ او + درگاهِ او» استفاده می‌شود و دیگر هیچ‌گاه با رباتِ
    پلتفرم قاطی نمی‌شود.
    """

    __slots__ = ("bot_token", "provider_token", "missing", "username", "uses_own_bot", "shop_bot_id", "warnings")

    def __init__(
        self,
        bot_token: str,
        provider_token: str | None,
        missing: tuple[str, ...],
        *,
        username: str = "",
        uses_own_bot: bool = False,
        shop_bot_id: int | None = None,
        warnings: tuple[str, ...] = (),
    ) -> None:
        self.bot_token = bot_token
        self.provider_token = provider_token
        self.missing = missing
        self.username = username
        self.uses_own_bot = uses_own_bot
        self.shop_bot_id = shop_bot_id
        self.warnings = warnings

    @property
    def available(self) -> bool:
        return not self.missing


# هشدارها (برخلافِ `missing`) پرداخت را خاموش نمی‌کنند، فقط می‌گویند مقصدِ پول عوض شده است.
SHOP_HAS_PROVIDER_WITHOUT_BOT = "shop_provider_without_bale_bot"
SHOP_HAS_BOT_WITHOUT_PROVIDER = "shop_bale_bot_without_provider"


async def shop_status(
    session: AsyncSession, shop_bot: ShopBot | None, row: ShopPaymentSettings | None
) -> ShopBaleStatus:
    """*تنها* ملاکِ بله‌پی برایِ یک فروشگاه **و** تنها منبعِ سطحِ پرداخت.

    هر سه مصرف‌کننده (کیبوردِ مشتری، `pm_bale` و ساختِ صورتحساب) از این می‌خوانند، پس «دکمه‌ای
    که نشان داده می‌شود»، «پرداختی که ساخته می‌شود» و «مقصدِ پول» هیچ‌وقت از هم جدا نمی‌شوند
    (علتِ ریشه‌یِ B11).

    قاعدهٔ P34 — افزودنی، تا هیچ فروشگاهِ فعلی بدونِ پرداخت نماند:
    • فروشگاه **هر دو** ورودی را ثبت کرده (توکنِ رباتِ بله + توکنِ درگاه) ⇒ جفتِ *خودش*:
      صورتحساب با رباتِ او و درگاهِ او ساخته می‌شود و لینک به چتِ همان ربات می‌رود، پس پول در
      کیف‌پولِ خودِ فروشگاه می‌نشیند.
    • فقط توکنِ درگاه ⇒ مثلِ گذشته با رباتِ پلتفرم (درگاهِ خودِ فروشگاه، و اگر نداشت سراسری)
      + هشدارِ `SHOP_HAS_PROVIDER_WITHOUT_BOT` که همین را به فروشگاه‌دار می‌گوید.
    • توکنِ درگاه از هیچ‌کدام ⇒ فعال نیست (علتِ `MISSING_PROVIDER_TOKEN`).
    """
    from app.services import bale_bot_service  # import محلی: چرخه‌یِ import نسازد

    missing: list[str] = []
    warnings: list[str] = []
    admin_row = await get_admin_settings(session)

    own_provider = ((shop_bot.bale_provider_token if shop_bot is not None else None) or "").strip()
    own_bot = bool(shop_bot is not None and bale_bot_service.connectable(shop_bot) and (shop_bot.bale_bot_username or "").strip())
    platform_provider = (admin_row.bale_provider_token or "").strip()

    uses_own_bot = bool(own_provider and own_bot)
    if uses_own_bot:
        token = bale_bot_service.raw_token(shop_bot)
        username = (shop_bot.bale_bot_username or "").strip()
        provider = own_provider
    else:
        token = bot_token()
        username = _panel_bot_username
        provider = own_provider or platform_provider or None
        if not token:
            missing.append(MISSING_BOT_TOKEN)
        if own_provider and not own_bot:
            warnings.append(SHOP_HAS_PROVIDER_WITHOUT_BOT)
        if own_bot and not own_provider:
            warnings.append(SHOP_HAS_BOT_WITHOUT_PROVIDER)

    if row is not None and not row.bale_enabled:
        # نبودِ ردیف یعنی فروشگاه‌دار هرگز تنظیماتِ پرداخت را باز نکرده ⇒ کلیدِ بله‌پی رویِ پیش‌فرضِ خودش (روشن) است.
        missing.append(SHOP_DISABLED)
    if not admin_row.bale_pay_enabled:
        missing.append(ADMIN_DISABLED)
    if not provider:
        missing.append(MISSING_PROVIDER_TOKEN)
    if not username or build_pay_link(username, "payment-0-0") is None:
        # B11/P26: دکمه‌ای که لینکش ساخته نمی‌شود، همان «دکمهٔ مرده»یِ گزارش‌شده است.
        missing.append(MISSING_PAY_BOT_USERNAME)
    return ShopBaleStatus(
        token,
        provider,
        tuple(missing),
        username=username,
        uses_own_bot=uses_own_bot,
        shop_bot_id=(shop_bot.id if (shop_bot is not None and uses_own_bot) else None),
        warnings=tuple(warnings),
    )


async def methods(
    session: AsyncSession, shop_bot: ShopBot | None, row: ShopPaymentSettings | None, *, include_manual: bool = True
) -> list[str]:
    """فهرستِ روش‌هایِ پرداختِ مشتری با بله‌پیِ راستی‌آزمایی‌شده (جایگزینِ صدازدنِ مستقیمِ payment_settings_service)."""
    status = await shop_status(session, shop_bot, row)
    resolver = payment_settings_service.checkout_methods if include_manual else payment_settings_service.online_methods
    return resolver(row, shop_bot, bale_available=status.available)


def platform_status(session_row) -> tuple[bool, list[str]]:
    """مسیرِ سراسری (شارژِ کیف‌پولِ فروشگاه‌دار به پلتفرم): توکنِ ربات + کلیدِ ادمین + توکنِ درگاهِ ادمین.

    پیش‌نیازِ چهارم نامِ کاربریِ همان ربات است (`MISSING_PAY_BOT_USERNAME`): لینکِ پرداخت
    به شکلِ `ble.ir/<username>` ساخته می‌شود و بدونِ آن دکمه‌ای ساخته نمی‌شود — قاعدهٔ B11.
    """
    missing: list[str] = []
    if not bot_token():
        missing.append(MISSING_BOT_TOKEN)
    if not getattr(session_row, "bale_pay_enabled", False):
        missing.append(ADMIN_DISABLED)
    if not (getattr(session_row, "bale_provider_token", None) or ""):
        missing.append(MISSING_PROVIDER_TOKEN)
    if not pay_link_available():
        missing.append(MISSING_PAY_BOT_USERNAME)
    return (not missing, missing)
