# TEST_RESULTS — این نشست (P18 → «master prompt»)

تاریخ: ۲۰۲۶-۱۱-۰۱ · همه‌یِ اعداد **MEASURED** هستند (من اجرا کردم)، مگر جایی که «NOT RUN» نوشته شده.

## ۱) محیطِ اجرا

| | |
|---|---|
| میزبان | Windows 11 (10.0.26200)، x64، Git Bash + PowerShell |
| رانتایمِ تست | Docker Desktop ← ایمیج `python:3.12-slim` (همان `Dockerfile`ِ پروژه، `USER app`) |
| دیتابیس | `postgres:16` در همان compose، پورت فقط `127.0.0.1:5432` |
| متغیرهایِ تست | `ADMIN_TELEGRAM_IDS=12345` (تصریفِ `run_all_tests.py`)، `ENCRYPTION_KEY` از fallbackِ محیطیِ پروژه، `RUN_MODE` روی polling |
| منبعِ کد | شاخهٔ `production-hardening` (از `p18-fixes`)؛ no push/merge/deploy |

## ۲) دستوراتِ دقیق

```powershell
docker compose build
docker compose run --rm bot alembic upgrade head
docker compose run --rm -e ADMIN_TELEGRAM_IDS=12345 bot python tests_manual/run_all_tests.py

# گیت‌هایِ استاتیکِ اختصاصیِ پروژه (رویِ هاست، Python 3.12)
python scripts/lint_names.py
python scripts/check_refs.py
python scripts/check_attrs.py
python scripts/audit_ai_commit.py

# lint (ruff فقط داخلِ کانتینر نصب می‌شود؛ در ایمیجِ production نیست)
docker compose run --rm bot python -m pip install --user --no-cache-dir ruff==0.16.4
docker compose run --rm bot python -m ruff check .          # و --statistics
docker compose run --rm bot python -m ruff format --check . # فقط گزارش؛ اجرا نشد
```

## ۳) نتیجه‌ها

| چک | بیس‌لاین (شروعِ این کار) | پایانِ این کار | جزئیات |
|---|---|---|---|
| `run_all_tests.py` | **۷۹/۷۹ فایل، ۵۰۷ تست ✅** (پس از واحدِ ۳A؛ پیش‌تر ۷۷/۴۹۲ و ۷۸/۴۹۹) | **۸۱/۸۱ فایل، ۵۲۵ تست ✅**، صفر fail، صفر skip | +۴ فایل تستِ جدید در این کار (زیر) |
| `scripts/lint_names.py` | OK | OK | نام‌هایِ تعریف‌نشده: صفر |
| `scripts/check_refs.py` | OK (215 فایل) | OK (221 فایل) | ارجاعِ شکسته: صفر |
| `scripts/check_attrs.py` | OK (215 فایل) | OK (221 فایل) | ویژگی/ستونِ ناموجود: صفر |
| `scripts/audit_ai_commit.py` | OK | OK | هیچ فراخوانیِ AI قبلِ `commit()` نیست |
| `alembic upgrade head` | head `c2e5a8b1d4f7` | head **`f9c4a7d2b5e8`**، `alembic heads` تک‌head | ۴ مایگریشنِ افزودنیِ جدید؛ رویِ دیتابیسِ واقعیِ بازگردانی‌شده هم اجرا شد |
| `docker compose build` + بوتِ واقعی | — | ایمیجِ تازه بالا آمد، ۳ رباتِ فعال بارگذاری و polling شروع شد | دو لاگِ «chat not found» از رکوردِ قدیمیِ خودِ کاربر (مدیریت‌شده، بی‌افتادگی) |
| `ruff check .` | **۲۶۰ finding** (۲۳۴ E501، ۱۷ F401، ۷ F841، ۲ F541) — در `app/`: ۱۳۷ | **انجام نشده در پایانِ کار** (NOT RUN دوباره) | lint سبز نیست؛ بیس‌لاینِ تاریخی است. طرحِ رفع: `REMAINING_ISSUES.md` P2-1 |
| `ruff format --check .` | ۱۸۹ فایل «باید فرمت شود» | همين‌طور (عمداً اجرا **نشد**) | فرمتِ سراسری = تغییرِ آرایشیِ گسترده؛ طبقِ قانونِ «بازنویسیِ گسترده نکن» انجام نشد |
| mypy / pyright | — | **NOT RUN** | در پروژه تعریف نشده‌اند؛ جایگزین: چهار گیتِ استاتیکِ بالا. اضافه‌کردنشان وابستگیِ جدید + صدها خطایِ اولیه است |
| تستِ بارِ مسیرِ کیف‌پول (PHASE 12) | — | **MEASURED** رویِ دیتابیسِ ایزوله: سقف ≈ **300 عملیات/s**، p50 از 24ms (همزمانی 10) تا 2.8s (همزمانی 2000)، `errors=0` | `scripts/loadtest_wallet_paths.py` → `SCALABILITY_AND_LOAD_TEST_REPORT.md` §۳ |
| تستِ بارِ HTTP | — | **NOT RUN** (عمدی: `RUN_MODE=webhook` رویِ میزبانِ dev، `set_webhook`ِ توکنِ واقعی را عوض می‌کند = اثرِ بیرونیِ ممنوع) | دلیل و طرحِ بعدی در همان گزارش §۱ و §۶ |

