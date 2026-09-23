#Requires -Version 5.1
<#
.SYNOPSIS
    راه‌اندازیِ خودکارِ محیطِ توسعه‌ی محلی برای «کسب‌وکار هوشمند» روی ویندوز.

.DESCRIPTION
    این اسکریپت به‌صورتِ خودکار:
      ۱. یه virtual environment پایتون می‌سازه و پکیج‌ها رو نصب می‌کنه
      ۲. فایلِ .env رو از .env.example می‌سازه (اگه از قبل نباشه) و یه
         ENCRYPTION_KEY تازه براش تولید می‌کنه
      ۳. اگه Docker نصب باشه، پیشنهاد می‌ده یه کانتینرِ PostgreSQL محلی بالا بیاره
      ۴. مایگریشن‌های Alembic رو روی دیتابیس اجرا می‌کنه

.NOTES
    قبل از اجرا مطمئن شو Python 3.12+‎ نصب و توی PATH هست.
    اجرا: .\scaffold.ps1
    اگه پالیسیِ اجرای اسکریپت‌ها بسته بود:
        Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#>

$ErrorActionPreference = "Stop"

function Write-Step($msg) {
    Write-Host ""
    Write-Host "==> $msg" -ForegroundColor Cyan
}

function Write-Ok($msg) {
    Write-Host "    OK: $msg" -ForegroundColor Green
}

function Write-Warn($msg) {
    Write-Host "    توجه: $msg" -ForegroundColor Yellow
}

$ProjectRoot = $PSScriptRoot
Set-Location $ProjectRoot

Write-Step "بررسیِ نصب‌بودنِ پایتون"
try {
    $pyVersion = & python --version 2>&1
    Write-Ok "$pyVersion پیدا شد"
} catch {
    Write-Host "پایتون پیدا نشد. لطفاً Python 3.12 یا بالاتر رو از python.org نصب کن و دوباره امتحان کن." -ForegroundColor Red
    exit 1
}

Write-Step "ساختِ virtual environment (venv\)"
if (-not (Test-Path "venv")) {
    python -m venv venv
    Write-Ok "venv ساخته شد"
} else {
    Write-Ok "venv از قبل وجود داره"
}

Write-Step "فعال‌سازیِ venv و نصبِ پکیج‌ها"
& ".\venv\Scripts\Activate.ps1"
python -m pip install --upgrade pip | Out-Null
pip install -r requirements.txt
Write-Ok "پکیج‌های requirements.txt نصب شدن"

Write-Step "آماده‌سازیِ فایلِ .env"
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Ok ".env از روی .env.example ساخته شد"

    $encKey = python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    (Get-Content ".env") -replace "ENCRYPTION_KEY=", "ENCRYPTION_KEY=$encKey" | Set-Content ".env"
    Write-Ok "یه ENCRYPTION_KEY تازه تولید و توی .env نوشته شد"

    Write-Warn "هنوز باید MAIN_BOT_TOKEN و ADMIN_TELEGRAM_IDS رو دستی توی .env پر کنی."
} else {
    Write-Ok ".env از قبل وجود داره؛ دست‌نخورده باقی موند"
}

Write-Step "بررسیِ Docker برای PostgreSQL محلی"
$dockerAvailable = $false
try {
    docker --version | Out-Null
    $dockerAvailable = $true
    Write-Ok "Docker پیدا شد"
} catch {
    Write-Warn "Docker پیدا نشد. اگه PostgreSQL رو خودت به‌صورتِ دیگه‌ای راه‌انداختی، این مرحله رو رد کن."
}

if ($dockerAvailable) {
    $existing = docker ps -a --filter "name=kasbokar-postgres" --format "{{.Names}}"
    if ($existing -eq "kasbokar-postgres") {
        Write-Ok "کانتینرِ kasbokar-postgres از قبل وجود داره؛ روشنش می‌کنیم"
        docker start kasbokar-postgres | Out-Null
    } else {
        $answer = Read-Host "می‌خوای یه کانتینرِ PostgreSQL محلی (روی پورتِ 5432) بالا بیارم؟ [Y/n]"
        if ($answer -ne "n" -and $answer -ne "N") {
            docker run -d --name kasbokar-postgres `
                -e POSTGRES_PASSWORD=postgres `
                -e POSTGRES_DB=kasbokar `
                -p 5432:5432 `
                postgres:16
            Write-Ok "کانتینرِ PostgreSQL بالا اومد (postgres/postgres، دیتابیسِ kasbokar، پورتِ 5432)"
            Write-Host "    چند ثانیه صبر می‌کنیم تا کاملاً آماده بشه..."
            Start-Sleep -Seconds 5
        }
    }
}

Write-Step "اجرای مایگریشن‌های Alembic"
try {
    alembic upgrade head
    Write-Ok "مایگریشن‌ها با موفقیت اجرا شدن"
} catch {
    Write-Warn "اجرای مایگریشن fail شد. مطمئن شو DATABASE_URL توی .env درست تنظیم شده و PostgreSQL در دسترسه."
    Write-Warn "خطا: $_"
}

Write-Step "تمام!"
Write-Host ""
Write-Host "مراحلِ بعدی:" -ForegroundColor Cyan
Write-Host "  ۱. فایلِ .env رو باز کن و MAIN_BOT_TOKEN و ADMIN_TELEGRAM_IDS رو پر کن"
Write-Host "  ۲. برای اجرا:  python -m app.main"
Write-Host "  ۳. برای تست‌ها، به docs\local-testing-guide.md یا docs\local-testing-guide-windows-docker.md نگاه کن"
Write-Host ""
