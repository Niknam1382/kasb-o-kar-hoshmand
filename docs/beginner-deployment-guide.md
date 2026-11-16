# راهنمایِ دیپلویِ مبتدی‌پسند — از صفر تا سرورِ زنده

برایِ کسی که برنامه‌نویس نیست. هر دستور رو دقیقاً کپی کن. جایی که `yourdomain.com` یا `YOUR_...` نوشته، مقدارِ خودت رو بذار.
اگه فقط می‌خوای روی لپ‌تاپت امتحان کنی (بدونِ دامنه)، `docs/docker-quickstart-guide.md` ساده‌تره.

**فهرست**: ۱) انتخابِ سرور · ۲) آماده‌سازیِ سرور · ۳) گرفتنِ پروژه · ۴) فایلِ `.env` · ۵) دامنه و HTTPS · ۶) اجرا و بررسیِ سلامت ·
۷) به‌روزرسانی بدونِ از دست رفتنِ دیتا · ۸) پشتیبان‌گیری · ۹) بازیابی · ۱۰) ریکاوریِ فاجعه · ۱۱) امنیت · ۱۲) پایش و ظرفیت

---

## ۱) انتخابِ سرور

- **سیستم‌عامل**: Ubuntu 24.04 (یا 22.04) LTS.
- **شروعِ مناسب**: ۲ هسته CPU، ۴ گیگ RAM، ۴۰ گیگ دیسک SSD. (برایِ چند ده فروشگاه کافیه؛ بخشِ ۱۲ رو ببین.)
- **مکان**: تلگرام در ایران فیلتره، پس سرور باید جایی باشه که به `api.telegram.org` و به سرویسِ AIِ انتخابیت دسترسی داره (معمولاً خارج از ایران).
  ⚠️ بعضی درگاه‌هایِ پرداختِ ایرانی ممکنه درخواست از IPِ خارج از ایران رو محدود کنن؛ قبل از تصمیمِ نهایی با یه تراکنشِ خیلی کوچیک
  زرین‌پال/بله‌پی رو از همون سرور امتحان کن.
- یه **دامنه** لازم داری (مثلاً `bot.yourdomain.com`) که رکوردِ `A`اش به IPِ سرور اشاره کنه (برایِ HTTPS و webhook).

## ۲) آماده‌سازیِ سرور

با SSH وصل شو (`ssh ubuntu@YOUR_SERVER_IP`) و این‌ها رو بزن:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y unzip curl ufw
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
```
بعدش یه بار از سرور خارج شو و دوباره وصل شو (تا دسترسیِ Docker فعال بشه)، و بررسی کن: `docker compose version`.

فایروال (فقط SSH و وب باز باشه):
```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

## ۳) گرفتنِ پروژه روی سرور

از کامپیوترت zip رو به سرور بفرست (روی ویندوز توی PowerShell یا CMD):
```
scp kasb-o-kar-hoshmand.zip ubuntu@YOUR_SERVER_IP:~/
```
روی سرور:
```bash
cd ~
unzip kasb-o-kar-hoshmand.zip
cd kasb-o-kar-hoshmand
ls
```
باید فایل‌هایی مثلِ `docker-compose.yml`، `Dockerfile`، `app`، `docs` رو ببینی.

## ۴) فایلِ `.env` (تنظیماتِ مخفی)

```bash
cp .env.docker.example .env
nano .env
```
مهم‌ترین مقدارها:

