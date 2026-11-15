"""P49-الف: کانالِ اینستاگرام — فقط از APIِ رسمیِ پیام‌رسانیِ متا (Instagram Messaging API).

چرا اصلاً یکِ سرویسِ جدا و نه چند خطِ پیاده‌شده در هندلرها: سه تصمیمِ امنیتی/پولی در این کانال
باید *یک‌جا* گرفته شوند و هر چهار مصرف‌کننده (وب‌هوک، پنلِ ادمین، پنلِ فروشگاه‌دار، تست) همان‌ها
را بخوانند:

۱) **هیچ‌وقت مسیرِ غیررسمی.** این فایل فقط `graph.facebook.com` و `instagram.com` را صدا می‌زند و
   آدرسِ پایه را از تنظیمات *فقط* اگر https و رویِ میزبانِ رسمیِ متا باشد می‌پذیرد. مسیرِ
   غیررسمی (scraper/لیبراری‌هایِ ناامید) رمزِ کاربر را می‌خواهد و خطرِ بستنِ اکانتِ فروشگاه و
   مشتری دارد؛ به‌همین‌دلیل هرگز استفاده نمی‌شود، حتی وقتی ادمین آدرسِ دیگری بنویسد.
۲) **رازها ماسک می‌مانند.** `access_token` داخلِ بدنهِ درخواستِ form-data می‌رود (نه URL، نه لاگ).
   متنِ خطاهایِ aiohttp آدرسِ کاملِ درخواست را دارند، پس همان `payment_event_service.sanitize`
   که ردیف‌هایِ پرداخت را امن می‌کند اینجا هم رویِ هر متنِ خطا اجرا می‌شود. `psid` هم فقط دو
   رقمِ آخرش در لاگ می‌نشیند.
۳) **پول و هویت مثلِ دو کانالِ قبلی.** شناسهٔ کاربر اینستاگرام رشته است ولی ستونِ `telegram_id`
   عددی است ⇒ `customer_key` همان نگاشتِ پایدارِ P19 را می‌سازد؛ مسیرِ پاسخِ AI، نگهبانِ محتوا،
   تاریخچه و کسرِ کیف‌پول *همان توابعِ موجود* در `customer.py` و `chat_billing_service` هستند،
   پس سه کانال یکِ ریاضیِ پول دارند نه سه تا.

کامنت‌ها و پاسخِ خصوصی به کامنت در P49-B می‌آیند؛ `parse_event` برایِ آن‌ها `None` می‌دهد.
"""

from __future__ import annotations

import asyncio
import datetime
import hashlib
import hmac
import json
import logging
import re
import secrets
import time
from collections import OrderedDict
from dataclasses import dataclass

import aiohttp
from aiogram.exceptions import TelegramAPIError
from sqlalchemy import distinct, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.main_bot import texts as main_texts
from app.bots.shop_bot import texts as shop_texts
from app.database.models import (
    AuditEventType,
    ConversationMessage,
    Customer,
    InstagramAccount,
    InstagramCommentBlock,
    InstagramCommentEvent,
    OrderConsultation,
    OrderStatus,
    ShopBot,
    WalletTransactionReason,
)
from app.services import (
    ai_context,
    ai_pool_service,
    ai_service,
    ai_usage_service,
    audit_log_service,
    bale_credentials_service,
    bale_service,
    bot_error_service,
    channel_knowledge_service,
    chat_billing_service,
    conversation_service,
    crm_service,
    customer_service,
    knowledge_service,
    moderation_notify_service,
    moderation_service,
    order_access_service,
    order_payment_service,
    order_transition_service,
    payment_event_service,
    payment_settings_service,
    platform_service,
    product_service,
    prompt_defaults,
    shop_bot_service,
    shop_owner_service,
    shop_prefs_service,
    wallet_service,
)
from app.services.admin_settings_service import cached_admin_settings, get_admin_settings
from app.services.rate_limiter import rate_limiter
from app.utils import text_limits
from app.utils.validators import fa_number
from app.utils.jalali import format_jalali_datetime, to_tehran
from app.config import settings
from app.utils.encryption import decrypt_token, encrypt_token

logger = logging.getLogger(__name__)

# نسخهٔ Graph که با آن تست شده است؛ با مقدارِ خالیِ تنظیمات هم همین استفاده می‌شود.
INSTAGRAM_GRAPH_VERSION = "v21.0"
DEFAULT_GRAPH_BASE = "https://graph.facebook.com"
DEFAULT_LOGIN_BASE = "https://www.instagram.com/oauth/authorize"
# میزبان‌هایی که خارجِ این فهرست‌اند هرگز صدا زده نمی‌شوند (نگهبانِ SSRF + نشتِ توکن).
_TRUSTED_HOSTS = frozenset({"graph.facebook.com", "graph.instagram.com", "www.instagram.com", "instagram.com"})
OAUTH_SCOPES = "user_profile,messaging,instagram_business_basic,instagram_business_manage_messages,instagram_business_manage_comments"

API_TIMEOUT_SECONDS = 20.0
DM_WINDOW_SECONDS = 24 * 60 * 60  # قاعدهٔ متا: تا ۲۴ ساعت از آخرین پیامِ مشتری می‌شود پاسخ داد
_STATE_TTL_SECONDS = 20 * 60
_MAX_SEEN_EVENTS = 4000
_MAX_PAYMENT_OFFERS = 1000
# سقفِ بدنهِ وب‌هوک: متا رویدادهایِ کوچک می‌فرستد؛ بدنهٔ غول‌پیکر یا JSONِ بی‌نهایت عمداً
# خوانده/پارس نمی‌شود (همان محافظی که در مسیرهایِ دیگرِ HTTP این پروژه هست).
MAX_WEBHOOK_BODY_BYTES = 1_000_000
_PAYMENT_OFFER_COOLDOWN_SECONDS = 30 * 60
_INT64_MAX = 2**63 - 1
_SAFE_ID_RE = re.compile(r"^[0-9A-Za-z_.-]{1,64}$")
# شناسه‌هایِ متا رقم‌اند؛ «.» و «-» در مسیرِ URL یعنی `/v21.0/../x` یا آدرسِ IP، پس برایِ
# کامنت/مدیا/اکانت الگویِ سخت‌گیرانه‌تر داریم (مسیرِ دایرکت مثلِ قبل می‌ماند).
_STRICT_ID_RE = re.compile(r"^[0-9]{1,32}$|^[0-9A-Za-z_-]{1,64}$")
# میزبان‌هایِ خصوصی/لوکال (همان فهرستِ admin.py · P24): آدرسِ برگشتِ OAuth نباید به آن‌ها برود.
_INTERNAL_HOST_RE = re.compile(
    r"^(?:localhost|0\.0\.0\.0|::1|127\.|10\.|192\.168\.|169\.254\.|172\.(?:1[6-9]|2\d|3[01])\.)",
    re.IGNORECASE,
)

# آدرسِ base که از تنظیمات می‌آید یک‌بار بررسی می‌شود؛ نتیجه کش نمی‌ماند تا تغییرِ .env بدونِ
# ری‌استارت معنا داشته باشد (هزینه‌اش یکِ urlparse به‌ازایِ درخواست است، بی‌اهمیت کنارِ خودِ شبکه).
_http_session: aiohttp.ClientSession | None = None
_http_loop: object | None = None
_seen_events: OrderedDict[str, float] = OrderedDict()
_payment_offered_at: dict[int, float] = {}


class InstagramError(Exception):
    """خطایِ فارسی و ماسک‌شده. هیچ‌وقت توکن/رمز/آدرسِ کاملِ درخواست را داخلِ خود ندارد."""


@dataclass(frozen=True)
class DirectMessage:
    """پیامِ دایرکتِ ورودی (بعدِ حذفِ echo و پیام‌هایِ بی‌متن)."""

    shop_account_id: str
    sender_psid: str
    text: str
    message_id: str | None
    created_at: datetime.datetime | None


@dataclass(frozen=True)
class CommentEvent:
    """کامنتِ عمومیِ تازه رویِ پست/ریلز/استوریِ همین فروشگاه (P49-ب).

    `media_id` برایِ جوابِ عمومی لازم است (endpoint کامنت زیرِ media می‌رود) و `comment_id` برایِ
    «پاسخِ خصوصی» که فقط یک‌بار به هرِ کامنت‌کننده اجازه دارد.
    """

    comment_id: str
    media_id: str
    ig_account_id: str
    text: str
    username: str
    created_at: datetime.datetime | None


# ============================================================================= ۱ — رونمایی/دیدنی‌بودن
def enabled(admin_settings) -> bool:
    """کلیدِ سراسریِ ادمین (پیش‌فرض false ⇒ دکمهٔ «🟣 اینستاگرام» نیست و هیچ رویدادی پاسخ نمی‌رود)."""
    return bool(getattr(admin_settings, "instagram_enabled", False))


def configured(admin_settings) -> bool:
    """آیا ادمین همان سه مقداری را که بدونِ آن‌ها اتصال ممکن نیست پر کرده است؟

    `app_id` برایِ ساختنِ لینکِ اتصال، `app_secret` برایِ مبادلهٔ کد و سنجشِ امضایِ وب‌هوک، و
    `verify_token` برایِ دست‌دادنِ اولیهٔ متا (`hub.challenge`). کم‌بودنِ هر سه یعنی کانال *نیمه‌کاره*
    است: پنلِ فروشگاه‌دار لینکِ بی‌فایده می‌دهد و وب‌هوک هرگز تأیید نمی‌شود.
    """
    for field in ("instagram_app_id", "instagram_app_secret", "instagram_webhook_verify_token"):
        if not (getattr(admin_settings, field, "") or "").strip():
            return False
    return True


async def visible_for(session: AsyncSession, shop_bot_id: int) -> tuple[bool, InstagramAccount | None]:
    """همان شکلِ `bale_bot_service.enabled()/visible_for()`: (رونماییِ سراسری، ردیفِ اتصالِ این فروشگاه).

    ردیفِ اتصال *مستقل ازِ سوییچِ ادمین* برگردانده می‌شود تا پنلِ فروشگاه‌دار با یکِ کوئری هم
    وضعیتِ اتصال را بداند؛ تصمیمِ «نشان بدهم یا نه» با اولین عضوِ خروجی است.
    """
    admin_settings = await get_admin_settings(session)
    if not enabled(admin_settings):
        return False, None
    return True, await account_for_shop(session, shop_bot_id)


