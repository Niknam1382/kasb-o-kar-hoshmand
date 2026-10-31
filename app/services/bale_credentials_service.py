"""منبعِ واحدِ حقیقتِ اعتبارهایِ بله‌پی (P18 · A1 + B11).

سه مقدار برایِ پرداختِ بله‌پی لازم است و هر سه می‌توانند از پنلِ ادمین بیایند (بدونِ ری‌استارت):

۱) **توکنِ رباتِ بله** (`bale_bot_token`) — سراسری؛ همان چیزی که رباتِ بله با آن کار می‌کند
   (getUpdates / setWebhook / createInvoiceLink / inquireTransaction). اولویت: پنل ← `.env`.
۲) **توکنِ درگاه (provider_token)** — مجوزِ ساختِ لینکِ پرداخت. اولویت: فروشگاه ← پنلِ ادمین (پشتیبان).
۳) **رازِ وب‌هوک** — فقط در `BALE_UPDATES_MODE=webhook` لازم است و **خودکار** ساخته می‌شود؛
   هرگز از ادمین پرسیده نمی‌شود (در `polling` که پیش‌فرض است اصلاً لازم نیست).

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
ADMIN_DISABLED = "admin_disabled"
SHOP_DISABLED = "shop_disabled"

# کشِ درون‌حافظه‌ایِ *فقط* مقدارِ پنل؛ مقدارِ .env همیشه زنده خوانده می‌شود تا تغییرِ پنل
# بدونِ ری‌استارت اثر کند و تست‌هایی که settings را جایگزین می‌کنند نشکنند.
_panel_bot_token: str = ""
_auto_webhook_secret: str = ""


def bot_token() -> str:
    """توکنِ رباتِ بله: پنلِ ادمین ← `.env`. خالی ⇒ بله‌پی غیرفعال."""
    return _panel_bot_token or (settings.bale_bot_token or "")


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
    global _panel_bot_token, _auto_webhook_secret
    _panel_bot_token = ""
    _auto_webhook_secret = ""


async def refresh(session: AsyncSession) -> str:
    """کش را از `AdminSettings` تازه می‌کند. در startup، در هر گردشِ حلقه‌یِ getUpdates و بلافاصله
    بعدِ ذخیره‌یِ توکن در پنل صدا زده می‌شود ⇒ تغییر بدونِ ری‌استارت اعمال می‌گردد."""
    global _panel_bot_token, _auto_webhook_secret
    row = await get_admin_settings(session)
    _panel_bot_token = (row.bale_bot_token or "").strip()
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
    return ShopBaleStatus(token, provider, tuple(missing))


async def methods(
    session: AsyncSession, shop_bot: ShopBot | None, row: ShopPaymentSettings | None, *, include_manual: bool = True
) -> list[str]:
    """فهرستِ روش‌هایِ پرداختِ مشتری با بله‌پیِ راستی‌آزمایی‌شده (جایگزینِ صدازدنِ مستقیمِ payment_settings_service)."""
    status = await shop_status(session, shop_bot, row)
    resolver = payment_settings_service.checkout_methods if include_manual else payment_settings_service.online_methods
    return resolver(row, shop_bot, bale_available=status.available)


def platform_status(session_row) -> tuple[bool, list[str]]:
    """مسیرِ سراسری (شارژِ کیف‌پولِ فروشگاه‌دار به پلتفرم): توکنِ ربات + توکنِ درگاهِ ادمین + کلیدِ ادمین."""
    missing: list[str] = []
    if not bot_token():
        missing.append(MISSING_BOT_TOKEN)
    if not getattr(session_row, "bale_pay_enabled", False):
        missing.append(ADMIN_DISABLED)
    if not (getattr(session_row, "bale_provider_token", None) or ""):
        missing.append(MISSING_PROVIDER_TOKEN)
    return (not missing, missing)
