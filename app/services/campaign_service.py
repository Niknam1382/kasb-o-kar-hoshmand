"""
سازنده‌ی کمپین (فازِ ۳) — تخفیفِ مخصوصِ مشتری‌هایِ هر فروشگاه، روی چک‌اوتِ سبدِ خرید.

این ماژول *کاملاً جدا* از discount_service ـه (که DiscountCodeِ پلتفرم برایِ
پرداختِ فروشگاه‌دار به پلتفرم رو مدیریت می‌کنه).

اصولِ طراحی (به‌خاطرِ اینکه با پول سروکار داره):
- منطقِ خالص (نرمال‌سازیِ کد، محاسبه‌ی تخفیف، پخشِ تخفیف بینِ ردیف‌ها) از
  دسترسی به دیتابیس جداست تا مستقل تست بشه.
- تعدادِ دفعاتِ استفاده *شمارنده* نیست؛ هر بار از روی سفارش‌هایِ واقعی
  (OrderConsultation.campaign_id) شمرده می‌شه. پس ردِ سفارش یا انقضایِ رزرو،
  خودبه‌خود سهمیه رو آزاد می‌کنه و چیزی «برگردونده» نمی‌شه که بشه فراموشش کرد.
- موقعِ «ثبتِ نهایی»، ردیفِ کمپین‌هایِ کاندید با FOR UPDATE قفل می‌شن (find_best_offer
  با lock=True) تا دو مشتریِ هم‌زمان نتونن هر دو آخرین ظرفیت رو بگیرن.
- هیچ‌وقت تخفیف از جمعِ سبد بیشتر یا منفی نمی‌شه.
"""
from __future__ import annotations

import dataclasses
import datetime
import enum
import string

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Campaign, CampaignDiscountType, OrderConsultation, OrderStatus
from app.services.rate_limiter import rate_limiter

MIN_CODE_LENGTH = 3
MAX_CODE_LENGTH = 20
MAX_NAME_LENGTH = 60
MAX_TOMAN_VALUE = 1_000_000_000  # زیرِ سقفِ INTEGER ـِ PostgreSQL با فاصله‌ی امن
MAX_DURATION_DAYS = 365
MAX_LIMIT_VALUE = 1_000_000

# امتحانِ کدِ تخفیف توسطِ مشتری: حداکثر این‌قدر تلاش در این بازه (جلوگیریِ از حدس‌زدنِ کد).
CODE_ATTEMPTS_MAX = 10
CODE_ATTEMPTS_WINDOW_SECONDS = 600

# سفارش‌هایی که «سهمیه‌ی کمپین» رو آزاد می‌کنن: رد/منقضی/لغو. (سفارش‌هایِ سبد فقط با ردِ
# فروشگاه‌دار یا انقضایِ رزرو به این وضعیت‌ها می‌رن؛ CANCELLED برایِ احتیاطه.)
RELEASED_ORDER_STATUSES = (OrderStatus.REJECTED, OrderStatus.EXPIRED, OrderStatus.CANCELLED, OrderStatus.REFUNDED)
_RELEASED_STATUS_VALUES = [status.value for status in RELEASED_ORDER_STATUSES]


class RejectReason(str, enum.Enum):
    """چرا یه کمپین/کد برایِ این سبد اعمال نشد."""

    NOT_FOUND = "not_found"
    INACTIVE = "inactive"  # فروشگاه‌دار متوقفش کرده
    NOT_STARTED = "not_started"
    ENDED = "ended"
    MIN_CART = "min_cart"
    TOTAL_LIMIT = "total_limit"
    CUSTOMER_LIMIT = "customer_limit"
    NO_DISCOUNT = "no_discount"


