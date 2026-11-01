# AUTONOMOUS_PROGRESS — Smart Business (کسب‌وکار هوشمند)

> checkpointِ معتبرِ این کار. هر واحدِ کاری که تمام شد، این فایل به‌روز می‌شود.
> اگر مدل/نشست/context قطع شد، ادامه از همین‌جا است — نه از حافظهٔ گفت‌وگو.

- شروعِ این کار: ۲۰۲۶-۱۱-۰۱
- شاخهٔ کاری: `production-hardening` (از HEAD تمیزِ `p18-fixes` = `b58194b`)
- مخزن: `C:\Users\nik0228\Desktop\نیمه نهایی\qoder\kasb-o-kar-hoshmand_FINAL4\kasb-o-kar-hoshmand`
- وضعیتِ worktree در لحظهٔ نوشتن این خط: فقط همین فایل تغییر کرده؛ هیچ ویرایشِ ناتمامِ دیگری وجود ندارد.

## ۰) برچسبِ نتیجه‌ها (قاعدهٔ سراسریِ این سند)

- **MEASURED** = من خودم اجرا کردم و خروجی‌اش را دیدم.
- **ESTIMATED** = استدلال روی شواهد، بدون اجرا.
- **NOT RUN** = اجرا نشد (و چرا).
- هیچ گزارشی «سبز» نیست مگر اینکه دستور و تعدادِ واقعی‌اش اینجا ثبت شده باشد.

## ۱) PHASE 1 — کشفِ مخزن

### ۱-۱) پشته و نقطه‌هایِ ورود (MEASURED از فایل‌ها)

| جزء | واقعیت |
|---|---|
| زبان/رانتایم | Python 3.12 (`python:3.12-slim`) |
| frameworkِ بات | aiogram 3.30.0 — دو بات: **main bot** (پنلِ ادمین + پنلِ فروشگاه‌دار) و **shop bot**ها (per-shop، با `ShopBotManager`) |
| وب | FastAPI 0.139.2 فقط به‌عنوانِ **transportِ webhook**: `/health`، `/webhook/main`، `/webhook/shop/{shop_bot_id}`، `/webhook/bale`، `/webhook/bale/{path_secret}`، callbackهایِ زرین‌پال |
| «پنل ادمین» | **وب‌داشبورد ندارد.** پنلِ ادمین = منویِ Telegramِ main bot. هر خواستهٔ «admin panel» (PHASE 15، PHASE 20-H) باید رویِ همین پیاده شود |
| دیتابیس | PostgreSQL 16 + SQLAlchemy 2.0.51 async (asyncpg) + Alembic 1.18.5؛ `models.py` = ۶۳ کلاس؛ `migrations/versions` = ۴۲ فایل، **یک head**: `c2e5a8b1d4f7` |
| سرویس‌ها | `app/services/*.py` = ۷۶ فایل (کیف‌پول، پرداخت، سفارش، AI، گزارش، ممیزی، CRM، …) |
| هندلرها | `app/bots/main_bot/handlers/` = ۱۸ فایل، `app/bots/shop_bot/handlers/` = ۶ فایل |
| کارِ زمینه‌ای | `app/services/scheduler.py` — حلقه‌هایِ asyncio (گزارش‌ها، انقضایِ پرداخت/سفارش، پاکسازیِ مکالمه، ممیزیِ بیو، اعتبار/شارژ) با `job_gate_service` (توقفِ گروهی) و `time_freeze_service` (توقفِ زمان) |
| یکپارچه‌سازی‌ها | Telegram/Bale API، زرین‌پال، کاوه‌نگار (OTP)، استخرِ کلیدهایِ AI (OpenAI-compatible: chat/vision/stt)، SMTP (aiosmtplib)، Excel (openpyxl)، PDF (fpdf2 + arabic-reshaper + python-bidi) |
| تست | `tests_manual/` = ۷۷ فایلِ **خودگردانِ بدونِ pytest** (اسکریپت + `harness.py` با FakeSession) و اجراگرِ `run_all_tests.py` |
| ابزارها | ruff 0.16.4 + pre-commit (`requirements-dev.txt`؛ در ایمیجِ production نصب نمی‌شود)، چهار گیتِ استاتیکِ اختصاصی در `scripts/` |
| CI | `.github/workflows/ci.yml`: pip install ← ruff (عمداً `continue-on-error`) ← `alembic upgrade head` ← `run_all_tests.py` رویِ Postgres 16 سرویس |
| استقرار | `docker-compose.yml` (bot + db، پورتِ db فقط رویِ 127.0.0.1)، Dockerfile با `USER app` (غیرroot)، `entrypoint.sh` (بررسیِ تنظیمات + migration) |

