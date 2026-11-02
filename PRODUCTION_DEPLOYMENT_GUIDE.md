# PRODUCTION_DEPLOYMENT_GUIDE — Smart Business

تاریخ: ۲۰۲۶-۱۱-۰۱ · مطابقِ کدِ همین مخزن در `production-hardening` (head `f9c4a7d2b5e8`).
بر اساسِ فایل‌هایِ واقعی نوشته شده: `Dockerfile`، `docker-compose.yml`، `entrypoint.sh`،
`app/config.py`، `.env.docker.example`. **هیچ deploy واقعی انجام نشده**؛ این راهنما تمرین‌شدگیِ
بخش‌هایِ لوکال را با برچسبِ MEASURED/NOT PRACTICED جدا می‌کند.

## ۰) نقشهٔ اجزا

| جزء | واقعیتِ موجود |
|---|---|
| ایمیج | `python:3.12-slim` + `pip install -r requirements.txt` + کد؛ `USER app` (غیرroot) |
| سرویس‌ها | `db` (postgres:16، فقط `127.0.0.1:5432`، healthcheck `pg_isready`، لاگرُتیشن ۵×۱۰MB) و `bot` (build محلی، `env_file: .env`، `depends_on: db healthy`) |
| بوت‌آپ | `entrypoint.sh`: اعتبارسنجیِ `.env` (ساختِ Fernet از `ENCRYPTION_KEY`) ← صبرِ حداکثر ۶۰ ثانیه برایِ DB ← `alembic upgrade head` ← `python -m app.main` |
| حالت‌ها | `RUN_MODE=polling` ⇒ فقط دیال‌آپِ تلگرام/بله (بدونِ HTTP). `RUN_MODE=webhook` ⇒ uvicorn روی `0.0.0.0:8000` + `set_webhook` با سکرت |
| نقاطِ پایانیِ HTTP | `GET /health`، `POST /webhook/main`، `POST /webhook/shop/{shop_bot_id}`، `POST /webhook/bale` و `/webhook/bale/{path_secret}`، `GET /payment/zarinpal/callback` |
| نقصِ شناخته‌شده | `bot` هیچ `ports:` و هیچ `healthcheck:` در compose ندارد ⇒ در حالتِ webhook حتماً باید پورت را (ترجیحاً فقط 127.0.0.1) بیرون بکشی و پروکسی جلویِ آن بگذاری. پایین ببین §4 و §5 |

## ۱) پیش‌نیازها

- Docker Engine + Compose v2، ۲GB RAM آزاد برایِ شروع (بخشِ ظرفیت: `HARDWARE_REQUIREMENTS_AND_CAPACITY_PLAN.md`).
- دامنه + TLS معتبر فقط اگر `RUN_MODE=webhook`.
- توکنِ رباتِ اصلی، شناسهٔ ادمین(ها)، کلیدِ ارائه‌دهندهٔ AI، و (اختیاری) توکن/درگاهِ بله، مرچنتِ زرین‌پال، کلیدِ کاوه‌نگار.

## ۲) متغیرهایِ محیطی (نسخهٔ کامل: `.env.docker.example`)

| کلید | لازم؟ | نکته |
|---|---|---|
| `MAIN_BOT_TOKEN` | بله | بدونِ آن entrypoint رد می‌شود |
| `ADMIN_TELEGRAM_IDS` | بله | لیستِ جداشده با کاما |
| `ENCRYPTION_KEY` | قویاً توصیه | Fernet. بدونش همهٔ رازها در حالتِ fallback/ساده می‌مانند: توکن ربات‌ها، توکن درگاه بله، کلیدهای AI (استخر و تکی)، کلید کاوه‌نگار، شماره کارت پلتفرم |
| `RUN_MODE` | بله | `polling` ساده‌ترین شروع است |
| `DATABASE_URL` | بله (webhook/dev) | سازگار با POSTGRES_* در compose |
| `WEBHOOK_BASE_URL` | در webhook | https و بدونِ اسلش انتهایی |
| `MAIN_BOT_WEBHOOK_SECRET` | در webhook | اگر خالی باشد بوتِ پلتفرم خودش می‌سازد و در `admin_settings` ذخیره می‌کند (قاعدهٔ «استارتِ بدونِ نگهبان ممنوع») |
| `BALE_BOT_TOKEN`, `BALE_WEBHOOK_SECRET`, `BALE_API_BASE`, `BALE_UPDATES_MODE` | اختیاری | برایِ بله |
| `AUTH_MODE`, `SMTP_*` | اختیاری | احرازِ ایمیلی/حالتِ ثبت‌نام |
| `POSTGRES_PASSWORD` | در سرور | پیش‌فرض `postgres` فقط برایِ dev است؛ در compose هم فقط رویِ 127.0.0.1 bind شده |