class CampaignError(ValueError):
    """خطایِ اعتبارسنجیِ ساختِ کمپین؛ code یه شناسه‌ی ماشینیه (نه متنِ کاربر)."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclasses.dataclass(frozen=True)
class Offer:
    campaign_id: int
    campaign_name: str
    code: str | None
    discount_toman: int
    list_total_toman: int

    @property
    def final_total_toman(self) -> int:
        return self.list_total_toman - self.discount_toman


@dataclasses.dataclass(frozen=True)
class OfferResult:
    """خروجیِ find_best_offer: offer = تخفیفی که واقعاً اعمال می‌شه (یا None)."""

    offer: Offer | None
    # فقط وقتی مشتری کد وارد کرده: چرا کدِ واردشده اعمال نشد (None = معتبر بود/کدی نبود).
    code_problem: RejectReason | None = None
    code_min_cart_toman: int | None = None
    # کد معتبر بود ولی یه کمپینِ دیگه تخفیفِ بیشتری می‌داد، پس اون اعمال شد.
    code_outranked: bool = False
    # lock=True بود و واقعاً ردیفی از کمپین‌ها قفل شد (پس صدازننده باید زود commit کنه).
    locked: bool = False


# =============================================================================
# منطقِ خالص (بدونِ دیتابیس)
# =============================================================================
_PERSIAN_LETTERS = "آابپتثجچحخدذرزژسشصضطظعغفقکگلمنوهیءئؤأإ"
_ALLOWED_CODE_CHARS = frozenset(string.ascii_uppercase + string.digits + "_-" + _PERSIAN_LETTERS)

# رقم‌هایِ فارسی/عربی → انگلیسی؛ ی/ک عربی → فارسی؛ نیم‌فاصله/کشیده/فاصله حذف.
_DIGIT_TABLE = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_CHAR_TABLE = str.maketrans({"ي": "ی", "ى": "ی", "ك": "ک", "\u200c": None, "\u200d": None, "ـ": None})


def normalize_code(raw: str | None) -> str | None:
    """کدِ تخفیف رو به شکلِ یکتا درمی‌آره: بدونِ فاصله/نیم‌فاصله، حروفِ لاتین بزرگ،
    رقم‌هایِ فارسی/عربی انگلیسی، «ي/ك» عربی فارسی. خالی → None.
    (نه حساس به حروفِ بزرگ/کوچیک، نه به نوعِ رقم/ی/ک.)"""
    if raw is None:
        return None
    text = raw.translate(_DIGIT_TABLE).translate(_CHAR_TABLE)
    text = "".join(text.split()).upper()
    return text or None


def is_valid_code(code: str | None) -> bool:
    """کدِ نرمال‌شده باید ۳ تا ۲۰ نویسه از: حروفِ لاتین/فارسی، رقم، _ و - باشه."""
    if not code or not (MIN_CODE_LENGTH <= len(code) <= MAX_CODE_LENGTH):
        return False
    return all(ch in _ALLOWED_CODE_CHARS for ch in code)


def compute_discount(discount_type: str, value: int, max_discount_toman: int | None, cart_total_toman: int) -> int:
    """مبلغِ تخفیف (تومانِ صحیح، floor). هیچ‌وقت منفی یا بیشتر از جمعِ سبد نمی‌شه."""
    if cart_total_toman <= 0 or value <= 0:
        return 0
    type_value = discount_type.value if hasattr(discount_type, "value") else discount_type
    if type_value == CampaignDiscountType.PERCENT.value:
        discount = cart_total_toman * min(value, 100) // 100
        if max_discount_toman is not None:
            discount = min(discount, max_discount_toman)
    else:
        discount = value
    return max(0, min(discount, cart_total_toman))


def distribute_discount(line_totals: list[int], discount: int) -> list[int]:
    """تخفیفِ کلِ سبد رو متناسب با مبلغِ هر ردیف بینِ ردیف‌ها پخش می‌کنه.

    جمعِ سهم‌ها *دقیقاً* برابرِ discount (با سقفِ جمعِ سبد) و سهمِ هر ردیف بینِ
    صفر و مبلغِ همون ردیفه. باقی‌مانده‌ی گردکردن به روشِ «بیشترین باقی‌مانده»
    پخش می‌شه (به هر ردیف حداکثر +۱)، نه اینکه یکجا به یه ردیف بره — چون روشِ
    دوم تو سبدِ چندقلمیِ هم‌قیمت می‌تونست قیمتِ یه ردیف رو منفی کنه.
    """
    total = sum(line_totals)
    if not line_totals or total <= 0 or discount <= 0:
        return [0] * len(line_totals)
    discount = min(discount, total)

    shares = [discount * line // total for line in line_totals]
    remainder = discount - sum(shares)
    if remainder > 0:
        order = sorted(
            range(len(line_totals)),
            key=lambda i: (-(discount * line_totals[i] % total), -line_totals[i], i),
        )
        for index in order[:remainder]:
            shares[index] += 1
    return shares


def check_availability(campaign: Campaign, now: datetime.datetime) -> RejectReason | None:
    """فقط وضعیت/بازه‌ی زمانی (بدونِ شمارشِ مصرف). starts_at <= now < ends_at."""
    if not campaign.is_active:
        return RejectReason.INACTIVE
    if now < campaign.starts_at:
        return RejectReason.NOT_STARTED
    if now >= campaign.ends_at:
        return RejectReason.ENDED
    return None


def campaign_status(campaign: Campaign, now: datetime.datetime) -> str:
    """برایِ نمایش به فروشگاه‌دار: ended / paused / scheduled / active."""
    if now >= campaign.ends_at:
        return "ended"
    if not campaign.is_active:
        return "paused"
    if now < campaign.starts_at:
        return "scheduled"
    return "active"


def register_code_attempt(shop_bot_id: int, customer_telegram_id: int) -> bool:
    """هر بار که مشتری یه کد رو امتحان می‌کنه صدا بزن؛ False = تلاش‌هایِ زیادی شده.
    شناسه‌ی فروشگاه رو منفی می‌دیم تا سطلِ این محدودکننده با سطلِ پیام‌هایِ چتِ همون
    مشتری (که با شناسه‌ی مثبت ثبت می‌شه) قاطی نشه."""
    return rate_limiter.check_and_record(-shop_bot_id, customer_telegram_id, CODE_ATTEMPTS_MAX, CODE_ATTEMPTS_WINDOW_SECONDS)


def _validate_limit(value: int | None) -> None:
    if value is not None and not (1 <= value <= MAX_LIMIT_VALUE):
        raise CampaignError("bad_limit")


# =============================================================================
# دیتابیس
# =============================================================================
async def get_owned(session: AsyncSession, campaign_id: int, shop_bot_id: int) -> Campaign | None:
    """مثلِ order_service.get_owned_by_id: فروشگاه‌دار فقط کمپین‌هایِ فروشگاهِ خودش رو می‌بینه."""
    result = await session.execute(select(Campaign).where(Campaign.id == campaign_id, Campaign.shop_bot_id == shop_bot_id))
    return result.scalar_one_or_none()


LIST_LIMIT = 20  # سقفِ فهرستِ رویِ صفحه؛ هندلر وقتی پر باشد «نمایشِ ناقص» را می‌گوید


async def list_for_shop(session: AsyncSession, shop_bot_id: int, limit: int = LIST_LIMIT) -> list[Campaign]:
    result = await session.execute(
        select(Campaign).where(Campaign.shop_bot_id == shop_bot_id).order_by(Campaign.id.desc()).limit(limit)
    )
    return list(result.scalars().all())


async def get_by_code(session: AsyncSession, shop_bot_id: int, code: str, *, lock: bool = False) -> Campaign | None:
    query = select(Campaign).where(Campaign.shop_bot_id == shop_bot_id, Campaign.code == code)
    if lock:
        query = query.with_for_update()
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def has_open_code_campaign(session: AsyncSession, shop_bot_id: int, now: datetime.datetime | None = None) -> bool:
    """آیا این فروشگاه الان کمپینِ کددارِ فعال (در بازه‌ی زمانی) داره؟ — فقط برایِ
    اینکه دکمه‌ی «🎟 کد تخفیف دارم» تویِ پیش‌نمایش نشون داده بشه."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    result = await session.execute(
        select(func.count(Campaign.id)).where(
            Campaign.shop_bot_id == shop_bot_id,
            Campaign.code.is_not(None),
            Campaign.is_active.is_(True),
            Campaign.starts_at <= now,
            Campaign.ends_at > now,
        )
    )
    return int(result.scalar_one()) > 0