### ۱-۲) جریان‌هایِ حیاتی که ردیابی شد

1. **ثبت‌نامِ فروشگاه‌دار/مشاور** → `handlers/start.py` (ویزارد) → `otp_service.send_phone_code` (کاوه‌نگار یا نمایشِ کد در چت) → `shop_owner_service.complete_registration` → کیف‌پولِ آزمایشی + معرف.
2. **شارژِ کیف‌پول** → `panel.py` (مبلغ ← کد تخفیف ← روشِ پرداخت) → `payment_service.create_*` → پرداخت (زرین‌پال/بله‌پی/کارت‌به‌کارتِ دستی) → تأییدِ سمتِ سرور → `wallet_service.add_charge` (**بسته‌یِ مستقلِ WalletCharge**) + `WalletTransaction` (+۴).
3. **مصرف** → `customer.py` (چت/ویس/تشخیصِ سفارش) → `estimate_*_cost` → `wallet_service.deduct` (**FIFO با `SELECT … FOR UPDATE`**) → یادآوریِ موجودیِ کم/تمام.
4. **سفارش** → `checkout.py` → `OrderConsultation` (گروهی با `cart_checkout_group_id`) → تایید/پرداخت/ارسال/استرداد با `order_transition_service` و گذارهایِ متمرکزِ `order_state.py`.
5. **رسید** → `payments.py` (عکس/متن) → `receipt_ai_service` (اختیاری، capability=vision) → تصمیمِ فروشگاه‌دار؛ `payment_event_log` با `correlation_id`.
6. **پشتیبانِ مالی** → `accounting_service`، `stats_service`، `excel_export_service` (با خنثی‌سازیِ تزریقِ فرمول)، `invoice_service` (PDF/HTML).

### ۱-۳) بیس‌لاینِ اجراشده (MEASURED، رویِ همین commit)

| چک | دستور | نتیجه |
|---|---|---|
| تستِ کامل | `docker compose run --rm -T -e ADMIN_TELEGRAM_IDS=12345 bot python tests_manual/run_all_tests.py` | ✅ **۷۷/۷۷ فایل، ۴۹۲ تست پاس، صفر شکست/اسکپ** (چند دقیقه پیش، همان HEAD که این کار از آن شروع شد) |
| گیت‌هایِ استاتیک | `python scripts/{lint_names,check_refs,check_attrs,audit_ai_commit}.py` | ✅ هر چهار «OK» (۲۱۷ فایل) |
| مایگریشن | `docker compose run --rm bot alembic upgrade head` رویِ دیتابیسِ واقعیِ بازیابی‌شده | ✅ از `d9e3a6b8c2f5` تا `c2e5a8b1d4f7` (۱۱ مایگریشنِ P18) بدونِ خطا |
| لینت | `python -m ruff check .` داخلِ کانتینر (ruff 0.16.4) | ❌ **۲۶۰ مورد**: ۲۳۴ E501 (بلندیِ خط)، ۱۷ F401 (import بلااستفاده)، ۷ F841 (متغیر بلااستفاده)، ۲ F541. در `app/` به‌تنهایی: ۱۳۷ مورد (۱۳۲ E501، ۲ F401، ۲ F841، ۱ F541). **این بدهیِ قدیمی است، نه نتیجهٔ این کار** |
| فرمت | `ruff format --check .` | ۱۸۹ فایل «باید فرمت شوند» ⇒ **عمداً اجرا نمی‌شود** (بازنویسیِ سراسریِ آرایشی؛ برخلافِ قانونِ «rewrite نکن») |
| Build | `docker compose build` | ✅ ایمیج ساخته می‌شود و بات با آن polling را شروع می‌کند (MEASURED: `Run polling for bot @Kkhtest2robot`) |
| type-check | — | **NOT RUN**: mypy/pyright در این پروژه تعریف نشده‌اند و اضافه‌کردنشان (وابستگیِ جدید + صدها خطایِ اولیه) خارجِ دامنهٔ «حداقلِ وابستگی» است. جایگزینِ عملی: چهار گیتِ استاتیکِ موجود |