async def account_for_shop(session: AsyncSession, shop_bot_id: int) -> InstagramAccount | None:
    result = await session.execute(select(InstagramAccount).where(InstagramAccount.shop_bot_id == shop_bot_id))
    return result.scalar_one_or_none()


async def account_by_ig_id(session: AsyncSession, ig_account_id: str) -> InstagramAccount | None:
    """نگاشتِ «شناسهٔ اکانتِ رسیده از متا → فروشگاه» (قاعدهٔ P19: عددِ کاربر فقط داخلِ یک سرویس یکتا)."""
    result = await session.execute(select(InstagramAccount).where(InstagramAccount.ig_account_id == ig_account_id))
    return result.scalars().first()


# پ۶۳ · خواستهٔ مالکِ محصول: «پنلِ ویژهٔ مدیریتیِ اینستاگرام» در پنلِ خودِ فروشگاه. اولینِ فعلِ
# مدیریتیِ واقعیِ همین فهرست است: خاموش‌کردنِ *موقتِ* کانال بدونِ قطعِ اتصال و بدونِ دست‌کاریِ توکن.
MUTE_PRESETS: tuple[tuple[int, str], ...] = ((1, "۱ ساعت"), (6, "۶ ساعت"), (24, "۲۴ ساعت"), (72, "۳ روز"))
MUTE_HOURS = {hours for hours, _label in MUTE_PRESETS}


def _aware(moment: datetime.datetime) -> datetime.datetime:
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=datetime.timezone.utc)


def is_muted(account, moment: datetime.datetime | None = None) -> bool:
    """True یعنی کانال *فعلاً* خاموش است (اتصال سالم است و فقط پاسخ‌گویی متوقف شده)."""
    until = getattr(account, "muted_until", None) if account is not None else None
    if until is None:
        return False
    return _aware(until) > (moment or datetime.datetime.now(datetime.timezone.utc))


def mute_until(account, moment: datetime.datetime | None = None) -> datetime.datetime | None:
    """پایانِ خاموشیِ موقت (اگر هنوز نرسیده باشد)؛ None یعنی کانال روشن است."""
    return _aware(account.muted_until) if account is not None and is_muted(account, moment) else None


async def set_mute(session: AsyncSession, account, hours: int | None, *, actor_telegram_id: int) -> datetime.datetime | None:
    """`hours` از فهرستِ پیش‌فرض‌هاست (None ⇒ آزاد کردن). هیچ چیزِ دیگری لمس نمی‌شود."""
    if hours is not None and hours not in MUTE_HOURS:
        return None
    until = None if hours is None else datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=hours)
    account.muted_until = until
    await session.flush()
    label = "لغوِ خاموشیِ موقت" if until is None else f"خاموش تا {_aware(until).isoformat(timespec='minutes')}"
    await audit_log_service.log(
        session,
        AuditEventType.INSTAGRAM_TOGGLED,
        shop_bot_id=account.shop_bot_id,
        actor_telegram_id=actor_telegram_id,
        details=f"مدیریتِ اینستاگرام: {label}",
    )
    return until


async def activity_summary(session: AsyncSession, shop_bot_id: int, *, now: datetime.datetime | None = None) -> dict:
    """چند گفتگو و چند پیامِ مشتری در ۲۴ ساعت و ۷ روزِ اخیر، *فقط* از راهِ دیتابیسِ خودمان.

    صراحتِ لازم: کامنت‌ها جایی ذخیره نمی‌شوند (متا فقط رویداد می‌دهد و ما پاسخ را زیرِ کامنت
    می‌فرستیم)، پس این صفحه «فعالیتِ دایرکت» را می‌شمارد و برایِ کامنت فقط ردیف‌هایِ نگهبانِ
    محتوا در ممیزی هست. عددِ ساختگی ساخته نمی‌شود.
    """
    moment = now or datetime.datetime.now(datetime.timezone.utc)
    windows = {"24h": moment - datetime.timedelta(days=1), "7d": moment - datetime.timedelta(days=7)}
    out: dict[str, object] = {"since_24h": 0, "since_7d": 0, "chats_7d": 0, "at": moment}
    for label, since in windows.items():
        count = (
            await session.execute(
                select(func.count())
                .select_from(ConversationMessage)
                .join(Customer, ConversationMessage.customer_id == Customer.id)
                .where(
                    Customer.shop_bot_id == shop_bot_id,
                    Customer.platform == platform_service.INSTAGRAM,
                    ConversationMessage.role == "user",
                    ConversationMessage.created_at >= since,
                )
            )
        ).scalar_one()
        if label == "24h":
            out["since_24h"] = count
        else:
            out["since_7d"] = count
    out["chats_7d"] = (
        await session.execute(
            select(func.count(distinct(ConversationMessage.customer_id)))
            .select_from(ConversationMessage)
            .join(Customer, ConversationMessage.customer_id == Customer.id)
            .where(
                Customer.shop_bot_id == shop_bot_id,
                Customer.platform == platform_service.INSTAGRAM,
                ConversationMessage.role == "user",
                ConversationMessage.created_at >= windows["7d"],
            )
        )
    ).scalar_one()
    return out


# ------------------------------------------------------------------ پ۷۳ · رویدادِ کامنت و گزارشِ آن
# خواستهٔ مالک (۲۰۲۶-۱۱-۱۲): «چند کامنت آمد، به چندتا جواب دادیم، خرجش چقدر بود». تا پیش ازِ این
# کامنت هیچ‌جا ثبت نمی‌شد (پ۶۳ همان را صریح نوشت)، پس این سه تابع همان شکست را ببندند:
# `record_comment` در مسیرِ وب‌هوک، `mark_comment` در پایانِ هرِ تصمیم، و `comment_report` برایِ پنل.
COMMENT_RECEIVED = "received"
COMMENT_REPLIED = "replied"
COMMENT_SKIPPED = "skipped"
COMMENT_FAILED = "failed"
COMMENT_OUTCOMES: tuple[str, ...] = (COMMENT_RECEIVED, COMMENT_REPLIED, COMMENT_SKIPPED, COMMENT_FAILED)
COMMENT_TEXT_LIMIT = 1200  # متنِ کامنت برایِ «چه پرسیده شد» می‌ماند، نه بایگانیِ کامل
COMMENT_WINDOWS: tuple[tuple[str, int, str], ...] = (("24h", 1, "۲۴ ساعت"), ("7d", 7, "۷ روز"), ("30d", 30, "۳۰ روز"))
COMMENT_WINDOW_KEYS = frozenset(key for key, _days, _label in COMMENT_WINDOWS)


