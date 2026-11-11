r"""پ۵۶ · مواردِ ۲۷ و ۴۱: سازوکارِ مشترکِ «جست‌وجو در فهرست‌هایِ مدیریتی».

چرا این فایل جدا است: همِ پنلِ ادمین (فهرستِ فروشگاه‌دارها) و همِ پنلِ فروشگاه‌دار (فهرستِ
مشتری‌ها) دقیقاً یکِ مشکلِ یکی دارند — پیدا‌کردنِ یکِ نفر از رویِ نام، نام‌کاربری، تلفن یا
شناسهٔ تلگرام. اگر منطقِ نرمال‌سازی و فرار‌دادنِ کاراکترهایِ LIKE دو بار نوشته شود، یکِ روز
فقط یکی از دو صفحه درست رفتار می‌کند.

سه نکتهٔ امنیتی/عملکردی که این فایل قاعده‌اش است:
۱. ورودیِ کاربر واردِ الگویِ LIKE می‌شود ⇒ `%` و `_` و `\` فرار می‌شوند، وگرنهٔ «%» می‌توانست
   کلِ جدول را برگرداند. هیچ مقدارِ کاربری داخلِ SQL نخوابیده نمی‌شود (همه bind param).
۲. نرمال‌سازیِ دوطرفه: ارقامِ فارسی/عربی به لاتین، ي/ك/ة به شکلِ فارسی، کشیده و ZWNJ حذف،
   فاصله‌هایِ اضافی یکی، حروفِ بزرگ کوچک. برایِ نامِ کامل، یکِ الگویِ «بدونِ فاصله» هم زده
   می‌شود تا «علی رضایی»، «علی‌رضایی» و «علی رضایی» یکِ نتیجه بدهند.
۳. این سازوکار *فیلتر* است، نه دسترسی: فراخوان باید همان `WHERE` مالکیت/دامنهٔ خودش را به
   شرایطِ این تابع اضافه کند. اینجا هیچ فرضی از «چه کسی اجازهٔ دیدن دارد» نمی‌شود.
"""

from __future__ import annotations

import re

from sqlalchemy import ColumnElement, func, or_

from app.utils.validators import normalize_iran_phone

_DIGIT_TABLE = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_CHAR_TABLE = str.maketrans({"ي": "ی", "ى": "ی", "ك": "ک", "ة": "ه", "ـ": "", "‌": ""})
_SPACES_RE = re.compile(r"\s+")
_MAX_TERM_CHARS = 64


def normalize_term(raw: str | None) -> str:
    """عبارتِ جست‌وجو را شکلِ قابلِ مقایسه می‌دهد؛ بیش از ۶۴ نویسه بریده می‌شود
    (جست‌وجویِ بی‌نهایه معنا ندارد و الگویِ LIKE را بیهوده بلند می‌کند)."""
    folded = (raw or "").strip().translate(_DIGIT_TABLE).translate(_CHAR_TABLE)
    folded = _SPACES_RE.sub(" ", folded).strip().casefold()
    return folded[:_MAX_TERM_CHARS]


def _like(term: str) -> str:
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _digits(term: str) -> str:
    return "".join(char for char in term if char.isdigit())


def filter_conditions(
    term: str | None,
    *,
    name_columns: tuple[ColumnElement, ...] = (),
    username_column: ColumnElement | None = None,
    phone_column: ColumnElement | None = None,
    telegram_column: ColumnElement | None = None,
) -> list[ColumnElement]:
    """شروطِ `OR`شده برایِ یکِ عبارتِ جست‌وجو؛ فهرستِ خالی یعنی «چیزی پیدا نشود» (نه «همه»).

    اگر عبارت فقط رقم باشد و به شکلِ شمارهٔ موبایلِ ایرانی بخورد، هم `phone` و هم `telegram_id`
    امتحان می‌شوند؛ اگر فقط رقم باشد ولی شکلِ تلفن نباشد، `telegram_id` دقیق تطبیق داده می‌شود.
    """
    normalized = normalize_term(term)
    if not normalized:
        return [or_(False)]
    pattern = _like(normalized)
    conditions = [column.ilike(pattern, escape="\\") for column in name_columns if column is not None]
    if username_column is not None:
        conditions.append(username_column.ilike(pattern, escape="\\"))

    compact = normalized.replace(" ", "")
    if compact and len(name_columns) > 1:
        # نامِ کامل در دو ستون جدا است، پس «علی محمدی» هیچ‌کدام از ستون‌ها به‌تنهایی نیست.
        # هر دو ترتیب امتحان می‌شود تا «علی محمدی» و «محمدی علی» یکی باشند. این شرط عمداً
        # «فقط وقتی فاصله دارد» نیست: عبارتِ با ZWNJ («علی‌محمدی») بعد از حذفِ ZWNJ فاصله ندارد
        # ولی همان نامِ دوکلمه‌ای است و باید پیدا شود.
        for order in (name_columns, tuple(reversed(name_columns))):
            joined = func.replace(func.concat(*[func.coalesce(column, "") for column in order]), " ", "")
            conditions.append(joined.ilike(_like(compact), escape="\\"))

    numeric = _digits(normalized)
    bare = normalized.replace(" ", "").lstrip("+")
    if numeric and numeric == bare:
        # فقط رقم: هم شناسهٔ تلگرام و هم شمارهٔ موبایل معنی دارند؛ هر دو امتحان می‌شوند.
        # «+98…», «۰۹۱۲…», «912…» و «0098…» همه با normalize_iran_phone به شکلِ ذخیره‌شده می‌رسند.
        if telegram_column is not None and 1 <= len(numeric) <= 15:
            conditions.append(telegram_column == int(numeric))
        if phone_column is not None:
            canonical = normalize_iran_phone(numeric)
            if canonical is not None:
                conditions.append(phone_column == canonical)
    return [or_(*conditions)] if conditions else [or_(False)]


def require_term(term: str | None) -> str:
    """نرمال‌سازی + ردِ عبارتِ خالی؛ هندلرها با این، «جست‌وجویِ بی‌نهایه» را از همان اول می‌بندند."""
    normalized = normalize_term(term)
    if not normalized:
        raise ValueError("عبارتِ جست‌وجو خالی است")
    return normalized