### ۱-۴) فهرستِ مشکلاتِ اولویت‌بندی‌شده (شواهد، نه حدس)

**P0 — مالی/امنیتی، مشخص و تکرارشدنی**
1. **حداقلِ شارژ ۵۰٬۰۰۰ تومان نیست و فقط در UI چک می‌شود.** `panel.py:414` مقدارِ دلخواه را `>= 10_000` می‌خواهد؛ `payment_service.create_card_to_card_payment/_zarinpal/_bale` **هیچ** اعتبارسنجیِ کمّیِ حداقلی ندارند ⇒ همِ الزامِ PHASE 5A نقض شده (عددِ غلط) و هم «backend must validate too». (پیش‌فرض‌هایِ دکمه `50k/100k/300k/500k` درست‌اند.)
2. **commission اصلاً وجود ندارد.** جست‌وجویِ `commission|کمیسیون` در `app/` = صفر نتیجه ⇒ PHASE 5D یک قابلیتِ **نو** است (نه رفعِ باگ) و باید با مدلِ تجاریِ موجود (کیف‌پولِ فروشگاه‌دار) طراحیِ واحد شود.
3. **دفترِ کیف‌پول ستون‌هایِ خواسته‌شده را ندارد.** `WalletTransaction` = (amount, reason, reference, wallet_charge_id، created_at) ⇒ **currency، status، idempotency_key و orderingِ قابلِ اطمینان** ندارد؛ `reference` هم آزاد است نه یکتا. (PHASE 5E)
4. **هیچ بازبینیِ همسنجیِ (reconciliation) موجودی/دفتر وجود ندارد.** ادعایِ docstring («مجموعِ amount_toman باید همیشه برابرِ wallet_balance_toman باشد») نه در کد چک می‌شود و نه تست دارد ⇒ ریسکِ سکوتِ اختلاف. (PHASE 5E/7)
5. `ShopBot.zarinpal_merchant_id` و `ShopBot.webhook_secret_token` **متنِ ساده** در دیتابیس‌اند در حالی که همتایِ سراسریِشان (`AdminSettings.zarinpal_merchant_id`) رمزنگاری‌شده و ماسک‌شده است ⇒ ناهمخوانیِ مدیریتِ راز. (PHASE 3)

**P1 — درستی/سرسختی**
6. `deduct` آسورنسِ منفی‌نشدن را با `FOR UPDATE` و چکِ پیشِ mutation دارد ✅، ولی مسیرهایِ **افزودنِ** اعتبار (K1 gift، refund، admin correction) باید تک‌به‌تکِ ایدمپوتنسی‌شان اثباتِ تستی شود (بخشی دارند: `AdminCreditBatchItem` UNIQUE).
7. چهار گیتِ استاتیکِ پروژه هیچ‌وقت در CI نیستند (`ci.yml` فقط ruff+migrate+tests را اجرا می‌کند) ⇒ گیت‌هایی که P18 با آن‌ها باگ گرفت، در CI محافظت نمی‌کنند.
8. ۲۴ findingِ واقعیِ ruff (F401/F841/F541) = کدِ مردهٔ بی‌خطر ولی نشانهٔ عدمِ نظارت.
9. لاگ‌ها **ساخت‌یافته/JSON نیستند** و correlation id فقط در `payment_event_logs` است، نه در همه‌یِ مسیرها (PHASE 16/20).

**P2 — زیرساخت/ظرفیت**
10. هیچ تستِ باری وجود ندارد (نه k6/locust نه اسکریپتِ داخلی) ⇒ PHASE 12 از صفر.
11. `docker-compose.yml` فقط bot+db است؛ healthcheck رویِ bot، resource limits، volumeِ backup و لاگرُتیشنِ دیسک باید بررسی/مستند شود.
12. `AUTONOMOUS_PROGRESS.md` و هشت سندِ PHASE 17 تا پیشِ این کار وجود نداشتند.

## ۲) وضعیتِ فازها

