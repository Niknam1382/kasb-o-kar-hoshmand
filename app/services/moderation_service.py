from __future__ import annotations

import datetime
import logging
import re
import signal
import threading

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import ModerationReport, ModerationRule

logger = logging.getLogger(__name__)

# =============================================================================
# محافظت در برابرِ ReDoS (Regular Expression Denial of Service)
# =============================================================================
#
# نسخه‌ی اول از ProcessPoolExecutor استفاده می‌کرد، ولی توی تست با Docker
# (و توی sandboxِ خودم) همیشه hang می‌کرد — به‌احتمالِ زیاد چون
# multiprocessing به‌شدت به semaphore/shared-memory وابسته‌ست و خیلی از
# محیط‌های کانتینری همین رو محدود می‌کنن. بعدِ تست، این نسخه به‌جاش از
# signal.SIGALRM استفاده می‌کنه — که مستقیم امتحانش کردم و برخلافِ
# asyncio.wait_for، واقعاً یه re.search()ِ گیرافتاده رو قطع می‌کنه (چون
# سیگنال، برخلافِ یه timeoutِ سطحِ asyncio، سطحِ سیستم‌عامله و کدِ در حالِ
# اجرا رو واقعاً وقفه می‌ده، نه اینکه فقط منتظرش نمونه).
#
# محدودیتِ signal.SIGALRM: فقط توی threadِ اصلیِ پردازه کار می‌کنه (محدودیتِ
# خودِ پایتونه، نه چیزی که من اضافه کرده باشم). چون کلِ اپ روی یه event loop
# تک‌رشته‌ای می‌چرخه، این عملاً همیشه صادقه؛ ولی برای احتیاط، اگه یه‌جا این
# فرض نقض بشه (مثلاً یه threadِ جدید)، بدونِ crash‌کردن به یه matchِ
# بدونِ‌محافظت (با لاگِ هشدار) برمی‌گرده — نگهبانِ محتوا یه قابلیتِ ایمنیِ
# جانبیه، نباید خودش باعثِ خرابیِ کلِ پیام‌رسانی بشه.
#
# محافظت دو لایه‌ست:
#   ۱. validate_pattern_safety: یه فیلترِ heuristic و ارزون در برابرِ رایج‌ترین
#      شکلِ خطرناک (کوانتیفایرِ تودرتو) — موقعِ ذخیره‌ی قانون.
#   ۲. تطبیقِ واقعی (check_text): مستقل از لایه‌ی ۱، هر matchِ regex رو با
#      سقفِ سختِ ۱۰۰ میلی‌ثانیه (SIGALRM) اجرا می‌کنه.

_REDOS_TIMEOUT_SECONDS = 0.1  # طبقِ مسترپرامپت: ۱۰۰ میلی‌ثانیه
_MAX_PATTERN_LENGTH = 200
_MAX_TEXT_LENGTH_FOR_REGEX = 4096  # پیام‌های تلگرام هم همین حدود سقف دارن؛ یه محافظتِ ارزونِ اضافه
_NESTED_QUANTIFIER_RE = re.compile(r"\([^()]*[+*][^()]*\)[+*{]")


class UnsafePatternError(ValueError):
    """الگوی regex به‌نظر خطرناک (احتمالِ ReDoS) یا نامعتبر می‌رسه."""


class _RegexTimeout(Exception):
    """داخلی: فقط برای قطع‌کردنِ re.search از طریقِ signal handler."""