async def count_uses(session: AsyncSession, campaign_id: int, customer_id: int | None = None) -> int:
    """تعدادِ دفعاتِ استفاده = تعدادِ *چک‌اوت*هایِ (cart_checkout_group_id) متمایزی که این
    کمپین رو گرفتن و سفارش‌شون ردشده/منقضی/لغو *نشده*. (یه گروه تا وقتی حداقل یه ردیفِ
    زنده داشته باشه یه استفاده حساب می‌شه.)"""
    query = select(func.count(func.distinct(OrderConsultation.cart_checkout_group_id))).where(
        OrderConsultation.campaign_id == campaign_id,
        OrderConsultation.status.not_in(_RELEASED_STATUS_VALUES),
    )
    if customer_id is not None:
        query = query.where(OrderConsultation.customer_id == customer_id)
    result = await session.execute(query)
    return int(result.scalar_one())


async def usage_stats(session: AsyncSession, campaign_id: int) -> tuple[int, int]:
    """(تعدادِ دفعاتِ استفاده، جمعِ تخفیفِ داده‌شده به تومان) — فقط سفارش‌هایِ آزادنشده."""
    uses = await count_uses(session, campaign_id)
    result = await session.execute(
        select(func.coalesce(func.sum(OrderConsultation.discount_toman), 0)).where(
            OrderConsultation.campaign_id == campaign_id,
            OrderConsultation.status.not_in(_RELEASED_STATUS_VALUES),
        )
    )
    return uses, int(result.scalar_one())


