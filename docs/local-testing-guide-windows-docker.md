# راه‌اندازیِ محیطِ تستِ محلی روی ویندوز (با Docker)

اگه روی ویندوز کار می‌کنی، ساده‌ترین راه برای داشتنِ یه PostgreSQL محلی
(بدونِ نصبِ مستقیمِ Postgres روی سیستم) استفاده از Docker Desktoپه.

## پیش‌نیازها

1. [Python 3.12+](https://www.python.org/downloads/) — موقعِ نصب، تیکِ
   «Add python.exe to PATH» رو بزن.
2. [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/)
   — بعد از نصب، مطمئن شو روشنه (آیکونِ نهنگ توی system tray).
3. [Git for Windows](https://git-scm.com/download/win) (اگه از قبل نداری).

## روشِ خودکار (پیشنهادی)

از ریشه‌ی پروژه، توی PowerShell:

```powershell
.\scaffold.ps1
```

این اسکریپت خودش venv می‌سازه، پکیج‌ها رو نصب می‌کنه، `.env` رو آماده می‌کنه،
و اگه Docker روشن باشه، پیشنهاد می‌ده یه کانتینرِ PostgreSQL بالا بیاره. اگه
پالیسیِ اجرای اسکریپت‌هاش اجازه نداد:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scaffold.ps1
```

## روشِ دستی

اگه ترجیح می‌دی خودت مرحله‌به‌مرحله انجام بدی:

```powershell
# ۱. ساختِ venv و نصبِ پکیج‌ها
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# ۲. بالا آوردنِ PostgreSQL با Docker
docker run -d --name kasbokar-postgres `
    -e POSTGRES_PASSWORD=postgres `
    -e POSTGRES_DB=kasbokar_test `
    -p 5432:5432 `
    postgres:16

# ۳. متغیرهای محیطی (برای همین سشنِ PowerShell)
$env:DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost/kasbokar_test"
$env:MAIN_BOT_TOKEN = "123456789:AAtestFAKEtokenFAKEtokenFAKEtokenFAKE"
$env:ENCRYPTION_KEY = python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
$env:ADMIN_TELEGRAM_IDS = "12345"
$env:WEBHOOK_BASE_URL = "https://example.com"
$env:RUN_MODE = "polling"
$env:AUTH_MODE = "test"

# ۴. مایگریشن + تست
alembic upgrade head
python tests_manual\run_all_tests.py
```

## دستوراتِ مفیدِ Docker

```powershell
docker stop kasbokar-postgres      # خاموش‌کردنِ موقتِ دیتابیس
docker start kasbokar-postgres     # روشن‌کردنِ دوباره (دیتا حفظ می‌شه)
docker logs kasbokar-postgres      # دیدنِ لاگ‌های Postgres
docker rm -f kasbokar-postgres     # حذفِ کاملِ کانتینر و دیتاش (برای شروعِ تازه)
```

## عیب‌یابیِ رایج

**«docker: command not found» یا خطای اتصال به Docker daemon:** مطمئن شو
Docker Desktop واقعاً روشن و کاملاً بالا اومده (نه فقط در حالِ لود). آیکونِ
نهنگ توی system tray باید ثابت (نه در حالِ چرخش) باشه.

**پورتِ ۵۴۳۲ از قبل اشغاله:** یا یه Postgres دیگه (نصب‌شده روی خودِ ویندوز)
داری که باید متوقفش کنی، یا پورتِ کانتینر رو عوض کن:
`-p 5433:5432` و متناسبش `DATABASE_URL` رو هم به `...@localhost:5433/...` تغییر بده.

**اسکریپتِ PowerShell اجرا نمی‌شه («running scripts is disabled»):**
پالیسیِ اجرا روی سیستمت محدوده. `Set-ExecutionPolicy -Scope Process
-ExecutionPolicy Bypass` رو قبل از اجرای اسکریپت بزن (فقط برای همون سشن اعمال
می‌شه، امنه).

**تست‌ها با خطای اتصال به دیتابیس fail می‌شن:** چک کن کانتینر واقعاً بالاست
(`docker ps`) و چند ثانیه بعد از `docker run`/`docker start` صبر کن — Postgres
یه چند ثانیه طول می‌کشه تا کاملاً آماده بشه.
