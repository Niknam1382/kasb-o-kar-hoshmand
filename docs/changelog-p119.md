# چنجلاگِ پ۱۱۹ — تحویلِ اعلان بی‌قفلِ طولانی، تجمیعِ UPDATEهایِ انقضا، دامنهٔ اجرایِ دستهٔ ادمین (۲۰۲۶-۱۱-۱۸)

سه قلمِ بازمانده از یافته‌هایِ ۵ و ۱۲ِ بازرسیِ ۱۴۰۵-۰۸-۱۴ که در پ۱۱۸ عمداً باز گذاشته شدند (هر سه
نیاز به بازآراییِ رفتار داشتند، نه یکِ اصلاحِ یک‌خطی). هیچ‌کدام مایگریشن لازم نداشت.

## ۱) صندوقِ اعلان‌ها: ارسالِ شبکه دیگر زیرِ قفل نیست (یافتهٔ ۱۲)
`notification_service.send_due` یکِ `SELECT … FOR UPDATE SKIP LOCKED` تا `DUE_LIMIT = 200` ردیف را
قفل می‌کرد و **همهٔ ۲۰۰ ارسالِ شبکه‌ای را داخلِ همان تراکنش** انجام می‌داد؛ وضعیتِ هر ردیف فقط در
حافظه عوض می‌شد و یکِ `flush()` در پایان. دو پیامد:

1. قفلِ ردیف‌ها تا چندِ دقیقه باز می‌ماند (با RTT واقعیِ تلگرام، ۲۰۰ پیام ≈ چندهزار مرتبه رفت‌وبرگشت).
2. کرش/خطا/ری‌استارت پیش ازِ commit ⇒ هیچ وضعیتی نوشته نشده بود، پس **هر ۲۰۰ پیامِ آنِ دور دوباره
   می‌رفتند** — از جمله «سفارشت پرداخت شد».

الان همان دو فاز، به همان ترتیبِ امن:

    فازِ ۱ (زیرِ قفل):  SELECT … FOR UPDATE SKIP LOCKED
                        status = "sending"، next_attempt_at = now + ۳۰۰s
                        ⇒ extractِ مقادیرِ لازم در یکِ list و  commit  (قفل‌ها آزاد می‌شوند)
    فازِ ۲ (بی‌قفل):    برایِ هر ردیف: send_message ⇒ یک UPDATEِ وضعیت + commit

ردیفِ گیرکرده در `sending` (پروسهٔ کشته‌شده) در ابتدایِ دورِ بعد با همان `UPDATE … WHERE status =
'sending' AND next_attempt_at <= now` به صفِ عادی برمی‌گردد ⇒ تضمینِ «دست‌کمِ یک‌بار» جایش را به
«بیشتر ازِ پیام‌هایِ یکِ دور تکرار نمی‌شود» می‌دهد. دو قیدِ رفتاری که عمداً حفظ شدند:

• نبودِ رباتِ فروشگاه (`customer_bot` ⇒ None) هرگز ردیف را `failed` نمی‌کند؛ فقط `attempts` و
  `next_attempt_at` جلو می‌رود (تستِ ۲ از ۴ تستِ این فاز همین را پین می‌کند).
• `sent_at` همچنان با زمانِ واقعیِ سرور نوشته می‌شود، و `next_attempt_at` با `now`ِ پاس‌داده‌شده —
  تا حلقهٔ backoffِ زمان‌محورِ تستِ پ۲۰ نشکند.

`stats()` یکِ کلیدِ تازه گرفت: `sending` (پنلِ ادمینِ «📬 صفِ اعلان» تنها `pending/failed/sent` را
می‌خواند ⇒ بی‌تغییر). `_defer` حذف شد: تنها مصرف‌کننده‌اش همین تابع بود و حالا منطقِ backoff در
خودِ `UPDATE`هایِ عبارت‌محور است.

## ۲) انقضایِ شارژها: یکِ UPDATE به‌ازایِ هر صاحبِ حساب (یافتهٔ ۱۲)
`wallet_service.expire_stale_charges` به‌ازایِ هر بسته‌یِ منقضی یکِ
`UPDATE shop_owners SET wallet_balance_toman = greatest(0, … - amount)` می‌زد؛ با ۵۰۰ فروشگاهِ
سه‌بسته‌ای یعنی ۱۵۰۰ UPDATE که ۱۰۰۰تایشان رویِ سطرهایِ تکراری و هر بار با خواندنِ دوبارهٔ سطر. حالا
جمعِ بسته‌ها در `totals_by_owner` درمی‌آید و بعد ازِ نوشتنِ ردیف‌هایِ دفتری، دقیقاً یکِ UPDATE
به‌ازایِ هر صاحبِ حساب اجرا می‌شود. **ردیفِ دفتر دست‌نخورده است** (به‌ازایِ هر بسته یکِ
`EXPIRY` با `idempotency_key = expiry:{charge_id}`) — چون تاریخچهٔ «کدامِ بسته کی سوخت» برایِ
مالکِ فروشگاه سندِ مالی است.

