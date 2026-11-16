# چنجلاگِ پ۱۰۳ — بازبینیِ یافتهٔ HIGH-4: «رمزنگاریِ سکرتِ وب‌هوک» (۲۰۲۶-۱۱-۱۷)

## چرا این فاز اصلاً وجود دارد
در `SECURITY_AUDIT_REPORT.md` (تاریخِ ۲۰۲۶-۱۱-۰۱) این مورد **OPEN** مانده بود و به‌عنوانِ تنها HIGHِ باز
در «چرا آمادهٔ تولید نیست» شمار می‌شد؛ در `REMAINING_ISSUES.md` هم P0-1 با طرحِ رفعِ دو مرحله‌ای.
سنجشِ امروز نشان داد آن متن **کهنه** است، نه بازمانده: کار در همان فازِ P20 انجام شده بود و فقط گزارش‌ها
به‌روز نشده بودند. پس این فاز کد ندارد؛ **اثباتِ دوباره با اندازه‌گیری** دارد و دو سند را اصلاح می‌کند.

## آنچه واقعاً وجود دارد (تأییدشده با grep/SQL)
• مدل: `webhook_secret_token: Mapped[str] = mapped_column(EncryptedToken(512), nullable=False)`
  (`app/database/models.py:665`) — `EncryptedToken` هنگامِ خواندن مقدارِ خامِ قدیمی را هم می‌پذیرد و
  هنگامِ نوشتن رمز می‌کند.
• مایگریشنِ پهن‌کردنِ ستون از `String(64)` به `String(512)`:
  `migrations/versions/b2e6f9c1d4a8_p20_security_secrets_and_audit_chain.py` (افزودنیِ نوع، بدونِ حذفِ داده).
• بازنویسیِ ردیف‌هایِ خام در بوت‌آپ: `shop_bot_service.reencrypt_secrets()` که با SQLِ خام خودش تشخیص
  می‌دهد کدام ردیف هنوز Fernet نیست و فقط آن‌ها را لمس می‌کند؛ از `app/main.py:103` صدا زده می‌شود.

## MEASURED (دیتابیسِ توسعه، ۲۰۲۶-۱۱-۱۷ — بدونِ چاپِ هیچ سکرتی)
`information_schema.columns.character_maximum_length = 512` و برایِ هر دو ردیفِ `shop_bots`:
`length(webhook_secret_token) = 140` با پیشوندِ `gAAAAA` ⇒ **نصِ روشن در حالِ خواب نیست**.

## تستِ موجود (همین را قفل کرده بود)
`test_p20_security_observability.py::test_webhook_secret_is_encrypted_and_legacy_rows_are_rewritten`:
ردیفِ تازه ⇒ `looks_encrypted(raw)` و `decrypt_token(raw) == مقدارِ خوانده‌شده` · ردیفی که با SQLِ خام
`plaintext-legacy-secret` شد ⇒ پس ازِ `reencrypt_secrets()` رمزی می‌شود ولی خواندنش همان مقدار را می‌دهد ·
اجرایِ دوم ⇒ ۰ نوشتن (ایدِمپوتنت).

## چیزی که همچنان NOT RUN است (و صادقانه نوشته شد)
ثبتِ واقعیِ webhook رویِ تلگرام/بله با این سکرت در سرورِ تولید — این محیط HTTPSِ عمومی ندارد. چیزی که
NOT RUN است فقط «رفتارِ end-to-endِ بسترِ webhook» است، نه رمزنگاریِ در حالِ سکون.

## اصلاحِ مستندات
`SECURITY_AUDIT_REPORT.md`: HIGH-4 ⇒ FIXED با شواهدِ بالا و جدولِ خلاصه ۴ FIXED / ۰ OPEN.
`REMAINING_ISSUES.md`: P0-1 و P0-2 ⇒ بسته‌شده (P0-2 هم با `JsonFormatter` + `settings.json_logs` +
`/metrics` + مسیرهایِ `logs_view` و زنجیرهٔ هشِ ممیزی اثبات شد). دو غلطِ املاییِ «بوت‌اپ» ⇒ «بوت‌آپ» هم درست شد.
