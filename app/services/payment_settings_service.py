"""تنظیماتِ روش‌هایِ پرداختِ مشتریِ هر فروشگاه (C5). منطقِ خالص (اعتبارسنجی/ماسک/clamp) جدا از DB."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import ShopBot, ShopPaymentSettings
from app.utils.encryption import decrypt_token, encrypt_token

METHOD_CARD = "card"
METHOD_BALE = "bale"
METHOD_ZARINPAL = "zarinpal"
METHOD_MANUAL = "manual"

DEADLINE_MIN_MINUTES = 5
DEADLINE_MAX_MINUTES = 1440
REVIEW_HOLD_MIN_MINUTES = 60
REVIEW_HOLD_MAX_MINUTES = 4320
MAX_ATTEMPTS_LIMIT = 10

_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def normalize_digits(raw: str) -> str:
    return (raw or "").translate(_DIGITS)


def parse_card_number(raw: str) -> str | None:
    """۱۶ رقم + اعتبارِ Luhn؛ فاصله/خط‌تیره/ارقامِ فارسی پذیرفته. نامعتبر ⇒ None."""
    digits = "".join(ch for ch in normalize_digits(raw) if ch.isdigit())
    if len(digits) != 16 or digits == digits[0] * 16:
        return None
    total = 0
    for index, ch in enumerate(reversed(digits)):
        d = int(ch)
        if index % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return digits if total % 10 == 0 else None


def mask_card(number: str | None) -> str:
    if not number:
        return "—"
    return f"{number[:4]} **** **** {number[-4:]}"


def format_card(number: str) -> str:
    return " ".join(number[i : i + 4] for i in range(0, 16, 4))


# سقفِ سخت (ایمنیِ زمانِ استفاده): حتی با تنظیماتِ ادمین، مهلت از این بازه بیرون نمی‌ره. بازه‌یِ مجازِ فروشگاه‌دار
# (W5 · 2.2) از AdminSettings می‌آد و *موقعِ ثبت* اعمال می‌شه؛ مقدارِ ذخیره‌شده‌یِ قدیمی دست نمی‌خوره.
DEADLINE_HARD_MIN_MINUTES = 1
DEADLINE_HARD_MAX_MINUTES = 10080
REVIEW_HOLD_HARD_MIN_MINUTES = 10
REVIEW_HOLD_HARD_MAX_MINUTES = 43200


def clamp_deadline(minutes: int) -> int:
    return max(DEADLINE_HARD_MIN_MINUTES, min(DEADLINE_HARD_MAX_MINUTES, int(minutes)))


def clamp_review_hold(minutes: int) -> int:
    return max(REVIEW_HOLD_HARD_MIN_MINUTES, min(REVIEW_HOLD_HARD_MAX_MINUTES, int(minutes)))


def deadline_bounds() -> tuple[int, int]:
    """(کف, سقف) مهلتِ پرداخت به دقیقه.

    A5: این بازه دیگر از پنلِ ادمین تنظیم نمی‌شود؛ فقط همین بازه‌یِ ایمنیِ کد وجود دارد و فروشگاه‌دار
    داخلِ آن انتخاب می‌کند. `clamp_deadline` سقفِ سخت‌ترِ زمانِ استفاده است.
    """
    return DEADLINE_MIN_MINUTES, DEADLINE_MAX_MINUTES


def review_hold_bounds() -> tuple[int, int]:
    """(کف, سقف) مهلتِ بررسیِ رسید به دقیقه — مثلِ `deadline_bounds` فقط از کد (A5)."""
    return REVIEW_HOLD_MIN_MINUTES, REVIEW_HOLD_MAX_MINUTES


def parse_positive_int(raw: str, low: int, high: int) -> int | None:
    text = normalize_digits(raw).strip()
    if not text.isascii() or not text.isdecimal() or len(text) > 6:
        return None
    value = int(text)
    return value if low <= value <= high else None


async def get_or_create(session: AsyncSession, shop_bot_id: int) -> ShopPaymentSettings:
    result = await session.execute(select(ShopPaymentSettings).where(ShopPaymentSettings.shop_bot_id == shop_bot_id))
    row = result.scalar_one_or_none()
    if row is None:
        row = ShopPaymentSettings(shop_bot_id=shop_bot_id)
        session.add(row)
        await session.flush()
    return row


async def get(session: AsyncSession, shop_bot_id: int) -> ShopPaymentSettings | None:
    result = await session.execute(select(ShopPaymentSettings).where(ShopPaymentSettings.shop_bot_id == shop_bot_id))
    return result.scalar_one_or_none()


def set_card(row: ShopPaymentSettings, number: str, holder: str | None, bank: str | None) -> None:
    row.card_number_enc = encrypt_token(number)
    row.card_holder_name = (holder or None) and holder.strip()[:80]
    row.bank_name = (bank or None) and bank.strip()[:64]


def get_card_number(row: ShopPaymentSettings | None) -> str | None:
    if row is None or not row.card_number_enc:
        return None
    try:
        return decrypt_token(row.card_number_enc)
    except Exception:  # noqa: BLE001 — کلیدِ رمزِ عوض‌شده/داده‌یِ خراب ⇒ «تنظیم‌نشده»
        return None


def online_methods(
    row: ShopPaymentSettings | None, shop_bot: ShopBot | None = None, *, bale_available: bool | None = None
) -> list[str]:
    """روش‌هایِ **آنلاین/کارتیِ فعال و کامل‌تنظیم** (بدونِ manual). ترتیبِ نمایش: بله‌پی، زرین‌پال، کارت.

    `bale_available` نتیجه‌یِ `bale_credentials_service.shop_status` است (توکنِ ربات + توکنِ درگاهِ فروشگاه
    یا سراسری + کلیدِ ادمین + کلیدِ فروشگاه). هر مصرف‌کننده‌یِ واقعی باید آن را پاس بدهد تا «دکمه‌یِ نمایش‌داده‌شده»
    و «پرداختِ واقعاً ممکن» هرگز از هم جدا نیفتند (B11). بدونِ آن، ملاکِ قدیمیِ فقط‌فروشگاهی استفاده می‌شود."""
    if row is None:
        return []
    methods: list[str] = []
    bale_ok = (
        bool(bale_available)
        if bale_available is not None
        else bool(row.bale_enabled and shop_bot is not None and shop_bot.bale_provider_token)
    )
    if bale_ok:
        methods.append(METHOD_BALE)
    if row.zarinpal_enabled and row.zarinpal_merchant_id_enc:
        methods.append(METHOD_ZARINPAL)
    if row.card_enabled and get_card_number(row):
        methods.append(METHOD_CARD)
    return methods


def checkout_methods(
    row: ShopPaymentSettings | None, shop_bot: ShopBot | None = None, *, bale_available: bool | None = None
) -> list[str]:
    """روش‌هایِ قابلِ انتخاب در چک‌اوت: آنلاین‌ها + «دستی» (اگه روشن). حداقلِ یک روش (fallbackِ دستی)."""
    methods = online_methods(row, shop_bot, bale_available=bale_available)
    if not methods:
        return []  # هیچ روشِ آنلاینی ⇒ جریانِ قدیمی (سفارش مستقیم pending)
    if row is None or row.manual_enabled or not methods:
        methods.append(METHOD_MANUAL)
    return methods


def deadline_minutes(row: ShopPaymentSettings, method: str) -> int:
    if method == METHOD_CARD:
        return clamp_deadline(row.card_deadline_minutes)
    if method == METHOD_BALE:
        return clamp_deadline(row.bale_deadline_minutes)
    if method == METHOD_ZARINPAL:
        return clamp_deadline(row.zarinpal_deadline_minutes)
    return clamp_deadline(60)