## ۴) فایل‌هایِ تستِ این کار و معنی هرکدام

| فایل | تست | چه چیزی را قفل می‌کند |
|---|---|---|
| `tests_manual/test_p2_credit_expiry_preserved.py` | ۷ | **PHASE 2**: مدت = `validity_months × ۳۰ روز` از لحظهٔ شارژ، پیش‌فرضِ ۱۲ قفل، بسته‌هایِ مستقل، FIFO، «بستهٔ منقضی مصرف نمی‌شود»، ایدمپوتنسیِ جاب + ردیفِ `EXPIRY`، احترام به توقفِ زمان، مرزهایِ یادآوریِ یک‌بارمصرف |
| `tests_manual/test_p5_min_recharge.py` | ۱۰ | **PHASE 5A**: ردِ سمتِ سرویس در هر سه روش، قبولِ دقیقِ حداقل، تغییرِ حداقل توسطِ ادمین، ردِ خارجِ بازه، دامنه فقط `WALLET_TOPUP`، هم‌راستاییِ UI با سرویس (پیش‌فرض‌ها + callbackِ جعلی + متنِ راهنما)، کفِ ایمنیِ ۱٬۰۰۰، پیش‌فرضِ ۵۰٬۰۰۰ |
| `tests_manual/test_p5_ledger_integrity.py` | ۸ | **PHASE 5E/7**: پرشدنِ `currency/status/payment_id/idempotency_key`، فقط‌افزودنی (ویرایش/حذف ⇒ خطا)، یکتا بودنِ کلید، کلیدِ خارجیِ ناموجود ⇒ رد، همسنجیِ سالم/دو نوع انحراف، تراتل + هشدار + «اصلاحِ خودکار نمی‌کند»، پنلِ ادمین + ممیزی |
| `tests_manual/test_p5_commission.py` | ۱۰ | **PHASE 5D + چک‌لیستِ ۱۰–۱۹ و ۲۲**: ریاضیاتِ اعشاری، خاموش ⇒ هیچ، رزرو ⇒ hold بدونِ کسر، تسویه ⇒ دقیقاً یک‌بار، گذارهایِ تکراری ⇒ بدونِ کسرِ دوباره، snapshotِ نرخ، لغو/انقضا ⇒ آزادسازی، استرداد ⇒ ردیفِ معکوس، اعتبارِ ناکافی ⇒ ردِ رزرو و ردِ تسویه، کفِ صفرِ موجودی، پنلِ ادمین (توگل + ۰/۰٫۵/۱۵۰) |

جمعِ تست‌هایِ این کار: **۳۵ تستِ جدید**. مجموعِ نهاییِ مجموعه: **۸۱ فایل / ۵۲۵ تست** (بیس‌لاینِ نشستِ قبل: ۶۵ فایل / ۴۱۲ تست).

## ۵) چیزی که «NOT RUN» مانده (و چرا)

- بارِ **HTTP**: فعال‌کردن `RUN_MODE=webhook` رویِ میزبانِ dev، `set_webhook(...)` را رویِ
  توکن‌هایِ **واقعی** می‌نویسد و مقصدِ آپدیتِ رباتِ زنده را عوض می‌کند ⇒ عمداً انجام نشد.
- `ruff check` در پایانِ کار (بیس‌لاینِ ۲۶۰ مورد ثبت شده؛ کدِ جدید باید بعداً جدا بررسی شود).
- تستِ coverage، تستِ نفوذ، تمرینِ `alembic downgrade` رویِ دادهٔ واقعی، و استقرارِ واقعیِ webhook
  با TLS ⇒ همه **NOT RUN** و در `PRODUCTION_READINESS_REPORT.md` به‌عنوانِ بلاکر/محدودیت ثبت شده‌اند.

