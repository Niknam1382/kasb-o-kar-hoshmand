"""منبعِ واحدِ حقیقتِ اعتبارهایِ بله‌پی (P18 · A1 + B11).

سه مقدار برایِ پرداختِ بله‌پی لازم است و یکِ مقدار اختیاری (همه از پنلِ ادمین، بدونِ ری‌استارت):

۱) **توکنِ رباتِ بله** (`bale_bot_token`) — سراسری؛ همان چیزی که رباتِ بله با آن کار می‌کند
   (getUpdates / setWebhook / createInvoiceLink / inquireTransaction). اولویت: پنل ← `.env`.
۲) **توکنِ درگاه (provider_token)** — تعیین می‌کند پول در کیف‌پولِ چه کسی می‌نشیند.
   اولویت: فروشگاه ← پنلِ ادمین (پشتیبانِ سراسری).
۳) **رازِ وب‌هوک** — فقط در `BALE_UPDATES_MODE=webhook` لازم است و **خودکار** ساخته می‌شود؛
   هرگز از ادمین پرسیده نمی‌شود (در `polling` که پیش‌فرض است اصلاً لازم نیست).
۴) **نامِ کاربریِ رباتِ پرداخت** — از `getMe` خوانده و کش می‌شود (هیچ‌وقت از ادمین پرسیده نمی‌شود).
   لینکِ پرداختِ بله از همین ساخته می‌شود: `https://ble.ir/<username>?start=<payload>`.
   این همیشه رباتِ پلتفرم است، نه رباتِ بله‌یِ خودِ فروشگاه — آن ربات فقط پیام می‌فرستد و
   آپدیت‌هایش را نمی‌خوانیم، پس `/start`ِ لینک هرگز به ما نمی‌رسید (`pay_link_username`).
   از P26 دیگر ستونی به‌نامِ «قالبِ لینک» مصرف نمی‌شود: بله هیچ آدرسِ پرداختی ندارد
   (`ble.ir/pay/…` و `bale.ai/pay/<id>` هر دو ۴۰۴ — MEASURED) و خروجیِ `createInvoiceLink` فقط
   شناسهٔ مینی‌اپ است. ستونِ `bale_pay_link_template` در دیتابیس می‌ماند (قاعدهٔ «حذفِ ستون نه»)
   ولی هیچ کدی آن را نمی‌خواند و در پنل هم نیست.

هیچ مقدارِ خامی در این ماژول لاگ یا برگردانده نمی‌شود؛ نمایش فقط ماسک‌شده (در `texts`).
ملاکِ `shop_status` *تنها* معیاری است که هم «نمایشِ دکمه به مشتری» و هم «شروعِ پرداخت» از آن
استفاده می‌کنند، پس این دو هیچ‌وقت با هم اختلاف پیدا نمی‌کنند (علتِ ریشه‌یِ B11).
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
    """نامِ رباتی که لینکِ پرداخت به چتش می‌رود — همیشه رباتِ پرداختِ پلتفرم.

    چرا رباتِ بله‌یِ خودِ فروشگاه نه؟ چون آن ربات فقط برایِ فرستادنِ پیام است: در `bot_manager` و
    `app/main.py` فقط توکنِ پلتفرم `set_webhook`/`getUpdates` می‌شود، پس `/start`ِ لینکِ
    پرداخت در چتِ رباتِ فروشگاه هیچ‌وقت به ما نمی‌رسید و لینک مرده می‌شد. جابه‌جاییِ پول
    به نامِ کاربری وابسته نیست، به `provider_token` وابسته است (همین را صفحهٔ پنل هم می‌گوید).
    """
    return _panel_bot_username


def pay_link_available() -> bool:
    """P26 (قاعدهٔ B11): دکمه فقط وقتی ساخته می‌شود که لینکِ پرداخت هم ساخته‌شدنی باشد."""
    from app.services import bale_service  # لازیم؛ چرخه‌یِ import را می‌شکند

    return bale_service.pay_chat_link(pay_link_username(), "payment-0-0") is not None


def pay_link_for(payload: str) -> str | None:
    """لینکِ «برو به پرداختِ بله» برایِ این پرداخت. None ⇒ چیزی نساز و پیامِ صادقانه بده."""
    from app.services import bale_service  # لازیم؛ چرخه‌یِ import را می‌شکند

    return bale_service.pay_chat_link(pay_link_username(), payload)


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
    """توکنِ درگاه: اولِ خودِ فروشگاه، بعدِ پنلِ ادمین به‌عنوانِ پشتیبانِ سراسری."""
    own = ((shop_bot.bale_provider_token if shop_bot is not None else None) or "").strip()
    if own:
        return own
    row = await get_admin_settings(session)
    return (row.bale_provider_token or "").strip() or None


class ShopBaleStatus:
    """نتیجه‌یِ بررسیِ پیش‌نیازهایِ بله‌پی برایِ یک فروشگاه."""

    __slots__ = ("bot_token", "provider_token", "missing")

    def __init__(self, bot_token: str, provider_token: str | None, missing: tuple[str, ...]) -> None:
        self.bot_token = bot_token
        self.provider_token = provider_token
        self.missing = missing

    @property
    def available(self) -> bool:
        return not self.missing


async def shop_status(
    session: AsyncSession, shop_bot: ShopBot | None, row: ShopPaymentSettings | None
) -> ShopBaleStatus:
    """*تنها* ملاکِ بله‌پی برایِ یک فروشگاه. هر دو مصرف‌کننده (کیبوردِ مشتری و `pm_bale`) از این استفاده می‌کنند."""
    missing: list[str] = []
    token = bot_token()
    if not token:
        missing.append(MISSING_BOT_TOKEN)
    if row is not None and not row.bale_enabled:
        # نبودِ ردیف یعنی فروشگاه‌دار هرگز تنظیماتِ پرداخت را باز نکرده ⇒ کلیدِ بله‌پی رویِ پیش‌فرضِ خودش (روشن) است.
        missing.append(SHOP_DISABLED)
    admin_row = await get_admin_settings(session)
    if not admin_row.bale_pay_enabled:
        missing.append(ADMIN_DISABLED)
    provider = await provider_token(session, shop_bot)
    if not provider:
        missing.append(MISSING_PROVIDER_TOKEN)
    if not pay_link_available():
        # B11/P26: دکمه‌ای که لینکش ساخته نمی‌شود، همان «دکمهٔ مرده»یِ گزارش‌شده است.
        missing.append(MISSING_PAY_BOT_USERNAME)
    return ShopBaleStatus(token, provider, tuple(missing))


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
