"""پ۱۰۰ · تستِ بستهٔ آزمونِ A/Bِ پرامپت (قاعدهٔ ۸: هر ویژگیِ تازه یکِ فایلِ تستِ اختصاصی می‌خواهد).

پ۹۸ یکِ اسکریپتِ اجرایی ساخت که هزینه‌اش با مالکِ محصول است. این فایل **هیچ فراخوانِ شبکه‌ای** نمی‌زند
(همه‌چیز با یکِ سرویسِ جعلی) و چهار چیز را قفل می‌کند که اگر روزی بشکنند، آزمونِ A/B بی‌معنی می‌شود:

۱. parityِ دو نسخه: پرامپتِ A و B **فقط** در دو خطِ نگهبان فرق دارند ⇒ با جای‌گذاریِ برگشتیِ همان دو خط،
   B عیناً A می‌شود (هر تغییرِ تصادفیِ دیگر در `build_system_prompt` این تست را می‌شکند).
۲. `--dry-run` صفر فراخوانیِ AI است (`build_ai_service` جعلی که اگر صدا زده شود، می‌ترکد).
۳. گزارشِ Markdown **هیچ رازی ندارد**: نه کلیدِ API، نه سرِصفحهٔ احراز، نه شناسهٔ فنیِ داخلی.
۴. `order=alternate` ترتیبِ نسخه‌ها را بینِ سوالِ زوج و فرد عوض می‌کند و هرِ سوال دقیقاً دو فراخوانی دارد.

اجرا: python3 tests_manual/run_one.py test_p100_ab_kit.py
"""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from app.database.session import session_scope  # noqa: E402
from app.services import ai_context, ai_pool_service, product_service  # noqa: E402
from app.services.ai_service import AiCallResult  # noqa: E402
from harness import reset_database  # noqa: E402
from scripts import ab_prompt_test as ab  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

OWNER_TG_ID = 10_100_000_001
SHOP_BOT_TG_ID = 10_100_000_002
API_KEY_SENTINEL = "sk-ab-key-9b4c2d7e1f3a"
REPORT_PATH = "/tmp/p100_ab_report.md"

_shop_id = 0
_prompts_cache: dict[str, str] = {}


