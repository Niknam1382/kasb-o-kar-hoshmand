# AGENTS.md — قواعدِ کاریِ این مخزن (برایِ هر جلسهٔ تازه)

اگر تازه واردِ این پروژه شده‌ای (یا پوشه جابه‌جا شده): اول همین فایل، بعد
`docs/HANDOFF-P29.md` (وضعیتِ امروز + عددها + کارهایِ باز) را بخوان.
این فایل هیچ رازی ندارد؛ توکن‌ها فقط در `.env` هستند که در گیت نیست.

## ۱) این چیست
پلتفرمِ چندفروشگاهیِ «کسب‌وکار هوشمند»: هر فروشگاه با توکنِ خودش یک رباتِ تلگرامی
می‌گیرد که با هوش مصنوعی به مشتری جواب می‌دهد، و صاحبِ فروشگاه از یک رباتِ مرکزی
محصول/سفارش/کیف‌پول/کمپین/CRM/گزارش را مدیریت می‌کند. Python 3.12، aiogram 3.30،
SQLAlchemy 2 async + asyncpg، Alembic، PostgreSQL 16، FastAPI (فقط `/health` و `/metrics`)،
fpdf2 برایِ فاکتورِ فارسی. اجرایِ واقعی با Docker Compose (دو سرویس: `db` و `bot`).
توضیحِ کاملِ عملکردیِ محصول به زبانِ ساده: `docs/bot-functional-overview-fa.txt`.

## ۲) قوانینِ غیرقابلِ مذاکره (از دستورهایِ مستقیمِ مالکِ محصول)
1. **هرگز `git push` نکن.** ریموتِ این مخزن عمداً تعریف نشده است. هر بخش = یکِ commit با پیامِ کوتاهِ فارسی.
2. **فایلِ `.env` را باز نکن، تغییر نده، commit نکن.** مقدارِ هیچ توکن/کلید/رمزی را در خروجی، لاگ،
   تست، commit یا مستندات چاپ نکن. فقط `.env.example` و `.env.docker.example` را به‌روز کن.
3. **دستورهایِ مخرب** (`docker compose down -v`، `git reset --hard`، حذفِ volume/دیتابیس/فایل)
   فقط با ضرورتِ روشن و **اول `pg_dump`** از دیتابیسِ توسعه.
4. مایگریشن‌ها **افزوندی** باشند (هیچ ستون/جدولی حذف نشود، `server_default` داشته باشند) و
   **همیشه فقط یکِ alembic head**. پیش از commit: `docker compose run --rm bot alembic heads`.
5. UI کاملاً فارسی، راست‌به‌چپ، ارقامِ جلالی؛ در متنِ مشتری هیچ شناسهٔ فنیِ داخلی و هیچ
   عدد/کلمهٔ انگلیسیِ قاطیِ فارسی نباشد. `callback_data` ≤ ۶۴ بایت.
6. هر دکمهٔ تازه در کیبورد + `_KNOWN_MENU_BUTTONS` + تستِ منو/RBAC ثبت شود.
7. پول و وضعیت **ایدبمپوتنت** باشند؛ پیش از فراخوانیِ AI/شبکه `commit()` کن.
8. هر ویژگیِ تازه **یکِ فایلِ تستِ اختصاصی** می‌خواهد که در `tests_manual/run_all_tests.py` ثبت شود.
   تست‌هایِ قدیمی فقط وقتی عوض می‌شوند که رفتار عمداً عوض شده و در `docs/PROGRESS.md` نوشته شده باشد.
9. بدونِ اجازه: دیپلوی، پوش، مرج، تغییرِ قابلیت‌ها در «بهینه‌سازی»؛ و هرگز پیام/پرداختِ واقعی نفرست.
10. هر گزارشِ عددی با برچسبِ **MEASURED / ESTIMATED / EXTRAPOLATED / NOT RUN**. اگر چیزی را با چشم
    ندیده‌ای، نگو «دیدم». اگر تستی که دست نخورده fail شد، آن را flaky نخوان — دوباره اجرا کن.
