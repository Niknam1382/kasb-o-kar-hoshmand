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

import db_env  # هم‌کناریِ همین فایل در tests_manual/

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
    "test_customer_broadcast.py",
    "test_nightly_report.py",
    "test_bale_pay_for_orders.py",
    "test_shopping_cart.py",
    "test_cart_ai_editing.py",
    "test_campaigns.py",
    "test_campaign_owner_flow.py",
    "test_campaign_checkout.py",
    "test_checkout_c3.py",
    "test_w5_bale_hardening.py",
    "test_w5_layer2.py",
    "test_orders_manage.py",
    "test_w5_receipt_text_and_product_photos.py",
    "test_w5_security.py",
    # فازِ ۴
    "test_knowledge_gaps.py",
    "test_learned_answers.py",
    "test_accounting.py",
    "test_crm.py",
    "test_crm_ai_summary.py",
    "test_owner_assistant.py",
    # فازِ ۶-الف
    "test_phase6a_batching_and_settings.py",
    "test_identity_and_profile.py",
    "test_customer_menu_and_prompts.py",
    "test_bale_payment_foundation.py",
    "test_catalog_digital_physical.py",
    "test_orders_w2.py",
    "test_payments_w3w4.py",
    # P18
    "test_p18_bale_credentials.py",
    "test_p18_security.py",
    "test_p18_topup_receipt.py",
    "test_p18_weekly_report.py",
    "test_p18_block_and_conversation.py",
    "test_p18_per_shop_settings.py",
    "test_p18_checkout_steps.py",
    "test_p18_consultation_panel.py",
    "test_p18_sms.py",
    "test_p18_bot_branding.py",
    "test_p18_ai_model_pool.py",
    "test_p18_pdf_invoice.py",
    "test_p2_credit_expiry_preserved.py",
    "test_p5_min_recharge.py",
    "test_p5_ledger_integrity.py",
    "test_p5_commission.py",
    "test_p19_bale_shop_bot.py",
    "test_p20_money_integrity.py",
    "test_p20_security_observability.py",
    "test_p20_performance_outbox.py",
    "test_p21_ops.py",
    "test_p21_money.py",
    "test_p21_growth.py",
    "test_p21_access.py",
    "test_p21_security.py",
    "test_customer_keyboard_layout.py",
    "test_p22_wallet_months_and_wording.py",
    "test_p22_bale_token_in_panel.py",
    "test_p22_shipping_coordination.py",
    "test_p22_seed_cleanup_safety.py",
    "test_p22_export_beautification.py",
    "test_p22_inactive_owners.py",
    "test_p24_dead_buttons_and_scope.py",
    "test_p25_bale_link_and_discounts.py",
    "test_p26_bale_handoff_and_ux.py",
    "test_p27_invoice_persian_layout.py",
    "test_p27_receipt_one_click.py",
    "test_p28_docs_pdf_builder.py",
    "test_p29_bounded_bot_startup.py",
    "test_p29_job_query_bounds.py",
    "test_p30_catalog_instruction_conflict.py",
    "test_p30_platform_revenue_split.py",
    "test_p30_zero_credit_orders.py",
    "test_p30_concurrency_report.py",
    "test_p31_message_statement_bounds.py",
    "test_p31_nightly_stats_batching.py",
    "test_p32_fsm_postgres.py",
    "test_p33_admin_settings_race.py",
    "test_p33_cart_submit_idempotency.py",
    "test_p33_ai_usage_debt.py",
    "test_p34_bale_own_payment_surface.py",
    "test_p35_text_accuracy.py",
    "test_p36_bale_smarten_flow.py",
    "test_p37_hardening.py",
    "test_p39_no_markdown_markers.py",
    "test_p39_wallet_per_charge_expiry.py",
    "test_p40_inspection_fixes.py",
    "test_p41_order_payment_never_platform.py",
    "test_p42_bale_split_and_money.py",
    "test_p43_moderation_reports.py",
    "test_p44_month_length_and_backup.py",
    "test_p45_capacity_layers.py",
    "test_p46_per_shop_memory_and_rate_limit.py",
    "test_p47_ai_key_load_balance.py",
    "test_p48_logs_and_audit_range.py",
    "test_p49_instagram_channel.py",
    "test_p49_b_instagram_comments.py",
    "test_p51_revenue_chart.py",
    "test_p52_concurrency_report.py",
    "test_p53_wallet_history_export.py",
    "test_p54_payment_queue.py",
    "test_p55_customer_ai_usage.py",
    "test_p56_search.py",
    "test_p57_persian_digits.py",
    "test_p58_mode_gates.py",
    "test_p59_output_polish.py",
    "test_p60_instagram_panel.py",
    "test_p61_capacity_panel.py",
    "test_p62_server_doctor.py",
    "test_p63_instagram_management.py",
    "test_p64_navigation_guards.py",
    "test_p65_account_deletion.py",
    "test_p66_consultation_screens.py",
    "test_p67_user_dossier.py",
    "test_p68_checkout_province_city.py",
    "test_p69_ai_cost_estimate.py",
    "test_p70_ai_usage_per_shop.py",
    "test_p71_invoice_paging.py",
    "test_p72_doctor_thresholds.py",
    "test_p73_instagram_comment_report.py",
    "test_p74_product_categories.py",
    "test_p75_gap_clusters.py",
    "test_p76_recurring_broadcasts.py",
    "test_p77_instagram_comment_blocks.py",
    "test_p78_digital_retired.py",
    "test_p79_counter_aggregation.py",
    "test_p80_concise_prompts.py",
    "test_p81_metrics_peer_summary.py",
    "test_p84_comment_erasure.py",
    "test_p87_ops_endpoint.py",
    "test_p90_ops_measurements.py",
    "test_p91_ops_panel.py",
    "test_p94_purge_guards.py",
    "test_p95_prompt_parity.py",
    "test_p97_digital_archive.py",
    "test_p99_retention_apply.py",
    "test_p100_ab_kit.py",
]