async def _evaluate(
    session: AsyncSession, campaign: Campaign, customer_id: int, list_total_toman: int, now: datetime.datetime
) -> tuple[Offer | None, RejectReason | None]:
    problem = check_availability(campaign, now)
    if problem is not None:
        return None, problem
    if campaign.min_cart_total_toman is not None and list_total_toman < campaign.min_cart_total_toman:
        return None, RejectReason.MIN_CART
    if campaign.total_usage_limit is not None and await count_uses(session, campaign.id) >= campaign.total_usage_limit:
        return None, RejectReason.TOTAL_LIMIT
    if campaign.per_customer_limit is not None:
        if await count_uses(session, campaign.id, customer_id) >= campaign.per_customer_limit:
            return None, RejectReason.CUSTOMER_LIMIT

    discount = compute_discount(campaign.discount_type, campaign.discount_value, campaign.max_discount_toman, list_total_toman)
    if discount <= 0:
        return None, RejectReason.NO_DISCOUNT
    return Offer(campaign.id, campaign.name, campaign.code, discount, list_total_toman), None


async def _load_auto_campaigns(
    session: AsyncSession, shop_bot_id: int, now: datetime.datetime, lock: bool
) -> list[Campaign]:
    query = (
        select(Campaign)
        .where(
            Campaign.shop_bot_id == shop_bot_id,
            Campaign.code.is_(None),
            Campaign.is_active.is_(True),
            Campaign.starts_at <= now,
            Campaign.ends_at > now,
        )
        .order_by(Campaign.id)
    )
    if lock:
        query = query.with_for_update()
    result = await session.execute(query)
    return list(result.scalars().all())


async def find_best_offer(
    session: AsyncSession,
    shop_bot_id: int,
    customer_id: int,
    list_total_toman: int,
    *,
    code: str | None = None,
    now: datetime.datetime | None = None,
    lock: bool = False,
) -> OfferResult:
    """بهترین (بیشترین) تخفیفِ معتبر برایِ این سبد: کمپین‌هایِ خودکارِ فعال + (اگه
    مشتری کد داده) کمپینِ اون کد. حداکثر *یکی* اعمال می‌شه؛ تخفیف‌ها جمع نمی‌شن.
    اگه تخفیفِ دو کمپین مساوی بود، کمپینِ کددار برنده‌ست، بعد شناسه‌ی کوچک‌تر.

    code باید قبلاً normalize_code شده باشه. lock=True (موقعِ «ثبتِ نهایی»): ردیفِ همه‌ی
    کمپین‌هایِ کاندید به ترتیبِ شناسه با FOR UPDATE قفل می‌شه *قبل* از شمارشِ مصرف، تا
    اعتبارسنجی و ساختِ سفارش‌ها نسبت به چک‌اوتِ هم‌زمانِ مشتریِ دیگه اتمیک باشه.
    """
    now = now or datetime.datetime.now(datetime.timezone.utc)

    autos = await _load_auto_campaigns(session, shop_bot_id, now, lock)
    code_campaign = await get_by_code(session, shop_bot_id, code, lock=lock) if code else None

    code_offer: Offer | None = None
    code_problem: RejectReason | None = None
    code_min_cart: int | None = None
    if code:
        if code_campaign is None:
            code_problem = RejectReason.NOT_FOUND
        else:
            code_offer, code_problem = await _evaluate(session, code_campaign, customer_id, list_total_toman, now)
            if code_problem == RejectReason.MIN_CART:
                code_min_cart = code_campaign.min_cart_total_toman

    offers: list[Offer] = []
    for campaign in autos:
        offer, _problem = await _evaluate(session, campaign, customer_id, list_total_toman, now)
        if offer is not None:
            offers.append(offer)
    if code_offer is not None:
        offers.append(code_offer)

    best: Offer | None = None
    if offers:
        best = max(offers, key=lambda o: (o.discount_toman, 1 if o is code_offer else 0, -o.campaign_id))

    return OfferResult(
        offer=best,
        code_problem=code_problem if code else None,
        code_min_cart_toman=code_min_cart,
        code_outranked=code_offer is not None and best is not code_offer,
        locked=lock and (bool(autos) or code_campaign is not None),
    )


