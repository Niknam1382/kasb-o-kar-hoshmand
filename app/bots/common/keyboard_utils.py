"""ابزارهایِ مشترکِ کیبورد (P24).

`reply_markup=None` در aiogram داخلِ payload می‌رود (`{'reply_markup': None}` — اندازه‌گیری‌شده رویِ
aiogram ۳٫۳۰) و تلگرام آن را «بدونِ تغییرِ کیبورد» می‌فهمد، نه «حذفِ کیبورد». پس هیچ‌یک از
هندلرهایی که می‌خواستند دکمه‌هایِ اینلاینِ یکِ پیامِ تمام‌شده را بردارند موفق نبودند: مشتری
می‌توانست «❌ لغوِ سفارش» یا «✅ تایید»ِ یکِ پیامِ کهنه را بزند و ما آن را فقط با توست رد می‌کردیم.
برایِ حذفِ واقعی باید `InlineKeyboardMarkup(inline_keyboard=[])` پاس داده شود.
"""

from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup

NO_INLINE_KEYBOARD = InlineKeyboardMarkup(inline_keyboard=[])
