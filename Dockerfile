FROM python:3.12-slim

WORKDIR /app

# نصبِ پکیج‌های پایتون جدا از کپیِ کدِ برنامه، تا در بیلدهای بعدی (وقتی فقط کد
# عوض شده، نه requirements.txt) این مرحله از کش استفاده کنه و سریع‌تر باشه.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# د(ب): اجرای کانتینر با کاربرِ غیرroot. مالکیتِ /app به همان کاربر داده می‌شود چون پایتون
# `__pycache__` می‌سازد و entrypoint فایلِ موقتِ بررسیِ تنظیمات می‌نویسد.
RUN chmod +x /app/entrypoint.sh \
    && groupadd --system app \
    && useradd --system --gid app --home-dir /app --no-create-home app \
    && chown -R app:app /app

USER app

ENTRYPOINT ["/app/entrypoint.sh"]
