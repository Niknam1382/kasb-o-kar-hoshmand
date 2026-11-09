FROM python:3.12-slim

WORKDIR /app

# P18 · B6: فونتِ فارسیِ پشتیبان. Vazirmatn داخلِ ایمیج باندل شده (app/assets/fonts)، ولی اگر آن
# فایل به هر دلیلی به ایمیج نرسد، DejaVu Sans (که بلوکِ عربی/فارسی را دارد) از سیستم برداشته می‌شود.
# عمداً قبلِ USER app نصب می‌شود؛ کاربرِ غیرroot نمی‌تواند بسته نصب کند.
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# نصبِ پکیج‌های پایتون جدا از کپیِ کدِ برنامه، تا در بیلدهای بعدی (وقتی فقط کد
# عوض شده، نه requirements.txt) این مرحله از کش استفاده کنه و سریع‌تر باشه.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# د(ب): اجرای کانتینر با کاربرِ غیرroot. مالکیتِ /app به همان کاربر داده می‌شود چون پایتون
# `__pycache__` می‌سازد و entrypoint فایلِ موقتِ بررسیِ تنظیمات می‌نویسد.
# P44 · موردِ ۵۱: /backups هم مالکِ همان کاربر می‌شود تا volumeِ مشترک (در docker-compose) وقتی
# برایِ اولینِ بار ساخته می‌شود، مالکیتِ پوشه را از ایمیج به ارث ببرد؛ بدونِ این، جابِ نگهداری
# نمی‌تواند فایلِ قدیمی را پاک کند (فقط خواندن ممکن است).
RUN chmod +x /app/entrypoint.sh \
    && groupadd --system app \
    && useradd --system --gid app --home-dir /app --no-create-home app \
    && mkdir -p /backups \
    && chown -R app:app /app /backups

USER app

ENTRYPOINT ["/app/entrypoint.sh"]