سنجشِ این فاز با شمارشِ statement: دو بسته از یکِ حساب ⇒ **MEASURED ۶ statement در کلِ کارِ انقضا**
و دقیقاً **یک** `UPDATE shop_owners` (پیش‌تر دو تا).

## ۳) اجرایِ دستهٔ اعتبارِ ادمین هم دامنه دارد (یافتهٔ ۵)
`credit_batch_service.select_owner_ids` از پ۲۱-F دامنهٔ ادمینِ عملیاتی را رویِ **مجموعهٔ هدف**
اعمال می‌کرد، ولی `at_go:` (تایید و اجرا) و `at_no:` (انصراف) هیچ بازبینیِ تازه‌ای نداشتند ⇒ یک
ادمینِ دامنه‌دار که `batch_id` دستهٔ سوپرادمین را ببیند (پیامِ پیش‌نمایش در چتِ همان سوپرادمین است
و کال‌بک قابلِ دست‌کاری) می‌توانست آن را اجرا یا لغو کند. توابعِ سرویس را لمس نکردم (مرزِ امنیتی
در همین هندلرهاست، همان‌جا که هویتِ عامل معلوم است) و یکِ نگهبانِ مشترک اضافه شد:

    app/bots/main_bot/handlers/admin_time.py::_outside_actor_scope(session, actor_id, batch_id)
      ⇒ scope = admin_role_service.scope_for(actor)      # None = سوپرادمین/بی‌دامنه ⇒ همیشه False
      ⇒ رد اگر created_by != actor  یا  owner_ids ⊄ scope

«دستهٔ نبود» False برمی‌گرداند تا پیامِ درست از خودِ `execute/cancel` بیاید (نه یکِ انکارِ مبهم).

## تست
`tests_manual/test_p119_outbox_lease_and_bounds.py` — ثبت‌شده در `run_all_tests.py`:

| تست | چه را می‌بندد |
|---|---|
| `test_send_due_commits_per_row_and_reclaims_lease` | شکستِ ارسال همان‌جا commit می‌شود؛ ردیفِ `sending`ِ بی‌مهلت دوباره برداشته می‌شود |
| `test_missing_bot_never_marks_failed` | نبودِ ربات ⇒ تا بیش ازِ `MAX_ATTEMPTS` دور هم `pending` می‌ماند |
| `test_expiry_writes_one_owner_update_per_account` | دو بسته ⇒ یکِ UPDATEِ صاحبِ حساب + دو ردیفِ `EXPIRY` + موجودیِ صفر |
| `test_batch_execute_is_scope_and_owner_bound` | دستهٔ خودش در دامنهٔ خودش ✔ / دستهٔ ادمینِ دیگر ✘ / هدفِ بیرونِ دامنه ✘ / سوپرادمین ✔ |

نتیجه: **MEASURED ۴/۴ PASS** (`run_one.py`). بازگشت‌هایِ لمس‌شده از این تغییر، جدا هم اجرا شدند:
`test_p20_performance_outbox.py` ⇒ **MEASURED ۷/۷**، `test_p20_money_integrity.py` ⇒ **MEASURED ۸/۸**،
`test_p21_growth.py` ⇒ **MEASURED ۶/۶**، `test_p21_ops.py` ⇒ **MEASURED ۵/۵**.

## فایل‌ها
`app/services/notification_service.py` · `app/services/wallet_service.py` ·
`app/bots/main_bot/handlers/admin_time.py` · `tests_manual/test_p119_outbox_lease_and_bounds.py` ·
`tests_manual/run_all_tests.py`

## چیزی که تغییر نکرد
هیچ ستون/جدولی اضافه یا حذف نشد؛ `DUE_LIMIT`، `MAX_ATTEMPTS` و جدولِ backoff دست‌نخورده‌اند؛
صفحهٔ «📬 صفِ اعلان» در پنلِ ادمین همان چهار خطِ قبلی است.