def main() -> int:
    results: list[tuple[str, bool, float, str]] = []

    # P22: دیتابیسِ جدا (kasbokar_test) + مایگریشنِ یک‌بار، تا اجرایِ سوئیت دادهٔ پنل را نابود نکند.
    db_env.prepare()
    print(f"دیتابیسِ تست: {db_env.TEST_DB_NAME} (رشتهٔ اتصال چاپ نمی‌شود)")

    for filename in TEST_FILES:
        path = TEST_DIR / filename
        print(f"\n{'=' * 70}\n▶ {filename}\n{'=' * 70}")
        start = time.monotonic()
        try:
            proc = subprocess.run(
                [sys.executable, str(path)],
                cwd=str(TEST_DIR.parent),
                # تست‌هایِ ادمین آیدیِ ۱۲۳۴۵ را فرض می‌کنن؛ متغیرِ محیطی بر `.env` (مثلاً .envِ واقعیِ شما با آیدیِ ادمینِ خودتان) غالب است.
                # P22: DATABASE_URL هم به `kasbokar_test` تبدیل می‌شود — هر فایلِ تست TRUNCATE
                # می‌زند و رویِ دیتابیسِ توسعه، تنظیماتی که ادمین در پنل نوشته پاک می‌شد.
                env=db_env.child_env(),
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
            output = stdout + stderr + "\n❌ TIMEOUT: بیش از ۶۰ ثانیه طول کشید و کشته شد.\n"
            passed = False
        print(output.strip())
        results.append((filename, passed, elapsed, output))

    print(f"\n\n{'#' * 70}\n# خلاصه‌ی نهایی\n{'#' * 70}")
    total_passed = sum(1 for _, ok, _, _ in results if ok)
    for filename, ok, elapsed, output in results:
        mark = "✅" if ok else "❌"
        test_count = (output.count("✅ test_") + output.count("PASS test_"))
        print(f"{mark} {filename:<45} ({test_count} تست، {elapsed:.1f} ثانیه)")

    print(f"\n{total_passed}/{len(results)} فایل با موفقیت پاس شدن.")
    total_individual_tests = sum((output.count("✅ test_") + output.count("PASS test_")) for _, _, _, output in results)
    print(f"مجموعِ تست‌های جداگانه‌ی پاس‌شده: {total_individual_tests}")

    if total_passed < len(results):
        print("\n❌ حداقل یه فایل fail شد. برای جزئیات به خروجیِ بالا نگاه کن.")
        return 1

    print("\n✅ همه‌ی فایل‌های تست با موفقیت پاس شدن.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