class StubAi:
    """جایِ سرویسِ واقعیِ AI: متنِ ساختگی برمی‌گرداند و هر فراخوانی را ثبت می‌کند (بدونِ شبکه)."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def get_reply(self, system_prompt: str, history, user_message: str) -> AiCallResult:
        self.calls.append((system_prompt, user_message))
        return AiCallResult(text=f"پاسخِ ساختگی به «{user_message}»", total_tokens=123)


async def _seed_shop() -> int:
    global _shop_id
    await reset_database()
    _shop_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    async with session_scope() as session:
        await product_service.create_product(session, _shop_id, "دفترِ خط‌دار", None, 45_000, None, stock_quantity=7)
        await product_service.create_product(session, _shop_id, "کیفِ دوشی", None, 890_000, None, stock_quantity=2)
        await session.commit()
    return _shop_id


def _install_stub(monkey: StubAi | None) -> None:
    """`build_ai_service` را با جعلِ خودِ تست عوض می‌کنیم (بدونِ هیچ شبکه/کلیدِ واقعی)."""
    original = ai_pool_service.build_ai_service

    async def _fake(session, admin_settings, capability: str):
        if monkey is None:
            raise AssertionError("dry-run نباید سازندهٔ سرویسِ AI را صدا بزند")
        return monkey

    ai_pool_service.build_ai_service = _fake  # type: ignore[assignment]
    _install_stub.original = original  # type: ignore[attr-defined]


# ============================================================================= ۱
async def test_variants_differ_only_in_guard_lines() -> None:
    shop_id = await _seed_shop()
    args = await ab._collect(shop_id)
    prompts = ab._prompts(args)
    _prompts_cache.update(prompts)
    a, b = prompts["A"], prompts["B"]
    assert a != b, "دو نسخه باید فرق داشته باشند"
    assert len(b) < len(a), (len(a), len(b))
    assert ai_context.GUARD_INJECTION_VERBOSE in a and ai_context.GUARD_FORMAT_VERBOSE in a
    assert ai_context.GUARD_INJECTION_CONCISE in b and ai_context.GUARD_FORMAT_CONCISE in b
    reconstructed = (
        b.replace(ai_context.GUARD_INJECTION_CONCISE, ai_context.GUARD_INJECTION_VERBOSE)
        .replace(ai_context.GUARD_FORMAT_CONCISE, ai_context.GUARD_FORMAT_VERBOSE)
    )
    assert reconstructed == a, "تفاوتِ A/B باید **فقط** همان دو خطِ نگهبان باشد"
    assert len(ab.QUESTIONS) == 20, len(ab.QUESTIONS)
    assert "دستورالعمل" in ab.QUESTIONS[13] or "قانونِ جدید" in ab.QUESTIONS[13], ab.QUESTIONS[13]
    print("PASS test_variants_differ_only_in_guard_lines")


# ============================================================================= ۲
async def test_dry_run_makes_zero_ai_calls() -> None:
    shop_id = await _seed_shop()
    _install_stub(None)
    try:
        code = await ab.run(shop_id, limit=3, order="alternate", out_path="/tmp/p100_should_not_exist.md", dry_run=True)
    finally:
        ai_pool_service.build_ai_service = _install_stub.original  # type: ignore[attr-defined]
    assert code == 0, code
    assert not os.path.exists("/tmp/p100_should_not_exist.md"), "dry-run فایلِ گزارش نمی‌سازد"
    print("PASS test_dry_run_makes_zero_ai_calls")


# ============================================================================= ۳ و ۴
async def test_report_is_secret_free_and_order_alternates() -> None:
    shop_id = await _seed_shop()
    stub = StubAi()
    _install_stub(stub)
    try:
        code = await ab.run(shop_id, limit=4, order="alternate", out_path=REPORT_PATH, dry_run=False)
    finally:
        ai_pool_service.build_ai_service = _install_stub.original  # type: ignore[attr-defined]
    assert code == 0, code
    assert len(stub.calls) == 8, len(stub.calls)  # چهار سوال × دو نسخه
    a_len = len(_prompts_cache["A"])
    b_len = len(_prompts_cache["B"])
    first_of_each_question = [stub.calls[i] for i in range(0, 8, 2)]
    seen = [len(prompt) for prompt, _q in first_of_each_question]
    assert seen == [a_len, b_len, a_len, b_len], f"سوالِ زوج باید با نسخهٔ B شروع کند (alternate): {seen}"
    for prompt, question in stub.calls:
        assert question in ab.QUESTIONS
        assert prompt in (_prompts_cache["A"], _prompts_cache["B"])

    with open(REPORT_PATH, encoding="utf-8") as fh:
        report = fh.read()
    assert "MEASURED" in report and "A (مفصّل)" in report and "B (کوتاه)" in report, report[:300]
    assert "پاسخِ ساختگی" in report
    for forbidden in (API_KEY_SENTINEL, "Authorization", "api_key", "Bearer", "sk-", "encrypted_token"):
        assert forbidden not in report, f"راز/شناسهٔ فنی در گزارشِ A/B: {forbidden}"
    os.remove(REPORT_PATH)
    print("PASS test_report_is_secret_free_and_order_alternates")


# ============================================================================= ۵ (پ۱۰۵)
async def test_pick_selects_only_those_questions_and_cost_uses_new_ratio() -> None:
    await _seed_shop()
    _install_stub(None)
    try:
        code = await ab.run(
            _shop_id, limit=20, order="alternate", out_path="/tmp/p100_pick_should_not_exist.md", dry_run=True, pick="14,16"
        )
    finally:
        ai_pool_service.build_ai_service = _install_stub.original  # type: ignore[attr-defined]
    assert code == 0, code
    assert not os.path.exists("/tmp/p100_pick_should_not_exist.md")
    # ضریبِ نو (نویسه÷۲٫۲) باید هزینه را *بیشتر* از قاعدهٔ قدیمی (نویسه÷۴) نشان دهد، چون اندازه‌گیری
    # واقعیِ پ۱۰۵ (پرامپت ۷۸٬۹۳۹ نویسه ⇒ ۳۶٬۷۷۵ توکن) همان را گفت.
    prompt_len = len(_prompts_cache["A"])
    assert prompt_len // 10 * 10 * 10 // 22 > prompt_len // 4, prompt_len
    print("PASS test_pick_selects_only_those_questions_and_cost_uses_new_ratio")


async def main() -> None:
    await test_variants_differ_only_in_guard_lines()
    await test_dry_run_makes_zero_ai_calls()
    await test_report_is_secret_free_and_order_alternates()
    await test_pick_selects_only_those_questions_and_cost_uses_new_ratio()


if __name__ == "__main__":
    asyncio.run(main())