def validate_pattern_safety(pattern: str, is_regex: bool) -> None:
    """
    اگه pattern مشکوکه (کوانتیفایرِ تودرتو مثلِ (x+)+ یا (x*)+، خیلی بلنده، یا
    اصلاً regexِ نامعتبریه) یه UnsafePatternError پرتاب می‌کنه. برای قوانینِ
    غیر-regex کاری نمی‌کنه.
    """
    if not is_regex:
        return
    if len(pattern) > _MAX_PATTERN_LENGTH:
        raise UnsafePatternError(f"الگو خیلی بلنده (بیشتر از {_MAX_PATTERN_LENGTH} کاراکتر مجاز نیست).")
    if _NESTED_QUANTIFIER_RE.search(pattern):
        raise UnsafePatternError(
            "این الگو یه کوانتیفایرِ تودرتو داره (مثلِ (x+)+ یا (x*)+) که می‌تونه باعثِ "
            "کندیِ فاجعه‌بار (ReDoS) بشه. لطفاً الگو رو ساده‌تر بنویس."
        )
    try:
        re.compile(pattern)
    except re.error as exc:
        raise UnsafePatternError(f"الگوی regex نامعتبره: {exc}") from exc


def _alarm_handler(signum, frame) -> None:
    raise _RegexTimeout()


def _safe_regex_match(pattern: str, text: str) -> bool:
    """
    نتیجه‌ی matchِ regex، با سقفِ ۱۰۰ میلی‌ثانیه‌ای. اگه زمان تموم بشه یا هر
    خطای دیگه‌ای پیش بیاد، False برمی‌گردونه (یعنی این قانون برای همین‌یه
    پیام نادیده گرفته می‌شه، نه این‌که کلِ پیامِ مشتری بلاک بشه) و لاگ می‌شه.
    این تابع sync ـه (نه async) چون SIGALRM فقط با کدِ synchronous معنی داره؛
    check_text آسنکرونه ولی خودِ این match یه عملیاتِ کوتاه و بلاک‌کننده‌ست
    (حداکثر ۱۰۰ میلی‌ثانیه)، دقیقاً مثلِ خودِ re.search بدونِ محافظت.
    """
    text = text[:_MAX_TEXT_LENGTH_FOR_REGEX]

    if threading.current_thread() is not threading.main_thread():
        # signal.signal فقط توی threadِ اصلی کار می‌کنه. این حالت توی معماریِ
        # فعلی (یه event loopِ تک‌رشته‌ای) نباید پیش بیاد، ولی برای احتیاط،
        # به‌جای crash، بدونِ محافظتِ timeout مچ می‌کنیم (بهتر از قطع‌شدنِ
        # کاملِ نگهبانِ محتوا).
        logger.warning("چکِ regexِ نگهبانِ محتوا خارج از threadِ اصلی صدا زده شد — بدونِ محافظتِ timeout اجرا می‌شه.")
        try:
            return re.search(pattern, text, re.IGNORECASE) is not None
        except re.error:
            return False

    old_handler = signal.signal(signal.SIGALRM, _alarm_handler)
    signal.setitimer(signal.ITIMER_REAL, _REDOS_TIMEOUT_SECONDS)
    try:
        return re.search(pattern, text, re.IGNORECASE) is not None
    except _RegexTimeout:
        logger.error(
            "قانونِ نگهبانِ محتوا با الگوی regex بیش از %d میلی‌ثانیه طول کشید (احتمالِ ReDoS) — "
            "برای این پیام نادیده گرفته شد. الگو: %r",
            int(_REDOS_TIMEOUT_SECONDS * 1000),
            pattern,
        )
        return False
    except re.error:
        logger.exception("الگوی regexِ نگهبانِ محتوا نامعتبره: %r", pattern)
        return False
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)