11. فایل‌هایِ بزرگ را از نو ننویس؛ وابستگیِ تازه را pin کن؛ برایِ مقیاس، منابعِ پولی/سنگینِ تازه اضافه نکن.
12. بیوگرافی فقط رویِ ربات‌هایِ فروشگاهی اعمال شود، بازرسی per-ربات باشد، و اخطار فقط به همان متخلف برود.

## ۳) پنج گیتِ ایستایی (ابتدا و انتهایِ هر گروه کار)
`python scripts/check_gates.py` — رویِ ویندوز **بدونِ داکر** هم اجرا می‌شود. شاملِ:
`check_refs.py` (ارجاع‌ها)، `check_attrs.py` (ستون‌هایِ مدل)، `lint_names.py`،
`check_callbacks.py` (شکلِ `callback_data`)، `check_text_hygiene.py` (نویسهٔ سیریلیک/CJK/هانجی) +
بررسیِ ثبتِ فایل‌هایِ تست در `run_all_tests.py`. `ruff --select F,E9` رویِ `app/` هم باید تمیز باشد.
⚠️ گیت‌ها نشتِ **لاتین** داخلِ کلمهٔ فارسی را نمی‌گیرند (`dیتابیس`، `lحن`، «پنجم passes»)؛ بعد از
هر پاسِ متنیِ سنگین، یکِ اسکنِ موقتِ `python` با الگویِ `[A-Za-z][فارسی]` و `[فارسی][A-Za-z]` بزن
و پیام‌هایِ commit را هم اسکن کن.

## ۴) چطور اجرا و تست شود (این محیط)
```bash
# هیچ volume mount کد نیست ⇒ بعد از هر تغییرِ کد، build اجباری است
docker compose build bot
docker compose stop bot                      # هنگامِ سوئیت (تا قفلِ polling و TRUNCATE نسازد)
docker compose run --rm -e PYTHONIOENCODING=utf-8 -e PYTHONUTF8=1 bot python3 tests_manual/run_all_tests.py
docker compose run --rm -e PYTHONIOENCODING=utf-8 -e PYTHONUTF8=1 bot python3 tests_manual/run_one.py test_p29_job_query_bounds.py
docker compose up -d bot                     # بعد ازِ تمامِ کارها: محیط را روشن برگردان
docker compose exec -T bot python -c "import urllib.request;print(urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=5).status)"
```
- تست‌ها فقط رویِ `kasbokar_test` می‌نویسند (`tests_manual/db_env.py`، گاردِ `is_test_database()`).
  اجرایِ مستقیمِ یکِ فایلِ تست رویِ `kasbokar` متوقف می‌شود؛ برایِ همین `run_one.py` را استفاده کن.
- `harness.py`: `FakeSession` (بدونِ شبکه؛ شمارشِ پیام‌ها، `edited_captions`، `fail_answer_callbacks`)،
  `build_test_dispatchers()` **فقط یکِ بار در هر پروسه** (راوترها singleton‌اند)،
  `make_shop_bot`/`register_fake_shop_bot` (بدونِ شبکه ثبت کن)، `seed_usable_shop` در `shop_setup.py`.
- توکنِ جعلیِ داخلِ تست/سید باید با قاعدهٔ aiogram بخورد: رقم‌ها، دونقطه، و ≥۳۰ نویسه بعد از دونقطه.
- سنجشِ مقیاس: `docker compose run --rm bot python3 scripts/scale_probe.py --sizes 1,50,200,500 --levels 25,100,300 --per-level 400 --memory --webhook-sample 20`
- بارسنجیِ دیتابیس: `scripts/loadtest_message_path.py` / `loadtest_wallet_paths.py` (نیازمند `LOADTEST_DB_CONFIRM=1` و دیتابیسِ جدا).
- PDFِ مستندات: `docs/` در `.dockerignore` است ⇒ داخلِ ایمیج نیست. رِسیپت:
  `MSYS_NO_PATHCONV=1 docker compose run --rm -v "C:/Users/.../Temp/work:/work:rw" bot sh -c "cd /app && python3 scripts/build_docs_pdf.py /work/x.md /work/x.pdf"`
  (کانتینرِ خاموش با `compose cp` فایل را نشان نمی‌دهد.)
