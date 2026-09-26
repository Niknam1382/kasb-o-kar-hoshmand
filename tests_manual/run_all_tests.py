#!/usr/bin/env python3
"""
اجراکننده‌ی همه‌ی تست‌های tests_manual/. هر فایل به‌عنوانِ یه ساب‌پروسسِ جدا اجرا
می‌شه (چون روترهای aiogram سطحِ‌ماژول هستن و نمی‌شه دو دیسپچرِ متفاوت رو توی یه
پروسه برای دو فایلِ مختلف ساخت) و یه خلاصه‌ی موفق/ناموفق در پایان چاپ می‌شه.

اجرا: python3 tests_manual/run_all_tests.py
خروجی: کدِ ۰ اگه همه‌ی فایل‌ها پاس بشن، ۱ اگه حتی یکی fail بشه.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

TEST_DIR = Path(__file__).parent

TEST_FILES = [
    "test_start_registration.py",
    "test_shop_bot_and_products.py",
    "test_fsm_escape.py",
    "test_message_debounce.py",
    "test_photo_handling.py",
    "test_voice_handling.py",
    "test_discount_amount_bug.py",
    "test_excel_export.py",
    "test_admin_owner_management.py",
    "test_payment_approval.py",
    "test_admin_channel_management.py",
    "test_admin_pricing.py",
    "test_admin_settings.py",
    "test_referral_and_trial.py",
    "test_card_to_card_improvements.py",
    "test_order_product_id_matching.py",
    "test_order_customer_confirmation.py",
    "test_wallet_service.py",
    "test_wallet_integration.py",
    "test_order_reservation.py",
    "test_consultation_mode.py",
    "test_kill_switches.py",
    "test_moderation_and_audit_log.py",
    "test_wallet_history_and_finops.py",
    "test_webhook_idempotency.py",
    "test_ai_retry_and_fallback.py",
    "test_webhook_security_and_health.py",
    "test_moderation_redos_protection.py",
    "test_conversation_retention.py",
    "test_bale_pay_wallet_topup.py",
    "test_order_dedup_fix.py",
    "test_pagination.py",
    "test_wallet_concurrency_fix.py",
    "test_wallet_pricing_formula.py",
    "test_ai_key_pool.py",
    "test_admin_rbac.py",
    "test_excel_product_import.py",
    "test_wallet_correction.py",
]


def main() -> int:
    results: list[tuple[str, bool, float, str]] = []

    for filename in TEST_FILES:
        path = TEST_DIR / filename
        print(f"\n{'=' * 70}\n▶ {filename}\n{'=' * 70}")
        start = time.monotonic()
        try:
            proc = subprocess.run(
                [sys.executable, str(path)],
                cwd=str(TEST_DIR.parent),
                capture_output=True,
                text=True,
                timeout=60,
            )
            elapsed = time.monotonic() - start
            output = proc.stdout + proc.stderr
            passed = proc.returncode == 0
        except subprocess.TimeoutExpired as exc:
            # یه فایلِ گیرکرده نباید جلوِی اجرای بقیه‌ی فایل‌ها رو بگیره —
            # به‌عنوانِ fail ثبتش می‌کنیم و ادامه می‌دیم.
            elapsed = time.monotonic() - start
            stdout = exc.stdout.decode("utf-8", "replace") if exc.stdout else ""
            stderr = exc.stderr.decode("utf-8", "replace") if exc.stderr else ""
            output = stdout + stderr + f"\n❌ TIMEOUT: بیش از ۶۰ ثانیه طول کشید و کشته شد.\n"
            passed = False
        print(output.strip())
        results.append((filename, passed, elapsed, output))

    print(f"\n\n{'#' * 70}\n# خلاصه‌ی نهایی\n{'#' * 70}")
    total_passed = sum(1 for _, ok, _, _ in results if ok)
    for filename, ok, elapsed, output in results:
        mark = "✅" if ok else "❌"
        test_count = output.count("✅ test_")
        print(f"{mark} {filename:<45} ({test_count} تست، {elapsed:.1f} ثانیه)")

    print(f"\n{total_passed}/{len(results)} فایل با موفقیت پاس شدن.")
    total_individual_tests = sum(output.count("✅ test_") for _, _, _, output in results)
    print(f"مجموعِ تست‌های جداگانه‌ی پاس‌شده: {total_individual_tests}")

    if total_passed < len(results):
        print("\n❌ حداقل یه فایل fail شد. برای جزئیات به خروجیِ بالا نگاه کن.")
        return 1

    print("\n✅ همه‌ی فایل‌های تست با موفقیت پاس شدن.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