# =============================================================================
# P43 · موردِ ۳۰ — دقتِ تطبیق (باگِ واقعی: قانونِ «خر» کلمهٔ «آخر/خرید» را هم می‌گرفت)
# =============================================================================
# دو لایه:
#   ۱) نرمال‌سازی: ي/ك/ى عربی ← فارسی، حذفِ تنوین/کشیده/علامت‌ها، ZWNJ مرزِ کلمه است.
#   ۲) تطبیقِ «کلِ کلمه» برایِ قوانینِ غیرِ regex: الگو به کلمه‌ها شکسته می‌شود و باید
#      *به‌ترتیب و کامل* در کلمه‌هایِ پیام بیاید. پس «خر» ≠ «آخر» و «خرید» ≠ «خر»، ولی
#      «تقلب  کردن» همان عبارت را با فاصله‌هایِ اضافه هم پیدا می‌کند.
# برایِ regex رفتارِ قبلی دست‌نخورده است (نویسندهٔ الگو خودش مرز را می‌نویسد) و همان محافظتِ
# ReDoS ۱۰۰ میلی‌ثانیه‌ای سرِ جایش است.
_ARABIC_TO_PERSIAN = {"ي": "ی", "ك": "ک", "ى": "ی", "ە": "ه", "ؤ": "و", "أ": "ا", "إ": "ا", "آ": "ا"}
_DIACRITICS = "ًٌٍَُِّْٰـ​"  # تنوین‌ها، حرکته‌ها، کشیده، ZWSP
_WORD_RE = re.compile("[0-9A-Za-z\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF']+")


def normalize_text(value: str) -> str:
    """نرمال‌ِ یکسانِ «الگو» و «متنِ پیام» — بی‌این، دو شکلِ نوشتاریِ یکِ کلمه مقابقت نمی‌کردند."""
    out = []
    for ch in value:
        if ch in _DIACRITICS:
            continue
        out.append(_ARABIC_TO_PERSIAN.get(ch, ch))
    return "".join(out).lower().replace("‌", " ")


def tokenize(value: str) -> list[str]:
    """کلمه‌هایِ نرمال‌شده؛ ترتیب نگه داشته می‌شود (تطبیقِ عبارت به ترتیب نیاز دارد)."""
    return _WORD_RE.findall(normalize_text(value))


def _phrase_matches(pattern_words: list[str], text_words: list[str]) -> bool:
    if not pattern_words:
        return False
    span = len(pattern_words)
    for start in range(len(text_words) - span + 1):
        if text_words[start : start + span] == pattern_words:
            return True
    return False


SCOPE_PLATFORM = "platform"
SCOPE_SHOP = "shop"
EXCERPT_MAX_LENGTH = 220


def excerpt_of(text: str) -> str:
    """بریدهِ دیدنیِ گزارش: بدونِ کنترل‌نویسه، با سقفِ طول (متنِ پیامِ مشتری، نه رازِ فنی)."""
    cleaned = " ".join((text or "").split())
    return cleaned[:EXCERPT_MAX_LENGTH]


async def get_rules(session: AsyncSession, shop_bot_id: int | None = None, *, active_only: bool = True) -> list[ModerationRule]:
    """قانون‌هایِ پلتفرم (shop_bot_id خالی) + قانون‌هایِ *همان* فروشگاه، در یکِ SELECT.

    ترتیبِ عمدی: اولِ فروشگاه (اختصاصی‌تر)، بعدِ سراسری. بی‌این مرتب‌سازی، دو قانونِ یکسان با
    اکشنِ متفاوت بسته بهِ ترتیبِ بازگشتِ دیتابیس رفتارِ متفاوت می‌دادند.
    """
    query = select(ModerationRule)
    if active_only:
        query = query.where(ModerationRule.is_active.is_(True))
    if shop_bot_id is None:
        query = query.where(ModerationRule.shop_bot_id.is_(None))
    else:
        query = query.where(
            (ModerationRule.shop_bot_id.is_(None)) | (ModerationRule.shop_bot_id == shop_bot_id)
        )
    rows = list((await session.execute(query.order_by(ModerationRule.shop_bot_id.asc().nulls_last(), ModerationRule.id))).scalars().all())
    return rows


async def get_active_rules(session: AsyncSession) -> list[ModerationRule]:
    result = await session.execute(select(ModerationRule).where(ModerationRule.is_active.is_(True)))
    return list(result.scalars().all())


async def get_all_rules(session: AsyncSession) -> list[ModerationRule]:
    result = await session.execute(select(ModerationRule).order_by(ModerationRule.id.desc()))
    return list(result.scalars().all())