| فاز | وضعیت | یادداشت |
|---|---|---|
| 1 کشف و بیس‌لاین | **COMPLETED** | این بخش؛ بیس‌لاین بالا MEASURED است |
| 2 حفظِ انقضایِ شارژ | **COMPLETED** | ۷ رگرسیون‌تستِ تازه در `tests_manual/test_p2_credit_expiry_preserved.py` (MEASURED: ۷/۷ پاس) و اجرایِ کاملِ مجموعه: **۷۸ فایل / ۴۹۹ تست سبز**. معنا/مدت/مبدأ/FIFO/ایدپوتنسیِ جاب قفل شد؛ هیچ کدِ محصولی در این واحد عوض نشد |
| 3 امنیت | NOT STARTED | یافته‌هایِ بالا (۵) و مرورِ دامنه‌هایِ پرداخت |
| 4 درستیِ کارکردی | NOT STARTED | |
| 5 مالی | NOT STARTED | حداقلِ شارژ، gating، commission، ledger |
| 6 صورتحسابِ API | NOT STARTED | بخشِ زیادی موجود است (AI cost)؛ باید اثبات/تفکیک شود |
| 7+8 داده و ماشینِ حالت | NOT STARTED | |
| 9 کیفیتِ کد | NOT STARTED | فقط F-codes، نه فرمتِ سراسری |
| 10 تست | IN PROGRESS | بیس‌لاین ۴۹۲ تست سبز |
| 11+12+16 | NOT STARTED | |
| 13+16.5 | NOT STARTED | |
| 17+18 تحویل/پذیرش | IN PROGRESS | همین فایل + شش سندِ دیگر در پایان |
| 19 قطع‌شدن‌ناپذیری | **COMPLETED (continuous)** | این فایل، همان checkpoint است |
| 20 لاگ/ممیزی/مانیتورینگ | NOT STARTED | |

## ۳) حقیقتِ «انقضایِ اعتبارِ شارژ» (PHASE 2 — مبنایِ حفظ)

MEASURED از کد (`app/database/models.py:463`، `app/services/wallet_service.py:56-95`، `app/services/wallet_expiry_service.py`):
- **مدل:** هر شارژ = یک ردیفِ مستقلِ `wallet_charges` با `expires_at`، `remaining_toman`، `is_expired` و سه پرچمِ یادآوری.
- **مبدأِ زمان:** `now = datetime.now(utc)` در لحظهٔ ساختِ شارژ (یعنی لحظهٔ موفق‌شدنِ شارژ، دقیقاً همان‌که خواسته شده) و `expires_at = now + validity_months × 30 روز`.
- **مدتِ مدتِ اعتبار:** از `AdminSettings.wallet_topup_validity_months` (پیکربندیِ ادمین، ستونِ موجود؛ قابل‌تنظیم از «🔑 تنظیمات کلیدها»). `validity_months` می‌تواند per-call داده شود (K1 gift، اشتراک) وگرنه از تنظیماتِ سراسری.
- **مصرف:** FIFO از قدیمی‌ترین شارژِ منقضی‌ننشده، با قفلِ سطر (`FOR UPDATE`)، پخشِ بینِ چند بسته، و ردِّ کلِ عمل اگر مجموعِ باقی‌مانده کم باشد.
- **جابِ انقضا:** `wallet_expiry_service.process_wallet_expiry_and_reminders` → `expire_stale_charges` (منقضی‌کردنِ واقعی + کسرِ موجودیِ کش‌شده) و یادآوری‌هایِ ۳۰/۷/۱ روز (هر بسته یک‌بار به‌ازایِ هر مرز).
- **هیچ مکانیزمِ رقیبی وجود ندارد:** `credit_batch_service` فقط «عملیاتِ گروهیِ ادمین» است و اعتبار را از همان `wallet_service` می‌سازد؛ جدولِ `admin_credit_batch_items` برایِ ایدمپوتنسیِ اجراست نه انقضا.
- **تعهد:** هیچ‌یک ازِ این معنی/عدد/توالی در این کار تغییر نمی‌کند. تست‌هایِ رگرسیونِ تازه همین را قفل می‌کنند.

## ۴) تصمیم‌ها و فرض‌هایِ این کار