| متغیر | چی بذارم؟ |
|-------|-----------|
| `DATABASE_URL` | دست نزن (به سرویسِ `db` توی docker-compose اشاره می‌کنه). اگه رمزِ دیتابیس رو عوض کردی (بخشِ ۱۱) اینجا هم عوض کن. |
| `MAIN_BOT_TOKEN` | توکنِ ربات اصلی از @BotFather |
| `ADMIN_TELEGRAM_IDS` | آیدیِ عددیِ تلگرامِ خودت (از @userinfobot)؛ چندتا → با کاما |
| `ENCRYPTION_KEY` | کلیدِ رمزنگاری — دستورِ ساختنش پایینه. **این رو جدا از سرور هم نگه دار** |
| `RUN_MODE` | روی سرور: `webhook` |
| `WEBHOOK_BASE_URL` | `https://yourdomain.com` (بدونِ `/` آخرِ آدرس) |
| `MAIN_BOT_WEBHOOK_SECRET` | یه رشته‌یِ تصادفیِ بلند: `openssl rand -hex 32` |
| `AUTH_MODE` | روی سرورِ واقعی **حتماً `sms` یا `email`**؛ `test` کدِ تایید رو توی چت نشون می‌ده (فقط برایِ تست) |
| `SMTP_*` | فقط اگه `AUTH_MODE=email` |
| `BALE_BOT_TOKEN`، `BALE_WEBHOOK_SECRET` | اختیاری؛ فقط اگه بله‌پی می‌خوای |

ساختنِ کلیدِ رمزنگاری (بعد از `docker compose build`، بخشِ ۶):
```bash
docker compose build
docker compose run --rm bot python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
خروجی رو جلویِ `ENCRYPTION_KEY=` بذار. بعدش دسترسیِ فایل رو محدود کن: `chmod 600 .env`.

> ⚠️ **`ENCRYPTION_KEY` رو هیچ‌وقت عوض نکن و گمش نکن.** اگه گم بشه، توکنِ ذخیره‌شده‌یِ همه‌یِ ربات‌هایِ فروشگاهی قابلِ خوندن نیست و همه‌یِ
> فروشگاه‌دارها باید توکن‌شون رو دوباره وارد کنن. یه کپی توی یه مدیرِ رمز یا جایِ امنِ دیگه بذار.

## ۵) دامنه و HTTPS (با Caddy — ساده‌ترین راه)

۱. رکوردِ `A` دامنه‌ات رو به IPِ سرور بده و صبر کن (چند دقیقه تا چند ساعت).
۲. Caddy رو نصب کن (HTTPS رو خودش خودکار می‌گیره و تمدید می‌کنه):
```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install -y caddy
```
۳. فایلِ `/etc/caddy/Caddyfile` رو باز کن (`sudo nano /etc/caddy/Caddyfile`)، کلِ محتواش رو پاک کن و این رو بذار:
```
yourdomain.com {
    reverse_proxy 127.0.0.1:8000
}
```
۴. `sudo systemctl reload caddy`.

حالا باید به ربات اجازه بدی از بیرونِ کانتینر روی پورتِ ۸۰۰۰ (فقط از خودِ سرور) در دسترس باشه. کنارِ `docker-compose.yml` یه فایلِ
تازه به اسمِ `docker-compose.override.yml` بساز (Compose خودش خودکار ادغامش می‌کنه):

```yaml
services:
  bot:
    ports:
      - "127.0.0.1:8000:8000"
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "5"
  db:
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "5"
```
(بخشِ `logging` جلوی پر شدنِ دیسک با لاگ رو می‌گیره.)

**پورتِ دیتابیس**: توی `docker-compose.yml` زیرِ سرویسِ `db` خطِ `- "5432:5432"` هست که دیتابیس رو به بیرون باز می‌کنه. روی سرورِ واقعی
اون خط رو به `- "127.0.0.1:5432:5432"` تغییر بده (فقط از خودِ سرور قابلِ دسترسه). `nano docker-compose.yml`

## ۶) اجرا و بررسیِ سلامت

```bash
docker compose build
docker compose up -d
docker compose ps
docker compose logs -f bot
```
(با `Ctrl+C` از نمایشِ لاگ خارج شو؛ ربات به کارش ادامه می‌ده.) مایگریشنِ دیتابیس موقعِ استارت **خودکار** اجرا می‌شه
(`entrypoint.sh`). توی لاگ باید «مایگریشن‌ها با موفقیت اعمال شدن» و بعدش اجرایِ ربات رو ببینی.

بررسیِ سلامت از بیرون: `curl https://yourdomain.com/health` — باید جوابِ موفق بده. بعدش توی تلگرام به ربات اصلی `/admin` بزن
(با همون آیدیِ عددیِ ادمین)؛ پنلِ ادمین باید باز بشه. تنظیماتِ اولیه‌یِ ادمین (کلیدِ AI، قیمت‌گذاری، کانالِ اجباری، طرح): `docs/admin-guide.md`.

