# چنجلاگِ پ۱۲۰ — مرچنت‌آیدی زرین‌پالِ پلتفرم هم در دیتابیس رمز می‌شود (۲۰۲۶-۱۱-۱۸)

آخرین قلمِ بازِ یافتهٔ ۵ِ بازرسیِ ۱۴۰۵-۰۸-۱۴. بقیهٔ همان یافته در پ۱۱۸ بسته شده بود (ماسکِ رازهایِ
`.env` در `observability.scrub`، شمارشِ اتمیکِ کدِ تخفیف) و دامنهٔ دستهٔ ادمین در پ۱۱۹.

## مشکل
`admin_settings` پر از راز است و همه‌شان از پ۱۸ · د(۴) رویِ `EncryptedText` بودند
(`ai_api_key`، `ai_fallback_api_key`، `bale_bot_token`، `platform_card_number` از پ۲۴، …) —
جزِ `zarinpal_merchant_id` که `String(64)` و **خام** می‌خوابید. یعنی:

• هر `pg_dump` / بکاپِ شبانه / بازگردانیِ snapshot، شناسهٔ درگاهِ پلتفرم را به‌صورتِ خوانا با خودش
  می‌برد (راهنمایِ ادمین از پ۱۸ «رازها رمزنگاری می‌شوند» را ادعا می‌کرد).
• مسیرِ تستِ رازِ `.env` (`observability.scrub`) هم آن را نمی‌گرفت، چون مقدارِ درگاه از `.env` نمی‌آید،
  از پنل نوشته می‌شود.

## راهِ فنی (همان الگویِ پ۲۴ برایِ `platform_card_number`)
1. **مایگریشنِ افزودنی** `d7b3f0a4c8e2_p120_merchant_id_text.py`: عرضِ ستون از `VARCHAR(64)` به
   `TEXT`. هیچ ستونی حذف/تنگ نشده و داده‌ای از بین نمی‌رود (`TEXT ⊃ VARCHAR`). رمزِ Fernetِ یکِ
   مرچنت‌آیدی ۳۶ نویسه‌ای ≈۱۴۰ نویسه است، پس این تنها راهِ ممکن است.
   `downgrade` عمداً **no-op** است: برگرداندنِ ستون به `VARCHAR(64)` رویِ ردیفِ رمزنگاری‌شده خطا
   می‌دهد و یکِ ارتقایِ بی‌خطر را به مسیرِ یک‌طرفه تبدیل می‌کرد؛ عرضِ بازِ ستون به‌تنهایی هیچ رفتاری
   را عوض نمی‌کند. (این تنها انحرافِ آگاهانه از الگویِ پ۲۴ است که `downgrade`اش را تنگ می‌کرد.)
2. **مدل**: `zarinpal_merchant_id` ⇒ `EncryptedText`. خواندن/نوشتن شفاف است و **مقدارِ قدیمیِ
   رمزنگاری‌نشده هم خوانده می‌شود** ⇒ نصبِ موجود در لحظهٔ ارتقا هیچ‌چیز را از دست نمی‌دهد.
3. **پاسِ بوت‌آپ**: `admin_settings_service.reencrypt_merchant_id(session)` در `app/main.py`، بلافاصله
   بعد ازِ `shop_bot_service.reencrypt_secrets` (پ۲۰ · B2). دلیلِ بوت‌آپ و نه مایگریشن:
   `ENCRYPTION_KEY` فقط در خودِ ربات در دسترس است؛ اجرایِ دوباره بی‌اثر است (اول با SQLِ خام
   نگاه می‌کند که آیا مقدار `gAAAAA…` است یا نه).

## چیزی که عمداً تغییر نکرد
`shop_bots.zarinpal_merchant_id` (مرچنتِ خودِ فروشگاه) دست‌نخورده ماند: مسیرِ واقعیِ پرداختِ
فروشگاهی از جدولِ تنظیماتِ پرداختِ خودِ فروشگاه می‌گذرد
(`shop_payment_settings.zarinpal_merchant_id_enc` — که **از قبل رمزنگاری‌شده** است و تنها جایی است که
`payments.py` و `main.py` از آن می‌خوانند) و آن ستونِ قدیمی در `shop_bots` بی‌مصرف است. ضمناً هیچ‌جا در کد این ستون‌ها با `WHERE = مقدار` مقایسه نمی‌شوند،
پس رمزنگاری هیچ کوئری‌ای را نمی‌شکند. یکِ کامنتِ کهنه در `models.py` که می‌گفت `bale_provider_token`
رمزنگاری نمی‌شود اصلاح شد (از پ۲۰ `EncryptedToken(512)` است).

## تست
`tests_manual/test_p120_merchant_id_encrypted.py` — ثبت‌شده در `run_all_tests.py`:

| تست | چه را می‌بندد |
|---|---|
| `test_column_is_wide_enough_for_ciphertext` | `information_schema` ⇒ نوعِ ستون `text` است (مایگریشن اجرا شده) |
| `test_write_stores_ciphertext_and_reads_plaintext` | نوشتنِ عادی ⇒ در DB رمز، در ORM متنِ اصلی |
| `test_legacy_plaintext_is_readable_and_gets_encrypted_once` | ردیفِ خامِ قدیمی ⇒ خوانده می‌شود، یک‌بار رمز می‌شود، اجرایِ دوباره بی‌اثر |
| `test_empty_value_is_left_alone` | ستونِ خالی ⇒ هیچ نوشتنی انجام نمی‌شود |

نتیجه: **MEASURED ۴/۴ PASS** (`run_one.py`). در همان اجرا، مایگریشنِ پ۱۲۰ رویِ دیتابیسِ تست
توسطِ `tests_manual/db_env.py` اعمال شد (مسیرِ واقعیِ `alembic upgrade head`).

## دیتابیسِ توسعه
پیش ازِ اعمالِ مایگریشن، `pg_dump` گرفته شد: `C:\Users\nik0228\kasbokar-backups\kasbokar-before-p120.dump`
(**MEASURED ۴۴۶٬۴۷۸ بایت** در ظرفِ دیتابیس و رویِ دیسکِ میزبان). بعد ازِ ارتقا:
`data_type = text` و `alembic_version = d7b3f0a4c8e2` (**MEASURED** با `psql`، و
`alembic heads` ⇒ یکِ head).

## فایل‌ها
`app/database/models.py` · `app/services/admin_settings_service.py` · `app/main.py` ·
`migrations/versions/d7b3f0a4c8e2_p120_merchant_id_text.py` ·
`tests_manual/test_p120_merchant_id_encrypted.py` · `tests_manual/run_all_tests.py` · `README.md`
