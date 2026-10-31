"""«⬅️ برگشت / ⏭ رد کردن / ❌ انصراف»ِ مشترکِ ویزاردها (قاعده‌یِ ۹؛ W5/1.2).

برچسب‌ها codepoint-دقیق با ثابت‌هایِ ثبت‌نام (`main_bot.texts.REG_*`) یکی‌اند و فقط اینجا تعریف می‌شن.
هیچ‌چیزِ aiogram-محور به‌جز سازنده‌یِ دکمه نیست؛ callback_dataها را فراخوان تعیین می‌کنه (≤۶۴ بایت)."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

BTN_BACK = "⬅️ برگشت"
BTN_SKIP = "⏭ رد کردن"
BTN_CANCEL = "❌ انصراف"


def nav_row(
    *,
    back_cb: str | None = None,
    skip_cb: str | None = None,
    cancel_cb: str | None = None,
) -> list[InlineKeyboardButton]:
    """یک ردیفِ ناوبری؛ هر دکمه فقط وقتی callback داده شده باشه می‌آید (ترتیب: برگشت، رد کردن، انصراف)."""
    row: list[InlineKeyboardButton] = []
    if back_cb:
        row.append(InlineKeyboardButton(text=BTN_BACK, callback_data=back_cb))
    if skip_cb:
        row.append(InlineKeyboardButton(text=BTN_SKIP, callback_data=skip_cb))
    if cancel_cb:
        row.append(InlineKeyboardButton(text=BTN_CANCEL, callback_data=cancel_cb))
    return row


def with_nav(
    rows: list[list[InlineKeyboardButton]] | None = None,
    *,
    back_cb: str | None = None,
    skip_cb: str | None = None,
    cancel_cb: str | None = None,
) -> InlineKeyboardMarkup:
    """ردیف‌هایِ محتوا + ردیفِ ناوبریِ استاندارد."""
    all_rows = list(rows or [])
    nav = nav_row(back_cb=back_cb, skip_cb=skip_cb, cancel_cb=cancel_cb)
    if nav:
        all_rows.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=all_rows)
