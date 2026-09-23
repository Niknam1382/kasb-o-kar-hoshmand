"""
تست: محافظتِ ReDoS در نگهبانِ محتوا — هم لایه‌ی ذخیره (الگوی خطرناک رد بشه) و
هم لایه‌ی اجرا (اگه یه الگوی خطرناک هرجوری وارد دیتابیس شده باشه، matchِ روش
بیشتر از ۱۰۰ میلی‌ثانیه طول نکشه و کلِ اپ رو فریز نکنه). فازِ ۱ - بازیابی.

اجرا: python3 tests_manual/test_moderation_redos_protection.py
"""
from __future__ import annotations

import asyncio
import sys
import time

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from harness import reset_database  # noqa: E402

from app.database.models import ModerationRule  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import moderation_service  # noqa: E402


async def test_nested_quantifier_pattern_rejected_at_creation() -> None:
    await reset_database()
    async with session_scope() as session:
        try:
            await moderation_service.create_rule(session, r"(a+)+$", is_regex=True, action="block")
            raise AssertionError("نباید اجازه‌ی ذخیره‌ی این الگوی خطرناک رو بده")
        except moderation_service.UnsafePatternError:
            pass

        rules = await moderation_service.get_all_rules(session)
        assert len(rules) == 0, "قانونِ ردشده نباید توی دیتابیس ذخیره شده باشه"
    print("✅ test_nested_quantifier_pattern_rejected_at_creation PASSED")


async def test_invalid_regex_rejected_at_creation() -> None:
    await reset_database()
    async with session_scope() as session:
        try:
            await moderation_service.create_rule(session, r"[این‌یه‌regexِ‌نامعتبره(", is_regex=True, action="block")
            raise AssertionError("regexِ نامعتبر نباید ذخیره بشه")
        except moderation_service.UnsafePatternError:
            pass
    print("✅ test_invalid_regex_rejected_at_creation PASSED")


async def test_safe_regex_pattern_still_matches_correctly() -> None:
    await reset_database()
    async with session_scope() as session:
        rule = await moderation_service.create_rule(session, r"\b09\d{9}\b", is_regex=True, action="warn")
        assert rule.id is not None

        matched = await moderation_service.check_text(session, "شماره‌م اینه: 09123456789")
        assert matched is not None and matched.id == rule.id, "الگوی سالم باید مثلِ قبل کار کنه"

        no_match = await moderation_service.check_text(session, "سلام، قیمتِ محصول چنده؟")
        assert no_match is None
    print("✅ test_safe_regex_pattern_still_matches_correctly PASSED")


async def test_catastrophic_pattern_in_db_times_out_instead_of_hanging() -> None:
    """
    شبیه‌سازیِ قانونی که (مثلاً از قبلِ این پچ) با یه الگوی فاجعه‌بار توی
    دیتابیسه — مستقیم مدل رو می‌سازیم تا از چکِ create_rule رد بشیم و لایه‌ی
    دومِ محافظت (تایم‌اوتِ زمانِ اجرا) رو مجزا تست کنیم.
    """
    await reset_database()
    async with session_scope() as session:
        session.add(ModerationRule(pattern=r"(a+)+$", is_regex=True, action="block"))
        await session.flush()

    evil_input = "a" * 35 + "!"  # ورودی‌ای که باعثِ backtrackingِ نمایی می‌شه

    async with session_scope() as session:
        started = time.monotonic()
        # خودِ تستِ ما هم یه سقفِ زمانیِ سخاوتمندانه داره (۳ ثانیه) که اگه
        # محافظتِ داخلیِ moderation_service اصلاً کار نکنه، کلِ تست‌سوییت رو
        # به‌جای فریزِ ابدی، با یه fail واضح متوقف کنه.
        result = await asyncio.wait_for(moderation_service.check_text(session, evil_input), timeout=3.0)
        elapsed = time.monotonic() - started

    assert result is None, "قانونِ فاجعه‌بار باید نادیده گرفته بشه، نه این‌که به‌اشتباه match حساب بشه"
    assert elapsed < 1.0, f"محافظتِ ۱۰۰ میلی‌ثانیه‌ای باید جلوی طولانی‌شدنِ match رو بگیره (طول کشید: {elapsed:.2f}s)"
    print(f"✅ test_catastrophic_pattern_in_db_times_out_instead_of_hanging PASSED ({elapsed*1000:.0f}ms)")


async def main() -> None:
    await test_nested_quantifier_pattern_rejected_at_creation()
    await test_invalid_regex_rejected_at_creation()
    await test_safe_regex_pattern_still_matches_correctly()
    await test_catastrophic_pattern_in_db_times_out_instead_of_hanging()


if __name__ == "__main__":
    asyncio.run(main())
