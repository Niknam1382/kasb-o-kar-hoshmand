"""
تست: محکم‌کاریِ آپدیت‌های تکراریِ وب‌هوکِ تلگرام (بخشِ ۲ مسترپرامپت).

اجرا: python3 tests_manual/test_webhook_idempotency.py
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")

from app.main import _MAX_SEEN_UPDATES, _is_duplicate_update, _seen_update_ids  # noqa: E402


def test_first_occurrence_not_duplicate() -> None:
    _seen_update_ids.clear()
    assert _is_duplicate_update(bot_id=1, update_id=100) is False
    print("✅ test_first_occurrence_not_duplicate PASSED")


def test_repeated_update_id_is_duplicate() -> None:
    _seen_update_ids.clear()
    assert _is_duplicate_update(bot_id=1, update_id=200) is False
    assert _is_duplicate_update(bot_id=1, update_id=200) is True, "همون update_id دوباره باید تکراری تشخیص داده بشه"
    print("✅ test_repeated_update_id_is_duplicate PASSED")


def test_same_update_id_different_bot_not_duplicate() -> None:
    """update_id فقط بینِ یه ربات معنی داره؛ دو ربات ممکنه هم‌زمان همون شماره رو داشته باشن."""
    _seen_update_ids.clear()
    assert _is_duplicate_update(bot_id=1, update_id=300) is False
    assert _is_duplicate_update(bot_id=2, update_id=300) is False, "بینِ دو ربات جدا نباید تکراری حساب بشه"
    print("✅ test_same_update_id_different_bot_not_duplicate PASSED")


def test_memory_bounded() -> None:
    _seen_update_ids.clear()
    for i in range(_MAX_SEEN_UPDATES + 50):
        _is_duplicate_update(bot_id=1, update_id=i)
    assert len(_seen_update_ids) <= _MAX_SEEN_UPDATES, "حافظه نباید بی‌نهایت رشد کنه"
    print("✅ test_memory_bounded PASSED")


def main() -> None:
    test_first_occurrence_not_duplicate()
    test_repeated_update_id_is_duplicate()
    test_same_update_id_different_bot_not_duplicate()
    test_memory_bounded()


if __name__ == "__main__":
    main()