## ۳) استقرارِ نوپا (گام‌به‌گام)

```bash
git clone <repo> && cd kasb-o-kar-hoshmand
cp .env.docker.example .env         # فقط نام‌ها؛ مقادیرِ واقعی را خودت بگذار
docker compose build
docker compose run --rm bot python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
#   ⇒ خروجی را در ENCRYPTION_KEY= .env بگذار
docker compose up -d                # entrypoint خودش migrate می‌کند
docker compose ps                   # db healthy + bot up
docker compose logs --tail=50 bot   # باید: «تنظیماتِ .env معتبره» ← «مایگریشن‌ها با موفقیت اعمال شدن» ← polling
```

تاییدِ سالمِ بوت (MEASURED در dev): `3 ربات فروشگاهیِ فعال بارگذاری شد` و
`Run polling for bot @…`. دو خطایِ «chat not found» از رکورد‌هایِ قدیمیِ خودِ محیط است و
مدیریت‌شده‌اند (لاگ، بدونِ کرش).

## ۴) webhook + پروکسی معکوس (وقتی `RUN_MODE=webhook`)

۱) در compose پورت را فقط لوکال باز کن:
```yaml
  bot:
    ports: ["127.0.0.1:8000:8000"]
    healthcheck:
      test: ["CMD-SHELL", "python -c \"import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read()\""]
      interval: 30s
      timeout: 5s
      retries: 3
```
۲) nginx/Caddy: `location / { proxy_pass http://127.0.0.1:8000; proxy_set_header X-Forwarded-For $remote_addr; proxy_set_header Host $host; }` + TLS.
۳) `WEBHOOK_BASE_URL=https://damene-شما`.
۴) **فقط وقتی** پروکسی جلویِ سرور است و `X-Forwarded-For` را درست می‌کند، به‌سویِ rate-limitِ
   مبتنی بر IP برو (این مورد هنوز پیاده نشده — `REMAINING_ISSUES.md` P1-1). تا آن زمان IPِ
   مستقیمِ سرور را در معرضِ وب‌هوک نگذار.

## ۵) مهاجرتِ دیتابیس: امن، قابلِ بازگشت، قابلِ راستی‌آزمایی

```bash
# ۱) قبلِ هر کاری: بکاپِ سردِ منطقی
docker compose exec -T db pg_dump -U postgres kasbokar > backup_$(date +%Y%m%d_%H%M).sql

# ۲) وضعیتِ فعلی
docker compose run --rm bot alembic current          # مثال: f9c4a7d2b5e8 (head)

# ۳) ارتقا (entrypoint خودش انجام می‌دهد؛ دستی برایِ کنترلِ لاگ)
docker compose run --rm bot alembic upgrade head
docker compose run --rm bot alembic heads             # باید فقط یک شناسه بدهد

# ۴) روی کپیِ بکاپ، downgrade را تمرین کن (نه رویِ دیتابیسِ زنده)
createdb kasbokar_test && pg_restore -d kasbokar_test backup_XXXX.sql
docker compose run -e DATABASE_URL=postgresql+asyncpg://postgres:postgres@db/kasbokar_test --rm bot alembic downgrade -1
```
قاعدهٔ پروژه: مایگریشن‌ها **افزودنی**‌اند (ستون/جدید با `server_default`) و هیچ ستون/جدولی
حذف نمی‌شود ⇒ `downgrade` در همهٔ مواردِ این کار نوشته شده ولی رویِ دادهٔ واقعی **تمرین نشده
(NOT PRACTICED)**. تنها downgrade واقعی که در این نشست اجرا شد: بازگردانیِ کامل از
`backup_before_p18.sql` (pg_dump) و سپس اعمالِ دوبارهٔ ۱۵ مایگریشن رویِ همان داده ✅ MEASURED.

## ۶) بکاپ/بازیابی (سناریویِ واقعی)

