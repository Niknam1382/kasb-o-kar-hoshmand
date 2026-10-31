from __future__ import annotations

import logging
import re
import signal
import threading

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import ModerationRule

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


async def get_active_rules(session: AsyncSession) -> list[ModerationRule]:
    result = await session.execute(select(ModerationRule).where(ModerationRule.is_active.is_(True)))
    return list(result.scalars().all())


async def get_all_rules(session: AsyncSession) -> list[ModerationRule]:
    result = await session.execute(select(ModerationRule).order_by(ModerationRule.id.desc()))
    return list(result.scalars().all())


async def check_text(session: AsyncSession, text: str) -> ModerationRule | None:
    """
    متن رو در برابرِ همه‌ی قوانینِ فعال چک می‌کنه و اولین قانونِ مطابق رو
    برمی‌گردونه (یا None اگه چیزی مطابقت نداشت).
    """
    if not text:
        return None
    rules = await get_active_rules(session)
    lowered = text.lower()
    for rule in rules:
        if rule.is_regex:
            if _safe_regex_match(rule.pattern, text):
                return rule
        else:
            if rule.pattern.lower() in lowered:
                return rule
    return None


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