اگه چیزی کار نکرد: `docker compose logs --tail=100 bot` رو نگاه کن؛ معمولاً یا `.env` ناقصه (پیام می‌ده کدوم)، یا دامنه هنوز به IP نرسیده.

## ۷) به‌روزرسانی بدونِ از دست رفتنِ دیتا

دیتا توی «volume»ِ داکر (`postgres_data`) می‌مونه و با بیلد/ری‌استارتِ کانتینر پاک نمی‌شه. مراحلِ امنِ آپدیت:

```bash
cd ~/kasb-o-kar-hoshmand
mkdir -p ~/backups
docker compose exec -T db pg_dump -U postgres -Fc kasbokar > ~/backups/before-update-$(date +%F-%H%M).dump   # ۱) پشتیبان
# ۲) فایل‌هایِ نسخه‌یِ جدید رو روی پوشه کپی/جایگزین کن (zip جدید رو unzip کن؛ .env و docker-compose.override.yml رو دست نزن)
docker compose build                                                                                          # ۳) بیلد
docker compose up -d                                                                                          # ۴) جایگزینیِ ربات؛ مایگریشن خودکار
docker compose logs --tail=50 bot                                                                             # ۵) بررسی
curl https://yourdomain.com/health
```
زمانِ قطعی: فقط چند ثانیه (ری‌استارتِ کانتینرِ `bot`)؛ پیام‌هایی که توی اون چند ثانیه می‌رسن، تلگرام معمولاً دوباره تحویل می‌ده.
**اگه آپدیت خراب شد**: نسخه‌یِ قبلیِ کد رو برگردون، `docker compose build && docker compose up -d`؛ و اگه مایگریشنِ جدید دیتابیس رو عوض کرده
بود، بخشِ ۹ (بازیابی از پشتیبانِ همون قبلِ آپدیت) امن‌ترین راهه.

## ۸) پشتیبان‌گیری

**دستی (یک بار):**
```bash
mkdir -p ~/backups
docker compose exec -T db pg_dump -U postgres -Fc kasbokar > ~/backups/kasbokar-$(date +%F-%H%M).dump
ls -lh ~/backups
```

**خودکار (هر شب ساعتِ ۳ + نگه‌داریِ ۱۴ روز):**
```bash
crontab -e
```
و این خط رو ته فایل اضافه کن (`ubuntu` رو با نامِ کاربریِ خودت عوض کن؛ علامتِ `\%` عمدی‌ه):
```
0 3 * * * cd /home/ubuntu/kasb-o-kar-hoshmand && docker compose exec -T db pg_dump -U postgres -Fc kasbokar > /home/ubuntu/backups/kasbokar-$(date +\%F).dump && find /home/ubuntu/backups -name 'kasbokar-*.dump' -mtime +14 -delete
```
**نسخه‌یِ بیرونی (خیلی مهم):** پشتیبانی که روی همون سرور باشه، با مُردنِ سرور از بین می‌ره. هر روز/هفته یه کپی جایِ دیگه‌ای هم بذار؛ مثلاً از
کامپیوتر خودت: `scp ubuntu@YOUR_SERVER_IP:~/backups/kasbokar-2026-10-05.dump .` (یا با rclone به یه فضایِ ابری). این فایل‌ها دیتایِ
فروشگاه‌دارها رو دارن؛ خصوصی نگهشون دار. و `.env`/`ENCRYPTION_KEY` رو **جدا** ذخیره کن (بدونِ اون، توکنِ ربات‌هایِ داخلِ پشتیبان قابلِ خوندن نیست).

