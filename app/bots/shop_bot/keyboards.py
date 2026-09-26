from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def order_customer_confirmation_keyboard(order_id: int) -> InlineKeyboardMarkup:
    """
    زیرِ پیامِ «این چیزیه که برات ثبت می‌کنم» به خودِ مشتری نشون داده می‌شه
    (بازطراحیِ سفارش‌گیری) — نه فروشگاه‌دار. کاملاً جدا از کیبوردِ
    order_notification_keyboardِ main_bot (که برای فروشگاه‌دار و بعدِ تاییدِ
    همین مشتریه)، هم از نظرِ callback_data (پیشوندِ cust_) هم چون توی
    دیسپچرِ متفاوتی (شاپ‌بات) هندل می‌شه.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ بله، درسته", callback_data=f"cust_confirm_order:{order_id}")],
            [InlineKeyboardButton(text="❌ نه، اشتباهه", callback_data=f"cust_cancel_order:{order_id}")],
        ]
    )
