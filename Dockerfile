FROM python:3.12-slim

WORKDIR /app

# نصبِ پکیج‌های پایتون جدا از کپیِ کدِ برنامه، تا در بیلدهای بعدی (وقتی فقط کد
# عوض شده، نه requirements.txt) این مرحله از کش استفاده کنه و سریع‌تر باشه.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