```bash
# بکاپِ زمان‌بندی‌شده (cron روزانه، نگه‌داشتنِ ۱۴ نسخه)
docker compose exec -T db pg_dump -U postgres -Fc kasbokar > /backups/kasbokar_$(date +%F).dump
# بازیابی
docker compose stop bot
docker compose exec -T db psql -U postgres -c "DROP DATABASE IF EXISTS kasbokar;" -c "CREATE DATABASE kasbokar;"
docker compose exec -T db pg_restore -U postgres -d kasbokar --no-owner /backups/kasbokar_YYYY-MM-DD.dump
docker compose up -d bot      # entrypoint migrate را از جایِ درست ادامه می‌دهد
```
راستی‌آزماییِ بازیابی (حتماً اجرا کن):
```bash
docker compose exec -T db psql -U postgres -d kasbokar -c "\dt" | wc -l
docker compose exec -T db psql -U postgres -d kasbokar -tAc "SELECT version_num FROM alembic_version;"
docker compose exec -T db psql -U postgres -d kasbokar -tAc "SELECT count(*) FROM shop_owners;"
docker compose run --rm -e ADMIN_TELEGRAM_IDS=12345 bot python tests_manual/run_all_tests.py   # 81/525
```
⚠️ توجهِ عملیاتی: پوشهٔ `tests_manual/` در ابتدایِ هر فایلِ تست جدول‌ها را **TRUNCATE** می‌کند.
هرگز مجموعهٔ تست را رویِ دیتابیسِ production اجرا نکن و بعد از اجرایِ آن رویِ dev، یا بکاپ را
برگردان یا دیتابیسِ تستِ جدا داشته باش.

## ۷) عیب‌یابیِ عملیاتی

| نشانه | معنی/کار |
|---|---|
| «تنظیماتِ .env ناقص است» | `MAIN_BOT_TOKEN` خالی یا `ENCRYPTION_KEY` ناقص/با فاصله |
| «دیتابیس بعد از ۳۰ تلاش آماده نیست» | db بالا نیست / `DATABASE_URL` نادرست / volume خراب |
| «chat not found» در لاگ | شناسهٔ تلگرامِ یک فروشگاه‌دار/ادمین دیگر وجود ندارد؛ ردیفِ دیتابیس را اصلاح کن (برنامه نمی‌خوابد) |
| «بارگذاریِ ربات فروشگاهی N ناموفق» | توکنِ آن فروشگاه باطل/حذف‌شده است؛ از پنلِ «🔑 ثبت/ویرایش توکن ربات» تازه‌اش کن |
| بیویِ ربات برنمی‌گردد | خطایِ ۴۲۹/رباتِ غیرفعال است؛ در لاگ `bot_branding_service` و شمارندهٔ `error` را ببین؛ بعد از رفع، «همین الان همسازسازی» را بزن |
| پیامک نمی‌رسد | `sms_enabled`/کلید/سرشماره/نامِ قالب را چک کن؛ کد در چت نمایش داده می‌شود (مسیرِ جایگزین) و سقفِ ساعتی را نباشد |
| فاکتور HTML رفت | ساختِ PDF ناموفق بوده (فونت/کتابخانه)؛ در لاگ `invoice_service` علت هست، فاکتور گم نمی‌شود |
| «⚠️ N فروشگاه‌دار اختلافِ حسابداری دارد» | همسنجیِ PHASE 5E؛ از «📤 دفترِ کیف‌پول (اکسل) › 🔎 همسنجیِ دفتر» ببین و با ردیفِ معکوسِ ادمین اصلاح کن (تاریخچه را ویرایش نکن) |
| «نسخهٔ دیگری از این ربات در حالِ polling است» (P24) | دو نسخة هم‌زمان بالا آمده (`--scale bot=2`، یا deployِ جدید قبل از کشتنِ قدیمی). دومی عمداً هیچ getUpdates‌ای شروع نمی‌کند تا پیام دوباره پاسخ نگیرد و کیف‌پول دوباره کم نشود؛ نسخهٔ قدیمی را ببند (`docker compose ps`، بعد `up -d`) |
| `Bad Request: inline keyboard button URL 'invoice_id=…' is invalid` در لاگ (P23/P24) | قالبِ لینکِ پرداختِ بله در پنل تنظیم نشده؛ «🔑 تنظیمات کلیدها › 🔗 قالبِ لینکِ پرداختِ بله‌پی» را از برگهٔ «اطلاعات اتصالِ وب‌سرویس» بله پر کن |

## ۸) مانیتورینگِ حداقلی

