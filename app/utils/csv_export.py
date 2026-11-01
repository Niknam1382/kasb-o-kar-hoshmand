"""CSVِ امن برایِ خروجی‌هایِ پنل (P21-E · F9).

چرا جدا از اکسل: فایلِ CSV را اکسل/LibreOffice مستقیماً ارزیابی می‌کند؛ اگر مقداری با `=` یا `+`
شروع شود، به‌عنوانِ فرمول اجرا می‌شود (CSV injection). هر مقدارِ متنیِ کاربرپسند از این
عبور می‌کند ⇒ پیشوندِ `'` جلویِ ارزیابی را می‌گیرد و متن در همان‌حین قابلِ خواندن می‌ماند.
BOM هم برایِ فارسیِ راست‌به‌چپ در اکسل لازم است، وگرنه متنِ فارسی بهم‌ریخته نمایش داده می‌شود.
"""

from __future__ import annotations

import csv
import io

_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
_BOM = "\ufeff"


def safe_cell(value: object) -> str:
    """هر مقدار را به رشتهٔ «غیرفرمول» تبدیل می‌کند."""
    if value is None:
        return ""
    text = str(value)
    if text and text[0] in _FORMULA_PREFIXES:
        return "'" + text
    return text


def build_csv(headers: list[str], rows: list[list[object]]) -> bytes:
    buffer = io.StringIO(initial_value="", newline="")
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow([safe_cell(header) for header in headers])
    for row in rows:
        writer.writerow([safe_cell(cell) for cell in row])
    return (_BOM + buffer.getvalue()).encode("utf-8")