## ۶) باگ‌هایی که همین تست‌ها در کدِ محصول پیدا و رفع کردند

| باگ | کجا | قفلِ رگرسیون |
|---|---|---|
| گذارِ وضعیتِ سفارش با ردیفِ خالی `IndexError` می‌داد | `invoice_service.build_invoice_data` | (P18 · B6) فاکتورِ خالی در `test_p18_pdf_invoice.py` |
| Vazirmatn گلیفِ `✓` را ندارد ⇒ جعبهٔ خالی در فاکتور | `invoice_service` | `test_no_missing_glyph_warnings` |
| کلیدِ ایدپوتنسیِ شارژ هدیهٔ گروهیِ K1 را می‌شکست (مرجعِ مشترکِ همهٔ مخاطبان) | `wallet_service.add_charge` | `test_new_ledger_columns_are_filled_on_insert` (دو فروشگاه‌دار، یک مرجع) |
| موجودیِ کش‌شده می‌توانست زیرِ صفر برود | `wallet_service._apply_balance_delta` | `test_cached_balance_can_never_go_negative` |
| `PENDING → awaiting_payment` در ماشینِ حالت مجاز نیست ⇒ رزرو هرگز اجرا نمی‌شد | `checkout.py` + `order_transition_service` | `test_p5_commission` (رزرو از مسیرِ واقعی چک‌اوت) |
| (P18) `from aiogram.types import Bot` ⇒ ImportError سراسری | `handlers/admin.py` | کل مجموعه |
| (P18) `main_bot: Bot` در هندلرهایِ روترِ اصلی تزریق نمی‌شود | `handlers/admin.py` | `test_p18_bot_branding.py` |

## ۷) محدودیتِ افشاشده

کیفیتِ داوری‌ها به پوششِ همان ۸۱ فایل محدود است. پوششِ خط‌به‌خط (coverage) ابزارسنجی‌شده **NOT RUN**
(coverage در `requirements-dev.txt` نیست و اجرایِ آن رویِ همین harness بدونِ pytest نیاز به کارِ جدای دارد).
«۵۲۵ تست سبز» یعنی «هیچ‌کدام از ادعاهایِ ثبت‌شده در تست‌ها نشکست»، نه «کد جای‌جای درست است».

---

# P20 — اجرایِ دوبارهٔ کامل (۲۰۲۶-۱۱-۰۱، شاخهٔ `p20-hardening`)

## ۸) نتیجه‌ها (MEASURED)

| چک | عددِ این اجرا | جزئیات |
|---|---|---|
| `run_all_tests.py` | **۸۵/۸۵ فایل، ۵۵۹ تست ✅** (صفر fail، صفر skip) | بیس‌لاینِ این نشست ۸۲/۵۳۶ بود؛ +۳ فایل و +۲۳ تست در P20 |
| `scripts/check_refs.py` / `check_attrs.py` / `lint_names.py` / `audit_ai_commit.py` | هر چهار **OK** (232 فایل) | در ابتدایِ و انتهایِ هر گروه اجرا شد |
| `alembic upgrade head` (رویِ `kasbokar` و `kasbokar_load`) | head = **`d4a8c2e6f9b3`**، `alembic heads` تک‌head | چهار مایگریشنِ افزودنیِ این دوره: `b2e6f9c1d4a8` (رمزنگاری + زنجیرهٔ هش)، `c3f7a1d5b8e2` (ایندکس‌ها)، `d4a8c2e6f9b3` (outbox) |
| `scripts/verify_audit_chain.py` | زنجیرهٔ هشِ دفترِ ممیزی سالم؛ دست‌کاریِ ردیف ⇒ کشف می‌شود | تستِ `test_audit_chain_links_and_detects_tampering` |
| بارسنجیِ مسیرِ کیف‌پول (P12) | سقف ≈ ۳۰۰ کسر/s | بیس‌لاینِ قبلی، بدونِ تغییر |
| **بارسنجیِ مسیرِ کاملِ پیام (P20-F)** | **≈ ۱۴۵ پیام/s در یکِ پروسه**، منحنیِ صاف ۱۰→۴۰۰ همزمانی، `errors=0`، «همه روی یکِ فروشگاه» −۱۴٪ | `scripts/loadtest_message_path.py` رویِ `kasbokar_load` (ایزوله) → §۹ گزارشِ ظرفیت |
| pgbench رویِ همان میزبان | ۲٬۱۷۹ / ۱٬۹۷۳ / ۱٬۹۳۲ تراکنش/s در c=20/50/100 | بامِ دیتابیس ~۱۳× بامِ اپ ⇒ DB گلوگاهِ اول نیست |
| پروفایلِ مرحله‌به‌مرحلهٔ یکِ پیام | ۱۲٫۶ms (≈۹ms CPUِ پایتون/ORM + ≈۳٫۵ms دیتابیس) | علتِ اینکه بامِ اپ «پروسه‌محور» است نه «دیتابیس‌محور» |
| آزمونِ `synchronous_commit=off` | بدونِ تغییرِ معنادار (۱۳۳→۱۴۵ rps در c=1۰، یکسان در c=5۰) | فرضیهٔ «دیسکِ داکر» **رد شد** |
| آزمونِ استخر | ۲۰+۳۰ ⇒ ۴۸ rps در c=5۰ · ۲۰+۱۰ ⇒ ۸۲ · ۲۰+۰ ⇒ ۱۳۶ · ۵۰+۰ ⇒ ۱۴۱ | پیش‌فرضِ کد: **۲۵+۰**، `pool_timeout=15` |
| بارِ HTTP / تستِ زندهٔ بله / تأخیرِ واقعیِ AI | **NOT RUN** (عمدی — دلایلِ یکسان با §۵، به‌علاوهٔ هزینهٔ واقعیِ توکن) | طرحِ گرفتنشان در `REMAINING_ISSUES.md` §P20 |

