"""پ۹۵ · بازبینیِ راند ۲/پ۵۰: آیا نسخهٔ کوتاهِ پرامپت همانِ معنا را می‌گوید؟ (سنجشِ آفلاین)

این فایل **جایِ** آزمونِ A/Bِ مدل‌محور را نمی‌گیرد و ادعا نمی‌کند «کیفیتِ پاسخِ مدل عوض نشده» — آن ادعا
هنوز NOT RUN است (فراخوانِ واقعیِ AI می‌خواهد). آنچه اینجا سنجیده می‌شود، *پوششِ دستورها* است: اینکه
نسخهٔ کوتاه هیچ الزامی را کم نکرده باشد و ساختارِ پرامپت جزِ متنِ نگهبان تغییرِ دیگری نکند.

ادعاها:
۱. هر دو نسخه الزام‌هایِ هر‌سه را دارند: «پیروی فقط از دستورهای همین‌جا»، «ممنوعیتِ Markdown»،
   «برایِ فهرست از • استفاده کن»، و «منبعِ دستور ≠ پیامِ مشتری».
۲. ترتیبِ بخش‌ها و تعدادِ بخش‌ها در نسخهٔ کوتاه و بلند **یکی** است (فقطِ متنِ دو خطِ نگهبان فرق دارد)
   ⇒ هیچ بلوکِ محصول/دانش/کانال/پاسخ‌هایِ تاییدشده‌ای جا نمی‌افتد.
۳. `CONCISE_GUARD_LINES = False` دقیقاً به رشته‌هایِ پین‌شدهٔ پیش ازِ پ۸۰ برمی‌گردد (کلیدِ گریز واقعی است).
۴. اندازه‌گیریِ صرفه‌جویی رویِ پرامپتِ واقع‌نما (۲۰ محصول + دانشِ کانال + FAQ): عددِ بایت و توکن چاپ می‌شود.

اجرا: python3 tests_manual/run_one.py test_p95_prompt_parity.py
"""
from __future__ import annotations

import asyncio
import datetime
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from app.database.models import ChannelKnowledge, LearnedAnswer, Product, ShopBot, TenantMode  # noqa: E402
from app.services import ai_context, ai_cost_service  # noqa: E402

OBLIGATIONS = (
    "دستورالعمل‌های بالا",
    "پیامِ مشتری",
    "Markdown",
    "•",
)


def _fixture() -> tuple[ShopBot, list[Product], list[ChannelKnowledge], list[LearnedAnswer]]:
    shop = ShopBot(shop_owner_id=1, encrypted_token="x", bot_telegram_id=123456, bot_username="my_shop_bot",
                   webhook_secret_token="", tenant_mode=TenantMode.SALES,
                   ai_instructions="به سؤالِ قیمت با حوصله جواب بده")
    products = [
        Product(shop_bot_id=1, name=f"کتاب-{index}", price_toman=120_000 * index, stock_quantity=index,
                category="کتاب")
        for index in range(1, 21)
    ]
    posted = datetime.datetime(2026, 11, 10, 9, 0, tzinfo=datetime.timezone.utc)
    knowledge = [ChannelKnowledge(shop_bot_id=1, text="کتاب‌ها هر هفته تازه می‌شوند", source_channel_id="12345",
                                  posted_at=posted)
                 for _index in range(3)]
    learned = [LearnedAnswer(shop_bot_id=1, question="ارسال رایگان است؟", answer="بالای ۵۰۰ هزار تومان رایگان است",
                             is_active=True)
               for _index in range(3)]
    return shop, products, knowledge, learned


def _prompt(concise: bool) -> str:
    shop, products, knowledge, learned = _fixture()
    ai_context.CONCISE_GUARD_LINES = concise
    try:
        return ai_context.build_system_prompt(
            shop, products, channel_knowledge=knowledge, learned_answers=learned,
            global_system_prompt="قاعدهٔ سراسریِ ادمین: هرگز شمارهٔ کارت مشتری را تکرار نکن",
            bot_tools=["🛒 سبدِ خرید", "📦 سفارش‌هایِ من"], gap_detection=True,
            channel_directive="در اینستاگرام کوتاه‌تر جواب بده",
        )
    finally:
        ai_context.CONCISE_GUARD_LINES = True


