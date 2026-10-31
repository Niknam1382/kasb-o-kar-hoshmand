from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class CheckoutStates(StatesGroup):
    """فازِ ۳ — چک‌اوتِ سبدِ خرید: سوال‌هایِ فروشگاه‌دار-تعریف‌شده (یا پیش‌فرض:
    شماره/آدرس) رو یکی‌یکی می‌پرسه، بعد یه پیامِ تاییدِ نهایی نشون می‌ده."""

    answering_questions = State()
    confirming = State()
    # کمپین/کدِ تخفیف: مشتری از روی پیش‌نمایشِ نهایی دکمه‌ی «🎟 کد تخفیف دارم» رو می‌زنه
    # و کد رو تایپ می‌کنه؛ بعدش دوباره به confirming برمی‌گرده.
    entering_discount_code = State()

    # W5 · C3 — چک‌اوتِ مرحله‌ای (قبلِ سوال‌هایِ فروشگاه‌دار)
    entering_name = State()
    entering_phone = State()
    choosing_address = State()
    managing_addresses = State()
    entering_province = State()
    entering_city = State()
    entering_address = State()
    entering_postal = State()
    choosing_shipping = State()
    entering_note = State()


class PaymentStates(StatesGroup):
    """کارت‌به‌کارت (W3 · C6): مشتری منتظرِ ارسالِ رسید (عکس/فایلِ تصویری/شماره‌پیگیری)."""

    waiting_receipt = State()

