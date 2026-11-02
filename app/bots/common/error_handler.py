"""هندلرِ سراسریِ خطایِ هندلرها (P24 · «دکمه‌ای که هیچ کاری نمی‌کند»).

چند ده هندلر در این پروژه `int(callback.data.split(":")[1])` می‌کنند و چندتایشان کلیدِ state را
بدونِ بررسی می‌خوانند. اگر کاربر رویِ کیبوردِ کهنه بزند یا callback_data دستکاری‌شده برسد،
`ValueError`/`KeyError` *پیش ازِ* `callback.answer()` رخ می‌دهد؛ نتیجه دقیقاً همان چیزی است که
کاربر گزارش کرد: دکمه‌ای که «هیچ کاری نمی‌کند» (تلگرام هیچ جوابی نمی‌گیرد و اسپینر می‌چرخد).

به‌جایِ بیست‌وچند ویرایشِ موردی، این هندلر رویِ روترِ اصلی ثبت می‌شود تا خطایِ هر هندلرِ
فرزند هم: الف) کامل لاگ شود (با traceback، برایِ عیب‌یابیِ واقعی)، ب) حداقل یکِ بازخوردِ دیدنی
به کاربر بدهد، ج) باعثِ سقوطِ حلقهٔ polling نشود.

عمداً پیام، فنی نیست: شمارهٔ خط، نامِ کلاسِ استثنا یا هیچ مقدارِ داخلی به کاربر نشان داده نمی‌شود
(قراردادِ پروژه: جزئیاتِ فنی به لاگ، راهنمایِ عملی به کاربر).
"""

from __future__ import annotations

import logging

from aiogram.types import CallbackQuery, ErrorEvent, Message

logger = logging.getLogger(__name__)

CALLBACK_FAILED_TOAST = "⚠️ این دکمه کامل نشد. چند لحظه بعد دوباره امتحان کن؛ اگر تکرار شد به پشتیبانی بگو."
MESSAGE_FAILED_REPLY = "⚠️ درخواستِ این لحظه کامل نشد. دوباره امتحان کن؛ چیزی ذخیره یا پرداخت نشده است."


async def on_handler_error(event: ErrorEvent) -> bool:
    """True ⇒ خطا مدیریت شد. هر شکستِ خودِ این هندلر هم فقط لاگ می‌شود (نباید polling را بیندازد)."""
    exception = getattr(event, "exception", None)
    logger.error(
        "هندلرِ آپدیتِ %s با خطا مواجه شد: %s",
        getattr(event.update, "update_id", "?"),
        type(exception).__name__ if exception is not None else "?",
        exc_info=exception,
    )
    update = event.update
    callback = update.callback_query
    if isinstance(callback, CallbackQuery):
        try:
            # ممکن است هندلر قبلِ خطا уже جواب داده باشد؛ آن خطا هم نادیده گرفته می‌شود.
            await callback.answer(CALLBACK_FAILED_TOAST, show_alert=True)
        except Exception:  # noqa: BLE001 - بازخوردِ دوم هرگز نباید خودِ مسیر را ببیند
            logger.debug("جوابِ دومِ callback ممکن نشد (احتمالاً قبلاً پاسخ داده شده).")
        return True
    message = update.message
    if isinstance(message, Message):
        try:
            await message.answer(MESSAGE_FAILED_REPLY)
        except Exception:  # noqa: BLE001
            logger.debug("پیامِ خطا به کاربر نرسید.")
        return True
    return False
