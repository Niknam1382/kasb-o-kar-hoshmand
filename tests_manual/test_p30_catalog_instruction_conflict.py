"""
تست: جملهٔ «دستورالعملِ AIِ» فروشگاه نباید محصولاتِ واقعی را از چشمِ ربات پاک کند.

ریشه‌یِ باگ (۱۴۰۵-۰۸-۱۲): فروشگاه ۲ دو محصولِ دستی («مداد»، «مداد طلا») و ده محصولِ ایمپورت‌شده
با اکسل داشت و همه `is_active` با موجودیِ سالم بودند؛ ولی در `ai_instructions` نوشته شده بود
«تو فقط مداد فروشی…». آن جمله *جایِ* دستورالعملِ پیش‌فرض را می‌گرفت، پس ربات در پاسخِ
«چه محصولاتی داری» ده محصولِ اکسل را انکار می‌کرد.

اجرا: python3 tests_manual/test_p30_catalog_instruction_conflict.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from app.database.models import Product, ShopBot, TenantMode  # noqa: E402
from app.services import ai_context  # noqa: E402

OWNER_ONLY_PENCILS = "تو فقط مداد فروشی و کم حرف بزن و فقط محصولات موجود رو بفروش"

MANUAL = ("مداد", "مداد طلا")
IMPORTED = (
    "کابل شارژ تایپ‌سی ۱ متری",
    "کابل شارژ آیفون لایتنینگ",
    "گلس شیشه‌ای محافظ صفحه",
    "قاب سیلیکونی ضدضربه",
    "پاوربانک ۱۰۰۰۰ میلی‌آمپر",
    "هندزفری بلوتوثی بی‌سیم",
    "شارژر دیواری ۲۰ وات",
    "هولدر موبایل داخل خودرو",
    "رم میکرو اس‌دی ۶۴ گیگابایت",
    "پایه نگهدارنده رومیزی موبایل",
)


def _shop(mode=TenantMode.SALES, instructions=None) -> ShopBot:
    return ShopBot(tenant_mode=mode, ai_instructions=instructions)


def _catalog() -> list[Product]:
    rows = [Product(name=n, price_toman=1000, kind="physical", stock_quantity=53) for n in MANUAL]
    rows += [Product(name=n, price_toman=185000, kind="physical", stock_quantity=40) for n in IMPORTED]
    return rows


def test_custom_instruction_keeps_default_instructions() -> None:
    prompt = ai_context.build_system_prompt(_shop(instructions=OWNER_ONLY_PENCILS), _catalog())
    assert "دستیار فروش" in prompt, "دستورالعملِ پیش‌فرض نباید با جملهٔ فروشگاه پاک شود"
    assert OWNER_ONLY_PENCILS in prompt, "جملهٔ فروشگاه باید در پرامپت بماند"
    print("✅ test_custom_instruction_keeps_default_instructions PASSED")


def test_all_twelve_products_reach_the_prompt() -> None:
    prompt = ai_context.build_system_prompt(_shop(instructions=OWNER_ONLY_PENCILS), _catalog())
    missing = [name for name in (*MANUAL, *IMPORTED) if name not in prompt]
    assert not missing, f"این محصولات به پرامپت نرسیدند: {missing}"
    print("✅ test_all_twelve_products_reach_the_prompt PASSED")


def test_catalog_is_declared_complete() -> None:
    prompt = ai_context.build_system_prompt(_shop(instructions=OWNER_ONLY_PENCILS), _catalog())
    assert "تمامِ محصولاتِ ثبت‌شده" in prompt, "فهرست باید صریح بگوید این تمامِ محصولات است"
    assert "«نداریم» نگو" in prompt
    print("✅ test_catalog_is_declared_complete PASSED")


def test_prompt_without_custom_instruction_is_unchanged() -> None:
    prompt = ai_context.build_system_prompt(_shop(), _catalog())
    blocks = prompt.split("\n\n")
    instruction_block = next(b for b in blocks if "دستیار فروش" in b)
    assert instruction_block == ai_context.DEFAULT_SALES_INSTRUCTIONS, "بدونِ جملهٔ فروشگاه، متنِ دستورالعمل باید عیناً مثلِ قبل باشد"
    assert prompt.count(ai_context.DEFAULT_SALES_INSTRUCTIONS) == 1, "دستورالعملِ پیش‌فرض نباید دوبار چاپ شود"
    print("✅ test_prompt_without_custom_instruction_is_unchanged PASSED")


def test_consultation_mode_keeps_consultation_framing() -> None:
    prompt = ai_context.build_system_prompt(_shop(mode=TenantMode.CONSULTATION, instructions="فقط وقتِ جلسه بده"), [])
    assert "دستیارِ مشاوره" in prompt, "در مودِ مشاوره هم جملهٔ فروشگاه نباید چارچوبِ پیش‌فرض را پاک کند"
    assert "فقط وقتِ جلسه بده" in prompt
    print("✅ test_consultation_mode_keeps_consultation_framing PASSED")


def test_out_of_stock_marker_survives() -> None:
    rows = [Product(name="کالایِ تمام‌شده", price_toman=5000, kind="physical", stock_quantity=0)]
    prompt = ai_context.build_system_prompt(_shop(), rows)
    assert "[ناموجود - فعلاً پیشنهادش نده]" in prompt, "علامتِ ناموجود نباید از دست برود"
    print("✅ test_out_of_stock_marker_survives PASSED")


async def main() -> None:
    test_custom_instruction_keeps_default_instructions()
    test_all_twelve_products_reach_the_prompt()
    test_catalog_is_declared_complete()
    test_prompt_without_custom_instruction_is_unchanged()
    test_consultation_mode_keeps_consultation_framing()
    test_out_of_stock_marker_survives()


if __name__ == "__main__":
    asyncio.run(main())