async def check_text(session: AsyncSession, text: str, *, shop_bot_id: int | None = None) -> ModerationRule | None:
    """اولین قانونِ مطابق (None ⇒ هیچ). `shop_bot_id` ⇒ قانون‌هایِ خودِ فروشگاه هم چک می‌شوند."""
    if not text:
        return None
    rules = await get_rules(session, shop_bot_id)
    if not rules:
        return None
    words = tokenize(text)
    for rule in rules:
        if rule.is_regex:
            if _safe_regex_match(rule.pattern, text):
                return rule
        elif _phrase_matches(tokenize(rule.pattern), words):
            return rule
    return None


def scope_of(rule: ModerationRule) -> str:
    return SCOPE_SHOP if rule.shop_bot_id is not None else SCOPE_PLATFORM


async def record_report(
    session: AsyncSession,
    *,
    shop_bot_id: int,
    customer_id: int | None,
    rule: ModerationRule,
    text: str,
) -> ModerationReport:
    """ردیفِ گزارش — پیش ازِ هر فراخوانیِ شبکه نوشته و commit می‌شود (قاعدهٔ ۷)."""
    report = ModerationReport(
        shop_bot_id=shop_bot_id,
        customer_id=customer_id,
        rule_id=rule.id,
        pattern=rule.pattern[:200],
        category=rule.category,
        action=rule.action.value if hasattr(rule.action, "value") else str(rule.action),
        scope=scope_of(rule),
        excerpt=excerpt_of(text),
    )
    session.add(report)
    await session.flush()
    return report


async def get_report(session: AsyncSession, report_id: int) -> ModerationReport | None:
    return await session.get(ModerationReport, report_id)


async def list_reports(session: AsyncSession, shop_bot_ids: list[int] | None, *, limit: int, offset: int = 0, only_open: bool = True):
    """گزارش‌هایِ تازه‌تر‌اول. `shop_bot_ids=None` ⇒ همه (پنلِ ادمین)؛ فهرست ⇒ فقط آن فروشگاه‌ها."""
    query = select(ModerationReport)
    if shop_bot_ids is not None:
        if not shop_bot_ids:
            return []
        query = query.where(ModerationReport.shop_bot_id.in_(shop_bot_ids))
    if only_open:
        query = query.where(ModerationReport.reviewed.is_(False))
    query = query.order_by(ModerationReport.created_at.desc(), ModerationReport.id.desc()).limit(limit).offset(offset)
    return list((await session.execute(query)).scalars().all())


async def count_reports(session: AsyncSession, shop_bot_ids: list[int] | None, *, only_open: bool = True) -> int:
    """چند گزارشِ باز؟ `shop_bot_ids=None` ⇒ همهٔ فروشگاه‌ها (صفحهٔ ادمین)."""
    query = select(func.count()).select_from(ModerationReport)
    if shop_bot_ids is not None:
        if not shop_bot_ids:
            return 0
        query = query.where(ModerationReport.shop_bot_id.in_(shop_bot_ids))
    if only_open:
        query = query.where(ModerationReport.reviewed.is_(False))
    return int((await session.execute(query)).scalar_one())


async def mark_reviewed(session: AsyncSession, report: ModerationReport) -> None:
    report.reviewed = True
    report.reviewed_at = datetime.datetime.now(datetime.timezone.utc)
    await session.flush()


async def create_rule(
    session: AsyncSession, pattern: str, is_regex: bool, action: str, category: str | None = None
) -> ModerationRule:
    validate_pattern_safety(pattern, is_regex)
    rule = ModerationRule(pattern=pattern, is_regex=is_regex, action=action, category=category)
    session.add(rule)
    await session.flush()
    return rule


async def get_by_id(session: AsyncSession, rule_id: int) -> ModerationRule | None:
    return await session.get(ModerationRule, rule_id)


async def toggle_active(session: AsyncSession, rule: ModerationRule) -> None:
    rule.is_active = not rule.is_active
    await session.flush()


async def delete_rule(session: AsyncSession, rule: ModerationRule) -> None:
    await session.delete(rule)
    await session.flush()