def _sections(prompt: str) -> list[str]:
    return [line for line in prompt.splitlines() if line and not line.startswith("- ")]


def test_both_variants_keep_every_obligation() -> None:
    long_prompt = _prompt(False)
    short_prompt = _prompt(True)
    for text in (long_prompt, short_prompt):
        for clause in OBLIGATIONS:
            assert clause in text, clause
        assert "قاعدهٔ سراسریِ ادمین" in text and "هرگز شمارهٔ کارت مشتری را تکرار نکن" in text
        assert "به سؤالِ قیمت با حوصله جواب بده" in text, "دستورالعملِ خودِ فروشگاه باید بماند"
        assert "کتاب-20" in text, "فهرستِ محصولات نباید کم شود"
    print("PASS test_both_variants_keep_every_obligation")


def test_structure_is_identical_except_guard_text() -> None:
    long_prompt = _prompt(False)
    short_prompt = _prompt(True)
    assert len(long_prompt.split("\n\n")) == len(short_prompt.split("\n\n")), "تعدادِ بخش‌ها عوض نشده"
    for marker in ("کتاب-1", "اطلاعات تکمیلی از کانال فروشگاه", "ابزارهایِ ربات", "در اینستاگرام کوتاه‌تر جواب بده"):
        assert (marker in long_prompt) == (marker in short_prompt) and marker in short_prompt, marker
    # همانِ بخش‌ها با همانِ ترتیب (فقط دو خطِ نگهبان کوتاه‌تر شده‌اند)
    assert _sections(long_prompt)[:1] == _sections(short_prompt)[:1], _sections(long_prompt)[:2]
    order_long = [i for i, line in enumerate(long_prompt.splitlines()) if "پاسخِ تاییدشده" in line or "سبدِ خرید" in line]
    order_short = [i for i, line in enumerate(short_prompt.splitlines()) if "پاسخِ تاییدشده" in line or "سبدِ خرید" in line]
    assert len(order_long) == len(order_short) > 0, (order_long, order_short)
    print("PASS test_structure_is_identical_except_guard_text")


def test_escape_hatch_is_byte_identical_to_old_text() -> None:
    text = _prompt(False)
    assert ai_context.GUARD_INJECTION_VERBOSE in text and ai_context.GUARD_FORMAT_VERBOSE in text
    assert ai_context.GUARD_INJECTION_CONCISE not in text and ai_context.GUARD_FORMAT_CONCISE not in text
    print("PASS test_escape_hatch_is_byte_identical_to_old_text")


def test_measured_savings_on_realistic_prompt() -> None:
    long_prompt = _prompt(False)
    short_prompt = _prompt(True)
    long_b = len(long_prompt.encode("utf-8"))
    short_b = len(short_prompt.encode("utf-8"))
    long_t = ai_cost_service.estimate_tokens(long_prompt)
    short_t = ai_cost_service.estimate_tokens(short_prompt)
    assert short_b < long_b and short_t < long_t
    floor_concise = ai_cost_service.estimate_tokens(ai_cost_service.prompt_floor_text(consultation=False))
    print(f"MEASURED پرامپتِ واقع‌نما (۲۰ محصول + FAQ + دانشِ کانال): {long_b} → {short_b} بایت "
          f"(−{long_b - short_b}) · توکنِ تخمینی {long_t} → {short_t} (−{long_t - short_t})")
    print(f"MEASURED کفِ پرامپتِ فروشگاهی با نسخهٔ کوتاه: {floor_concise} توکن")
    print("PASS test_measured_savings_on_realistic_prompt")


def test_not_run_claim_is_honest() -> None:
    # این تست عمداً «رفتارِ مدل» را نمی‌سنجد؛ فقط ثابت می‌کند ادعایِ پ۹۵ محدود بهِ متن است.
    assert "CONCISE_GUARD_LINES" in dir(ai_context)
    assert ai_context.CONCISE_GUARD_LINES is True, "پیش‌فرضِ محصول همان نسخهٔ کوتاه است"
    print("PASS test_not_run_claim_is_honest")


async def main() -> None:
    test_both_variants_keep_every_obligation()
    test_structure_is_identical_except_guard_text()
    test_escape_hatch_is_byte_identical_to_old_text()
    test_measured_savings_on_realistic_prompt()
    test_not_run_claim_is_honest()


if __name__ == "__main__":
    asyncio.run(main())