async def record_comment(session: AsyncSession, account, event) -> tuple[object | None, bool]:
    """ردیفِ رویدادِ کامنت ⇒ (ردیف، رسیدگی‌شده‌بودنِ پیشین). نوشتن هرگز نباید وب‌هوک را بشکند.

    `(None, False)` یعنی «ثبت نشد ولی کار را متوقف نکن» (خطایِ موقتِ دیتابیس ⇒ رفتارِ دیروز)؛
    `(ردیف، True)` یعنی اینِ کامنت پیش‌تر دیده و تمام شده ⇒ پاسخِ دوباره نساز (dedupِ پایدار،
    چون `claim_event` فقط درونِ یکِ پروسه یکتاست و دوباره‌ارسالِ متا بعد ازِ ری‌استارت ممکن است).
    """
    shop_bot_id = getattr(account, "shop_bot_id", None)
    comment_id = (event.comment_id or "")[:64]
    if not shop_bot_id or not comment_id:
        return None, False
    try:
        async with session.begin_nested():
            row = InstagramCommentEvent(
                shop_bot_id=shop_bot_id,
                comment_id=comment_id,
                media_id=(event.media_id or "")[:64] or None,
                username=(event.username or "")[:64] or None,
                text=(event.text or "")[:COMMENT_TEXT_LIMIT] or None,
                comment_created_at=event.created_at,
                outcome=COMMENT_RECEIVED,
            )
            session.add(row)
            await session.flush()
        return row, False
    except IntegrityError:
        existing = (
            await session.execute(
                select(InstagramCommentEvent).where(
                    InstagramCommentEvent.shop_bot_id == shop_bot_id,
                    InstagramCommentEvent.comment_id == comment_id,
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            return None, False
        return existing, existing.outcome != COMMENT_RECEIVED
    except Exception:  # noqa: BLE001 — ثبتِ مشاهده، بهایِ متوقف‌شدنِ پاسخگویی را ندارد
        logger.warning("پ۷۳: ردیفِ رویدادِ کامنت ثبت نشد؛ پاسخگویی ادامه می‌یابد.", exc_info=True)
        return None, False


def mark_comment(row, outcome: str, *, reason: str | None = None, tokens: int | None = None, cost: int | None = None) -> None:
    """نتیجهٔ همان رویداد رویِ خودِ ردیف (بدونِ پرس‌وجویِ تازه؛ commit با جریانِ موجود)."""
    if row is None or outcome not in COMMENT_OUTCOMES:
        return
    row.outcome = outcome
    if reason is not None:
        row.reason = reason[:32]
    if tokens is not None:
        row.ai_tokens = int(tokens)
    if cost is not None:
        row.cost_toman = int(cost)


async def comment_report(
    session: AsyncSession, shop_bot_id: int, *, window: str = "7d", page: int = 0,
    now: datetime.datetime | None = None, page_size: int = 10,
) -> dict:
    """سه پرس‌وجو برایِ یکِ صفحه: جمعِ پنجره، تفکیکِ دلیل‌ها، و آخرینِ کامنت‌هایِ همان پنجره."""
    days = next((d for key, d, _label in COMMENT_WINDOWS if key == window), 7)
    moment = now or datetime.datetime.now(datetime.timezone.utc)
    since = moment - datetime.timedelta(days=days)
    scope = (InstagramCommentEvent.shop_bot_id == shop_bot_id, InstagramCommentEvent.created_at >= since)
    total, replied, skipped, failed, tokens, cost = (
        await session.execute(
            select(
                func.count(),
                func.count().filter(InstagramCommentEvent.outcome == COMMENT_REPLIED),
                func.count().filter(InstagramCommentEvent.outcome == COMMENT_SKIPPED),
                func.count().filter(InstagramCommentEvent.outcome == COMMENT_FAILED),
                func.coalesce(func.sum(InstagramCommentEvent.ai_tokens), 0),
                func.coalesce(func.sum(InstagramCommentEvent.cost_toman), 0),
            ).where(*scope)
        )
    ).one()
    reasons = [
        ((reason or "unknown"), count)
        for reason, count in (
            await session.execute(
                select(InstagramCommentEvent.reason, func.count())
                .where(*scope, InstagramCommentEvent.outcome != COMMENT_REPLIED)
                .group_by(InstagramCommentEvent.reason)
                .order_by(func.count().desc(), InstagramCommentEvent.reason)
            )
        ).all()
    ]
    pages = max(1, (total + page_size - 1) // page_size)
    page = max(0, min(page, pages - 1))
    items = list(
        (
            await session.execute(
                select(InstagramCommentEvent)
                .where(*scope)
                .order_by(InstagramCommentEvent.created_at.desc(), InstagramCommentEvent.id.desc())
                .limit(page_size)
                .offset(page * page_size)
            )
        ).scalars().all()
    )
    return {
        "window": window, "days": days, "at": moment,
        "total": int(total), "replied": int(replied), "skipped": int(skipped), "failed": int(failed),
        "tokens": int(tokens), "cost": int(cost), "reasons": reasons,
        "items": items, "page": page, "pages": pages, "page_size": page_size,
    }


# ------------------------------------------------------------------ پ۷۷ · «به این حساب جواب نده»
# حلقهٔ چهارمِ اینستاگرام: فروشگاه‌دار می‌تواند یکِ نامِ کاربری را برایِ همیشه از پاسخ‌گوییِ
# کامنت‌ها خارج کند. در این فهرست فقط نامِ کاربری می‌ماند (نه متن، نه شناسهٔ کامنت) و درِ آن
# *پیش ازِ هر فراخوانیِ AI* بررسی می‌شود، پس حسابِ مسدود هیچ هزینه‌ای نمی‌سازد.
COMMENT_BLOCK_REASON = "sender_blocked"
COMMENT_BLOCK_MAX = 200  # سقفِ فهرست per-فروشگاه (دی‌ان‌اسِ بی‌نهایتِ ورودی، حافظه/کوئری می‌بلعد)
_USERNAME_STRIP_CHARS = " \t\n\r._-"


def normalize_comment_username(raw: str | None) -> str:
    """نامِ کاربری را برایِ مقایسه یکدست می‌کند: «@Ali.Rezaee_» ⇒ «ali.rezaee».

    اینستاگرام نامِ کاربری را case-insensitive می‌شمارد و «.» مرزِ خوانایی است، پس بدونِ این
    یکدست‌سازی «Ali» و «ali» دو حسابِ جدا به‌نظر می‌رسند. نتیجهٔ خالی یعنی «قابلِ ذخیره نیست».
    """
    name = (raw or "").strip().lstrip("@").strip().lower()
    name = name.strip(_USERNAME_STRIP_CHARS)
    if not name:
        return ""
    return name[:64]


async def list_comment_blocks(session: AsyncSession, shop_bot_id: int) -> list[InstagramCommentBlock]:
    return list(
        (
            await session.execute(
                select(InstagramCommentBlock)
                .where(InstagramCommentBlock.shop_bot_id == shop_bot_id)
                .order_by(InstagramCommentBlock.created_at.desc(), InstagramCommentBlock.id.desc())
            )
        ).scalars().all()
    )


async def comment_sender_is_blocked(session: AsyncSession, shop_bot_id: int, username: str | None) -> bool:
    name = normalize_comment_username(username)
    if not name:
        return False
    found = (
        await session.execute(
            select(InstagramCommentBlock.id).where(
                InstagramCommentBlock.shop_bot_id == shop_bot_id, InstagramCommentBlock.username == name
            ).limit(1)
        )
    ).first()
    return found is not None


async def block_comment_sender(
    session: AsyncSession, shop_bot_id: int, username: str | None, *, actor_telegram_id: int
) -> tuple[InstagramCommentBlock | None, str]:
    """⇒ (ردیف، "added"|"exists"|"invalid"|"full"). idempotent: دو بار زدنِ همان نام خطا نمی‌سازد."""
    name = normalize_comment_username(username)
    if not name:
        return None, "invalid"
    rows = await list_comment_blocks(session, shop_bot_id)
    existing = next((row for row in rows if row.username == name), None)
    if existing is not None:
        return existing, "exists"
    if len(rows) >= COMMENT_BLOCK_MAX:
        return None, "full"
    row = InstagramCommentBlock(shop_bot_id=shop_bot_id, username=name)
    session.add(row)
    await session.flush()
    await audit_log_service.log(
        session,
        AuditEventType.INSTAGRAM_TOGGLED,
        shop_bot_id=shop_bot_id,
        actor_telegram_id=actor_telegram_id,
        details=f"پ۷۷: «@{name}» به فهرستِ جواب‌نده‌ها افزوده شد",
    )
    return row, "added"


async def unblock_comment_sender(
    session: AsyncSession, shop_bot_id: int, block_id: int, *, actor_telegram_id: int
) -> InstagramCommentBlock | None:
    """برداشتنِ یکِ حساب از فهرست؛ مالکیتِ ردیف چک می‌شود (کال‌بکِ دستکاری‌شده به فروشگاهِ دیگر نمی‌رسد)."""
    row = (
        await session.execute(
            select(InstagramCommentBlock).where(
                InstagramCommentBlock.id == block_id, InstagramCommentBlock.shop_bot_id == shop_bot_id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    name = row.username
    await session.delete(row)
    await session.flush()
    await audit_log_service.log(
        session,
        AuditEventType.INSTAGRAM_TOGGLED,
        shop_bot_id=shop_bot_id,
        actor_telegram_id=actor_telegram_id,
        details=f"پ۷۷: «@{name}» از فهرستِ جواب‌نده‌ها برداشته شد",
    )
    return row


# ============================================================================= ۲ — آدرس‌ها و توکنِ وضعیت
def _safe_base(raw: str | None, fallback: str) -> str | None:
    """آدرسِ پایه فقط اگر https و رویِ میزبانِ رسمیِ متا باشد پذیرفته می‌شود (ورودیِ ادمین ⇒ کدِ امن)."""
    candidate = (raw or "").strip() or fallback
    if not candidate.lower().startswith("https://"):
        return None
    host = candidate[len("https://") :].split("/", 1)[0].split(":", 1)[0].lower()
    if host not in _TRUSTED_HOSTS:
        return None
    return candidate.rstrip("/")


def graph_base() -> str:
    return _safe_base(settings.instagram_api_base, DEFAULT_GRAPH_BASE) or DEFAULT_GRAPH_BASE


def graph_version() -> str:
    value = (settings.instagram_graph_version or "").strip()
    return value if re.fullmatch(r"v[0-9]{1,3}(\.[0-9])?", value) else INSTAGRAM_GRAPH_VERSION


def login_base() -> str:
    return _safe_base(settings.instagram_login_base, DEFAULT_LOGIN_BASE) or DEFAULT_LOGIN_BASE


def public_base_url() -> str | None:
    """آدرسِ عمومیِ HTTPSِ همین سرویس؛ بدونِ آن نه لینکِ اتصال ساخته می‌شود نه آدرسِ وب‌هوک.

    عمداً سخت‌گیرانه: https اجباری است و میزبانِ داخلی/لوکال رد می‌شود، چون داخلِ `redirect_uri`
    کدِ موقتِ احراز می‌نشیند — رویِ http یا هاستِ داخلی آن کد در دسترسِ هر کسی قرار می‌گیرد
    (همان نگرانیِ `_URL_FIELDS` در پنلِ ادمینِ کلیدِ AI).
    """
    raw = (settings.instagram_public_base_url or "").strip()
    if not raw.lower().startswith("https://"):
        return None
    host = raw[len("https://") :].split("/", 1)[0].split(":", 1)[0].lower()
    if not host or _INTERNAL_HOST_RE.match(host):
        return None
    return raw.rstrip("/")


def webhook_url() -> str | None:
    base = public_base_url()
    return f"{base}/webhook/instagram" if base else None


def redirect_uri() -> str | None:
    base = public_base_url()
    return f"{base}/webhook/instagram/oauth" if base else None


def build_oauth_url(app_id: str, redirect_uri: str, state: str) -> str:
    """لینکِ «Instagram Login for Business» — تنها مقداری که از پنل داخلِ آدرس می‌رود app_id است."""
    from urllib.parse import urlencode

    return (
        f"{login_base()}?{urlencode({'client_id': app_id.strip(), 'redirect_uri': redirect_uri, 'scope': OAUTH_SCOPES, 'response_type': 'code'})}"
    )


def make_state(shop_bot_id: int) -> str:
    """`state`ی که خودش امضا/رمزنگاری‌شده است (Fernetِ کلیدِ پلتفرم).

    چرا نه یکِ dict در حافظه: در حالتِ webhookِ چندپروسه‌ای (P45) کلیکِ فروشگاه‌دار و بازگشتِ
    متا می‌توانند به دو پروسهٔ مختلف برسند؛ هر چیزِ درِحافظه آن‌جا گم می‌شد و اتصال هرگز کامل
    نمی‌شد. همان کلیدِ `ENCRYPTION_KEY` که توکن‌ها را رمز می‌کند این‌جا امضا هم می‌کند ⇒ بدونِ
    وابستگیِ تازه و بدونِ ستونِ تازه.
    """
    payload = f"{int(shop_bot_id)}:{int(time.time())}:{secrets.token_hex(8)}"
    return encrypt_token(payload)


def parse_state(state: str | None) -> int | None:
    """شناسهٔ فروشگاهِ داخلِ `state`؛ None ⇒ امضا/ساختارِ نامعتبر یا قدیمی‌تر از ۲۰ دقیقه."""
    raw = (state or "").strip()
    if not raw:
        return None
    try:
        decoded = decrypt_token(raw)
    except Exception:  # noqa: BLE001 — هر رمزِ باز نشدنی = جعلی؛ هرگز استثنا به بیرون نمی‌رود
        return None
    parts = decoded.split(":")
    if len(parts) != 3 or not parts[0].isascii() or not parts[0].isdigit():
        return None
    try:
        issued = int(parts[1])
    except ValueError:
        return None
    if time.time() - issued > _STATE_TTL_SECONDS:
        return None
    return int(parts[0])


# ============================================================================= ۳ — امضایِ وب‌هوک و رویدادها
def verify_signature(body: bytes, header: str | None, app_secret: str) -> bool:
    """`X-Hub-Signature-256`: HMAC-SHA256 رویِ بدنهِ * خام* با پیشوندِ `sha256=`.

    مقایسه با `hmac.compare_digest` (زمان‌ثابت). رازِ تنظیم‌نشده ⇒ هر امضایی رد می‌شود؛ بدنهٔ
    خالی هم هیچ‌وقت «معتبر» حساب نمی‌شود، وگرنه یکِ درخواستِ بی‌بدنه با هدرِ درست رد می‌شد.
    """
    secret = (app_secret or "").strip()
    value = (header or "").strip()
    if not secret or not body or not value.lower().startswith("sha256="):
        return False
    provided = value.split("=", 1)[1].strip().lower()
    if not provided.isascii() or len(provided) != 64:
        return False
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, provided)


def _as_text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _as_time(value: object) -> datetime.datetime | None:
    """متا گاهی ثانیهٔ Unix می‌فرستد (صفِ اعشاری)، گاهی میلی‌ثانیه و گاهی رشته.

    هر مقدارِ بیرونِ بازه «None» می‌شود، نه استثنا: این تابع رویِ مسیرِ وب‌هوکِ متا اجرا می‌شود و
    یک `ValueError` یعنی پاسخِ ۵۰۰ و تلاشِ بی‌پایانِ متا برایِ یکِ عددِ عجیبِ داخلِ یکِ رویداد.
    """
    if value is None:
        return None
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return None
    if seconds <= 0:
        return None
    if seconds > 1e11:  # میلی‌ثانیه (متا در بعضی فیلدها همین را می‌فرستد)
        seconds /= 1000.0
    if seconds > 4102444800:  # سال ۲۱۰۰ — هر چیزِ بعدی دادهٔ خراب است
        return None
    try:
        return datetime.datetime.fromtimestamp(seconds, datetime.timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


def parse_event(payload: dict) -> list:
    """رویدادهایِ قابلِ پردازش: `DirectMessage` برایِ دایرکت، `None` برایِ آنچه P49-B است.

    عمداً رد می‌شوند (هیچ عضوی ساخته نمی‌شود): پیام‌هایِ `is_echo` (پاسخِ خودِ فروشگاه ⇒ اگر
    پردازش می‌شد، ربات به خودش جواب می‌داد و حلقه می‌افتاد)، پیام‌هایِ فقط-پیوست (متنی برای AI
    نیست)، رسیدِ خوانده‌شدن/ری‌اکشن. کامنت‌ها (`entry[].changes[]`) همان‌طور که خواسته شده
    `None` برمی‌گردانند تا شمارشِ «چه چیزی آمد» در P49-B گم نشود.
    """
    events: list = []
    if not isinstance(payload, dict):
        return events
    for entry in payload.get("entry") or []:
        if not isinstance(entry, dict):
            continue
        entry_id = _as_text(entry.get("id"))
        for change in entry.get("changes") or []:
            if not isinstance(change, dict):
                continue
            comment = _as_comment(change, entry_id)
            events.append(comment)  # None ⇒ رویدادِ ناشناخته (نه کامنت) تا شمارشِ «چه آمد» گم نشود
        for messaging in entry.get("messaging") or []:
            if not isinstance(messaging, dict):
                continue
            message = messaging.get("message")
            if not isinstance(message, dict) or message.get("is_echo"):
                continue
            text = _as_text(message.get("text"))
            if not text:
                continue
            sender = messaging.get("sender") if isinstance(messaging.get("sender"), dict) else {}
            recipient = messaging.get("recipient") if isinstance(messaging.get("recipient"), dict) else {}
            psid = _as_text(sender.get("id"))
            account_id = _as_text(recipient.get("id")) or entry_id
            if not psid or not _SAFE_ID_RE.fullmatch(psid) or not _SAFE_ID_RE.fullmatch(account_id):
                continue  # شناسهٔ ناشناخته ⇒ نه در آدرس می‌رود نه در ستونِ ۶۴نویسه‌ای
            events.append(
                DirectMessage(
                    shop_account_id=account_id,
                    sender_psid=psid,
                    text=text[:4000],
                    message_id=_as_text(message.get("id")) or None,
                    created_at=_as_time(message.get("created_time")) or _as_time(messaging.get("timestamp")),
                )
            )
    return events


def claim_event(key: str | None) -> bool:
    """«این رویداد را قبلاً پردازش کرده‌ام؟» — متا با هر ۲۰۰ ندادن دوباره می‌فرستد.

    بدونِ این، یکِ پیامِ تکراری یکِ پاسخِ AIِ دیگر و یکِ کسرِ کیف‌پولِ دیگر می‌ساخت (قاعدهٔ ۷:
    پول باید ایدبمپوتنت باشد). درِحافظه و کرانه‌دار است، چون پنجرهٔ دوباره‌ارسالِ متا کوتاه است.
    اولین فراخوانیِ هم‌زمان (پیش ازِ هر await در `_handle_inbound`) برنده است.
    """
    if not key:
        return True
    now = time.monotonic()
    if key in _seen_events:
        return False
    _seen_events[key] = now
    while len(_seen_events) > _MAX_SEEN_EVENTS:
        _seen_events.popitem(last=False)
    return True


def event_key(event: DirectMessage) -> str:
    return f"{event.shop_account_id}:{event.message_id or event.sender_psid}"


def dm_window_is_open(last_user_activity_at: datetime.datetime | None, now: datetime.datetime | None = None) -> bool:
    """قاعدهٔ ۲۴ ساعتِ متا: بیرون ازِ پنجره، ارسالِ عادی رد می‌شود (پاسخِ human_agent نه).

    None یعنی «نمی‌دانیم» ⇒ بسته حساب می‌شود: فرستادنِ پیامی که متا رد می‌کند بهتر از این است که
    فکر کنیم رفته، و فروشگاه‌دار در «آخرین خطا» دلیلِ فارسی می‌بیند.
    """
    if last_user_activity_at is None:
        return False
    moment = now or datetime.datetime.now(datetime.timezone.utc)
    if last_user_activity_at.tzinfo is None:
        last_user_activity_at = last_user_activity_at.replace(tzinfo=datetime.timezone.utc)
    return 0 <= (moment - last_user_activity_at).total_seconds() < DM_WINDOW_SECONDS


def customer_key(raw: str) -> int:
    """شناسهٔ عددیِ مشتری از `psid`ِ رشته‌ایِ اینستاگرام (ستونِ Customer.telegram_id عددی است).

    رشته‌هایِ تمام‌رقمی که در int64 جا می‌شوند عیناً می‌مانند؛ بقیه هشِ پایدارِ SHA-1 در ۱۵ رقمِ
    شش‌زدایی (۶۰ بیت ⇒ همیشه زیرِ ۲^۶۳−۱ و بدونِ برخوردِ معنادار)، تا تاریخچه/بلاک/سبدِ یکِ
    مشتری با هر رویدادِ تازه عوض نشود — همان دلیلی که P19 پلتفرم را به کلیدِ یکتای مشتری افزود.
    """
    text = (raw or "").strip()
    if text.isascii() and text.isdigit():
        value = int(text)
        if value <= _INT64_MAX:
            return value
    return int(hashlib.sha1(text.encode("utf-8")).hexdigest()[:15], 16)


# ============================================================================= ۴ — شبکه (Graph API)
async def _http() -> aiohttp.ClientSession:
    """جلسه‌یِ مشترکِ HTTP (همان الگویِ bale_service؛ سوکتِ TCP/DNS در هر درخواست دوباره ساخته نمی‌شود)."""
    global _http_session, _http_loop
    loop = asyncio.get_running_loop()
    if _http_session is None or _http_session.closed or _http_loop is not loop:
        _http_session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=API_TIMEOUT_SECONDS),
            connector=aiohttp.TCPConnector(limit=10, ttl_dns_cache=300),
        )
        _http_loop = loop
    return _http_session


async def _drop_http_session() -> None:
    global _http_session, _http_loop
    if _http_session is not None and not _http_session.closed:
        try:
            await _http_session.close()
        except Exception:  # noqa: BLE001 — پاکیزگیِ مسیرِ خطا نباید خودِ خطا را بپوشاند
            pass
    _http_session = None
    _http_loop = None


async def close_http_session() -> None:
    await _drop_http_session()


def _mask(value: object) -> str:
    """هر متنِ خطا (آدرسِ درخواست، پاسخِ JSON) پیش ازِ رفتن در last_error/لاگ از رازها پاک می‌شود."""
    return payment_event_service.sanitize(value)


def _tail(psid: str) -> str:
    return f"…{psid[-4:]}" if len(psid) > 4 else "…"


async def _post_json(url: str, data: dict, *, label: str) -> dict:
    http = await _http()
    try:
        async with http.post(url, data=data) as resp:
            status = resp.status
            body = await resp.text()
    except Exception as exc:  # noqa: BLE001 — شبکه هیچ‌وقت نباید به پنل/وب‌هوک برسد
        await _drop_http_session()
        raise InstagramError(f"ارتباط با سرورِ رسمیِ متا برقرار نشد ({label}): {_mask(str(exc))}") from exc
    return _decode(body, status, label)


async def _get_json(url: str, params: dict, *, label: str) -> dict:
    http = await _http()
    try:
        async with http.get(url, params=params) as resp:
            status = resp.status
            body = await resp.text()
    except Exception as exc:  # noqa: BLE001
        await _drop_http_session()
        raise InstagramError(f"ارتباط با سرورِ رسمیِ متا برقرار نشد ({label}): {_mask(str(exc))}") from exc
    return _decode(body, status, label)


def _decode(body: str, status: int, label: str) -> dict:
    """پاسخِ متا ⇒ dict. خطاها به InstagramErrorِ فارسی و ماسک‌شده تبدیل می‌شوند (نه استثنایِ خام)."""
    try:
        data = json.loads(body) if body else {}
    except ValueError:
        raise InstagramError(f"پاسخِ متا قابلِ خواندن نبود ({label} · HTTP {status})") from None
    if not isinstance(data, dict):
        raise InstagramError(f"پاسخِ متا شکلِ انتظار را نداشت ({label} · HTTP {status})")
    if status != 200 or data.get("error"):
        error = data.get("error")
        detail = _mask(error.get("message") if isinstance(error, dict) else error)[:180]
        raise InstagramError(f"متا این درخواست را نپذیرفت ({label} · HTTP {status}): {detail}")
    return data


async def exchange_code(app_id: str, app_secret: str, code: str, redirect: str) -> dict:
    """کدِ احراز ⇒ توکنِ اکانت. خروجی: {access_token, ig_account_id, username} یا InstagramError."""
    token_url = f"{graph_base()}/{graph_version()}/oauth/access_token"
    data = await _post_json(
        token_url,
        {
            "client_id": app_id,
            "client_secret": app_secret,
            "grant_type": "authorization_code",
            "redirect_uri": redirect,
            "code": code,
        },
        label="تبدیلِ کد به توکن",
    )
    access_token = _as_text(data.get("access_token"))
    if not access_token:
        raise InstagramError("متا توکنِ دسترسی برنگرداند؛ اتصال کامل نشده است.")
    info = await fetch_account_info(access_token)
    return {"access_token": access_token, **info}


async def fetch_account_info(access_token: str) -> dict:
    """`user_id` (همان شناسهٔ روتینگِ رویدادها) و نامِ کاربریِ اکانت."""
    data = await _get_json(
        f"{graph_base()}/{graph_version()}/me",
        {"fields": "user_id,username", "access_token": access_token},
        label="خواندنِ مشخصاتِ اکانت",
    )
    ig_account_id = _as_text(data.get("user_id"))
    if not ig_account_id or not _SAFE_ID_RE.fullmatch(ig_account_id):
        raise InstagramError("شناسهٔ اکانتِ اینستاگرام از متا معتبر نبود؛ دوباره اتصال را امتحان کن.")
    return {"ig_account_id": ig_account_id, "username": _as_text(data.get("username"))[:64]}


COMMENT_PUBLIC_LIMIT = 280  # کامنتِ عمومی کوتاه می‌ماند؛ جزئیات به دایرکت می‌رود
COMMENT_REPLY_DAYS = 7  # قاعدهٔ متا: پاسخِ خصوصی فقط تا ۷ روزِ بعد ازِ کامنت، و فقط یکِ پیام
_COMMENT_FIELDS = ("comments", "live_comments")


def _as_comment(change: dict, entry_id: str) -> CommentEvent | None:
    """تبدیلِ یکِ `changes[]` به CommentEvent؛ هر چیزِ دیگر (ویرایشِ پست و…) ⇒ None."""
    if _as_text(change.get("field")) not in _COMMENT_FIELDS:
        return None
    value = change.get("value")
    if not isinstance(value, dict):
        return None
    comment_id = _as_text(value.get("id"))
    text = _as_text(value.get("text"))
    media = value.get("media") if isinstance(value.get("media"), dict) else {}
    media_id = _as_text(media.get("id"))
    from_user = value.get("from") if isinstance(value.get("from"), dict) else {}
    username = _as_text(from_user.get("username")) or _as_text(value.get("username"))
    account_id = _as_text(value.get("ig_id")) or entry_id
    if not comment_id or not text or not media_id:
        return None
    if not (_STRICT_ID_RE.fullmatch(comment_id) and _STRICT_ID_RE.fullmatch(media_id) and _STRICT_ID_RE.fullmatch(account_id)):
        return None  # شناسهٔ ناشناخته نه به آدرسِ Graph می‌رود نه به ستونِ ۶۴نویسه‌ای
    return CommentEvent(
        comment_id=comment_id,
        media_id=media_id,
        ig_account_id=account_id,
        text=text[:2000],
        username=username[:64],
        created_at=_as_time(value.get("timestamp")),
    )


def comment_reply_is_open(created_at: datetime.datetime | None, now: datetime.datetime | None = None) -> bool:
    """پاسخِ خصوصی فقط تا ۷ روزِ بعد ازِ کامنت مجاز است (بعد ازِ آن متا رد می‌کند)."""
    if created_at is None:
        return True  # بی‌زمان ⇒ تصمیم با خودِ متا؛ پیام را از دست نمی‌دهیم
    moment = now or datetime.datetime.now(datetime.timezone.utc)
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=datetime.timezone.utc)
    return (moment - created_at) <= datetime.timedelta(days=COMMENT_REPLY_DAYS)


async def reply_to_comment(session: AsyncSession, account: InstagramAccount | None, event: CommentEvent, text: str) -> bool:
    """جوابِ *عمومی* زیرِ همان کامنت: `POST /{ig}/media/{media_id}/comments`."""
    if account is None or not (account.access_token or ""):
        return False
    if not _STRICT_ID_RE.fullmatch(account.ig_account_id or "") or not _STRICT_ID_RE.fullmatch(event.media_id):
        return False
    body = text_limits.clip(text, text_limits.INSTAGRAM_DM_LIMIT)
    if not body:
        return False
    url = f"{graph_base()}/{graph_version()}/{account.ig_account_id}/media/{event.media_id}/comments"
    try:
        await _post_json(url, {"access_token": account.access_token, "message": body}, label="پاسخِ عمومی به کامنت")
    except InstagramError as exc:
        await remember_error(session, account, str(exc))
        logger.warning("پاسخِ عمومی به کامنت برایِ فروشگاه %s ناموفق بود.", account.shop_bot_id)
        return False
    return True


async def send_private_reply(session: AsyncSession, account: InstagramAccount | None, event: CommentEvent, text: str) -> bool:
    """«پاسخِ خصوصی» به کامنت‌کننده: `POST /{ig}/messages` با `recipient={"comment_id": …}`.

    متا به‌ازایِ هرِ کامنت فقط **یکِ پیام** اجازه می‌دهد؛ این مسیر ادامهٔ گفتگو نیست، فقط درِ ورود به
    دایرکت است (ادامه وقتی مجاز است که خودِ کاربر جواب بدهد ⇒ همان مسیرِ DM).
    """
    if account is None or not (account.access_token or ""):
        return False
    if not _STRICT_ID_RE.fullmatch(account.ig_account_id or "") or not _STRICT_ID_RE.fullmatch(event.comment_id):
        return False
    if not comment_reply_is_open(event.created_at):
        await remember_error(session, account, f"{fa_number(COMMENT_REPLY_DAYS)} روز از کامنت گذشته است؛ متا پاسخِ خصوصی را قبول نمی‌کند.")
        return False
    body = text_limits.clip(text, text_limits.INSTAGRAM_DM_LIMIT)
    if not body:
        return False
    url = f"{graph_base()}/{graph_version()}/{account.ig_account_id}/messages"
    payload = {
        "access_token": account.access_token,
        "recipient": json.dumps({"comment_id": event.comment_id}),
        "message": json.dumps({"text": body}),
        "messaging_type": "RESPONSE",
        "tag": "PRIVATE_TEXT",
    }
    try:
        await _post_json(url, payload, label="پاسخِ خصوصی به کامنت")
    except InstagramError as exc:
        await remember_error(session, account, str(exc))
        logger.warning("پاسخِ خصوصی اینستاگرام برایِ فروشگاه %s ناموفق بود.", account.shop_bot_id)
        return False
    return True


async def send_message(
    session: AsyncSession,
    account: InstagramAccount | None,
    psid: str,
    text: str,
    *,
    reply_type: str = "response",
    window_opened_at: datetime.datetime | None = None,
) -> bool:
    """یکِ دایرکت از طریقِ `POST /{ig_account_id}/messages`. True ⇒ متا پذیرفت.

    توکن در بدنهِ form-data می‌رود (نه URL)؛ نه توکن، نه psid کامل، نه متنِ پیام لاگ می‌شود.
    """
    if account is None or not (account.access_token or ""):
        return False
    if not _SAFE_ID_RE.fullmatch(account.ig_account_id or "") or not _SAFE_ID_RE.fullmatch(psid or ""):
        return False
    if window_opened_at is not None and not dm_window_is_open(window_opened_at):
        await remember_error(session, account, "۲۴ ساعت از آخرین پیامِ مشتری گذشته است؛ متا پاسخِ عادی را قبول نمی‌کند.")
        return False
    body = text_limits.clip(text, text_limits.INSTAGRAM_DM_LIMIT)
    if not body:
        return False
    payload: dict = {
        "access_token": account.access_token,
        "recipient": json.dumps({"id": psid}),
        "messaging_type": "RESPONSE",
        "message": json.dumps({"text": body}),
    }
    if reply_type == "human_agent":
        # برچسبِ «اپراتورِ انسانی» تا متا پیام را داخلِ پنجرهٔ ۲۴ساعته هم بی‌اعتبار نداند.
        payload["tag"] = "HUMAN_AGENT"
        payload["metadata"] = json.dumps({"response_type": "human_agent"})
    url = f"{graph_base()}/{graph_version()}/{account.ig_account_id}/messages"
    try:
        await _post_json(url, payload, label="ارسالِ دایرکت")
    except InstagramError as exc:
        await remember_error(session, account, str(exc))
        logger.warning("ارسالِ دایرکتِ اینستاگرام برایِ فروشگاه %s به %s ناموفق بود.", account.shop_bot_id, _tail(psid))
        return False
    await remember_error(session, account, None)
    return True


async def mark_seen(account: InstagramAccount, message_id: str | None) -> None:
    """علامتِ «دیده شد» — کارِ جانبیِ بی‌اهمیت؛ هیچ‌وقت خطا نمی‌دهد و هزینه‌ای ندارد."""
    if account is None or not message_id or not (account.access_token or ""):
        return
    if not _SAFE_ID_RE.fullmatch(account.ig_account_id or ""):
        return
    url = f"{graph_base()}/{graph_version()}/{account.ig_account_id}/messages"
    payload = {
        "access_token": account.access_token,
        "sender_action": "mark_seen",
    }
    try:
        await _post_json(url, payload, label="علامتِ دیده‌شدن")
    except InstagramError:
        logger.debug("علامتِ دیده‌شدنِ اینستاگرام نرفت (بی‌اهمیت).")


async def remember_error(session: AsyncSession, account: InstagramAccount | None, message: str | None) -> None:
    """`last_error` همیشه فارسی و ماسک‌شده است؛ None ⇒ پاک‌کردنِ خطایِ قبلی (موفقیتِ تازه)."""
    if account is None or session is None:
        return  # «یادآوریِ» خطا بهترین‌تلاش است؛ بی‌سشن نباید خودِ مسیرِ ارسال را بشکند
    account.last_error = text_limits.clip(message, 500) if message else None
    await session.flush()


# ============================================================================= ۵ — اتصالِ اکانت (از پنلِ فروشگاه‌دار)
async def connect_with_code(session: AsyncSession, shop_bot: ShopBot, code: str) -> InstagramAccount:
    """کدِ بازگشتی از متا ⇒ ردیفِ اتصالِ همین فروشگاه (یا InstagramErrorِ فارسی، بدونِ ردیفِ نیمه‌کاره)."""
    admin_settings = await get_admin_settings(session)
    app_id = (admin_settings.instagram_app_id or "").strip()
    app_secret = (admin_settings.instagram_app_secret or "").strip()
    redirect = redirect_uri()
    if not app_id or not app_secret or redirect is None:
        raise InstagramError("پلتفرم هنوز کامل تنظیم نشده؛ از ادمین بخواه «🟣 اینستاگرام» را در تنظیمات پر کند.")
    result = await exchange_code(app_id, app_secret, code, redirect)
    account = await account_for_shop(session, shop_bot.id)
    if account is None:
        account = InstagramAccount(shop_bot_id=shop_bot.id)
        session.add(account)
    account.ig_account_id = result["ig_account_id"]
    account.ig_username = result.get("username") or None
    account.access_token = result["access_token"]
    account.is_active = True
    account.connected_at = datetime.datetime.now(datetime.timezone.utc)
    account.last_error = None
    await session.flush()
    await audit_log_service.log(
        session,
        AuditEventType.INSTAGRAM_CONNECTED,
        shop_bot_id=shop_bot.id,
        details=f"@{account.ig_username or '—'}",
    )
    await session.commit()
    return account


async def unbind(session: AsyncSession, account: InstagramAccount) -> None:
    """حذفِ ردیفِ اتصال (توکن از دیتابیس بیرون می‌رود). تاریخچهٔ گفتگویِ مشتری عمداً دست‌نخورده می‌ماند."""
    shop_bot_id = account.shop_bot_id
    await session.delete(account)
    await session.flush()
    await audit_log_service.log(session, AuditEventType.INSTAGRAM_UNBOUND, shop_bot_id=shop_bot_id)
    await session.commit()


# ============================================================================= ۶ — پرداخت (همان منطقِ موجود)
class InstagramMessenger:
    """آداپتورِ باریک: هر کدی که امروز `send_message(chat_id, text, reply_markup=…)` صدا می‌زند،
    رویِ دایرکت می‌نشیند. دایرکتِ اینستاگرام دکمهٔ inline ندارد ⇒ لینکِ دکمه به‌صورتِ متنِ
    قابلِ کپی اضافه می‌شود و هیچ مبلغ/صورتحسابِ تازه‌ای ساخته نمی‌شود."""

    def __init__(self, session: AsyncSession, account: InstagramAccount, psid: str) -> None:
        self.session = session
        self.account = account
        self.psid = psid
        self.sent = 0

    async def send_message(self, chat_id=None, text="", reply_markup=None, **kwargs) -> None:
        link = _first_url(reply_markup)
        body = text if not link else f"{text}\n🔗 لینکِ پرداخت (همین آدرس را در مرورگر باز کن): {link}"
        if await send_message(self.session, self.account, self.psid, body, window_opened_at=datetime.datetime.now(datetime.timezone.utc)):
            self.sent += 1


def _first_url(reply_markup) -> str | None:
    for row in getattr(reply_markup, "inline_keyboard", None) or []:
        for button in row:
            url = getattr(button, "url", None)
            if url:
                return str(url)
    return None


async def maybe_offer_payment(session: AsyncSession, account: InstagramAccount, shop_bot: ShopBot, customer, psid: str) -> bool:
    """اگر سفارشی در وضعیتِ «منتظرِ پرداخت» باشد، همان پیشنهادِ پرداختِ موجود را در دایرکت می‌فرستد.

    مسیرِ پرداخت عمداً *همه‌اش* وام‌گرفته شده است: `customer.py::_maybe_offer_online_payment`
    با همان `bale_credentials_service.shop_status`، همان `bale_service.create_invoice_link` و همان
    payloadِ `order-{id}-{hex}`؛ برایِ کارت‌به‌کارت هم همان `order_payment_service.start_payment`
    (ایدبمپوتنت: پرداختِ فعالِ همین روش را دوباره نمی‌سازد) و همان
    `shop_bot.texts.card_payment_instructions`. هیچ عدد/لینک/صورتحسابِ تازه‌ای در این فایل نیست.
    یکِ سقفِ ۳۰دقیقه‌ای به‌ازایِ هر سفارش گذاشته شده تا مشتری هر پیام با یادآوریِ پرداخت باز نشود.
    """
    order = await _awaiting_payment_order(session, shop_bot.id, customer.id)
    if order is None:
        return False
    moment = time.monotonic()
    if moment - _payment_offered_at.get(order.id, 0.0) < _PAYMENT_OFFER_COOLDOWN_SECONDS:
        return False
    _payment_offered_at[order.id] = moment
    while len(_payment_offered_at) > _MAX_PAYMENT_OFFERS:
        _payment_offered_at.pop(next(iter(_payment_offered_at)))
    messenger = InstagramMessenger(session, account, psid)
    from app.bots.shop_bot.handlers import customer as customer_handlers  # import محلی: چرخه‌یِ import نشود

    try:
        await customer_handlers._maybe_offer_online_payment(messenger, session, shop_bot, order, customer.telegram_id)
    except bale_service.BaleError:
        logger.info("پیشنهادِ بله‌پی در اینستاگرام برایِ سفارش %s ناموفق بود (مشتری کارت‌به‌کارت را می‌بیند).", order.id)
    if messenger.sent:
        return True
    return await _offer_card_payment(session, account, shop_bot, order, psid, messenger)


async def _awaiting_payment_order(session: AsyncSession, shop_bot_id: int, customer_id: int) -> OrderConsultation | None:
    result = await session.execute(
        select(OrderConsultation)
        .where(
            OrderConsultation.shop_bot_id == shop_bot_id,
            OrderConsultation.customer_id == customer_id,
            OrderConsultation.status == OrderStatus.AWAITING_PAYMENT,
        )
        .order_by(OrderConsultation.id.desc())
        .limit(1)
    )
    return result.scalars().first()


async def _offer_card_payment(session, account, shop_bot, order, psid, messenger) -> bool:
    """کارت‌به‌کارت: دقیقاً همان دو فراخوانیِ `payments.py::pm_card` (ردیفِ پرداخت + متنِ کارت)."""
    settings_row = await payment_settings_service.get(session, shop_bot.id)
    methods = await bale_credentials_service.methods(session, shop_bot, settings_row, include_manual=False)
    if payment_settings_service.METHOD_CARD not in methods:
        return False
    _payment, expires = await order_payment_service.start_payment(
        session, [order], payment_settings_service.METHOD_CARD, settings_row
    )
    await session.commit()
    text = shop_texts.card_payment_instructions(
        payment_settings_service.get_card_number(settings_row),
        settings_row.card_holder_name,
        settings_row.bank_name,
        order_transition_service.group_total_toman([order]),
        shop_texts.order_code([order]),
        format_jalali_datetime(to_tehran(expires)),
    )
    await messenger.send_message(text=text)
    return bool(messenger.sent)


# ============================================================================= ۷ — مسیرِ ورودی (مغزِ AI + پول)
async def handle_comment(session: AsyncSession, main_bot, event: CommentEvent) -> None:
    """یکِ کامنتِ عمومی ⇒ جوابِ کوتاه از همان مغزِ AI، و در صورتِ روشن‌بودن «پاسخِ خصوصی».

    تفاوتِ عمدی با دایرکت: کامنت‌کننده هنوز مشتریِ فروشگاه نیست و گفتگویی در تاریخچه ندارد، پس
    تاریخچه‌ای خوانده/نوشته نمی‌شود و هویتِ Customer برایش ساخته نمی‌شود (ساختنِ مشتری از رویِ یکِ
    کامنت، CRMِ فروشگاه را با آدم‌هایِ غریبه پر می‌کرد). هزینهٔ AI مثلِ بقیهٔ کانال‌ها از کیف‌پولِ
    صاحبِ فروشگاه کم می‌شود. هیچ استثنایی به وب‌هوک بیرون نمی‌رود.


    پ۷۳: هرِ کامنتِ *دیده‌شده* یکِ ردیفِ فقط‌مشاهده‌ای در `instagram_comment_events` می‌گیرد (با نتیجه، دلیلِ جواب‌نرفتن و همان توکن/مبلغِ کسرشده) — بدونِ مشتری، بدونِ گفتگو و بدونِ هیچ اثری رویِ تصمیمِ پول؛ اگر نوشتن خطا داد، پاسخگویی مثلِ دیروز ادامه می‌یابد.
    """
    try:
        await _handle_comment(session, main_bot, event)
    except Exception:  # noqa: BLE001 — وب‌هوکِ متا باید ۲۰۰ بگیرد، وگرنه تا ابد دوباره می‌فرستد
        logger.exception("پردازشِ کامنتِ اینستاگرام ناموفق بود.")
        await session.rollback()


async def _handle_comment(session: AsyncSession, main_bot, event: CommentEvent) -> None:
    key = f"ig-comment:{event.comment_id}"
    if not claim_event(key):
        return
    admin_settings = await cached_admin_settings(session)
    if not enabled(admin_settings):
        return
    account = await account_by_ig_id(session, event.ig_account_id)
    if account is None:
        return
    # پ۷۳: ردیفِ رویداد پیش ازِ درهایِ حسابی نوشته می‌شود تا «چند کامنت آمد و چرا جواب نرفت» شمارش
    # بماند؛ بی‌ثباتیِ نوشتن هیچ‌وقت پاسخگویی را متوقف نمی‌کند.
    row, handled = await record_comment(session, account, event)
    if handled:
        return  # اینِ کامنت پیش‌تر دیده و تمام شده (دوباره‌ارسالِ متا بعد ازِ ری‌استارت)
    if not account.is_active:
        mark_comment(row, COMMENT_SKIPPED, reason="account_off")
        await session.commit()
        return
    if not account.auto_reply_comments:
        mark_comment(row, COMMENT_SKIPPED, reason="comments_off")
        await session.commit()
        return
    if is_muted(account):
        mark_comment(row, COMMENT_SKIPPED, reason="muted")
        await session.commit()
        return
    # پ۷۷: فهرستِ «به این حساب جواب نده» — پیش ازِ هر پرس‌وجویِ حساب/صاحب و هر خرجِ AI.
    if await comment_sender_is_blocked(session, account.shop_bot_id, event.username):
        mark_comment(row, COMMENT_SKIPPED, reason=COMMENT_BLOCK_REASON)
        await session.commit()
        return
    shop_bot = await shop_bot_service.get_by_id(session, account.shop_bot_id)
    if shop_bot is None or not shop_bot.is_active or admin_settings.maintenance_mode:
        mark_comment(row, COMMENT_SKIPPED, reason="shop_inactive")
        await session.commit()
        return
    owner = await shop_owner_service.get_by_id(session, shop_bot.shop_owner_id)
    if owner is None:
        mark_comment(row, COMMENT_SKIPPED, reason="no_owner")
        await session.commit()
        return

    matched_rule = await moderation_service.check_text(session, event.text, shop_bot_id=shop_bot.id)
    if matched_rule is not None:
        action = matched_rule.action.value if hasattr(matched_rule.action, "value") else str(matched_rule.action)
        await audit_log_service.log(
            session,
            AuditEventType.MODERATION_MATCH,
            shop_bot_id=shop_bot.id,
            details=f"الگو: {matched_rule.pattern} | اکشن: {action} | کانال: اینستاگرام (کامنت)",
        )
        await session.commit()
        if action == "block":
            mark_comment(row, COMMENT_SKIPPED, reason="moderation_block")
            await session.commit()
            return  # جوابِ عمومیِ زیرِ کامنتِ تخلفی، برندِ فروشگاه را هم آلوده می‌کند

    if not admin_settings.ai_api_key:
        mark_comment(row, COMMENT_SKIPPED, reason="no_ai_key")
        await session.commit()
        return
    access_state = await order_access_service.evaluate(session, owner, admin_settings)
    if not order_access_service.chat_continues(access_state):
        mark_comment(row, COMMENT_SKIPPED, reason="no_access")
        await session.commit()
        return

    products = await product_service.get_active_by_shop_bot(session, shop_bot.id)
    knowledge_limit = shop_prefs_service.resolve(shop_prefs_service.KNOWLEDGE_ITEMS, shop_bot, admin_settings)
    knowledge = await channel_knowledge_service.get_recent_knowledge(session, shop_bot.id, knowledge_limit)
    learned_answers = await knowledge_service.get_active_for_prompt(session, shop_bot.id)
    system_prompt = ai_context.build_system_prompt(
        shop_bot,
        products,
        knowledge,
        prompt_defaults.resolve_global_prompt(admin_settings, shop_bot.tenant_mode),
        learned_answers=learned_answers,
        gap_detection=False,  # «سوالِ بی‌جواب» برایِ گفتگویِ خصوصی است، نه کامنتِ عمومی
        bot_tools=[],
        channel_directive=instruction_directive(account, admin_settings, shop_bot),
    )
    ai = await ai_pool_service.build_ai_service(session, admin_settings, "chat")
    if ai is None:
        mark_comment(row, COMMENT_SKIPPED, reason="no_ai_pool")
        await session.commit()
        return
    try:
        await session.commit()  # قاعدهٔ ۷: آزادکردنِ اتصال پیش ازِ انتظارِ شبکه
        ai_result = await ai.get_reply(system_prompt, [], event.text)
    except ai_service.AiServiceError:
        logger.warning("پاسخِ AI به کامنتِ اینستاگرام برایِ فروشگاه %s ناموفق بود.", shop_bot.id)
        await bot_error_service.log_error(session, shop_bot.id)
        mark_comment(row, COMMENT_FAILED, reason="ai_error")
        await session.commit()
        return

    reply = text_limits.strip_markdown(knowledge_service.strip_gap_marker(ai_result.text)[0])
    public = text_limits.clip(reply, COMMENT_PUBLIC_LIMIT)
    if not public:
        mark_comment(row, COMMENT_SKIPPED, reason="empty_reply")
        await session.commit()
        return
    if not await reply_to_comment(session, account, event, public):
        mark_comment(row, COMMENT_FAILED, reason="send_failed")
        await session.commit()
        return  # پاسخِ نرسیده هزینهٔ صاحبِ فروشگاه نمی‌شود

    if account.private_reply_enabled:
        await send_private_reply(session, account, event, private_reply_text(reply, shop_bot))
    cost = wallet_service.estimate_chat_cost(admin_settings, ai_result.total_tokens)
    mark_comment(row, COMMENT_REPLIED, tokens=ai_result.total_tokens, cost=cost)
    await chat_billing_service.deduct_and_notify(
        session, owner, admin_settings, cost, WalletTransactionReason.CHAT_MESSAGE, main_bot,
        ai_total_tokens=ai_result.total_tokens,
    )
    await session.commit()


def instruction_directive(account, admin_settings, shop_bot) -> str | None:
    """پ۶۰ · خواستهٔ مالکِ محصول: متنِ هوشمندسازیِ اینستاگرامِ *خودِ فروشگاه*.

    دو لایه دارد: متنِ سراسریِ ادمین (اگر پر باشد) و متنِ خودِ فروشگاه؛ و در آخر یکِ
    قاعدهٔ مود. در مودِ مشاوره‌ای فروش ممنوع است (نه قیمت، نه لینکِ پرداخت، نه دعوت به سبد)
    ولی پاسخِ سؤالات و پاسخِ کامنت آزاد است. هیچ‌کدام جایِ متنِ اصلیِ فروشگاه را نمی‌گیرد.
    """
    parts = []
    platform = (getattr(admin_settings, "instagram_platform_instructions", None) or "").strip()
    if platform:
        parts.append("دستورِ سراسریِ پلتفرم برایِ اینستاگرام:\n" + platform)
    own = (getattr(account, "instructions", None) or "").strip() if account is not None else ""
    if own:
        parts.append("دستورِ خودِ این فروشگاه برایِ اینستاگرام:\n" + own)
    mode_value = shop_bot.tenant_mode.value if hasattr(shop_bot.tenant_mode, "value") else shop_bot.tenant_mode
    if mode_value == "consultation":
        parts.append(
            "قاعدهٔ کانالِ اینستاگرام (حالتِ مشاوره): فقط به سؤالات جواب بده و مشاوره بده. "
            "هیچ قیمتی اعلام نکن، هیچ سبد/پرداخت/لینکِ خرید نساز، و هیچ عددی را از خودت "
            "نساز؛ اگر مشتری قیمت یا خرید خواست، بگو از راهِ ارتباطِ رسمیِ همان فروشگاه "
            "پرسش کند."
        )
    else:
        parts.append(
            "قاعدهٔ کانالِ اینستاگرام (حالتِ فروش): می‌توانی محصول و قیمت را از فهرستِ "
            "موجود بگویی، ولی در کامنتِ عمومی هیچ لینکِ پرداختی نساز و برایِ گرفتنِ "
            "شمارهٔ تماس یا آدرس، مشتری را به دایرکت دعوت کن."
        )
    return "\n\n".join(parts) if parts else None


def private_reply_text(answer: str, shop_bot) -> str:
    """متنِ دایرکتِ خصوصی: همان جواب + دعوتِ ادامهٔ گفتگو (فقط یکِ پیام مجاز است، پس کامل فرستاده می‌شود)."""
    body = text_limits.clip(answer, text_limits.INSTAGRAM_DM_LIMIT - 120)
    return f"{body}\n\nهر سؤالِ دیگری داشتی همین‌جا در دایرکت بنویس تا پاسخِ کامل‌تری بگیری."


async def handle_inbound(session: AsyncSession, main_bot, event: DirectMessage) -> None:
    """یکِ دایرکتِ ورودی ⇒ همان لوله‌یِ `customer.py` (دسترسی، نگهبانِ محتوا، AI، تاریخچه، کسر).

    هیچ‌چیز اینجا دوباره اختراع نمی‌شود و هیچ استثنایی به وب‌هوک بیرون نمی‌رود: متا اگر پاسخِ
    HTTP موفق نبیند رویداد را دوباره می‌فرستد و دوباره‌ارسال با `claim_event` بی‌اثر می‌ماند.
    """
    try:
        await _handle_inbound(session, main_bot, event)
    except Exception:  # noqa: BLE001 — مسیرِ کانالِ تازه نباید وب‌هوک را بشکند
        logger.exception("پردازشِ رویدادِ اینستاگرام ناموفق بود.")
        await _remember_failure(session, event)


async def _remember_failure(session: AsyncSession, event: DirectMessage) -> None:
    account = await account_by_ig_id(session, event.shop_account_id)
    await remember_error(session, account, "پردازشِ این پیام در سرویسِ ما ناموفق بود؛ جزئیات در لاگِ سرور است.")
    await session.commit()


async def _handle_inbound(session: AsyncSession, main_bot, event: DirectMessage) -> None:
    # اولین کار (پیش ازِ هر await): برنده/بازندهٔ دوباره‌ارسالِ متا مشخص شود تا هیچ پیامی دو بار
    # هزینه نسازد، حتی اگر دو نسخه از یک رویداد هم‌زمان به این پروسه برسند.
    if not claim_event(event_key(event)):
        return
    admin_settings = await cached_admin_settings(session)
    if not enabled(admin_settings):
        return  # کانال خاموش ⇒ بی‌صدا رد (پیامِ «خاموش است» به مشتری معنایی ندارد)
    account = await account_by_ig_id(session, event.shop_account_id)
    if account is None or not account.is_active or is_muted(account):
        return
    shop_bot = await shop_bot_service.get_by_id(session, account.shop_bot_id)
    if shop_bot is None or not shop_bot.is_active:
        return
    if not account.auto_reply_dm:
        return  # فروشگاه‌دار پاسخِ خودکار را خاموش کرده؛ رویداد فقط خوانده می‌شود

    customer_tg_id = customer_key(event.sender_psid)
    owner = await shop_owner_service.get_by_id(session, shop_bot.shop_owner_id)
    # هر پیامِ تازه از مشتری، پنجرهٔ ۲۴ساعته را از نو باز می‌کند؛ متا گاهی `created_time` را
    # نمی‌فرستد، پس «همین حالا» پیش‌فرضِ امن است (ردِ پاسخِ تازه بدتر از فرستادنش است).
    window_opened_at = event.created_at or datetime.datetime.now(datetime.timezone.utc)

    if admin_settings.maintenance_mode:
        await send_message(session, account, event.sender_psid, shop_texts.PLATFORM_MAINTENANCE_REPLY, window_opened_at=window_opened_at)
        return

    access_state = await order_access_service.evaluate(session, owner, admin_settings)
    if access_state == order_access_service.NO_CREDIT:
        await send_message(session, account, event.sender_psid, shop_texts.SHOP_UNAVAILABLE, window_opened_at=window_opened_at)
        if owner is not None and await wallet_service.try_claim_empty_notification(session, owner):
            await _notify_owner(main_bot, owner.telegram_id)
        await session.commit()
        return

    if not rate_limiter.check_and_record(
        shop_bot.id,
        customer_tg_id,
        shop_prefs_service.resolve(shop_prefs_service.RATE_LIMIT_MESSAGES, shop_bot, admin_settings),
        shop_prefs_service.resolve(shop_prefs_service.RATE_LIMIT_SECONDS, shop_bot, admin_settings),
    ):
        await send_message(session, account, event.sender_psid, shop_texts.RATE_LIMITED, window_opened_at=window_opened_at)
        return

    customer = await customer_service.get_or_create_customer(
        session, shop_bot.id, customer_tg_id, None, None, platform=platform_service.INSTAGRAM
    )
    if customer.is_blocked:
        # P18 · B4 مثلِ دو کانالِ دیگر: پیامِ بلاک‌شده بی‌هزینه رد می‌شود (نه AI، نه سفارش، نه کسر).
        await send_message(session, account, event.sender_psid, shop_texts.CUSTOMER_BLOCKED_NOTICE, window_opened_at=window_opened_at)
        await session.commit()
        return

    matched_rule = await moderation_service.check_text(session, event.text, shop_bot_id=shop_bot.id)
    if matched_rule is not None:
        action = matched_rule.action.value if hasattr(matched_rule.action, "value") else str(matched_rule.action)
        report = await moderation_service.record_report(
            session, shop_bot_id=shop_bot.id, customer_id=customer.id, rule=matched_rule, text=event.text
        )
        await audit_log_service.log(
            session,
            AuditEventType.MODERATION_MATCH,
            shop_bot_id=shop_bot.id,
            actor_telegram_id=customer_tg_id,
            details=f"الگو: {matched_rule.pattern} | اکشن: {action} | کانال: اینستاگرام | گزارش: {report.id}",
        )
        if action == "block":
            await crm_service.set_blocked(session, customer, True)
        await session.commit()
        await send_message(session, account, event.sender_psid, shop_texts.MODERATION_BLOCKED_REPLY, window_opened_at=window_opened_at)
        await moderation_notify_service.send_report_cards(
            main_bot,
            session,
            shop_bot=shop_bot,
            owner=owner,
            customer=customer,
            report=report,
            to_admins=matched_rule.shop_bot_id is None,
        )
        if action != "warn":
            return

    if not order_access_service.chat_continues(access_state):
        # موجودی در فاصله‌یِ خواندنِ رویداد تا اینجا صفر شده ⇒ هزینه‌یِ بی‌فایده تحمیل نمی‌شود.
        await send_message(session, account, event.sender_psid, shop_texts.SHOP_UNAVAILABLE, window_opened_at=window_opened_at)
        return

    if not admin_settings.ai_api_key:
        logger.warning("کلید API هوش مصنوعی تنظیم نشده؛ پاسخِ اینستاگرام ممکن نیست (فروشگاه %s).", shop_bot.id)
        await send_message(session, account, event.sender_psid, shop_texts.AI_ERROR_REPLY, window_opened_at=window_opened_at)
        await bot_error_service.log_error(session, shop_bot.id)
        await session.commit()
        return

    products = await product_service.get_active_by_shop_bot(session, shop_bot.id)
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
        # در دایرکتِ اینستاگرام هیچ دکمه‌ای نمایش داده نمی‌شود ⇒ «ابزارهایِ ربات» خالی می‌ماند تا
        # مدل مشتری را به دکمه‌ای دعوت نکند که وجود ندارد (همان قاعدهٔ P24ِ «دکمهٔ مرده»).
        bot_tools=[],
        channel_directive=instruction_directive(account, admin_settings, shop_bot),
    )
    history = await conversation_service.get_recent_history(
        session, customer.id, shop_prefs_service.resolve(shop_prefs_service.HISTORY_LIMIT, shop_bot, admin_settings)
    )

    ai = await ai_pool_service.build_ai_service(session, admin_settings, "chat")
    if ai is None:
        logger.error("هیچ کلیدِ AI‌ای برای فروشگاه %s تنظیم نشده (کانالِ اینستاگرام).", shop_bot.id)
        await send_message(session, account, event.sender_psid, shop_texts.AI_ERROR_REPLY, window_opened_at=window_opened_at)
        await session.commit()
        return

    # پ۵۵ · موردِ ۲۳: همان دو اهرمِ ادمین برایِ کاربرِ اینستاگرام هم اجرا می‌شود، وگرنه یکِ
    # کاربرِ متوقف‌شده می‌توانست از راهِ کانالِ دیگر بی‌هزینه پاسخ بگیرد.
    guard = await ai_usage_service.block_reason(session, customer)
    if guard is not None:
        await send_message(
            session,
            account,
            event.sender_psid,
            shop_texts.AI_USAGE_PAUSED_REPLY if guard == ai_usage_service.REASON_PAUSED else shop_texts.AI_USAGE_LIMIT_REPLY,
            window_opened_at=window_opened_at,
        )
        await session.commit()
        return

    try:
        await session.commit()  # قاعدهٔ ۷: آزادکردنِ اتصالِ دیتابیس پیش ازِ انتظارِ شبکه
        ai_result = await ai.get_reply(system_prompt, history, event.text)
    except ai_service.AiServiceError:
        logger.exception("فراخوانیِ هوش مصنوعی برایِ مشتریِ اینستاگرام %s در فروشگاه %s ناموفق بود.", _tail(event.sender_psid), shop_bot.id)
        await send_message(session, account, event.sender_psid, shop_texts.AI_ERROR_REPLY, window_opened_at=window_opened_at)
        await bot_error_service.log_error(session, shop_bot.id)
        await session.commit()
        return

    reply, gap_flagged = knowledge_service.strip_gap_marker(ai_result.text)
    reply = text_limits.strip_markdown(reply)
    reply = text_limits.clip(reply, text_limits.INSTAGRAM_DM_LIMIT)
    if not reply:
        reply = shop_texts.GAP_FALLBACK_REPLY
    if gap_flagged and admin_settings.knowledge_gap_enabled:
        await knowledge_service.record_gap(session, shop_bot.id, event.text)

    if not await send_message(session, account, event.sender_psid, reply, window_opened_at=window_opened_at):
        # پاسخِ نرسیده هزینهٔ صاحبِ فروشگاه نمی‌شود و تاریخچه هم عوض نمی‌شود (مثلِ تلگرام/بله).
        await session.commit()
        return

    await conversation_service.save_turn(session, customer.id, event.text, reply)
    cost = wallet_service.estimate_chat_cost(admin_settings, ai_result.total_tokens)
    await chat_billing_service.deduct_and_notify(
        session, owner, admin_settings, cost, WalletTransactionReason.CHAT_MESSAGE, main_bot, customer_id=customer.id,
        ai_total_tokens=ai_result.total_tokens,
    )
    await session.commit()

    await mark_seen(account, event.message_id)
    await maybe_offer_payment(session, account, shop_bot, customer, event.sender_psid)


async def _notify_owner(main_bot, owner_telegram_id: int) -> None:
    """اعلانِ «کیف‌پول خالی است» از رباتِ اصلی — همان متنِ مشترکِ سه کانال، بدونِ شکستنِ مسیر."""
    try:
        await main_bot.send_message(owner_telegram_id, main_texts.wallet_empty_notification())
    except TelegramAPIError:
        logger.exception("اطلاعِ اتمامِ کیف‌پول به فروشگاه‌دار %s ناموفق بود.", owner_telegram_id)