- شمارشِ statement در تست/اسکریپت: `event.listen(engine.sync_engine, "before_cursor_execute", ...)`؛
  شمارندهٔ کلاس‌ای را با `self.x += 1` زیاد نکن (instance attr می‌سازد و صفر می‌ماند).
- مقایسهٔ «ایمیج == دیسک»: هشِ کاملِ `sha256sum` را در فایل بنویس و مقایسه کن؛ `cut` رویِ هشِ نصفه،
  ناسازگاریِ ساختگی می‌سازد.

## ۵) تله‌هایِ این ماشین (win32 + Git Bash + Docker Desktop)
- `grep` با الگویِ فارسی گاهی خروجی را می‌بلعد: خروجی را در فایلِ plain بنویس، بعد `tail` کن.
- برایِ پایتون: `PYTHONIOENCODING=utf-8 PYTHONUTF8=1` (و `PYTHONUNBUFFERED=1` برایِ لاگِ زنده).
- MSYS مسیرهایِ مطلقِ داخلِ کانتینر را عوض می‌کند: یا `sh -c "cmd //tmp//file"`، یا
  `MSYS_NO_PATHCONV=1` + مسیرِ ویندوزی در `-v`.
- کشتنِ یکِ تسکِ background در این CLI کانتینرِ `compose run` را نمی‌کشد؛ با `docker rm -f` پاکشان کن.
- فایل‌هایِ CRLF/LF: یکِ `\r` تنهایِ وسطِ فایل، diff را به بازنویسیِ کاملِ فایل تبدیل می‌کند؛ بعد ازِ
  ویرایش‌هایِ دسته‌ای، `git diff --stat` را چک کن.
- **این شبکه به `api.telegram.org` نمی‌رسد** (DNS آن را به `10.10.34.36`، یعنی آدرسِ خصوصیِ
  غیرقابلِ مسیر می‌دهد) ⇒ سرویسِ `bot` با `TelegramNetworkError` هر ~۳۰ ثانیه ری‌استارت می‌شود و
  هر سنجشِ «تلگرام واقعی» (RTT، ارسالِ پیام، پرداختِ بله) باید NOT RUN برچسب بخورد.

## ۶) اگر پوشه را جابه‌جا کردی (مهم)
نامِ پروژهٔ داکر از **نامِ پوشه** ساخته می‌شود و حجمِ دیتابیس `kasb-o-kar-hoshmand_postgres_data`
به همین نام است. اگر نامِ پوشه عوض شود، `docker compose up` یکِ دیتابیسِ **خالیِ** تازه می‌سازد و
همه‌چیز «پاک شده» به‌نظر می‌آید (داده در حجمِ قبلی سالم است). راهِ حل:
- `name: kasb-o-kar-hoshmand` در بالایِ `docker-compose.yml` (این کار در P29 انجام شد)، یا
- `docker compose -p kasb-o-kar-hoshmand ...`، یا همان نامِ پوشه را نگه دار.
- `.env` در گیت نیست ⇒ با کپیِ پوشه منتقل می‌شود، ولی با `git clone` نه. **`ENCRYPTION_KEY` باید
  دقیقاً همان بماند**، وگرنه هیچ توکن/رازِ ذخیره‌شده‌ای بازخوانی نمی‌شود.
- چک‌لیستِ کاملِ جابه‌جایی: `docs/HANDOFF-P29.md` §۵.

## ۷) نقشهٔ مستندات
`docs/PROGRESS.md` (تاریخچهٔ فازها) · `docs/changelog-pNN.md` (هر فاز) · `REMAINING_ISSUES.md` (بازمانده‌ها) ·
`TEST_RESULTS.md` (عددِ هر اجرا) · `SCALABILITY_AND_LOAD_TEST_REPORT.md` (ظرفیت) ·
`docs/deployment-playbook.md` + `.pdf` (دیپلوی، سخت‌افزار، مقیاس) · `docs/user-guide.md` (فروشگاه‌دار) ·
`docs/admin-guide.md` (ادمین) · `docs/local-testing-guide-windows-docker.md` (محیطِ توسعهٔ محلی).