## ۹) بازیابی (و تستِ بازیابی)

**اول تست کن که پشتیبانت واقعاً کار می‌کنه** (بدونِ دست‌زدن به دیتابیسِ اصلی؛ ماهی یک بار انجامش بده):
```bash
docker compose exec -T db createdb -U postgres kasbokar_restore_test
docker compose exec -T db pg_restore -U postgres -d kasbokar_restore_test --no-owner < ~/backups/kasbokar-2026-10-05.dump
docker compose exec -T db psql -U postgres -d kasbokar_restore_test -c "select count(*) from shop_owners;"
docker compose exec -T db dropdb -U postgres kasbokar_restore_test
```
اگه تعدادِ فروشگاه‌دارها درست نشون داده شد، پشتیبان سالمه.

**بازیابیِ واقعی** (دیتابیسِ فعلی خراب/اشتباهاً پاک شده):
```bash
docker compose stop bot
docker compose exec -T db dropdb -U postgres --if-exists kasbokar
docker compose exec -T db createdb -U postgres kasbokar
docker compose exec -T db pg_restore -U postgres -d kasbokar --no-owner < ~/backups/kasbokar-2026-10-05.dump
docker compose start bot
docker compose logs --tail=50 bot
```
(هر چیزی که بعد از زمانِ اون پشتیبان ثبت شده بود از دست می‌ره؛ برای همین پشتیبانِ شبانه مهمه.)

## ۱۰) ریکاوریِ فاجعه (سرور مرد / دیتابیس کاملاً از بین رفت)

فرض: یه پشتیبان (`.dump`) و کپیِ `.env` (با همون `ENCRYPTION_KEY`) جایِ امن داری.

۱. یه سرورِ تازه بگیر و **بخش‌هایِ ۲ تا ۳** رو انجام بده (Docker، فایروال، zip پروژه).
۲. فایلِ `.env` قبلی رو (با **همون** `ENCRYPTION_KEY`) روی سرورِ جدید بذار: `nano .env` و `chmod 600 .env`.
۳. فایلِ `docker-compose.override.yml` و تغییرِ پورتِ دیتابیس (بخشِ ۵) رو دوباره اعمال کن.
۴. فقط دیتابیس رو بالا بیار: `docker compose build` سپس `docker compose up -d db` و ۱۰ ثانیه صبر کن.
۵. پشتیبان رو به سرور بفرست (`scp kasbokar-….dump ubuntu@NEW_IP:~/backups/`) و بازیابی کن:
```bash
docker compose exec -T db createdb -U postgres kasbokar
docker compose exec -T db pg_restore -U postgres -d kasbokar --no-owner < ~/backups/kasbokar-2026-10-05.dump
```
۶. دامنه رو به IPِ جدید بده (رکوردِ `A`) و Caddy رو (بخشِ ۵) دوباره راه بنداز.
۷. `docker compose up -d` — ربات موقعِ استارت webhookها رو (ربات اصلی و رباتِ فروشگاه‌هایِ فعال) دوباره نزدِ تلگرام ثبت می‌کنه.
۸. بررسی: `curl https://yourdomain.com/health`، یه `/admin` به ربات اصلی، و چک کردنِ یکی-دو فروشگاه (کیف‌پول، محصول).
۹. اگه توکنِ بعضی ربات‌ها «نامعتبر» شد، یعنی `ENCRYPTION_KEY` یکی نبوده؛ فروشگاه‌دار باید توکن رو دوباره وارد کنه.

## ۱۱) امنیتِ پایه (قبل از اعلامِ عمومی)

- [ ] `AUTH_MODE` ≠ `test`، `MAIN_BOT_WEBHOOK_SECRET` مقدارِ واقعی داره.
- [ ] رمزِ دیتابیس: توی `docker-compose.yml` مقدارِ `POSTGRES_PASSWORD` رو **قبل از اولین اجرا** (روی دیتابیسِ خالی) قوی کن و همون رو توی
      `DATABASE_URL` (`.env`) بذار. (عوض‌کردنش روی دیتابیسِ موجود با این روش اثر نداره.)
