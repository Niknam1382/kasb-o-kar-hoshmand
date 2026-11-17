from __future__ import annotations

import enum

from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthMode(str, enum.Enum):
    TEST = "test"
    SMS = "sms"
    EMAIL = "email"


class RunMode(str, enum.Enum):
    POLLING = "polling"
    WEBHOOK = "webhook"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    # ظرفیت (فازِ ۶-الف · بازمهندسیِ P20-F): اندازه‌یِ استخرِ اتصال‌هایِ دیتابیس.
    # بارسنجیِ E (دیتابیسِ جدا، ۲۰۰۰ پیام در هر سطح): با `pool=20/overflow=30` در همزمانیِ ۵۰
    # تنها ۴۸ پیام/ثانیه و میانگینِ ۹۴۶ms گرفتم؛ با همان استخرِ ثابت و `overflow=0` همان بار
    # ۱۳۶ پیام/ثانیه و ۲۴۵ms شد (سقفِ واقعیِ پروسه ≈ ۱۴۵). علتِ افتِ اولِ «ساختن و بستنِ
    # اتصالِ اضافه» در هر موج است، نه دیتابیس (pgbench روی همین میزبان ≈ ۲٬۰۰۰ تراکنش/ثانیه).
    # پس: استخر را به اندازهٔ اوجِ ترافیک بگیر و overflow را صفر بگذار — صفِ کوتاه، بهتر از
    # پرِتشِ اتصال است. `pool_timeout` هم سقفِ صبرِ یکِ درخواست است (نه زمانِ پاسخِ AI).
    # نکتهٔ مقیاس: هر پروسهٔ کارگر استخرِ خودش را دارد ⇒ workers × (pool_size+overflow) +
    # چند اتصالِ مدیریت < max_connections پستگرس (پیش‌فرض ۱۰۰).
    db_pool_size: int = 25
    db_max_overflow: int = 0
    db_pool_timeout: int = 15
    # پ۱۰۱: `null` یعنی هر اتصال موقعِ برگشتن بسته می‌شود (NullPool). در تولید خالی بگذار؛
    # سوئیتِ تست این را `null` می‌گذارد تا اتصالِ رهاشده در پایانِ پروسه GC نشود و نویزِ
    # `greenlet is being finalized` / `non-checked-in connection` پدیدار نشود.
    db_pool_class: str = ""
    ai_max_concurrent_calls: int = 40
    # P47: این عدد دیگر «سقفِ هرِ کلید» نیست؛ سقفِ کلِ پلتفرم است. سقفِ خودِ هرِ کلید در
    # پنلِ ادمین (بخشِ «کلیدهایِ AI») نوشته می‌شود و کلیدهایی که عددی ننوشته‌اند این
    # مقدار را مساوی بینِ خودشان تقسیم می‌کنند. ⇒ برایِ ۲٬۰۰۰ درخواستِ هم‌زمان: ۲۰۰۰ (یا
    # بیشتر) اینجا، و ۲۰۰ به ازایِ هرِ یکِ از ۱۰ کلید در پنل.
    ai_queue_timeout_seconds: int = 120
    # P47: سقفِ استخرِ سوکتِ aiohttp به *هرِ میزبان*. پیش‌فرضِ خودِ aiohttp ۱۰۰ است و همان
    # گلوگاهِ خاموشِ مسیرِ AI بود؛ ۰ یعنی بی‌سقف، چون governorِ واقعی `ai_max_concurrent_calls`
    # است و درخواستِ بیشتر از آن هرگز به سوکت نمی‌رسد.
    ai_http_pool_limit: int = 0
    # P42 · موردِ ۳۲: پاسخ‌هایِ بلندِ مودِ مشاوره‌ای (متنِ آموزشیِ چند پاراگراف) از سقفِ ۶۰ ثانیه‌یِ
    # قبلی رد می‌شدند و مشتری «هیچ پاسخی» نمی‌گرفت. ۹۰ ثانیه + این‌که تایم‌اوت دیگر *تکرار*
    # نمی‌شود (تکرارِ همان پرسش، هم زمانِ انتظار را دو‌به‌دو می‌کند هم یکِ فراخوانیِ پولیِ دیگر).
    ai_timeout_seconds: int = 90
    # P29 (MEASURED با scripts/scale_probe.py رویِ ۵۰۰ فروشگاه): در حالتِ polling همهٔ
    # `delete_webhook`ها در یکِ لحظه می‌رفتند (اوجِ هم‌زمانی = ۵۰۰) و در حالتِ webhook ثبت
    # ترتیبی بود (۲۰ ربات = ۵٫۰ ثانیه ⇒ ۵۰۰ ربات ≈ ۱۲۵ ثانیه). این عدد می‌گوید «چند فروشگاه
    # هم‌زمان ثبت/شروعِ پولینگ کنند». فقط سرعتِ راه‌اندازی را عوض می‌کند؛ هیچ رباتی حذف یا ادغام
    # نمی‌شود و هر فروشگاه همان یک تسکِ polling خودش را دارد.
    bot_register_concurrency: int = 24
    main_bot_token: str
    admin_telegram_ids: str = ""

    run_mode: RunMode = RunMode.POLLING
    webhook_base_url: str = ""
    webhook_listen_host: str = "0.0.0.0"
    webhook_listen_port: int = 8000
    main_bot_webhook_secret: str = ""
    # ربات بله‌پی برای پرداخت (اختیاری — اگه خالی بمونه، Bale Pay غیرفعال می‌مونه).
    # مشابهِ main_bot_token، چون یه Bot ثابته و موقعِ startup ساخته می‌شه، نه یه
    # چیزی که بدونِ ری‌استارت از پنلِ ادمین عوض بشه (برخلافِ bale_provider_token
    # که در AdminSettings ذخیره می‌شه، چون فقط یه پارامترِ per-request ـه).
    bale_bot_token: str = ""
    # B1: آدرسِ پایه‌یِ APIِ بله؛ مستنداتِ رسمی https://tapi.bale.ai (قبلاً .ir هاردکد بود). تاییدِ نهایی: تراکنشِ واقعی.
    bale_api_base: str = "https://tapi.bale.ai"
    bale_webhook_secret: str = ""
    # B6: «polling» (پیش‌فرض؛ getUpdates، بدونِ HTTPSِ عمومی) یا «webhook». هم‌زمان ممکن نیست.
    bale_updates_mode: str = "polling"

    # P49-الف: کانالِ اینستاگرام — فقط APIِ رسمیِ متا (Instagram Messaging API). هیچ‌وقت از
    # مسیرِ غیررسمی/خصوصی استفاده نمی‌شود، چون آن مسیر رمزِ کاربر را می‌خواهد و خطرِ بستنِ
    # اکانتِ مشتری/فروشگاه دارد (توضیحِ کامل در .env.example).
    # آدرسِ پایه و نسخهٔ گراف هاردکدِ امن هستند (https ثابت؛ از ورودیِ ادمین ساخته نمی‌شوند تا
    # SSRF مثلِ `ai_base_url` ممکن نشود). تنها ورودیِ بیرونی که داخلِ آدرس می‌نشیند app_id است.
    instagram_api_base: str = "https://graph.facebook.com"
    instagram_graph_version: str = "v21.0"
    # لینکِ «اتصالِ اکانت» که فروشگاه‌دار با آن واردِ صفحهٔ ورودِ متا می‌شود.
    instagram_login_base: str = "https://www.instagram.com/oauth/authorize"
    # آدرسِ عمومیِ HTTPSِ همین سرویس (مثلِ WEBHOOK_BASE_URL)؛ برایِ دو چیز لازم است:
    # ۱) `redirect_uri` در لینکِ اتصال ۲) آدرسی که در پنلِ متا به‌عنوانِ وب‌هوک وارد می‌کنید
    # (`<این مقدار>/webhook/instagram`). خالی ⇒ دکمهٔ «اتصال» پیامِ صادقانه می‌دهد و لینکی نمی‌سازد.
    instagram_public_base_url: str = ""

    # W5: سطحِ لاگِ برنامه (DEBUG/INFO/WARNING/ERROR). لاگِ «Update handled»ِ aiogram همیشه WARNING است تا لاگ‌ها شلوغ نشن.
    log_level: str = "INFO"
    # P20 · PHASE 20: «true» ⇒ لاگ‌ها JSONِ ساختاریافته (برایِ Collector/Loki/CloudWatch) با
    # correlation-id؛ «false» ⇒ همان متنِ خوانایِ فعلی. در هر دو حالتِ scrubber رد می‌شود.
    json_logs: bool = False
    # P20 · B3: سقفِ درخواستِ HTTP به‌ازایِ (IP, مسیر) در هر دقیقه رویِ endpointهایِ عمومی.
    # تلگرام/بله در اوجِ ترافیکِ یکِ رباتِ بزرگ می‌توانند چند ده آپدیت در ثانیه بفرستند، پس
    # پیش‌فرض محافظه‌کارانه ولی نه تنگ است. ۰ ⇒ محدودسازی خاموش (فقط برایِ تست).
    webhook_rate_limit_per_minute: int = 600
    # P20 · B3: اگر پشتِ یکِ reverse-proxyِ مطمئن (nginx/Caddy) هستی، X-Forwarded-For را باور کن
    # وگرنه IP هر درخواست «خودِ پراکسی» است و سقفِ مشترک همه را با هم می‌بندد.
    trust_proxy_headers: bool = False
    # P20: رازِ خواندنِ /metrics. خالی ⇒ endpoint اصلاً وجود ندارد (۴۰۴).
    metrics_token: str = ""
    # پ۱۰۹ · پنلِ نوشتنیِ وب: کلیدِ HMAC برایِ امضایِ کوکیِ نشست و نشانهٔ CSRF. خالی ⇒ مسیرهایِ
    # `/web/*` وجود ندارند (۴۰۴) — یعنی با تنظیماتِ امروزِ همین استقرار هیچ درِ نوشتنیِ تازه‌ای باز
    # نمی‌شود. این کلید *جدا* از METRICS_TOKEN است، چون آن کلید فقط «دیدن» می‌دهد و این «تغییر دادن».
    # آدرسِ لینک از WEBHOOK_BASE_URL ساخته می‌شود (کلیدِ تازه‌ای برایِ آن لازم نیست).
    panel_secret: str = ""
    # P21-B (O2): در حالتِ polling هم یک اپِ کوچکِ «فقط /health و /metrics» بالا بیاید.
    # مسیرهایِ webhook در این اپ نیستند، پس رازِ وب‌هوک هم مثلِ حالتِ webhook الزامی نمی‌شود.
    health_enabled: bool = True
    # P32: نگهدارندهٔ حالتِ مکالمه (FSM). `memory` = رفتارِ همیشگی (با ری‌استارت می‌پرد)؛
    # `postgres` = همان حالت رویِ دیتابیس، تا چک‌اوتِ نیمه‌کارهٔ مشتری با ری‌استارت/دیپلوی
    # از نیمه نشکند. Redis گزینهٔ معمول است ولی اینجا نصب‌نشدنی بود (§۲-۱۱ هم سرویسِ تازه
    # را برایِ مقیاس منع می‌کند).
    fsm_storage: str = "memory"
    # ============================================================================
    # P45 · ظرفیت: نقشِ پروسه و شارد. با `all` (پیش‌فرض) رفتارِ تک‌پروسه‌ایِ امروز مو‌به‌مو
    # می‌ماند؛ چیزی که در `.env` نوشته نشده عوض نمی‌شود.
    #   core   = رباتِ مرکزی + جاب‌ها + صفِ اعلان + pollingِ بله‌پی + وب‌هوک‌ها (یکِ پروسه)
    #   poller = فقط ربات‌هایِ فروشگاهیِ شاردِ خودش (چتِ مشتری‌ها؛ هرچه فروشگاه بیشتر، پروسهٔ بیشتر)
    #   web    = فقط دریافتِ webhook و پاسخ (برایِ وقتی که HTTPS داری؛ بدونِ هیچ socketِ باز)
    #   all    = همهٔ بالا در یکِ پروسه (دیپلویِ فعلی)
    # شارد با `shop_bot_id % SHARD_COUNT == SHARD_INDEX` تقسیم می‌شود، پس پیام‌هایِ یکِ فروشگاه
    # همیشه در یکِ پروسه می‌نشینند و debounceِ درِحافظهٔ همان پروسه همچنان درست است.
    app_role: str = "all"
    shard_index: int = 0
    shard_count: int = 1
    # P45: در حالتِ webhook، پروسهٔ دریافت فقط ربات‌هایی را می‌سازد که *واقعاً* ترافیک دارند
    # (LRU). با ۱٬۵۰۰ فروشگاه و ۳۰۰ فروشگاهِ پرمصرف، رمِ هر پروسه به ۳۰۰ اتصال می‌رسد نه ۱٬۵۰۰.
    webhook_bot_cache_size: int = 400
    # P44 · موردِ ۵۱: پوشهٔ مشترکی که سرویسِ جانبیِ `backup` فایل‌هایِ `kasbokar-YYYYMMDD-HHMMSS.dump`
    # را می‌نویسد و همین اپ آن‌ها را برایِ ادمین می‌فرستد و قدیمی‌ها را پاک می‌کند. در داکر رویِ یکِ
    # volume مشترک سوار می‌شود؛ نبودِ پوشه = «بکاپی نیست» (جاب بی‌صدا رد می‌شود، کاری نشکسته می‌شود).
    backup_dir: str = "/backups"

    auth_mode: AuthMode = AuthMode.TEST

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_use_tls: bool = True

    encryption_key: str

    @property
    def admin_ids(self) -> set[int]:
        return {int(x.strip()) for x in self.admin_telegram_ids.split(",") if x.strip()}


settings = Settings()
