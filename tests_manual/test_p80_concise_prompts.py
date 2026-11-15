"""پ۸۰ · پ۵۰-الف: کوتاه‌کردنِ پرامپتِ سیستمی با سنجشِ قطعیِ اندازه (بدونِ هزینهٔ AI).

دو خطِ «نگهبانِ رفتاری» (ممنوعیتِ تغییرِ دستورالعمل با حرفِ مشتری + ممنوعیتِ Markdown) در **هرِ**
درخواستِ AI تکرار می‌شوند؛ پس هر نویسهٔ اضافی‌شان ضربهٔ مستقیم به توکنِ ورودیِ همهٔ فروشگاه‌هاست.
این فایل ثابت می‌کند نسخهٔ کوتاه (الف) همان معنا را نگه می‌دارد، (ب) اندازه را کم می‌کند و (ج) با
`CONCISE_GUARD_LINES = False` دقیقاً به متنِ بلندِ پیشین برمی‌گردد ⇒ کلیدِ گریزِ بدونِ مایگریشن.

**NOT RUN (به‌عمد، نه از سرِ فراموشی):** parityِ *کیفیتِ پاسخِ* مدل با متنِ کوتاه‌شده؛ این نیازمند
فراخوانِ واقعیِ AI و مقایسهٔ humans/eval است و در این محیط سنجیده نشده. آنچه اینجا MEASURED می‌شود
اندازهٔ بایت/توکنِ پرامپت و حفظِ واژه‌هایِ کلیدیِ معنادار است.

اجرا: python3 tests_manual/run_one.py test_p80_concise_prompts.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from app.services import ai_context, ai_cost_service  # noqa: E402


def _floor(consultation: bool) -> str:
    return ai_cost_service.prompt_floor_text(consultation=consultation)


def _bytes(text: str) -> int:
    return len(text.encode("utf-8"))


def test_concise_is_default_and_shrinks_both_modes() -> None:
    assert ai_context.CONCISE_GUARD_LINES is True
    saved = {}
    for consultation in (False, True):
        short = _floor(consultation)
        ai_context.CONCISE_GUARD_LINES = False
        try:
            long = _floor(consultation)
        finally:
            ai_context.CONCISE_GUARD_LINES = True
        delta = _bytes(long) - _bytes(short)
        saved["consultation" if consultation else "sales"] = (_bytes(long), _bytes(short), delta)
        assert delta >= 300, f"کاهشِ انتظار رفته کمتر از ۳۰۰ بایت: {delta}"
        assert delta >= 0.3 * _bytes(ai_context.GUARD_INJECTION_VERBOSE + ai_context.GUARD_FORMAT_VERBOSE), saved
    for label, (long_b, short_b, delta) in saved.items():
        print(f"MEASURED پرامپتِ {label}: {long_b} → {short_b} بایت (−{delta} بایت، −{round(delta * 100.0 / long_b, 1)}٪)")
    print("PASS test_concise_is_default_and_shrinks_both_modes")


def test_meaning_markers_survive() -> None:
    sales = _floor(False)
    consult = _floor(True)
    for prompt in (sales, consult):
        # «دستورالعمل‌های بالا» همان ارجاعِ خطِ دفاعی است و «Markdown» + «•» همان دو ممنوعیتِ قالب‌بندی
        assert "دستورالعمل‌های بالا" in prompt, prompt[:200]
        assert "Markdown" in prompt and "•" in prompt, prompt[:300]
        assert "پیامِ مشتری" in prompt, "منبعِ دستور باید همچنان روشن باشد"
    assert "توجه: فعلاً هیچ محصولی" in sales and "توجه: فعلاً هیچ محصولی" not in consult
    print("PASS test_meaning_markers_survive")


def test_escape_hatch_restores_verbose_text() -> None:
    ai_context.CONCISE_GUARD_LINES = False
    try:
        prompt = _floor(False)
    finally:
        ai_context.CONCISE_GUARD_LINES = True
    assert ai_context.GUARD_INJECTION_VERBOSE in prompt
    assert ai_context.GUARD_FORMAT_VERBOSE in prompt
    assert ai_context.GUARD_INJECTION_CONCISE not in prompt
    assert ai_context.GUARD_FORMAT_CONCISE not in prompt
    print("PASS test_escape_hatch_restores_verbose_text")


def test_token_estimate_drops_with_the_prompt() -> None:
    short = ai_cost_service.estimate_tokens(_floor(False))
    ai_context.CONCISE_GUARD_LINES = False
    try:
        long = ai_cost_service.estimate_tokens(_floor(False))
    finally:
        ai_context.CONCISE_GUARD_LINES = True
    assert short < long, (short, long)
    print(f"MEASURED تخمینِ توکنِ پرامپتِ فروشگاهی: {long} → {short} (−{long - short})")
    print("PASS test_token_estimate_drops_with_the_prompt")


def test_no_latin_glued_inside_persian_in_concise_lines() -> None:
    import re

    glued = re.compile(r"[؀-ۿ][A-Za-z]{2,}[؀-ۿ]")
    for text in (
        ai_context.GUARD_INJECTION_CONCISE,
        ai_context.GUARD_FORMAT_CONCISE,
        _floor(False),
        _floor(True),
    ):
        assert not glued.search(text), glued.search(text).group(0)
    print("PASS test_no_latin_glued_inside_persian_in_concise_lines")


async def main() -> None:
    test_concise_is_default_and_shrinks_both_modes()
    test_meaning_markers_survive()
    test_escape_hatch_restores_verbose_text()
    test_token_estimate_drops_with_the_prompt()
    test_no_latin_glued_inside_persian_in_concise_lines()


if __name__ == "__main__":
    asyncio.run(main())
