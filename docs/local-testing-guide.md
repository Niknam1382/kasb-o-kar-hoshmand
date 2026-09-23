# راهنمای تست‌های محلی

## چرا این تست‌ها به توکنِ واقعیِ تلگرام نیاز ندارن

`tests_manual/harness.py` یه `FakeSession` پیاده‌سازی می‌کنه — جایگزینِ
`BaseSession` واقعیِ aiogram — که همه‌ی متدهای API تلگرام (`SendMessage`،
`SendPhoto`، `GetChatMember`، `GetFile`، دانلودِ فایل، و...) رو بدونِ زدنِ
درخواستِ واقعی شبیه‌سازی می‌کنه و نتیجه رو ضبط می‌کنه تا توی تست‌ها بشه چکش
کرد. یعنی تست‌ها مستقیماً روی **دیسپچر و هندلرهای واقعیِ پروژه** اجرا می‌شن،
نه یه نسخه‌ی ساده‌شده — تنها چیزی که فیک شده، لایه‌ی شبکه‌ست.

تنها پیش‌نیازِ واقعی یه **PostgreSQL محلی** برای اجرای واقعیِ کوئری‌هاست
(چون تست‌ها روی SQLAlchemy واقعی اجرا می‌شن، نه موکِ ORM).

## پیش‌نیازها

```bash
# یه دیتابیسِ جداگانه برای تست بساز (هیچ‌وقت رویِ دیتابیسِ پروداکشن تست نزن!)
psql -U postgres -c "CREATE DATABASE kasbokar_test;"
```

## متغیرهای محیطیِ لازم برای تست

```bash
export DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost/kasbokar_test"
export MAIN_BOT_TOKEN="123456789:AAtestFAKEtokenFAKEtokenFAKEtokenFAKE"
export ENCRYPTION_KEY="$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
export ADMIN_TELEGRAM_IDS="12345"
export WEBHOOK_BASE_URL="https://example.com"
export RUN_MODE="polling"
export AUTH_MODE="test"
```

نکته: `ADMIN_TELEGRAM_IDS=12345` باید با `ADMIN_TG_ID` ای که توی فایل‌های
تستِ مربوط به ادمین استفاده شده مچ باشه.

## اجرا

```bash
alembic upgrade head                      # مایگریشن‌ها رو روی دیتابیسِ تست اعمال کن
python3 tests_manual/run_all_tests.py     # کلِ مجموعه‌ی تست رو اجرا کن
```

هر فایلِ تست رو هم می‌شه تکی اجرا کرد:

```bash
python3 tests_manual/test_message_debounce.py
```

## چرا هر فایل یه ساب‌پروسسِ جداست

روترهای aiogram آبجکت‌های سطحِ‌ماژول هستن و هر روتر فقط یه‌بار می‌تونه به یه
دیسپچرِ پرنت وصل بشه. برای همین `run_all_tests.py` هر فایل رو با یه پروسه‌ی
پایتونِ تازه اجرا می‌کنه (نه import مستقیم)، دقیقاً همون‌طوری که در پروداکشن
فقط یه‌بار در طولِ عمرِ پروسه دیسپچر ساخته می‌شه.

## چه چیزی پوشش داده می‌شه

