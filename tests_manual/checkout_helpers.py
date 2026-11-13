"""helperِ مشترکِ تست‌ها برایِ چک‌اوتِ مرحله‌ایِ سبد (W5 · C3).

جریانِ چک‌اوت از «دو سوالِ پیش‌فرض» به مرحله‌هایِ ساخت‌یافته تغییر کرد (تغییرِ عمدی؛ PROGRESS بخش ۵). تست‌هایی که
خودِ چک‌اوت موضوعشون نیست فقط با `run_checkout` تا پیش‌نمایش پیش می‌رن. `tap(data)` و `say(text)` دو coroutine-callableِ
تست‌ان (هر تست پیاده‌سازیِ خودش از feed_update رو داره)."""

from __future__ import annotations

from typing import Awaitable, Callable, Sequence

DEFAULT_NAME = "علی رضایی"
DEFAULT_PHONE = "09120000000"
DEFAULT_PROVINCE = "تهران"
DEFAULT_CITY = "تهران"
DEFAULT_ADDRESS = "خیابانِ آزادی، کوچه‌یِ دوم، پلاکِ ده"


async def run_checkout(
    tap: Callable[[str], Awaitable[None]],
    say: Callable[[str], Awaitable[None]],
    *,
    physical: bool = True,
    name: str = DEFAULT_NAME,
    phone: str = DEFAULT_PHONE,
    saved_address_id: int | None = None,
    province: str = DEFAULT_PROVINCE,
    city: str = DEFAULT_CITY,
    region_steps: bool = False,
    address: str = DEFAULT_ADDRESS,
    postal: str | None = None,
    ship_method_id: int | None = None,
    answers: Sequence[str] = (),
    note: str | None = None,
    start: bool = True,
    has_saved_addresses: bool = False,
) -> None:
    """از «🧾 نهایی‌کردن» تا پیش‌نمایشِ نهایی. physical=False ⇒ سبدِ فقط‌دیجیتال (بدونِ آدرس/ارسال).
    saved_address_id ⇒ آدرس از دفترچه؛ وگرنه آدرسِ تازه (پ۶۸: با region_steps=True استان ← شهر ← آدرس ← کدپستی/رد،
    و با پیش‌فرضِ جدیدِ محصول فقط آدرس ← کدپستی/رد).
    ship_method_id همیشه وقتی لازمه که فروشگاه حتی یک روشِ ارسالِ فعال داره (B8: انتخابِ خودکار حذف شد).
    از P22 اگر None باشد و سبد فیزیکی باشد، «هماهنگیِ ارسال» (ck_ship:0) انتخاب می‌شود — گام رد نمی‌شود.
    has_saved_addresses=True وقتی این مشتری قبلاً آدرسی ذخیره کرده (چک‌اوتِ دوم به بعد): فهرستِ آدرس‌ها نشون داده
    می‌شه و «➕ آدرسِ جدید» باید زده بشه."""
    if start:
        await tap("cart_checkout_start")
    await say(name)
    await say(phone)
    if physical:
        if saved_address_id is not None:
            await tap(f"ck_addr_sel:{saved_address_id}")
        else:
            if has_saved_addresses:
                await tap("ck_addr_new")
            if region_steps:
                await say(province)
                await say(city)
            await say(address)
            if postal is None:
                await tap("ck_skip")
            else:
                await say(postal)
        if ship_method_id is not None:
            await tap(f"ck_ship:{ship_method_id}")
        else:
            # P22 (مشکلِ ۵): گامِ ارسال همیشه پرسیده می‌شود؛ بدونِ روشِ فعال ⇒ «هماهنگیِ ارسال» (شناسهٔ ۰)
            await tap("ck_ship:0")
    for answer in answers:
        await say(answer)
    if note is None:
        await tap("ck_skip")
    else:
        await say(note)
