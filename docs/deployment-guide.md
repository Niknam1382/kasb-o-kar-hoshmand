# راهنمای دیپلویِ پروداکشن

## Polling در برابرِ Webhook

- **Polling** (`RUN_MODE=polling`): ساده‌تره، نیازی به دامنه/HTTPS نداره،
  برای تستِ محلی یا سرورهای کوچیک مناسبه. با `python -m app.main` اجرا می‌شه.
- **Webhook** (`RUN_MODE=webhook`): سریع‌تر و برای پروداکشن توصیه می‌شه، ولی
  نیاز به یه دامنه با گواهیِ HTTPS معتبر داره (تلگرام فقط HTTPS رو قبول می‌کنه).
  از طریقِ FastAPI/Uvicorn اجرا می‌شه.

## راه‌اندازیِ حالتِ Webhook

1. یه دامنه با HTTPS معتبر آماده کن (مثلاً با Let's Encrypt پشتِ Nginx).
2. توی `.env`:
   ```
   RUN_MODE=webhook
   WEBHOOK_BASE_URL=https://yourdomain.com
   WEBHOOK_LISTEN_HOST=0.0.0.0
   WEBHOOK_LISTEN_PORT=8000
   MAIN_BOT_WEBHOOK_SECRET=<یه رشته‌ی تصادفیِ طولانی بساز>
   ```
3. اپ FastAPI رو با Uvicorn اجرا کن:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
   (روی استارتاپ، خودِ اپ webhook رو نزدِ تلگرام برای ربات اصلی ثبت می‌کنه؛
   ربات‌های فروشگاهیِ فعال هم به‌صورتِ خودکار بارگذاری و ثبت می‌شن.)

   دو مسیرِ webhook وجود داره: `/webhook/main` (ربات اصلی) و
   `/webhook/shop/{shop_bot_id}` (هر ربات فروشگاهی مسیرِ خودش رو داره).

## نمونه‌ی پیکربندیِ Nginx (reverse proxy)

```nginx
server {
    listen 443 ssl;
    server_name yourdomain.com;

    ssl_certificate     /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## اجرا به‌عنوانِ سرویسِ systemd (لینوکس)

`/etc/systemd/system/kasbokar.service`:

```ini
[Unit]
Description=Kasb-o-Kar Hoshmand
After=network.target postgresql.service

[Service]
Type=simple
User=kasbokar
WorkingDirectory=/opt/kasb-o-kar-hoshmand
EnvironmentFile=/opt/kasb-o-kar-hoshmand/.env
ExecStart=/opt/kasb-o-kar-hoshmand/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now kasbokar
sudo systemctl status kasbokar
```

برای حالتِ polling (بدونِ Uvicorn)، `ExecStart` رو به
`.../venv/bin/python -m app.main` تغییر بده.

## دیتابیس در پروداکشن

- همیشه قبل از دیپلویِ نسخه‌ی جدید، `alembic upgrade head` رو اجرا کن.
- از یه دیتابیسِ PostgreSQلِ مدیریت‌شده (یا حداقل با بکاپِ خودکارِ روزانه)
  استفاده کن.
- `ENCRYPTION_KEY` رو جایی امن (نه توی گیت) نگه دار — این کلید توکنِ همه‌ی
  ربات‌های فروشگاهی رو رمزگشایی می‌کنه؛ گم‌شدنش یعنی همه‌ی فروشگاه‌دارها باید
  توکن‌شون رو دوباره وارد کنن.

## چک‌لیستِ قبل از رفتن به پروداکشن

- [ ] `AUTH_MODE` رو از `test` به `sms` یا `email` تغییر بده (حالتِ `test` کدِ
      تاییدو مستقیم توی چت نشون می‌ده — فقط برای توسعه‌ست)
- [ ] `ai_api_key`، `zarinpal_merchant_id`، اطلاعاتِ کارتِ پلتفرم از پنلِ ادمین تنظیم شده
- [ ] حداقل یه کانالِ اجباری و یه طرحِ قیمت‌گذاری تعریف شده
- [ ] `MAIN_BOT_WEBHOOK_SECRET` یه مقدارِ تصادفیِ واقعی داره (نه خالی)
- [ ] بکاپِ خودکارِ دیتابیس فعاله
- [ ] مانیتورینگ/لاگینگ (حداقل لاگِ سطحِ اپ به فایل یا سرویسِ بیرونی) وصله

## W5 — مایگریشن‌ها و تنظیماتِ تازه
- **دو مایگریشنِ تازه** (head = `c8d2f5a7e1b4`): `b7c1e4a9d2f3` (رمزنگاریِ `bale_provider_token` در `admin_settings` و `shop_bots`؛ ستون‌ها به ۵۱۲ بلند می‌شن و داده‌یِ خامِ قدیمی با کلیدِ `ENCRYPTION_KEY` رمز می‌شه — **کلیدِ رمزنگاری رو گم نکن**، بدونِ آن توکن‌ها خونده نمی‌شن) و `c8d2f5a7e1b4` (ستون‌هایِ تنظیماتِ ادمین، `time_freezes`، `admin_credit_batches`). `alembic upgrade head` در entrypoint خودکار اجرا می‌شه؛ قبلش `pg_dump` بگیر.
- **`BALE_UPDATES_MODE`** (پیش‌فرض `polling`): در حالتِ polling ربات با getUpdates پرداختِ بله‌پی رو می‌گیره و **به HTTPSِ عمومی نیاز ندارد**؛ webhookِ قبلیِ بله موقعِ شروع حذف می‌شه. برایِ استقرارِ دارایِ دامنه‌یِ HTTPS مقدارِ `webhook` بذار (آدرسِ webhook مثلِ قبل). هر دو هم‌زمان ممکن نیست. اگه چند نمونه (replica) اجرا می‌کنی در حالتِ polling فقط **یک** نمونه باید فعال باشه.
- ایدمپوتنسیِ پرداخت‌هایِ قدیمی (`bale_paid_at`) حالا با قفلِ ردیف است؛ دریافتِ هم‌زمانِ webhook و polling اثرِ دوم ندارد.