## ۹) نکتهٔ عملیِ کشف‌شده در این اجرا (و چرا یک فایل «دروغ» گفت)

در اجرایِ اولِ سوئیت، `test_p19_bale_shop_bot.py` با **۰ تست** fail شد: `reset_database()`
(TRUNCATE … RESTART IDENTITY CASCADE) با تراکنش‌هایِ رباتِ درحالِ polling **بن‌بست** کرد
(`DeadlockDetectedError`). کد سالم بود؛ محیطِ اجرا اشتباه بود. با `docker compose stop bot`
همان فایل هر ۸ تستش پاس شد و سوئیتِ نهایی ۸۵/۸۵ شد. **قاعدهٔ جدیدِ اجرایی:** قبل از سوئیت،
بات را خاموش کن (این در `docs/PROGRESS.md` §۱۲-۴ هم ثبت شد).

## ۱۰) تست‌هایِ تازهٔ P20 (۲۳ مورد) + یک تقویتِ RBAC

| فایل | تست | چه چیزی را قفل می‌کند |
|---|---|---|
| `test_p20_money_integrity.py` | ۸ | تاییدِ دوبارهٔ پرداخت ⇒ یک شارژ، کلیدِ ایدمپوتنسیِ شارژ، فروشِ آخرینِ موجودی ⇒ یک نفر، تاییدِ دستی ⇒ آزادسازیِ holdِ کمیسیون، تسویه با اعتبارِ ناکافی ⇒ آزادسازی، هدیه ⇒ بازه + پیش‌نمایش + nonce، دابل‌تپِ اعتبارِ آزمایشی ⇒ یک‌بار، کپشنِ بلند ⇒ بریده می‌شود نه حذف |
| `test_p20_security_observability.py` | ۸ | اسکرابِ هر شکلِ سکرت، فیلتر رویِ root handler، لاگِ JSON با correlation، پنجرهٔ rate-limit، ۴۲۹ پس از سقف، `/metrics` پنهان/محافظت‌شده، زنجیرهٔ هشِ ممیزی + کشفِ دست‌کاری، رمزنگاریِ رازِ وب‌هوک + بازنویسیِ ردیف‌هایِ ساده‌متنِ قدیمی |
| `test_p20_performance_outbox.py` | ۷ | چرخهٔ outbox + dedupe، backoff و «شکستِ بلندگو‌مد» (نه گم‌شدن)، سقوطِ خبرِ سفارش به صف، تخلیه توسطِ جابِ دوره‌ای، «قابل‌استفاده/در آستانهٔ انقضا»، `lazy="raise"` رویِ محصولات، و **پنلِ ادمینِ صف + دکمهٔ تلاشِ دوباره** |
| `test_admin_rbac.py` (تقویت) | +۱ ادعا | ادمینِ عملیاتی نمی‌تواند `admin_notification_queue` / `admin_notification_retry` / `admin_branding_sync` را با callbackِ جعلی اجرا کند — حتی `callback.answer()` هم نمی‌گیرد |
