"""
تست: P22 — «ماه»ِ تقویمی و متنِ درستِ یادآوریِ انقضا (مشکلِ ۱ کاربر)

۱. `add_months` ماهِ تقویمی می‌دهد و روزِ سرِ ماه را clamp می‌کند — همان قاعده‌ای که حالا
   همِ شارژِ کیف‌پول است هم مدتِ اشتراک (قبلاً کیف‌پول ۳۰×N روز بود و اشتراک ماهِ واقعی).
2. متنِ یادآوری دیگر «شارژِ تازه بزن» نمی‌گوید (چنان دکمه‌ای در پنل وجود ندارد) و مسیرِ
   واقعیِ «💰 کیف‌پول › 💰 شارژ کیف‌پول» را نشان می‌دهد؛ عددِ روزها هم روزهایِ واقعی است.

اجرا: python3 tests_manual/run_one.py test_p22_wallet_months_and_wording.py
"""
from __future__ import annotations

import datetime
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from app.bots.main_bot import texts as main_texts  # noqa: E402
from app.utils.dates import add_months  # noqa: E402

UTC = datetime.timezone.utc


# ============================================================================= ۱ — ماهِ تقویمی
def test_add_months_is_calendar_not_thirty_days() -> None:
    # ۳۱ → ۳۰: ماهِ بعد ۳۱ روز ندارد ⇒ clamp به آخرین روزِ همان ماه (این را «۳۰ روز» نمی‌دهد)
    assert add_months(datetime.datetime(2026, 1, 31, 9, 0, tzinfo=UTC), 1) == datetime.datetime(2026, 2, 28, 9, 0, tzinfo=UTC)
    # ۲۹ اسفندِ سالِ کبیسه + ۱۲ ماه ⇒ ۲۸ اسفندِ سالِ بعد (۲۹ فوریه وجود ندارد)
    assert add_months(datetime.datetime(2024, 2, 29, 12, 0, tzinfo=UTC), 12) == datetime.datetime(2025, 2, 28, 12, 0, tzinfo=UTC)
    # ماهِ ۳۱ روزه ⇒ یکِ ماه واقعاً ۳۱ روز است، نه ۳۰
    assert (add_months(datetime.datetime(2026, 3, 21, tzinfo=UTC), 1) - datetime.datetime(2026, 3, 21, tzinfo=UTC)).days == 31
    # چرخشِ سال: ۱۵ دی + ۲ ماه ⇒ ۱۵ اسفند
    assert add_months(datetime.datetime(2026, 12, 15, tzinfo=UTC), 2) == datetime.datetime(2027, 2, 15, tzinfo=UTC)
    assert add_months(datetime.datetime(2026, 6, 30, 23, 59, 59, tzinfo=UTC), 0) == datetime.datetime(2026, 6, 30, 23, 59, 59, tzinfo=UTC)
    print("✅ test_add_months_is_calendar_not_thirty_days PASSED")


def test_add_months_keeps_timezone_and_accepts_strings() -> None:
    aware = add_months(datetime.datetime(2026, 1, 31, 9, 0, tzinfo=UTC), 1)
    assert aware.tzinfo is not None, "جابِ انقضا رویِ UTC کار می‌کند؛ naive شدنش یعنی یکِ روز خطا"
    assert add_months(datetime.datetime(2026, 1, 31, tzinfo=UTC), "3") == datetime.datetime(2026, 4, 30, tzinfo=UTC), "عددِ پنل رشته است"
    naive = add_months(datetime.datetime(2026, 1, 31, 9, 0), 1)
    assert naive.tzinfo is None and naive.day == 28
    print("✅ test_add_months_keeps_timezone_and_accepts_strings PASSED")


# ============================================================================= ۲ — متنِ یادآوری
def test_expiry_reminder_points_to_the_real_button() -> None:
    message = main_texts.wallet_expiry_reminder(30, 75_000)
    assert "شارژِ تازه" not in message, "چنان دکمه‌ای در پنل نیست؛ کاربر را به مسیرِ واقعی بفرست"
    assert "💰 شارژ کیف‌پول" in message, message
    assert "💰 کیف‌پول" in message, message
    assert "75,000" in message or "۷۵" in message, "مبلغِ بسته‌ای که می‌سوزد باید در پیام باشد"
    assert "30 روزِ دیگه" in message, message

    assert main_texts.wallet_expiry_reminder(1, 5_000).startswith("⏳") and "فردا" in main_texts.wallet_expiry_reminder(1, 5_000)
    assert "0 روزِ دیگه" not in main_texts.wallet_expiry_reminder(0, 5_000), "«امروز» نباید «۰ روزِ دیگه» شود"
    assert "7 روزِ دیگه" in main_texts.wallet_expiry_reminder(7, 5_000)
    print("✅ test_expiry_reminder_points_to_the_real_button PASSED")


def test_topup_button_label_matches_the_message() -> None:
    """پیامِ انقضا نامِ دکمه را نقل می‌کند ⇒ اگر روزی دکمه عوض شد، این تست می‌گوید."""
    assert "💰 شارژ کیف‌پول" in main_texts.wallet_topup_action_label(), main_texts.wallet_topup_action_label()
    print("✅ test_topup_button_label_matches_the_message PASSED")


def main() -> None:
    test_add_months_is_calendar_not_thirty_days()
    test_add_months_keeps_timezone_and_accepts_strings()
    test_expiry_reminder_points_to_the_real_button()
    test_topup_button_label_matches_the_message()


if __name__ == "__main__":
    main()