| فایل | چی رو تست می‌کنه |
|---|---|
| `test_start_registration.py` | ثبت‌نامِ کامل، نرمالایزِ شماره‌موبایل، گیتِ کانالِ اجباری |
| `test_shop_bot_and_products.py` | افزودن/ویرایش/حذفِ محصول، موجودیِ انبار |
| `test_fsm_escape.py` | خروجِ اضطراری از یه state گیرکرده با دکمه‌ی منو |
| `test_message_debounce.py` | ترکیبِ پیام‌های پشت‌سرهمِ مشتری |
| `test_photo_handling.py` | فورواردِ عکسِ مشتری + تحلیلِ هوشمندِ تصویر |
| `test_voice_handling.py` | رونویسیِ پیامِ صوتی |
| `test_discount_amount_bug.py` | صحتِ محاسبه‌ی تخفیف (یه‌بار، نه دوبار) |
| `test_excel_export.py` | استایل و صحتِ داده‌ی خروجیِ اکسل |
| `test_admin_owner_management.py` | تعلیق/رفعِ تعلیق، اعتبارِ هدیه |
| `test_payment_approval.py` | تاییدِ/ردِ پرداختِ کارت‌به‌کارت |
| `test_admin_channel_management.py` | افزودن/حذفِ کانالِ اجباری |
| `test_admin_pricing.py` | طرح‌های قیمت‌گذاری |
| `test_admin_settings.py` | منوی تنظیماتِ ادمین (کلیدها، محدودیت‌ها) |
| `test_referral_and_trial.py` | پیشنهادِ آزمایشی + پاداشِ معرف |
| `test_card_to_card_improvements.py` | فرمتِ HTML رسیدِ کارت‌به‌کارت، راهنماییِ ارسالِ عکس به‌جای متن |
| `test_order_product_id_matching.py` | تطبیقِ شناسه‌ی محصول توسطِ هوش مصنوعی در تشخیصِ سفارش |
| `test_wallet_service.py` | منطقِ پایه‌ی کیف‌پول: شارژ، کسر (FIFO)، انقضا، یادآوری |
| `test_wallet_integration.py` | یکپارچه‌سازیِ کیف‌پول با جریانِ پیام‌رسانی: قطعِ دسترسی، کسرِ دقیق، محاسبه‌گرِ هزینه |
| `test_order_reservation.py` | رزروِ خودکارِ موجودی، وضعیت‌های رسمیِ سفارش (تایید/رد/انقضا/پیشروی) |
| `test_consultation_mode.py` | تفاوتِ پرامپت/طبقه‌بندی‌کننده بینِ حالتِ فروش و مشاوره، تغییرِ حالت از پنل |
| `test_kill_switches.py` | بستنِ ثبت‌نام، غیرفعال‌کردنِ شارژِ کیف‌پول، حالتِ تعمیرِ سراسری |
| `test_moderation_and_audit_log.py` | نگهبانِ محتوا (WARN/BLOCK/REVIEW) + ثبتِ رویداد در گزارشِ ممیزی |
| `test_wallet_history_and_finops.py` | نمایشِ تاریخچه‌ی تراکنش به فروشگاه‌دار + آمارِ مالیِ سبکِ ادمین |
| `test_webhook_idempotency.py` | جلوگیری از پردازشِ دوباره‌ی یه آپدیتِ تکراریِ تلگرام |
| `test_ai_retry_and_fallback.py` | تلاشِ مجددِ خودکار روی خطای موقتی + سوییچ به سرویسِ پشتیبان |

## محدودیت‌های شناخته‌شده

- **اعتبارسنجیِ توکنِ ربات فروشگاهی** (`save_shop_bot_token` در `panel.py`) یه
  `getMe` واقعی به `api.telegram.org` می‌زنه که توی محیطِ سندباکسِ توسعه در
  دسترس نیست. تست‌های مربوط به فروشگاه‌بات، ردیفِ `ShopBot` رو مستقیم از طریقِ
  لایه‌ی سرویس می‌سازن (بایپس‌کردنِ همین یه مرحله‌ی شبکه‌ای) و از اونجا به بعد
  از هندلرهای واقعی استفاده می‌کنن.
- تستِ `admin_owner_unsuspend` یه Bot واقعی می‌سازه و تلاش می‌کنه polling رو
  شروع کنه (که در محیطِ بدونِ دسترسی به تلگرام fail می‌شه، ولی چون
  `asyncio.create_task` بلاک‌کننده نیست، خودِ تست رو متوقف نمی‌کنه).

## اضافه‌کردنِ تستِ تازه

الگو: DB رو با `reset_database()` خالی کن، دیتای موردنیاز رو مستقیم از طریقِ
لایه‌ی سرویس بساز، یه `Update` جعلی با `make_message_update`/`make_callback_update`
بساز و با `dispatcher.feed_update(bot, update)` به دیسپچرِ واقعی بده، و در
نهایت نتیجه رو هم از روی دیتابیس (با یه کوئریِ مستقیم) و هم از روی
`session.sent_messages`/`sent_photos`/... چک کن.