1. شاخهٔ تازه از HEAD تمیزِ P18؛ **هیچ push/merge/deploy** انجام نمی‌شود (قانونِ ۱۲).
2. `ruff format` اجرا نمی‌شود؛ فقط F-codes و مشکلاتِ واقعیِ `app/` اصلاح می‌شوند (قانونِ ۳/۹: حداقلِ تغییرِ قابلِ بازگشت).
3. «admin panel» = همان منویِ Telegramِ main bot. هیچ وب‌داشبوردی اضافه نمی‌شود (قانونِ ۹: زیرساختِ جدیدِ غیرضروری نه).
4. هیچ وابستگیِ پولی/سرویسِ پولی/ELK/Kubernetes اضافه نمی‌شود. تستِ بار با اسکریپتِ پایتونِ داخلِ مخزن (stdlib + aiohttpِ موجود) و هدفِ mock/sandbox، نه سرویسِ بیرونی.
5. دیتابیسِ dev همین حالا (توسطِ کاربر اجازه گرفته شد) از `backup_before_p18.sql` بازگردانی شد و ۱۱ مایگریشنِ P18 رویِ دادهٔ واقعی اجرا شد؛ **قبل از هر حرکتِ مخربِ دیگری دوباره اجازه گرفته می‌شود** و بکاپِ تازه می‌گیرم.
6. پوشهٔ تست (`run_all_tests.py`) جدول‌ها را TRUNCATE می‌کند ⇒ بعد از هر اجرایِ کاملِ تست، یا باید دیتابیسِ جدا برایِ تست داشت یا بکاپ برگردانده شود. این را در راهنمایِ استقرار می‌نویسم.

## ۵) اقدامِ بعدی (دقیق)

1. **واحدِ ۲A:** افزودنِ `tests_manual/test_p18_phase2_expiry_preserved.py` که این‌ها را قفل می‌کند: مدت از `wallet_topup_validity_months` (مثلاً ۱۲ ⇒ ۳۶۰ روز)، مبدأ = لحظهٔ شارژ، بسته‌ها مستقل‌اند، FIFO از قدیمی‌ترینِ منقضی‌ننشده، بستهٔ منقضی مصرف نمی‌شود، جابِ انقضا موجودیِ کشیده را کم می‌کند و هر بار فقط یک‌بار عمل می‌کند (ایدپوتنت)، یادآوری هر مرز یک‌بار. سپس ثبتِ عددِ تست‌ها در این فایل و `TEST_RESULTS.md`.
2. **واحدِ ۳A (P0-1):** ستونِ تازه‌یِ افزودنیِ `AdminSettings.min_topup_amount_toman` (پیش‌فرض ۵۰۰۰۰، `server_default`) + اعتبارسنجیِ **سرویس** در `payment_service.create_*` (هر سه روش) + UIِ بات (پیامِ فارسیِ روشن با حداقلِ فعلی) + دکمهٔ ادمین در همان «🔑 تنظیمات کلیدها» + تست‌هایِ ۱/۲/۳ِ چک‌لیستِ PHASE 10.
3. بعد از هر واحد: گیت‌هایِ استاتیک + تست‌هایِ مرتبط + اجرایِ کاملِ مجموعه، و سپس commit.

## ۶) لاگِ اجرا (append-only)

| زمان | واحد | وضعیت | فایل‌ها | چک‌هایِ واقعی |
|---|---|---|---|---|
| ۲۰۲۶-۱۱-۰۱ | PHASE 1 کشف + بیس‌لاین | COMPLETED | `AUTONOMOUS_PROGRESS.md` (جدید) | ruff 260/۱۳۷ (MEASURED)، `alembic upgrade head` موفق، گیت‌هایِ استاتیک OK، ۴۹۲ تست سبز |
| ۲۰۲۶-۱۱-۰۱ | واحدِ ۲A — قفلِ رگرسیونِ انقضا | COMPLETED | `tests_manual/test_p2_credit_expiry_preserved.py` (جدید، ۷ تست)، `tests_manual/run_all_tests.py` | تستِ فایل: ۷/۷ ✅ · تستِ کامل: **۷۸/۷۸ فایل، ۴۹۹ تست** ✅ · گیت‌ها OK. کدِ محصول دست‌نخورده (قفلِ رفتار، نه تغییرِ رفتار) |
| ۲۰۲۶-۱۱-۰۱ | واحدِ ۳A — حداقلِ شارژ (PHASE 5A) | IN PROGRESS | `app/database/models.py` (+`min_topup_amount_toman`)، `migrations/versions/d7a2c5e9f3b8_p5_min_recharge_amount.py` (جدید)، `app/services/payment_service.py` (گاردِ سرویس)، `app/bots/main_bot/handlers/panel.py`، `keyboards.py`، `texts.py`، `handlers/admin.py`، `tests_manual/test_p5_min_recharge.py` (جدید، ۸ تست) | گیت‌هایِ استاتیک OK (MEASURED). اجرایِ تست‌ها در حالِ انجام است؛ عددِ نهایی در خطِ بعدی این جدول ثبت می‌شود |