- [ ] پورتِ ۵۴۳۲ فقط روی `127.0.0.1` (بخشِ ۵)؛ `sudo ufw status` فقط ۲۲، ۸۰، ۴۴۳ رو نشون بده.
- [ ] ورودِ SSH با کلید (نه رمز) و `chmod 600 .env`.
- [ ] به‌روزرسانیِ خودکارِ امنیتیِ سیستم: `sudo apt install -y unattended-upgrades`.
- [ ] آیدیِ ادمین‌ها (`ADMIN_TELEGRAM_IDS`) فقط خودت و افرادِ مورد اعتماد.
- [ ] پشتیبانِ شبانه + یک بار تستِ بازیابی (بخش‌هایِ ۸ و ۹).

## ۱۲) پایش و ظرفیت

روزانه/هفتگی:
```bash
docker compose ps                       # هر دو سرویس باید Up باشن
docker compose logs --tail=100 bot      # خطایِ تکراری؟
docker stats --no-stream                # مصرفِ CPU/RAM
df -h                                   # دیسک پر نشده باشه
```
- **اولین هفته‌ها**: مصرفِ RAM/CPU و تعدادِ اتصال‌هایِ دیتابیس رو یادداشت کن. هدف: CPU معمولاً زیرِ ۶۰٪ و RAM خالیِ کافی.
- **اگه رشد کردی**: اول سرور رو بزرگ‌تر کن (CPU/RAM)، بعد دیتابیس رو به یه PostgreSQLِ مدیریت‌شده ببر (`DATABASE_URL` رو عوض کن؛
  از پشتیبان بازیابی کن). اجرایِ هم‌زمانِ چند نمونه‌یِ ربات فعلاً توصیه نمی‌شه (محدودیتِ نرخ و قفل‌ها درون‌پردازه‌ای‌ن؛ `docs/PROJECT_COMPLETION.md` بخشِ ۸).
- هزینه‌یِ AI فقط به مصرفِ مشتری‌ها بستگی داره و از کیف‌پولِ فروشگاه‌دارها کم می‌شه؛ مدیریتش: `docs/ai-production-guide.md`.

---

## 🖥 نگاهِ عملیاتی در مرورگر (پ۹۱)

پس ازِ بالا آمدنِ سرویس‌ها، در همان سرور می‌توانی وضعیت را در مرورگر ببینی:

1. در `.env` مقدارِ `METRICS_TOKEN` را پر کن (یکِ رشتهٔ تصادفیِ طولانی؛ این تنها رمزِ این صفحه است).
2. آدرس: `https://دامنه-ی-سرور-تو/panel` → مرورگر نامِ کاربر و رمز می‌خواهد؛ نامِ کاربر هرچی باشد،
   رمز = همان `METRICS_TOKEN`.
3. صفحه فقط‌خواندنی است و هر ۳۰ ثانیه خودش را تازه می‌کند: تعدادِ پروسه‌هایِ زنده (اگر کمتر از تعدادِ
   کانتینرهایِ تو شد، یکِ worker خوابیده)، درصدِ بار/رم/دیسک، استخرِ دیتابیس، فشارِ کلیدهایِ AI،
   یافته‌هایِ عیب‌یاب و فهرستِ فروشگاه‌ها.
4. برایِ ماشین‌ها (نه آدم) همان داده در `GET /ops/status` هست با هدرِ `x-metrics-token`.

⚠️ دو قیدِ امنیتی: این صفحه باید پشتِ **HTTPS** باشد (رمز با Basic Auth ارسال می‌شود) و بهتر است با
`allow` رویِ IPِ اداری یا VPN محدودش کنی. اگر `METRICS_TOKEN` خالی بماند، هر دو مسیر ۴۰۴ می‌دهند.
