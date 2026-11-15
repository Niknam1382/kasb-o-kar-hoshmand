# پ۷۹ — ایجنتِ سرور راند ۳: جمعِ شمارنده‌ها بینِ پروسه‌ها (۲۰۲۶-۱۱-۱۵)

## باگِ واقعیِ گرفته‌شده (مهم‌ترینِ خروجِ این فاز)
`server_doctor.inspect()` شمارنده‌ها را از `capacity_service.counters_lines()` می‌گرفت که **کلیدهایش
برچسبِ فارسی** است («رویدادِ نامعتبرِ ردشده»)؛ ولی `_counter_findings` با **نامِ خام** می‌پرسید
(`webhook.rejected`). نتیجه: سه یافتهٔ `webhook_rejected` / `webhook_rate_limited` / `wallet_denied`
در تولید **هرگز** شلیک نمی‌کردند و گزارش «همه‌چیز سبز» می‌داد. حالا `local_counters()` نامِ خام می‌دهد
و برچسب فقط در نمایش ساخته می‌شود.

## جمعِ چندپروسه‌ای
• جدولِ افزودنی `runtime_counter_snapshots` (یکِ ردیف به‌ازایِ هرِ پروسه، `process_key` یکتا) —
  مایگریشن `f8c3a1d6b240`.
• `capacity_service.publish_counters()` در یکِ حلقهٔ ضربانِ ۳۰ ثانیه‌ای که در **همهٔ** پروسه‌ها بالا
  می‌آید (`scheduler.run_counter_heartbeat` در `app/main.py`؛ قبلاً جاب‌ها فقط در core بودند).
• `aggregate_counters()` سهمِ خودِ پروسه را از حافظه می‌گیرد و ردیفِ دیگران را تا ۱۵۰ ثانیه معتبار
  می‌شمارد؛ ردیفِ قدیمی یا JSONِ خراب در شمارهِ «بی‌ضربان» گزارش می‌شود (کم‌گوییِ پنهان نه).
• پنلِ ظرفیت حالا می‌گوید «جمعِ شمارنده‌ها از N پروسهٔ زنده» و عیب‌یاب دو یافتهٔ تازه دارد:
  `counters.scope` (اطلاع) و `counters.stale_rows` (هشدار).

## تست
**MEASURED** — `test_p79_counter_aggregation.py`: ۶/۶ (exit=0)؛ رگرسیونِ باگِ اصلی در
`test_doctor_uses_raw_names_and_reports_scope` ثبت شده است.
