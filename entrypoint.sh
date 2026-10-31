#!/bin/sh
# این اسکریپت خودکار قبل از اجرای ربات صدا زده می‌شه: صبر می‌کنه دیتابیس آماده
# بشه، مایگریشن‌ها رو اجرا می‌کنه، و بعد ربات رو بالا میاره. یعنی کاربر هیچ‌وقت
# نیازی نداره دستورِ alembic رو دستی بزنه.
set -e

# اگه دستورِ دیگه‌ای بهش پاس داده شده (مثلاً برای ساختنِ کلیدِ رمزنگاری با
# «docker compose run --rm bot python -c ...»)، همون رو مستقیم اجرا کن و از
# منطقِ صبر-برای-دیتابیس/مایگریشن رد شو. بدونِ این چک، چون Dockerfile از
# ENTRYPOINT استفاده می‌کنه، هر دستوری که پاس بدی به‌جای جایگزین‌کردنِ این
# اسکریپت، فقط به‌عنوانِ آرگومان بهش اضافه می‌شه و نادیده گرفته می‌شه.
if [ "$#" -gt 0 ]; then
    exec "$@"
fi

echo "در حالِ بررسیِ صحتِ تنظیماتِ .env ..."
if ! python -c "
from app.config import settings
from cryptography.fernet import Fernet
Fernet(settings.encryption_key.encode())
" 2>/tmp/config_check_error.txt; then
    echo ""
    echo "خطا: فایلِ .env ناقص یا نادرسته. جزئیاتِ خطا:"
    echo "--------------------------------------------------"
    cat /tmp/config_check_error.txt
    echo "--------------------------------------------------"
    echo "احتمالاً MAIN_BOT_TOKEN خالیه یا ENCRYPTION_KEY درست پر نشده/کامل کپی نشده."
    exit 1
fi
echo "تنظیماتِ .env معتبره."

echo "در حالِ بررسیِ آماده‌بودنِ دیتابیس..."
MAX_TRIES=30
TRIES=0
until python -c "
import asyncio
from app.config import settings
from sqlalchemy.ext.asyncio import create_async_engine

async def check():
    engine = create_async_engine(settings.database_url)
    async with engine.connect() as conn:
        pass
    await engine.dispose()

asyncio.run(check())
" 2>/tmp/db_check_error.txt; do
    TRIES=$((TRIES + 1))
    if [ "$TRIES" -ge "$MAX_TRIES" ]; then
        echo ""
        echo "دیتابیس بعد از ${MAX_TRIES} تلاش (۶۰ ثانیه) هنوز آماده نیست. آخرین خطا:"
        echo "--------------------------------------------------"
        cat /tmp/db_check_error.txt
        echo "--------------------------------------------------"
        exit 1
    fi
    echo "دیتابیس هنوز آماده نیست، ${TRIES}/${MAX_TRIES}... ۲ ثانیه صبر می‌کنیم"
    sleep 2
done
echo "دیتابیس آماده‌ست."

echo "در حالِ اجرای مایگریشن‌های دیتابیس (alembic upgrade head)..."
alembic upgrade head
echo "مایگریشن‌ها با موفقیت اعمال شدن."

echo "در حالِ اجرای ربات..."
exec python -m app.main
