"""
تست: پ۱۰۸ — هیچ پرامپتِ پیش‌فرضی نباید دکمه‌ای را نام ببرد که در ربات وجود ندارد.

چرا این تست هست: مالکِ محصول در رباتِ مشاوره‌ای دید که هوش مصنوعی گفت «از دکمهٔ مشاوره استفاده کن» —
در حالی که دکمه‌ای وجود ندارد. علت در `prompt_defaults` بود: پرامپتِ پیش‌فرضِ مشاوره «💬 درخواستِ
مشاوره» (که هرگز ساخته نشد) و «🗂 خدمات و بسته‌ها» (که پ۲۴ از منویِ مشاوره برداشت) را معرفی می‌کرد.
قاعدهٔ تست: هر نقل‌قولِ برچسب‌دارِ *دکمه‌مانند* (چیزی که ایموجی دارد) باید در فهرستِ دکمه‌هایِ
واقعیِ همان مود باشد؛ و هر دکمه‌ای که واقعاً در کیبوردِ مشتری هست باید در «ابزارهایِ ربات» دیده شود.

اجرا: python3 tests_manual/test_p108_prompt_dead_buttons.py
"""
from __future__ import annotations

import re
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from app.bots.shop_bot import keyboards, texts  # noqa: E402
from app.database.models import TenantMode  # noqa: E402
from app.services import ai_context, prompt_defaults  # noqa: E402

# دکمه‌هایی که بیرونِ منو و «به‌موقع» می‌آیند (پس در پرامپت مجازند): کارتی و موقعیتی.
CONTEXTUAL_BUTTONS = {
    "➕ افزودن به سبد",
    "🛒 دیدنِ سبدِ خرید",
    "📎 ارسالِ رسید",
}
MENU_BUTTONS = {texts.BTN_PRODUCTS, texts.BTN_CART, texts.BTN_SERVICES, texts.BTN_SUPPORT, texts.BTN_MY_ORDERS}


def _has_pictogram(value: str) -> bool:
    return any(0x2190 <= ord(ch) <= 0x2BFF or 0x1F000 <= ord(ch) <= 0x1FAFF for ch in value)


def _button_names(prompt: str) -> list[str]:
    """نقل‌قول‌هایِ «…» که شکلِ دکمه دارند (ایموجی دارند) — نامِ ساده‌یِ فارسی حساب نمی‌شود."""
    return [span for span in re.findall(r"«([^»\n]+)»", prompt) if _has_pictogram(span)]


def test_default_prompts_name_only_existing_buttons() -> None:
    known = MENU_BUTTONS | CONTEXTUAL_BUTTONS
    for mode, prompt in (
        ("sales", prompt_defaults.DEFAULT_GLOBAL_PROMPT_SALES),
        ("consultation", prompt_defaults.DEFAULT_GLOBAL_PROMPT_CONSULTATION),
    ):
        dead = [name for name in _button_names(prompt) if name not in known]
        assert not dead, f"دکمهٔ مرده در پرامپتِ {mode}: {dead}"
    consult = prompt_defaults.DEFAULT_GLOBAL_PROMPT_CONSULTATION
    assert texts.BTN_SERVICES not in consult, "«خدمات و بسته‌ها» در مودِ مشاوره دکمهٔ مرده است (P24)"
    assert "درخواستِ مشاوره»" not in consult, "دکمهٔ «درخواستِ مشاوره» هیچ‌وقت ساخته نشده"
    assert "«ابزارهایِ ربات»" in consult, "مرجعِ درست: همان فهرستِ پویا، نه نامِ ثابتِ دکمه"
    print("PASS test_default_prompts_name_only_existing_buttons")


def test_tools_match_the_real_customer_keyboard() -> None:
    for support_enabled in (False, True):
        menu = {
            button.text
            for row in keyboards.customer_main_keyboard(TenantMode.SALES, support_enabled).keyboard
            for button in row
        }
        listed = {
            match.group(1)
            for line in prompt_defaults.build_bot_tools(TenantMode.SALES, support_enabled, texts)
            for match in [re.match(r"«(.+)»", line)]
            if match
        }
        assert menu == listed, f"منو و ابزارها فرق دارند (پشتیبانی={support_enabled}): {menu ^ listed}"
    assert prompt_defaults.build_bot_tools(TenantMode.CONSULTATION, False, texts) == []
    assert [texts.BTN_SUPPORT] == [
        match.group(1) for line in prompt_defaults.build_bot_tools(TenantMode.CONSULTATION, True, texts)
        for match in [re.match(r"«(.+)»", line)] if match
    ], "تنها ابزارِ مودِ مشاوره پشتیبانی است"
    print("PASS test_tools_match_the_real_customer_keyboard")


def test_missing_tools_are_declared_not_silenced() -> None:
    shop_bot = TenantMode.SALES  # فقط برایِ پر کردنِ آرگومان؛ build_system_prompt به tenant_mode نگاه می‌کند
    baseline = ai_context.build_system_prompt(
        _ShopStub(shop_bot), [], None, "G", learned_answers=None, gap_detection=False
    )
    assert ai_context.build_system_prompt(_ShopStub(shop_bot), [], None, "G", bot_tools=None) == baseline
    empty = ai_context.build_system_prompt(_ShopStub(shop_bot), [], None, "G", bot_tools=[])
    assert ai_context.NO_BOT_TOOLS_NOTE in empty, "فهرستِ خالی باید صریح گفته شود"
    assert len(ai_context.NO_BOT_TOOLS_NOTE) < 150, "این خط در *هر* درخواستِ این مود هزینه دارد"
    print("PASS test_missing_tools_are_declared_not_silenced")


def test_scanner_over_whole_app_is_clean() -> None:
    """همان چیزی که `scripts/check_prompt_buttons.py` در گیت‌ها می‌سنجد، اینجا با عددِ اجرا می‌شود."""
    import pathlib
    import sys as _sys
    import time

    _sys.path.insert(0, "scripts")
    import check_prompt_buttons as scanner  # noqa: E402

    root = pathlib.Path("app")
    started = time.perf_counter()
    live = scanner._live_labels(root)
    dead = scanner._mentioned(root, live)
    elapsed = time.perf_counter() - started
    assert len(live) > 500, f"فهرستِ دکمه‌هایِ زنده خالی است: {len(live)}"
    assert not dead, "دکمهٔ مرده در متن/پرامپت‌ها: " + " | ".join(dead[:8])
    print(f"PASS test_scanner_over_whole_app_is_clean ({len(live)} برچسبِ زنده، {elapsed:.2f}s)")


class _ShopStub:
    def __init__(self, tenant_mode) -> None:
        self.tenant_mode = tenant_mode
        self.ai_instructions = None


def main() -> None:
    test_default_prompts_name_only_existing_buttons()
    test_tools_match_the_real_customer_keyboard()
    test_missing_tools_are_declared_not_silenced()
    test_scanner_over_whole_app_is_clean()


if __name__ == "__main__":
    main()
