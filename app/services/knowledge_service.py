"""
خلأیِ دانش + پرسش‌وپاسخِ تاییدشده (فازِ ۴-الف و ۴-ب).

۴-الف — تشخیصِ خلأ (بدونِ هزینه‌یِ AIِ اضافه): وقتی کلیدِ سراسریِ ادمین روشنه، به پرامپتِ
رباتِ فروشگاه یه دستور اضافه می‌شه که اگه جوابِ سوال رو نمی‌دونه، آخرِ پیام نشانه‌یِ
`[[GAP]]` بذاره. کد (customer.py) نشانه رو *قبل از ذخیره و ارسال* حذف می‌کنه (پس نه به
مشتری می‌رسه نه توی تاریخچه می‌ره) و سوالِ مشتری رو اینجا ثبت می‌کنه.

۴-ب — یادگیری فقط با تاییدِ فروشگاه‌دار: هیچ‌چیز خودکار از مکالمه‌ها یاد گرفته نمی‌شه.
فروشگاه‌دار برایِ یه «سوالِ بی‌جواب» جواب می‌نویسه (یا دستی یه پرسش‌وپاسخ اضافه می‌کنه)، و
فقط همین‌ها (حداکثر ۲۰ موردِ جدیدِ فعال) توی پرامپتِ ربات می‌رن.

اصولِ امنیتی:
- سوالِ ثبت‌شده از متنِ مشتری میاد = *غیرِ قابلِ اعتماد* (ممکنه تزریقِ پرامپت باشه). توی UI
  همیشه متنِ ساده نشون داده می‌شه و توی پرامپت فقط به‌شکلِ نقل‌قولِ برچسب‌دار می‌ره.
- سقفِ تعدادِ سوال‌هایِ بازِ هر فروشگاه (MAX_OPEN_GAPS_PER_SHOP): مشتریِ بدخواه نتونه با
  سوال‌هایِ بی‌پایانِ متفاوت، فهرستِ فروشگاه‌دار رو سیل کنه (تکراری‌ها همچنان شمرده می‌شن).

منطقِ خالص (بدونِ دیتابیس) جدا از بخشِ دیتابیسه تا مستقل تست بشه.
"""
from __future__ import annotations

import datetime
import hashlib
import re

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import KnowledgeGap, KnowledgeGapStatus, LearnedAnswer

# نشانه‌ای که AI آخرِ پیام می‌ذاره؛ این رشته دقیقاً توی دستورِ پرامپت (ai_context) هم هست.
GAP_MARKER = "[[GAP]]"
# یک یا دو کروشه: دستور «[[GAP]]» می‌خواد، ولی مدل‌ها گاهی «[GAP]» می‌نویسن؛ هر دو حذف و به‌عنوانِ نشانه
# حساب می‌شن تا هیچ‌وقت به مشتری نرسه.
_GAP_MARKER_RE = re.compile(r"\[{1,2}\s*GAP\s*\]{1,2}", re.IGNORECASE)

GAP_QUESTION_MAX_LEN = 300
LEARNED_QUESTION_MAX_LEN = 200
LEARNED_ANSWER_MAX_LEN = 500
MAX_LEARNED_ANSWERS_PER_SHOP = 200
PROMPT_LEARNED_LIMIT = 20
MAX_OPEN_GAPS_PER_SHOP = 500

GAPS_PAGE_SIZE = 5
LEARNED_PAGE_SIZE = 8

_DIGIT_TABLE = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_CHAR_TABLE = str.maketrans({"ي": "ی", "ى": "ی", "ك": "ک", "ـ": None})
_DIACRITICS_RE = re.compile("[\u064b-\u065f\u0670]")
_SPACES_RE = re.compile(r"\s+")


