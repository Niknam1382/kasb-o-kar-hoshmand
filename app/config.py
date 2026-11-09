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
    ai_max_concurrent_calls: int = 40
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
    # P21-B (O2): در حالتِ polling هم یک اپِ کوچکِ «فقط /health و /metrics» بالا بیاید.
    # مسیرهایِ webhook در این اپ نیستند، پس رازِ وب‌هوک هم مثلِ حالتِ webhook الزامی نمی‌شود.
    health_enabled: bool = True
    # P32: نگهدارندهٔ حالتِ مکالمه (FSM). `memory` = رفتارِ همیشگی (با ری‌استارت می‌پرد)؛
    # `postgres` = همان حالت رویِ دیتابیس، تا چک‌اوتِ نیمه‌کارهٔ مشتری با ری‌استارت/دیپلوی
    # از نیمه نشکند. Redis گزینهٔ معمول است ولی اینجا نصب‌نشدنی بود (§۲-۱۱ هم سرویسِ تازه
    # را برایِ مقیاس منع می‌کند).
    fsm_storage: str = "memory"
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