async def create_campaign(
    session: AsyncSession,
    shop_bot_id: int,
    *,
    name: str,
    discount_type: CampaignDiscountType,
    discount_value: int,
    duration_days: int,
    max_discount_toman: int | None = None,
    min_cart_total_toman: int | None = None,
    code: str | None = None,
    total_usage_limit: int | None = None,
    per_customer_limit: int | None = 1,
    now: datetime.datetime | None = None,
) -> Campaign:
    """کمپینِ جدید می‌سازه و *همون لحظه* شروع می‌شه (starts_at = now)؛ هم‌زمان همه‌ی
    قواعدِ اعتبارسنجی رو (دفاعِ دوم؛ ویزارد هم جداگانه چک می‌کنه) اعمال می‌کنه و در
    صورتِ نقض CampaignError با شناسه‌ی ماشینی می‌ده.

    قاعده‌ی ایمنی: برایِ تخفیفِ مبلغ‌ثابت، حداقلِ مبلغِ سبد اجباریه و باید از خودِ
    تخفیف بیشتر باشه (تا سفارشِ رایگان/منفی ساخته نشه)."""
    now = now or datetime.datetime.now(datetime.timezone.utc)

    clean_name = (name or "").strip()
    if not clean_name or len(clean_name) > MAX_NAME_LENGTH:
        raise CampaignError("bad_name")

    if discount_type == CampaignDiscountType.PERCENT:
        if not (1 <= discount_value <= 100):
            raise CampaignError("bad_value")
        if max_discount_toman is not None and not (1 <= max_discount_toman <= MAX_TOMAN_VALUE):
            raise CampaignError("bad_max_discount")
    elif discount_type == CampaignDiscountType.FIXED:
        if not (1 <= discount_value <= MAX_TOMAN_VALUE):
            raise CampaignError("bad_value")
        max_discount_toman = None  # برایِ مبلغ‌ثابت بی‌معنیه
        if min_cart_total_toman is None or min_cart_total_toman <= discount_value:
            raise CampaignError("fixed_needs_min_cart")
    else:
        raise CampaignError("bad_type")

    if min_cart_total_toman is not None and not (1 <= min_cart_total_toman <= MAX_TOMAN_VALUE):
        raise CampaignError("bad_min_cart")
    if not (1 <= duration_days <= MAX_DURATION_DAYS):
        raise CampaignError("bad_duration")
    _validate_limit(total_usage_limit)
    _validate_limit(per_customer_limit)

    normalized_code: str | None = None
    if code is not None:
        normalized_code = normalize_code(code)
        if not is_valid_code(normalized_code):
            raise CampaignError("bad_code")
        existing = await get_by_code(session, shop_bot_id, normalized_code)
        if existing is not None:
            raise CampaignError("code_taken")

    campaign = Campaign(
        shop_bot_id=shop_bot_id,
        name=clean_name,
        code=normalized_code,
        discount_type=discount_type,
        discount_value=discount_value,
        max_discount_toman=max_discount_toman,
        min_cart_total_toman=min_cart_total_toman,
        starts_at=now,
        ends_at=now + datetime.timedelta(days=duration_days),
        total_usage_limit=total_usage_limit,
        per_customer_limit=per_customer_limit,
        is_active=True,
    )
    session.add(campaign)
    await session.flush()
    return campaign


async def set_active(session: AsyncSession, campaign: Campaign, is_active: bool) -> None:
    campaign.is_active = is_active
    await session.flush()


async def delete_if_unused(session: AsyncSession, campaign: Campaign) -> bool:
    """فقط کمپینی که *هیچ* سفارشی (با هر وضعیتی) بهش وصل نیست حذف می‌شه؛ وگرنه False
    (فروشگاه‌دار فقط می‌تونه متوقفش کنه، تا سوابقِ فروش/اکسل سالم بمونه). ردیفِ
    کمپین اول قفل می‌شه تا چک‌اوتِ هم‌زمان وسطِ حذف، سفارشِ تازه‌ای بهش وصل نکنه."""
    await session.execute(select(Campaign.id).where(Campaign.id == campaign.id).with_for_update())
    result = await session.execute(
        select(func.count(OrderConsultation.id)).where(OrderConsultation.campaign_id == campaign.id)
    )
    if int(result.scalar_one()) > 0:
        return False
    await session.delete(campaign)
    await session.flush()
    return True