- `GET /health` در **هر دو حالت** (O2): ۲۰۰ سالم / ۵۰۳ با `{"database":"down"}` یا `{"bot":"not_initialized"}`؛
  در حالتِ polling رویِ `127.0.0.1:8000` است و از P24 خودِ compose هم همین مسیر را به‌عنوانِ
  `healthcheck` می‌پرسد ⇒ گیرکردنِ حلقهٔ polling ری‌استارتِ خودکار را فعال می‌کند.
  `/metrics` هم همین‌جا است، ولی **با `METRICS_TOKEN`ِ خالی عمداً ۴۰۴ می‌دهد** (پیش‌فرضِ امن):
  برایِ دیدنِ شمارنده‌ها `METRICS_TOKEN=…` را در `.env` بگذار و با هدرِ `X-Metrics-Token` بپرس.
- لاگ stdout + چرخشِ ۵×۱۰MB در compose؛ `LOG_LEVEL` در `.env`.
- ممیزیِ عملیاتیِ انسانی: «📜 گزارشِ ممیزی» در پنلِ ادمین (`audit_log_entries`)، «🔎 آخرین رویدادهایِ پرداخت» (`payment_event_logs` + correlation id).
- هشدارهایِ ادمین: `admin_alert_service` (پنجرهٔ ۵ دقیقه، آستانه‌ها، کول‌دان ۳۰ دقیقه، بودجهٔ ۱۲/ساعت) — حالا `KIND_LEDGER` هم دارد.
- نبودِ متریک‌هایِPrometheus‌مانند = شناخته‌شده و باز: `REMAINING_ISSUES.md` P1-5.

## ۹) چک‌لیستِ انتشار

۱) `.env` از `.env.docker.example` با مقادیرِ واقعی، بدونِ commit شدن (در `.gitignore` و `.dockerignore` است) ۲) `ENCRYPTION_KEY` بکاپ‌شده و جدا نگه‌داشته شده (بدونش رازها قابلِ بازیابی نیستند) ۳) بکاپِ تازه قبلِ migrate ۴) `docker compose build` و `up -d` در پنجرهٔ کم‌ترافیک ۵) `alembic heads` تک‌head ۶) لاگِ بوت تمیز + یک سفارشِ تستیِ واقعیِ کوچک در حالتِ sandbox/مبلغِ ناچیز ۷) بازگشتِ `RUN_MODE=polling` در دسترس به‌عنوانِ kill-switch ۸) «🔑 تنظیمات کلیدها › 🚧 حالتِ تعمیر» برایِ قطعِ ترافیکِ مشتری در صورتِ نیاز.

۹) (P24) `python3 scripts/check_gates.py` سبز باشد — از این پاس **پنج** گیت دارد:
`check_refs` (ارجاعِ ماژولی)، `check_attrs` (صفاتِ ORM)، `lint_names` (نام‌هایِ مشکوک)،
`check_callbacks` (هر `callback_data` که ساخته می‌شود مصرف‌کننده داشته باشد ⇒ «دکمهٔ مرده» دیگر
نمی‌تواند به production برسد) و `check_text_hygiene` (نویسهٔ سیریلیک/CJK/هانجی در خطِ فارسی).
رویِ سرور با `docker compose run --rm bot python3 scripts/check_gates.py` و رویِ ماشینِ خودت
بدونِ داکر هم اجرا می‌شود. ۱۰) (P24) رویِ سرور فقط **یک** نسخهٔ `bot` بالا باشد؛ نسخهٔ دوم
قفلِ دیتابیس را نمی‌گیرد و polling را شروع نمی‌کند (لاگش را می‌شود دید) — این امنیتِ احتیاطی است،
نه مجوزِ scale: برایِ افقی‌شدن، بندِ §۵ِ `HARDWARE_REQUIREMENTS_AND_CAPACITY_PLAN.md` را اول بخوان.
۱۱) (P24) `docker compose ps` ستونِ `health` را `healthy` نشان دهد؛ `mem_limit: 1g` رویِ سرویسِ bot
است (MEASURED: RSS بی‌کاری ۲۰۸MiB ⇒ ۵ برابرِ سرِ‌باز) و رویِ سرورِ بزرگ‌تر می‌توانی بالا ببری.
۱۲) (P24) اگر شمارنده‌ها را جایی جمع می‌کنی، `METRICS_TOKEN` را در `.env` تنظیم کن — بدونِ آن
`/metrics` عمداً **۴۰۴** است و فقط `/health` جواب می‌دهد (این را در dev اندازه گرفتیم).