class KnowledgeError(ValueError):
    """خطایِ اعتبارسنجی؛ code یه شناسه‌یِ ماشینیه (نه متنِ کاربر): empty_question، empty_answer،
    limit_reached، gap_not_open."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


# =============================================================================
# منطقِ خالص (بدونِ دیتابیس)
# =============================================================================
def strip_gap_marker(text: str | None) -> tuple[str, bool]:
    """همه‌یِ نشانه‌هایِ [[GAP]] (یا [GAP]؛ بدونِ حساسیت به حروف، با فاصله‌یِ اختیاری تویِ کروشه، هر
    جایِ متن) رو حذف می‌کنه. خروجی: (متنِ تمیز، آیا نشانه بود). متنِ تمیز بدونِ فاصله‌یِ اضافه در
    ابتدا/انتهاست و فاصله‌هایِ دوبل‌شده‌یِ جایِ نشانه جمع می‌شن."""
    if not text:
        return "", False
    if not _GAP_MARKER_RE.search(text):
        return text, False
    cleaned = _GAP_MARKER_RE.sub("", text)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    return cleaned.strip(), True


def normalize_question(text: str | None) -> str:
    """سوال رو برایِ تشخیصِ تکراری بودن یکسان‌سازی می‌کنه: حروفِ کوچیک، رقمِ فارسی/عربی →
    انگلیسی، «ي/ك» عربی → فارسی، اعراب و کشیده حذف، و همه‌چیزِ غیرِ حرف/رقم (فاصله، نیم‌فاصله،
    علامت‌هایِ نگارشی، ایموجی) دور ریخته می‌شه. پس «قیمتِ ارسال؟» و «قیمت ارسال» یکی‌ان."""
    if not text:
        return ""
    folded = text.translate(_DIGIT_TABLE).translate(_CHAR_TABLE).casefold()
    folded = _DIACRITICS_RE.sub("", folded)
    return "".join(ch for ch in folded if ch.isalnum())


def make_question_key(text: str | None) -> str | None:
    """هشِ (SHA-256، ۶۴ حرفِ hex) سوالِ نرمال‌شده؛ اگه چیزی از متن نمونه (فقط علامت/ایموجی) → None."""
    normalized = normalize_question(text)
    if not normalized:
        return None
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def truncate_text(text: str | None, max_len: int) -> str:
    """متن رو تک‌خطی می‌کنه (هر فاصله/خطِ جدیدِ پشتِ‌هم → یه فاصله) و اگه از max_len بلندتر بود با
    «…» می‌بره، طوری که طولِ نتیجه هیچ‌وقت از max_len بیشتر نشه."""
    collapsed = _SPACES_RE.sub(" ", (text or "")).strip()
    if len(collapsed) <= max_len:
        return collapsed
    return collapsed[: max_len - 1].rstrip() + "…"


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


# =============================================================================
# ۴-الف: ثبتِ خلأ
# =============================================================================
async def count_open_gaps(session: AsyncSession, shop_bot_id: int) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(KnowledgeGap)
        .where(KnowledgeGap.shop_bot_id == shop_bot_id, KnowledgeGap.status == KnowledgeGapStatus.OPEN)
    )
    return int(result.scalar_one())


async def record_gap(
    session: AsyncSession, shop_bot_id: int, question_text: str | None, now: datetime.datetime | None = None
) -> bool:
    """سوالِ مشتری رو به‌عنوانِ «بی‌جواب» ثبت می‌کنه. اتمیک (INSERT … ON CONFLICT DO UPDATE)،
    پس دو مشتریِ هم‌زمان که یه سوال رو می‌پرسن یه ردیف می‌سازن و occurrences درست بالا می‌ره.

    - تکراری: occurrences += 1 و last_seen_at؛ status دست‌نخورده (گپِ dismissed/answered دوباره
      باز نمی‌شه، فقط شمارنده بالا می‌ره).
    - اگه فروشگاه به سقفِ MAX_OPEN_GAPS_PER_SHOP رسیده باشه، سوالِ *تازه* ثبت نمی‌شه (فقط
      تکراری‌هایِ موجود شمرده می‌شن).
    خروجی: True = ثبت/شمارش شد، False = متنِ بی‌معنی بود یا سقف پر بود.
    """
    key = make_question_key(question_text)
    if key is None:
        return False
    now = now or _utcnow()
    clean_text = truncate_text(question_text, GAP_QUESTION_MAX_LEN)

    if await count_open_gaps(session, shop_bot_id) >= MAX_OPEN_GAPS_PER_SHOP:
        result = await session.execute(
            update(KnowledgeGap)
            .where(KnowledgeGap.shop_bot_id == shop_bot_id, KnowledgeGap.question_key == key)
            .values(occurrences=KnowledgeGap.occurrences + 1, last_seen_at=now)
        )
        return bool(result.rowcount)

    statement = pg_insert(KnowledgeGap).values(
        shop_bot_id=shop_bot_id,
        question_text=clean_text,
        question_key=key,
        cluster_key=cluster_signature(question_text),  # پ۷۵: امضا همان لحظه نوشته می‌شود
        occurrences=1,
        first_seen_at=now,
        last_seen_at=now,
        status=KnowledgeGapStatus.OPEN,
    )
    statement = statement.on_conflict_do_update(
        index_elements=["shop_bot_id", "question_key"],
        set_={"occurrences": KnowledgeGap.occurrences + 1, "last_seen_at": now},
    )
    await session.execute(statement)
    return True


async def list_open_gaps(
    session: AsyncSession, shop_bot_id: int, page: int = 0, page_size: int = GAPS_PAGE_SIZE
) -> tuple[list[KnowledgeGap], int]:
    """(ردیف‌هایِ همین صفحه، تعدادِ کلِ سوال‌هایِ باز). به ترتیبِ تکرار (بیشتر اول) و بعد تازگی."""
    total = await count_open_gaps(session, shop_bot_id)
    page = max(0, page)
    result = await session.execute(
        select(KnowledgeGap)
        .where(KnowledgeGap.shop_bot_id == shop_bot_id, KnowledgeGap.status == KnowledgeGapStatus.OPEN)
        .order_by(KnowledgeGap.occurrences.desc(), KnowledgeGap.last_seen_at.desc(), KnowledgeGap.id.desc())
        .offset(page * page_size)
        .limit(page_size)
    )
    return list(result.scalars().all()), total


async def get_owned_gap(session: AsyncSession, gap_id: int | None, shop_bot_id: int) -> KnowledgeGap | None:
    """gap_id از callback_data میاد (قابلِ دستکاری) → مالکیت همیشه چک می‌شه."""
    if gap_id is None:
        return None
    result = await session.execute(
        select(KnowledgeGap).where(KnowledgeGap.id == gap_id, KnowledgeGap.shop_bot_id == shop_bot_id)
    )
    return result.scalar_one_or_none()


async def dismiss_gap(session: AsyncSession, gap: KnowledgeGap) -> bool:
    """فقط یه گپِ باز رو می‌شه نادیده گرفت. True = انجام شد."""
    if gap.status != KnowledgeGapStatus.OPEN:
        return False
    gap.status = KnowledgeGapStatus.DISMISSED
    await session.flush()
    return True


async def count_new_open_gaps(
    session: AsyncSession, shop_bot_id: int, since: datetime.datetime, until: datetime.datetime
) -> int:
    """برایِ گزارشِ شبانه: چند سوالِ *تازه* (اولین‌بارِ دیده‌شدنش توی بازه) هنوز بازه."""
    result = await session.execute(
        select(func.count())
        .select_from(KnowledgeGap)
        .where(
            KnowledgeGap.shop_bot_id == shop_bot_id,
            KnowledgeGap.status == KnowledgeGapStatus.OPEN,
            KnowledgeGap.first_seen_at >= since,
            KnowledgeGap.first_seen_at < until,
        )
    )
    return int(result.scalar_one())


# =============================================================================
# ۴-ب: پرسش‌وپاسخِ تاییدشده
# =============================================================================
async def count_learned(session: AsyncSession, shop_bot_id: int) -> int:
    result = await session.execute(select(func.count()).select_from(LearnedAnswer).where(LearnedAnswer.shop_bot_id == shop_bot_id))
    return int(result.scalar_one())


async def create_learned_answer(
    session: AsyncSession, shop_bot_id: int, question: str | None, answer: str | None, source_gap_id: int | None = None
) -> LearnedAnswer:
    """یه پرسش‌وپاسخِ تاییدشده می‌سازه. طول‌ها دفاعی کوتاه می‌شن (سوال ۲۰۰، جواب ۵۰۰)؛ UI قبلش
    ورودیِ بلندتر رو رد می‌کنه. سقفِ ۲۰۰ مورد به‌ازایِ هر فروشگاه."""
    clean_question = truncate_text(question, LEARNED_QUESTION_MAX_LEN)
    clean_answer = truncate_text(answer, LEARNED_ANSWER_MAX_LEN)
    if not clean_question:
        raise KnowledgeError("empty_question")
    if not clean_answer:
        raise KnowledgeError("empty_answer")
    if await count_learned(session, shop_bot_id) >= MAX_LEARNED_ANSWERS_PER_SHOP:
        raise KnowledgeError("limit_reached")

    learned = LearnedAnswer(
        shop_bot_id=shop_bot_id, question=clean_question, answer=clean_answer, source_gap_id=source_gap_id, is_active=True
    )
    session.add(learned)
    await session.flush()
    return learned


async def answer_gap(session: AsyncSession, gap: KnowledgeGap, answer: str | None) -> LearnedAnswer:
    """جوابِ فروشگاه‌دار به یه سوالِ بی‌جواب: پرسش‌وپاسخِ تاییدشده می‌سازه و گپ → ANSWERED.
    فقط گپِ باز. اگه ساختِ پرسش‌وپاسخ خطا بده، وضعیتِ گپ عوض نمی‌شه."""
    if gap.status != KnowledgeGapStatus.OPEN:
        raise KnowledgeError("gap_not_open")
    learned = await create_learned_answer(session, gap.shop_bot_id, gap.question_text, answer, source_gap_id=gap.id)
    gap.status = KnowledgeGapStatus.ANSWERED
    await session.flush()
    return learned


async def list_learned(
    session: AsyncSession, shop_bot_id: int, page: int = 0, page_size: int = LEARNED_PAGE_SIZE
) -> tuple[list[LearnedAnswer], int]:
    total = await count_learned(session, shop_bot_id)
    page = max(0, page)
    result = await session.execute(
        select(LearnedAnswer)
        .where(LearnedAnswer.shop_bot_id == shop_bot_id)
        .order_by(LearnedAnswer.id.desc())
        .offset(page * page_size)
        .limit(page_size)
    )
    return list(result.scalars().all()), total


async def get_owned_learned(session: AsyncSession, learned_id: int | None, shop_bot_id: int) -> LearnedAnswer | None:
    if learned_id is None:
        return None
    result = await session.execute(
        select(LearnedAnswer).where(LearnedAnswer.id == learned_id, LearnedAnswer.shop_bot_id == shop_bot_id)
    )
    return result.scalar_one_or_none()


async def update_learned_answer(session: AsyncSession, learned: LearnedAnswer, new_answer: str | None) -> None:
    clean_answer = truncate_text(new_answer, LEARNED_ANSWER_MAX_LEN)
    if not clean_answer:
        raise KnowledgeError("empty_answer")
    learned.answer = clean_answer
    learned.updated_at = _utcnow()
    await session.flush()


async def set_learned_active(session: AsyncSession, learned: LearnedAnswer, is_active: bool) -> None:
    learned.is_active = is_active
    learned.updated_at = _utcnow()
    await session.flush()


async def delete_learned(session: AsyncSession, learned: LearnedAnswer) -> None:
    await session.delete(learned)
    await session.flush()


async def get_active_for_prompt(
    session: AsyncSession, shop_bot_id: int, limit: int = PROMPT_LEARNED_LIMIT
) -> list[LearnedAnswer]:
    """جدیدترین پرسش‌وپاسخ‌هایِ *فعال*، حداکثر limit تا (پیش‌فرض ۲۰) — برایِ پرامپتِ ربات."""
    result = await session.execute(
        select(LearnedAnswer)
        .where(LearnedAnswer.shop_bot_id == shop_bot_id, LearnedAnswer.is_active.is_(True))
        .order_by(LearnedAnswer.id.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


# =============================================================================
# ۴-پ (پ۷۵): خوشه‌بندیِ سوال‌هایِ بی‌جواب
# =============================================================================
# خواستهٔ مالک (موردِ ۹): «سوال‌هایِ مشابه را گروه کن و از آن‌ها دانش بساز». امضا **واژگانی** است،
# نه معنایی: بدونِ وابستگیِ تازه و بدونِ هیچ فراخوانِ هوشِ مصنوعی، چون هدفِ این صفحه این است که
# فروشگاه‌دار *یک بار* جواب بنویسد و چند سوالِ هم‌معنی با همان جواب بسته شوند. پس دو سوال وقتی
# گروه می‌شوند که مجموعهٔ واژه‌هایِ محتوایی‌شان یکی باشد (ترتیب، علامت، اعراب و پرهملول‌ها بی‌اهمیت).
CLUSTER_MIN_SIZE = 2
CLUSTER_SCAN_LIMIT = MAX_OPEN_GAPS_PER_SHOP
CLUSTER_STOPWORDS = frozenset({
    "و", "با", "از", "به", "در", "که", "کی", "کجا", "چرا", "چه", "چی", "چطور", "چگونه", "آیا", "ای",
    "است", "هست", "می", "خوب", "لطفا", "لطفاً", "این", "آن", "یک", "دو", "چند", "من", "تو", "شما",
    "هو", "او", "ها", "ی", "اگه", "اگر", "بعد", "درباره", "درمورد", "را", "نیز", "هم",
})
# فقط حروفِ واقعی (عربی/فارسی/لاتین + رقم): علامت‌هایِ خودِ خطِ عربی («؟»، «،»، «؛»، «۔»، «٪») هم
# داخلِ بازهٔ U+0600-U+06FF هستند، پس اگر «هرچیز جز فاصله» را واژه بگیریم «چنده؟» با «چنده» یکی
# نمی‌شود و هیچ سوالی گروه نمی‌گیرد.
_LETTER_RUN_RE = re.compile(r"[0-9A-Za-z\u0621-\u063A\u0641-\u064A\u066E-\u06D3\uFB50-\uFD3F\uFE70-\uFEFC]+")
_ZWNJ_RE = re.compile(r"[\u200c\u0640]")


def _fold_words(text: str | None) -> str:
    """همان یکسان‌سازیِ `normalize_question`، ولی فاصله‌ها را نگه می‌دارد تا واژه‌ها جدا بمانند."""
    if not text:
        return ""
    folded = text.translate(_DIGIT_TABLE).translate(_CHAR_TABLE).casefold()
    folded = _DIACRITICS_RE.sub("", folded)
    folded = _ZWNJ_RE.sub("", folded)
    return " ".join(_LETTER_RUN_RE.findall(folded))


def cluster_signature(text: str | None) -> str | None:
    """امضایِ گروهِ سوال ⇒ هشِ ۶۴تاییِ مجموعهٔ واژه‌هایِ محتوایی؛ None اگر چیزی نماند.

    واژه‌هایِ پرهملول (و/با/چه/است/…) حذف می‌شوند تا «قیمت ارسال چنده» و «چنده قیمت ارسال» یکی
    شوند. اگر کمتر از دو واژهٔ محتوایی بماند امضا ساخته نمی‌شود (None): «سلام» یا «قیمت؟» با هر
    سوالِ مبهمِ دیگری گروه نمی‌شود، و سوالِ بی‌امضا در صفحهٔ گروه‌ها ظاهر نمی‌شود.
    """
    tokens = {word for word in _fold_words(text).split() if len(word) > 1 and word not in CLUSTER_STOPWORDS}
    if len(tokens) < 2:
        return None
    return hashlib.sha256("|".join(sorted(tokens)).encode("utf-8")).hexdigest()


async def backfill_cluster_keys(session: AsyncSession, shop_bot_id: int) -> int:
    """ردیف‌هایِ قدیمیِ همین فروشگاه که امضا ندارند را محاسبه و پر می‌کند (یکِ SELECT + UPDATEها).

    صفحهٔ خوشه‌ها همین‌جا را صدا می‌زند، پس مایگریشنِ داده لازم نیست: امضا فقط از متنِ خودِ سوال
    می‌آید و هیچ تصمیمِ تازه‌ای نمی‌گیرد.
    """
    rows = (
        await session.execute(
            select(KnowledgeGap.id, KnowledgeGap.question_text)
            .where(KnowledgeGap.shop_bot_id == shop_bot_id, KnowledgeGap.cluster_key.is_(None))
            .limit(CLUSTER_SCAN_LIMIT)
        )
    ).all()
    for gap_id, question_text in rows:
        await session.execute(update(KnowledgeGap).where(KnowledgeGap.id == gap_id).values(cluster_key=cluster_signature(question_text)))
    await session.flush()
    return len(rows)


async def list_gap_clusters(
    session: AsyncSession, shop_bot_id: int, *, min_size: int = CLUSTER_MIN_SIZE, limit: int = 10
) -> list[dict]:
    """گروه‌هایِ سوال‌هایِ باز، بزرگ‌ترینِ گروه اول.

    خروجیِ هر گروه: `representative` (ردیفِ پرتکرارترین، برایِ شناسه و متنِ نمایش)، `questions`
    (متن‌هایِ عضو)، `size` (چند سوالِ متفاوت) و `occurrences` (جمعِ تکرارها). فقط گروه‌هایی که
    حداقل `min_size` سوالِ *متفاوت* دارند برمی‌گردند؛ سوالِ یکتا خوشه نیست.
    """
    await backfill_cluster_keys(session, shop_bot_id)
    rows = list(
        (
            await session.execute(
                select(KnowledgeGap)
                .where(
                    KnowledgeGap.shop_bot_id == shop_bot_id,
                    KnowledgeGap.status == KnowledgeGapStatus.OPEN,
                    KnowledgeGap.cluster_key.is_not(None),
                )
                .order_by(KnowledgeGap.occurrences.desc(), KnowledgeGap.last_seen_at.desc(), KnowledgeGap.id.desc())
                .limit(CLUSTER_SCAN_LIMIT)
            )
        ).scalars().all()
    )
    buckets: dict[str, list[KnowledgeGap]] = {}
    for gap in rows:
        buckets.setdefault(gap.cluster_key, []).append(gap)
    clusters = [
        {
            "signature": key,
            "representative": members[0],
            "questions": [member.question_text for member in members],
            "size": len(members),
            "occurrences": sum(int(member.occurrences) for member in members),
        }
        for key, members in buckets.items()
        if len(members) >= max(1, min_size)
    ]
    clusters.sort(key=lambda item: (-item["size"], -item["occurrences"], item["representative"].id))
    return clusters[:limit]


async def answer_cluster(session: AsyncSession, shop_bot_id: int, signature: str, answer: str | None) -> tuple[LearnedAnswer, int]:
    """یکِ جواب برایِ همهٔ سوال‌هایِ گروه: یکِ پرسش‌وپاسخِ فعال + ANSWERED شدنِ همهٔ عضوهایِ باز.

    متنِ سوالِ نماینده از خودِ مشتری آمده ⇒ غیرِ قابلِ اعتماد است و مثلِ مسیرِ تک‌سوالی برش می‌خورد؛
    جواب را خودِ فروشگاه‌دار نوشته (تاییدِ انسانی همان چیزی است که «خودکار» بودنِ این مسیر را امن
    می‌کند). خطایِ اعتبارسنجی از `create_learned_answer` عیناً بالا می‌آید و هیچ گپی عوض نمی‌شود.
    """
    if not signature:
        raise KnowledgeError("gap_not_open")
    members = list(
        (
            await session.execute(
                select(KnowledgeGap)
                .where(
                    KnowledgeGap.shop_bot_id == shop_bot_id,
                    KnowledgeGap.cluster_key == signature,
                    KnowledgeGap.status == KnowledgeGapStatus.OPEN,
                )
                .order_by(KnowledgeGap.occurrences.desc(), KnowledgeGap.last_seen_at.desc(), KnowledgeGap.id.desc())
            )
        ).scalars().all()
    )
    if not members:
        raise KnowledgeError("gap_not_open")
    representative = members[0]
    learned = await create_learned_answer(
        session, shop_bot_id, representative.question_text, answer, source_gap_id=representative.id
    )
    result = await session.execute(
        update(KnowledgeGap)
        .where(
            KnowledgeGap.shop_bot_id == shop_bot_id,
            KnowledgeGap.cluster_key == signature,
            KnowledgeGap.status == KnowledgeGapStatus.OPEN,
        )
        .values(status=KnowledgeGapStatus.ANSWERED.value)
    )
    await session.flush()
    return learned, int(result.rowcount or 0)
