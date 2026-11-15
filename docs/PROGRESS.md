# PROGRESS — کسب‌وکار هوشمند
- آخرین به‌روزرسانی: ۲۰۲۶-۱۱-۰۱ (**P18 تحویل شد ✅** — اصلاحاتِ پس از تستِ واقعی: A1–A7، B1–B9، C1–C4، بخشِ د). · فاز: ۱ · وضعیتِ Docker: **۷۷ فایل / ۴۹۲ تست سبز**، مایگریشنِ head `c2e5a8b1d4f7` (۴۲ فایل، یک head)، شاخه‌یِ `p18-fixes`. · بیس‌لاینِ این فاز: `…_FINAL.zip` = ۶۵ فایل / ۴۱۲ تست (head `d9e3a6b8c2f5`) — هیچ تست/ستونی از قبل‌ها حذف نشد.
- آخرین zip: `kasb-o-kar-hoshmand_P18.zip` (ساخته‌شده با `git archive` از HEAD ⇒ بدونِ `.git`، `__pycache__`، `backup_*.sql` و `.env`) · عددِ تاییدشده در Docker: **۷۷ فایل / ۴۹۲ تست** · head: `c2e5a8b1d4f7` · ۱۲ فایلِ تستِ تازه‌یِ P18. · جزئیاتِ هر بخش: `docs/changelog-p18.md` و `docs/P18_TODO.md`.
- مرجع: MASTER_PROMPT_ADAME_KARp14.md (بدونِ تغییر)
- تشخیصِ فاز (بخشِ ۰-۱): در zipِ ورودی (نسخه‌یِ ۶-الف) `docs/PROGRESS.md` نبود ⇒ چتِ ۱ / فازِ ۱ / شروع از `P1-S0`.

## ۱) جدولِ مرحله‌ها   (⏳ نشده · 🟡 در حال انجام · ✅ تحویل · ⏩ منتقل‌به‌فازِ۲ با دلیل)
| مرحله | محتوا | وضعیت | zip | یادداشت |
|-------|-------|--------|-----|---------|
| P1-S0 | بازبینیِ استاتیک/خط‌به‌خطِ ۶-الف + `PROGRESS.md` + سه فهرستِ مرجع | ✅ | `kasb-o-kar-hoshmand_P1-S0.zip` | یک باگِ واقعی (`isdigit`) اصلاح شد؛ بقیه‌یِ ۶-الف با sandbox تایید شد (بخش ۷) |
| P1-S1 | هویت: A1، A2، A3، N1، H2، D2 (+ستون‌ها و UIِ تنظیماتِ D1) · مایگریشن `c1a5e0d7b3f2` | ✅ | `…_P1-S2.zip` (تجمیعی) | ویزارد، پروفایل، مود روی مالک، `identity_service`، پشتیبانی؛ تست: `test_identity_and_profile.py` |
| P1-S2 | مود + رباتِ مشتری v2 + مستر پرامپت‌ها: A4، C1، J1–J3، E2 (پیش‌فرضِ ۸ث)، D1-مستقیم · مایگریشن `e3c7a9d1f5b2` | ✅ | `kasb-o-kar-hoshmand_P1-S2.zip` | تست: `test_customer_menu_and_prompts.py` |
| P1-S3 | کاتالوگ: B2 (فیزیکی/دیجیتال، استخرِ کد، ارسال) · مایگریشن `b9e2f6a4c8d1` | 🟡 W1 تحویل شد (منتظرِ Docker) | `kasb-o-kar-hoshmand_W1.zip` | تست: `test_catalog_digital_physical.py` (۱۵ تست). ⏩ منتقل‌شده‌ها: بخشِ ۸ |
| P1-S4 | سبد → سفارش: C2، C3، C4، C8، C9، D5-ساده · مایگریشن `c2d7a4f1e8b3` | 🟡 W2 هسته تحویل شد (منتظرِ Docker) | `kasb-o-kar-hoshmand_W4.zip` | تست: `test_orders_w2.py` (۱۲ تست). **انجام‌شده:** C4 (order_state، گذارِ گروهی، خط‌زمان، «سفارش‌هایِ من»، دکمه‌هایِ گروهیِ فروشگاه‌دار)، C8 (فاکتور، روی‌تقاضا)، C9 (ردّ با دلیل/استرداد/اطلاعِ مشتری)، D5-ساده، C2-جزئی (فلگِ legacy + پیشنهادِ دکمه). **⏩ بخشِ ۸** |
| P1-S5a | پایه‌یِ پرداخت: ۵ب-B1–B7، B10–B13؛ HTTPِ همیشه‌روشن (F6)؛ `payment_event_log`؛ «🧪 آزمایشِ بله‌پی»؛ `BALE_UPDATES_MODE`؛ رمزنگاریِ provider_token؛ `.env.example` + FAQ · مایگریشن `f4d8b2c6a1e9` | ✅ جزئی (Docker ✅) | `…_P1-FINAL.zip` | انجام شد: B1، B2، B3 (بدونِ retryِ pending)، B4، B5 (مسیرِ دارایِ راز)، B12، B13. **انجام نشد:** B6 (polling)، B7 (رمزنگاریِ provider_token)، B10 (UNIQUE تراکنش)، B11 (تابعِ اتمیِ اعمال)، F6 (HTTPِ همیشه‌روشن)، retryِ pending |
| P1-S5b | کارت‌به‌کارت + مهلت‌ها: C5، C6 (+جابِ ۶۰ثانیه‌ایِ انقضا، پرداختِ دیرهنگام) · مایگریشن ۱ | ⏳ (چتِ بعد) | | |
| P1-S5c | بله‌پی برایِ سفارش: C7 (`resolve_bale_credentials`، پذیرشِ خودکار) | ⏳ (چتِ بعد) | | |
| P1-S5d | زرین‌پالِ فروشگاه: M (+جابِ تطبیق، صفحه‌یِ بازگشت) · مایگریشن ۰–۱ | ⏳ (چتِ بعد) | | شیرِ اطمینانِ دوم |
| P1-S6 | ابزارهایِ ادمین: K1–K4 (+K5 اگه ظرفیت) · مایگریشن ۱ | ⏳ (چتِ بعد) | | اولین شیرِ اطمینان |
| W5 (چتِ B) | **لایه‌یِ ۱:** C3 چک‌اوتِ مرحله‌ایِ کامل (نام/موبایل/دفترچه‌آدرس/ارسال+هزینه/توضیح/پیش‌فاکتور/ویرایش)، `wizard_nav`، C2 پیشنهاد+تاییدِ AI، اعلانِ خودکارِ تایید/ردِ دستی، «✉️ پیام به مشتری» روی تک‌سفارش، B6 (getUpdates)، B7 (رمزنگاریِ provider_token)، B10 (قفل/بازپخش) · **لایه‌یِ ۲:** تحلیلِ AIِ رسید، تاییدِ دیرهنگام، هشدارِ ۲ساعته، حدودِ مهلتِ ادمین، برگشتِ موجودی، K1–K4 · مایگریشن `b7c1e4a9d2f3` + `c8d2f5a7e1b4` | 🟡 تحویل شد (منتظرِ Docker) | `kasb-o-kar-hoshmand_FINAL.zip` | تست: `test_checkout_c3.py` (۱۱)، `test_w5_bale_hardening.py` (۷)، `test_w5_layer2.py` (۱۲)، `test_orders_manage.py` (۴) + به‌روزرسانیِ عمدیِ ۹ فایلِ قدیمی (بخش ۵). ⏩ها: بخش ۸ |
| P1-END | سندها + دستورِ Docker + چک‌لیستِ تستِ دستی + «منتظرِ نتیجه» | 🟡 | `…_P1-FINAL.zip` | README/PROJECT_COMPLETION/testing-guide/.env.example به‌روز؛ فازِ ۱ هنوز تموم نشده (S3، S4، S5b–d، S6) ⇒ این zip «نقطه‌یِ بررسی»ـه نه پایانِ فاز |
| P2-T0 | تریاژِ نتیجه‌یِ تست، تصمیمِ بله‌پی (Plan A/B، B8)، ریسکِ دامنه‌یِ زرین‌پال، منتقل‌شده‌ها | ⏳ | | |
| P2-T1 | ارتباط: D1-رله، D3، D4، D5-کامل | ⏳ | | |
| P2-T2 | محدودیت/ضدِ اسپم/حافظه: E1، E2 (باقی)، E3، E4 | ⏳ | | |
| P2-T3 | رشد/اعتماد/شفافیت: G1، G2، H1 (+K5/M/S6 اگه منتقل شده) | ⏳ | | |
| P2-T4 | ظرفیت و بازنگریِ جامع: I1 + جارویِ I2 رویِ مسیرهایِ مالی + `load_simulation` | ⏳ | | |
| P2-T5 | پاکسازی + سخت‌سازی: L1، L2 | ⏳ | | |
| P2-T6 | آماده‌یِ سرور: L3 | ⏳ | | |
| P2-T7 | راهنمایِ مبتدی + پذیرشِ نهایی: L4 | ⏳ | | |
| P2-END | `…_P2-FINAL.zip` + دستورِ Dockerِ نهایی | ⏳ | | |

## ۲) نیازمندی‌ها   (شناسه ← وضعیت ← مرحله)
- گروهِ A: A1 ✅ P1-S1 ✅ کد+تست نوشته شد (Docker ✅) (+N1) · A2 ✅ P1-S1 ✅ (Docker ✅) · A3 ✅ P1-S1 ✅ (Docker ✅) · A4 ✅ P1-S2 ✅ (Docker ✅)
- گروهِ B (کاتالوگ): B1 ✅ «⏭ رد کردن» (۶-الف؛ در S0 با تست و کد تطبیق داده شد، Docker ✅) · B2 🟡 P1-S3 (W1؛ منتظرِ Docker؛ باقی‌مانده ⏩ بخشِ ۸)
- گروهِ C: C1 ✅ P1-S2 ✅ (Docker ✅) · C2 ⏳ P1-S4 · C3 ⏳ P1-S4 · C4 ⏳ P1-S4 · C5 ⏳ P1-S5b · C6 ⏳ P1-S5b · C7 ⏳ P1-S5a+S5c · C8 ⏳ P1-S4 · C9 ⏳ P1-S4
- گروهِ D: D1 ✅ مستقیم ✅ (S1 تنظیمات + S2 دکمه‌یِ مشتری؛ Docker ✅) + ⏳ P2-T1 (رله) · D2 ✅ P1-S1 ✅ (Docker ✅) · D3 ⏳ P2-T1 · D4 ⏳ P2-T1 · D5 ⏳ P1-S4 (ساده) + P2-T1 (کامل)
- گروهِ E: E1 ⏳ P2-T2 · E2 ✅ تنظیمِ فروشگاه‌دار + پیش‌فرضِ ۸ث + typing ✅ (P1-S2؛ Docker ✅)، باقی ⏳ P2-T2 · E3 ⏳ P2-T2 · E4 ⏳ P2-T2
- گروهِ G/H: G1 ⏳ P2-T3 · G2 ⏳ P2-T3 · H1 ⏳ P2-T3 · H2 ✅ P1-S1 ✅ (Docker ✅)
- گروهِ I: I1 🟡 ابزار+محافظِ ظرفیت (۶-الف؛ semaphore/استخر/`load_simulation` بازبینی‌شد) + ⏳ P2-T4 · I2 ⏳ پایانِ هر مرحله (نتیجه در بخش ۷؛ S0 ✔️)
- گروهِ J: J1 ✅ ✅ · J2 ✅ ✅ · J3 ✅ ✅ (P1-S2؛ Docker ✅)
- گروهِ K: K1 ⏳ P1-S6 · K2 ⏳ P1-S6 · K3 ⏳ P1-S6 · K4 ⏳ P1-S6 · K5 ⏳ P1-S6 اگه ظرفیت، وگرنه P2-T3
- گروهِ L: L1 ⏳ P2-T5 · L2 ⏳ P2-T5 · L3 ⏳ P2-T6 · L4 ⏳ P2-T7
- گروهِ M: M ⏳ P1-S5d
- بله‌پی (بخشِ ۵-ب؛ با پیشوندِ «۵ب-» تا با B1/B2ِ کاتالوگ قاطی نشه): ۵ب-B1…B5 ✅ ✅ (S5a؛ Docker ✅) · ۵ب-B6 ⏳ · ۵ب-B7 ⏳ (چتِ بعد) · ۵ب-B12، B13 ✅ ✅ (S5a؛ Docker ✅) · ۵ب-B10، B11 ⏳ (چتِ بعد) · ۵ب-B8 ⏳ `resolve_bale_credentials` در P1-S5c، تصمیم در P2-T0 · ۵ب-B9 ⏳ P1-S5c (متنِ راهنما) · ۵ب-B14 ⏩ فقط اگه Plan A در تستِ واقعی رد شد
- ردیف‌هایِ T01…T66 (بخشِ ۹): ۱۶ ✅ از قبل · ۵ تا 🟡 (نوشته‌شده در ۶-الف و در S0 بازبینی‌شده: **T01** فهرستِ ادمین، **T02** ظرفیت، **T13** چند پیام = یک جواب، **T16** «⏭ رد کردن»، **T40** تجمیعِ پیام) · بقیه ⏳ و هم‌خطِ شناسه‌هایِ بالا. هر ۵ تا 🟡 تا Dockerِ پایانِ فازِ ۱ همین‌طور می‌مونن.

## ۳) تصمیم‌ها و فرض‌هایِ گرفته‌شده (به‌ترتیب)
- [P1-S0] فاز از نبودنِ `docs/PROGRESS.md` تشخیص داده شد (۰-۱) ⇒ فازِ ۱، شروع از S0.
- [P1-S0] ادعاهایِ ساختاریِ بخشِ ۵ با کدِ واقعیِ zip تطبیق داده شد و **همه درست بودن**: B1 (`API_BASE` با `.ir`)، B2 (`currency: "IRR"`)، B3 (فقط `successful/success/paid/ok` موفق؛ `main.py` سه مسیر)، B7 (`provider_token` بدونِ رمزنگاری)، F6 (`uvicorn.run(... port=8000)` هاردکد؛ polling بدونِ سرورِ HTTP)، F7 (`CHECK_INTERVAL_SECONDS = 30*60`)، F16 (`MemoryStorage`)، F17 (پورتِ ۵۴۳۲ بیرون، `postgres/postgres`، Dockerفایلِ بدونِ `USER`)، F18، F20 (`shop_bot/router.py` فقط `customer.router`).
- [P1-S0] ارقام: ۵۳ فایلِ تست / ۳۱۳ تابعِ `test_*` / ۳۱۳ چاپِ «✅ … PASSED» (استاتیک شمرده شد) و هر ۵۳ فایل در `TEST_FILES`ِ `run_all_tests.py` ثبت‌ان ⇒ عددِ انتظارِ ۵۳/۳۱۳ درسته. مایگریشن: ریشه `e59de9fae404`، یک head `b7d4e2a9c1f5`، بدونِ `down_revision`ِ ناشناخته.
- [P1-S0] اصلاحِ باگ در **همه‌یِ** نقاطی که ورودیِ تایپیِ کاربر به `int()` می‌رسه (نه فقط کدِ ۶-الف)، چون یه تغییرِ یک‌توکنیه (`isdigit()`→`isdecimal()`) و رفتارِ ارقامِ فارسی/عربی/ASCII دقیقاً حفظ می‌شه (در sandbox تایید شد). `cart_edit_service.py:172` (`isascii() and isdigit()`) امن بود و دست نخورد.
- [P1-S0] `.env` همون‌طور که در zipِ ورودی بود (دست‌نخورده) توی zip موند تا با «جایگزینیِ محتوایِ پوشه» چیزی گم نشه؛ در `P2-T5` (L2) از zipِ نهایی حذف می‌شه.
- [P1-S1] شماره‌ها: `ShopOwner.phone_number` همون `09…` می‌مونه (تست‌ها/داده‌یِ قبلی)؛ ستون‌هایِ **تازه** (`Customer.phone_number`، پشتیبانیِ پلتفرم/فروشگاه) `+98…` ذخیره می‌شن؛ نمایش همیشه `+98…` (`validators.format_phone_display`). `normalize_iran_phone` حالا ارقامِ فارسی/عربی هم می‌پذیره.
- [P1-S1] ویزارد: مود ← نامِ کوچک (نامِ دوکلمه‌ای: ۳ دکمه، خودکار جدا نمی‌شه) ← نامِ خانوادگی ← موبایل ← ایمیل ← مرور؛ OTP بلافاصله بعدِ همون فیلد طبقِ `AUTH_MODE`؛ ذخیره فقط با «✅ تایید و شروع»؛ مخاطبِ دیگران رد می‌شه (`contact.user_id`)؛ موبایل/ایمیلِ تکراری رد؛ `/start` وسطِ ویزارد از همون قدم ادامه می‌ده؛ برچسب‌هایِ ناوبری (⬅️ برگشت/❌ انصراف) عمداً **در `_KNOWN_MENU_BUTTONS` نیستن**.
- [P1-S1] مود: منبعِ حقیقت `ShopOwner.business_mode`؛ `set_business_mode` هر دو ستون رو می‌نویسه؛ callbackِ نهایی همون `set_tenant_mode:<mode>` (تستِ قدیمی دست‌نخورده)؛ تغییر با سفارشِ باز (`OPEN_ORDER_STATUS_VALUES` در `order_service`) مسدود؛ پرسشِ مودِ بعد از ثبتِ توکن حذف شد؛ «🔀 نوعِ کسب‌وکار»/«✏️ ویرایش اطلاعات» از منو رفتن ولی دکمه‌یِ کهنه همون پروفایل رو باز می‌کنه.
- [P1-S1] H2: `identity_service.display_user` تنها سازنده‌یِ هویتِ متنی؛ استثنایِ فنی: `audit_log_entry_line` و خطِ «🔧 شناسه‌یِ فنی» در `admin_role_detail_text`؛ نگهبانِ static در `test_static_no_numeric_ids_in_ui_texts`؛ `IdentityRefreshMiddleware` (outer، ربات اصلی) یوزرنیم رو فقط وقتی عوض شده تازه می‌کنه؛ `Customer.last_name` از همه‌یِ مسیرهایِ `get_or_create_customer` پر می‌شه.
- [P1-S1] D1/D2: پشتیبانیِ پلتفرم فقط برایِ فروشگاه‌دار (پروفایل، «📞 پشتیبانی»، متنِ «ثبت‌نام بسته»)؛ تست‌ِ static تضمین می‌کنه `platform_support` در `app/bots/shop_bot` نیست؛ گزینه‌یِ `relay` اصلاً نمایش داده نمی‌شه؛ پاک‌شدنِ آخرین راهِ تماس، پشتیبانی رو خودکار خاموش می‌کنه.
- [P1-S2] J: `prompt_defaults.resolve_global_prompt` (مود ← قدیمی ← پیش‌فرضِ حرفه‌ای) در کدِ فراخوان‌ها (چت و پیش‌نمایش)، نه داخلِ `build_system_prompt`؛ `bot_tools` پارامترِ اختیاریِ `build_system_prompt` (بدونِ آن خروجی بایت‌به‌بایت مثلِ قبل ⇒ تست‌هایِ بایت‌به‌بایت دست‌نخورده).
- [P1-S2] E2: `DEFAULT_MESSAGE_BATCH_SECONDS=8`؛ `_sleep_with_typing` (پنجره‌یِ <۲ث بدونِ typing)؛ `harness.reset_database()` هر تست رو با `DEBOUNCE_SECONDS=3.0` شروع می‌کنه تا تست‌هایِ قدیمیِ debounce (فهرستِ ۶-۳) دست‌نخورده بمونن.
- [P1-S5a] بله: `BALE_API_BASE` (پیش‌فرضِ `https://tapi.bale.ai`؛ **با تراکنشِ واقعی تایید نشده**)؛ `setWebhook` فقط `url` می‌فرسته و اگه `BALE_WEBHOOK_SECRET` هست، رازِ وب‌هوک **در مسیر** ثبت می‌شه (`/webhook/bale/{secret}`)؛ مسیرِ قدیمیِ `/webhook/bale` با هدر هنوز کار می‌کنه؛ اعتباردهی فقط با `classify_transaction_status == success` («succeed» هم) و مبلغِ هم‌خوان (`verify_transaction_amount`؛ مبلغِ برنگشته = رد نمی‌شه)؛ هر تماس/رویداد در `payment_event_logs` (session مستقل، توکن/شماره‌کارت ماسک)؛ دکمه‌هایِ «🧪 آزمایشِ بله‌پی»/«🔎 آخرین رویدادهایِ پرداخت» داخلِ «🔑 تنظیمات کلیدها» (سوپرادمین).
- [W1/P1-S3] **ورودِ جدا برایِ دیجیتال:** به‌جایِ «قدمِ اولِ نوعِ محصول» در جریانِ قدیمیِ افزودن، دکمه‌یِ جداگانه‌یِ «💾 افزودنِ محصولِ دیجیتال» (`product_add_digital`، فقط مودِ فروشگاهی) گذاشته شد؛ جریانِ «➕ افزودن محصول جدید» (فیزیکی) و تست‌هایِ قدیمیش بایت‌به‌بایت دست‌نخورده‌ان. فیلدهایِ مخصوصِ فیزیکی (وزن/زمانِ تحویل/مرجوعی/دستورِ AI) فقط از «✏️ ویرایش» هستن، نه در فرمِ افزودن.
- [W1] **تحویلِ دیجیتال فعلاً روی «تاییدِ فروشگاه‌دار»** (`confirm_order:` و `confirm_cart_group:`؛ وضعیت CONFIRMED به بعد) چون وضعیتِ `paid` تا W2/W3 نیست. نقطه‌یِ وصلِ بعدی: هرجا `paid` ثبت می‌شه `digital_service.deliver_order(...)` صدا زده بشه (ایدمپوتنته). `DELIVERABLE_STATUSES` در W2 به `order_state.py` وصل می‌شه.
- [W1] **ناوردایِ موجودیِ code_pool:** `Product.stock_quantity == تعدادِ کدهایِ available`؛ `confirm_order` همون‌طور که بود از stock کم می‌کنه و تحویل کدها رو در همون تراکنش مصرف می‌کنه؛ `sync_pool_stock` فقط بعد از افزودنِ کد صدا زده می‌شه (نه بعد از هر تحویل، تا پنجره‌یِ هم‌زمانی نسازه). تحویلِ نصفه ممنوع (کدِ کم ⇒ `insufficient`، هیچ کدی عوض نمی‌شه، سفارشِ منتظر با افزودنِ کد به‌ترتیبِ قدیمی‌ترین‌اول تحویل می‌شه).
- [W1] کدها با `encrypt_token` (Fernet) ذخیره می‌شن؛ یکتایی با `code_hash` (sha256) و `UNIQUE(product_id, code_hash)`. «دریافتِ دوباره» (`dl_again:<order_id>`) شمارنده `digital_download_count` رو زیرِ قفلِ سطری بالا می‌بره؛ ارسالِ اول هم جزوِ سقفِ `digital_max_downloads` حساب می‌شه. اگه ارسالِ اول شکست بخوره (مشتری رباتِ فروشگاه رو بلاک کرده)، تحویل ثبت‌شده می‌مونه (کد دوباره اختصاص داده نمی‌شه) و به فروشگاه‌دار اعلانِ «ارسال ناموفق» نشون داده می‌شه.
- [W1] file_idِ رباتِ اصلی روی رباتِ فروشگاه کار نمی‌کنه ⇒ اولین ارسال: دانلود از رباتِ اصلی + آپلودِ مجدد؛ `digital_file_shop_file_id` برایِ دفعاتِ بعد کش می‌شه (با تعویضِ فایل ریست می‌شه).
- [W1] اکسل: ستونِ پنجمِ اختیاریِ «نوع»؛ «دیجیتال» = روشِ تحویلِ `code_pool` با استخرِ خالی (موجودی ۰ تا فروشگاه‌دار کد اضافه کنه)؛ فایل‌هایِ ۴ستونه‌یِ قدیمی بدونِ تغییر (کلیدِ `kind` فقط برایِ ردیفِ دیجیتال در دیکشنری هست).
- [W1] سبدِ فقط‌دیجیتال: سوال‌هایِ چک‌اوتِ *پیش‌فرض* = فقط «شماره تماس» (سوال‌هایِ سفارشیِ فروشگاه‌دار دست‌نخورده). سبدِ ترکیبی = پیش‌فرضِ قبلی (شماره + آدرس).

- [W2] **`order_state.py` منبعِ حقیقتِ مجموعه‌هایِ وضعیت** (خالص، بدونِ import از models). ۵ وضعیتِ تازه (`awaiting_payment`، `receipt_submitted`، `paid`، `refund_pending`، `refunded`) فقط رشته‌ان (ستونِ `String(32)`)؛ `OPEN_ORDER_STATUS_VALUES`، `accounting_service` (SUCCESS/RELEASED/STATUS_ORDER)، `digital_service.DELIVERABLE_STATUSES` از آن مشتق می‌شن؛ `campaign_service.RELEASED_ORDER_STATUSES` + `refunded`؛ `crm_service.SUCCESS_STATUSES` + `paid`. SHIPPED عمداً مثلِ قبل «باز» حساب نمی‌شه.
- [W2] **`order_transition_service.transition_group`**: قفلِ سطری (`FOR UPDATE` + `populate_existing`) رویِ کلِ گروه، اعتبارسنجی با `can_transition`، اثرِ رزرو (آزادسازی در rejected/expired/cancelled/refunded؛ مصرفِ موجودی در paid/confirmed؛ مثلِ `confirm_order`)، **یک** `order_events` به‌ازایِ گروه، ایدمپوتنت (همه‌یِ ردیف‌ها در مقصد ⇒ `changed=False`، بدونِ رویداد). سرویس پیام نمی‌فرسته و commit نمی‌کنه؛ هندلر بعد از commit به مشتری اطلاع می‌ده. استردادِ `refunded` موجودی رو **برنمی‌گردونه** (فروشگاه‌دار دستی تصمیم می‌گیره).
- [W2] مسیرِ قدیمیِ `confirm_order:`/`confirm_cart_group:`/`reject_order:`/`reject_cart_group:`/`advance_order:` **بدونِ تغییرِ رفتار** ماند (فقط `order_events` اضافه می‌نویسن و بعد از تاییدِ گروه، کیبوردِ `og_*` نشون می‌دن) تا هیچ تستِ قدیمیِ شمارشِ پیام/سند نشکنه؛ دکمه‌یِ «ردِ کلِ سفارش» در اعلانِ گروه حالا `og_rej:` (ردّ با دلیل) است. کهنه‌ها هنوز کار می‌کنن.
- [W2] callbackهایِ فروشگاه‌دار پیشوندِ `og_` (کلید = `o<id>` تک‌محصولی یا hexِ گروه، ≤۶۴ بایت)؛ مشتری `myord_*`. کلیدِ جعلی/حدسی ⇒ هشدارِ مودبانه؛ مالکیت با `shop_bot_id` (فروشگاه‌دار) و `customer_id` (مشتری) چک می‌شه.
- [W2] **C2:** `ShopBot.legacy_ai_order_detection` (پیش‌فرض False) در ابتدایِ `_detect_and_notify_order` چک می‌شه ⇒ هیچ فراخوانیِ AI/هزینه‌یِ `ORDER_DETECTION`. **`seed_usable_shop` (تست‌ها) فلگ رو True می‌کنه** تا همه‌یِ تست‌هایِ قدیمیِ مسیرِ چت بدونِ ویرایش کار کنن (استثنایِ قاعده‌یِ ۷). `cart_suggest_service.suggest_cart_products` (خالص؛ نامِ محصولِ فعال+موجود در متنِ جواب؛ حداکثر ۳؛ شناسه هرگز از متنِ AI) + `keyboards.cart_suggest_keyboard` زیرِ جوابِ چت (فقط مودِ فروشگاهی).
- [W2] **فاکتور (C8):** `invoice_service` — اسنپ‌شاتِ ثابت در `invoices.data_json`، یکی به‌ازایِ (فروشگاه، گروه) با `UNIQUE`، شماره `INV-{shop}-{YYYYMM}-{seq}` با `invoice_counters` + `FOR UPDATE` + savepoint؛ پیام + فایلِ HTMLِ RTL (همه‌چیز escape، بدونِ منبعِ خارجی). فعلاً **فقط روی‌تقاضا** از «📦 سفارش‌هایِ من ← 📄 فاکتور» (ارسالِ خودکار در `paid` با W3/W4 که `paid` می‌سازن).
- [W2] «📦 سفارش‌هایِ من» دکمه‌یِ reply تازه (`BTN_MY_ORDERS`)؛ در چهار جا: keyboards + `CUSTOMER_MENU_BUTTONS` + هندلر + تست. فقط مودِ فروشگاهی.

- [W3] **تنظیماتِ پرداخت (C5):** جدولِ `shop_payment_settings` (۱:۱ با فروشگاه؛ شماره‌کارت و مرچنتِ زرین‌پال با `encrypt_token`) + منوی «⚙️ روش‌هایِ پرداختِ مشتری» که **دکمه‌یِ اینلاین روی پیامِ «💳 پرداختِ آنلاینِ سفارش‌ها»** است (دکمه‌یِ reply تازه نساختم تا تستِ منویِ پنل نشکنه). شماره‌کارت: ۱۶ رقم + Luhn؛ مهلت‌ها clamp (پرداخت ۵–۱۴۴۰ دقیقه، نگهداریِ بررسیِ رسید ۶۰–۴۳۲۰). اگه هیچ روشِ آنلاین/کارتیِ کامل‌تنظیم فعال نباشه، `checkout_methods=[]` ⇒ **جریانِ قدیمیِ pending بدونِ تغییر**؛ وگرنه سفارش مستقیم `awaiting_payment` می‌شه و مشتری روش انتخاب می‌کنه (`awaiting_payment → pending` برایِ «پرداختِ دستی» به جدولِ گذار اضافه شد).
- [W3] **کارت‌به‌کارت (C6):** `order_payments` (`initiated→submitted→approved|rejected|expired`) + `order_payment_service` (شروعِ پرداخت ایدمپوتنت، رسیدِ عکس/فایلِ تصویری/شماره‌پیگیری ≥۶ رقم، SHA-256 و شماره‌پیگیریِ تکراری فقط **پرچم** (هرگز ردِ خودکار)، تایید ⇒ `paid` + اعلان + فاکتور + تحویلِ دیجیتال، ردّ با دلیل ⇒ برگشت به `awaiting_payment` تا سقفِ `max_receipt_attempts` وگرنه `rejected`). هیچ پرداختی بدونِ تاییدِ فروشگاه‌دار `paid` نمی‌شه. مهلتِ رزرو: انتخابِ روش ⇒ `card_deadline`، ارسالِ رسید ⇒ `receipt_review_hold`.
- [W3] **انقضا (F7):** جابِ جدایِ ۶۰ثانیه‌ایِ `scheduler.run_payment_expiry_loop` (+ شروع در هر دو حالتِ polling/webhook) و **expire-on-read** (`expire_if_overdue` در هر callbackِ پرداخت). نگهبانِ «پرداخت کردم/واریز کردم» برایِ مشتریِ دارایِ سفارشِ `awaiting_payment` با regexِ خالص (بدونِ AI، هزینه ۰) راهنمایِ «📎 ارسالِ رسید» می‌ده.
- [W4] **بله‌پیِ سفارش (C7):** جریانِ تازه با `OrderPayment(method=bale)`؛ وب‌هوکِ `cartgroup-` اگه پرداختِ جریانِ تازه برایِ گروه وجود داشته باشه به `_handle_bale_new_flow` می‌ره (وگرنه مسیرِ قدیمیِ `bale_paid_at` دست‌نخورده). **قبل از اعتبار: استعلامِ سمتِ سرور + تطبیقِ مبلغ** (`_bale_outcome_ok`)؛ «در انتظار» با backoff ۵/۲۰/۶۰/۱۸۰ ثانیه دوباره پرسیده می‌شه (B3)؛ شناسه‌یِ تراکنش `UNIQUE` (B10) ⇒ وب‌هوکِ تکراری بی‌اثر. `pre_checkout` برایِ جریانِ تازه هم پرداختِ فعال + وضعیتِ مجاز رو چک می‌کنه.
- [W4] **زرین‌پالِ هر فروشگاه (M):** مرچنتِ خودِ فروشگاه، `request_payment` با `callback=/payment/zarinpal/callback`، هر ضربه ⇒ اتوریتیِ تازه و پرداختِ قبلی `expired`؛ callback اول `OrderPayment` با `provider_ref=Authority` رو می‌جوئه (وگرنه مسیرِ پلتفرم)، `verify_payment` با مرچنتِ فروشگاه، `transaction_ref=zp-<ref_id>`.
- [W4] **پرداختِ دیرهنگام:** `apply_verified_online_payment`: گروهِ `expired` دوباره رزرو می‌شه؛ اگه موجودی کافی نبود **پول گرفته شده ⇒ `paid` + `needs_review`** (نه processing خودکار) و پیامِ «نیازِ بررسیِ دستی» به فروشگاه‌دار؛ سفارشِ لغو/ردشده/تکراری که پول گرفت هم `needs_review`. `auto_accept_online` فقط وقتی `needs_review=False` ⇒ `paid → processing`.
- **[W5] تصمیم‌هایِ چک‌اوتِ C3:** روترِ تازه `handlers/checkout.py` قبل از `customer.router` (F20)؛ کلِ بلوکِ چک‌اوتِ قدیمیِ `customer.py` به آن منتقل شد (فقط `_split_checkout_questions` برایِ یک تستِ قدیمی ماند). سوال‌هایِ پیش‌فرضِ «شماره/آدرس» حذف شد (مرحله‌هایِ ثابت جایگزین)؛ سوال‌هایِ فروشگاه‌دار فقط *اضافه* هستن. هزینه‌یِ ارسال از جمعِ **کالایِ فیزیکیِ قبل از تخفیف** سنجیده می‌شه؛ روی همه‌یِ ردیف‌هایِ گروه ذخیره می‌شه و `group_total_toman` (max) جمعِ پرداختی می‌دهد؛ `estimated_value_toman` همچنان *بعد از تخفیف و بدونِ ارسال* است (قانونِ طلایی). `previewed_final_total` حالا شاملِ ارسال است و هزینه‌یِ ارسال بینِ پیش‌نمایش و ثبت عوض بشه ثبت نمی‌شه. آدرسِ تازه در پایانِ مرحله‌یِ کدپستی ذخیره می‌شه (نه موقعِ ثبتِ نهایی)؛ سقفِ ۵ آدرس. اشتراکِ مخاطب فقط با «ارسالِ مخاطب» (Contact، کاربر=فرستنده) نه دکمه‌یِ reply-keyboard (برای دست‌نخوردن منویِ اصلی) ⏩ نسخه‌یِ بعد.
- **[W5] C2:** `CartAiProposal` (قبلاً ساخته شده بود) حالا استفاده می‌شه؛ `claim` اتمی با UPDATE…RETURNING؛ پیشنهادِ جدید پیشنهادهایِ بازِ قبلیِ همان سبد را منسوخ می‌کند؛ هزینه‌یِ AI همان لحظه‌یِ پیشنهاد کسر می‌شه (اعمال/ردّ رایگان).
- **[W5] B7:** `EncryptedToken` (TypeDecorator) روی دو ستون — شفاف برایِ کل کد؛ مقدارِ خامِ قدیمی خوانده می‌شه و با اولین نوشتن رمز می‌شه؛ مایگریشن داده‌یِ قدیمی رو رمز می‌کنه. **B6:** حلقه‌یِ getUpdates با offset درون‌حافظه‌ای (ایدمپوتنسیِ هندلرها جلویِ تکرار پس از ری‌استارت را می‌گیرد)، پیش‌فرضِ `BALE_UPDATES_MODE=polling` و webhook پس از شروع حذف می‌شه. **B10:** `get_by_cart_checkout_group(lock=True)`/`lock_order` + `bale_transaction_used_elsewhere`؛ (UNIQUE روی ستونِ `bale_transaction_id` عمداً نیست چون ردیف‌هایِ یک سبد یک تراکنش را به‌اشتراک می‌گذارند.)
- **[W5] 2.1/2.2:** تحلیلِ رسید فقط برایِ *عکس* و فقط وقتی `receipt_ai_enabled` و کیفِ پول ≥ هزینه؛ commit قبلِ AI؛ شکستِ AI یا JSONِ نامعتبر ⇒ بدونِ هزینه. حدودِ مهلتِ ادمین فقط موقعِ *ثبتِ* تنظیمِ فروشگاه‌دار اعمال می‌شه؛ ثابت‌هایِ زمانِ استفاده به بازه‌یِ سختِ وسیع (۱–۱۰۰۸۰ دقیقه / ۱۰–۴۳۲۰۰ دقیقه) رفتن.
- **[W5] K1–K4:** عملیاتِ گروهی با `AdminCreditBatch` + `AdminCreditBatchItem(UNIQUE batch_id+owner)` و savepoint به‌ازایِ هر نفر؛ توقفِ زمان `TimeFreeze` (شروع فقط ثبت؛ ازسرگیری = یک تراکنشِ جابه‌جاییِ تاریخ‌ها، جابه‌جایی حداکثر تا `ends_at`)؛ جاب‌هایِ `wallet_service`/`grace_period_service` مشمولینِ فریز را رد می‌کنن؛ `scheduler.run_periodic_pass` برایِ تست‌پذیری از حلقه جدا شد.

## ۴) تله‌هایِ تازه‌یِ کشف‌شده
1. **محیطِ کار:** `bash_tool` با `/bin/sh` (dash) اجرا می‌شه ⇒ `${PIPESTATUS[0]}`/`[[ ]]` کار نمی‌کنن (کلِ اسکریپت می‌پره)؛ `cut -c`/`head -c` وسطِ حروفِ فارسی می‌بُره و خروجی UTF-8نامعتبر می‌شه ⇒ پردازشِ متنِ فارسی فقط با پایتون. `compileall` پوشه‌یِ `__pycache__` می‌سازه ⇒ **قبل از zip پاکشون کن** (zipِ ورودی هیچ‌کدوم نداشت). aiogram/sqlalchemy/pydantic/aiohttp این‌جا نیستن (و شبکه بسته‌ست).
2. **`isdigit()` ≠ «int() می‌پذیره».** «²، ①، ¹⁰» `isdigit()==True` ولی `int()` ValueError می‌ده؛ همیشه `isdecimal()` (یا `isascii() and isdigit()`). برایِ هر اعتبارسنجیِ تازه‌یِ ورودیِ کاربر (S1: شماره/کدپستی/یوزرنیم؛ S4: آدرس؛ S5: مبلغ) همین رو رعایت کن و یه assertِ «²/①» بذار.
3. **سقفِ `MAX_BUFFER_WAIT_SECONDS` نرمه:** `delay = min(window, max(0.3, max_wait - elapsed))` یعنی اگه پیام‌ها تندتر از ۰٫۳ث پشتِ‌هم بیان (انسان نمی‌تونه؛ rate-limiter هم جلوشو می‌گیره) پردازش شروع نمی‌شه. برایِ E2 (پیش‌فرضِ ۸ث ⇒ `max_wait = max(10, 24) = 24ث`) قابلِ‌قبوله؛ دست نزن.
4. **دابل‌تپِ `product_skip:stock` / ثبتِ محصول:** `state.clear()` بعد از I/Oِ دیتابیسه ⇒ دو تپِ تقریباً هم‌زمان (aiogram در polling هر آپدیت رو تسکِ جدا اجرا می‌کنه و `MemoryStorage` قفل نداره) می‌تونه دو محصول بسازه (همین ریسک برایِ متنِ «رد شدن» هم بود). کم‌خطر؛ در **جارویِ I2ِ P2-T4** با الگویِ `state.clear()`-اول (مثلِ `cart_checkout_confirm`) درست بشه. هرجا دکمه‌یِ تازه‌ایِ پول‌ساز/ساخت‌ساز اضافه می‌کنی همین الگو رو از همون اولِ خودش بذار.
5. **`harness.reset_database()` همه‌یِ جدول‌ها رو TRUNCATE می‌کنه** (همه‌یِ تست‌ها + `load_simulation.py`). اگه کاربرِ مبتدی روی سرورِ پروداکشن `run_all_tests.py` یا `load_simulation.py` اجرا کنه، دیتا پاک می‌شه ⇒ در **P2-T5/T6** نگهبان بذار (مثلاً `ALLOW_DESTRUCTIVE_TESTS=1` یا ردِ اجرا وقتی `DATABASE_URL` محلی/تستی نیست) و در راهنما هشدار بده.
6. **برچسبِ دکمه‌هایِ `keyboards.py` literal هستن** (مثلاً خطِ ۷۰ برایِ «⚙️ تنظیماتِ ربات فروشگاه»)، نه ثابتِ `texts`؛ ریسکِ ناهم‌خوانیِ ZWNJ/variation-selector. در S0 با ast بررسی شد: ۳۶ دکمه (۲۴ فروشگاه‌دار + ۱۲ ادمین) همه codepoint-برابرِ `_KNOWN_MENU_BUTTONS`ان. هر دکمه‌یِ تازه: keyboards + escape-set + handler + تست.
7. **تست‌هایِ ۶-الف انتظارِ فعلی رو قفل کردن که S1 عوضش می‌کنه:** `test_phase6a…` برایِ مالکِ بی‌نام «`987654 — بدونِ ربات`» (آیدیِ عددی) انتظار داره؛ H2 (هرگز آیدیِ عددی) در S1 باید `texts.admin_owner_list_item_label` و همین assert رو هم‌زمان عوض کنه (استثنایِ قاعده‌یِ ۷).
8. **روشِ ممیزیِ «commit قبل از AI»** (قابلِ تکرار در هر مرحله): با `ast` همه‌یِ فراخوانی‌هایِ `.get_reply/.analyze_image/.transcribe_audio` رو پیدا کن و ببین قبلشون `.commit()` هست. در S0: ۱۴ نقطه، همه ✔️ (مورد CRM: commit در فراخوان، `crm.py:346`). مرحله‌هایِ بعد که AIِ تازه می‌آرن (C6 تحلیلِ رسید، پیشنهادِ سبد) باید همین رو رعایت کنن.
9. **sandbox (بندِ ۱۱):** `extract(path, names)` با `ast` تعریف‌هایِ سطحِ ماژول رو از فایلِ واقعی بیرون می‌کشه و با stub (`session_scope`، `_generate_and_send_reply`، `shop_bot_service`) `exec` می‌کنه؛ همین‌طور قفل/پنجره‌یِ `customer.py` با asyncioِ واقعی اجرا شد (فایلِ sandbox جزوِ پروژه نیست).
10. **هرگز فایلِ بزرگِ ثابت‌دار (`texts.py`) رو با «تا تابعِ بعدی» برش نزن** — بینِ توابع ثابت‌ها (constants) هست؛ در S1 دو بار ناخواسته پاک شد و فقط با مقایسه‌یِ AST با نسخه‌یِ اصلی پیدا شد. ویرایشِ تابع/ثابت فقط با `ast` (خط‌هایِ دقیقِ node) یا جایگزینیِ یکتای رشته.
11. `texts.py` حالا `identity_service` رو import می‌کنه (بدونِ دور: `identity_service` فقط `validators` رو می‌خونه)؛ `keyboards.py` هم `texts` رو (بدونِ دور).
12. در `_prompt` ویزارد، `reg_phone_text`/`reg_*` از `StateFilter(*_ALL_REG_STATES)` استفاده می‌کنن؛ هر stateِ تازه‌یِ ویزارد باید به `_STATE_STEP` و `_ALL_REG_STATES` اضافه بشه.
13. برچسب‌هایِ `shop_owner_panel_keyboard`: «📞 پشتیبانی» در `_KNOWN_MENU_BUTTONS` هست؛ هر دکمه‌یِ تازه همون چهارجا (keyboards، escape-set، handler، تست).
14. **اصلاحِ یک خطایِ بازنگریِ S0:** ممیزیِ «commit قبل از AI» در S0 فقط وجودِ `.commit()` رو می‌دید و نه اینکه `session` در آن تابع تعریف شده باشه. `order_detection_service.detect_order` و `cart_edit_service.classify` (دو تابعِ بدونِ session، از ۶-الف) `await session.commit()` داشتن ⇒ **NameError** در هر تحلیلِ سفارش/ویرایشِ سبد. در این چت اصلاح شد: commit از سرویس‌ها برداشته و در فراخوان‌ها (`customer.py`) گذاشته شد. هر commitِ جدید باید روی sessionِ پارامتر/متغیرِ همون تابع باشه.
15. ابزارهایِ استاتیکِ تازه (جزوِ پروژه نیستن؛ بسازشون): `lint_names` (نامِ تعریف‌نشده/use-before-assign با ast؛ همین باگ رو در baseline پیدا کرد؛ هشدارهایِ comprehension false-positive‌ان) و sandboxِ debounce (کدِ واقعیِ `customer.py` با `ast`+stub اجرا می‌شه؛ در S2 یک `UnboundLocalError` (`customer_tg_id` در `_wait_then_process`) پیش از تحویل گرفت).
16. `bale_service._call` حالا هر تماس رو در `payment_event_logs` می‌نویسه؛ تست‌ها با جایگزین‌کردنِ `bale_service._call` از شبکه جدا می‌شن (رویدادِ DB در اون حالت نوشته نمی‌شه).
17. **ویرایشِ چندخطیِ کد با regexِ حریص ممنوع:** در S1 با یک regex به همه‌یِ `get_or_create_customer(...)` پارامترِ `last_name=` اضافه کردم؛ regex تا اولین `    )` ادامه داد و در `_check_access` به فراخوانِ `rate_limiter.check_and_record(...)` چسبید ⇒ `TypeError` در **هر پیامِ مشتری** (۱۰ فایلِ تست). اصلاح شد. برایِ ویرایش فقط جایگزینیِ رشته‌یِ یکتا (با assert شمارش) یا ast.
18. دیتابیسِ داکرتِ قدیمی ممکنه مایگریشنی بشناسه که در zip نیست (`alembic upgrade head` ← «Can't locate revision»)؛ راهِ حل: `docker compose down -v` (دیتابیسِ تست یک‌بارمصرفه).
19. دیتایِ بذرِ `seed_usable_shop` ایمیل رو از روی آیدی می‌سازه (`owner{tg_id}@example.com`)؛ تست‌هایِ «بدونِ آیدیِ عددی» باید خطِ ایمیل رو کنار بگذارن.
20. **گیت‌هایِ استاتیکِ اجباریِ پیش از هر zip** (در `scripts/`، بدونِ وابستگی؛ هر دو باید «OK» بدن): `python3 scripts/lint_names.py` (NameError/UnboundLocalErrorِ scope-aware؛ هر دو باگِ ۶-الف رو روی baseline پیدا می‌کنه) و `python3 scripts/audit_ai_commit.py` (هر فراخوانیِ AI ← commitِ معتبرِ قبلش). کنارِ `compileall` (با `migrations`)، `check_refs.py`، `check_attrs.py`.
21. مشخصاتِ کاملِ پروژه در `docs/spec/MASTER_PROMPT_P14.md` (بدونِ تغییر) هست؛ نقشه‌یِ موج‌ها و محدوده‌یِ خط‌هایِ هر موج در مستر پرامپتِ اجرایِ خودکار (p15) آمده.
22. **[W1] `cut`/`head -c` روی متنِ فارسی در خروجیِ `grep` هم خطرناکه** (خروجیِ UTF-8نامعتبر کلِ نتیجه رو می‌خوره)؛ برایِ نمایشِ خطوطِ فارسی از پایتون استفاده کن.
23. **[W1] `parse_price_toman`/`parse_nonneg_int` فقط «,»، «،» (U+060C) و فاصله رو به‌عنوانِ جداکننده‌یِ هزارگان حذف می‌کنن؛ «٬» (U+066C) رو نه.** در تست‌ها از «،» یا «,» استفاده کن (تستِ اولیه‌یِ W1 همین‌جا اشتباه داشت و قبل از تحویل با sandbox گرفته شد).
24. **[W1] هیچ جدولِ تازه با TRUNCATE مشکل نداره (`harness.reset_database` از `pg_tables`)؛ ولی هر مایگریشنِ تازه ⇒ `alembic upgrade head` قبلِ تست.**
- **[W5] تله:** (۱) دکمه‌هایِ `ck_*` در stateِ نامربوط ⇒ `checkout_stale_button` (آخرین هندلرِ روتر) نه سکوت؛ ولی `cart_checkout_*` عمداً بدونِ fallback (دابل‌تپِ ثبت نباید alert بده). (۲) چک‌اوتِ دومِ همان مشتری فهرستِ آدرس‌ها را نشان می‌دهد ⇒ تست‌ها `has_saved_addresses=True` می‌دهند. (۳) `process_result_value` با مقدارِ خام خطا نمی‌دهد ولی `where(col == "plain")` رویِ ستونِ رمزشده **کار نمی‌کند** (IV تصادفی) — هیچ‌جا چنین فیلتری نیست؛ نسازید. (۴) در `cb_confirm_*` اعلانِ دستی برایِ سفارشِ *دیجیتال* عمداً نیست (خودِ تحویل اعلان است). (۵) `time_freeze_service.resume` پس از `ends_at` فقط تا سقفِ خودش جبران می‌کند.

## ۵) تست‌هایِ تغییرداده‌شده/حذف‌شده (استثناهایِ قاعده‌یِ ۷؛ هر کدوم با دلیل)
- `tests_manual/test_phase6a_batching_and_settings.py` (۶-الف؛ هیچ‌وقت اجرا نشده بود): داخلِ تستِ خالصِ موجودِ `test_pure_batch_seconds_parsing_and_window_fallback` assertهایِ رگرسیونِ ارقامِ «²/①/¹⁰/-²» برایِ `parse_batch_seconds`، `owner_common.parse_suffix_int`، `validators.parse_price_toman/parse_signed_toman_amount` اضافه شد (+ دو import: `owner_common`، `validators`). **تعدادِ تست‌ها عوض نشد (۳۱۳).** دلیل: باگِ `isdigit` (بخش ۷).
- `test_start_registration.py`: جریانِ ویزارد (قدمِ ۰ مود + مرورِ نهایی/تایید) — استثنایِ «متن‌هایِ ثبت‌نام»؛ تعدادِ تست‌ها عوض نشد.
- `test_phase6a_batching_and_settings.py`: برچسبِ مالکِ بی‌نام «کاربرِ بی‌نام — بدونِ ربات» (H2)؛ لیستِ callbackهایِ صفحه‌یِ تنظیمات + `sp_open`؛ پیش‌فرضِ ۸ثانیه (`DEFAULT_MESSAGE_BATCH_SECONDS == 8`، «8 ثانیه (پیش‌فرضِ سیستم)»).
- `harness.py`: `FakeSession` برایِ `SendChatAction` مقدارِ `True` می‌ده؛ `reset_database()` پیش‌فرضِ debounce رو ۳ثانیه می‌گذاره (دلیل در بخش ۳).
- فایل‌هایِ تازه: `test_identity_and_profile.py` (۸ تست)، `test_customer_menu_and_prompts.py` (۵ تست) — در `TEST_FILES` ثبت شدن.
- فایلِ تازه: `test_bale_payment_foundation.py` (۵ تست). مجموعِ فعلی: **۵۶ فایل / ۳۳۱ تست**.
- فایلِ تازه (W1): `test_catalog_digital_physical.py` (۱۵ تست؛ ثبت در `TEST_FILES`). مجموعِ فعلی: **۵۷ فایل / ۳۴۶ تست**.
- **[W2]** فایلِ تازه: `test_orders_w2.py` (۱۲ تست) ⇒ **۵۸ فایل / ۳۵۸ تست**. - **[W3/W4]** فایلِ تازه: `test_payments_w3w4.py` (۱۲ تست: خالص، تنظیمات، کارت‌به‌کارتِ تایید/ردّ/سقف/تکراری، دستی، انقضا، نگهبانِ «پرداخت کردم»، امنیتِ بین‌فروشگاهی، بله‌پی [نادرست/نامشخص/در انتظار/موفق/تکراری/دیرهنگام/فروشِ بیش‌ازموجودی]، زرین‌پالِ فروشگاه) ⇒ **۵۹ فایل / ۳۷۰ تست**.
  **استثنایِ قاعده‌یِ ۷ (تغییرِ عمدیِ منو):** `test_customer_menu_and_prompts.py` — لیستِ برچسب‌هایِ منویِ فروشگاهی (۶ assert + مجموعه‌یِ `CUSTOMER_MENU_BUTTONS`) حالا شاملِ `BTN_MY_ORDERS`؛ تعدادِ تست‌ها عوض نشد. `tests_manual/shop_setup.py::seed_usable_shop`: `legacy_ai_order_detection=True` (دلیلِ بالا، بخشِ ۳). هیچ تستِ قدیمی تغییر نکرد (فقط `TEMPLATE_HEADERS`ِ اکسل یک ستونِ اختیاری گرفت؛ تستِ اکسل از همون ثابت استفاده می‌کنه).
- **[W5] استثناهایِ قاعده‌یِ ۷ (تغییرِ عمدی؛ شمارِ تست‌ها عوض نشد):** `test_shopping_cart.py` (۳ جریان: `_quick_checkout`، جریانِ کامل با شمارشِ پیام‌هایِ مرحله‌ایِ تازه، سوال‌هایِ فروشگاه‌دار بعد از مرحله‌هایِ ثابت)؛ `test_campaign_checkout.py` (`reach_preview` + `_callbacks` دکمه‌هایِ `ck_edit:*` را کنار می‌گذارد)؛ `test_orders_w2.py` (`_Env.checkout`)؛ `test_cart_ai_editing.py` (۷ تست: AI حالا پیشنهاد می‌دهد و با `cart_ai_apply` اعمال می‌شود؛ تستِ هم‌زمانی بازنویسی شد: پیشنهادِ دوم اولی را منسوخ می‌کند)؛ `test_catalog_digital_physical.py` (تاییدِ دستیِ فیزیکی اکنون دقیقاً یک پیامِ اعلان می‌دهد)؛ `test_admin_rbac.py` (دکمه‌یِ «⏱ اعتبار و زمان» در کیبوردِ ادمینِ عملیاتی)؛ `harness.py` (پارامترِ `contact_user_id`)؛ `checkout_helpers.py` (تازه، مشترک).
- **[W5] فایل‌هایِ تازه:** `test_checkout_c3.py` (۱۱)، `test_w5_bale_hardening.py` (۷)، `test_w5_layer2.py` (۱۲) ⇒ **۶۵ فایل / ۴۱۲ تست**.

## ۵-پ۱۸) [P18] تست‌هایِ عمداً تغییرداده‌شده (استثنایِ قاعده‌یِ «تستِ قدیمی را دست نزن»)
هر مورد زیر به‌خاطرِ **تغییرِ عمدیِ رفتارِ محصول** عوض شد، نه به‌خاطرِ شکستِ تصادفی:
- `test_checkout_c3.py` — **B8:** با یک روشِ ارسالِ فعال هم مرحله‌یِ انتخابِ ارسال نشان داده می‌شود ⇒ جریانِ مشترکِ چک‌اوت یک مرحله بلندتر شد.
- `test_bale_payment_foundation.py` — **A1:** منبعِ واحدِ اعتبارِ بله (`bale_credentials_service`)؛ انتظارها از «تنها env» به «پنلِ ادمین + env fallback» عوض شد.
- `test_identity_and_profile.py` — **B7** (پشتیبانی با ثبتِ راهِ تماس خودکار روشن می‌شود) و **C1** (برچسبِ منویِ مشاوره «🗂 خدمات و بسته‌ها»).
- `test_w5_receipt_text_and_product_photos.py` — **B2:** تستِ تازه‌یِ «دکمه‌یِ سبدِ کارتِ عکس»، شمارِ تست‌ها ۴→۵.
- `test_admin_pricing.py` — **A6:** بازنویسیِ کامل (UIِ طرح‌هایِ اشتراک حذف؛ داده/سرویس می‌ماند؛ کدهایِ تخفیفِ همان منو سالم).
- `test_phase6a_batching_and_settings.py:292` — **B5 + A5 + A2:** فهرستِ کالبک‌هایِ صفحه‌یِ تنظیمات با `rp_open`، `br_open`، `sp_prefs_open` بلندتر شد.
- `test_crm.py:308` و تستِ «همه‌یِ دکمه‌هایِ پنل در مجموعه‌یِ escape» — **B4 + C2/C3:** دو دکمه‌یِ تازه رویِ کارتِ مشتری و منویِ تازه‌یِ مشاوره.
- `test_w5_layer2.py` — **A5:** `test_admin_deadline_bounds` → `test_owner_deadline_bounds_come_from_code` (بازه‌ها فقط از کد).
- `test_payments_w3w4.py:97` — **A5:** مهلتِ پرداختِ per-shop.
- `test_consultation_mode.py` — **C1/C2/C3:** برچسب‌هایِ منویِ مشاوره.
- `test_admin_settings.py` — **A5 + A4:** دو تستی که `knowledge_items_limit` و `wallet_cost_photo_analysis_toman` را از پنلِ ادمین تنظیم می‌کردند حالا `conversation_history_limit` و `wallet_cost_receipt_analysis_toman` را می‌سنجند + assertِ عمدیِ «دکمه‌یِ کهنه هیچ چیزی عوض نمی‌کند».
- `test_conversation_retention.py` — **A5:** تستِ «ادمین retention را تنظیم می‌کند» → «retention دیگر تنظیمِ ادمین نیست» (ستون و پیش‌فرضِ سراسری می‌مانند).
- `test_p18_per_shop_settings.py` — **A4:** فهرستِ `REMOVED_FROM_ADMIN` از خودِ محصول خوانده می‌شود (تست و کد جدا نمی‌افتند).
- `test_card_to_card_improvements.py` + `harness.py` — **A7:** بعد از دستورالعملِ کارت یک پیامِ «رسید بفرست / ⬅️ برگشت» می‌آید ⇒ assert به پیامِ حاویِ «شماره کارت» تغییر کرد؛ `FakeSession` حالا `parse_mode` را هم ضبط می‌کند.
- `test_photo_handling.py` — **A4:** بازنویسیِ کامل (۳ تست): عکسِ مشتری **بدونِ هیچ فراخوانیِ AI و بدونِ کسرِ هزینه** فوروارد می‌شود؛ مشتریِ بلاک‌شده عکسی نمی‌فرستد؛ `estimate_photo_cost` وجود ندارد.
- `test_p18_sms.py` / `test_p18_bot_branding.py` — اصلاحِ خودِ تست (فلویِ تنظیمات بعد از هر ذخیره state را پاک می‌کند ⇒ برایِ «خالی» باید دوباره از منو وارد شد) و برچسبِ ماسکِ واقعی (`●●●●`).
**فایل‌هایِ تازه‌یِ P18 (۱۲):** `test_p18_bale_credentials.py`، `test_p18_security.py`، `test_p18_topup_receipt.py`، `test_p18_weekly_report.py`، `test_p18_block_and_conversation.py`، `test_p18_per_shop_settings.py`، `test_p18_checkout_steps.py`، `test_p18_consultation_panel.py`، `test_p18_sms.py`، `test_p18_bot_branding.py`، `test_p18_ai_model_pool.py`، `test_p18_pdf_invoice.py`.

## ۶) فهرست‌هایِ مرجع (از P1-S0)
**۶-۱) مصرف‌هایِ `OrderStatus`**  (ستونِ enum `String(32)` ⇒ مقدارِ تازه مایگریشنِ ساختاری نمی‌خواد؛ ولی *همه‌یِ* موارد زیر هم‌زمان به‌روز شن — مجموعه‌یِ مرکزیِ `order_state.py`)
- به‌نامِ enum (۶ فایل): `database/models.py:80` (تعریف؛ پیش‌فرضِ ستون `PENDING`) · `services/order_service.py` (۱۶ خط؛ همه‌یِ گذارها: `create_order`، `create_order_awaiting_confirmation`، `customer_confirm_order`، `customer_cancel_order`، `expire_stale_customer_confirmations`، `confirm_order`، `reject_order`، `advance_status` [CONFIRMED→PROCESSING→SHIPPED→COMPLETED]، `expire_stale_reservations`) · `services/campaign_service.py:43` (`RELEASED_ORDER_STATUSES` = REJECTED/EXPIRED/CANCELLED؛ مصرف :243/:257 با `_RELEASED_STATUS_VALUES`) · `services/crm_service.py:44/:46` (`SUCCESS_STATUSES` = CONFIRMED/PROCESSING/SHIPPED/COMPLETED؛ مصرف :221/:224/:288) · `services/accounting_service.py` (:328 `PENDING`) · `services/stats_service.py:108` (`PENDING`).
- ⚠️ **نسخه‌یِ رشته‌ایِ جدا (به enum وصل نیست؛ جاماندنی):** `accounting_service.py:32–33` (`SUCCESS_STATUS_VALUES`، `RELEASED_STATUS_VALUES`) و :35–45 (`STATUS_ORDER` با literal؛ ترتیبِ نمایش در گزارش)، مصرف :187/:210/:276.
- برچسب/دکمه‌ها: `main_bot/texts.py` ~:543–556 (دیکشنریِ برچسبِ وضعیت + برچسبِ دکمه‌یِ «وضعیتِ بعدی»)، مصرف :1689 (CRM) و `panel.py:892/:901` (`order_next_status_button_label(order.status)`)؛ `excel_export_service.py` ← `texts.accounting_status_label`؛ انقضا از راهِ `order_service.expire_*` (بدونِ literal در `order_expiry_service.py`).
- 🚫 **همنام ولی نامربوط (دستشون نزن):** `status`ِ JSONِ طبقه‌بندِ AI (`order_detection_service.py` :35–211؛ `customer.py:918/:921/:1080/:1128`؛ `cart_edit_service.py:234–243`)، `KnowledgeGapStatus` (`owner_assistant_service.py:182`، `knowledge_service.py`)، وضعیتِ کمپین (`keyboards.py:484–499`)، وضعیتِ پرداخت (`texts.py:429`)، وضعیتِ عضویتِ کانال (`panel.py:307`، `admin.py:269`).

**۶-۲) نقاطِ مود-حساس / مود-ناآگاه**
- مود-حساس (الان کار می‌کنن): `services/ai_context.py` (:3، :14، :75، :89–97؛ پیش‌فرضِ دستورِ هر مود) · `order_detection_service.py` (:51–176؛ طبقه‌بندِ مشاوره) · `cart_edit_service.py` (:178، :180، :283، :291) · `shop_bot/handlers/customer.py` (:21، :907–908، :1102–1103) · `main_bot/handlers/panel.py` (:27، :87، :130–154 تغییرِ مود، :203–204 پیش‌نمایش) · `handlers/start.py` (:61–62، :258–259) · `handlers/assistant.py:53–54` · `keyboards.py:54–55، :76–80` (`shop_owner_panel_keyboard(tenant_mode)` فقط برچسبِ «📦 محصولات ↔ 🗂 خدمات و بسته‌ها» رو عوض می‌کنه) · `texts.py:118–119، :129–130` · `models.py:112، :437` (`TenantMode`، `ShopBot.tenant_mode`).
- **مود-ناآگاه (F1/F3؛ در S2 باید درست شن):** `shop_bot/keyboards.py:15` `customer_main_keyboard()` بدونِ آرگومانِ مود (فراخوانی در `customer.py:103`) · «🛍 محصولات» (`customer.py:192`، `cart_open_products` :193) و «🛒 سبدِ خرید» (:209، `cart_open_view` :210) · ۱۴ هندلرِ callback/FSMِ سبد و چک‌اوت بدونِ چکِ مود (`cart_browse/add/view/inc/dec/remove/ai_clear/ai_keep`، `cart_checkout_start/answering/cancel/discount/confirm`؛ :228–538) · منویِ فروشگاه‌دار `keyboards.py:59–70`: «💳 پرداختِ آنلاینِ سفارش‌ها»، «📝 سوال‌هایِ چک‌اوتِ سبد»، «🎯 کمپین‌ها»، «🔀 نوعِ کسب‌وکار» (و سفارش‌محورها: «📊 آمار»، «📤 خروجی اکسل»، «🧮 حسابداری») در مشاوره هم دیده می‌شن.
- مود در ثبت‌نام (A3): `ShopOwner` ستونِ مود نداره؛ `ShopBot.tenant_mode` فقط بعد از ثبتِ توکن ساخته می‌شه (`shop_bot_service.upsert_shop_bot`، پیش‌فرضِ SALES).

**۶-۳) نقاطِ نشتِ آیدیِ عددی** (`telegram_id` در متن/دکمه‌یِ کاربرمحور؛ H2 + تستِ static در پذیرشِ نهایی)
- `main_bot/texts.py` (۱۴ مورد، به‌ترتیبِ تابع): `admin_new_payment_notification` :396 (نامِ فروشگاه‌دار؛ fallbackِ `str(owner.telegram_id)`) · `order_detected_notification` :482/:486 و `cart_order_notification` :508/:512 (نامِ مشتری fallback + «آیدی تلگرام: …» در اعلانِ سفارش/مشاوره به فروشگاه‌دار) · `owner_profile_text` :789/:795 (پروفایلِ من: «آیدی تلگرام») · `admin_owner_list_item_label` :1029 (فهرستِ ادمین؛ از ۶-الف) · `admin_shop_owner_detail` :1062–1063 · `admin_role_added_confirmation` :1228 · `admin_role_detail_text` :1234/:1236 («آیدی»، «اضافه‌شده توسطِ») · `audit_log_entry_line` :1262 («کاربر: …»).
- `main_bot/keyboards.py:461` (دکمه‌یِ «👤 {role.telegram_id}») · `main_bot/handlers/admin.py:71` (`_owner_display_name` fallback). (`admin.py:113–122، :1308، :1341` لاگ/جزئیاتِ ممیزیِ داخلی‌ان؛ شناسه‌یِ عددی در ممیزی لازمه ولی در متنِ UI نه.)
- `shop_bot/texts.py` در این جستجو نشتی نداشت. فهرستِ کامل: `grep -n "telegram_id" app/bots/*/texts.py` (+ `from_user.id` در f-string).
- **تست‌هایِ بایت‌به‌بایتِ `build_system_prompt`** (باید دست‌نخورده بمونن؛ استثنایِ مجازِ قاعده‌یِ ۷ فقط با دلیلِ صریح): `test_consultation_mode.py` (:39، :47، :56) · `test_knowledge_gaps.py` (:151–155؛ `baseline == same`) · `test_owner_assistant.py` (:143، :283)؛ کامنتِ `ai_context.py:107` («بدونِ مورد/با کلیدِ خاموش، خروجی بایت‌به‌بایت»)؛ نقاطِ فراخوانی: `customer.py` ≈۸۱۰ و `panel.py` (پیش‌نمایش).
- **تست‌هایِ debounce / وابسته به پیش‌فرضِ ۳ثانیه** (با E2 → پیش‌فرضِ ۸ باید در P1-S2 یکی‌یکی چک و به‌روز بشن): `test_message_debounce.py` (:75، :107؛ `sleep(4.5)`)، `test_moderation_and_audit_log.py` (:57، :85، :106، :130)، `test_cart_ai_editing.py` (:655–661)، `test_order_customer_confirmation.py:84`، `test_order_product_id_matching.py:85`، `test_voice_handling.py:65`، `test_phase6a_batching_and_settings.py` (با `DEBOUNCE_SECONDS=0.3` و پیش‌فرضِ ۳ در تستِ خالص)، `load_simulation.py:94`. کدِ `app`: `customer.py:56–57، :86، :710، :721`، `shop_bot_service.py:60`، `shop_settings.py:21`، `models.py:434`.

## ۷) بازنگریِ بی‌رحمانه (خلاصه‌یِ هر مرحله، ۳–۵ خط)
- **[P1-S0]** بررسی شد ✔️ (+sandbox/ast): (۲/۶) قفل و پنجره‌یِ `customer.py` با کدِ واقعی و asyncioِ واقعی — پیام‌هایِ وسطِ پردازش = دقیقاً یه دسته‌یِ پیگیری (حتی ۱۰ پیام)، هیچ‌وقت دو پردازشِ هم‌زمان برایِ یه مشتری، کلیدهایِ مستقل هم‌زمان، آزادشدنِ قفل بعد از خطا، پاک‌شدنِ بافر/تسک/قفلِ WeakValue؛ (۵/۸) `commit` قبل از هر ۱۴ فراخوانیِ AI و semaphore/تایم‌اوتِ AI (صفِ انتظار از تایم‌اوتِ ۶۰ث جداست)؛ (۱۰) ۳۶ دکمه codepoint-برابرِ escape-set؛ (۱۲) ورودیِ جعلی/بد (`bs_batch:99/abc/خالی`، متنِ نامعتبر).
- **ایراد پیدا و اصلاح شد (۱۲):** `isdigit()` ارقامِ «²/①» رو می‌پذیره ولی `int()` می‌ترکه ⇒ هر ورودیِ تایپیِ کاربر (مدتِ تجمیع، قیمت، مبلغِ اصلاحِ کیف‌پول، موجودیِ اکسل، آیدیِ کانال) بدونِ پاسخ exception می‌داد. ۹ نقطه در ۸ فایل → `isdecimal()`؛ رفتارِ قبلی حفظ شد؛ regression در تستِ ۶-الف.
- ثبت‌شده برایِ بعد (بخش ۴): دابل‌تپِ ثبتِ محصول (۴)، نگهبانِ تست‌هایِ مخرب (۵)، انتظارِ «۹۸۷۶۵۴ — بدونِ ربات» (۷). **بررسی‌نشدنی بدونِ Docker:** SQL/استخرِ واقعی، dispatchِ aiogram و ۹ تستِ `test_phase6a…` (فقط ذهنی‌اجرا + sandboxِ منطقِ خالص).
- **[P1-S1]** ✔️ `commit`/دابل‌تپ: `reg_confirm` اول state رو پاک می‌کنه؛ callbackِ جعلی/کهنه (`reg_mode:bogus`، `pf_edit:bogus`، `set_tenant_mode:bogus`، `sp_edit:bogus`) پیامِ مودبانه؛ ورودیِ بد (`²`، لینک/@/رقم در نام، یوزرنیمِ نامعتبر)؛ ممیزی بدونِ مقدارِ کاملِ موبایل/ایمیل. ثبت‌شده: دابل‌تپِ ثبتِ محصول (بخش ۴-۴) همچنان باز. **بررسی‌نشدنی بدونِ Docker:** SQL/dispatchِ واقعیِ ویزارد/پروفایل و ۱۳ تستِ تازه (فقط ذهنی‌اجرا + sandboxِ منطقِ خالص).
- **[P1-S2]** ✔️ ۳۶+۱ دکمه‌یِ پنلِ فروشگاه‌دار codepoint-برابرِ escape-set؛ مشاوره‌ای بدونِ هیچ دکمه‌/ابزارِ سبد؛ دکمه‌یِ کهنه پیامِ مودبانه + کیبوردِ مودِ جاری؛ FSMِ چک‌اوت با دکمه‌یِ منو پاک می‌شه.
- **[P1-S5a]** ✔️ مبلغِ ناهمخوان/pending/failed اعتبار نمی‌ده؛ payloadِ >۱۲۸ بایت صراحتاً رد؛ تست‌ها شبکه‌یِ واقعی لازم ندارن. **باز:** تراکنشِ pending بعداً موفق شه، سیستم دوباره نمی‌پرسه (فقط لاگ) ⇒ باید retry/تطبیقِ دوره‌ای. `provider_token` هنوز رمزنگاری نیست (B7).
- **[اصلاحِ S0]** خطایِ NameErrorِ دو سرویسِ ۶-الف از بازنگریِ S0 جا مونده بود و حالا اصلاح شده (تله‌یِ ۱۴). «ذهنی‌اجرا» کافی نیست؛ اولین کارِ چتِ بعد: اجرایِ Docker و گزارشِ خطاها.
- **[W1/P1-S3] بازنگریِ بی‌رحمانه (۱۳ بند):** ۱) دابل‌تپ: `state.clear()` قبل از ساختِ محصول/روشِ ارسال؛ تحویل با قفلِ سطریِ سفارش ⇒ `ready`+`already` (تست) ✔️ · ۲) callbackِ جعلی/کهنه (`dg_mode:bogus`، `dg_skip:*` بدونِ state، `ship_*:bogus`، `dl_again:abc`، شناسه‌یِ فروشگاه/مشتریِ دیگه) ⇒ پیامِ مودبانه ✔️ · ۳) ری‌استارت وسطِ FSM ⇒ دکمه‌یِ کهنه (همان ۲) ✔️ · ۴) مرزِ عدد (`²/①`، منفی، صفر، بزرگ، ارقامِ فارسی) در وزن/سقف/هزینه ✔️ · ۵) پول/تحویل: ایدمپوتنت، اتمی (SKIP LOCKED + همان تراکنش)، هیچ تحویلِ نصفه؛ ثبتِ ممیزی/`order_events` ندارد ⇒ ⏩ W2 (جدولش آنجا ساخته می‌شه) 🟡 · ۶) AI: هیچ فراخوانیِ AIِ تازه نیومد؛ محتوایِ تحویلِ نوعِ «متن»/کدها هرگز در پرامپت نیست (تست) ✔️ · ۷) نشتِ بینِ فروشگاه‌ها: همه‌یِ دسترسی‌ها با `get_owned*`/`shop_bot_id`؛ `prepare_redelivery` با `customer_id` ✔️ · ۸) آیدیِ عددی در UI: ندارد ✔️ · ۹) مودِ اشتباه: دکمه‌هایِ دیجیتال/ارسال فقط در SALES (تست) ✔️ · ۱۰) برچسبِ منو: هیچ دکمه‌یِ منویِ reply تازه نیومد (فقط inline) ✔️ · ۱۱) تست‌هایِ قدیمی: `grep` رویِ `products_list_keyboard`/`edit_product_field_keyboard`/`TEMPLATE_HEADERS`/`confirm_order` ⇒ هیچ‌کدوم محتوایِ قدیمی رو assert نمی‌کنن؛ پارامترهایِ تازه همه اختیاری ✔️ · ۱۲) N+1: حلقه‌یِ `deliver_pending_for_product` فقط روی سفارش‌هایِ منتظرِ یک محصول و فقط بعد از افزودنِ کد (مسیرِ غیرداغ) ✔️ · ۱۳) لاگ: کدها/لینک‌ها هیچ‌جا لاگ نمی‌شن (`logger` فقط شناسه) ✔️.
  **بررسی‌نشدنی بدونِ Docker:** SQL واقعیِ `FOR UPDATE SKIP LOCKED`، dispatchِ aiogram، دانلود/آپلودِ فایلِ واقعی؛ ۱۵ تستِ تازه فقط ذهنی‌اجرا + sandboxِ منطقِ خالص (parse_codes، validate_link، parse_nonneg_int، build_delivery_text) شدن.
- **[W2] بازنگری (خلاصه؛ فقط ذهنی/استاتیک + sandboxِ خالص):** ۱) دابل‌تپ: گذار ایدمپوتنت (`changed=False` ⇒ بدونِ اعلانِ دوم)، `state.clear()` قبل از I/O در کدِ رهگیری/دلیل/پیام ✔️ · ۲) callbackِ جعلی/کهنه (`og_*` با کلیدِ bogus، `myord_*` با کلیدِ نامعتبر/مشتریِ دیگه) ⇒ هشدارِ مودبانه ✔️ · ۴) مرز: ارقامِ «²» در کلید رد (`parse_key`) ✔️ · ۵) پول: تغییرِ وضعیت با قفل + `order_events`؛ استرداد دستی و بدونِ بازگشتِ موجودی (تصمیمِ ثبت‌شده) ✔️ · ۶) AI: هیچ فراخوانیِ تازه؛ فلگِ خاموش ⇒ هزینه ۰ ✔️ · ۷) نشتِ بینِ فروشگاه‌ها/مشتری‌ها: `get_owned_by_id`/`customer_id` ✔️ · ۸) آیدیِ عددیِ تلگرام در متنِ تازه: ندارد (`display_user`؛ کدِ سفارش = شناسه‌یِ سفارش) ✔️ · ۱۰) برچسبِ منو در ۴ جا ✔️ · ۱۱) تست‌هایِ قدیمی: فقط تستِ منو (بالا) ✔️ · ۱۲) N+1: `list_groups_for_customer` همه‌یِ سفارش‌هایِ مشتری رو می‌خونه و در پایتون صفحه‌بندی می‌کنه (برایِ مشتریِ با هزاران سفارش کند؛ ثبت برایِ I2) ⚠️ · ۱۳) لاگ: فاکتور/کد لاگ نمی‌شه ✔️.
  **بررسی‌نشدنی بدونِ Docker:** SQL (`FOR UPDATE`+`populate_existing`، savepointِ شمارنده)، ترتیبِ روتر (`order_ops` بعد از `panel`؛ اگه یک هندلرِ بی‌stateِ `panel` متنِ FSM رو بخوره، `test_lifecycle_group_ops` می‌شکنه)، dispatchِ aiogram؛ ۱۲ تستِ تازه فقط با sandboxِ منطقِ خالص (`order_state`، `suggest_cart_products`، `parse_key`) اجرا شدن.

## ۸) آنچه عمداً به فازِ ۲ رفت (و چرا)
- (تا P1-S5a-جزئی هیچ‌چیز؛ ⏩هایِ W1 در پایینِ همین بخش.)
- فازِ ۱ تموم **نشد**؛ به «فازِ ۲» هیچ‌چیز منتقل نشده (⏩هایِ W1 به W2 = بخشِ بعدیِ فازِ ۱ می‌رن). باقی‌مانده‌یِ فازِ ۱ (برایِ چتِ بعد، به‌ترتیب): S3 (B2)، S4 (C2–C4، C8، C9، D5-ساده)، باقی‌یِ S5a (B6، B7، B10، B11، F6، retryِ pending)، S5b (C5، C6)، S5c (C7)، S5d (M)، S6 (K1–K4(+K5))، و P1-END.
- **[W1 ⏩ منتقل‌شده به W2 (C3/S4)]:** (الف) *اعمالِ هزینه‌یِ ارسال در چک‌اوت* (انتخابِ روشِ ارسال، جمعِ کل، فاکتورِ تفکیک‌شده برایِ سبدِ ترکیبی): جدولِ `invoices`/ستون‌هایِ سفارش و چک‌اوتِ مرحله‌ایِ C3 در W2 ساخته می‌شه؛ در W1 فقط تعریفِ روش‌ها (`shipping_methods` + UI) هست. (ب) *«⬅️ برگشت»* در فرمِ افزودنِ دیجیتال (فقط «⏭ رد کردن» و «❌ انصراف» هست) ⇒ با `wizard_nav` مشترکِ W2. (ج) *«📥 دریافتِ دوباره» از «📦 سفارش‌هایِ من»*: منوی سفارش‌ها در W2 (C8/C9) می‌آد؛ فعلاً دکمه‌یِ همون پیامِ تحویله. (د) *تحویل بعد از `paid`*: در W2/W3 که `paid` هست (بند ۳ بالا). (هـ) فیلدهایِ فیزیکی در فرمِ افزودن (فعلاً فقط ویرایش).
- **[⏩ منتقل‌شده به چتِ بعد — جمع‌بندیِ W2+W3+W4]:** (الف) **C3 چک‌اوتِ مرحله‌ایِ کامل** (نامِ تحویل‌گیرنده/موبایل/دفترچه‌آدرس/روشِ ارسال و **هزینه‌یِ ارسال**) + `wizard_nav`؛ (ب) **C2 پیشنهاد+تاییدِ ویرایشِ سبد با AI**؛ (ج) تحلیلِ AIِ رسید (`receipt_ai_enabled` و ستون‌هایِ `ai_json/ai_verdict` آماده‌ان ولی استفاده نمی‌شن)؛ (د) B6 (polling پایدار)، B7 (رمزنگاریِ `bale_provider_token` — با تست‌هایِ قدیمی که توکنِ خام می‌ذارن باید هم‌زمان اصلاح بشن)، B10 روی مسیرِ قدیمیِ `bale_paid_at`؛ (ه) K1–K4 (اعتبارِ زمان‌دارِ ادمین)، سقف/کفِ مهلت‌ها توسطِ ادمین، هشدارِ «۲ ساعت مونده» روی رسیدِ بررسی‌نشده، تاییدِ دیرهنگامِ رسیدِ کارت بعد از انقضا (الان `illegal`)، برگشتِ موجودی بعد از `refunded`؛ (و) بقیه‌یِ موردِ W2 زیر.
- **[W2 ⏩، به‌ترتیبِ اولویت]:** (۱) **C3 چک‌اوتِ مرحله‌ایِ کامل** (نامِ تحویل‌گیرنده ← موبایلِ نرمال‌شده ← دفترچه‌آدرس `customer_addresses` [جدول ساخته شده، بدونِ UI] ← انتخابِ روشِ ارسال و **اعمالِ هزینه‌یِ ارسال** ← سوال‌هایِ فروشگاه‌دار ← توضیح ← پیش‌فاکتور با روشِ پرداخت) + `wizard_nav` («⬅️ برگشت» مشترک، شاملِ فرمِ دیجیتال) — چون جریانِ `CheckoutStates` رو عوض می‌کنه و ۳ فایلِ تستِ قدیمی (`test_shopping_cart`، `test_campaign_checkout`، `test_cart_ai_editing`) رو لمس می‌کنه، بدونِ Docker عمداً شروع نشد. (۲) **C2 پیشنهاد+تاییدِ ویرایشِ سبد با AI** (`cart_ai_proposals` ساخته شده ولی بی‌استفاده؛ تغییرِ رفتارِ `test_cart_ai_editing`). (۳) ~~ساختنِ `awaiting_payment`~~ **انجام شد در W3/W4**؛ تحویلِ دیجیتال و فاکتور در گذارِ `paid` هم برایِ کارت (`rcpt_ok`) و آنلاین (`notify_online_payment`) انجام می‌شه. (۴) اعلانِ خودکار به مشتری روی تاییدِ دستیِ قدیمی (`confirm_*`) — عمداً حذف تا تست‌هایِ شمارشِ پیام/سندِ W1 نشکنه. (۵) دکمه‌یِ «✉️ پیام به مشتری» روی اعلانِ سفارشِ **تک‌محصولی** (فقط گروه‌هایِ سبد دارنش؛ `og_msg:o<id>` آماده است). (۶) «📞 پشتیبانی دربارهٔ این سفارش»، فهرستِ سفارش‌هایِ فروشگاه‌دار، جابِ انقضایِ `awaiting_payment`. (۷) ~~W3 و W4 شروع نشدن~~ → هسته‌یِ هر دو انجام شد (بالا).
- **[W5 ⏩ منتقل‌شده، با دلیل]:** (۱) **wizard_nav در فرمِ افزودنِ محصولِ دیجیتال/فیزیکی** (دکمه‌یِ «⬅️ برگشت»): ماژولِ مشترک ساخته و در چک‌اوت استفاده شد؛ بازنویسیِ ماشینِ حالتِ چندمرحله‌ایِ پنل بدونِ Docker ریسکِ شکستنِ تست‌هایِ B2 داشت. (۲) **دکمه‌یِ reply-keyboardِ «اشتراکِ شماره»** در چک‌اوت (منویِ اصلی را عوض می‌کند). (۳) مدیریتِ دفترچه‌آدرس **بیرون از چک‌اوت** (منوی «آدرس‌هایِ من»). (۴) پاکسازیِ پیشنهادهایِ منقضیِ `cart_ai_proposals` (جدولِ کوچک؛ جابِ prune). (۵) رابطِ ادمین برایِ ثبتِ دلیلِ توقفِ جاب‌ها (فقط زمان/عامل ثبت می‌شه). (۶) **لایه‌یِ ۳ (فازِ ۲: D1-رله، D3، D4، D5-کامل، E1، E3، E4، G1، G2، H1، I1، I2، L1–L4 …)** کلاً شروع نشد: هر مورد نیاز به تایید Dockerِ لایه‌هایِ ۱–۲ دارد و قاعده‌یِ بودجه (۸۰٪) اجازه نداد؛ نصفه‌کاره نیامد.

## ۹) نتیجه‌یِ تستِ کاربر (چتِ ۲ پر می‌کنه)
- Docker: … · دستی: … · پرداخت‌هایِ واقعی: …
- **W1:** zip `kasb-o-kar-hoshmand_W1.zip` تحویل شد؛ نتیجه‌یِ Docker (۵۷/۳۴۶) منتظرِ کاربر.
- **W1..W4 (چتِ A):** zip `kasb-o-kar-hoshmand_W4.zip` (۵۹/۳۷۰، head `d4a9c6e2b8f1`) — همه‌یِ موج‌ها داخلشه؛ منتظرِ Docker.
- **Dockerِ اول (پس از `down -v`):** ۴۶/۵۶ فایل، ۲۸۹ تست. ۱۰ فایلِ ❌ (`message_debounce`، `photo_handling`، `voice_handling`، `order_product_id_matching`، `order_customer_confirmation`، `moderation_and_audit_log`، `wallet_integration`، `cart_ai_editing`، `phase6a_batching_and_settings`) همه به‌خاطرِ یک باگِ خودم: `TypeError: check_and_record() got an unexpected keyword argument 'last_name'` (تله‌یِ ۱۷). `test_identity_and_profile` هم یک false-positiveِ تست (تله‌یِ ۱۹) داشت و بعد از اولین assert متوقف شد؛ ۶ تستِ بعدیِ اون فایل هنوز اجرا نشده بود. هر دو در `P1-FIX1` اصلاح شد؛ منتظرِ اجرایِ دوبارهِ Docker.
- **Dockerِ دوم (`P1-FIX1`، پس از `down -v`): ۵۶/۵۶ فایل، ۳۳۱ تست ✅.** (S0، S1، S2، S5a-جزئی تایید شد.) تستِ دستی و پرداختِ واقعی هنوز انجام نشده.
- **W5 (چتِ B):** zip `kasb-o-kar-hoshmand_FINAL.zip` (۶۵/۴۱۲، head `d9e3a6b8c2f5`) تحویل شد؛ نتیجه‌یِ Docker منتظرِ کاربر. هیچ تستی در این چت اجرا نشد (sandbox بدونِ aiogram/SQLAlchemy/Postgres)؛ فقط منطقِ خالص با sandbox و گیت‌هایِ استاتیک (`check_refs`، `check_attrs`، `lint_names`، `audit_ai_commit`، پارسِ ast و تک‌headِ مایگریشن) تایید شد. احتمالِ خطایِ اول در Docker بالاست — لاگِ ❌ها را بفرست.

- **[W5 · Dockerِ اول: ۵۷/۶۲ فایل، ۳۵۷ تست]** ۵ فایل افتاد؛ علت‌ها همه در *تست‌ها* بود و اصلاح شد: `test_shopping_cart` (شمارشِ پیام‌ها پس از چک‌اوتِ ۸مرحله‌ای: ۸+۱=۹)، `test_cart_ai_editing` (تستِ «unsure» باید پیشنهاد را با `_apply` اعمال کند)، `test_checkout_c3` (بعد از انتخابِ آدرسِ ذخیره‌شده مرحله‌یِ «توضیح» هست)، `test_w5_layer2` (موجودیِ تست در چند چک‌اوتِ پشت‌سرهم تمام می‌شد و `group_id()` گروهِ قدیمی برمی‌گرداند ⇒ موجودی ۵۰)، `test_payments_w3w4` (`clamp_deadline/review_hold` اکنون سقفِ سخت‌اند؛ بازه‌یِ مجاز از `deadline_bounds/review_hold_bounds`). فایل‌هایِ بعد از اولین شکست در هر فایل هنوز اجرا نشده بودند ⇒ احتمالِ شکستِ تازه در آن‌ها هست.
- **[W5 · درخواستِ کاربر]** دکمه‌یِ «🧾 مدیریتِ سفارش‌ها (جاری)» (فقط فروشگاه‌دارِ فروشگاهی): `orders_manage_service` + `handlers/orders_manage.py` — فهرستِ گروه‌هایِ سفارشِ باز با اولویتِ «منتظرِ تصمیم»، فیلترِ «فقط منتظرِ اقدام»، صفحه‌بندیِ ۵تایی، تازه‌سازی، و بازکردنِ هر سفارش با *همان دکمه‌هایِ اقدامِ اعلانِ اصلی* (رسید، تایید/رد، پردازش، ارسال، استرداد، پیام). هیچ منطقِ تصمیمِ تازه‌ای ندارد؛ ایزولاسیونِ فروشگاه با `_load_rows`.
- **[W5 · باگ‌هایِ گزارشِ کاربر — رفع شد]** (۱) **رسیدِ متنی:** مشتری حالا می‌تونه متنِ رسید (کپی از اپِ بانک/پیامک؛ ≥۸ حرف و ≥۴ رقم) بفرسته، نه فقط عکس/فایل/«فقط شماره‌پیگیری». متن در `OrderPayment.receipt_text` ذخیره و برایِ فروشگاه‌دار زیرِ پیامِ رسید نشون داده می‌شه؛ شماره‌پیگیری فقط کنارِ برچسبش («پیگیری/رهگیری/مرجع») استخراج می‌شه (مبلغ و شماره‌کارت هرگز)؛ متنِ تکراری پرچمِ `dup_file` می‌گیره؛ تاییدِ دیرهنگام هم برایِ رسیدِ متنی کار می‌کنه. (۲) **عکسِ محصول:** عکس را فروشگاه‌دار در *رباتِ اصلی* آپلود می‌کرد و file_idِ آن در رباتِ فروشگاه معتبر نبود و هیچ مسیرِ نمایشی برایِ مشتری وجود نداشت. حالا: دکمه‌یِ «🖼» کنارِ محصولاتِ عکس‌دار در مرورِ محصولات، درخواستِ متنیِ «عکسِ X رو بفرست» (بدونِ AI/هزینه)، کارتِ محصول با «➕ افزودن به سبد»، آپلودِ دوباره به رباتِ فروشگاه + کشِ `Product.photo_shop_file_id` (قالبِ «برچسبِ منبع|file_id»؛ با تغییرِ عکس خودکار باطل می‌شه)، و کنترلِ مالکیتِ محصول (محصولِ فروشگاهِ دیگر/غیرفعال رد می‌شه). مایگریشن `d9e3a6b8c2f5`.
- **[W5 · بازبینیِ امنیتی]** گزارش: `docs/security-review-w5.md`. اصلاحِ فوری در کد: پورتِ Postgres فقط روی 127.0.0.1، غیرفعال‌کردنِ `/docs`/`/openapi.json`، مقایسه‌یِ زمان‌ثابتِ رازِ webhookها، خنثی‌سازیِ تزریقِ فرمول در اکسل‌ها؛ تست: `test_w5_security.py`.
- **[W5 · Dockerِ سوم: ۴۴/۶۵ فایل، ۳۴۴ تست]** تحلیل: **(الف) ۱۷ فایلِ «ادمین»** (admin_owner_management، payment_approval، admin_channel، admin_pricing، admin_settings، kill_switches، moderation، retention، pricing_formula، ai_key_pool، admin_rbac، wallet_correction، nightly_report، knowledge_gaps، accounting، phase6a، identity، bale_foundation) همگی با «Update … is not handled» و `IndexError` روی پیامِ ادمین افتادند ⇒ علت: این تست‌ها `ADMIN_TELEGRAM_IDS=12345` را فرض می‌کنن و در آن اجرا `.env`ِ واقعی (با آیدیِ ادمینِ شما) غالب بود؛ در Dockerِ دوم همین تست‌ها پاس بودند و هیچ کدِ ادمینی تغییر نکرده. **اصلاح:** `run_all_tests.py` حالا `ADMIN_TELEGRAM_IDS=12345` را به هر تست می‌دهد (متغیرِ محیطی بر `.env` غالب است؛ `.env`ِ واقعی دست‌نخورده می‌ماند). **(ب) سه ایرادِ واقعیِ تازه، اصلاح شد:** `test_payments_w3w4` (پیامِ مهلتِ نامعتبر حالا «بازه‌یِ مجاز» هم دارد)، `test_checkout_c3` (پیامِ «کدپستیِ نامعتبر» باید دکمه‌هایِ «⏭ رد کردن/⬅️ برگشت» را داشته باشد ⇒ در محصول اصلاح شد)، `test_w5_layer2::admin_time_ui_flow` (ادمینِ عملیاتی در دیتابیس ثبت نشده بود ⇒ تست `grant_operator` می‌زند). **(ج) سیستمِ لاگ:** `LOG_LEVEL`، قالبِ زمان‌دار، خاموش‌کردنِ نویزِ «Update handled»، و چرخشِ لاگِ Docker (۵×۱۰MB).
## ۹-پ۱۸) نتیجه‌یِ Docker در P18
- **اجرایِ نهایی (پس از همه‌یِ اصلاحات): ۷۷ فایل / ۴۹۲ تست ✅** (`docker compose build` ← `alembic upgrade head` ← `ADMIN_TELEGRAM_IDS=12345 run_all_tests.py`). headِ مایگریشن `c2e5a8b1d4f7` و `alembic heads` فقط همین یک شناسه را برمی‌گرداند.
- **مسیرِ سبز شدن (چیزی که افتاد و چرا):** بیس‌لاین ۶۵/۴۱۲ → پس از گروهِ ۱ و ۲ سبز → گروهِ ۳ در چند اجرایِ میانی ۷۰/۷۴ (۴۵۵) و ۷۶/۷۷ (۴۹۰) بود. علت‌ها و رفع‌ها:
  1. `from aiogram.types import Bot` ⇒ `ImportError` (در aiogram v3، `Bot` از `aiogram` می‌آید)؛ یک import، چهار فایل را خاموش کرده بود.
  2. پارامترِ `main_bot: Bot` در دو هندلرِ روترِ *اصلی* ⇒ aiogram آن را تزریق نمی‌کند (`TypeError: setting_value_entered() missing 1 required positional argument`)؛ به `bot: Bot` عوض شد (همان نمونه‌ای که آپدیت را دریافت کرده).
  3. `payment.purpose.value` ⇒ ستونِ enum رشته‌یِ خام است (`_enum_column` = `String(32)`).
  4. سه تستِ پنلی «خالی» را بدونِ دوباره‌زدنِ دکمه می‌فرستادند، ولی فلویِ تنظیمات بعدِ هر ذخیره `state.clear()` می‌کند ⇒ تست اصلاح شد نه محصول.
  5. `test_card_to_card_improvements` دو باگِ واقعیِ تستی را نشان داد: پیامِ «رسید بفرست/برگشت» (A7) پیامِ آخر شده بود، و `FakeSession` اصلاً `parse_mode` را ضبط نمی‌کرد ⇒ هر دو اصلاح شد.
  6. `normalize_sender_digits` و قالبِ پیش‌فرضِ OTP داخلِ `KavenegarSmsService.__init__` بودند و تست با جعلِ factory از آن‌ها رد می‌شد ⇒ تصمیمِ لایه‌ای: مصرف‌کننده (`otp_service`) مقادیرِ مؤثر را خودش نرمال/حل می‌کند تا هر provider یکسان صدا زده شود.
  7. `build_invoice_data([])` با `IndexError` می‌ترکید (فاکتورِ بدونِ قلم) ⇒ در محصول اصلاح شد.
  8. Vazirmatn جادویِ `✓` را ندارد ⇒ فاکتور PDF جعبه‌یِ خالی می‌گذاشت؛ تستِ «هیچ warningِ missing glyph نباید باشد» اضافه شد.
- **مشاهده‌یِ از پیش موجود (عمداً دست‌نزنده):** `ERROR asyncio: Unclosed client session` در انتهایِ چند فایلِ تست که AI را با aiohttp جعل می‌کنند. در بیس‌لاین هم بود و تستی نیست (اثری رویِ نتیجه ندارد) ⇒ ⏩ (بستنِ `_http_session` در fixture مشترکِ تست‌ها).

## ۱۰) کارِ بعدی (دقیق: کدوم مرحله/فایل)
- **اول: Docker برایِ W1..W4** (`docker compose down -v` فقط اگه «Can't locate revision»؛ سپس `build` ← `alembic upgrade head` (باید به `d4a9c6e2b8f1` برسه) ← `run_all_tests.py` (انتظار: **۵۹ فایل / ۳۷۰ تست**)). خروجی/خطاها رو بفرست؛ ترایاژ (p15 بخشِ ۷) قبلِ موجِ تازه.
- بعدش **باقی‌یِ W2** (⏩هایِ W2 در بخشِ ۸: C3 چک‌اوتِ مرحله‌ایِ کامل + هزینه‌یِ ارسال + wizard_nav؛ C2 پیشنهاد/تایید) و سپس W3 و W4 طبقِ p16.
- چک‌لیستِ تستِ دستیِ W1 (۸ مورد): ۱) «➕ افزودن» ← «💾 افزودنِ محصولِ دیجیتال» ← لینک؛ ۲) همون با «🔑 کدِ یکتا» و ۳ کد؛ ۳) در رباتِ مشتری سبد ← چک‌اوت (فقط «شماره تماس» پرسیده شه) ← ثبتِ نهایی؛ ۴) «✅ تایید» سفارش ← پیامِ تحویل به مشتری + «📥 دریافتِ دوباره»؛ ۵) «🚚 روش‌هایِ ارسال» ← افزودن/خاموش/حذف؛ ۶) «✏️ ویرایش» محصولِ فیزیکی ← وزن/زمانِ تحویل؛ ۷) «✏️ ویرایش» محصولِ کدی ← «🔑 افزودنِ کد» با فایلِ txt؛ ۸) در مودِ مشاوره دکمه‌هایِ دیجیتال/ارسال دیده نشن.
- **[بعد از W5] اول:** Docker برایِ FINAL: `docker compose down -v` فقط اگه «Can't locate revision» ← `build` ← `alembic upgrade head` (باید به `d9e3a6b8c2f5` برسه؛ مایگریشنِ `b7c1e4a9d2f3` به `ENCRYPTION_KEY` نیاز دارد) ← `run_all_tests` (انتظار ۶۵ فایل / ۴۱۲ تست). ❌ها را بفرست تا اصلاح شود.
- **چک‌لیستِ تستِ دستیِ W5 (۸ مورد):** ۱) سبدِ فیزیکی ← نهایی‌کردن ← نام ✅ ← موبایل ← آدرسِ تازه ← (ارسال) ← پیش‌فاکتور با هزینه‌یِ ارسال ← ثبت؛ ۲) چک‌اوتِ دوم: آدرسِ ذخیره‌شده + «✏️ آدرس» + «⬅️ برگشت»؛ ۳) «دوتا برنج اضافه کن» ← پیشنهاد ← «✅ اعمال» (و دابل‌تپ)؛ ۴) تاییدِ دستیِ یک سفارشِ فیزیکی ← مشتری پیام می‌گیره؛ ۵) کارت‌به‌کارت با عکسِ رسیدِ واقعی ← خطِ «🤖 تحلیلِ خودکار» + کسرِ هزینه؛ ۶) «⏱ اعتبار و زمان» ← هدیه‌یِ گروهی (پیش‌نمایش ← تایید) و توقفِ زمان (شروع/ازسرگیری)؛ ۷) تنظیماتِ ادمین ← حدودِ مهلت ← سعی در ثبتِ مهلتِ خارج از بازه؛ ۸) `BALE_UPDATES_MODE=polling` و یک پرداختِ آزمایشیِ بله‌پی.
- بعدش: ⏩هایِ W5 (بخش ۸) و فازِ ۲ (لایه‌یِ ۳) طبقِ p17.

## ۱۰-پ۱۸) کارِ بعدی (P19)
- **اولِ اولویت:** تستِ دستیِ چک‌لیستِ ۱۰موردیِ `docs/changelog-p18.md` + یک پرداختِ واقعیِ کوچک (کارت‌به‌کارت و بله‌پی) رویِ دیتابیسِ واقعی.
- ⏩هایِ P18 که باید در P19 تصمیم گرفته شوند: (۱) قیمت‌گذاریِ صوت **به‌ازایِ دقیقه** (ستونِ تازه + سقفِ طولِ ویس) به‌جایِ مبلغِ ثابتِ ۳۰۰؛ (۲) قیمت‌گذاریِ تحلیلِ رسید با فرمولِ توکنی (مثلِ چت) به‌جایِ ۵۰۰ ثابت؛ (۳) بودجه‌یِ کلیِ «تعدادِ تلاشِ HTTP در هر درخواست» برایِ استخرِ AI (الان ۵ مدلِ پشتیبان × retryِ خودش)؛ (۴) بستنِ `aiohttp.ClientSession` در تست‌ها؛ (۵) رمزنگاریِ `ShopBot.token` در صورتِ نیاز به چرخشِ کلید (مهاجرتِ داده با ENCRYPTION_KEYِ تازه).
- اگر بیو/برندینگ گسترش یافت: متنِ ادمین فعلاً یک رشته‌یِ سراسری است؛ نسخه‌یِ per-shop یا per-category نیاز به طراحیِ دوباره دارد.


## ۱۱) پ۱۹ — بیوگرافی، رباتِ بلهٔ هر فروشگاه، مرتب‌سازیِ منو

تاریخ: ۲۰۲۶-۱۱-۰۱ · شاخه: `bio-bale-fixes` · مایگریشنِ head: `a1d5e9f3b7c2` · سه commit:
`e21f9b2` (رفعِ بیو) · `b30366f` (رباتِ بله) · `54e7495` (مرتب‌سازیِ منو).
جزئیاتِ کامل: `docs/changelog-p19.md`.

### ۱۱-۵) تغییراتِ **عمدیِ** رفتار (به‌جایِ شکستنِ بی‌صدایِ تست‌هایِ قبلی)

| تغییر | چرا | تستِ به‌روز شده |
|--------|------|------------------|
| دورهٔ بازرسیِ بیو ۶ ساعت ← ۱ ساعت | با ۶ ساعت «بیو دستکاری شد و برگشت» عملاً دیده نمی‌شد؛ هزینه‌اش یک GET به‌ازایِ هر ربات در هر دور است | `test_p18_bot_branding.py::test_branding_job_interval` |
| متنِ پیش‌فرضِ بیویِ تلگرام دیگر «دست‌کاری» نیست | وگرنه اولین پاس برایِ همهٔ ربات‌هایِ تازه اخطارِ بی‌دلیل می‌فرستاد | همان فایل، بخشِ apply |
| `_ctx`/`_resolve` در رباتِ فروشگاهی به‌جایِ عددِ `bot.id` خودِ شیء `Bot` را می‌گیرد | پلتفرم (تلگرام/بله) از عددِ شناسه قابلِ فهمیدن نیست | همهٔ تست‌هایِ رباتِ مشتری (بدونِ تغییرِ متنِ تست) |
| `deliver_pending_for_product(product, bot_manager, shop_bot_id, main_bot)` | تحویلِ دیجیتال باید از رباتِ همان پلتفرمِ مشتری برود | تست‌هایِ محصولِ دیجیتال |
| `broadcast_customer_ids` در FSM = شناسهٔ **ردیفِ** مشتری، نه شناسهٔ تلگرام | تا پلتفرمِ هر گیرنده موقعِ ارسال پیدا باشد | `test_crm.py` |
| منویِ تنظیماتِ ادمین دوسطحی شد (۱۰ سوییچ + ۷ دسته) | ۵۵ ردیفِ تخت؛ ادمین مقدار را پیدا نمی‌کرد. هیچ callback/مقداری حذف نشد | `test_admin_settings.py::test_settings_menu_is_grouped_and_complete` (تازه) |
| `run_periodic_tasks(main_bot, stop_event, bot_manager)` آرگومانِ سوم | بدونِ آن پاسِ بیو هرگز اجرا نمی‌شد (ریشهٔ باگِ گزارش‌شده) | `test_p18_bot_branding.py::test_periodic_pass_restores_tampered_bio` (تازه) |

### ۱۱-۹) تست

**۸۲ فایل / ۵۳۶ تست** (`run_all_tests.py`)؛ فایلِ تازهٔ `test_p19_bale_shop_bot.py` (۸ تست) و یک تستِ تازه
در `test_admin_settings.py`. هارنس: `FakeSession` حالا `GetMyShortDescription`/`SetMyShortDescription`
را پشتیبانی می‌کند (لازمِ رگرسیونِ بیو).

### ۱۱-۱۰) کارِ بعدی

- **تستِ دستیِ بله** (چهار موردِ انتهایِ بخشِ P19 در `docs/admin-guide.md`) — تنها راهِ
  مطمئن‌شدنِ سازگاریِ API بله؛ تا آن وقت ویژگی را برایِ همه رونمایی نکن.
- سه باگِ HIGHِ پولیِ پیدا‌شده در ممیزیِ منطقی (دفترِ نامتکرارِ شارژ، قفلِ موجودیِ محصول، نشتِ holdِ
  کمیسیون در «پرداختِ دستی») — فهرستِ ۱۳موردی با شاهدِ فایل:خط در `REMAINING_ISSUES.md` بخشِ P19.

## ۱۲) پ۲۰ — رفعِ همهٔ باگ‌هایِ باقی‌مانده، امنیتِ حداکثری، بهینه‌سازیِ سراسری و ظرفیت‌سنجی

تاریخ: ۲۰۲۶-۱۱-۰۱ · شاخه: `p20-hardening` · مایگریشنِ head: `d4a8c2e6f9b3` (یک head) · پنج commit:
`7f4d337` (پول) · `2ef7db5` (امنیت) · `9960692` (عملکرد+outbox) · `8c335c4` (صفِ اعلان در پنل) ·
`dd2a7b2` (استخر/ظرفیت). جزئیاتِ کامل: `docs/changelog-p20.md`.

### ۱۲-۱) آنچه بسته شد

- **۸ باگِ پولیِ تأییدشده** + ۴ باگِ رفتاری (کپشنِ بلند، `answer()` دوباره‌ای، آستانهٔ انقضا،
  `usable_credit` دوتایی) — همه با رگرسیونِ مستقل در `test_p20_money_integrity.py`.
- **سه بلاکرِ تولیدِ `SECURITY_AUDIT_REPORT.md`**: B2 (رمزنگاریِ رازِ وب‌هوک + بازمهندسِ ردیف‌هایِ قدیمی)،
  B3 (محدودِ درخواست per `(ip,path)` با ۴۲۹ِ فارسی و `TRUST_PROXY_HEADERS`)، B1 (لاگِ scrub‌شده،
  correlation-id، `/metrics` با توکن، زنجیرهٔ هشِ دفترِ ممیزی + `scripts/verify_audit_chain.py`).
- **بهینه‌سازی**: ۵ ایندکسِ تازه، خاتمهٔ کوئریِ پنهانِ «همهٔ محصولات» (`lazy="raise"`)،
  استخرِ اتصالِ ثابت (`25+0`، `pool_timeout=15`) که ۲٫۸ برابرِ توانِ اندازه‌گیری‌شده را پس داد.
- **ویژگی‌هایِ تازه**: صندوقِ خروجیِ اعلان‌ها (backoffِ ۶ مرحله‌ای + dedupe + صفِ قابلِ شمارش)،
  گزارشِ همان صف در پنلِ ادمین با «تلاشِ دوباره»، دو عددِ درستِ کیف‌پول («قابل‌استفاده» و
  «در آستانهٔ انقضا»)، دکمهٔ همگام‌سازیِ فوریِ بیوگرافی.

### ۱۲-۲) ظرفیت (MEASURED)

`scripts/loadtest_message_path.py` رویِ `kasbokar_load` (ایزوله، گاردِ `LOADTEST_DB_CONFIRM=1`):
**بامِ یکِ پروسه ≈ ۱۴۵ پیامِ کاملِ مشتری در ثانیه**، منحنیِ صاف تا همزمانیِ ۴۰۰، `errors=0`؛
pgbench رویِ همان میزبان ≈ ۲٬۰۰۰ تراکنشِ PG/s ⇒ گلوگاه، CPUِ پایتون است نه دیتابیس.
تبدیلِ محافظه‌کارانه: **≈۸٬۷۰۰ کاربرِ فعالِ هم‌زمان با ۱ پیام/دقیقه** (فقط کد+DB؛ سقفِ AI و
`AI_MAX_CONCURRENT_CALLS=40` در عمل زودتر می‌شکنند ⇒ با AIِ ۳ ثانیه‌ای ≈ ۴۰۰ کاربر).
تأخیرِ AI **NOT RUN** (هزینهٔ واقعی). جدول‌ها: `SCALABILITY_AND_LOAD_TEST_REPORT.md` §۹ و
توصیهٔ سخت‌افزار: `HARDWARE_REQUIREMENTS_AND_CAPACITY_PLAN.md` §۸-الف (شروع: ۴ vCPU / ۸GB /
۸۰GB NVMe؛ اولین ارتقا جداکردنِ DB).

### ۱۲-۳) تغییراتِ **عمدیِ** رفتار (تست‌هایِ قدیمی به‌خاطرِ این‌ها به‌روز شدند)

| تغییر | چرا | تستِ به‌روز شده |
|--------|------|------------------|
| «🎁 اعطای اعتبارِ هدیه» پیش‌نمایش + تاییدِ nonce + سقفِ مبلغ گرفت | دابل‌تپ/اشتباهِ تایپی = خلقِ اعتبارِ نامحدود (دکمه در پنلِ ادمینِ عملیاتی می‌ماند؛ نقش‌آگاه‌سازیِ کیبوردِ جزئیاتِ فروشگاه‌دار کارِ بعدی است) | `test_admin_owner_management.py`، `test_wallet_correction.py` (یک‌تپِ `admin_gift_confirm`) |
| `approve_*_payment` در تاییدِ تکراری `(None, None)` می‌دهد | دو وب‌هوکِ تکراری نباید دو شارژ بسازد | `test_p20_money_integrity.py::test_payment_approved_twice_credits_once` + نگهبانِ `_effect is None` در پنل |
| `find_charges_needing_reminder` سه‌تاییِ `(charge, threshold, ceil_days_left)` برمی‌گرداند | پیامِ «۷ روز دیگر» برایِ بسته‌یِ ۲ روزه گمراه‌کننده بود | `test_p2_credit_expiry_preserved.py` |
| `ShopBot.products` با `lazy="raise"` | خواندنِ `ShopBot` نباید بی‌خبر فهرستِ محصولات را بیاورد | `test_p20_performance_outbox.py::test_shop_bot_products_is_no_longer_eagerly_loaded` |
| `db_max_overflow` از ۳۰ → ۰ | بارسنجی: اتصالِ اضافه در اوج، توان را از ۱۳۶ به ۴۸ می‌رساند | `test_phase6a_batching_and_settings.py` (sizing را از تنظیمات می‌خواند) |
| منویِ تنظیماتِ دستهٔ «🏪 فروشگاه‌دارها و گزارش‌ها» دکمهٔ صفِ اعلان گرفت | دیدِ ادمین از «چند خبر نرسیده» + راهِ اقدام | `test_p20_performance_outbox.py::test_admin_notification_queue_panel_and_retry` |

### ۱۲-۴) نکتهٔ عملیِ زیستِ تست (برایِ دفعهٔ بعد)

کانتینرِ `bot` در حالِ polling، `reset_database()` (TRUNCATE) را **بن‌بست** می‌کند. قبل از سوئیت:
`docker compose stop bot` و بعد از آن `docker compose up -d bot`. همین یکی از فایل‌هایِ سوئیت
(`test_p19_bale_shop_bot.py`) را در اجرایِ کامل بدونِ خطایِ واقعی «fail» نشان داد؛ با بوتِ
خاموش، هر ۸ تستش پاس شد.

### ۱۲-۵) تست

سه فایلِ تازه / **۲۳ تستِ تازه** (۸ پول + ۸ امنیت/قابلیتِ مشاهده + ۷ عملکرد/outbox) +
تقویتِ `test_admin_settings.py` و `test_admin_rbac.py` (نگهبانیِ سطحِ callback).
سوئیتِ پایانی: **۸۵/۸۵ فایل · ۵۵۹ تست · صفر fail · صفر skip** — جدولِ کامل در `TEST_RESULTS.md` §۸.

### ۱۲-۶) کارِ بعدی

- `REMAINING_ISSUES.md` §«P20 — آنچه عمداً باز ماند» (امضایِ بله‌پی، تستِ زندهٔ بله، بارِ HTTP،
  پنلِ لاگ، بدهکاریِ کمیسیون، قیمتِ صوت، و سه مانعِ stateless‌سازی).
- PHASE 6 (صورتحسابِ مصرفِ API) هنوز باز است.

---

## ۱۳) پ۲۱ — بیوگرافیِ کامل، سریع‌بردها، پولِ منصفانه، رشد، نقش‌ها و بازرسیِ امنیتی

تاریخ: ۲۰۲۶-۱۱-۰۱ · شاخهٔ `p20-hardening` · headِ مایگریشن: `c9f4a7e2b5d8` (تک‌head، ۵۴ مایگریشن)
· جزئیاتِ فنیِ هر گروه در `docs/changelog-p21.md`.

### ۱۳-۱) چه شد

| گروه | محموله |
|---|---|
| P21-A | بیوگرافی: قاعدهٔ محصول (فقطِ رباتِ فروشگاه، هرگزِ رباتِ اصلی) — پوششِ بله، محافظتِ متنِ خودِ فروشگاه، بازرسیِ per-ربات با بازهٔ قابلِ تنظیم، گزارشِ تخلف، اخطارِ ماندگارِ ۲۴ ساعته، و تفکیکِ «ویرایشِ عادی» از «دستکاری» (رفعِ false-positiveِ P18) |
| P21-B | `/health` + `/metrics` در حالتِ polling (اپِ جدا بدونِ مسیرهایِ webhook)، پاک‌سازیِ خودِ صفِ اعلان، تنظیمِ PostgreSQL در compose، پاک‌کردنِ F-codes، تخلیهٔ صف هر ۶۰ ثانیه |
| P21-C | قیمتِ دقیقه‌ایِ صوت و توکنیِ رسید (با پیش‌فرضِ صفر = رفتارِ قبلی)، دفترِ «طلبِ کمیسیون» با جمع‌آوریِ خودکار از `usable_credit`، و مسیرِ داغِ یک‌گزاره‌ایِ مشتری |
| P21-D | خلاصهٔ پولیِ گزارشِ شبانه، پخشِ زمان‌بندی‌شده (سوار بر صندوقِ اعلان)، اخطارِ موجودیِ کم per-shop، پیگیریِ مشاوره، و `scripts/seed_demo.py` |
| P21-E | دامنهٔ فروشگاه‌دارها برایِ ادمینِ عملیاتی، فیلتر/پنجره/CSVِ دفترِ ممیزی، سلامتِ مدارِ استخرِ AI، قفلِ advisoryِ جاب برایِ چندپروسه |
| P21-F | بازرسیِ امنیتی + رفعِ هشت یافته (جدولِ §۶ِ changelog) |
| P21-G | سوئیتِ کامل، ریستِ دیتابیسِ توسعه و بالا آوردنِ داکر |

### ۱۳-۲) رفتارهایی که عمداً عوض شدند (و تست‌هایِ قدیمیِ همان‌ها)

| رفتارِ تازه | چرا | فایلِ قدیمیِ به‌روز‌شده |
|---|---|---|
| `parse_owner_ids("")` ⇒ `set()` (نه `None`) و `set_scope(role, [])` ⇒ `""` (نه NULL) | «دامنهٔ تهی» قبلاً یعنی **دسترسیِ کامل**: اگر ادمین فهرستِ تایپی/بی‌نتیجه می‌فرستاد، نتیجه برعکسِ قصدش می‌شد | `test_p21_access.py::test_scope_parsing_is_pure` |
| `retry_failed()` دیگر `last_error` را پاک نمی‌کند و تا `RETRY_BATCH_LIMIT=1000` ردیف برمی‌گرداند | پنل وعدهٔ «پاک نشدنِ تاریخچه» را می‌داد و آن متن تنها شاهدِ «چرا نرسید» است؛ بازگرداندنِ کلِ صفِ شکست‌خورده در یکِ کلیک ریزشِ دوباره رویِ همان کانالِ خراب است | `test_p20_performance_outbox.py::test_admin_notification_queue_panel_and_retry` |
| کیبوردِ تاییدِ پیامِ همگانی دکمهٔ «⏰ برایِ بعد از» گرفت | P21-D (F2) | `test_crm.py`، `test_campaign_owner_flow.py` |
| صفحهٔ «⚙️ تنظیماتِ ربات فروشگاه» دکمهٔ «📦 اخطارِ موجودی» گرفت | P21-D (F5) | `test_phase6a_batching_and_settings.py` |
| منویِ مشتریِ مشاوره‌ای «🧾 سفارش‌های من» گرفت | P21-D (F6) | `test_customer_menu_and_prompts.py` |
| `app.include_router(observability_router)` ⇒ `app.routes` یکِ `_IncludedRouter` دارد | P21-B (O2)؛ starlette 1.x route‌های include‌شده را تنبل نگه می‌دارد و `route.path` ندارد | `test_w5_security.py::test_api_docs_are_disabled` (همان کمکیِ `test_p21_ops.py`) |

### ۱۳-۳) بازرسیِ امنیتیِ P21-F — هشت یافته، همه با تست

`tests_manual/test_p21_security.py` (۱۲ تست). دو بازرسیِ read-onlyِ مستقل + بازبینیِ دستی.
خلاصه در `docs/changelog-p21.md` §۶ و یافته‌هایِ پذیرفته‌شده/بازمانده در
`REMAINING_ISSUES.md` §«P21 — آنچه عمداً باز ماند».

### ۱۳-۴) تستِ پایانی و وضعیتِ اجرا (MEASURED)

سوئیتِ کامل با کانتینرِ `bot` **خاموش**: **۹۰/۹۰ فایل · ۵۹۸ تست · صفر fail · صفر skip**
(بیس‌لاینِ پیشِ P21: ۸۵/۵۵۹). جدولِ کامل در `TEST_RESULTS.md` §۱۱.

بعد از ریستِ دیتابیسِ توسعه (pg_dump → `DROP SCHEMA public` → `alembic upgrade head` →
`docker compose up -d`) و seedِ دادهٔ نمایشی:

- `/health` ⇒ `200 {"status":"ok"}`، `/metrics` ⇒ `404` (بدونِ `METRICS_TOKEN`)،
  `/docs` ⇒ `404`، `/webhook/main` ⇒ `404` — یعنی اپِ سلامتِ حالتِ polling دقیقاً همان دو مسیر
  را دارد و نه بیشتر (MEASURED داخلِ کانتینر).
- لاگِ بوت‌آپ تمیز: `.env معتبر`، `دیتابیس آماده`، `مایگریشن‌ها اعمال شد`،
  `0 ربات فروشگاهی فعال`، `اپِ سلامت روی 0.0.0.0:8000`، `Start polling` ← `@Kkhtest2robot`.
  تنها خطاهایِ ظاهری دو `DeprecationWarning`ِ از پیش موجودِ `on_event` است.
- اثباتِ زندهٔ ماسکِ راز: شناسهٔ رباتِ اصلی در لاگ `id=924●●●●` چاپ شد (الگویِ شمارهٔ موبایلِ
  ایران رویِ ارقامِ ۱۰digitِ تلگرام هم اثر می‌کند — بی‌ضرر، شناسهٔ ربات راز نیست).

### ۱۳-۵) کارِ بعدی

- `REMAINING_ISSUES.md` §«P21 — آنچه عمداً باز ماند» (صفِ اعلانِ per-shop، سقفِ مخاطبِ پخش،
  `/health` بی‌احرازِ هویت، دامنه‌دارنکردنِ صفِ تاییدِ پرداخت، نبودِ سقفِ مبلغِ اصلاحِ کیف‌پول).
- PHASE 6 (صورتحسابِ مصرفِ API) هنوز باز است.

---

## ۱۴) پ۲۲ — چینشِ دکمه‌هایِ رباتِ کاربر (دونادونه)

منویِ مشتری ستونی بود (هر دکمه یکِ ردیفِ تمام‌عرض ⇒ منویِ بلند و بی‌نظم). `app/bots/shop_bot/keyboards.py`
یکِ تابعِ مشترکِ ردیف‌بندی `_chunks(items, 2, max_label)` دارد و این صفحه‌ها دونادونه شدند: منویِ اصلی
(فروشگاهی و مشاوره‌ای)، فهرستِ «📦 سفارش‌هایِ من»، کارتِ سفارش، پیش‌نمایشِ چک‌اوت، انتخابِ روشِ پرداخت،
رسید، تاییدِ سفارش، کارتِ محصول و نگارستانِ عکس‌ها.

دو قاعده عمداً از «دونادونه» سرپیچی می‌کنند:
- دکمهٔ «❌ …» تمام‌عرض و تنها می‌ماند؛ `myord_cancel:` بی‌تاییدیهٔ دوم سفارش را لغو می‌کند و یکِ
  کلیکِ کنارِ دستی نباید سفارشِ درست را بکُشد.
- برچسبِ بلندتر از ۲۶ نویسه تنها می‌ماند، چون تلگرام دکمهٔ تنگ را با «…» می‌بُرد
  (مثلاً «🤝 پرداختِ دستی/هماهنگی با فروشگاه»).

ترتیبِ خطیِ دکمه‌ها هیچ‌جا عوض نشده ⇒ هندلرها و تست‌هایِ قدیمی دست‌نخورده‌اند.
تست: `tests_manual/test_customer_keyboard_layout.py` (۵ مورد، سطحِ ساختارِ ردیف).
NOT RUN: نمایشِ واقعی در تلگرام/بله (چینشِ نهایی به عرضِ صفحهٔ کاربر بستگی دارد).

---

## ۱۵) پ۲۲ — هشتِ مشکلِ کاربر (به ترتیبِ خودش) و لایهٔ حرفه‌ای‌سازی

جزئیاتِ کامل و جدولِ «چه/کجا» در `docs/changelog-p22.md` است؛ این‌جا فقط خلاصهٔ وضعیت:

| # | مشکل | وضعیت |
|---|---|---|
| ۱ | متنِ «شارژِ تازه بزن» + «ماه = ۳۰ روز؟» | ✅ `add_months` (ماهِ تقویمی) + متنِ مسیرِ واقعیِ دکمه |
| ۲ | دکمه‌ها دونفره نیستند | ✅ `grid(per_row=2, max_label=…)` در هر دو پنل + رباتِ مشتری |
| ۳ | ثبتِ رباتِ بله‌پی در پنلِ فروشگاه‌دار نیست | ✅ «🔑 توکنِ درگاهِ بله‌پی» در صفحهٔ پرداخت |
| ۴ | فاکتور و فایل‌هایِ خروجی زشت‌اند | ✅ PDFِ نوین + HTMLِ نوین + اکسل/CSVِ نوین (جمعِ کل، هزارگان، فیلتر، زبانهٔ رنگی، تاریخِ جلالی) |
| ۵ | روشِ ارسال پرسیده نمی‌شود و به هزینه اضافه نمی‌شود | ✅ گام همیشه پرسیده می‌شود (روشِ واقعی یا «🤝 هماهنگی ارسال») + دعوتِ فروشگاه‌دار به تنظیم با مسیرِ دقیق |
| ۶ | پنلِ ادمین و کاربر حرفه‌ای‌تر شود | ✅ چهار لایه: تاریخِ جلالیِ یکدست، ارقامِ فارسی، واژگانِ یکدستِ سوییچ‌ها + برشِ برچسب، بازخورد/ناوبری/صفحهٔ خالی (سیاههٔ بازمانده‌ها در REMAINING_ISSUES §P22) |
| ۷ | دادهٔ پنل پاک نشود | ✅ تست‌ها روی `kasbokar_test` + گیتِ ضدِ TRUNCATE + **رفعِ باگِ مرگبارِ `seed_demo --cleanup`** (با `>=` همهٔ حساب‌هایِ واقعی را پاک می‌کرد) + pg_dump |
| ۸ | دیلیت‌اکانت و دستهٔ غیرفعال‌ها | ✅ «🧹 کاربرانِ غیرفعال» (۷/۳۰/۹۰ روز) + حذفِ نرم با تایید + حذفِ قطعی با نوشتنِ «حذفِ قطعی» و ممیزی؛ دروازهٔ حسابِ پاک‌شده ادمین‌هایِ پلتفرم را قفل نمی‌کند |

کارِ بعدیِ این بخش: صفحه‌بندیِ واقعی برایِ ۱۵ فهرستِ بریده‌شده، تاییدِ دو مرحله‌ای برایِ
حذفِ کمپین/کلیدِ AI/نگهبان/ادمین، و PHASE ۶ (صورتحسابِ مصرفِ API).

## ۱۶) پ۲۳ — «دکمه‌هایِ پرداختِ اعتبار هیچ‌کاری نمی‌کردند»

گزارشِ کاربر بعد ازِ تنظیمِ توکنِ بله/پروایدر و شماره کارت در پنلِ ادمین. تشخیص از لاگِ زنده و
`payment_event_logs` گرفته شد، نه از حدس (جدولِ کامل در `docs/changelog-p23.md`):

| علت | شاهد | رفع |
|---|---|---|
| بله از `createInvoiceLink` شناسه می‌دهد نه آدرس | `result: "invoice_id=M6dm…"` و بعد `TelegramBadRequest: inline keyboard button URL 'invoice_id=…' is invalid: Wrong HTTP URL` | `bale_service.resolve_payment_link` + ستونِ `admin_settings.bale_pay_link_template` (مایگریشنِ `b3e7d1a9c4f6`) + فیلد در «🔑 تنظیمات کلیدها». بدونِ قالب، دکمهٔ بله‌پی هیچ‌جا ساخته نمی‌شود |
| سه دکمهٔ «روشِ پرداخت» با state خالی می‌شکستند | `KeyError: 'base_amount'` / `'final_amount'` در لاگ (FSM در `MemoryStorage`؛ کیبوردِ کهنه یا ری‌استارت) | `_payment_draft()` + توستِ `PAYMENT_FLOW_STALE` پیش ازِ هر نوشتن؛ بدونِ ردیفِ Payment نیمه‌کاره |

تغییرِ رفتاریِ عمدی که پنج فایلِ قدیمی را هم‌راستا کرد: `shop_status`/`platform_status` حالا
قالبِ لینک را هم می‌شمارند ⇒ `test_p18_bale_credentials` (۴ علت ⇒ ۵ علت)،
`test_bale_pay_for_orders`، `test_shopping_cart`، `test_campaign_checkout` و
`test_payments_w3w4` (تنظیمِ قالب در بلوکِ پیکربندی). تستِ تازه:
`test_p23_bale_payment_link.py` (۶ مورد).

**بازمانده (نیازمندِ متنِ برگهٔ بله):** کانالِ «بعد ازِ پرداخت، خودکار تایید شود» برایِ مسیرِ
لینک. راستی‌آزماییِ امروز شناسهٔ تراکنش را از آپدیتِ `successful_payment` می‌گیرد (مسیرِ چت)؛
برایِ لینک یا callback با HTTPS عمومی لازم است یا استعلام با همان `invoice_id` — که فقط از
«اطلاعات اتصالِ وب‌سرویس» صادرشده توسطِ خودِ بله در می‌آید. `REMAINING_ISSUES.md` §P23.

## ۱۷) پ۲۴ — شکارِ باگِ منطقی/امنیتی و آماده‌سازیِ دیپلوی

جزئیات در `docs/changelog-p24.md`. خلاصهٔ سه خواستهٔ این پاس:

| خواستهٔ کاربر | نتیجه |
|---|---|
| «دکمهٔ ارسال‌های زمان‌بندی‌شده چیزی نداره که کار کنه» | سه علتِ جدا: صفحهٔ خالی بدونِ هیچ دکمه ⇒ `scheduled_empty_keyboard`؛ نبودِ راهِ ساختِ ارسال از همان صفحه ⇒ هندلرِ `sched_new`؛ افشایِ شناسهٔ داخلی در برچسبِ «🗑 لغوِ ارسالِ شمارهٔ ۱۷» ⇒ شمارهٔ صفحه‌ایِ ۱..N. **کشفِ بزرگ‌تر:** `callback_data="main_menu"` در پنج کیبورد ساخته می‌شد با *هیچ* هندلر ⇒ هر صفحهٔ خالیِ پنل بن‌بست بود؛ `cb_back_to_panel` اضافه شد (کیبوردِ درست برایِ هر نقش). |
| «دکمه‌هایِ دونفرهٔ رباتِ مشاوره‌ای را بردار» | «🗂 خدمات و بسته‌ها» و «📦 سفارش‌هایِ من» حذف شدند؛ در آن حالت همیشه خالی بودند (کاتالوگ در مشاوره عمداً بسته است؛ پیگیری فقط `OrderType.ORDER` را می‌خواند و درخواست‌هایِ این مود `CONSULTATION`‌اند). منو یا فقط «📞 پشتیبانی» است یا `ReplyKeyboardRemove` تا دکمه‌هایِ مرده از صفحهٔ مشتری هم برداشته شوند؛ تپِ کهنه به منویِ درست می‌رود. |
| «باگ‌هایِ منطقی و امنیتی را پیدا و رفع کن؛ آمادهٔ دیپلوی» | ۱ حفرهٔ دسترسیِ پول (تایید/ردِ پرداخت بدونِ `_scoped_owner`) + ۸ hardening (حالتِ تعمیر رویِ سه دکمهٔ مشتری، ۱۲ سقفِ عددیِ تازه، `ai_base_url` ⇒ ضدِ SSRF/نشتِ کلید، اسکرابرِ شمارهٔ کارت، سقفِ ۵MB عکسِ مشتری، پیام همگانیِ ادمین از حلقهٔ هندلر به تسکِ پس‌زمینه با ریتم و retry، `NO_INLINE_KEYBOARD` در هفت نقطه، رمزنگاریِ `platform_card_number`) + ۳ گیتِ دیپلوی (healthcheck رویِ `/health`، `mem_limit: 1g` با MEASURED ۲۰۸MiB، قفلِ دیتابیسِ ضدِ دو-نسخه‌ایِ polling). |

سه ابزارِ دائمیِ تازه: `scripts/check_callbacks.py` (گیتِ تازهٔ `check_gates`: هر `callback_data`
باید مصرف‌کننده داشته باشد — امروز ۳۰۶ شکل، همه OK) و `scripts/check_text_hygiene.py` (گیتِ پنجم:
نویسهٔ بیگانهٔ سیریلیک/CJK/هانجی در خطِ فارسی)، `app/bots/common/error_handler.py`
(آخرینِ زنجیر: traceback در لاگ + توستِ دیدنی به‌جایِ سکوت برایِ هر هندلرِ شکست‌خورده) و
`app/bots/common/keyboard_utils.py`. تستِ تازه: `test_p24_dead_buttons_and_scope.py` (۱۱ مورد).

**تست‌هایِ قدیمیِ هم‌راستاشده با تغییرِ عمدی:** `test_customer_keyboard_layout.py` و
`test_customer_menu_and_prompts.py` — انتظارِ «دو دکمه در مودِ مشاوره» را با انتظارِ جدید
(«هیچ دکمهٔ بی‌کاربری در منو نماند») عوض کردند. هیچ تستِ دیگری تغییرِ انتظاری نداد.

**عددِ MEASUREDِ این پاس:** ۹۹/۹۹ فایل · ۶۴۸ تست · صفر fail (بیس‌لاینِ P23 = ۹۸/۶۳۷)، پنج گیت +
`ruff` تمیز، `alembic heads` = `c4f8a2d6b9e1`، زنجیرهٔ ممیزیِ دیتابیسِ توسعه سالم، و دو سنجشِ
دیپلوی: نسخهٔ دومِ اپ قفلِ polling را **نگرفت** و `bot` با `healthcheck`ِ تازه `healthy` بالا آمد.
جزئیات و اجرایِ باطل‌شدهٔ اول (قفلِ TRUNCATE/polling با رباتِ روشن) در `TEST_RESULTS.md` §۱۴.

**آمادهٔ دیپلوی؟** بله — چک‌لیستِ §۹ِ `PRODUCTION_DEPLOYMENT_GUIDE.md` به ۱۲ بند رسید (سه بندش
مالِ همین پاس: گیتِ چهارم، تک‌نسخه‌بودنِ `bot`، و `docker compose ps` → `healthy`). تنها پیش‌نیازِ
بیرونیِ باقی‌مانده، «قالبِ لینکِ پرداختِ بله‌پی» است که از برگهٔ «اطلاعات اتصالِ وب‌سرویسِ» بله
درمی‌آید (§P23). ← این پیش‌نیاز در **P25** افتاد: پیش‌فرضِ مستندِ بله داخلِ کد نشست (§۱۸).

## ۱۸) پ۲۵ — بله‌پی از ریشه، حذفِ «مبلغ ثابت»، و بهینه‌سازیِ مسیرِ پرداخت

جزئیات در `docs/changelog-p25.md`.

| خواسته | نتیجه |
|---|---|
| «دکمه پرداخت بله‌پی در پنل کاربر و در ربات اصلی/خریدِ اعتبار هنوز کار نمی‌کند» | از لاگِ زنده (۱۳:۰۲:۴۸ و ۱۳:۰۴:۳۳) و `payment_event_logs` (شش `createInvoiceLink` با `ok`): بله سالم بود؛ **میزبانِ آدرس** همان متنِ نمونهٔ داکیومنت (`YOUR_BALE_PAYMENT_BASE_URL`) بود و تلگرام «Wrong HTTP URL» می‌داد. رفع: `DEFAULT_PAY_LINK_TEMPLATE = https://bale.ai/pay/{invoice_id}` از سندِ کاربر + `usable_link_template()` (ردِ میزبانِ جعلی در پنل و نادیده‌گرفتنِ مقدارِ خراب در اجرا) + حذفِ «قالب» از علت‌هایِ آماده‌نبودنِ بله ⇒ با همان دیتابیسِ کاربر دکمه کار می‌کند و لازم نیست چیزی را پاک کند |
| «هرجا لازمه اصلاح کن» | پرداختِ بی‌ارسال دیگر نمی‌ماند: در `panel.py` و `payments.py` خطایِ ارسال ⇒ باطل‌کردنِ ردیفِ پرداخت (`reject_payment` / `mark_link_failed` با `P_FAILED` که بی‌مصرف بود) + پیامِ صادقانه. کرشِ فهرستِ کدهایِ تخفیف (`'str' object has no attribute 'value'`) رفع شد و بازرسیِ همان الگو در کل `app/` نشان داد دیگری نمانده است |
| «کد تخفیف مبلغ ثابت را از پنلِ ادمین حذف کن» | گزینه، کیبورد، مرحلهٔ FSM و پرسشِ «نوع تخفیف» حذف؛ هر کدِ تازه `percent` است و ورودیِ >۱۰۰ رد می‌شود. داده و `DiscountType.FIXED` و کمپین‌هایِ فروشگاه دست‌نخورده‌اند؛ کدهایِ قدیمی با برچسبِ «(قدیمی)» نمایش داده و همچنان مصرف می‌شوند؛ `discount_type:fixedِ` کهنه توست می‌گیرد نه دکمهٔ مرده |
| «یک بهینه‌سازیِ کلیِ سخت‌افزاری و نرم‌افزاری» | نرم‌افزار: sessionِ مشترکِ aiohttp در بله (به‌جایِ هر درخواست یکی تازه؛ `limit=10`, `ttl_dns_cache=300`، دورانداختنِ کانکتور در خطایِ شبکه، بستن در shutdown) · long-pollِ `getUpdates` از ۱۰ ⇒ ۲۵ ثانیه (≈۷٬۹۰۰ → ≈۳٬۳۰۰ دور در روز، از حسابِ پیکربندی) · `order_for_handling()` که `pre_checkout_query`ها را اول پردازش می‌کند (سقفِ ۱۰ ثانیه‌ایِ بله). دیتابیس: `log_min_duration_statement=250ms` و `random_page_cost=1.1` در compose (از `pg_settings` تأیید شد)؛ بازرسیِ ایندکسِ مسیرِ پرداخت انجام شد و کمبودی نبود ⇒ مایگریشن لازم نشد |

**تست‌هایِ هم‌راستاشده با تغییرِ عمدی:** `test_p18_bale_credentials` (۴ علت ⇒ ۳، و با خاموشیِ
فروشگاه ۵ ⇒ ۴)، `test_p23_bale_payment_link` (موردِ ۱ و ۳: پیش‌فرضِ لینک و «نمایش = توانایی»)،
`test_admin_pricing` (جریانِ کدِ تخفیف بدونِ مرحلهٔ نوع)، `test_payments_w3w4` (بستنِ session در
پایان). تستِ تازه: `test_p25_bale_link_and_discounts.py` (۸ مورد).

## ۱۹) پ۲۶ — لینکِ پرداختِ بله رویِ `ble.ir`، متنِ مشاوره‌ای و زمان‌بندیِ آماده

جزئیات در `docs/changelog-p26.md`. P25 نصفه‌راست بود: «لینک نساز و نمی‌میرد» را درست کرد، ولی
شکلِ آدرس را از سندِ کاربر پذیرفت؛ بازرسیِ خودِ سندِ بله و پروبِ زنده آن را رد کرد.

| خواسته | نتیجه |
|---|---|
| «لینکِ پرداختِ بله‌پی ۴۰۴ می‌دهد» | MEASURED: `bale.ai/pay/<id>` ⇒ ۴۰۴، `ble.ir/pay/abc` ⇒ ۴۰۴، `ble.ir/smartbusinessbot` ⇒ ۲۰۰، `ble.ir/<ربات>?start=pay-TEST` ⇒ ۲۰۰ (رباتِ ناموجود ⇒ ۴۰۴). سندِ رسمیِ بله هم `createInvoiceLink` را «شناسهٔ پرداختِ **مینی‌اپ**» می‌داند که فقط با `openInvoice` مصرف می‌شود ⇒ هیچ آدرسِ پرداختی وجود ندارد. طراحیِ تازه: لینک = چتِ رباتِ پرداخت با `?start=<payload>`، و ربات در آن چت `sendInvoice` می‌فرستد؛ همان `payload` کلیدِ تطبیقِ `successful_payment` است، پس هیچ جدولِ واسطِ تازه‌ای لازم نشد |
| «تنظیماتِ رباتِ بله‌پی را در رباتِ اصلی و پنلِ مدیران درست بچین» | فیلد «🔗 قالبِ لینک» از پنل حذف شد (ستونِ DB می‌ماند، هیچ کدی نمی‌خواندش)؛ برچسبِ توکنِ ربات حالا «رباتِ پرداخت: @username» را از `getMe` نشان می‌دهد؛ توضیحِ توکنِ درگاه به «پول در کیف‌پولِ چه کسی می‌نشیند» اصلاح شد؛ صفحهٔ «💳 پرداختِ آنلاینِ سفارش‌ها» مسیرِ چهارمرحله‌ایِ مشتری را می‌گوید؛ «🧪 آزمایشِ بله‌پی» هر دو پیش‌نیاز را جدا می‌سنجد؛ و قاعدهٔ B11 («نمایش = توانایی») با علتِ تازهٔ `pay_bot_username` به نامِ کاربری هم کشیده شد — یکِ تستِ رگرسیونِ قدیمی (P18) همان را گرفت |
| بازرسیِ خودِ طراحیِ P26 (بدونِ درخواستِ کاربر) | لینک ابتدا «رباتِ بله‌یِ خودِ فروشگاه، وگرنه پلتفرم» انتخاب می‌شد؛ بازرسیِ `app/main.py:326/733` و `bale_bot_service` نشان داد رباتِ بلهٔ فروشگاه **فقط فرستندنِ پیام** است و آپدیت‌هایش هیچ‌جا خوانده نمی‌شود ⇒ `/start` در آن چت هرگز به ما نمی‌رسید و لینک مرده می‌شد (همان باگِ گزارش‌شده، در لباسِ تازه). لینک به رباتِ پلتفرم قفل شد و `shop_bot` از امضایِ `pay_link_*` بیرون رفت |
| «متنِ خوشامدِ حالتِ مشاوره‌ای را عوض کن، ما دکمه نداریم» | `SHOP_WELCOME_CONSULTATION` بدونِ هیچ وعدهٔ دکمه بازنویسی شد؛ `shop_welcome_consultation(support_enabled)` فقط وقتی «📞 پشتیبانی» روشن است همان یک دکمه را معرفی می‌کند |
| «استفاده از پیامِ زمان‌بندی را راحت‌تر کن» | «کی ارسال بشه؟» پنج گزینهٔ آماده گرفت (+۱س، +۳س، امشب ۲۱:۰۰، فردا ۱۰:۰۰، فردا ۱۸:۰۰) + «✍️ ساعتِ دلخواه» + «❌ لغو»؛ هر دکمه به همان رشته‌ای نگاشت می‌شود که `parse_when` می‌فهمد (`SCHEDULE_PRESETS`) و هندلرِ دکمه/متن یکِ تابعِ مشترک `_store_scheduled_broadcast` را صدا می‌زنند. «❌ لغو» قبلاً در این صفحه بی‌جواب می‌ماند (StateFilter فقط مرحلهٔ پیش‌نمایش را داشت) |

**تست:** `test_p26_bale_handoff_and_ux.py` (۶ مورد: `/start`ِ معتبر ⇒ `sendInvoice` با مبلغِ ریالیِ
درست و همان payload، payloadِ ناشناس/تسویه‌شده ⇒ هیچ صورتحسابی نه، خوشامدِ مشاوره‌ای، نگاشتِ
پیش‌فرض‌ها به `parse_when`، صفحهٔ تنظیماتِ ادمین، و «لینک به رباتِ polled می‌رود نه رباتِ send-only»).
`test_p25_bale_link_and_discounts.py` بازنویسی
شد (۸ مورد، از جمله «بدونِ رباتِ شناخته‌شده ⇒ نه دکمه، نه ردیف»). `test_p23_bale_payment_link.py`
**حذف** شد: موضوعش (تبدیلِ `invoice_id` به آدرسِ وب) از بین رفته و دو تضمینِ زنده‌اش (گاردِ
کیبوردِ کهنه، تبدیلِ تومان→ریال) به فایلِ P25 منتقل شد. `test_p18_bale_credentials.py`،
`test_bale_pay_for_orders.py`، `test_shopping_cart.py` و `test_campaign_checkout.py` با
نامِ کاربریِ رباتِ پرداخت (از `remember_pay_bot_username`، بی‌شبکه) هم‌راستا شدند.

## ۲۰) پ۲۷ — فاکتورِ یکدست و مرتب، تاییدِ رسید با یکِ کلیک

جزئیات در `docs/changelog-p27.md`. دو باگِ گزارش‌شدهٔ کاربر، بدونِ دست‌زدنِ بقیهٔ موارد.

| خواسته | نتیجه |
|---|---|
| «صاحبِ انلاین‌شاپ باید دو بار رویِ تاییدِ رسید کلیک کند» | ریشه از لاگِ زنده: `TelegramBadRequest: query is too old…` ⇒ در `rcpt_ok` بعد از `approve_payment` و `commit()`، هر شکستی (پاسخِ دیرهنگامِ کالبک، یا خطایِ فاکتور/اعلان) هندلر را می‌کشت **بعد ازِ ثبتِ تایید** و پیامِ فروشگاه‌دار با دکمهٔ «✅ تایید» می‌ماند؛ کلیکِ دوم (ایدبمپوتنت) فقط پیام را عوض می‌کرد. رفع: `callback.answer()` در `try/except`، کارهایِ جانبی به `_after_approval_notify()` پشتِ `try/except Exception`، و ویرایشِ پیامِ فروشگاه‌دار **همیشه** اجرا می‌شود. ضمناً `_edit_owner_message` پیامِ **سند** را هم مثلِ عکس با `edit_caption` به‌روز می‌کند (قبلاً برایِ رسیدِ فایلی `edit_text` را امتحان می‌کرد، تلگرام ردش می‌کرد و پیامِ تازه‌ای پایینِ چت می‌رفت درحالی‌که کیبوردِ کهنه رویِ پیامِ اصلی می‌ماند) |
| «متن‌هایِ فارسی و انگلیسی با هم قاطی نشه + فاکتور زیباتر» | با کاوشِ زنده رویِ همان کتابخانه‌ها (`arabic_reshaper` + `get_display`) ثابت شد رشته‌یِ «فاکتور INV-3-… · ۱۴۰۵/۰۸/۱۱» با ترتیبِ به‌هم‌ریخته و جداکننده‌هایِ تاریخِ جداافتاده رستر می‌شود. قاعدهٔ چیدنِ تازه در `invoice_service`: هر رشته یا کاملاً فارسی است یا یکِ برچسب + یکِ مقدار ⇒ شمارهٔ فاکتور و تاریخ در دو خطِ جدا، `invoice_phone_display` با فرمتِ ملی و ارقامِ فارسی، `customer` فقط نام (یوزرنیم کلید/خطِ جدا؛ قبلاً شماره دو بار در فاکتور می‌آمد)، واحدِ پول در سرستون، تخفیف بدونِ `-`ِ لاتین (فقط رنگ)، «دیجیتال» با گیومه، پنلِ نرمِ مشخصات با قدراِسنجیِ `dry_run`، ردیف‌هایِ خط‌زیردار، برچسبِ رنگیِ وضعیت، پاورقیِ چسبان. کپشنِ چت هم یکدستِ فارسی شد |

**تست:** `test_p27_invoice_persian_layout.py` (۶ مورد، بی‌دیتابیس: هیچ خطِ رسترشده نباید هم‌زمان حرفِ لاتین و رقمِ فارسی داشته باشد، پرانتزِ لاتین ممنوع، شماره/تاریخ جدا، شکل‌هایِ لبه) و `test_p27_receipt_one_click.py` (۴ مورد: پاسخِ دیرهنگامِ کالبک، شکستِ فاکتور، رسیدِ سندی با `edit_caption`، و رگرسیونِ یک‌کلیک/دابل‌تپ). برایِ اثباتِ این‌که تست‌ها باگ را می‌گیرند، هر دو رفع موقتاً برگردانده شد و تست‌ها همان‌جا fail کردند (`بدونِ ویرایشِ پیام، دکمهٔ «✅ تایید» می‌ماند…` و `edited_captions == []`). `harness.py` دو افزودنیِ بی‌خطر گرفت: `fail_answer_callbacks` و ثبتِ `EditMessageCaption` در `edited_captions`.

**عددِ این اجرا:** ۱۰۲/۱۰۲ فایل · ۶۶۶ تست · صفر fail · پنج گیت OK (۳۱۰ شکلِ `callback_data`، بدونِ دکمهٔ تازه) · `ruff` تمیز · تک‌head · زنجیرهٔ ممیزی ۷/۷ · ۷/۷ فایلِ دست‌خورده در ایمیج == دیسک · `bot` healthy و polling با صفر خطا. دیدنِ چشمیِ PDF و تراکنشِ واقعیِ بله‌پی هنوز **NOT RUN**.

## ۲۱) پ۲۸ — راهنمایِ masterِ دیپلوی + PDFِ فارسیِ مستندات

جزئیات در `docs/deployment-playbook.md` (و همان‌جا `docs/deployment-playbook.pdf`، ۱۵ صفحه).

| خواسته | نتیجه |
|---|---|
| «یک راهنمایِ دیپلوی بنویس؛ سخت‌افزار و مدلِ سرور برایِ تعدادهایِ مختلف» | §۳ فایلِ تازه: پنج لایه از «۲ هسته/۲GB/۲۰GB ≤ ~۲۰ فروشگاه‌دار» تا «۱۶ هسته/۳۲GB برایِ ~۱۰۰۰ رویدادِ هم‌زمان» — هر سطر با برچسبِ MEASURED/EXTRAPOLATED/ESTIMATED و عددِ منبع‌دار (`HARDWARE_REQUIREMENTS_AND_CAPACITY_PLAN.md` + `SCALABILITY_AND_LOAD_TEST_REPORT.md`: بامِ ~۱۴۵ پیام/s، ~۳۰۶ RPSِ کیف‌پول، ~۲٬۰۰۰ TPSِ pgbench، سقوطِ ۱۳۶⇒۴۸ RPS با `overflow=30`). مصرفِ امروزِ همین نصب هم اندازه‌گیری و ثبت شد: `bot` ۲۵۶MiB، `db` ~۱٫۲GiB، ایمیج ۳۲۴MB، دیتابیس ۱۴MB/۴۶ جدول. راهنمایِ خرید (NVMe، هستهٔ اختصاصی، IP سالم، ایران یا خارج) هم اضافه شد |
| «تعداد APIهایِ هوش مصنوعی برایِ تعداد کاربرانِ مختلف» | §۴: سه سقفِ مستقل (سِمافورِ ۴۰ِ in-process ⇒ ~۸۰۰ درخواست/دقیقه در هر پروسه، سقفِ RPMِ ارائه‌دهنده، سقفِ هر فروشگاه ۲۰/۱۰دقیقه و هر مشتری ۱۵ پیام/دقیقه) + جدولِ مقیاس→تعدادِ کلید→توکن/روز→خرجِ ارائه‌دهنده→خرجی که از فروشگاه‌دار گرفته می‌شود (۲۰/۱۰۰/۳۰۰/۱۰۰۰ فروشگاه ⇒ ۲/۲–۳/۳–۴/۵–۶ کلید، ~۲ تا ~۹۶ میلیون توکن در روز) + «۱۰۰۰ پیامِ مشتری ≈ ۴۰٬۰۰۰ تا ۷۵٬۰۰۰ تومان» با ضریبِ سودِ ۵٫۰ |
| «آموزشِ دیپلوی» | §۶ تا §۹: جدولِ .env (با «اگر عوض نکنی چه می‌شود»)، نصبِ گام‌به‌گام رویِ VPSِ اوبونتو، ترتیبِ واقعیِ `entrypoint.sh`، بکاپِ cron با ۱۴ نسخه و **تمرینِ بازگردانی**، آپدیتِ کد، و «چرا `--scale bot=2` کمکی نمی‌کند» (قفلِ advisoryِ polling و کش‌هایِ in-process) |
| «نکاتی که نمی‌دانم یا بعداً سؤالم می‌شود» | §۱۴: پانزده سوالِ عملی (گم‌شدنِ `ENCRYPTION_KEY`، buildِ فراموش‌شده به‌خاطرِ نبودِ volume mount، پریدنِ FSM موقعِ ری‌استارت، ترتیبِ عیب‌یابیِ کندی، چرا تست رویِ سرورِ تولیدی ممنوع است، retentionِ ۹۰ روزه، انقضایِ اعتبار، آپگریدِ نسخهٔ اصلیِ PostgreSQL، ساعتِ کران، لاگرُتیشن، NOT RUNها) + §۱۵ «هر عدد از کجا آمد» و §۱۲ سه ادعایِ کهنه در راهنماهایِ قبلی (`--scale` مجاز، «جاب در هر نسخه»، «اعتبارِ شارژ ۱ ماه» در برابرِ ۱۲ ماهِ کد) |
| «اگر می‌توانی PDF بساز» | `scripts/build_docs_pdf.py`: مارکداونِ فارسی ← PDFِ A4ِ راست‌به‌چپ با همان Vazirmatnِ باندل‌شده (سرصفحه، جدولِ ستون‌بندی‌شده با قدراِسنجیِ `dry_run`، بلوکِ کدِ چپ‌چین، فوترِ شماره‌صفحه). دلیلِ ساختنش: در این ایمیج و میزبان هیچ رندرکنندهٔ PDF نیست (`pdftoppm`/`ghostscript`/`pymupdf`/`pypdf` همه نیستند) و `docs/` هم عمداً داخلِ ایمیج نمی‌رود؛ راهنما داخلِ فایلِ سه‌دستورِ `docker compose cp`… نوشته شده. خروجیِ نهایی: ۱۵ صفحه، ۶۵KB، فونتِ امبد‌شده، **صفر هشدارِ گلیفِ گم‌شده** |

**تست:** `test_p28_docs_pdf_builder.py` (۳ مورد: PDFِ معتبرِ %PDF/%%EOF با فونتِ امبد، نبودِ «missing glyphs»، درست‌بودنِ فیلترِ ایموجی/پیکان؛ موردِ سوم رویِ خودِ راهنما اگر `docs/` در دسترس باشد وگرنه SKIPPED با دلیل).

## ۲۲) پ۲۹ — بهینه‌سازیِ مقیاس تا ۵۰۰ فروشگاهِ هم‌زمان (بدونِ دست‌زدن به قابلیت)

جزئیات در `docs/changelog-p29.md`؛ عددهایِ مقیاس در `SCALABILITY_AND_LOAD_TEST_REPORT.md` §۱۰؛ تنظیماتِ دیپلوی در `docs/deployment-playbook.md` §۵-الف.

| خواسته | نتیجه |
|---|---|
| «اول ثابت کن، بعد بهینه کن» | `scripts/scale_probe.py` ساخته شد: رویِ `kasbokar_test`، بدونِ هیچ درخواستِ واقعی به تلگرام/AI، با N = ۱/۵۰/۲۰۰/۵۰۰ چهار چیز را می‌سنجد — راه‌اندازی (زمان، statement، **اوجِ هم‌زمانیِ درخواست‌ها**، تسک، RSS، fd)، رمِ خودِ N اتصال، مسیرِ یکِ پیام (statement/پیام + p50/p95/RPS در همزمانیِ ۲۵/۱۰۰/۳۰۰)، و یکِ پاسِ کاملِ جاب (سرد و گرم). بیس‌لاینِ ۵۰۰ فروشگاه: اوجِ هم‌زمانی **۵۰۰** `delete_webhook` در یکِ لحظه، حالتِ webhook **۵٫۰ ثانیه برایِ ۲۰ ربات** (۵۰۰تا ≈ ۱۲۵ ثانیه)، پاسِ گرمِ جاب **۵۲۸** statement که ۵۰۰تاش `SELECT shop_bots` برایِ ربات‌هایِ *بی‌نوبت* بود، و **۰٫۴–۰٫۷MB رم به‌ازایِ هر اتصال** (۲۰۰–۳۳۰MB در ۵۰۰) |
| «به قابلیت‌ها دست نزن» | هیچ متن، دکمه، جریانِ پول یا پاسخِ ربات عوض نشد؛ مسیرِ پیام همچنان **۱۲٫۰** statement به‌ازایِ هر پیام دارد (در هر چهار اندازه — یعنی اصلاً با N رشد نمی‌کرد و هنوز هم نمی‌کند) و بامِ ~۱۲۰ پیام/s در برابرِ بارِ واقعیِ ۵۰۰ فروشگاه (~۸ پیام/s با فرضِ یکِ پیام/دقیقه) ~۱۵ برابرِ سرِ‌باز دارد |
| رفعِ ۱ — راه‌اندازی/خاموش‌شدنِ کرید‌شده | `BOT_REGISTER_CONCURRENCY=24` + یکِ `asyncio.Semaphore` در `ShopBotManager`: `load_all` با `gather` و همان سقف، و `delete_webhook` اولِ هر تسکِ polling داخلِ همان قفل ⇒ اوجِ هم‌زمانی **۵۰۰ ← ۲۴**، حالتِ webhook **۵٫۰ ← ۰٫۲۵ ثانیه** برایِ ۲۰ ربات. هزینهٔ عمدی: رسیدنِ همهٔ ۵۰۰ ربات به اولین پول ۰٫۲۷ ← ۵٫۴ ثانیه (رشِ پله‌ای به‌جایِ گلهٔ ۵۰۰تاییِ TLS/API که تلگرام از یکِ IP معمولاً ۴۲۹ می‌کند). `shutdown()` تازه: بستنِ اتصال‌ها هم کرید‌شده، چون ترتیبی یعنی ۵۰۰×RTT > مهلتِ ۱۰ ثانیهٔ داکر ⇒ **هر دیپلوی با SIGKILL**؛ با `stop_grace_period: 30s` و `ulimits.nofile: 65536` (۵۰۰ سوکتِ باز) و `BOT_MEM_LIMIT` جمع شد |
| رفعِ ۲ — جاب‌ها بدونِ N+1 | `sync_all` ردیفِ ربات‌ها را در یکِ `WHERE id IN (…)` می‌خواند (به‌جایِ یکِ `session.get` به‌ازایِ هر رباتِ ثبت‌شده، هر ۳۰ دقیقه) ⇒ پاسِ گرم **۵۲۸ ← ۳۰ statement (−۹۴٪)** و زمانِ پاس ۰٫۵۴ ← ۰٫۱۲ ثانیه. در گزارشِ دوره‌ای/شبانه هم مالک‌ها دسته‌ای خوانده می‌شوند |
| باگِ واقعی که در همین مسیر گرفته شد | گزارشِ شبانه برایِ خطِ «طلبِ کمیسیونِ وصول‌نشده» از `commission_receivable_service.summary(session)` استفاده می‌کرد — تابعی که جمعِ **سراسریِ پنلِ ادمین** است و داخلِ حلقهٔ *هر فروشگاه* صدا زده می‌شد ⇒ (۱) با ۵۰۰ فروشگاه یکِ aggregate رویِ کلِ جدول ۵۰۰ بار در یکِ پاس (O(N²) با رشدِ داده)، (۲) هر فروشگاه‌دار در گزارشِ خصوصیِ خودش **بدهیِ همهٔ فروشگاه‌ها** را می‌دید. حالا `open_totals_by_owner()` در یکِ کوئریِ گروهی، بدهیِ همان فروشگاه؛ فروشگاهِ بی‌بدهی دیگر آن خط را نمی‌بیند |
| چه چیزی **انجام نشد** (و چرا) | محتوایِ آمارِ گزارش هنوز ~۱۰ کوئری/فروشگاه دارد (دسته‌ای‌کردنش ریسکِ عوض‌شدنِ عددِ پولیِ داخلِ گزارش داشت؛ در مقیاسِ ۵۰۰ ≈ ۲٫۸ statement/ثانیه)؛ تکراری‌هایِ مسیرِ پیام (دو خواندنِ مشتری/مالک، دو UPDATEِ کیف‌پول، دو بار `admin_settings`) دست‌نخورده ماند چون هندلرِ اصلیِ چت است و باید تستِ اختصاصیِ خودش را داشته باشد — هر دو در `REMAINING_ISSUES.md` §P29 با طرحِ رفع ثبت شده. ایندکس/مایگریشنِ تازه **نلزم** بود: کوئری‌هایِ حذف‌شده همه با کلیدِ اصلی بودند؛ مشکل تعداد بود نه پلنِ اجرا |

**تست:** `test_p29_bounded_bot_startup.py` (۵ مورد، بی‌دیتابیس: اوجِ هم‌زمانی ≤ سقف *و* > ۱، ثبتِ کاملِ همهٔ ربات‌ها با یکِ تسک به‌ازایِ هر فروشگاه، همان کرید در حالتِ webhook، خطایِ `delete_webhook` ربات را از پولینگ نمی‌اندازد، سقفِ ۰ = یکی‌یکی نه بن‌بست، و `shutdown()` همه را می‌بندد) و `test_p29_job_query_bounds.py` (۳ مورد با دیتابیس: ۶ ربات ⇒ **یک** `SELECT shop_bots`، فقط رباتِ نوبت‌دار برچسبِ بازرسی می‌گیرد، گزارشِ شبانه بدهیِ *همان* فروشگاه را نشان می‌دهد و عددِ سراسری در هیچ گزارشی نیست). هر دو رفع موقتاً به کدِ کهنه برگردانده شد و تست‌ها همان‌جا fail شدند: `همزمانی از سقف (24) گذشت: 72` و `۶ ربات ⇒ 6 SELECT از shop_bots`.

**عددِ این اجرا:** ۱۰۵/۱۰۵ فایل · ۶۷۶ تست · صفر fail · پنج گیت OK (۲۶۴ فایل، ۳۱۰ شکلِ `callback_data`، بدونِ نشتِ نویسه) · `ruff --select F,E9` رویِ `app/` تمیز · alembic تک‌head `c4f8a2d6b9e1` (بدونِ مایگریشنِ تازه) · زنجیرهٔ ممیزی ۷/۷ · ایمیج == دیسک ۹/۹. **NOT RUN:** RTTِ واقعیِ تلگرام (DNSِ این محیط `api.telegram.org` را به `10.10.34.36` حل می‌کند و اتصال ممکن نیست ⇒ همهٔ زمان‌ها با RTTِ شبیه‌سازی‌شدهٔ ۲۵۰ms)، ۵۰۰ سوکتِ TLS واقعی، رمِ زیرِ بار، و بارِ واقعی رویِ سرورِ مقصد. *(رجوع: در همان روز، در اجرایِ دوباره دسترسی برقرار شد و `getMe` واقعی ۸۲۷ms جواب داد — §۲۳.)*

## ۲۳) ثبتِ پرداختِ واقعیِ بله‌پی و باطل‌کردنِ دو ادعایِ کهنه (۱۴۰۵-۰۸-۱۲ = ۲۰۲۶-۱۱-۰۳)

| خواسته | نتیجه |
|---|---|
| «متن‌هایی که می‌گویند تراکنشِ واقعیِ بله‌پی هنوز تست نشده را به حالتِ عادی برگردان» | بازرسیِ `payment_event_logs` و `order_payments` در دیتابیسِ **توسعه** نشان داد زنجیرهٔ `لینک → چتِ بله → sendInvoice → pre_checkout_query → successful_payment → inquire_result=success` در ۱۴۰۵-۰۸-۱۱ با **۱٬۰۰۰ تومانِ واقعی** اجرا شده و سفارش با `decided_by=gateway` به `paid` رسیده (پاسخِ pre_checkout در ۲۱۴ms؛ جدولِ کاملِ زمان‌ها در `TEST_RESULTS.md` §۱۹). جملة «هیچ درخواستِ واقعی به APIِ بله زده نشد» هم باطل است: ۱٬۹۲۰ رویدادِ `out` و ۷ رویدادِ `in`. متن‌هایِ جاریِ مستندات و یکِ پیامِ پنل اصلاح شدند: `AGENTS.md` §۵، `docs/HANDOFF-P29.md` §۱ و §۶ و §۷، `REMAINING_ISSUES.md` §P0/P1-۲ و §P23-۳ و §P25-۱ و §P26-۱، `docs/deployment-playbook.md` §۱۰ و §۱۳ و §۱۴ و §۱۵، `docs/testing-guide.md` §ه، `docs/PROJECT_COMPLETION.md` §۱ و §۷، `docs/bot-functional-overview-fa.txt` §۱۲، کامنتِ `app/services/bale_service.py` و `app/bots/main_bot/texts.py` (صفحهٔ «توکنِ درگاه») |
| مرزِ درستِ «هنوز تست‌نشده» (حذف نشد؛ صریح ماند) | سه NOT RUN: **شارژِ کیف‌پول** از همین مسیر (صورتحسابش ۱۷:۵۱ با `sendInvoice` موفق ساخته شد ولی هیچ `pre_checkout_query` برایش نیامد؛ دو ردیفِ `payments` با `method=bale_pay` و `purpose=wallet_topup` هنوز `pending`) · **زرین‌پالِ واقعی** (صفر ردیف) · **گفت‌وگو/پرداخت در رباتِ بلهٔ خودِ فروشگاه** (P19؛ آن ربات `getUpdates` نمی‌خواند) |
| ادعایِ کهنهٔ «این شبکه به تلگرام نمی‌رسد» | در `docker compose up -d --build` امروز: `api.telegram.org` → `149.154.166.110`، `getMe` = **۸۲۷ms (MEASURED)**، `RestartCount=0`، صفر `TelegramNetworkError` در لاگِ ۱۰ دقیقه ⇒ جایِ ادعایِ مطلق، قاعدهٔ «اول با یکِ `getMe` زمان‌دار دست‌سنجی کن» در `AGENTS.md` §۵ نشست. عددهایِ `scale_probe` همچنان با RTTِ **شبیه‌سازی‌شدهٔ** ۲۵۰ms‌اند و باید دوباره سنجیده شوند |
| چه چیزی دست‌نخورده ماند | ردیف‌هایِ تاریخیِ `docs/changelog-p24..p27.md` و §۱۱ تا §۱۸ِ `TEST_RESULTS.md` (رکوردِ همان روزها هستند؛ بازنویسی‌شان = تحریفِ تاریخ). فقط `docs/changelog-phase4.md` §۶-۶ که فعلِ «همچنان» داشت یکِ خطِ تصحیحِ زمانِ فعلی گرفت. `docs/spec/MASTER_PROMPT_P14.md` (بایگانیِ دستورِ فاز) دست‌نخورده |

**گیت‌ها پس ازِ ویرایش:** پنج گیت OK (۲۶۴ فایل · ۳۱۰ شکلِ `callback_data` · بدونِ نویسهٔ بیگانه) · `ruff --select F,E9` رویِ `app/` تمیز · اسکنِ دستیِ نشتِ لاتین داخلِ فارسی رویِ ۱۰۶ خطِ افزوده: ۲۸ مورد، همه‌شان مخفف/شناسه با نشانهٔ جدا (`RTTِ`، `۸۲۷ms`، `MEASURED،`، `AI،`) و هیچ‌کدام لاتینِ داخلِ کلمهٔ فارسی نبود. بدونِ مایگریشن، بدونِ دکمهٔ تازه، بدونِ تغییرِ تست.

## ۲۴) پ۳۰ — چهار خواسته از یکِ نشستِ ده‌سوالی (۱۴۰۵-۰۸-۱۲ = ۲۰۲۶-۱۱-۰۴)

جزئیات کامل در `docs/changelog-p30.md`.

| خواسته | نتیجه |
|---|---|
| «ده محصولِ اکسلی را ربات نمی‌گوید؛ ریشه‌اش را پیدا و رفع کن» | ریشه نه ایمپورت بود نه فیلترِ کاتالوگ: `shop_bots.ai_instructions` همان فروشگاه می‌گفت «تو فقط مداد فروشی…» و در `ai_context.py` **جایِ** دستورالعملِ پیش‌فرض را می‌گرفت. با داده‌هایِ واقعیِ همان فروشگاه سنجیده شد: ۱۲ محصول در دیتابیس ⇒ ۱۲ خطِ فهرست در پرامپت (یعنی فهرست هرگز حذف نمی‌شد؛ مدل انکار می‌کرد). رفع: پیش‌فرض می‌ماند + جملهٔ فروشگاه بعدش می‌آید + سرتیتر صریح می‌شود «این فهرست تمامِ محصولاتِ ثبت‌شده است». تست: `test_p30_catalog_instruction_conflict.py` |
| «درآمد از کمیسیون و از API را در آمار تفکیک کن» | `get_platform_stats` یکِ aggregateِ تازه گرفت و «📊 آمار سراسری» بخشِ «درآمد به تفکیکِ منبع» دارد (کمیسیون · فروشِ اعتبارِ AI · جمعِ دو، بدونِ دوبارشماری، با خالص‌سازیِ settle/reverse). تست: `test_p30_platform_revenue_split.py` |
| «دکمه‌ای در پنلِ ادمین: ادامهٔ ثبتِ سفارش با اعتبارِ صفر + گزینهٔ سقفِ بدهی؛ بعد از سقف دکمه‌ها از کار بیفتد» | سوییچِ سراسری + «سقفِ بدهیِ کمیسیون» (۰ = بی‌سقف، سقفِ ورودیِ پنل ۵۰۰٬۰۰۰٬۰۰۰) با مایگریشنِ افزودنی `e1b7c9d4a6f2` و سه وضعیتِ `order_access_service` (`ALLOWED` / `NO_CREDIT` / `DEBT_CEILING`). در `DEBT_CEILING` چت ادامه می‌یابد و فقط «🧾 نهایی‌کردنِ سفارش» و انتخابِ روشِ پرداخت بسته می‌شوند؛ بدهی از `commission_receivables` باز، per-shop خوانده می‌شود. تست: `test_p30_zero_credit_orders.py` (۷ مورد) |
| «دکمه‌ای که وضعیتِ همزمانی کاربران در طولِ زمان و گزارشِ عملکرد ربات را با قابلیت‌های مختلف نشان دهد» | «📈 وضعیتِ همزمانی و عملکرد» با دو بازه (۲۴ ساعت/دانهٔ ۱۰ دقیقه، ۷ روز/دانهٔ یک ساعت) در `perf_report_service` — سه aggregate، بدونِ حلقهٔ per-shop؛ نوارِ متنی + بیشینه + «همین حالا» + تفکیکِ فراخوانی‌ها به‌ازایِ هر قابلیت + سفارش/مشاوره/پرداخت/رویدادِ درگاه. تست: `test_p30_concurrency_report.py` (۶ مورد) |
| تغییرِ یکِ تستِ قدیمی (قاعدهٔ §۲-۸) | `test_admin_rbac.py`: مجموعهٔ `OPERATOR_VISIBLE_BUTTONS` یکِ عضوِ تازه گرفت، چون آن تست کیبورد را با *برابریِ مجموعه* می‌سنجد. رفتارِ دیگری عوض نشد |

**عددها:** پنج گیت OK · `callback_data` ۳۱۰ ← ۳۱۱ · alembic تک‌head `e1b7c9d4a6f2` · پیش‌فرضِ دو ستونِ تازه `false / 0` ⇒ رفتارِ امروزِ فروشگاه‌ها دست‌نخورده (رویِ دیتابیسِ توسعه اعمال و دیده شد) · سوئیتِ کاملِ همین نشست: **۱۰۹/۱۰۹ فایل · ۶۹۹ تست · صفر fail** (عدد در `TEST_RESULTS.md` §۲۰؛ اجرایِ اول ۱۰۷/۱۰۹ بود و دو failِ آن همان‌جا §۲۰-پ مستند شده). **NOT RUN:** اثرِ مالیِ سوییچِ اعتبارِ صفر رویِ مصرفِ واقعیِ AI (نیازمندِ کلیدِ AI و پولِ خودت).

## ۲۵) پ۳۱ — پرفورمنسِ مسیرِ پیام و گزارش‌ها + برگشتِ مایگریشن (۱۴۰۵-۰۸-۱۲)

| خواسته | نتیجه |
|---|---|
| «پرفورمنس را برایِ تعدادِ زیادِ کاربر بالا ببر» | (۱) حذفِ UPDATEِ تکراریِ موجودی ⇒ در سنجهٔ `scale_probe` هر رویدادِ پولی ۱۲٫۰ ← **۱۱٫۰** statement؛ (۲) کشِ خواندنِ `admin_settings` با باطل‌سازیِ رویداد-محور ⇒ سه خواندن در هر پیام و شش خواندن در هر پاسِ جاب حذف شد؛ (۳) تجمیعِ آمارِ گزارشِ شبانه ⇒ **پنج کوئری مستقل از تعدادِ فروشگاه** با برابریِ عینِ عددها |
| تصحیحِ ادعایِ کهنهٔ خودم | «۱۲ statement برایِ هر پیام» مسیرِ شبیه‌سازی بود؛ مسیرِ واقعیِ هندلر **۳۰** است و همان در `test_p31_message_statement_bounds.py` قفل شد |
| برگشتِ مایگریشن (تست‌نشده تا امروز) | `scripts/check_migration_roundtrip.py`: upgrade ۳٬۲۷۶ms ← `downgrade base` ۲٬۱۵۶ms ← upgrade ۲٬۶۳۷ms، هر سه exit=0، تک‌head، ۴۶ جدول؛ بدونِ دست‌زدن به `kasbokar`/`kasbokar_test`؛ به CI هم اضافه شد |
| CI | دیتابیسِ غلط (سوئیت را در همان اول می‌کشت) → `kasbokar_test`؛ پنج گیت + تک‌head + `ruff --select F,E9` مسدودکننده؛ triggerِ شاخهٔ کاری + `workflow_dispatch`. خودِ CI اجرا نشده ⇒ NOT RUN |
| مسدود تا روشن‌شدنِ VPN/شبکه | Redis برایِ FSM، پوششِ کد، `pip-audit` (`pip download redis` ناموفق بود ⇒ کدِ Redisِ تست‌نشده عمداً نوشته نشد) |
| باقی‌ماندهٔ بدونِ VPN | ۱۱ تا از ۳۰ statement = سه‌خوانیِ `shop_bots`/`shop_owners`/`customers` در سه سشن؛ رفعش پاس‌دادنِ شناسه‌ها بینِ میدل‌ور و تسکِ پاسخ (هدف ~۲۲) |

**سوئیتِ کامل و دو تستِ قدیمی که دست خورد (قاعدهٔ §۲-۸ — رفتارِ محصول عوض نشده، خودِ تست معیوب بود):**
- `test_customer_keyboard_layout.py`: فهرستِ *دقیقِ* دکمه‌هایِ پنلِ ادمینِ عملیاتی را با برابریِ ترتیب‌دار می‌سنجد؛ «📈 وضعیتِ همزمانی و عملکرد» (P30-D) به همان فهرست اضافه شد. این همان چیزی است که تست باید بگوید، پس اصلاحِ تست درست است نه بازگرداندنِ کد.
- `test_nightly_report.py` — **نقصِ واقعیِ همین تست، نه کد:** تیکِ بعدیِ زمان‌بند را با `now + ۳۰ دقیقه` شبیه‌سازی می‌کرد؛ اگر ساعتِ واقعی داخلِ ۳۰ دقیقهٔ آخرِ روزِ UTC باشد (۲۳:۳۰–۲۴:۰۰) آن جمع به روزِ بعد می‌افتد، `today` عوض می‌شود و گزارشِ شبانه دوباره فرستاده می‌شود ⇒ تست فقط در همان پنجره fail می‌شد (دو اجرایِ جدا و تکرارشده در ۲۳:۴۱ UTC، پس flaky نبود). حالا تا مرزِ همان روز clamp می‌شود و هیچ وابستگیِ ساعتی ندارد. منطقِ `report_service` (مقابله با تکرار با `last_nightly_report_date`) دست‌نخورده است.


## ۲۶) پ۳۲ — FSM رویِ دیتابیس، سنجشِ واقعیِ تلگرام و یکِ ضعفِ معماریِ تازه (۱۴۰۵-۰۸-۱۳)

· تلگرام با VPN: `getMe` واقعی **۳۹۹ms** (MEASURED)، `bot` با `RestartCount=0` پولینگ می‌کند.
· PyPI: `pypi.org` ۲۰۰ می‌دهد ولی `files.pythonhosted.org` resolve نمی‌شود ⇒ Redis/coverage/pip-audit نصب‌ناپذیر.
· `fsm_states` + `PostgresStorage` + کلیدِ `FSM_STORAGE` (پیش‌فرض `memory`) — تستِ واحد ۵/۵ سبز.
· ⚠️ کشفِ مهم: محافظِ دابل‌تپ در `checkout.py:884-886` بر اتمیک‌بودنِ `MemoryStorage` تکیه دارد؛ با نگهدارندهٔ DB-محور (و با Redis هم همین‌طور) دو تپِ هم‌زمان هر دو از فیلتر رد می‌شوند. راهِ رفع: ایدبمپوتنتیِ دیتابیسیِ گذارِ سبد←سفارش. جزئیات در `REMAINING_ISSUES.md` §P32.


## ۲۷) پ۳۳ — ایدبمپوتنتیِ واقعی و بستنِ نقص‌هایِ زمان‌سنجی‌شده (۱۴۰۵-۰۸-۱۳ = ۲۰۲۶-۱۱-۰۴)

جزئیات در `docs/changelog-p33.md`.

| خواسته | نتیجه |
|---|---|
| «تازیدگیِ درجِ `admin_settings` را رفع کن» | درج داخلِ savepoint + خواندنِ دوباره؛ تستِ منفی‌سنجی‌شده با کدِ کهنه همان `UniqueViolationError: pk_admin_settings` را می‌گیرد و با رفع ۵/۵ سبز است. `test_p33_admin_settings_race.py` |
| «ایدبمپوتنتیِ گذارِ سبد←سفارش را درست کن» | `carts.submit_token` (مایگریشن `b7d4e2a9c3f6`) + ادعایِ نشانه در **تراکنشِ کوتاهِ جدا** (تلاشِ اول داخلِ تراکنشِ اصلی بود و `DeadlockDetectedError` ساخت). سنجهٔ قبولی: `test_checkout_c3` با `FSM_STORAGE=postgres` که پیش‌تر دو سفارش می‌ساخت، حالا ۱۱/۱۱ سبز است (MEASURED؛ `test_shopping_cart` ۱۱ و `test_cart_ai_editing` ۱۶ هم با هر دو نگهدارنده سبز) |
| نتیجهٔ دوم | علامتِ «آماده نیست» از `fsm_storage.build_storage()` و راهنماها برداشته شد؛ پیش‌فرض هنوز `memory` و فعال‌سازی با `FSM_STORAGE=postgres` در `.env` (که من نمی‌نویسم) |
| بدهیِ مصرفِ AI (P33-C) | جدولِ `ai_usage_debts` + `ai_debt_service`؛ `_deduct_and_notify` فقط با سوییچِ روشن بدهی می‌نویسد و `order_access_service` سقف را با مجموعِ کمیسیون + AI می‌سنجد. تستِ ۳ موردی با منفی‌سنجی.وصولِ خودکار (کسر از شارژِ بعدی) عمداً ساخته نشد — تصمیمِ محصولی است |
| کاهشِ خواندن‌هایِ مسیرِ پیام (P33-D) | شناسهٔ مشتری از میدل‌ور به تسکِ پاسخ پاس داده می‌شود ⇒ ۳۰ ← **۲۹** statement (MEASURED با همان تستِ سقف، که حالا رویِ ۲۹ قفل است). باقیِ تکرارها سه‌سشن‌بودنِ عمدیِ debounce است و تغییرِ معماری می‌خواهد |
| پاک‌سازیِ ruff (P33-E) | گامِ بلاک‌کنندهٔ ruffِ CI (که در پ۳۱ اضافه شد و هرگز اجرا نشده بود) در اجرایِ محلی **۲۹ خطا** در `tests_manual/` داد ⇒ صفر شد، بدونِ تغییرِ رفتار: فراخوانی‌هایِ اثردار ماندند و فقط binding‌هایِ بی‌مصرف رفتند (۲۰ فایل). `REMAINING_ISSUES.md` §P33-E |
| عددِ سوئیتِ پ۳۳ | **۱۱۵/۱۱۵ فایل · ۷۲۰ تست · صفر fail · `exit=0`** (MEASURED؛ رباتِ خاموشِ تأییدشده). پیش ازِ پ۳۳: ۱۱۲ فایل · ۷۰۹ تست. پس ازِ پاک‌سازیِ ruff هم دوباره همان عدد گرفته شد ⇒ رفتاری عوض نشده |
| دست‌نخورده | پوششِ کد/Redis (نصبِ پکیج در این محیط ممکن نیست) |


## ۲۸) پ۳۴ — پرداختِ سفارش به حسابِ خودِ فروشگاه (۱۴۰۵-۰۸-۱۳ = ۲۰۲۶-۱۱-۰۴)

جزئیات در `docs/changelog-p34.md`. این اولین کار از ششِ خواستهٔ تازهٔ مالکِ محصول است.

| خواسته | نتیجه |
|---|---|
| «در پنلِ کاربر مثلِ پنلِ ادمین دو ورودی باشد تا پول به حسابِ آنلاین‌شاپ برود، نه حسابِ من» | ریشه در کد بود: `app/main.py:719` و `bale_credentials_service.pay_link_username` صورتحسابِ سفارش را **همیشه** با رباتِ پلتفرم می‌ساختند و توکنِ درگاهِ فروشگاه را کنارِ آن می‌گذاشتند (جفتِ ناسازگار؛ توکنِ درگاه برایِ یک رباتِ خاص صادر می‌شود). حالا `ShopBaleStatus` سطحِ پرداخت را می‌دهد: هر دو ورودی ⇒ رباتِ خودِ فروشگاه + درگاهِ خودش + لینک در چتِ خودش؛ فقط درگاه ⇒ مثلِ قبل + هشدارِ `SHOP_HAS_PROVIDER_WITHOUT_BOT` در پنل. |
| «پنلِ فروشگاه‌دار» | صفحهٔ «🟢 رباتِ بله‌یِ فروشگاه» هر دو ورودی را با هم نشان می‌دهد (ماسک‌شده، چهار حالتِ صادق، دکمهٔ `🏦 توکنِ درگاهِ بله‌پی`، FSMِ تازه، «حذف» از همان صفحه). صفحهٔ قدیمیِ «💳 پرداختِ آنلاینِ سفارش‌ها» دست‌نخورده ماند. |
| آپدیت‌هایِ رباتِ بلهٔ فروشگاه | `bot_manager` حالا سه نوعِ آپدیتِ پرداخت را در پولینگِ بله مصرف می‌کند و با **توکنِ همان ربات** به هندلرهایِ `app/main.py` می‌دهد (`/start order-…`، `pre_checkout_query`، `successful_payment`)؛ `allowed_updates` هم `pre_checkout_query` را گرفت (بی‌این، بله هرگز می‌فرستدش). |
| باگِ لو‌رفته در همین مسیر | `app/main.py:712` مبلغِ سفارش را از `order.total_toman` می‌خواند که رویِ این مدل وجود ندارد ⇒ `AttributeError` و لینکِ مرده. شد `estimated_value_toman`. |
| تست | `test_p34_bale_own_payment_surface.py` = ۴ تست (ثبت‌شده). رگرسیونِ عمودیِ بله پس ازِ تغییر: p18 ۸/۸ · p19 ۸/۸ · p25 ۸/۸ · p26 ۶/۶ · bale_pay_for_orders ۷/۷ · wallet_topup ۵/۵ (MEASURED). |
| عمداً انجام نشد | حذفِ حالتِ «فقط درگاه» (باگرفتنِ دکمه از فروشگاه‌هایِ امروز) — در `REMAINING_ISSUES.md` §P34 با برچسبِ NOT RUN. مایگریشنِ تازه ساخته نشد: تک‌head `c8f1a4d7b2e5` بدونِ تغییر. |


## ۲۹) پ۳۵ — بازنگریِ متن‌هایِ ربات (۱۴۰۵-۰۸-۱۳ = ۲۰۲۶-۱۱-۰۴)

جزئیات در `docs/changelog-p35.md`. دومین کار از ششِ خواستهٔ مالک.

| خواسته | نتیجه |
|---|---|
| «متنِ زیرمجموعه ۲۰ هزار تومان می‌گوید، درحالی‌که من درصد تعیین می‌کنم» | `referral_code_text` حالا درصدِ زندهٔ `AdminSettings.referral_reward_value` را می‌گوید، صریح که «فقط به معرف»، و اگر صفر باشد هیچ پاداشی وعده نمی‌دهد. عددِ ۲۰٬۰۰۰ از ستونِ مردهٔ `referral_reward_wallet_toman` می‌آمد (مایگریشن `8b5d55b35561` خودش اعلام کرده که مصرف نمی‌شود) |
| همان درگوییِ پنلِ ادمین | `{fa_number(...)}٪` یعنی «۱۰.۰٪» با ممیزِ لاتین ⇒ `_percent_label()` با `fa_percent`؛ در خطِ «🎁 پورسانتِ معرف» و پیامِ پاداش هم نشست |
| باگِ لو‌رفته در همین بازنگری | مسیرِ اطلاع‌رسانیِ پاداش در `main.py:146-151` و `admin.py:162-167` کلیدِ `referred_telegram_id` را از dictی می‌خواند که `referral_service` هیچ‌وقت آن را نمی‌سازد ⇒ `KeyError` در هر پاداشِ واقعی. بلوکِ دوم و تابعِ بی‌مصرف حذف شدند؛ رفتارِ مالی دست‌نخورده |
| «متنِ توکنِ درگاه چرت‌وپرتِ طولانی است» | `bale_provider_token_current` از ~۱٬۱۰۰ به کمتر از ۷۰۰ نویسه (سنجیده در تست) و جملهٔ غلطِ «توکنِ ربات لازم نیست» با قاعدهٔ پ۳۴ عوض شد |
| «متنِ کدِ تخفیفِ خریدِ اعتبار باید درصد را بگوید» | `discount_applied_text` درصد/نوعِ همان کد و مبلغِ کم‌شده را می‌گوید؛ `INVALID_DISCOUNT_CODE` هر چهار علتِ واقعیِ `validate_code` را می‌شمارد (سقفِ استفاده قبلاً نبود) |
| «همهٔ متن‌ها بازنگری شوند» | اسکنِ MEASURED: ۱۳۶ خطِ دارایِ رقمِ فارسی در دو `texts.py` (۴٬۰۵۴ خط). تک‌تکِ عدد‌هایِ ثابت با کدِ محدودیت‌شان مقابله شدند؛ فهرستِ «درست ماندن» در changelog §۴ (۵ مگابایت، ۳۰ دقیقه، ۶۰ ثانیه، ۴۵ روز، ۱۰ دقیقه، کرکره‌ها). سه دیتِ فارسی (`user-guide`، `bot-functional-overview-fa`) هم‌راستا شد |
| تست | `test_p35_text_accuracy.py` = ۵ تست (ثبت‌شده). رگرسیونِ پنج فایلِ متنی رویِ ایمیجِ درست: ۷+۵+۶+۲+۴ سبز. **تذکرِ صادقانه:** سنجشِ اولِ همین رگرسیون پیش ازِ `build` گرفته شد، پس کدِ پ۳۵ را نداشت و عددش باورنکردنی بود؛ سوئیتِ کامل، `test_p22_bale_token_in_panel` را رد کرد (سرتیترِ قدیمیِ صفحهٔ توکنِ درگاه را انتظار می‌کشید) و آن تست به متنِ تازه هم‌راستا شد. جزئیات در `docs/changelog-p35.md` §۵ |


## ۳۰) پ۳۶ — هوشمندسازیِ رباتِ بله با توکنِ رباتِ بله (۱۴۰۵-۰۸-۱۳ = ۲۰۲۶-۱۱-۰۴)

جزئیات در `docs/changelog-p36.md`. سومین کار از ششِ خواستهٔ مالک.

| خواسته | نتیجه |
|---|---|
| «کاربر علاوه بر توکنِ تلگرام، توکنِ رباتِ بله را هم بفرستد تا همان قابلیت‌ها در بله فعال شود» | زیرساخت از پ۱۹ بود: توکنِ رمزنگاری‌شده رویِ `ShopBot`، `bot_manager.register_bale()` و pollingِ همان توکن با همان روترهایِ فروشگاهی. چیزی که نبود: (۱) پیشنهادِ روشنِ این کار در مسیرِ اتصال، (۲) امنیتِ چندرونشتی، (۳) مستندات درست |
| پیشنهاد در پنل | بعد ازِ «✅ رباتِ تلگرام وصل شد»، اگر ویژگی رونمایی شده و توکنِ بله ثبت نشده باشد، صفحهٔ دو ورودی (`🔑 توکنِ ربات بله` + `🏦 توکنِ درگاه`) پیشنهاد می‌شود؛ با توکنِ ثبت‌شده مزاحمی نیست |
| امنیتِ رونمایی | `BALE_POLLING_LOCK_KEY` (قفلِ advisoryِ جدایِ pollingِ بله): در حالتِ webhook هر رونوشت `on_startup` را اجرا می‌کند و pollingِ بله مستقل از `run_mode` است ⇒ بدونِ قفل، یکِ پیامِ بله‌ای دو بار به AI و دو بار کسرِ کیف‌پول. فقط صاحبِ قفل اتصال‌ها را شروع می‌کند؛ قفل در `on_shutdown` آزاد می‌شود |
| تصحیحِ ادعایِ کهنه | `REMAINING_ISSUES.md` §P26 بندِ ۶ («رباتِ بله هیچ‌جا getUpdates نمی‌خواند») با ذکرِ خط‌شماره‌هایِ امروز تصحیح شد؛ متنِ تاریخی پاک نشد، تذکرِ تاریخ‌دار اضافه شد |
| رونمایی در دیتابیسِ توسعه | `bale_shop_bots_enabled = true` با بکاپِ قبلی (`kasbokar-backups\pیش-از-P36-رونمایی-بله-2026-11-04-2237.dump`). پیش‌فرضِ کد برایِ نصبِ تازه هنوز خاموش است و دکمهٔ ادمین همان «🟢 رباتِ بله‌یِ فروشگاه‌ها» است |
| تست | `test_p36_bale_smarten_flow.py` = ۳ تست (ثبت‌شده): پاسخِ AI و کسرِ کیف‌پول برایِ مشتریِ بله‌ای با `platform=bale` · دروازهٔ قفل (MEASURED با لاگِ «رونوشتِ دیگری قفل را دارد») · پیشنهادِ پنل. رگرسیون: پ۳۴ ۴/۴ · bale_pay_for_orders ۷/۷ · p22 ۲/۲ · پ۳۵ ۵/۵ |
| NOT RUN | گفت‌وگویِ واقعی با رباتِ بلهٔ واقعی · دو رونوشتِ هم‌زمان رویِ یکِ دیتابیس · کشِ platform-mbenaی `photo_shop_file_id` (کارِ ۴) |


## ۳۱) پ۳۷ — بهینه‌سازیِ امنیتی/کارایی (پنجمین کار از ششِ خواسته، ۱۴۰۵-۰۸-۱۴ = ۲۰۲۶-۱۱-۰۵)

جزئیات در `docs/changelog-p37.md`. دامنه با تأییدِ مالک محدود شد به «فقط چیزِ کم‌ریسکِ داخلِ همین کد».

| مورد | نتیجه |
|---|---|
| یافتهٔ اصلیِ بازرسی (امنیت) | **توکنِ ربات می‌توانست در لاگ و در گزارشِ «🧪 آزمایشِ بله‌پی» چاپ شود:** `_api_url` توکن را در آدرس می‌گذارد (`bale_service.py:56`)، مسیرِ خطا `str(exc)` را داخلِ `BaleError` می‌ریخت و متنِ خطاهایِ aiohttp آدرسِ کامل را دارد؛ پاسخِ غیرJSON هم بدونِ بررسیِ `status/content_type` مستقیم `json()` می‌خورد. رفع: `_safe_error()` (همان `sanitize` که `payment_event_logs` را امن می‌کرد) + `_read_json()` + لایهٔ دومِ ماسکِ `/bot…/` در `payment_event_service` |
| SSRFِ آدرسِ AI | `_host_is_internal()` با `socket.inet_aton` + `ipaddress`: شکل‌هایِ مبدّلِ همان آدرسِ داخلی (`2130706433`, `0177.0.0.1`, `0x7f.0.0.1`, `127.1`, IPv6ِ کاملِ لوپ‌بک) حالا رد می‌شوند؛ DNS عمداً حل نمی‌شود (بندینگِ دوبارهٔ DNS به‌عنوانِ ریسکِ باقی‌مانده در راهنما و §P34 ثبت شد) |
| باگِ کارایی | کشِ `photo_shop_file_id` پلتفرم‌مبنا شد (قالبِ سه‌بخشی، سازگار با ردیف‌هایِ قدیمی) ⇒ دیگر file_idِ تلگرام به بله و برعکس داده نمی‌شود و آپلودِ دوبارهٔ مزمن حذف شد |
| باگِ درستیِ عدد | `apply_discount` از `float` به `Decimal` + `ROUND_DOWN` رسید؛ «۲٫۹٪ از ۱۰۰٬۰۰۰» قبلاً ۹۷٬۱۰۱ می‌داد (یکِ تومان گران‌تر)، حالا ۹۷٬۱۰۰ |
| باگِ «ساعتِ بوت» (سوئیتِ همین فاز لو داد) | `time.monotonic()` رویِ لینوکس از **بوتِ ماشین** می‌شمارد؛ دو مقایسه با `0.0` باعث می‌شد رویِ سرورِ تازه‌بوت‌شده **اولین هشدارِ ادمینِ هر نوع تا ۳۰ دقیقه** و **اولین همسنجیِ دفترِ کیف‌پول تا یک ساعت** خاموش بماند. رفع با `None` به‌جای `0.0`. شاهد: `test_p18_security` و `test_p5_ledger_integrity` که هفته‌ها سبز بودند با بالا آمدنِ دوبارهٔ داکر رد شدند — و flaky برچسب نخوردند، چون به‌تنهایی هم رد می‌شدند |
| تست | `test_p37_hardening.py` = ۸ تست (ثبت‌شده، شاملِ دو تستِ ساعتِ بوت با ساعتِ جعلیِ ۱۲ و ۹ ثانیه). رگرسیون: bale_payment_foundation ۵ · w5_photos ۵ · p24 ۱۱ · p25 ۸ · payments_w3w4 ۱۲ · p26 ۶ · **p18_security ۶/۶ و p5_ledger_integrity ۸/۸ پس ازِ رفع** (MEASURED رویِ ایمیجِ تازه) |
| عمداً انجام نشد | پکیجِ تازه (نصب‌ناپذیر) · Stateless‌سازی/webhook (تغییرِ معماریِ مسیرِ پول) · بالا بردنِ `db_max_overflow` (اندازه‌گیری‌شده که توان را می‌شکند) |


## ۳۲) پ۳۸ — راهنمایِ مبتدیِ استقرار + PDF (ششمین… یعنی پنجمین خواسته، ۱۴۰۵-۰۸-۱۴)

سندِ تازه: `docs/deployment-guide-beginner-fa.md` → `docs/deployment-guide-beginner-fa.pdf` با همان
`scripts/build_docs_pdf.py` (fpdf2 + Vazirmatn + shaping؛ docs/ در `.dockerignore` است ⇒ build با mount).

تفاضلش با `docs/deployment-playbook.md` این است که برایِ کسی نوشته شده که اولین سرور را می‌خرد: واژه‌نامه،
جدولِ «چند مشتری ← چند فروشگاه ← چه سرور»، نصبِ قدم‌به‌قدمِ کپی‌شدنی، `.env` با ستونِ «اگر خالی بماند چه
می‌شود»، بکاپ/بازگردانی با cron و قاعدهٔ «بکاپِ بازگردانی‌نشده بکاپ نیست»، آپدیتِ امن، جدولِ تنظیماتِ
۵۰۰ فروشگاه، جدولِ کلیدِ AI و خرج، عیب‌یاریِ «نشانه ← علت ← کارِ درست»، چک‌لیستِ بیست‌دقیقه‌ایِ قبلِ اولین
مشتری، و بخشِ پایانیِ «چه چیزی را هنوز نمی‌دانیم».

همهٔ عددها از سه سندِ اندازه‌گیری‌شده آمد (`SCALABILITY_AND_LOAD_TEST_REPORT.md` §۳/§۹/§۱۰،
`TEST_RESULTS.md`، `docs/deployment-playbook.md` §۵-الف) و برچسبِ اندازه‌گیری/محاسبه/تخمین حفظ شده است.


## ۳۳) پ۳۹ — چهار باگِ گزارش‌شدهٔ مالکِ محصول (۱۴۰۵-۰۸-۱۴ = ۲۰۲۶-۱۱-۰۵)

۱. **متنِ بدونِ ستاره:** هیچ پیامی با `parse_mode` فرستاده نمی‌شود ⇒ `**bold**` عیناً به چشم می‌آمد.
   چهار رشتهٔ ثابت پاک شد و خروجیِ مدل در چهار نقطه (چتِ مشتری/مشاوره، پیش‌نمایشِ پنل، دستیارِ
   مدیریتی، خلاصهٔ CRM) از `text_limits.strip_markdown` عبور می‌کند؛ پرامپت هم خطِ «قالب‌بندی
   ننویس» گرفت. تستِ AST جلویِ برگشتِ `**` را در هر دو `texts.py` می‌گیرد.
۲. **جریانِ توکنِ بله:** پیشنهادِ پس ازِ ثبتِ توکنِ تلگرام بدونِ کیبورد شد («بعداً» / ورودیِ بی‌ربط
   state را آزاد می‌کند)، دکمهٔ `bale_provider_edit` و state و متن‌هایش حذف شدند، و «💳 پرداختِ
   آنلاینِ سفارش‌ها» هر دو توکن را می‌گیرد (اول ربات، بعد درگاه — با کلیدِ رونماییِ خاموش فقط درگاه).
۳. **تاییدِ خودکارِ پرداختِ بله‌پی:** ریلِ قدیمی (`order-` و سبدِ بدونِ `OrderPayment`) فقط
   `bale_paid_at` می‌زد. ماشینِ وضعیتِ `apply_verified_online_payment` به تابعِ مشترکِ
   `apply_verified_gateway_payment` منتقل شد و همان تابع را هر دو ریل مصرف می‌کنند: گذار به
   `paid` (+`processing` با auto_accept)، رویدادِ خطِ زمانی، رزرو+تسویهٔ کمیسیون، `payment_method`
   روی ردیف‌ها (پس فاکتور «بله‌پی» می‌نویسد) و `notify_online_payment` که فاکتور و تحویلِ دیجیتال
   را هم فرستد. `pending → paid` به گذارهایِ مجاز اضافه شد (فقط از همین راهِ راستی‌آزمایی‌شده).
۴. **انقضایِ هر شارژ:** `credit_summary` یکِ مبلغِ قاطی‌شدهٔ ۳۰ روزه + نزدیک‌ترینِ روز می‌داد؛ حالا
   `expiry_lots` با همان یکِ SELECT، به تفکیکِ *روزِ* انقضا و به ترتیبِ FIFO برمی‌گرداند و صفحهٔ
   «💰 کیف‌پول» برایِ هر شارژ می‌گوید چقدر مانده و چند روز (+تاریخِ جلالی). گزارشِ شبانه «نزدیک‌ترین
   انقضا» را می‌گوید.

تازه‌ها: `test_p39_no_markdown_markers.py` (۵ تست)، `test_p39_wallet_per_charge_expiry.py` (۴ تست)،
یکِ تستِ تازه در `test_p34`، و به‌روزکردنِ هفت فایلِ تستِ قدیمی که رفتارِ عمداً عوض‌شده را پین کرده بودند
(`test_bale_pay_for_orders`، `test_shopping_cart`، `test_p20`، `test_p22`، `test_p34`، `test_p36`).
تعدادِ سوئیت: **۱۲۱/۱۲۱ فایل · ۷۵۰ تست · صفر fail · `exit=0`** (MEASURED — رباتِ خاموشِ تأییدشده،
کانتینرِ detached). مبنایِ پیش ازِ پ۳۹: ۱۱۹ فایل · ۷۴۰ تست ⇒ +۲ فایل و +۱۰ تست.


## ۳۴) پ۴۰ — بچ Aِ بازرسی: پنج رفعِ کم‌ریسک (۱۴۰۵-۰۸-۱۴)

پس ازِ پ۳۹، بازرسیِ کاملِ فنی/امنیتی/منطقی با دو بازرِسِ read-only موازی گرفته شد و هر یافته با
file:line دوباره تأیید دستی شد. مالکِ محصول «بچ A» را انتخاب کرد (رفتارِ پولی عوض نشود):

۱. `/webhook/bale` در `BALE_UPDATES_MODE=polling` (پیش‌فرضِ `.env`) بسته شد — تا پیش از این در
   ترکیبِ `RUN_MODE=webhook` + بله‌polling کاملاً بی‌احراز بود و آپدیتِ جعلی یعنی صورتحسابِ واقعی
   در چتِ دلخواه. اعتبارِ پولی از قبل محافظت داشت (استعلامِ سمتِ سرور + قیدِ یکتای `transaction_ref`).
۲. پاسخِ AI حالا به ۴۰۹۶ نویسه برش می‌خورد، تاریخچه فقط پس ازِ ارسالِ موفق نوشته می‌شود، پاسخِ
   نرسیده هزینه کم نمی‌کند (همان وعدهٔ راهنمایِ کاربر)، و متنِ جمع‌شدهٔ مشتری به ۸۰۰۰ نویسه محدود
   شد (سابقاً ~۶۰هزارنویسه با خرج رویِ کیفِ فروشگاه).
۳. رازِ وب‌هوک از `payment_event_logs.raw` ماسک می‌شود (`setWebhook`/`getWebhookInfo`)، بدونِ
   سوزاندنِ شناسهٔ عددیِ `/webhook/shop/42`.
۴. «پرداخت تایید شد» + فاکتور به مشتری فقط وقتی می‌رود که گروه واقعاً جلو رفته باشد؛ در
   `needs_review` تنها صاحبِ فروشگاه متوجه می‌شود.
۵. مایگریشنِ افزودنی `d4e7b1c8a902`: دو ایندکسِ partial (`reservation_expires_at`،
   `bale_transaction_id`) برایِ دو اسکنِ بی‌`shop_bot_id` (جابِ هر ~۶۰ ثانیه و هر وب‌هوکِ پرداخت) +
   `ORDER BY … LIMIT 200` در اسکنِ مهلت. تک‌head حفظ شد.

باقی‌مانده‌ها (بچ Bِ پول/قفل و بچ Cِ بهداشتی) با شماره و file:line در `REMAINING_ISSUES.md` §P40.
جزئیات: `docs/changelog-p40.md`. تعدادِ سوئیت: **۱۲۲/۱۲۲ فایل · ۷۵۷ تست · صفر fail · `exit=0`** (MEASURED، مبنایِ پیش: ۱۲۱ فایل · ۷۵۰ تست ⇒ +۱ فایل/+۷ تست)؛ تک‌headِ تازه `d4e7b1c8a902`.


## ۳۵) پ۴۱ — پرداختِ سفارش هیچ‌وقت به کیف‌پولِ پلتفرم نمی‌نشیند (۱۴۰۵-۰۸-۱۵ = ۲۰۲۶-۱۱-۰۶)

مالکِ محصول صفحهٔ پنل را فرستاد: توکنِ درگاه ثبت شده، توکنِ رباتِ بله نه، و متن می‌گفت «پول در
کیف‌پولِ پلتفرم می‌نشیند» — و گفت «جلوشو بگیر». قاعدهٔ افزودنیِ P34 (fallback به سطحِ پلتفرم با یک
هشدارِ متنی) حذف شد: حالا `shop_status` برایِ پرداختِ **سفارش** فقط جفتِ کاملِ خودِ فروشگاه را
می‌پذیرد (توکنِ رباتِ بلهٔ خودش + توکنِ درگاهِ خودش)؛ هر کدام ناقص ⇒ بله‌پی برایِ مشتری آن فروشگاه
فعال نیست و دکمه‌اش هم نشان داده نمی‌شود. علت‌هایِ تازه (`shop_bale_bot_token`،
`shop_provider_token`) به خانه‌هایِ همین صفحه اشاره می‌کنند، نه به پنلِ ادمین.

سه چیز که در همین مسیر درست شد:
۱. شارژِ کیف‌پولِ *پلتفرم* (payloadِ `payment-`) مثلِ قبل با سطحِ پلتفرم کار می‌کند — آن پرداخت را
   صاحبِ فروشگاه به سرویس می‌دهد، پس مقصدِ درست همان است (تست دارد).
۲. چند متنِ عمداً دروغ‌گو اصلاح شد: «پول در کیف‌پولِ پلتفرم می‌نشیند»، «توکنِ سراسریِ مدیر استفاده
   می‌شود»، و `BALE_PROVIDER_TOKEN_REMOVED` دو حالتی.
۳. پلِ `/start`ِ صورتحساب: وقتی لینک از رباتِ خودِ فروشگاه می‌آید، آپدیت هم با توکنِ همان ربات
   می‌رسد (`bot_manager`)؛ تست‌هایِ قدیمی همان را شبیه‌سازی می‌کنند.

پاک‌سازیِ دیتابیسِ توسعه (خواستِ صریحِ مالکِ محصول): با `pg_dump -Fc` پیش ازِ حذف، همهٔ دادهٔ
کسب‌وکار و لاگ‌ها پاک شد و **تنظیماتِ پلتفرم/ادمین ماند**: `admin_settings`، `admin_roles`،
`ai_api_key_pool`، `subscription_plans`، `mandatory_channels`، `moderation_rules` (+ `alembic_version`).
MEASURED (قبل ← بعد): `shop_owners` ۵←۰، `shop_bots` ۳←۰، `products` ۱۳←۰، `customers` ۷←۰، `orders_consultations` ۱۲←۰، `order_events` ۲۹←۰، `order_payments` ۸←۰، `payments` ۲←۰، `payment_event_logs` ۹۸۳←۰، `wallet_transactions` ۲۸←۰، `wallet_charges` ۳←۰، `carts` ۵←۰، `customer_addresses` ۳←۰، `shipping_methods` ۳←۰، `shop_payment_settings` ۳←۰، `conversation_messages` ۱۲←۰، `invoices`/`invoice_counters` ۲←۰، `direct_messages` ۱←۰، `discount_codes` ۱←۰. تنظیماتِ نگه‌داشته‌شده: `admin_settings` (یکِ ردیف: بله‌پی روشن، رونماییِ بله روشن، پورسانتِ معرف ۲۰٪، اعتبارِ شارژ ۱ ماه، کمیسیون ۰٫۵٪) + `alembic_version`؛ `admin_roles`/`ai_api_key_pool`/`subscription_plans`/`mandatory_channels`/`moderation_rules` از قبل خالی بودند و دست‌نخورده ماندند. شماره‌گذاریِ شناسه‌ها (sequence) ری‌استارت نشد — شناسه‌هایِ تازه از عددِ قبلی ادامه می‌کنند (عمدی؛ هیچ قاعده‌ای به عددِ کوچک وابسته نیست). پیش ازِ حذف، `pg_dump -Fc` گرفته شد: `kasbokar-backups/pish-az-P41-wipe-2026-11-06-0315.dump` (۲۱۰٬۶۹۷ بایت).
تعدادِ سوئیت: **۱۲۳/۱۲۳ فایل · ۷۶۰ تست · صفر fail · `exit=0`** (MEASURED، مبنایِ پیش ازِ این فاز: ۱۲۲ فایل · ۷۵۷ تست) جزئیات: `docs/changelog-p41.md`.

## ۳۶) پ۴۲ — تفکیکِ effort از دستورِ ۵۱موردی + دوازده رفعِ کم‌هزینه/متوسط (۱۴۰۵-۰۸-۱۷ = ۲۰۲۶-۱۱-۰۸)

مستر‌پرامپتِ مالکِ محصول ۵۱ مورد داشت و دستورِ صریحِ سطرِ اولش: «کارهایِ extra-high را جدا کن،
مابقی را کامل انجام بده و بعد متوقف شو». جدولِ تفکیک و وضعیت: `docs/WORK-ORDER-P42.md`؛
گزارشِ تک‌تکِ موارد + پاسخِ سؤال‌ها + جدولِ ظرفیت + پیشنهادِ کمیسیون: `docs/REPORT-P42.md`
(PDF: `docs/report-p42.pdf`)؛ جزئیاتِ فنی: `docs/changelog-p42.md`.

چه عوض شد (مواردِ ۱، ۲، ۳، ۴، ۵، ۶، ۷، ۲۱، ۲۶، ۲۸، ۲۹، ۳۲، ۳۳، ۳۵، ۴۲):
- **بله دو مسیرِ مستقل شد** (۱، ۲، ۲۸، ۲۹): دکمهٔ سبز از منویِ هر دو پنل حذف شد و «🟢 هوشمندسازیِ
  بله» داخلِ همان «🔑 ثبت/ویرایش توکن ربات» انتخاب می‌شود؛ «💳 پرداختِ آنلاینِ سفارش‌ها» اول
  گزینه‌ها را نشان می‌دهد؛ توکنِ نوشته‌شده از آن صفحه هوشمندسازی را روشن **نمی‌کند** و خاموش‌کردنِ
  هوشمندسازی پرداخت را نمی‌کُشد (`bale_bot_service.has_token` ملاکِ پرداخت،
  `ShopBotManager._bale_smarten` ملاکِ گفت‌وگو).
- **ریشهٔ «پرداختِ بله‌پی تایید نشد»** (۳): `python -m app.main` ⇒ نامِ ماژولِ زنده `__main__` بود و
  `from app import main` در پلِ پرداختِ بله، کپیِ دومی با `_state` خالی می‌ساخت؛ بعد ازِ commit،
  `KeyError: 'main_bot'` ⇒ اعلانِ فروشگاه‌دار/مشتری و فاکتور هرگز نمی‌رفت.گره‌زدنِ نامِ `app.main` به همان ماژولِ زنده، درستِ بلوکِ `__main__` بسته شد.
- **تاییدِ ادمین رویِ رسیدِ متنی** (۴): `edit_caption` رویِ پیامِ بی‌کپشن خطا می‌داد و کلِ تراکنش
  rollback می‌شد؛ حالا نوعِ پیام شناخته می‌شود و تصمیم **پیش ازِ شبکه commit** می‌شود. «None ماه»
  هم ریشهٔ جدا داشت: ردیفِ شارژ هیچ‌وقت `duration_months` نمی‌گرفت ⇒ `_validity_months` +
  `texts._duration_label` («اعتبارِ شارژ: ۱ ماه»).
- **کیف‌پول** (۵، ۲۱): تمدیدِ دسته‌ای رویِ *همهٔ* بسته‌هایِ زنده (`extend_live_charges`)، هدیه رویِ
  دیرترین بسته (`add_charge(merge_into_latest=True)`)، و `expiry_lots` بدونِ GROUP BY ⇒ دو شارژِ
  هم‌انقضا دو خطِ جدا.
- **پنلِ ادمین** (۷، ۳۵): عددِ «سقفِ بدهیِ کمیسیون» حالا FSM سلاح می‌کند و ذخیره می‌شود؛
  سوئیچِ «تشخیصِ سوال‌هایِ بی‌جواب» هر دو دکمه را از *هر دو* پنل برمی‌دارد (منبعِ مشترکِ
  `owner_common.panel_keyboard` تا در هشت صفحه فراموش نشود).
- **AI** (۳۲): `AI_TIMEOUT_SECONDS` (پیش‌فرض ۹۰) به‌جای ۶۰ ثانیه‌یِ ثابت و **حذفِ تکرارِ تایم‌اوت**
  (تکرارِ همان بارِ پولی، مشتری را دوبرابر معطلِ هیچ می‌کرد).
- **ثبت‌نام** (۴۲): درِ «کاربرانِ جدید» در `/start`، گیتِ کانال و تاییدِ نهاییِ ویزارد چک می‌شود.
- **معرف** (۲۶، بخشِ اول): با ساختنِ ردیفِ `Referral`، خبرِ «با لینکِ تو وارد شد» از صفِ اعلان‌ها
  می‌رود (`dedupe_key` ⇒ هر دعوت یکِ خبر).
- **متنِ تخمین** (۶): «دو‌برابر شارژ کن برایِ خیالِ راحت» حذف شد و مبنایِ عدد صریح گفته می‌شود.

تست: فایلِ تازهٔ `test_p42_bale_split_and_money.py` (۱۰ تست) + به‌روزرسانیِ هفت فایلِ قدیمی که
رفتارِ *عمداً عوض‌شده* را پین کرده بودند (۱، ۲، ۵، ۲۱ و مسیرِ توکن) — فهرست و دلیلِ هر کدام در
`docs/changelog-p42.md` §۷. تعدادِ سوئیت این فاز: **۱۲۴/۱۲۴ فایل · ۷۷۰ تست · صفر fail · `exit=0`** (MEASURED؛ مبنایِ پیش ازِ این فاز ۱۲۳ فایل · ۷۶۰ تست).

مانده: ۲۳ موردِ extra-high (نگهبانِ محتوا، لاگ/ممیزی، تنظیماتِ per-shop، زمان‌بندی، آمارِ
سراسری و نمودار، حذفِ محصولاتِ دیجیتال، انقضایِ ۳۱ روزه و بکاپِ خودکار، …) + ادامهٔ ۳۲/۳۳/۲۶/۶.

## ۳۷) پ۴۳ — نگهبانِ محتوا: دقت، گزارش، بلاکِ واقعی (مواردِ ۳۰، ۳۱، ۱۰ از دستورِ ۵۱تایی؛ ۱۴۰۵-۰۸-۱۸)

اولینِ گروهِ extra-high از صفی که در `docs/WORK-ORDER-P42.md` جدا شده بود.

- **ریشهٔ گزارشِ نادرست (۳۰):** تطبیقِ زیررشته‌ای ⇒ «خر» داخلِ «آخرین/خرید/خبر» هم می‌آمد و در پنلِ
  مشاوره‌ای گزارشِ بی‌دلیل ثبت می‌شد. حالا متن اول نرمال می‌شود (ی/ك عربی، تنوین، کشیده، ZWNJ مرز)
  و الگو باید «کلِ کلمه یا کلِ عبارت» بیفتد؛ regex ها مثلِ قبل‌اند و همان محافظتِ ReDoS ۱۰۰ms.
- **اکشن‌ها (۳۱):** WARN فقط ثبت و خبر نبود ⇒ حالا یکِ ردیفِ گزارش + کارتِ قابلِ فهم برایِ صاحبِ
  کسب‌وکار می‌سازد و گفتگو ادامه می‌یابد. BLOCK فقط یکِ پاسخِ خنثی می‌داد ⇒ حالا
  `Customer.is_blocked` نوشته می‌شود (همان ستونی که میدل‌ورِ رباتِ فروشگاه جلوِ مشتری را می‌گیرد)
  و ممیزیِ `CUSTOMER_BLOCK_CHANGED` هم ثبت می‌شود.
- **شاکلهٔ گزارش (۱۰):** جدولِ تازهٔ `moderation_reports` + `moderation_rules.shop_bot_id`
  (مایگریشنِ افزودنی `f3a6c81b0d74`، تک‌head) ⇒ هر گزارش می‌داند از کدام فروشگاه/کدام مشتری/کدام
  قانون/کدام دامنه (سراسری یا خودِ فروشگاه) آمده و کارتِ آن دکمه‌هایِ «👁 گفتگو» (همان صفحهٔ CRM
  یا صفحهٔ مخاطبانِ مشاوره)، «👤 مشخصاتِ کاربر»، «🚫 بلاک / ✅ رفعِ بلاک» و «✅ بررسی شد» را دارد.
- **پنل‌ها:** «🛡 نگهبانِ محتوا» در *هر دو* پنل (فروشگاهی و مشاوره‌ای) با فهرستِ گزارش‌هایِ باز و
  صفحه‌بندی؛ از منویِ ادمین «📋 گزارش‌هایِ بازِ فروشگاه‌ها»؛ گزارشِ قانونِ سراسری به ادمین هم می‌رود
  با خطِ «این گزارش از کدام فروشگاه است»؛ هیچ صفحه‌ای بدونِ چکِ مالکیت داده نمی‌دهد.
- **ترتیبِ امن:** گزارش + ممیزی + بلاک ⇒ `commit()` ⇒ بعد پیام‌ها (هیچ شبکه‌ای وسطِ تراکنش).

عددِ سوئیت: **۱۲۵/۱۲۵ فایل · ۷۷۴ تست · صفر fail · `exit=0`** (MEASURED؛ مبنایِ پیش ازِ این فاز ۱۲۴ فایل · ۷۷۰ تست).
جزئیات و دو failِ اجرایِ اول با دلیل: `docs/changelog-p43.md`.
ماندهٔ همین گروه: افزودنِ قانونِ *خودِ فروشگاه* از پنلِ کاربر، دیدنِ گفتگو در کارتِ ادمین، تماسِ
مستقیم با صاحبِ کسب‌وکار از همان کارت، و موردِ ۹ (گروه‌کردنِ سؤالاتِ مشابه) — همگی در صف.

## ۳۸) پ۴۴ — ماهِ انتخابیِ ادمین + بکاپِ خودکارِ دیتابیس (موردِ ۵۱؛ ۱۴۰۵-۰۸-۱۸ = ۲۰۲۶-۱۱-۰۹)

دومین گروهِ extra-high از صفِ `docs/WORK-ORDER-P42.md`. سه خواستهٔ موردِ ۵۱ جدا انجام شد:

- **قاعدهٔ «ماه» از پنل**: ستونِ افزودنیِ `admin_settings.month_length_days` (۰ = تقویمی با
  `relativedelta` و clamp سرِ ماه؛ ۳۰/۳۱ = روزشمارِ دقیق). `add_validity_months` تنها نقطهٔ ساختِ
  انقضا است و هم `wallet_service.add_charge` و هم `subscription_service.purchase_or_renew` از آن
  استفاده می‌کنند — «ماه»ِ کیف‌پول و اشتراک دوباره یکی است ( P22 این را برایِ تقویمی درست کرده بود؛
  این‌جا انتخابِ خودِ ادمین اضافه شد). در پنل، ورودیِ غیراز ۰/۳۰/۳۱ رد می‌شود.
- **هیچ ردیفِ کهنه‌ای جابه‌جا نمی‌شود**: هیچ UPDATE دسته‌جمعی رویِ `wallet_charges.expires_at` یا
  `subscriptions.end_date` نیست؛ تست صریح همین را پین می‌کند (خواستِ مالکِ محصول).
- **بکاپِ خودکار**: سرویسِ `backup` در compose (ایمیجِ خودِ `postgres:16` ⇒ نسخهٔ pg_dump همیشه جفت
  است) هر شب فایل می‌سازد؛ `backup_service.run_nightly` در جابِ ۳۰ دقیقه‌ای، تازه‌ترینِ
  فرستاده‌نشده را **یک‌بار** به ادمین‌ها می‌فرستد (مارکرِ `backup_last_sent_at` + commit پیش ازِ
  شبکه) و فایل‌هایِ بیرونِ مهلت را پاک می‌کند (فقط الگوی `kasbokar-…dump`؛ هر فایلِ دیگری دست
  نمی‌خورد). سوییچ، مهلتِ نگهداری و دکمهٔ «📦 ارسالِ دستیِ آخرین بکاپ» در دستهٔ تازهٔ
  «🗄 بکاپ و نگهداریِ دیتابیس». **ارسالِ خودکار خاموشِ پیش‌فرض** است.
- **متنِ صادقِ گزارشِ شبانه**: `digest_wallet_line` عددِ پنجرهِ انقضا را از فراخوان می‌گیرد
  (`wallet_service.EXPIRING_SOON_DAYS`)، نه از متنِ ثابت.

مایگریشنِ افزودنی: `b5e2d9f7c1a3` (چهار ستون رویِ `admin_settings`، همه با `server_default`، تک‌head).
**تغییرِ عمدیِ رفتار در تستِ قدیمی** (قاعدهٔ ۸): `test_p39_wallet_per_charge_expiry.py` دیگر
«…تا ۳۰ روزِ دیگر منقضی می‌شود» انتظار ندارد؛ متنِ تازه «…ظرفِ ۳۰ روزِ آینده منقضی می‌شود» است و
عددش را فراخوان می‌دهد. دلیلش همین‌جا و `docs/changelog-p44.md` §۵ آمده است.

تستِ تازه: `tests_manual/test_p44_month_length_and_backup.py` (۶ تست؛ در `run_all_tests.py` ثبت).
عددِ سوئیت: **MEASURED ۱۲۶/۱۲۶ فایل · ۷۸۰ تست · صفر fail · exit=0** (اجرا: ۲۰۲۶-۱۱-۰۹، رباتِ خاموش؛ مبنایِ پیش ازِ این فاز ۱۲۵ فایل · ۷۷۴ تست ⇒ +۱ فایل و +۶ تستِ تازه، صفر تستِ حذف‌شده). پنج گیت OK و ruff (`F,E9`) تمیز؛ alembic heads = `b5e2d9f7c1a3 (head)` (تک‌head).

## ۳۹) پ۴۵ — ظرفیت: نقشِ پروسه، شارد، وب‌هوکِ بی‌حالت و چهار لایه (۱۴۰۵-۰۸-۱۸ = ۲۰۲۶-۱۱-۰۹)

درخواستِ تازهٔ مالکِ محصول: «برایِ ۱۰۰۰ کاربرِ هم‌زمان در حالِ چت و ~۱٬۵۰۰ فروشگاه زیرساخت بساز؛
فعلاً رویِ سرورِ ضعیف‌تر دیپلوی می‌کنم و بعداً ارتقا می‌دهم؛ زیاد هزینه اضافه نشود.»

- **نقشِ پروسه** (`APP_ROLE` = all/core/poller/web) و **شارد** (`SHARD_COUNT`/`SHARD_INDEX`):
  هر فروشگاه با `id % count` فقط در یکِ پروسه polling می‌شود ⇒ سوکت‌ها و رم تقسیم می‌شود، و چون
  ترافیکِ یکِ فروشگاه در یکِ پروسه می‌ماند، debounce و قفل‌هایِ درِحافظه همچنان درست‌اند.
- **قفلِ ضدِ تکرار به‌ازایِ شارد** (`app_roles.lock_key`): با `SHARD_COUNT=1` عددِ کلید عوض نمی‌شود،
  پس هیچ قفلِ قدیمی جابه‌جا نشده؛ دو پروسه با یکِ شارد ⇒ دومی هیچ `getUpdates` شروع نمی‌کند.
- **وب‌هوکِ بی‌حالت**: `/webhook/shop/{id}` ربات و رازِ وب‌هوک را از دیتابیس می‌گیرد و در LRU با
  استخرِ HTTPِ مشترک نگه می‌دارد (`WEBHOOK_BOT_CACHE_SIZE=400`) ⇒ رمِ پروسه با فروشگاه‌هایِ پرمصرف
  رشد می‌کند نه با تعدادِ کل. `update_dedupe` (مایگریشنِ افزودنی `c7d3a91e5b48`) دوباره‌دریافتِ
  تلگرام را بینِ پروسه‌ها مهار می‌کند و فقط در همین حالت نوشته می‌شود (سقفِ ۱۲ جمله/پیام دست‌نخورده).
- **چهار لایهٔ آماده**: `deploy/docker-compose.t2.yml` (۴ شارد)، `t3.yml` (۶ شارد + دیتابیس
  بزرگ‌تر و `max_connections=200`)، `webhook.yml` (core + دو پروسهٔ web + Caddy با TLSِ خودکار) و
  `deploy/Caddyfile`. `scripts/scale_readiness.py` جمعِ اتصال‌ها را از خودِ postgres می‌پرسد و
  سقفِ هم‌زمانیِ لازمِ هوشِ مصنوعی را حساب می‌کند.
- **درِ اصلی، سرور نیست**: `کاربرِ هم‌زمان ≈ (سقفِ هم‌زمانیِ AI ÷ تأخیر) × ۶۰ ÷ پیامِ هر کاربر در
  دقیقه`. برایِ ۱٬۰۰۰ نفر با تأخیرِ ۴ ثانیه و ۲ پیام در دقیقه ⇒ ~۱۳۳ درخواستِ هم‌زمان لازم است؛
  با سقفِ ۴۰ امروز ~۴۰۰ نفر درِ بسته است. این عدد قبلِ هر خریدِ سرور باید از ارائه‌دهندهٔ کلید گرفته شود.
- **سازگاریِ برگشت**: پیش‌فرضِ `all` + `SHARD_COUNT=1` رفتارِ امروز را مو‌به‌مو نگه می‌دارد؛ هیچ
  ستونی حذف نشده و هیچ مسیرِ پولی تازه‌ای اضافه نشده.

تستِ تازه: `tests_manual/test_p45_capacity_layers.py` (۷ تست؛ شارد، نقش، load_all، webhook_entry،
dedupe، ریاضِ لایه‌ها، پارس‌شدنِ overlayها و بودجهٔ اتصال).
عددِ سوئیت: **MEASURED ۱۲۷/۱۲۷ فایل · ۷۸۶ تست · صفر fail · exit=0** (اجرا: ۲۰۲۶-۱۱-۰۹، رباتِ خاموش؛ مبنایِ پیش ازِ این فاز ۱۲۶ فایل · ۷۸۰ تست ⇒ +۱ فایل و +۶ تستِ تازه، صفر تستِ حذف‌شده). پنج گیت OK و ruff (`F,E9`) تمیز؛ `alembic heads` = `c7d3a91e5b48 (head)` (تک‌head). اعتبارسنجیِ overlayها: `docker compose -f docker-compose.yml -f deploy/docker-compose.t2.yml config` و `… -f deploy/docker-compose.t3.yml -f deploy/docker-compose.webhook.yml config` هر دو درست پارس می‌شوند و در لایهٔ وب‌هوک، پروسه‌هایِ poller با profile خاموش می‌مانند.

## ۴۰) پ۴۶ — حافظهٔ هر گفتگو و سقفِ پیام per-shop (مواردِ ۳۷ و ۱۴؛ ۱۴۰۵-۰۸-۱۸)

- سه `IntPref`ِ تازه در `shop_prefs_service` (حافظهٔ مکالمه ۱..۲۰۰ پیام، سقفِ پیام ۱..۱۰۰۰،
  پنجره ۵..۳۶۰۰ ثانیه) + سه ستونِ nullable رویِ `shop_bots` (مایگریشنِ `d8a4c2f6b913`).
  NULL ⇒ همان پیش‌فرضِ سراسری، پس هیچ فروشگاهِ موجودی رفتارِ تازه‌ای پیدا نمی‌کند.
- مصرف‌کننده‌ها: `customer._generate_and_send_reply` (طولِ تاریخچه) و `customer._check_access`
  (سقفِ نرخ). صفحهٔ «تنظیماتِ ربات» در هر دو پنل خودکار از `ALL_PREFS` ساخته می‌شود؛ فقط برچسبِ
  فارسی و واحد اضافه شد.
- از پنلِ ادمین برداشته شد: `💭 حافظه‌ی مکالمه`، `🚦 محدودیت پیام`، دو هندلرِ FSMِ سقفِ پیام و
  states‌هایش. ستون‌هایِ سراسری به‌عنوانِ پیش‌فرض/guardrail ماندند (هیچ داده‌ای حذف نشد).
- «زمانِ گزارشِ دوره‌ای» که در موردِ ۱۴ خواسته شده بود، **از P18** per-shop است
  (`weekly_report_weekday/hour/enabled`)؛ عددِ سراسریِ `periodic_report_frequency_days` فقط متنِ
  «گزارشِ چندروزه» را می‌سازد، پس عمداً در پنلِ ادمین ماند.
- تغییرِ عمدیِ دو تستِ قدیمی (قاعدهٔ ۸): `test_p18_per_shop_settings` (انتظارِ نبودِ فیلد در پنلِ
  ادمین) و `test_admin_settings` (دو تستِ ماشینِ ویرایشِ عددی به `periodic_report_frequency_days`
  منتقل شدند تا همان پوشش از دست نرود). دلیل در `docs/changelog-p46.md` §۴.

تستِ تازه: `tests_manual/test_p46_per_shop_memory_and_rate_limit.py` (۵ تست).
عددِ سوئیت: **MEASURED ۱۲۸/۱۲۸ فایل · ۷۹۲ تست · صفر fail · exit=0** (اجرا: ۲۰۲۶-۱۱-۰۹، رباتِ خاموش؛ مبنایِ پیش ازِ این فاز ۱۲۷ فایل · ۷۸۶ تست ⇒ +۱ فایل و +۶ تستِ تازه، صفر تستِ حذف‌شده). پنج گیت OK (۲۹۶ فایل، ۳۲۰ شکلِ callback_data)، ruff تمیز، `alembic heads` = `d8a4c2f6b913 (head)`.

## ۴۱) پ۴۷ — استخرِ ۱۰ کلیدِ AI با سقفِ همزمانیِ هرِ کلید و توزیعِ مساوی (درخواستِ ۲۰۲۶-۱۱-۱۰)

مالکِ محصول پرسید: «اگر چند کلید بگذارم همزمانی پوشش داده می‌شود؟ جوری تنظیم کن که برایِ کلیدِ
پشتیبان هم سقفِ همزمانی داشته باشم؛ در پنل به‌جایِ کلیدِ اصلی و پشتیبان، کلیدِ اول تا دهم با
ورودی‌هایِ خودش؛ اگر ممکن است سقفِ همزمانیِ هرِ کلید همان‌جا وارد شود نه در `.env`؛ و درخواست‌ها
تقریباً مساوی و هم‌زمان بینشان تقسیم شود.»

### ریشهٔ فنیِ «کلیدِ بیشتر فایده نداشت»
سه درِ جدا رویِ هم بودند و هیچ‌کدام به تعدادِ کلید وابسته نبود:
۱) `AI_MAX_CONCURRENT_CALLS` (سِمافورِ سراسری، پیش‌فرض ۴۰) — هرچه کلید بیشتر، همین ۴۰ صف را بلندتر می‌کرد.
۲) انتخابِ کلید «تصادفی» بود و فقط *شروعِ* پیمایش را عوض می‌کرد؛ بارِ هم‌زمان را نمی‌سنجید.
۳) استخرِ سوکتِ `aiohttp` (پیش‌فرض ۱۰۰ اتصال به هرِ میزبان) — درِ خاموش: حتی با envِ ۲۰۰۰، ۱۰۱امین
درخواست آنجا منتظرِ سوکت می‌ماند.

### چه ساخته شد
- **مایگریشنِ افزودنی** `e1c7b4a9d260`: ستونِ `ai_api_key_pool.max_concurrent` (Integer، nullable).
  NULL ⇒ «سهمِ مساوی از سقفِ پلتفرم». زنجیر تک‌head است؛ هیچ ستون/جدولی حذف نشد.
- **دو تنظیمِ تازه در `config.py`**: `ai_queue_timeout_seconds=120` (سقفِ صبرِ *صف*، نه پاسخ) و
  `ai_http_pool_limit=0` (بی‌سقف؛ governorِ واقعی همان سِمافور است). `.env.example` و
  `.env.docker.example` به‌روز شدند (بلوکِ تکراریِ `AI_TIMEOUT_SECONDS` که جا مانده بود هم پاک شد).
- **`ai_service._KeySlots`**: جایگاهِ کارِ هرِ کلید با شمارنده + `asyncio.Event` (نه Semaphore، چون
  ادمین وسطِ کار عدد را عوض می‌کند)، per-(loop, key_id)، آزادسازی در `finally` ⇒ لغوِ تسک کلید را
  برایِ همیشه «پر» نمی‌گذارد. `PooledAiService` کم‌بارترینِ کلید (`inflight ÷ cap`) را برمی‌دارد و
  تساوی‌ها را با نشانگرِ چرخشی **per-loop** نوبتی می‌کند (per-instance نبود، چون سرویس برایِ هرِ
  درخواست از نو ساخته می‌شود و وگرنه همه از کلیدِ اول شروع می‌کردند).
- **`ai_pool_service`**: `MAX_KEYS=10`، `MIN/MAX_KEY_CAP=1..500`، `parse_key_cap` (ارقام جلالی،
  «خالی» = سهمِ مساوی، خطِ ننوشته = بدونِ عدد و بدونِ خطا)، `cap_of`، `key_cap_label`،
  `capacity_report` (گلوگاه: کلیدها یا env)، `set_max_concurrent`، `count_entries` و
  `import_legacy_key` (کلیدِ قدیمی → کلیدِ ۱، و بعد خالی‌کردنِ مقدارِ سراسری تا یکِ کلید دوبار در
  گردش نیفتد). `build_ai_service` حالا `caps` را به استخر می‌دهد.
- **پنلِ ادمین**: فهرستِ «🟢 کلید ۱ · برچسب (chat) · همزمان: ۲۵»، خطِ هفتمِ فرمِ افزودن،
  دکمهٔ «🔢 سقفِ همزمانیِ همینِ کلید» + stateِ `AiPoolStates.waiting_max_concurrent`،
  «⬆️ انتقالِ کلیدِ قدیمی به کلیدِ ۱»، اخطارِ سقفِ ۱۰ کلید، و خطِ «📊 ظرفیتِ فعلی + گلوگاه».
  چهار دکمهٔ «کلیدِ اصلی / کلیدِ پشتیبان / مدلِ پشتیبان / آدرسِ پشتیبان» از گروهِ AI برداشته شد
  (ستون‌ها و مسیرِ قدیمیِ `build_ai_service` برایِ نصب‌هایِ بدونِ استخر سرِ جایشان ماندند).
- **امنیت**: گاردِ ضدSSRFِ `ai_base_url` (فقط https، ردِ میزبانِ داخلی با `inet_aton` + `ipaddress`)
  حالا رویِ `base_url` هرِ کلیدِ تازه هم اجرا می‌شود؛ برچسب/مدل/آدرس به طولِ ستون بریده می‌شوند.
- **`scripts/scale_readiness.py`**: `effective_ai_ceiling()` ⇒ ظرفیتِ قابلِ استفاده = کمِینهِ
  «سقفِ پلتفرم» و «جمعِ سقفِ کلیدها»؛ سقفِ کلیدها را از دیتابیس می‌خواند و می‌گوید گلوگاه
  کجاست و چند کاربرِ هم‌زمان می‌شود.

### تغییرِ عمدیِ سه تستِ قدیمی (قاعدهٔ ۸)
- `test_admin_settings.py`: «ذخیرهٔ فیلدِ متنیِ سراسری» از `ai_api_key` به `ai_model` منتقل شد، چون
  کلیدها دیگر از آنِ صفحه تنظیم نمی‌شوند (پوششِ همانِ ماشینِ ویرایش از دست نرفت).
- `test_p18_ai_model_pool.py`: به‌جایِ قفلِ کردنِ «شروعِ تصادفی»، state استخر صفر می‌شود؛ انتخابِ
  کلید دیگر تصادفی نیست و چرخشِ واقعی در تستِ P47 سنجیده می‌شود.
- `test_p24_dead_buttons_and_scope.py`: پینِ `_URL_FIELDS` به `{ai_base_url}` عوض شد + پینِ تازه که
  مسیرِ «افزودنِ کلید» همان گاردِ `_url_value_error` را دارد.

تستِ تازه: `tests_manual/test_p47_ai_key_load_balance.py` (۱۴ تست) — سهمِ مساوی، توزیعِ ۸ درخواست
رویِ ۴ کلید، عبورنکردنِ سقفِ هرِ کلید زیرِ ۲۰ درخواست، خطای صف پس ازِ تایم‌اوت، آزادشدنِ جایگاه پس
ازِ لغو، per-loop بودنِ شمارنده‌ها، مدارِ قطع، `capacity_report`، پذیرشِ ارقام جلالی و ردِ ورودیِ
نامعتبر، خطِ هفتم + دکمهٔ سقف، ردِ یازدهمین کلید، انتقالِ کلیدِ قدیمی، گاردِ SSRF رویِ آدرسِ کلید.

یکِ باگِ واقعی که همین تست‌ها در سوئیتِ کامل گرفتند: `parse_key_cap(None)` ابتدا «خطا» می‌داد، پس
«افزودنِ کلید با ۵ خط» (بدونِ خطِ هفتم) بی‌صدا ذخیره نمی‌شد — `test_ai_key_pool` آن را گرفتم و برطرف شد.

عددِ سوئیت: **MEASURED ۱۲۹/۱۲۹ فایل · ۸۰۶ تست · صفر fail · exit=0** (اجرا: ۲۰۲۶-۱۱-۱۰، رباتِ خاموش؛
مبنایِ پیش ازِ این فاز ۱۲۸ فایل · ۷۹۲ تست ⇒ +۱ فایل و +۱۴ تستِ تازه، صفر تستِ حذف‌شده). پنج گیت OK
(۲۹۷ فایل، ۳۲۲ شکلِ callback_data)، ruffِ F,E9 تمیز، `alembic heads` = `e1c7b4a9d260 (head)`.

## ۴۲) پ۴۸ — لاگِ زندهٔ سرور در پنل + بازهٔ دلخواهِ ممیزی (مواردِ ۱۳، ۳۹، ۴۸؛ ۱۴۰۵-۰۸-۱۹ = ۲۰۲۶-۱۱-۱۰)

- **بافرِ حلقویِ لاگ** در `app/observability.py`: هندلرِ `RecentLogBuffer` رویِ root، فقط WARNING و
  بالاتر، `deque(maxlen=300)`، هر دو متن (msg و traceback) از `scrub()` لایهٔ P20 رد می‌شوند ⇒ هیچ
  توکن/کلید/موبایلی در حافظه و در پنل نمی‌ماند. `emit()` در `try/except` است تا لاگ‌بردارِ لاگ، خودِ
  مسیرِ پیام را نیاندازد. API: `recent_logs(view, limit)`، `recent_log_counts()`.
- **صفحهٔ «🧾 لاگِ سرور»** (سوپرادمین، `super_router`، دکمه ثبت‌شده در `_KNOWN_MENU_BUTTONS`):
  دو نمایِ «🟡 هشدارها و خطاها» / «🔴 فقط خطاها» + «🔄 تازه‌کردن»؛ callbackها `logs_view:warnings`،
  `logs_view:errors`، `logs_refresh`. متنِ صفحه صریح می‌گوید «فقط همین پروسه، در حافظه» — لاگِ کامل
  مثلِ قبل در stdout و فایلِ چرخشیِ داکر (۵×۱۰ مگابایت) است و با `JSON_LOGS=true` ساختاریافته می‌شود.
- **بازهٔ دلخواهِ دفترِ ممیزی**: `_filtered_statement()` (فیلترها یک‌جا)، `query(..., since=, until=)`
  (شمولی/غيرشمولی، **بر پنجره‌هایِ آماده اولویت دارد**) و `count_rows(...)` با یکِ `GROUP BY`.
  ویزاردِ «🗓 بازهٔ دلخواه» (`AuditRangeStates.waiting_from/waiting_until`) با پذیرشِ
  `YYYY-MM-DD [HH:MM]` و ارقام جلالی، «خالی/همه» برایِ لبهٔ باز، «✖️ حذفِ بازه»، و تیترِ جلالیِ
  «در این بازه: N ردیف · X مالی · Y تنظیمات». **CSVِ ممیزی هم حالا همان بازه/دسته را رعایت می‌کند.**
- عمداً انجام نشد (با دلیل در `docs/changelog-p48.md`): پاک‌کردنِ ردیف‌هایِ کهنهٔ ممیزی (زنجیرهٔ
  `prev_hash`/`row_hash` را می‌شکند؛ جایش بایگانیِ CSVِ بازه‌دار آمد)، نوشتنِ لاگِ خام در دیتابیس
  (سقفِ جمله‌هایِ مسیرِ پیام)، جست‌وجویِ متنِ آزاد در `details` (بدونِ `pg_trgm`).
- بدونِ مایگریشن ⇒ `alembic heads` همان `e1c7b4a9d260 (head)`.

تستِ تازه: `tests_manual/test_p48_logs_and_audit_range.py` (۶ تست) — ماسکِ رازِ داخلِ متنِ لاگ،
فیلترِ «فقط خطاها»، صفحهٔ لاگ + RBAC، مرزهایِ `since`/`until`، جمعِ `count_rows`، ویزاردِ بازه + CSV.

عددِ سوئیت: **MEASURED ۱۳۰/۱۳۰ فایل · ۸۱۲ تست · صفر fail · exit=0** (اجرا: ۲۰۲۶-۱۱-۱۰، رباتِ خاموش؛
مبنایِ پیش ازِ این فاز ۱۲۹ فایل · ۸۰۶ تست ⇒ +۱ فایل و +۶ تستِ تازه، صفر تستِ حذف‌شده). پنج گیت OK
(۲۹۸ فایل، ۳۲۶ شکلِ callback_data)، ruffِ F,E9 تمیز.

## ۴۳) پ۴۹ — کانالِ اینستاگرام فقط از راهِ رسمی (الف + ب + پ؛ ۱۴۰۵-۰۸-۱۹ = ۲۰۲۶-۱۱-۱۰)

مالکِ محصول خواست: «همزمان با تلگرام و بله، مشاوره و فروش در اینستاگرام هم باشد؛ ریسک بن را ببین؛
آموزشِ کامل و فایل تولید محتوا؛ و یک دکمه در پنل ادمین که با روشن‌شدنش دکمهٔ اینستاگرام در پنل
کاربران بیاید و با خاموش‌شدنش محو شود؛ پرداخت همان بله‌پی و کارت‌به‌کارتِ فعلی.» تحقیقِ ریسک در
`docs/instagram-research-fa.md` نتیجه داد: مسیرِ غیررسمی (ورود با رمز و کتابخانه‌هایی مثلِ
`instagrapi`) قراردادِ اینستاگرام را می‌شکند و بن دارد ⇒ **ساخته نشد**؛ همه‌چیز از APIِ رسمیِ متا.

### الف — ستونِ فقرات (مایگریشنِ `c9a4e6f2b813`)
`admin_settings`: `instagram_enabled` (پیش‌فرض **خاموش**) + `instagram_app_id` + `instagram_app_secret`
(رمزنگاری‌شده) + `instagram_webhook_verify_token`. جدولِ تازهٔ `instagram_accounts` (یکِ ردیف به‌ازایِ
هرِ فروشگاه، `ig_account_id` ایندکس‌شده برایِ مسیریابیِ رویداد، توکنِ رمزنگاری‌شده، سوییچ‌ها،
`greeting_text`، `last_error`). سرویسِ `instagram_service`: لینکِ OAuth با `state`ِ یکبارمصرف،
`verify_signature` (HMAC-SHA256 رویِ بدنِ خام + `compare_digest`)، `parse_event` (حذفِ echo و
فقط‌پیوست)، `claim_event` (دوباره‌ارسالِ متا ⇒ یکِ پاسخ، یکِ کسر)، قاعدهٔ **۲۴ ساعت**،
`customer_key` (هویتِ پایدارِ ۶۴بیتی)، `platform="instagram"` در همان جدولِ `Customer`، و
`handle_inbound` که دقیقاً همان لولهٔ `customer.py` را صدا می‌زند (دسترسی، نگهبانِ محتوا، AI،
تاریخچه، کسر). وب‌هوک‌ها: `GET/POST /webhook/instagram` + `GET /webhook/instagram/oauth`، همگی با
`app_roles.serves_http()` و سقفِ درخواستِ دقیقه‌ای؛ پاسخِ ۲۰۰ سریع و پردازش در تسک.

### ب — کامنت‌ها (مایگریشنِ `f4a8c1d7b206`)
`CommentEvent` از `changes[]` (فیلدهایِ `comments` و `live_comments`)، `reply_to_comment`
(`POST /{ig}/media/{media_id}/comments`، متنِ عمومی تا ۲۸۰ نویسه) و `send_private_reply`
(`recipient={"comment_id": …}` + `tag=PRIVATE_TEXT`، **فقط یکِ پیام تا ۷ روز** — قاعدهٔ متا).
`handle_comment` همان درِ سراسری + سوییچ‌هایِ فروشگاه + نگهبانِ محتوا (کامنتِ block ⇒ هیچ جوابِ
عمومی‌ای زیرِ آن نوشته نمی‌شود) + کسر از همان `chat_billing_service`؛ عمداً برایِ کامنت‌کننده‌ای که
هرگز دایرکت نداده `Customer` ساخته نمی‌شود تا CRMِ فروشنده با غریبه پر نشود. scopeِ
`instagram_business_manage_comments` به اتصال اضافه شد. دو سوییچِ تازه در صفحهٔ «🟣 اینستاگرام»
(«💬 کامنت» و «🔒 پاسخِ خصوصی») — سوییچِ دایرکت هندلرِ اختصاصیِ خودش را نگه داشت تا دو هندلر رویِ
یکِ کال‌بک نیفتند.

### پ — آموزش و تولید محتوا
`docs/instagram-owner-setup-fa.md` (گام‌به‌گامِ اپِ متا، Business Verification، App Review، تنظیمِ
وب‌هوک، تستِ سراسری، چک‌لیستِ چاپی) · `docs/instagram-user-guide-fa.md` (فعال‌سازیِ فروشنده، سه قانونِ
متا، پرداخت، سؤال‌هایِ پرتکرار) · `docs/instagram-content-pack-fa.md` (پیام‌هایِ فروش، ۱۰ ایدهٔ پست،
کپشن‌هایِ آماده، سناریویِ کامنت←دایرکت←فروش، جمله‌هایی که نباید گفت، تقویمِ چهار هفته‌ای) — هر سه PDF
دارند؛ `docs/admin-guide.md` و `docs/user-guide.md` و نقشهٔ مستنداتِ `AGENTS.md` به‌روز شدند.

### دو رفعِ امنیتی/پایداری که همین فاز پیدا کرد
۱) `_SAFE_ID_RE` نقطه و خطِ تیره را می‌پذیرفت ⇒ یکِ `../` در شناسه می‌توانست مسیرِ درخواستِ Graph را
   عوض کند؛ برایِ شناسه‌هایِ کامنت/مدیا/اکانت الگویِ سخت‌گیرانهٔ `_STRICT_ID_RE` جانشین شد.
۲) `remember_error()` بدونِ سشن می‌ترکید ⇒ یادداشت‌کردنِ خطا دیگر خودِ ارسال را نمی‌شکند.

### پول، کپی نشد
ریاضِ کسرِ اعتبار از `customer.py` به `app/services/chat_billing_service.py` منتقل شد تا هر سه کانال
یکِ مسیر داشته باشند (قاعدهٔ ۷: ایدبمپوتنت و بدونِ منطقِ دوتایی). پرداخت رویِ اینستاگرام همان لینکِ
بله‌پی (پول به حسابِ خودِ فروشنده) و همان کارت‌به‌کارت با کدِ رهگیری است.

تست‌ها: `test_p49_instagram_channel.py` (۱۰) و `test_p49_b_instagram_comments.py` (۷)، هر دو ثبت‌شده.
**بدونِ تماسِ واقعی با متا** (App Review و توکنِ واقعی هنوز در دستِ مالکِ محصول است ⇒ وضعیتِ
NOT RUN برایِ سنجشِ زنده؛ منطق، درها، پنجره‌هایِ زمانی، ماسکِ راز و مسیرهایِ خطا در تست پوشش داده شده).

عددِ سوئیت: **MEASURED ۱۳۲/۱۳۲ فایل · ۸۲۹ تست · صفر fail · exit=0** (اجرا: ۲۰۲۶-۱۱-۱۰، رباتِ خاموش؛
مبنایِ پیش ازِ این فاز ۱۳۰ فایل · ۸۱۲ تست ⇒ +۲ فایل و +۱۷ تست). پنج گیت OK (۳۰۲ فایل،
۳۳۳ شکلِ callback_data)، ruffِ F,E9 تمیز، `alembic heads` = `f4a8c1d7b206 (head)`.


## ۴۴) پ۵۱ — نمودارِ درآمدِ ماهانه در پنلِ ادمین (موردِ ۴۴؛ ۱۴۰۵-۰۸-۱۹ = ۲۰۲۶-۱۱-۱۰)

- `stats_service.platform_revenue_report(session, since=, until=)`: شش کوئریِ گروهی ⇒ سطل‌هایِ
  **ماهِ جلالی** (SQL جمعِ روز را می‌دهد، `gregorian_to_jalali` در ماه می‌نشاند؛ گروه‌بندیِ میلادی
  برچسبِ دروغ می‌داد)، فروشِ اعتبار **خالص** (مصرفِ منفی + برگشتِ مثبت ⇒ همان عددِ «خلاصهٔ کلِ دوره»)،
  کمیسیونِ جدا، **نقدِ دریافتی** (شارژ/اشتراک) جدا با هشدارِ صریحِ «با فروشِ اعتبار جمعش نکن»،
  تفکیکِ `tenant_mode` (🛍 فروش / 💬 مشاوره‌ای)، سفارش‌ها و پیام‌هایِ مشتری (`role='user'`).
  هدیه‌ها (تراِیل/معرفی/گرنت) هیچ‌جا درآمد شمرده نمی‌شوند.
- صفحهٔ «📊 آمار سراسری» دو نما + ویزاردِ بازه شد: «📈 نمودارِ ۱۲ ماهِ گذشته»، «📊 خلاصهٔ کلِ دوره»،
  «🗓 بازهٔ دلخواه» (`StatsRangeStates.waiting_from/waiting_until`، همان قالبِ تاریخِ فازِ ۴۸:
  `۲۰۲۶-۰۱-۰۱ [۱۴:۰۰]` UTC، ارقام جلالی، «همه» برایِ سرِ باز) و «✖️ حذفِ بازه». نوارها با
  `sparkline` و `▁▂▄▆█`ِ موجودِ پروژه‌اند ⇒ بدونِ matplotlib و بدونِ وابستگیِ تازه.
- دو باگِ واقعی که تستِ همین فاز گرفت: ۱) قدرمطلقِ هرِ روز ⇒ برگشت‌ها به‌جایِ کسرشدن اضافه
  می‌شدند؛ ۲) `state.clear()` بعد ازِ «همه» کلِ بازهٔ تنظیم‌شده را پاک می‌کرد و نمودار بی‌سروصدا
  به ۱۲ ماهِ گذشته برمی‌گشت (حالا فقط حالت بسته می‌شود، داده می‌ماند).

تستِ تازه: `tests_manual/test_p51_revenue_chart.py` (۵ تست، ثبت‌شده) — خالص/تفکیکِ منبع/سطلِ جلالی،
تفکیکِ مشاوره-فروش با عوض‌کردنِ `tenant_mode`، صداقتِ متنِ نمودار (سرِصفحه، سه تفکیک، نوارها،
بازهٔ خالی)، جریانِ کاملِ صفحه با تاریخِ نامعتبر و حذفِ بازه، و تستِ ایستا که نمی‌گذارد نمودار و
خلاصه از هم جدا بیفتند. بدونِ مایگریشن (از ستون‌هایِ موجود استفاده شد).

عددِ سوئیت: **MEASURED 133/133 فایل · 834 تست · صفر fail · exit=0**
(اجرا: ۲۰۲۶-۱۱-۱۰، رباتِ خاموش؛ مبنایِ پیش ازِ این فاز ۱۳۲ فایل · ۸۲۹ تست). پنج گیت OK،
ruffِ F,E9 تمیز، `alembic heads` همان `f4a8c1d7b206 (head)`.

## ۴۵) پ۵۲ — گزارشِ بازه‌دارِ همزمانی (موردِ ۲۰؛ ۲۰۲۶-۱۱-۱۱)

- مرزِ شروعِ شامل و پایانِ خارج از بازه رویِ همهٔ شمارش‌ها یکسان است؛ گزارشِ تاریخی تا اکنون کشیده نمی‌شود و رویدادِ آینده را نمی‌شمارد.
- دانه‌بندیِ خودکار و محدود، تفکیکِ کانال، فروشگاه‌هایِ پرپیام با گروه‌بندیِ مستقل حتی برایِ نام‌هایِ یکسان، و نرخِ پیام با دقتِ اعشاری افزوده شد.
- فرمِ بازه، ترتیب و صحتِ تاریخ را کنترل می‌کند؛ شروعِ مشخص لازم است و «همه» فقط برایِ پایان پذیرفته می‌شود. انتخابِ نیمه‌کاره و لغو، بازهٔ قبلی را تغییر نمی‌دهند.
- تخمینِ همزمانیِ هوشِ مصنوعی با فرضِ صریحِ یک فراخوانی به ازایِ هر پیام و تأخیرِ پنج‌ثانیه‌ای نمایش داده می‌شود؛ ظرفیتِ واقعی یا بارِ اوج تلقی نمی‌شود.
- **MEASURED:** هشت تستِ اختصاصی در `test_p52_concurrency_report.py` گذشت؛ شاملِ تاریخ‌هایِ پیش از مبدأِ یونیکس و ابتدایِ تقویم. سوئیتِ اولیه با هفت تستِ این فاز، ۱۳۴/۱۳۴ فایل و ۸۴۱ تست بود؛ آن عدد تأییدِ تغییراتِ بعدی یا پ۵۳ نیست. اجراکننده علاوه بر قالبِ قبلی، نشانِ `PASS test_` را برایِ تست‌هایِ جدید می‌شمارد.
- **تغییرِ عمدیِ انتظارِ تستِ قدیمی:** در `test_p30_concurrency_report.py` فقط برچسبِ «خلاصهٔ CRM» به «خلاصهٔ مشتری» تغییر کرد تا گزارش فارسی باشد؛ شمارش‌ها و آزمون‌ها حذف یا ضعیف نشدند. عنوانِ قابلیت‌ها هم «مصرف‌هایِ ثبت‌شده» شد، نه شمارشِ مستقیمِ فراخوانیِ شبکه.
- **رگرسیونِ گرفته‌شده در بازبینیِ نهایی:** بازنویسیِ کیبوردِ گزارش، دکمهٔ «⬅️ بازگشت به پنل» و تیکِ پنجرهٔ انتخاب‌شده را حذف کرده بود؛ هر دو برگشتند و آزمونِ منو حالا برایِ هر دو پنجره و هر دو حالتِ بازه، ترتیبِ دکمه‌ها + تیک + بودجهٔ ۶۴ بایتی را چک می‌کند (اجرایِ مجدد: ۸/۸).
- **نتیجهٔ سوئیتِ نخستِ نهایی:** ۱۳۴/۱۳۵ فایل و ۸۵۴ تست؛ تنها شکست `test_p48_logs_and_audit_range.py` با تایم‌اوت ۶۰ ثانیه بود، درحالی‌که بیلدِ داکر و رندرِ PDF موازیِ سوئیت اجرا می‌شدند و کمی بعد Docker Desktop هم خاموش شد. اجرایِ تنهایِ همان فایل ۶/۶ گذشت؛ این شکست «flaky» نامیده نمی‌شود، بلکه رقابتِ منابع ثبت می‌شود و سوئیتِ نهایی دوباره اجرا شد.
- **سوئیتِ نهایی (تأییدِ هر دو فاز):** **MEASURED ۱۳۵/۱۳۵ فایل · ۸۵۸ تست · صفر شکست · exit=0** رویِ ایمیج `6c65f7f1…`؛ مبنایِ پیش ازِ پ۵۲/پ۵۳ = ۱۳۳ فایل · ۸۳۴ تست (+۲ فایل، +۲۴ تست، صفر حذف). در این اجرا P48 در ۵٫۸ و P47 در ۶٫۹ ثانیه تمام شد که تشخیصِ رقابتِ CPU را تأیید می‌کند. پنج گیت + ruff + `git diff --check` تمیز، `alembic heads` تک‌head رویِ `f4a8c1d7b206`.
- **NOT RUN:** آزمونِ چشمیِ تلگرام/مرورگر و بارِ واقعیِ ارائه‌دهنده. شرح در `docs/changelog-p52.md` و راهنمایِ ادمین؛ نتیجهٔ سوئیت در `TEST_RESULTS.md` ثبت می‌شود.

## ۴۶) پ۵۳ — صفحه‌بندی و فایلِ خصوصیِ کیف‌پول (موردِ ۴۶؛ ۲۰۲۶-۱۱-۱۱)

- صفحه‌بندیِ شناسه‌محورِ مالک با رفت‌وبرگشت و صفحهٔ خالی، بدونِ بارگذاریِ کلِ تاریخچه؛ درجِ جدید نزدیک‌ترین صفحهٔ قبلی را جابه‌جا نمی‌کند.
- خروجیِ اکسلِ راست‌به‌چپ با تاریخِ جلالیِ تهران و مبلغِ عددیِ علامت‌دار، بخش‌هایِ حداکثر پنج‌هزارردیفی و توضیحِ صریحِ کامل/ادامه‌دار/پایانِ زنجیره.
- دامنهٔ مالک در همهٔ کوئری‌هاست؛ فرستندهٔ دکمه مبنایِ هویت است، نه فرستندهٔ پیام. شناسهٔ داخلی/ارجاع/کلیدِ خصوصی صادر نمی‌شود؛ فرمول خنثی می‌شود و تراکنش پیش از شبکه بسته می‌شود.
- خواندنِ تاریخچه موجودی، دفتر و بسته‌هایِ شارژ را تغییر نمی‌دهد؛ مایگریشن، وابستگی یا دکمهٔ منویِ اصلی اضافه نشد. دوبارکلیک از کمک‌کنندهٔ ویرایشِ امنِ موجود استفاده می‌کند.
- **MEASURED:** شانزده آزمونِ اختصاصی و شش آزمونِ گزارشِ پ۳۰ گذشت. اجرایِ نخستِ پ۵۳ در سازندهٔ پیامِ تست به مدلِ تغییرناپذیر انتساب می‌داد؛ با کپیِ مدل رفع شد، نه تغییرِ رفتارِ محصول برایِ دورزدنِ آزمون.
- راهنمایِ کاربر، راهنمایِ ادمین، فایلِ تولیدِ محتوا و گزارشِ ساده به‌روز شدند؛ ادعاهایِ کهنهٔ ظرفیت، «فقط ۱۵ تراکنشِ اخیر» و وضعیتِ یافته‌هایِ بازرسی اصلاح شدند. شرح در `docs/changelog-p53.md` و عددِ سوئیت در `TEST_RESULTS.md` §۳۷ (نهایی: ۱۳۵/۱۳۵ فایل · ۸۵۸ تست · exit=0).
- **NOT RUN:** مشاهدهٔ زندهٔ رابطِ تلگرام/اکسل، بارِ واقعیِ تولید و ارائه‌دهنده. هیچ پیام یا پرداختِ واقعی برایِ آزمون ارسال نشد.

## ۴۷) پ۵۴ — صفِ حرفه‌ایِ تاییدِ پرداخت‌ها (موردِ ۱۲؛ ۲۰۲۶-۱۱-۱۱)

- دکمهٔ «🧾 صف تایید پرداخت‌ها» که فقط می‌گفت «N پرداخت در انتظار است» به فهرستِ واقعی تبدیل شد:
  `payment_service.pending_queue_page()` (دامنه پیش از صفحه‌بندی، قدیمی‌ترین اول، ۱۰/صفحه، شمارِ
  همان دامنه) + `shop_owner_service.get_by_ids()` برایِ نامِ صاحبان در یکِ کوئری.
- کارتِ جزئیات (`pay_queue_view:<page>:<id>`): فروشگاه‌دار، هدف، روش، مبلغِ درخواستی، مبلغی که باید
  واریز شده باشد، مدتِ اعتبار، زمانِ ثبت و مهلتِ رزرو (جلالی/تهران)، شمارهٔ پیگیری، رسیدِ متنی و
  پرچم‌هایِ تکراری. دکمه‌هایِ «✅ تایید» و «❌ رد» همان دو هندلرِ قبلی‌اند ⇒ صفر منطقِ پولیِ تازه؛
  «🧾 بازگشت به صف» شمارهٔ صفحه را از `callback_data` می‌گیرد، نه از FSM (بی‌حالت و بدونِ قاطی‌شدن
  با stateهایِ دیگرِ پنل).
- حریم خصوصی: `receipt_file_id`، `receipt_sha256`، `zarinpal_authority/ref_id`،
  `bale_invoice_payload/transaction_id` هیچ‌گاه چاپ نمی‌شوند؛ رسیدِ متنی فقط به ادمین می‌رسد.
  ورودیِ خراب (`abc`، منفی، صفحهٔ بی‌حد، شناسهٔ صفر/ناموجود، شکلِ سه‌قسمتیِ غلط) پیش ازِ هر
  کوئری رد می‌شود؛ بیرونِ دامنه ⇒ اخطارِ «خارج از دامنه» و صفر تغییرِ مالی.
- هزینه: خودِ تابعِ صفحه دو جمله می‌زند (شمارِ دامنه + ردیف‌ها) و در تست سقفِ سه جمله دارد؛ صفحهٔ
  کاملِ پنل تا چهار جمله: دامنه، شمار، ردیف‌ها، نامِ صاحبان. `OFFSET` عمداً مجاز است چون فهرستِ
  ادمینیِ کم‌ترافیک است، نه مسیرِ پیامِ مشتری (سقفِ ۱۲ جمله دست‌نخورده).
- **MEASURED:** ۷ آزمونِ اختصاصی در `tests_manual/test_p54_payment_queue.py` (ثبت‌شده در
  `run_all_tests.py`) گذشت و سوئیتِ کامل **۱۳۶/۱۳۶ فایل · ۸۶۵ تست · صفر fail · exit=0** شد
  (مبنایِ پیش ازِ این فاز ۱۳۵ فایل · ۸۵۸ تست ⇒ +۱ فایل و +۷ تست، صفر تستِ حذف‌شده؛ ایمیج
  `28b3044d47975c7800c9f47f9b5c40325c0c8d2e6763b00316532a78ada60625`). در اجرایِ نخست، آزمونِ سوم
  انتظارِ غلطی از کیبورد داشت (دکمهٔ «قبلی» در صفحهٔ اول) — انتظارِ آزمون با رفتارِ درستِ
  صفحه‌گردانیِ موجود اصلاح شد، نه کد به سمتِ آزمون.
  پنج گیت OK (۳۰۷ فایل، ۳۴۵ شکلِ `callback_data`)، ruff تمیز، بی‌مایگریشن (head همان
  `f4a8c1d7b206`)، بی‌وابستگیِ تازه، بی‌دکمهٔ تازه در منویِ اصلی.
- **NOT RUN:** مشاهدهٔ چشمیِ این صفحه‌ها در تلگرام و سنجشِ زمانِ پاسخ رویِ صفِ شلوغِ تولیدی.
  شرحِ کامل: `docs/changelog-p54.md` و `docs/admin-guide.md` §صفِ تاییدِ پرداخت‌ها؛ عددها در
  `TEST_RESULTS.md` §۳۸.

## ۴۸) پ۵۵ — رتبه‌بندیِ مصرفِ هوشِ مصنوعیِ هر کاربر + سقف/توقف/بلاک (موردِ ۲۳؛ ۲۰۲۶-۱۱-۱۱)

- ریشهٔ کار: هیچ ردیفی از دفترِ کیف‌پول نمی‌توانست بگوید مصرف را *کدامِ مشتری* ساخته است؛
  `wallet_service.deduct` فقط `shop_owner_id` می‌دانست. مایگریشنِ افزودنی `b7d3e8a2c451` سه
  ستونِ nullable اضافه کرد: `wallet_transactions.customer_id` (FK با `ON DELETE SET NULL` +
  ایندکسِ `(customer_id, created_at)`)، `customers.ai_daily_limit_toman`، `customers.ai_paused_until`.
- اتصالِ مصرف: آرگومانِ اختیاریِ `customer_id` به `wallet_service.deduct` و
  `chat_billing_service.deduct_and_notify` اضافه شد و رویِ همان `INSERT`ی که از قبل نوشته
  می‌شد ست می‌شود ⇒ **صفر جملهٔ اضافه**. پنج مسیر وصل شدند: چتِ متنی، ویرایشِ سبد، رونویسیِ
  صوت، تشخیصِ سفارش، دایرکتِ اینستاگرام. سه مسیر عمداً NULL می‌مانند چون مشتریِ شناخته‌شده
  ندارند: کامنتِ اینستاگرام، خلاصهٔ CRM، دستیارِ مدیریتی. ردیف‌هایِ قدیمی هم NULL می‌مانند ⇒
  رتبه‌بندی مصرفِ این نسخه به بعد را می‌شمارد و این رویِ خودِ صفحه نوشته شده است.
- صفحهٔ «📊 مصرفِ کاربران» (فقط سوپرادمین، هندلرِ جدا در `handlers/admin_ai_usage.py`):
  پنجرهٔ ۲۴ ساعت/۷ روز/۳۰ روز، فهرستِ ده‌نفریِ نزولیِ مصرف با شمارِ کاربرانِ متمایز، کارتِ
  جزئیات، و سه اهرم: سقفِ ۲۴ ساعت (FSM با «بدونِ سقف» و «انصراف»)، توقفِ ۲۴ ساعت/آزادکردن،
  بلاک/رفعِ بلاک با `crm_service.set_blockedِ` موجود. هر سه در ممیزی ثبت می‌شوند و صفحه هیچ
  مبلغی جابه‌جا نمی‌کند.
- اهرم‌ها در مسیرِ مشتری: `ai_usage_service.block_reason` پیش ازِ فراخوانِ AI اجرا می‌شود؛ با
  توقف یا سقفِ پرشده پاسخِ AI ساخته نمی‌شود ⇒ هیچ کسری هم ثبت نمی‌شود (MEASURED در تست).
  تا وقتی کاربری تنظیم نشده باشد این چک صفرِ کوئری است، پس `MAX_STATEMENTS_PER_MESSAGE=29`
  دست‌نخورده ماند؛ سقفِ تنظیم‌شده یکِ `SUM` محدود می‌زند.
- مایگریشن: راندتریپِ کامل با `scripts/check_migration_roundtrip.py` رویِ دیتابیسِ
  یک‌بارمصرف (upgrade ۱۵۷۵ms ← downgrade ۹۸۱ms ← upgrade ۱۵۴۹ms)، تک‌head، ۵۱ جدول.
- **MEASURED:** ۸ آزمونِ اختصاصی در `tests_manual/test_p55_customer_ai_usage.py` (ثبت‌شده) و
  سوئیتِ کامل **۱۳۷/۱۳۷ فایل · ۸۷۳ تست · صفر fail · exit=0** رویِ ایمیج
  `c7aa599444e9a43641258a53d8bb43e878ed972c5e641538c5e43011ac9822df` (مبنایِ پیش ازِ این فاز
  ۱۳۶ فایل · ۸۶۵ تست ⇒ +۱ فایل و +۸ تست، صفر حذف). پنج گیت OK (۳۱۰ فایل، ۳۵۰ شکلِ
  `callback_data`) و ruff تمیز. هفت اشکالِ همین فاز همه در آزمون/کیبورد بود نه در منطقِ پول
  (فهرستِ کامل در `TEST_RESULTS.md` §۳۹)؛ سه اصلاحِ آخرِ ظاهر/کیبورد هم با ایمیجِ نهایی دوباره
  با سوئیت تأیید شد، نه فقط با اجرایِ قبلی.
- **NOT RUN:** دیدهٔ چشمیِ این صفحه‌ها در تلگرام و زمانِ رتبه‌بندی رویِ دفترِ میلیونیِ تولیدی.
  شرح: `docs/changelog-p55.md` و `docs/admin-guide.md` §رتبه‌بندیِ مصرفِ هر کاربر.

## ۴۹) پ۵۶ — جست‌وجو در فهرستِ فروشگاه‌دارها (ادمین) و مشتری‌ها (فروشگاه‌دار) (مواردِ ۲۷ و ۴۱؛ ۲۰۲۶-۱۱-۱۱)

- منطقِ جست‌وجو در یکِ فایلِ مشترک نشسته است: `app/services/search_service.py` —
  `normalize_term` (ارقامِ فارسی/عربی، `ي/ك/ة/ى`، حذفِ کشیده و ZWNJ، یک‌کردنِ فاصله، حروفِ
  بزرگِ کوچک)، `_like` (فرارِ `\` و `%` و `_`) و `filter_conditions` (شرطِ `ILIKE` برایِ هر ستون +
  نامِ کامل در هر دو ترتیب + اگر عبارت فقط رقم بود `telegram_id` و شمارهٔ تلفنِ نرمال‌شده).
  `ئ` عمداً تبدیل نمی‌شود چون در فارسی حرفِ مستقل است و تبدیلش «مسئله» را خراب می‌کرد.
  عبارتِ خالی ⇒ صفر نتیجه (نه «همه»)، و سقفِ ۶۴ نویسه.
- دو پنل از همان منطق استفاده می‌کنند: «👥 مدیریت فروشگاه‌دارها» → «🔍 جست‌وجویِ فروشگاه‌دار»
  (نتیجه در همان قالبِ وضعیت + نام + @ربات، با صفحه‌گردانیِ جدا و دکمهٔ بازگشت به فهرستِ کامل)
  و «👥 مشتری‌ها» → «🔍 جست‌وجویِ مشتری» (فقط مشتری‌هایِ همان فروشگاه، صفحه‌هایِ هشت‌تایی، هر
  نتیجه همان دکمهٔ «کارتِ مشتری» قبلی). هیچ ستون، هیچ مایگریشن و هیچ وابستگیِ تازه‌ای لازم نشد.
- دامنه و مالکیت **پیش ازِ صفحه‌بندی**: جست‌وجویِ ادمینِ عملیاتی فقط داخلِ دامنه‌اش نتیجه می‌دهد و
  شمارِ نتیجه هم شمارِ همان دامنه است (قاعدهٔ P21-E)؛ جست‌وجویِ فروشگاه‌دار `shop_bot_id` را در
  شرطِ SQL دارد، پس مشتریِ فروشگاهِ دیگر با حدس‌زدنِ شناسه در `callback_data` باز نمی‌شود.
- سه اشکالِ همین فاز در **کد** بود و درست شد (نه در آزمون): ۱) دکمهٔ `crm_search` گاردِ مالکیت
  نداشت و هر کاربری با ساختنِ دستیِ کال‌بک متنِ «چه چیزی را بگردم؟» می‌گرفت ⇒
  `require_shop_bot_cb` اضافه شد؛ ۲) شماره‌هایِ نتیجه با ارقامِ لاتین چاپ می‌شد و متنِ فهرست
  اصلاً خطِ شماره‌دار نداشت ⇒ `fa_number` + خطوطِ شماره‌دار؛ ۳) عبارتِ دارایِ ZWNJ («علی‌محمدی»)
  صفر نتیجه می‌داد چون شرطِ نامِ کامل فقط با فاصله اجرا می‌شد ⇒ هر دو ترتیب همیشه امتحان می‌شود.
- دو اشکالِ دیگر را **آزمونِ پیام‌رسانِ جعلی نمی‌دید** و با بازبینیِ خودم و اسکنِ الگو در `app/`
  گرفته شد: ۴) `crm_search_start` بعد ازِ گاردِ مالکیت دوباره `callback.answer()` می‌زد (در
  تلگرامِ واقعی «query is already answered») — همان الگو در `instagram.cb_toggle_flag` از پ۴۹ هم
  وجود داشت و هرِ دو رفع شدند؛ ۵) «⬅️ بخش‌ها» و «👥 فهرستِ کاملِ فروشگاه‌دارها» حالتِ FSMِ
  جست‌وجو را پاک نمی‌کردند، پس هر متنِ بعدیِ کاربر دوباره جست‌وجو حساب می‌شد ⇒ `state.clear()` در
  `crm_home` و `cb_owners_list` + آزمونِ نهمِ رفتاری.
- تغییرِ عمدیِ انتظارِ یکِ تستِ قدیمی (قاعدهٔ ۸): `test_crm.py` فهرستِ دکمه‌هایِ نمایِ بخش‌ها را
  دقیقاً برابرِ پنج بخش می‌خواست؛ چون دکمهٔ جست‌وجو عمداً به همان نما اضافه شده، انتظار به
  «پنج بخش + `crm_search`» عوض شد و دلیلش همان‌جا نوشته شد. هیچ شمارشِ دیگری و هیچ ادعایِ
  پولی در این فاز حذف یا ضعیف نشد.
- **MEASURED:** ۹ آزمونِ اختصاصی در `tests_manual/test_p56_search.py` (ثبت‌شده در
  `run_all_tests.py`) + `test_crm.py` ۱۲/۱۲. سوئیتِ کامل با کدِ ویژگی **۱۳۸ فایل · ۸۸۱ تست**، و با
  کدِ نهایی (بعد ازِ دو اصلاحِ آخر) **۱۳۸/۱۳۸ فایل · ۸۸۲ تست · صفر شکست · exit=0** رویِ ایمیج
  `a489d13bf3934c15d2fe7e0ae3383426f4631e55bde0973881c69facb6216fc1` (مبنایِ پیش ازِ این فاز ۱۳۷
  فایل · ۸۷۳ تست ⇒ +۱ فایل، +۹ تست، صفر حذف). پنج گیت OK (۳۱۲ فایل، ۳۵۳ شکلِ `callback_data`) و
  `ruff --select F,E9` رویِ `app/` تمیز. بی‌مایگریشن (head همان `b7d3e8a2c451`، تأییدشده با
  `alembic heads`)، بی‌دکمهٔ تازه در منویِ اصلی، بی‌تغییرِ مسیرِ پول.
- **NOT RUN:** دیدهٔ چشمیِ این صفحه‌ها در تلگرام و زمانِ جست‌وجو رویِ دیتابیسِ تولیدیِ بزرگ (شرط‌هایِ `ILIKE` ایندکس نمی‌گیرند؛ `pg_trgm` عمداً در این فاز اضافه نشد). شرحِ کامل:
  `docs/changelog-p56.md`، `docs/admin-guide.md` §مدیریتِ فروشگاه‌دارها و
  `docs/user-guide.md` §جست‌وجویِ مشتری‌ها؛ عددها در `TEST_RESULTS.md` §۴۰.

## ۵۰) پ۵۷ (موردِ ۳۴-الف) — ارقامِ جلالی در همهٔ خروجی‌هایِ پنل (۲۰۲۶-۱۱-۱۱)

- قاعدهٔ ۵ می‌گوید UI باید ارقامِ جلالی داشته باشد، ولی `scripts/check_text_hygiene.py` عمداً
  لاتین را بررسی نمی‌کند (نامِ تابع، URL و `noqa` بخشی از کدند) ⇒ رقمِ لاتینِ تولیدشده توسطِ
  خودِ ربات («خریدارِ فعال: 3 نفر») سال‌ها از گیت رد می‌شد. راهِ رفعِ ماندگار **آزمونِ
  رِندرشده** بود، نه گیتِ متنی: `tests_manual/test_p57_persian_digits.py` (ثبت‌شده در
  `run_all_tests.py`) خروجیِ توابعِ متن/کیبورد را می‌سازد و می‌گوید هر رشته‌ای که نویسهٔ فارسی
  دارد نباید رقمِ ASCII داشته باشد؛ رشتهٔ بی‌فارسی (کد/URL/شناسه) آزاد است.
- ۱۲ فایل و ۳۴ سطرِ درجِ عدد با `fa_number` پیچیده شد (تأییدشده با `git diff`؛ فهرستِ
  «قبل/بعد» در `docs/changelog-p57.md`): نمایِ
  بخش‌ها و دکمه‌هایش، کارتِ مشتری، فهرستِ مشتری‌هایِ بخش، فهرستِ مخاطبانِ مشاوره، تاییدِ
  درون‌ریزیِ انبوه، پیامِ سفارشِ سبد، خلاصهٔ سبد، متنِ سفارشِ چندقلمی، پرامپتِ «(۳/۵)» چک‌اوت،
  دکمه‌هایِ مدیریتِ آدرس، دکمه‌هایِ بی‌جواب‌ها، پیشنهادِ ویرایشِ سبد، خطاهایِ ردیفِ اکسل،
  محدوده‌هایِ تایمرِ ادمین، پیامِ تمدیدِ اشتراک، مهلتِ گریس‌پیریود، سقفِ بیو، هشدارِ خودکارِ
  پلتفرم، هشدارِ اختلافِ دفتر، پنجرهٔ ۷ روزهٔ اینستاگرام و توضیحِ فایلِ اکسلِ دفترِ کیف‌پول.
- مرزهایی که عمداً دست نخورد (و در changelog دلیلشان نوشته شده): سلول‌هایِ عددیِ اکسل
  (`validators.py:16-17` می‌گوید عددِ خام تا فیلتر و جمع کار کند)، نمایشِ تلفنِ `+98912…`
  (قابلِ کپی و شماره‌گیری)، شناسه‌هایِ فنی و دادهٔ خودِ کاربر، و متنِ پرامپت‌هایِ هوشِ مصنوعی.
- دو انتظارِ تستِ قدیمی **عمداً** عوض شد (قاعدهٔ ۸): `test_crm.py` (`وفادار (2)` ⇒ `(۲)`) و
  `test_excel_product_import.py` (`ردیف 4` ⇒ `ردیف ۴`)؛ هر دو همان رفتارِ درستِ جدید را می‌سنجند
  و هیچ شمارش، ادعایِ پولی یا فایلی حذف/ضعیف نشد.
- **MEASURED:** ۸ آزمونِ اختصاصی در `tests_manual/test_p57_persian_digits.py` (ثبت‌شده در
  `run_all_tests.py`) و سوئیتِ کامل **۱۳۹/۱۳۹ فایل · ۸۹۰ تست · صفر شکست · exit=0** رویِ ایمیج
  `bc550cb7a33b431f00459931098e42052fe481357402b8bee13eaa00dd640836` (مبنایِ پیش ازِ این فاز
  ۱۳۸ فایل · ۸۸۲ تست ⇒ +۱ فایل، +۸ تست، صفر حذف). اجرایِ اول رویِ ایمیج `c6f6ee0f…` ۱۳۷/۱۳۹ بود
  و هر دو شکست همان انتظارِ عددیِ قدیمی بود، نه باگِ کد. پنج گیت OK (۳۱۳ فایل، ۳۵۳ شکلِ
  `callback_data`) و ruff تمیز. بی‌مایگریشن،
  بی‌وابستگیِ تازه، بی‌دکمهٔ تازه در منویِ اصلی، بی‌تغییرِ مسیرِ پول.
- **NOT RUN:** دیدهٔ چشمیِ این صفحه‌ها در تلگرام/بله (همهٔ آزمون‌ها با پیام‌رسانِ جعلی‌اند).

## ۵۱) پ۵۸ (موردِ ۲۴-الف) — دروازهٔ مود برایِ صفحه‌هایِ فقط‌فروشگاهی (۲۰۲۶-۱۱-۱۱)

- ریشه: دکمه‌هایِ «👥 مشتری‌ها»، «🧾 مدیریتِ سفارش‌ها (جاری)»، «🎯 کمپین‌ها»، «🧮 حسابداری»،
  «💳 پرداختِ آنلاینِ سفارش‌ها» و «📝 سوال‌هایِ چک‌اوتِ سبد» از منویِ مودِ مشاوره‌ای حذف می‌شدند
  (`keyboards.py:140-183`)، ولی هیچ‌کدام از هندلرهایشان چکِ مود نداشت. کیبوردِ کهنهٔ تلگرام و
  تایپ‌کردنِ متنِ دکمه دو راهِ ورود بودند ⇒ فروشگاه‌دارِ مشاوره‌ای صفحه‌هایِ بی‌معنی/ناتمام می‌دید
  (نشتِ داده نبود: شرطِ `shop_bot_id` همه‌جا برقرار است).
- دروازهٔ مشترک در `owner_common.py`: `sales_mode(shop_bot)` (یکِ منبع، جای دو کپیِ محلیِ `_sales`
  در `products.py:21` و `catalog_b2.py:33`) + `require_sales_mode` / `require_sales_mode_cb` که با
  متنِ تازهٔ `texts.MODE_SALES_ONLY` جواب می‌دهند: چرا نیست، جایگزینِ مشاوره‌ای کدام دکمه است، و
  مود از کجا عوض می‌شود (همان «👤 پروفایل من» که `set_business_mode` را اجرا می‌کند).
- هفت هندلر دروازه خورد (`crm.open_crm`، `orders_manage.open_orders_manage`،
  `campaigns.open_campaigns` و `campaigns.campaign_new`، `accounting.open_accounting`،
  `panel.open_bale_provider_token` و `panel.open_checkout_questions`) + `bs_stock` و حذفِ دکمهٔ
  «📦 اخطارِ موجودی» از کیبوردِ تنظیماتِ مشاوره (`keyboards.py:1418-1440`). در `panel` این
  ناهماهنگی هم رفع شد: گاردِ پرداخت فقط پایین‌تر در `payment_ops.py:244` بود، نه در ورودی.
- تصمیمِ صریحِ «بیشتر نکنیم»: در همین چهار روتر ۵۰ هندلر ثبت شده است؛ کال‌بک‌هایِ داخلی
  (`crm_card:`، `om_*`، `acct:`، `campaign_view:`…) دروازه **نخوردند**، چون بعد ازِ بسته‌شدنِ
  ورودی یا بی‌داده‌اند یا با `shop_bot_id` خودِ فروشگاه محدود می‌شوند و هیچ پول/دادهٔ دیگری را
  نشان نمی‌دهند. فهرستِ کاملِ انتخاب‌ها و دلیلِ هر «نکردیم» در `docs/changelog-p58.md`.
- **MEASURED:** ۵ آزمونِ اختصاصی در `tests_manual/test_p58_mode_gates.py` (ثبت‌شده در
  `run_all_tests.py`) با کنترلِ مثبت: همان دو کال‌بکِ `campaign_new` و `bs_stock` برایِ فروشگاهِ
  فروشگاهی کار می‌کنند و حالتِ FSM را سلاح می‌کنند، و برایِ مشاوره فقط اخطار می‌دهند ⇒ تفاوت
  دقیقاً همان دروازه است. سوئیتِ کامل **۱۴۰/۱۴۰ فایل · ۸۹۵ تست · صفر شکست · exit=0** رویِ ایمیج
  `5e5bf7063518afd2d99ee530798c189f5e14b996039916dc2e36af1abd22164b` (مبنایِ پیش ازِ این فاز ۱۳۹
  فایل · ۸۹۰ تست ⇒ +۱ فایل، +۵ تست، صفر حذف)؛ اجرایِ اول ۱۳۹/۱۴۰ بود و تکِ شکستش فیکِ ناقصِ
  `test_customer_keyboard_layout` بود (کد عوض نشد، فیک کامل شد). پنج گیت OK (۳۱۴ فایل، ۳۵۳ شکلِ
  `callback_data`) و ruff تمیز. عددها در `TEST_RESULTS.md` §۴۲.
- **NOT RUN:** دیدهٔ چشمیِ این صفحه‌ها در تلگرام؛ زمانِ عوض‌شدنِ کیبوردِ قدیمیِ کاربرِ واقعی بعد
  ازِ تغییرِ مود رفتارِ خودِ تلگرام است، نه کدِ ما.

## ۵۲) پ۵۹ (موردِ ۳۴-ب) — خروجی‌هایِ حرفه‌ای: فاکتور، نامِ فایل‌ها، رقمِ جلالی (۲۰۲۶-۱۱-۱۲)

- `invoice_service` خودش در کامنتِ `two_cell` نوشته که برچسبِ فارسی و مقدارِ لاتین نباید در یکِ
  رشته بنشینند (الگوریتمِ bidi ترتیب را به‌هم می‌ریزد)، ولی خطِ «شمارهٔ فاکتور: INV-…» همان قانون
  را نقض می‌کرد ⇒ دو سلولِ جدا، با رنگِ سفید داخلِ نوارِ تیره (چون `two_cell` رنگِ جوهری دارد).
- ستونِ «تعداد» در فاکتورِ HTML خامِ لاتین بود درحالی‌که مسیرِ PDF از پ۵۷/پ۲۷ `fa_number` داشت ⇒
  جلالی شد.
- ۷ نامِ فایلِ لاتین به فارسی تبدیل شد و به‌عنوانِ **ثابت در `texts`** نشست تا در چند فایل تکرار
  نشود: `مشتریان.xlsx`، `سفارش‌ها.xlsx`، `حسابداری.xlsx`، `دفتر-کیف‌پول.xlsx`، `دفتر-ممیزی.csv`،
  `رسید`، و `فاکتور-INV-….pdf|html`.
- مرزهایِ آگاهانه: رشتهٔ `INV-…` (کلیدِ یکتا و کدِ پیگیری) تغییر شکل نکرد، فقط پیشوندِ فارسی
  گرفت؛ پسوندِ فایل لاتین ماند (تلگرام/ویندوز با پسوندِ فارسی فایل را نمی‌شناسند)؛ سلول‌هایِ
  عددیِ اکسل عددِ خام ماندند (قاعدهٔ پ۵۷)؛ و شماره‌گذاریِ صفحه در فاکتورِ چندصفحه‌ای عمداً
  انجام **نشد** (جنگِ `alias_nb_pages` با reshaper در برابرِ حالتِ نادر) — به `REMAINING_ISSUES.md` رفت.
- دو انتظارِ تستِ قدیمی عمداً عوض شد (قاعدهٔ ۸): `test_p18_pdf_invoice.py` (نامِ فایلِ فاکتور) و
  `test_accounting.py` (نامِ فایلِ حسابداری، دو جا)؛ دلیلش در `docs/changelog-p59.md`.
- **MEASURED:** ۴ آزمونِ اختصاصی + `test_p18_pdf_invoice.py` ۷/۷ و `test_accounting.py` ۹/۹.
  عددِ سوئیتِ کامل **۱۴۱/۱۴۱ فایل · ۸۹۹ تست · صفر شکست · exit=0** رویِ ایمیج
  `39aa31d629318f20517aa80322e20394d4f05e07901c943b7545ad9f0e9a7def` (مبنایِ پیش ازِ این فاز ۱۴۰
  فایل · ۸۹۵ تست ⇒ +۱ فایل، +۴ تست، صفر حذف)؛ پنج گیت OK (۳۱۵ فایل، ۳۵۳ شکلِ `callback_data`) و
  ruff تمیز. شکستِ اولِ سوئیت (۱۴۰/۱۴۱) ادعایِ اسپیوی `test_p27_invoice_persian_layout` بود که
  فقط رشته‌هایِ shaped را می‌دید و مقدارِ لاتینِ خامِ شمارهٔ فاکتور را نمی‌شناخت؛ اسپیون به
  «هر `cell` چاپ‌شده» گسترش یافت، نه اینکه ادعا حذف یا ضعیف شود.
- **NOT RUN:** دیدهٔ چشمیِ فاکتورِ PDF و بازکردنِ فایل‌ها در اکسل/تلگرام؛ رفعِ bidi از خواندنِ کد
  و قانونِ مستندِ خودِ فایل است، نه از رسترِ تصویر.
- یادداشتِ تاریخچه: کامیتِ این فاز `daab941` است؛ سطرِ اولِ پیامِ کامیت به‌اشتباه عنوانِ فازِ قبل (پ۵۷) را کپی کرد، درحالی‌که بدنهٔ پیام و همین بخش، عددها و `docs/changelog-p59.md` همگی پ۵۹ را درست توصیف می‌کنند. چون این مخزن «هرگز amend/پوش» ندارد و پیامِ کامیت جزوِ سابقهٔ ثبت‌شده است، همین‌جا تصحیح شد تا خوانندهٔ `git log` گمراه نشود.

## ۵۳) پ۶۰ — هوشمندسازیِ اینستاگرامِ خودِ هر فروشگاه + متنِ سراسریِ ادمین (خواستهٔ ۲۰۲۶-۱۱-۱۲)

- دکمهٔ «📝 متنِ هوشمندسازیِ اینستاگرام» در صفحهٔ «🟣 اینستاگرامِ» پنلِ فروشگاه‌دار (فقط با اتصال)،
  FSMِ `InstagramStates.waiting_instructions`، سقفِ ۱۵۰۰ حرف، «خالی» برایِ پاک‌کردن، و خطِ وضعیتِ
  «متنِ هوشمندسازیِ اینستاگرام: دارد/ندارد».
- فیلدِ «متنِ سراسریِ هوشمندسازیِ اینستاگرام» در دستهٔ اینستاگرامِ پنلِ ادمین (سقفِ ۲۰۰۰ حرف)؛
  الگویِ متنِ برندینگ: لایه‌هایِ سراسری و فروشگاه **کنارِ هم** می‌نشینند، نه به‌جای هم.
- `instagram_service.instruction_directive(account, admin_settings, shop_bot)` سه لایه را می‌چیند
  و قاعدهٔ مود را اضافه می‌کند: فروشگاهی ⇒ محصول/قیمت از فهرستِ موجود، بدونِ لینکِ پرداخت در
  کامنتِ عمومی؛ مشاوره‌ای ⇒ فقط مشاوره و پاسخِ سؤالات/کامنت، بدونِ اعلامِ قیمت، بدونِ سبد/
  پرداخت/لینکِ خرید، بدونِ عددِ ساخته‌شده.
- `ai_context.build_system_prompt` یکِ پارامترِ اختیاریِ `channel_directive` گرفت که همیشه آخرِ
  پرامپت می‌نشیند؛ فقط دو مسیرِ اینستاگرام (کامنت و دایرکت) آن را می‌فرستند ⇒ پرامپتِ تلگرام/بله
  بایت‌به‌بایت مثلِ قبل (ادعایِ آزمونِ ۲، نه ادعایِ متنی).
- مایگریشنِ افزودنی `c9e4a7f1b620`: `instagram_accounts.instructions` و
  `admin_settings.instagram_platform_instructions` — هرِ دو nullable با `server_default=""` ⇒
  متنِ خالی یعنی دقیقاً همان رفتارِ پ۴۹؛ راندتریپِ کامل (upgrade ۱۶۸۰ms ← downgrade ۱۰۲۷ms ←
  upgrade ۱۶۹۵ms)، تک‌head، ۵۱ جدول.
- **MEASURED:** ۵ آزمونِ اختصاصی در `tests_manual/test_p60_instagram_panel.py` (چیدمانِ لایه‌ها و
  تفاوتِ مود، بی‌تغییریِ پرامپتِ اصلی، جریانِ کاملِ پنلِ کاربر، دروها، کیبورد و برچسبِ واقعیِ
  ادمین). سوئیتِ کامل **۱۴۲/۱۴۲ فایل · ۹۰۴ تست · صفر شکست · exit=0** رویِ ایمیج
  `0f10e3ca03b1a7c2e12296b6fdfa5133502c7ccbd3123109c5b990f783d24207` (مبنایِ پیش ازِ این فاز ۱۴۱ فایل · ۸۹۹ تست ⇒ +۱ فایل، +۵ تست، صفر حذف)؛ پنج گیت OK و ruff
  تمیز — عددها در `TEST_RESULTS.md` §۴۴.
- **NOT RUN:** هیچ اتصالِ واقعیِ متا برایِ این فاز آزمایش نشد (همچنان مثلِ پ۴۹: اپِ تأییدشدهٔ متا،
  App Review و دامنهٔ HTTPS لازم است)؛ دیدهٔ چشمیِ صفحه‌ها در تلگرام هم انجام نشد.

## ۵۴) پ۶۱ — پنلِ «📡 ظرفیت و فشارِ سرور» در پنلِ ادمین (خواستهٔ ۲۰۲۶-۱۱-۱۲؛ ۲۰۲۶-۱۱-۱۲)

درخواستِ دومِ مالکِ محصول در پیامِ ۲۰۲۶-۱۱-۱۲: «برایِ مدیریتِ راحت‌ترِ سرور … یکِ قسمت در پنلِ ادمین
برایِ بررسیِ وضعیتِ ظرفیتِ API‌ها و فشارِ سرور به‌صورتِ درصدی و آمارِ دقیق». حلقهٔ اول همان پنلِ
درصدی است؛ ایجنتِ خواندنِ لاگ و تشخیصِ مشکل هنوز در صف است (`REMAINING_ISSUES.md` §پ۶۱ بندِ ۵).

- `app/services/capacity_service.py` (فایلِ تازه، فقط‌خواندنی، بی‌شبکه): بارِ زندهٔ هرِ کلید از
  `ai_service.slots_for(entry.id).inflight`، استخرِ دیتابیس از شمارنده‌هایِ `engine.sync_engine.pool`
  (بی‌کوئری)، باری/رم/دیسک از `/proc/loadavg`، `/proc/meminfo` و `shutil.disk_usage`، و شمارنده‌هایِ
  `observability` فیلترشده. **هیچ وابستگیِ تازه‌ای** اضافه نشد (psutil نه — قاعدهٔ ۱۱).
- `app/bots/main_bot/handlers/admin_capacity.py`: روترِ مستقلِ `IsSuperAdmin` (پیام و کال‌بک)، دکمهٔ
  «📡 ظرفیت و فشارِ سرور» در کیبوردِ سوپرادمین، «🔄 تازه‌سازی» ⇒ `capacity_refresh`، و بازگشت به پنل.
  ثبت در `_KNOWN_MENU_BUTTONS` و `router.include_router`.
- **دو اصلاحِ صحتِ عدد که فقط آزمون گرفتنشان (کدِ فاز پیش ازِ آن‌ها نادرست بود، نه آزمون):**
  ۱) سقفِ هرِ کلید باید همان فرمولِ governor باشد؛ نسخهٔ اول برایِ کلیدِ بی‌عدد «سقفِ پلتفرم» را
     می‌گذاشت در حالی که `ai_pool_service` سهمِ مساوی (`equal_share_cap`) می‌دهد ⇒ دو نسخهٔ «ظرفیت»
     ساخته می‌شد. ۲) استخرها per-capability‌اند ⇒ کلیدهایِ `stt` از «ظرفیتِ پاسخِ مشتری» جدا شدند و
     خطِ «🎙 صوت» گرفتند؛ وگرنه جمعِ سقفِ کلیدها بالاتر از آنچه واقعاً برایِ پاسخ اجازه دارد.
- **تغییرِ آزمونِ قدیمی (رفتارِ کد عوض نشد):** `test_p47_ai_key_load_balance.py` در سوئیتِ کامل دو بار
  پشتِ هم در `test_pool_state_is_loop_scoped` شکست (`assert loop_a != loop_b`) و در اجرایِ جداگانه
  سبز بود. علت: ادعا `id()` یکِ event loopِ بسته‌شده را با loopِ بعدی مقایسه می‌کرد و پایتون می‌تواند
  همان آدرس را بازتخصیص دهد؛ زیرِ بارِ سوئیت دو `asyncio.to_thread` serialize می‌شوند و آدرس می‌سازد.
  رفع فقط در *آزمون*: ارجاعِ خودِ loop نگه داشته می‌شود تا آدرس بازتخصیص نشود. `app/services/ai_service.py`
  دست‌نخورده است و قيدِ باقی‌ماندهٔ همین طراحی (ثبتِ `_key_slots` با `id(loop)`) در
  `REMAINING_ISSUES.md` §پ۶۱ بندِ ۶ نوشته شد.
- بی‌مایگریشن (head همان `b7d3e8a2c451`ِ پ۶۰)، بی‌وابستگی، بی‌هیچ تغییری در مسیرِ پیامِ مشتری.
- **MEASURED:** ۶ آزمونِ اختصاصی در `tests_manual/test_p61_capacity_panel.py`: برابریِ فرمولِ سقف با
  governor و بارِ زنده، بی‌شمرده‌شدنِ کلیدِ غیرفعال/صوت، گلوگاه در دو حالت، استخرِ خالی (بی‌تقسیمِ بر
  صفر)، صفر-کوئریِ خواندنهایِ `/proc` و استخر + برچسبِ فارسیِ شمارنده‌ها، جریانِ واقعیِ صفحه (سه ستون،
  ارقامِ جلالی، یادداشتِ NOT RUN، یکِ ویرایش و دقیقاً یکِ پاسخِ کال‌بک) و دسترسی (سوپرادمین/اپراتور).
  **سوئیتِ کامل: ۱۴۳/۱۴۳ فایل · ۹۱۰ تست · صفر fail · exit=0** رویِ ایمیج
  `be2969920f50ce36bebe04ec54c802e95b0487fc841bb0cc3b27bb1553f3f4a6`؛ پنج گیت OK (۳۱۹ فایل ·
  ۳۵۵ شکلِ `callback_data`) و `ruff --select F,E9` تمیز — عددها در `TEST_RESULTS.md` §۴۵.
- **NOT RUN:** دیدهٔ چشمیِ صفحه در تلگرام؛ سنجشِ درصدِ مصرف زیرِ بارِ واقعیِ چند فروشگاهِ هم‌زمان؛
  سقفِ واقعیِ سرویسِ ارائه‌دهنده (همان ادعایِ صریحِ رویِ صفحه).

## ۵۵) پ۶۲ — ایجنتِ عملیاتیِ سرور: لاگ و اعداد → تشخیص → پیشنهاد (خواستهٔ ۲۰۲۶-۱۱-۱۲؛ ۲۰۲۶-۱۱-۱۲)

نیمهٔ دومِ همان درخواستِ مالکِ محصول: «برایِ مدیریتِ راحت‌ترِ سرور به یکِ ایجنتِ در حالِ کار در
محیطِ سرور برایِ لاگ‌ها و بررسیِ مشکلات نیاز دارم» (نیمهٔ اول = پنلِ درصدیِ ظرفیت، پ۶۱).

- `app/services/server_doctor.py` (فایلِ تازه): ۱۳ قانونِ عددیِ ثابت رویِ سه منبعِ موجود —
  `capacity_service` (بار/رم/دیسک، استخرِ دیتابیس، بارِ هرِ کلیدِ AI)، بافرِ لاگِ `observability`
  و شمارنده‌هایِ آن. هیچِ تحلیلِ هوشِ مصنوعی‌ای ندارد: هزینه دارد و نتیجه‌اش تکرارپذیر نیست،
  ولی «چرا سرور خوابید» عددِ دقیق می‌خواهد (تصمیمِ مستند در `docs/changelog-p62.md`).
- صفحهٔ «🩺 عیب‌یابِ سرور» در پنلِ ادمین (فقط سوپرادمین) داخلِ همان روترِ `admin_capacity`؛
  سرِصفحهٔ جلالی، شمارشِ شدت‌ها، عدد + آستانه + جایِ اقدام برایِ هرِ یافته، و یادداشتِ صریح
  «هیچ چیزی را عوض نمی‌کند». سه دکمه: `doctor_refresh`، `capacity_refresh`، `main_menu`.
- **ایجنتِ «در حالِ کار» بدونِ جابِ تازه:** همان بازرسی هر ~۳۰ دقیقه داخلِ
  `scheduler._run_periodic_pass_locked` (زیرِ قفلِ advisoryِ دیتابیس ⇒ با چند نسخهٔ اپ هم
  دوباره‌ارسال نمی‌شود) و اگر یافته‌ای **تازه** باشد خلاصه به `settings.admin_ids` می‌رود، با
  خنک‌کردنِ یک‌ساعته برایِ هرِ کلیدِ یافته. خاموش/روشن از همان صفحهٔ موجود: گروهِ تازهٔ `doctor`
  در `job_gate_service.GROUPS` ⇒ **بی‌مایگریشن و بی‌ستونِ تازه** (همان `jobs_paused_groups`).
- بی‌هیچ اقدامِ تغییری: نه ری‌استارت، نه پاک‌کردن، نه تغییرِ تنظیمات. تصمیمِ نهاییِ مالک («فقط
  پیشنهاد؛ اقدام با دکمهٔ صریحِ ادمین + ممیزی») عیناً رعایت شد — اقدام‌ها همان دکمه‌هایِ موجودِ
  پنل‌اند که قبلاً ممیزی می‌شوند.
- **قیدِ ایمنیِ این محیط:** چون قاعدهٔ ۹ می‌گوید بدونِ اجازه پیامِ واقعی فرستاده نمی‌شود، جابِ
  `doctor` در دیتابیسِ *توسعهٔ همین ماشین* با `job_gate_service.toggle_group(..., by="cli:p62-dev-safety")`
  متوقف شد (پیش‌ازآن هیچ گروهِ دیگری متوقف نبود؛ حالا فقط `doctor` است). در استقرارِ واقعی با
  روشن‌کردنِ همان گروه فعال می‌شود. آزمون‌ها همه با پیام‌رسانِ جعلی‌اند.
- **MEASURED:** ۷ آزمونِ اختصاصی در `tests_manual/test_p62_server_doctor.py` (مرزهایِ آستانه‌ها،
  نبودِ «صفرِ ساختگی» وقتی `/proc` نیست، گرفتنِ خطا از پیام و استک‌تریس، فقط‌خواندنیِ `inspect` با
  دقیقاً یکِ `SELECT` و صفر INSERT/UPDATE، خنک‌کردنِ ساعتی و «بی‌مورد ⇒ بی‌پیام» و بی‌سقوطِ جاب با
  ارسالِ خراب، دروازهٔ `doctor`، صفحهٔ پنل با ارقامِ جلالی و یکِ پاسخِ کال‌بک، دسترسی).
  **سوئیتِ کامل: ۱۴۴/۱۴۴ فایل · ۹۱۷ تست · صفر fail · exit=0** رویِ ایمیج
  `13c34700b57a291023e7bd69e9a91974ee0eb05e3ccb4783e86323c3e3d7ebe9` (مبنایِ پ۶۱: ۱۴۳ فایل ·
  ۹۱۰ تست ⇒ +۱ فایل، +۷ تست، صفر حذف)؛ ایمیجِ نهاییِ رباتِ روشن `c134c0f38b7742fbcfed96b1b05e5f8c98a8d1ec84699b110e8c357aaaa95581`
  است و تنها فرورش با همان سوئیت یکِ سطرِ docstring در فایلِ تست بود. پنج گیت OK (۳۲۱ فایل ·
  ۳۵۶ شکلِ `callback_data`) و `ruff --select F,E9` تمیز — عددها در `TEST_RESULTS.md` §۴۶.
- **NOT RUN:** هیچ هشدارِ تلگرامیِ واقعی از این ایجنت ارسال نشد (عمداً، بالا)؛ دیدهٔ چشمیِ صفحه در
  تلگرام؛ و سنجشِ قوانین رویِ ترافیکِ واقعیِ سرورِ تولیدی.

## ۵۶) پ۶۳ — مدیریتِ زمان‌دار و گزارشِ فعالیتِ اینستاگرام در پنلِ کاربر (ادامهٔ خواستهٔ ۲۰۲۶-۱۱-۱۲؛ ۲۰۲۶-۱۱-۱۲)

حلقهٔ دومِ همان درخواست: «پنلِ ویژهٔ مدیریتیِ اینستاگرام برایشان باز شود در پنلِ خودشان». پ۶۰ فقط
متنِ هوشمندسازی را داد؛ این فاز دو فعلِ مدیریتیِ واقعی اضافه می‌کند.

- ستونِ افزودنی `instagram_accounts.muted_until` (مایگریشنِ `d3a8c1f5b742`، nullable ⇒ NULL یعنی
  روشن و هیچ اکانتِ موجودی رفتارِ تازه نمی‌گیرد). راندتریپِ کامل رویِ دیتابیسِ یک‌بارمصرف:
  upgrade ۱۹۶۴ms ← downgrade ۷۳۲ms ← upgrade ۶۷۶ms، تک‌head، بی‌حذفِ هیچ‌چیز.
- `instagram_service`: `MUTE_PRESETS` (۱/۶/۲۴ ساعت و ۳ روز)، `is_muted`/`mute_until` (مقایسهٔ
  timezone-aware، بی‌جابِ «روشن کردن» — مهلتِ گذشته خودش آزاد می‌شود)، `set_mute` (فقط همین ستون +
  ممیزیِ `INSTAGRAM_TOGGLED` با جزئیاتِ فارسی) و `activity_summary` (سه شمارشِ کرانه‌دار رویِ
  همان ایندکسِ `customer_id, created_at`؛ فقط پلتفرمِ اینستاگرامِ *همینِ* فروشگاه).
- **درِ هرِ دو مسیر:** `handle_comment` و `handle_inbound` زودتر ازِ خواندنِ فروشگاه، زودتر ازِ
  نگهبانِ محتوا، زودتر ازِ AI و زودتر ازِ هر کسرِ اعتبار برمی‌گردند ⇒ در زمانِ خاموشی هزینه ساخته
  نمی‌شود. آزمونِ ۲ این را با «اگر به `shop_bot_service.get_by_id` برسیم تست می‌ترکد» می‌سنجد.
- پنلِ فروشگاه‌دار: دو دکمهٔ تازه در «🟣 اینستاگرام» فقط با اتصالِ برقرار (`ig_mute`،
  `ig_activity`)، صفحهٔ مهلت‌ها با ✅ رویِ مهلتِ فعال، «▶️ آزاد کردنِ همین حالا»، «⬅️ بازگشت به
  اینستاگرام» (`ig_screen`) و خطِ وضعیتِ «روشن / خاموش تا …» رویِ همان صفحهٔ اصلی. ورودیِ
  دستکاری‌شده (`ig_mute:abc`، `ig_mute:5`، عددِ بزرگ) با توست رد می‌شود و هیچ ستونی را عوض نمی‌کند؛
  کال‌بکِ فروشگاهِ دیگر به ردیفِ اینِ فروشگاه نمی‌رسد (`require_shop_bot_cb`).
- **دو تصمیمِ «نساختیم»:** معیارِ «چه چیزی را جواب ندهد» به‌شکلِ فهرستِ دوم نساختیم، چون همان کار
  را «🛡 نگهبانِ محتوا» رویِ اینستاگرام انجام می‌دهد و دو منبعِ حقیقت می‌شد؛ و شمارشِ کامنت‌ها را
  ساختگی نکردیم (رویدادِ کامنت ذخیره نمی‌شود) — صفحه صریح می‌گوید فقط دایرکت شمرده می‌شود و
  «گفتگوی پاسخ‌گرفته‌شده» با «همهٔ دایرکت‌هایِ دریافتی» یکی نیست (`REMAINING_ISSUES.md` §پ۶۳).
- **MEASURED:** ۷ آزمونِ اختصاصی در `tests_manual/test_p63_instagram_management.py` (زمان‌سنجیِ
  mute، درهایِ هرِ دو مسیر، فقط‌ستونِ-mute + ممیزی، شمارشِ فعالیت با تفکیکِ پلتفرم و فروشگاه،
  جریانِ کاملِ پنل، صفحهٔ فعالیت با ارقامِ جلالی، کیبورد/بودجهٔ ۶۴ بایت/دکمه‌هایِ مشروط به اتصال).
  **سوئیتِ کامل: ۱۴۵/۱۴۵ فایل · ۹۲۴ تست · صفر fail · exit=0** رویِ ایمیج
  `9b54b998c19dcbfc5c24a3f3a77e2d2f99aa97637e979608e6f1ace1e8de4441` (مبنایِ پ۶۲: ۱۴۴ فایل ·
  ۹۱۷ تست ⇒ +۱ فایل، +۷ تست، صفر حذف)؛ پنج گیت OK (۳۲۲ فایل · ۳۶۱ شکلِ `callback_data`) و
  `ruff --select F,E9` تمیز — عددها در `TEST_RESULTS.md` §۴۷.
- **NOT RUN:** اتصالِ واقعیِ متا (اپِ تأییدشده، App Review، دامنهٔ HTTPS) ⇒ رفتارِ خاموشی و
  شمارشِ فعالیت فقط با HTTP/پیام‌رسانِ جعلی سنجیده شد؛ دیدهٔ چشمیِ دو صفحهٔ تازه در تلگرام.

## ۵۷) پ۶۴ — نگهبانِ «پاسخِ دوباره» در هارنس + جارویِ state.clear در ناوبریِ پنلِ مصرف (۲۰۲۶-۱۱-۱۲)

کارِ کیفیِ درونی (بدونِ دکمهٔ تازه، بدونِ مایگریشن، بدونِ وابستگی): دو کلاسِ باگی که سه بار در
پروژه برگشتند و هیچ ابزاری پیدایشان نمی‌کرد.

- `tests_manual/harness.py`: `DuplicateCallbackAnswer` (از `BaseException`، تا `on_handler_error`
  آن را نبلعد) + `_answered_ids`؛ پاسخِ **موفقِ دوم** به همان `callback_query_id` حالا تست را
  می‌شکند. پاسخِ ناموفق در حالتِ `fail_answer_callbacks` ثبت نمی‌شود تا سناریویِ P27
  («query is too old») مثلِ قبل کار کند.
- نگهبان **اختیاری** است (`strict_callback_answers`) و `phase4_helpers.Chat` آن را روشن می‌کند:
  اولینِ اجرایِ کامل با نگهبانِ همیشه‌روشن `test_p19_bale_shop_bot.py` و
  `test_p47_ai_key_load_balance.py` را شکست داد؛ بررسی شد که آن دو فایل `make_callback_update(1, …)`
  را با شناسهٔ ثابت برایِ چند رویدادِ جدا می‌فرستند ⇒ بازخوردِ نادرست، نه باگ. تستِ قدیمی را
  دست‌نزدیم (قاعدهٔ ۸) و توضیحِ کامل در `REMAINING_ISSUES.md` §پ۶۴-ب ماند.
- **باگِ واقعیِ پیدا‌شده توسطِ همان نگهبان:** `panel.py:tok_bale` اول `callback.answer()` می‌فرستاد و
  بعد `_own_shop_bot_cb` برایِ فروشگاهِ بی‌ربات دوباره پاسخ می‌داد ⇒ اخطارِ «رباتِ فروشگاهی تنظیم
  نشده» در تلگرام دور ریخته می‌شد و کاربر فقط ساعتِ چرخان می‌دید. حالا هرِ شاخه دقیقاً یکِ پاسخ دارد.
- **باگِ دوم (همان خانوادهٔ FSM):** چهار هندلرِ «📊 مصرفِ کاربران» (پنجره/صفحه، جزئیات، توقف، بلاک)
  حالتِ `AiUsageStates.waiting_limit` را پاک نمی‌کردند ⇒ عددی که ادمین بعد ازِ ناوبری می‌نوشت به‌عنوانِ
  سقفِ همان کاربر ذخیره می‌شد. `state.clear()` اضافه شد؛ `main_menu` از قبل پاک می‌کرد.
- جارویِ کورِ بقیهٔ روترها انجام **نشد** (`campaigns` ۱۲/۵، `start` ۱۰/۵، `catalog_b2` ۱۵/۱۲ فقط
  شمارش‌اند)؛ بَرسِ تک‌تکِ جریان در `REMAINING_ISSUES.md` §پ۶۴ ماند، چون ویزاردِ سبد/چک‌اوت در
  مسیرِ پولِ مشتری است.
- **MEASURED:** ۷ آزمونِ اختصاصی در `tests_manual/test_p64_navigation_guards.py` (فعال‌شدنِ نگهبان و
  ثبت‌نشدنِ پاسخِ ردشده، `BaseException`‌بودن، چهار جریانِ ناوبریِ پنلِ مصرف، ضدِ رگرسیونِ تنظیمِ سقف،
  و «یکِ پاسخِ تنها در ورودیِ بله»). **سوئیتِ کامل: ۱۴۶/۱۴۶ فایل · ۹۳۱ تست · صفر fail · exit=0**
  رویِ ایمیج `efac044e45632302a0f95dcd4ca739db3692635ec3c366bf36152c9baef25570` (مبنایِ پ۶۳: ۱۴۵ فایل ·
  ۹۲۴ تست ⇒ +۱ فایل، +۷ تست، صفر حذف) و صفر تکرارِ `DuplicateCallbackAnswer` در خروجیِ سوئیت؛
  پنج گیت OK (۳۲۳ فایل · ۳۶۱ شکلِ `callback_data`) و ruff تمیز — عددها در `TEST_RESULTS.md` §۴۸.
- **NOT RUN:** دیدهٔ چشمیِ اخطارِ «ربات تنظیم نشده» در تلگرام؛ پوششِ نگهبان رویِ هندلرهایی که هیچ
  تستِ Chat‌دار لمسشان نمی‌کند.

## ۵۸) پ۶۵ — «حذفِ حسابِ من» در پنلِ خودِ فروشگاه‌دار (نیمهٔ دومِ موردِ ۲۷/۴۱؛ ۲۰۲۶-۱۱-۱۳)

تا این فاز فقط ادمین می‌توانست حسابی را ببندد (پ۲۲). خواستهٔ مالکِ محصول این بود که خودِ
فروشگاه‌دار هم بتواند؛ چون «بستنِ حساب» با «محوِ اسنادِ مالی» یکی نیست، یکِ مسیرِ *سوم* ساخته شد
نه کپیِ آن دو.

- `app/services/account_deletion_service.py`: `preview()` (شمارشِ رفتنی‌ها/ماندنی‌ها + مانع‌ها) و
  `delete_account()`. **هویت و محتوا می‌روند**: نام/موبایل/ایمیل/یوزرنیمِ فروشگاه‌دار، هویت و
  یادداشت/برچسبِ مشتری‌ها (با `telegram_id = -id` تا ارجاعِ سفارش و دفترِ کیف‌پول نشکند و یکتاییِ
  (فروشگاه، شناسه، بستر) حفظ شود)، گفتگوها، پیام‌هایِ مستقیم، دفترچهٔ آدرس، سبدها، اتصالِ
  اینستاگرام، کدهایِ موقتِ SMS و صفِ *بازِ* اعلان/ارسالِ زمان‌دار. **رازها می‌روند**: توکنِ تلگرام،
  رازِ وبهوک، توکن/شناسه/یوزرنیمِ بله، کدِ درگاهِ بله، مرچنت زرین‌پال، کانالِ دانش، تماسِ پشتیبانی.
  **اسنادِ مالی و ممیزی می‌مانند**: سفارش‌ها، فاکتورها، دفترِ کیف‌پول، شارژها، کمیسیون‌ها و ردیف‌هایِ
  ممیزی (زنجیرهٔ هشِ ممیزی پاک‌شدنی نیست و `shop_purge_service` پ۲۲ برایِ همان ساخته شده بود).
- **مانعِ پول:** با موجودیِ کیف‌پولِ غیرصفر یا کمیسیونِ قفل‌شده هیچ ردیفی عوض نمی‌شود؛ عدد در پیام
  می‌آید. سفارشِ باز مانع نیست، **هشدار** است (تصمیم با صاحبِ حساب).
- پنل: «🗑 حذفِ حسابِ من» در «👤 پروفایل من» ⇒ پیش‌نمایش ⇒ دکمه ⇒ **نوشتنِ عبارتِ «حذفِ حساب»**
  (قراردادِ تاییدِ نوشتاریِ پ۲۲). واژهٔ تایید عمداً در `_KNOWN_MENU_BUTTONS` ثبت نشده، چون میدل‌ورِ
  فرارِ منو پیش ازِ هندلر حالت را می‌شکست و تایپِ واژه هیچ‌وقت حذف را انجام نمی‌داد؛ `/cancel` هم از
  هندلرِ واژه بیرون نگه داشته شد. رویِ صفحهٔ بن‌بست دکمهٔ «بله» نمایش داده نمی‌شود.
- **خاموش‌کردنِ رباتِ زنده** (شکافِ پ۲۲): بعد ازِ `commit()` برایِ هر ربات
  `bot_manager.unregister(id, disable_in_db=False)` و `unregister_bale(id)` — هر کدام در
  `try/except`، تا خرابیِ یکِ `delete_webhook` حذف را نصفه نگذارد. الگو از `admin.py:cb_owner_suspend`.
- تازه‌ها: `AuditEventType.OWNER_SELF_DELETED` + برچسبِ فارسی + عضویتش در دستهٔ `shops` (تا جمعِ
  دسته‌ها با کلِ ردیف‌ها بخواند)، `AccountDeletionStates`، روترِ `account_delete` (پیش ازِ پنل و
  **بی‌دروازهٔ کانالِ اجباری**: بستنِ حساب نباید مشروطِ عضویتِ کانالِ بازاریابی باشد)، دو کیبورد.
  **بی‌مایگریشن** (هیچ ستونِ تازه‌ای لازم نشد؛ نوعِ رویداد رویِ `String(32)` است).
- **باگِ واقعیِ پیدا‌شده در همین فاز (پ۶۲):** `server_doctor._ready_to_alert()` «هنوز هشدار نشده» را
  با `0.0` می‌سنجید؛ `time.monotonic()` رویِ ماشین/VMِ تازه‌روشن خودش کمتر از ۳۶۰۰ است ⇒ اولین
  هشدارِ عیب‌یاب پس ازِ هر بوت بی‌صدا خفه می‌شد. سوئیتِ پ۶۴ نگرفتشان (آپ‌تایمِ بیش از یک ساعت)؛ این
  بار `test_p62_server_doctor.py::test_run_cooldown_and_recipients` با `sent == 0` شکست خورد. درمان:
  `None` به‌جایِ sentinel، + آزمونِ تازه با ساعتِ کاذب ⇒ نتیجه دیگر به آپ‌تایم وابسته نیست.
- **تغییرِ عمدیِ دو انتظارِ قدیمی (قاعدهٔ ۸، با دلیلِ ثبت‌شده در `changelog-p65.md`):**
  `test_customer_keyboard_layout.py` (`[2,2,2]` ⇒ `[2,2,2,1]`، چون دکمهٔ خطرناک ردیفِ تنهاست) و
  `test_identity_and_profile.py` (افزودنِ `acc_delete` به فهرستِ فعل‌هایِ صفحهٔ پروفایل).
- **MEASURED:** ۷ آزمونِ اختصاصی در `test_p65_account_deletion.py` (شمارش/مانع‌ها، هستهٔ قولِ
  «هویت می‌رود، سندِ مالی می‌ماند» با `row_hash` ثابت، صفر تغییر عندِ مانع، جریانِ واقعیِ پنل +
  خاموش‌شدنِ ربات + بسته‌شدنِ دروازهٔ ورود، صفحهٔ بن‌بست، نبودِ واژه در مجموعهٔ فرارِ منو + برچسبِ
  ممیزی، بودجهٔ ۶۴ بایتی و بی‌اثر ماندنِ فروشگاهِ دوم). اولینِ سوئیتِ این فاز ۱۴۵/۱۴۷ · ۹۳۳ بود که
  هر دو شکست بررسی و رفع شدند (یکی انتظارِ برچسبِ رویدادِ ممیزی، یکی باگِ `clock`).
  **سوئیتِ کاملِ نهایی: ۱۴۷/۱۴۷ فایل · ۹۳۹ تست · صفر fail · exit=0** رویِ ایمیج
  `8af57637d84b3dbe06b72c08735fa2d19289726900b66b2811b2fd7447e3a53d`؛ پنج گیت OK و `alembic heads`
  تک‌هدی همان `d3a8c1f5b742`. عددها در `TEST_RESULTS.md` §۴۹.
- **NOT RUN:** دیدنِ چشمیِ جریانِ حذف در تلگرام؛ رفتارِ واقعیِ `delete_webhook` رویِ حسابِ تلگرامیِ
  فروشگاه؛ سناریویِ «restore پس ازِ حذفِ خودخدمت» با هویتِ پاک‌شده (فقط در کد/مستند بحث شده).

## ۵۹) پ۶۶ — «🧮 گزارشِ جلسات» و «🎯 بازگشتِ مخاطب» در مودِ مشاوره‌ای (نیمهٔ دومِ موردِ ۲۴؛ ۲۰۲۶-۱۱-۱۳)

پ۵۸ درِ صفحه‌هایِ فروشگاهی را بست و صریح نوشت «جایگزینِ مشاوره‌ای مانده». این فاز همان جایگزین را
می‌سازد و بعدش نشتیِ کال‌بک‌هایِ داخلی را هم می‌بندد. **بی‌مایگریشن، بی‌وابستگی، بی‌دکمهٔ تازه در منو.**

- **داده:** `accounting_service.fetch_rows/build_report/count_pending_total` کلیدواژهٔ
  `consultation=True` گرفتند ⇒ فقط ردیف‌هایِ `type = consultation`. مسیرِ فروشگاهی عمداً بی‌فیلترِ نوع
  ماند (ادعایِ تستِ پ۱۸ و تستِ حسابداری همین است). `crm_service.load_stats` هم `exclude_blocked` گرفت
  — فقط برایِ شمارشِ مخاطبانِ «بازگشتِ مخاطب»؛ فهرستِ CRM و کارتِ مشتری برخلافش بلاک‌شده‌ها را نشان
  می‌دهند تا فروشگاه‌دار فراموش نکند بلاکش کرده است.
- **«🧮 گزارشِ جلسات»:** همان اعداد با سه تفاوتِ عمدی — واژهٔ «سفارش» حذف، «پرفروش‌ترین‌ها/عملکردِ
  کمپین» حذف، سه وضعیتِ فروش برچسبِ مشاوره‌ای می‌گیرند (`awaiting_customer_confirmation` ⇒
  «⏳ منتظرِ تاییدِ تو») و شمارشِ روزبه‌روز اضافه می‌شود. اکسلش سه برگه دارد (خلاصه/جلسه‌ها/روزانه).
- **«🎯 بازگشتِ مخاطب»:** پنج بخشِ `crm_service` با تعدادِ نفر ⇒ انتخابِ یکِ بخش ⇒ همان
  `CustomerBroadcastStates` با `broadcast_customer_ids` ⇒ پیش‌نمایش/تایید/زمان‌بندی/لغو. **منطقِ ارسال
  دوباره ساخته نشد**؛ سقفِ `AUDIENCE_LIMIT = ۲۰۰۰` گذاشته شد چون شناسه‌ها در JSONِ حالتِ FSM می‌مانند.
- **جایِ دکمه‌ها داخلِ «💬 گفتگوها و کاربران» است، نه منو:** چهار تستِ قدیمی
  (`test_p18_consultation_panel`، `test_crm`، `test_consultation_mode`،
  `test_customer_menu_and_prompts`) صریحاً ادعا می‌کنند «🧮 حسابداری/🎯 کمپین‌ها/👥 مشتری‌ها» در
  منویِ مشاوره *نباید* باشند. با این انتخاب آن ادعاها دست‌نخورده و همچنان درست می‌مانند و قاعدهٔ
  ۲-۶ (دکمهٔ منو + تستِ منو/RBAC) درگیر نشد.
- **نشتی‌هایِ بسته‌شده (۱۰ کال‌بک):** `acct:` و `acct_xlsx:` (مشاوره گزارشِ فروشگاهی و اکسلش را
  می‌دید)، پنج فعلِ `campaign_*` از جمله **تغییرِ وضعیتِ** کمپین و **حذفِ** آن، و چهار کال‌بکِ
  `cs_*` (گام‌هایِ چک‌اوت). پ۵۸ فقط *ورودی* را بسته بود.
- **دروازهٔ معکوس:** `require_consultation_mode(_cb)` + `MODE_CONSULTATION_ONLY` (متنش «به
  صفحه‌هایِ فروشگاهی برو» است، نه برعکس).
- **MEASURED:** ۸ آزمونِ اختصاصی در `test_p66_consultation_screens.py` — فیلترِ نوع (مشاوره ۲۱۰٬۰۰۰
  در برابرِ فروشگاهی ۷۱۰٬۰۰۰ در *همان* فروشگاه)، واژگانِ متن/اکسل + **برابریِ برگه‌ها و سرستون‌هایِ
  نسخهٔ فروشگاهی با قبل**، شمارشِ بخش‌ها و حذفِ دکمهٔ بخشِ خالی، دو جریانِ واقعیِ پنل با یکِ پاسخِ
  کال‌بک در هر تپ، دروازه‌هایِ دوطرفه با صفر ویرایشِ صفحه، ورودیِ خراب (بازهٔ ناشناخته ⇒ «امروز»)،
  و دست‌نخورده ماندنِ منو/`_KNOWN_MENU_BUTTONS`. ۱۹ فایلِ درگیرِ قدیمی هم جدا سبز شدند
  (`test_p58_mode_gates`، `test_accounting`، `test_p18_consultation_panel`، `test_p59_output_polish`،
  `test_p57_persian_digits`، `test_customer_broadcast`، `test_crm`، `test_campaign_owner_flow`،
  `test_campaigns`، `test_consultation_mode`، `test_customer_menu_and_prompts`، `test_p65_*`،
  `test_p48_*`، `test_orders_manage`، `test_p18_checkout_steps`، `test_checkout_c3`،
  `test_p18_per_shop_settings`، `test_campaign_checkout`، `test_phase6a_batching_and_settings`).
- **عددِ سوئیتِ کامل:** **MEASURED ۱۴۸/۱۴۸ فایل · ۹۴۷ تست · صفر fail · exit=0** رویِ ایمیج `98eed7c7a44b382bd5c8fd20d547db066cafdd369f48e21184195f46cd3071d5` و **MEASURED دوباره**: اجرایِ قبلیِ همین کد هم ۱۴۸/۱۴۸ و ۹۴۷ بود؛ فرقِ تنهاشان حذفِ یکِ `import` بی‌استفاده در فایلِ تست بود (دو اجرایِ میانی هم باطل شد، نه قرمز: دو `run_all_tests` هم‌زمان رویِ یکِ `kasbokar_test` ⇒ ۱۰۵/۱۴۸) (مبنایِ پ۶۵: ۱۴۷ فایل · ۹۳۹ تست ⇒ +۱ فایل، +۸ تست، صفر حذف). دو اجرایِ اولِ این فاز **باطل** شد، نه قرمز: سوئیت را *هم‌زمان* با یکِ سوئیتِ دیگرِ همان دیتابیسِ تست گرفتم (۱۰۵/۱۴۸ و ۷۴۹ تست) ⇒ با `docker rm -f` کانتینرِ مزاحم بسته شد و سوئیتِ تنها گرفته شد؛ عددِ بالا مالِ همان اجرایِ تنهایی.
- **NOT RUN:** دیدنِ چشمیِ دو صفحه در تلگرام؛ ارسالِ واقعیِ پیامِ بخش‌محور به مخاطبِ زنده؛ بازکردنِ
  فایلِ اکسلِ «جلسه‌ها» در Excel/LibreOffice (ساختار با openpyxl خوانده شد، نه با چشم).

## ۶۰) پ۶۷ — «🧾 پروندهٔ کاملِ کاربر» در پنلِ ادمین (نیمهٔ بازِ موردِ ۲۷/۴۱؛ ۲۰۲۶-۱۱-۱۳)

ادامهٔ پ۶۵: خواستهٔ «مدیریتِ جامعِ کاربران» هنوز باز بود. اطلاعاتِ یکِ فروشگاه‌دار در چهار صفحه پخش
بود (مدیریتِ فروشگاه‌دارها = سه خط / مصرفِ کاربران = به‌ازایِ مشتری / کاربرانِ غیرفعال = دیدار و حذف /
اعتبار و زمان = گروهی). این فاز آن جمع را در یکِ نما می‌آورد.

- `app/services/owner_dossier_service.py`: `build()` + `recent_audit()`. هویت (موبایل ماسک‌شده،
  بدونِ نشتِ آیدیِ عددیِ تلگرام)، اتصال‌ها (تلگرام + ثبت/پاک‌بودنِ توکن، بله، اینستاگرام با mute،
  درگاه‌ها، کانالِ دانش، پشتیبانی)، پول (موجودی، قابلِ مصرف، کمیسیونِ قفل‌شده، بدهیِ بازِ مصرف،
  پرداخت‌هایِ تاییدشده)، اشتراک (وضعیت/پایان/روزهایِ مانده + «قابلِ استفاده با مهلت» از
  `subscription_service.is_shop_usable`)، مصرفِ AIِ **خودِ فروشگاه‌دار** در ۳۰ روز (جمعِ
  `wallet_transactions` رویِ `shop_owner_id` — این عدد هیچ‌جا نبود)، و فعالیت (مشتری‌ها، سفارش‌ها،
  سفارشِ باز، کمپینِ فعال، گزارشِ بازِ نگهبانِ محتوا، ردیف‌هایِ ممیزی + پنج رویدادِ آخر).
- **فقط‌خواندنی، با عدد:** صفر `INSERT/UPDATE/DELETE` و حداکثر ۱۶ `SELECT` (دو جمعِ تجمیعی به‌جای
  چهار جمله؛ `recent_audit` هم شناسهٔ ربات را *می‌گیرد* تا `shop_owners`/`shop_bots` را دوباره
  نخواند).
- `handlers/admin_dossier.py` (روترِ `IsAdmin` + دامنه): `owner_dossier:{id}` از کارتِ جزئیات،
  `owner_dossier_refresh:{id}`، `owner_dossier_extend:{id}`؛ پارسِ ایمنِ شناسه ⇒ ورودیِ
  دست‌کاری‌شده فقط توست و صفر ویرایش.
- **فعل‌ها بازسازی نشدند:** کیبورد فقط دکمه‌هایِ موجود را کنارِ هم می‌چیند
  (`admin_owner_suspend/unsuspend/gift/wallet_correction` + برایِ سوپرادمین `inact_deactivate/restore/purge`)
  ⇒ همان ممیزی، همان چکِ سوپر، همان `bot_manager.unregister`. ادمینِ عملیاتی `inact_*` نمی‌بیند.
- **تنها فعلِ تازه: تمدیدِ روز برایِ یکِ حساب** (تا پیشِ این فقط گروهی بود): همان
  `subscription_service.extend_by_days` با سقف‌هایِ `credit_batch_service` + رویدادِ ممیزیِ تازهٔ
  `SUBSCRIPTION_EXTENDED` با `shop_bot_id`. رویِ حسابِ بسته‌شده تمدید نمی‌کند.
- **بی‌دکمهٔ منو** ⇒ `test_admin_rbac` (تساویِ مجموعهٔ دکمه‌هایِ منو) و
  `test_customer_keyboard_layout` دست‌نخورده. **بی‌مایگریشن** (نوعِ ممیزی رویِ `String(32)`).
- **MEASURED:** ۹ آزمونِ اختصاصی در `test_p67_user_dossier.py` و ۱۳ فایلِ درگیرِ قدیمیِ جدا
  (شاملِ `test_p24_dead_buttons_and_scope` که `check_callbacks.main()==0` را می‌سنجد و
  `test_p22_export_beautification` که برچسبِ فارسیِ هر نوعِ رویدادِ ممیزی را).
- **عددِ سوئیتِ کامل:** **MEASURED ۱۴۹/۱۴۹ فایل · ۹۵۶ تست · صفر fail · exit=0** رویِ ایمیج `c88f6048b8c8eaa34082ba408e80eb538fb12a5011f0c4a2c0c7c2262d973076` (مبنایِ پ۶۶: ۱۴۸ فایل · ۹۴۷ تست ⇒ +۱ فایل، +۹ تست، صفر حذف؛ تنها اجرایِ این فاز، پس ازِ buildِ نهایی و بدونِ هیچ کارِ موازی)
- **NOT RUN:** دیدنِ چشمیِ کارتِ پرونده در تلگرام؛ زمانِ پاسخِ این صفحه رویِ دیتابیسِ پُرداده.

## ۶۱) پ۶۸ — «🗺 استان» و «🏙 شهر» خاموش‌شدنی در چک‌اوت، با پیش‌فرضِ «نپرس» (موردِ ۱۹؛ ۲۰۲۶-۱۱-۱۳)

موردِ ۱۹ از صفِ extra-high بود چون گرافِ مراحلِ پرداخت را لمس می‌کند. درخواستِ مالک: «گزینهٔ حذف در پنل +
پیش‌فرض «نپرسد»». گامِ «آدرس» چهار پرسش پشتِ هم داشت (استان ← شهر ← آدرسِ کامل ← کدپستی) درحالی‌که
`province`/`city` هیچ‌جای دیگری از محصول خوانده نمی‌شدند (فقط `format_address` و `short_label`).

- **بدونِ مایگریشن:** دو کلیدِ `province` و `city` به همان JSONِ `shop_bots.checkout_config` اضافه شد و
  `checkout_config_service.DEFAULT_ENABLED` تعیین می‌کند کدام گام پیش‌فرض خاموش است. `dump()` وقتی همه
  با پیش‌فرض‌اند همان `None` را می‌نویسد، پس «پیش‌فرضِ جدید» و «هرگز دست‌نزده» یکی‌اند و دادهٔ قدیمی
  مهاجرت نمی‌خواهد.
- **گرافِ آدرس از جدولِ ثابت به زنجیره تبدیل شد:** `checkout_flow.address_chain/address_first/address_next`
  با `disabled` کار می‌کنند؛ «آدرسِ کامل» و «کدپستی» کلیدِ پیکربندیِ ندارند، پس زنجیره همیشه دستِکم دو
  عضو دارد و هیچ حالتی نیست که گامِ آدرس بی‌پرسش بماند. فریزِ پیکربندی در `ck_disabled` مثلِ قبل است،
  پس تغییرِ تنظیمِ وسطِ چک‌اوت، مسیرِ نیمه‌کاره را نمی‌شکند.
- **صادق‌بودنِ متن:** `checkout_ui.region_hint(missing)` فقط همان چیزی را یادآوری می‌کند که پرسیده نمی‌شود
  (هر دو خاموش ⇒ «استان و شهر…»؛ فقط شهر ⇒ «شهر…»). با هر دو روشن، هیچ راهنمایی اضافه نمی‌شود و
  `ASK_ADDRESS_TEXT` هم دست‌نخورده ماند.
- **دفترچه‌آدرس:** `add_address` حالا `province`/`city`یِ `None` می‌پذیرد (ستون‌ها از قبل nullable) و
  `label` را از شهرِ خالی نمی‌سازد. آدرس‌هایِ قبلی که region دارند دست‌نخورده نمایش داده می‌شوند.
- **پنل:** همان «🧾 گام‌هایِ پیش‌فرضِ چک‌اوت» با دو ردیفِ تازه + توضیحِ `CHECKOUT_STEP_REGION_HINT`.
  بی‌دکمهٔ منویِ تازه ⇒ تستِ منو/RBAC دست‌نخورده. قاعدهٔ «آدرس+موبایل هم‌زمان خاموش نشود» بدونِ تغییر.
- **MEASURED:** ۹ آزمونِ اختصاصی در `test_p68_checkout_province_city.py` (منطقِ خالصِ پیکربندی، گرافِ
  زنجیره در چهار ترکیب، راهنما، پنل و بازگشتِ ستون به خالی، و پنج جریانِ واقعیِ مشتری: پیش‌فرضِ
  بی‌region با بررسیِ ردیفِ دیتابیس، زنجیره‌یِ کامل با روشن‌کردن، استان روشن/شهر خاموش، سبدِ دیجیتال،
  آدرسِ دفترچه‌ایِ دارایِ region) + سبزِ چهار فایلِ درگیرِ قدیمی.
- **تغییرِ عمدیِ رفتار (نه باگِ تست‌ها):** پیش‌فرضِ محصول عوض شد، پس چهار فایلِ قدیمی بازبینی شد:
  `checkout_helpers.py` (پارامترِ `region_steps`)، `test_checkout_c3.py` (سه تستِ زنجیره‌یِ کامل با
  `_region_on` و سه جریانِ دیگر رویِ مسیرِ کوتاه)، `test_p18_checkout_steps.py` (دو پیکربندیِ region
  روشن + جدولِ پیش‌فرض‌هایِ هفت‌گامی)، `test_shopping_cart.py` (شمارشِ پیام‌ها ۱۱←۹ و ۱۰←۸، حذفِ دو
  «تهران» و «تهران»ِ اعلانِ فروشگاه‌دار ← متنِ آدرس). هیچ ادعایی ضعیف نشد: همان رفتار در پیکربندیِ
  روشن هنوز سنجیده می‌شود.
- **عددِ سوئیتِ کامل:** **MEASURED ۱۵۰/۱۵۰ فایل · ۹۶۵ تست · صفر fail · exit=0** (مبنایِ پ۶۷: ۱۴۹ فایل ·
  ۹۵۶ تست ⇒ +۱ فایل، +۹ تست، صفر حذف) — تنها اجرایِ این فاز، پس ازِ buildِ نهایی و بدونِ هیچ کارِ موازی.
- **NOT RUN:** دیدنِ چشمیِ چک‌اوتِ کوتاه‌شده و صفحهٔ پنل در تلگرام/بله؛ سنجشِ واقعیِ اثرِ این تغییر بر
  رها‌کردنِ سبد (داده نداریم)؛ اطلاع‌رسانیِ انبوه به فروشگاه‌داران که عمداً فرستاده نشد (قاعدهٔ ۹).

## ۶۲) پ۶۹ — ثبتِ توکنِ واقعیِ هر فراخوانیِ AI + صفحهٔ «💸 برآوردِ هزینهٔ واقعی» (موردِ ۳۶؛ ۲۰۲۶-۱۱-۱۳)

موردِ ۳۶ می‌گفت «تخمینِ هزینه مبتنی بر پرامپتِ سیستمی و تجربهٔ واقعی + رابط». تا این نسخه
`usage.total_tokens` فقط *مصرف* می‌شد (همان لحظه برایِ کسر) و هیچ‌جا ثبت نمی‌شد، پس هیچ‌کس نمی‌توانست
بگوید فرضِ قیمت‌گذاری درست است یا نه.

- **مایگریشنِ افزودنیِ `e1b7c9d4a205`:** `wallet_transactions.ai_total_tokens` (nullable) + ایندکسِ
  جزئی `(created_at, reason) WHERE ai_total_tokens IS NOT NULL`. توکن رویِ **اولین ردیفِ** کسر
  می‌نشیند تا کسرِ چندبسته‌ای دوباره شمرده نشود؛ بی‌AI‌ها، مسیرِ صوت و ردیف‌هایِ قدیمی `NULL`
  می‌مانند ⇒ بدونِ بک‌فیلِ ساختگی. **صفر جملهٔ اضافه در مسیرِ پیام** (همان INSERT).
- `app/services/ai_cost_service.py`: `AI_REASONS` (هشت دلیلِ مصرفِ AI)، `observe()` با **یکِ
  GROUP BY** (تعداد/تعدادِ اندازه‌گرفته/جمعِ توکن/گرفته‌شده/گرفته‌شدهٔ اندازه‌گرفته)، `CostView`
  (میانگینِ توکن، گرفته‌شده به‌ازایِ هر ۱۰۰۰ توکن = MEASURED، هزینهٔ خام = EXTRAPOLATED،
  `margin_ratio()`، `coverage`) و `prompt_floor_tokens()` که **کفِ پرامپتِ سیستمی** را از خودِ
  `ai_context.build_system_prompt` می‌خواند و با `CHARS_PER_TOKEN=3.5` تخمین می‌زند (ESTIMATED).
- پنلِ سوپرادمین «💸 برآوردِ هزینهٔ واقعیِ AI» داخلِ «💰 تنظیمات قیمت و تخفیف» با بازه‌هایِ ۷/۳۰/۹۰
  روزه + سه عددِ قیمت (فعلی، خام، پیشنهادِ همان فرمولِ «محاسبهٔ خودکار») + یادداشتِ پوشش.
  **هیچ مبلغی را عوض نمی‌کند** — تصمیمِ قیمت با ادمین است.
- ارقامِ صفحه کاملاً جلالی (ادعای «صفر رقمِ لاتین»، نه «کمتر از قبل») و بی‌وابستگیِ تازه.
- **MEASURED:** ۷ آزمونِ اختصاصی در `test_p69_ai_cost_estimate.py` (پیش‌فرض‌هایِ پرامپت، ریاضِ
  `CostView`، جلالی‌بودن، ثبتِ یک‌بارهٔ توکن در کسرِ پخش‌شده، پنجره/گروه‌بندیِ `observe`،
  صفحه + بازهٔ دست‌کاری‌شده، انکارِ دسترسیِ ادمینِ عملیاتی).
- **عددِ سوئیتِ کامل:** **MEASURED ۱۵۱/۱۵۱ فایل · ۹۷۲ تست · صفر fail · exit=0** رویِ ایمیج
  `0017cb1ea672d54d1cb8d4b63ab890bd5001f58524a7e0f7fc4c4fbc6d6058fb` (مبنایِ پ۶۸: ۱۵۰ فایل ·
  ۹۶۵ تست ⇒ +۱ فایل، +۷ تست، صفر حذف؛ تنها اجرایِ این فاز، پس ازِ buildِ نهایی و بدونِ هیچ کارِ موازی)
- شرحِ کامل: `docs/changelog-p69.md`.
- **NOT RUN:** راستی‌آزماییِ `usd_to_toman_rate` و `ai_cost_usd_per_1m_tokens` با صورتحسابِ واقعیِ
  ارائه‌دهنده؛ دیدنِ چشمیِ صفحه در تلگرام؛ تفکیکِ input/output توکن (ارائه‌دهنده فقط total می‌دهد).

## ۶۳) پ۷۰ — «📈 پرمصرف‌هایِ AI» در پنلِ فروشگاه‌دار + تفکیکِ فروشگاه در پنلِ ادمین (+ دو باگِ واقعی) (۲۰۲۶-۱۱-۱۴)

یادآوریِ مالک: این قابلیت باید در پنلِ *خودِ* فروشگاه‌دار (فروشگاهی و مشاوره‌ای) باشد و در پنلِ ادمین
«به تفکیکِ فروشگاه» دیده شود. همان پیام دو گزارشِ UX هم داشت: دکمهٔ دومِ عیب‌یاب که «تازه‌سازی»
نام داشت ولی به پنلِ ظرفیت می‌رفت.

- `ai_usage_service.rank_page(..., shop_bot_id=None)`: joinِ اختیاری رویِ همان جمله ⇒ بی‌فیلتر
  **کوئریِ دقیقاً قبلی** است (پ۵۵ بدونِ تغییر سبز ماند) و با فیلتر فقطِ مشتریانِ همان فروشگاه.
- **پنلِ صاحبِ فروشگاه** (`handlers/owner_ai_usage.py` + کلیدهایِ `ouai_*`): ورودی از «👥 مشتری‌ها»
  و از «💬 گفتگوها و کاربران» (مودِ مشاوره‌ای)؛ فهرستِ پرمصرف‌ها با سه پنجره، کارتِ جزئیات و
  سه اهرمِ سقفِ ۲۴ ساعت (FSMِ تازهٔ `OwnerAiUsageStates`)، توقفِ پاسخِ خودکار، بلاک/رفعِ بلاک.
  هر فعل از `crm_service.get_owned_customer` می‌گذرد ⇒ شناسهٔ دست‌کاری‌شدهٔ فروشگاهِ دیگر = توست،
  صفر ویرایش و **ورود نکردن به FSM**؛ بلاک با همان `CUSTOMER_BLOCK_CHANGED` و سقف/توقف با نوعِ تازهٔ
  `AI_USAGE_CONTROL_CHANGED` (رویِ `String(32)` ⇒ بی‌مایگریشن). بی‌دکمهٔ کیبوردِ اصلی ⇒ منو و RBAC
  دست‌نخورده. صفر جابه‌جاییِ پول.
- **پنلِ ادمین:** کارتِ هر کاربر دکمهٔ «🏪 فقطِ این فروشگاه» گرفت (`ai_usage_shop:{id}`)؛ خطِ
  «🏪 فیلتر: فقطِ مشتریانِ فروشگاهِ @…» رویِ فهرست و «🌐 همهٔ فروشگاه‌ها» هم در نمایِ پُر و هم در
  نمایِ *خالی* (تا ادمین گیر نکند). فیلتر با تغییرِ پنجره/صفحه می‌ماند و قاعدهٔ پ۶۴ (پاک‌کردنِ
  حالتِ «در انتظارِ ورودی» در هر ناوبری) حفظ شده.
- **باگِ ۱ (بازمانده از پ۵۵):** کیبوردِ «🚫 بلاکِ کاربر» هدفِ وارونه می‌فرستاد ⇒ دکمه هرگز بلاک نمی‌کرد
  (و «رفعِ بلاک» هرگز رفع نمی‌کرد). تستِ پ۵۵ نگرفتشان چون payload را دستی می‌زد و در تستِ کیبورد
  همان مقدارِ وارونه را pin کرده بود. اصلاح شد و ادعایِ تازهٔ پ۷۰: *برچسبِ دکمه و هدفش باید یکی
  باشد* (هر دو وضعیت، هم ادمین هم فروشگاه‌دار).
- **باگِ ۲ (کاربری):** «🔄 تازه‌سازی» رویِ صفحهٔ عیب‌یاب در واقع پرش به پنلِ ظرفیت بود. مقصد مفید
  ماند و برچسب نامِ مقصد را گرفت (`DOCTOR_OPEN_CAPACITY` = «📡 ظرفیت و فشارِ سرور»)؛ حالا رویِ
  عیب‌یاب فقط یکِ «تازه‌سازی» هست. تستِ پ۶۲ هر دو ادعا را می‌سنجد.
- **MEASURED:** ۵ آزمونِ اختصاصی در `test_p70_ai_usage_per_shop.py` (فیلترِ سرویس، پنلِ صاحبِ
  فروشگاه با سه اهرم + ممیزی + ورودیِ بدِ FSM + ردِ مالکیت + صفرِ جابه‌جاییِ پول، ورودیِ مودِ
  مشاوره‌ای، رفت‌وبرگشتِ فیلترِ ادمین، شکلِ کیبورد و بودجهٔ ۶۴ بایتی) و ۹ فایلِ درگیرِ قدیمیِ سبز
  (`test_p55` با ادعایِ اصلاح‌شده، `test_p62`، `test_crm` با ردیفِ تازهٔ کیبورد، `test_admin_rbac`،
  `test_p22_export_beautification`، `test_p57_persian_digits`، `test_p56_search`، `test_p67_user_dossier`،
  `test_p24_dead_buttons_and_scope`).
- **گیت‌ها:** OK — ۳۳۶ فایل · ۳۸۱ شکلِ `callback_data` (هفت کلیدِ تازهٔ `ouai_*` + `ai_usage_shop:`
  همه مصرف‌کننده دارند) · ruff تمیز · تک‌هدِ مایگریشن (`e1b7c9d4a205`).
- **عددِ سوئیتِ کامل:** **MEASURED ۱۵۲/۱۵۲ فایل · ۹۷۷ تست · صفر fail · exit=0** رویِ ایمیج
  `d3b27cfdfdd33b629858183cef993e9490ce90015692d691fd08e9399e8cb22e` (مبنایِ پ۶۹: ۱۵۱ فایل ·
  ۹۷۲ تست ⇒ +۱ فایل، +۵ تست، صفر حذف؛ تنها اجرایِ این فاز، پس ازِ buildِ نهایی و بدونِ هیچ کارِ موازی)
- **NOT RUN:** دیدنِ چشمیِ هر دو صفحه در تلگرام/بله؛ راستی‌آزماییِ اینکه چه تعداد بلاکِ ادمینی در
  گذشته بی‌اثر مانده (بک‌فیل نشد — قابلِ بازیابی نیست).

## ۶۴) پ۷۱ — فاکتورِ PDFِ چندصفحه‌ای با پاورقیِ «صفحهٔ X از Y» (موردِ ۳۴-پ؛ ۲۰۲۶-۱۱-۱۴)

باقی‌ماندهٔ موردِ ۳۴ بود و در واقع یکِ باگِ پنهان: `invoice_service` از P18 اقلام را در **۴۰ قلم
می‌برید** و «… و N قلمِ دیگر» می‌نوشت — یعنی فاکتورِ ۶۰ قلمیِ مشتری بیست قلم نداشت، درحالی‌که
جمعِ کل از همهٔ قلم‌ها حساب می‌شد.

- **دو گذر، نه یکِ گذر:** گذرِ اول تعدادِ صفحه را می‌شمارد، گذرِ دوم همان چیدمان را با «صفحهٔ X از Y»
  مهر می‌کند. دلیل: fpdf2ِ ۲.۹.۰ این محیط `set_page` ندارد (نمی‌شود بعد ازِ رندر رویِ صفحه‌هایِ
  قبلی نوشت) و `{nb}` داخلِ متنِ شکل‌داده‌شده (reshaper + bidi) نه جایگزینی‌اش مطمئن است نه
  جلالی‌ماند. امن بودنِ این روش یکِ شرط دارد: چیدمان مستقل از پاورقی باشد — هست، چون پاورقی در
  نوارِ ثابتِ پایین (`_PDF_FOOTER_BAND = 16mm`) نوشته می‌شود و `get_y()` را جلو نمی‌برد؛
  `test_two_pass_page_count_is_stable` همان شرط را برایِ ۱/۲۴/۲۵/۲۶/۴۰/۴۱/۶۰/۹۷ قلم می‌سنجد.
- `set_auto_page_break` **خاموش** شد و شکستنِ صفحه دستی است (`new_page()`): قبلِ هر صفحهٔ تازه
  پاورقیِ صفحهٔ در‌شرفض ترک مهر می‌شود، سرِجدول تکرار می‌شود، و کادرِ جمع‌ها (۴۶mm) اگر جا نباشد
  به صفحهٔ بعد می‌رود تا «جمعِ کل» و برچسبِ پرداخت از هم جدا نیفتند.
- پاورقی: خطِ نازک + «صفحهٔ X از Y» با `fa_number` (ارقامِ جلالی، سمتِ چپ) و رویِ صفحهٔ آخر دو خطِ
  «این فاکتور رایانه‌ای…» و «صادرشده با…» (راست‌چین) ⇒ برخوردِ متنی نیست.
- سقفِ دفاعی ۴۰ ← **۳۰۰** قلم (محافظِ زمان/حافظه، نه بریدنِ عادی).
- **MEASURED با pymupdf (بیرون از سوئیت):** فاکتورِ ۶۰ قلمی = ۳ صفحه با ۲۵/۳۲/۳ قلم و هر ۶۰
  برچسبِ `ITEM-001…ITEM-060` در متنِ استخراجی ⇒ هیچ قلمی جا نیفتاده؛ صفحهٔ ۲ «صفحهٔ ۲ از ۳» و
  صفحهٔ ۳ دو خطِ توضیح + «صفحهٔ ۳ از ۳». فاکتورِ ۳ قلمی هنوز ۱ صفحه. سه صفحه به‌صورتِ تصویر هم
  دیده شد (چینشِ جدول، سرِجدولِ تکراری و جایِ پاورقی).
- **MEASURED:** ۵ آزمونِ اختصاصی در `test_p71_invoice_paging.py` + `test_p18_pdf_invoice` (۷ تست،
  شاملِ fallback به HTML و نامِ ۴۰۰ کاراکتری) بدونِ تغییرِ ادعا سبز.
- **عددِ سوئیتِ کامل:** **MEASURED ۱۵۳/۱۵۳ فایل · ۹۸۲ تست · صفر fail · exit=0** رویِ ایمیج
  `58f68b7536f1d220768ec20ba71c9046f338b2c19b945adbd69b79f19518b972` (buildِ همین فاز) (مبنایِ پ۷۰: ۱۵۲ فایل · ۹۷۷ تست ⇒ +۱ فایل، +۵ تست، صفر حذف).
  پاک‌سازیِ پایانیِ همان فایل (حذفِ یکِ ثابتِ بی‌مصرف و دو اصلاحِ کامنت) رویِ ایمیجِ نهایی
  `6139a714f6dab8fdd633ac3fd0b01855bdc1438e322431bbda7035b8daabfd2d` با اجرایِ دوبارهٔ
  `test_p18_pdf_invoice` (۷/۷) و `test_p71_invoice_paging` (۵/۵) تأیید شد؛ سوئیتِ کاملِ ۱۵۳تایی
  رویِ ایمیجِ پیش ازِ آن پاک‌سازیِ کاملاًِ ظاهری گرفته شد.
- **NOT RUN:** چاپِ واقعی رویِ چاپگرِ لیزری/AFS؛ فاکتورِ چندصد قلمیِ واقعیِ یکِ فروشگاه؛ دیدنِ
  چشمیِ فایلِ دریافتی در تلگرام/بله؛ فاکتورِ HTML (مسیرِ fallback) هنوز بی‌شمارهٔ صفحه است.

## ۶۵) پ۷۲ — آستانه‌هایِ تنظیم‌شدنیِ عیب‌یاب + پنجرهٔ زمانیِ شمارنده‌ها (ایجنتِ سرور راند ۲؛ ۲۰۲۶-۱۱-۱۴)

**خواستهٔ مالک (۲۰۲۶-۱۱-۱۲، ادامهٔ «ایجنتِ در حالِ کار در محیطِ سرور»):** عددی که «بد است یا نه» را
تعیین می‌کند نباید در کد قفل باشد، و شمارنده‌ها نباید «از شروعِ پروسه» قضاوت شوند.

**چه ساخته شد:**
- `server_doctor.THRESHOLD_SPECS`: یازده کلید با `(پیش‌فرض، کرانِ پایین، کرانِ بالا، نوع، برچسبِ فارسی)`؛
  پیش‌فرضِ هر کلید **عیناً** عددِ پ۶۲ است ⇒ نصبِ موجود هیچ تغییرِ رفتاری حس نمی‌کند و تستِ پ۶۲ بدونِ
  تغییرِ ادعا سبز ماند.
- ستونِ افزودنیِ `admin_settings.doctor_thresholds` (JSONِ «تفاوت با پیش‌فرض»، خالی = همه پیش‌فرض) با
  مایگریشن `f2c5b9a1d340` (مادر `e1b7c9d4a205`، تک‌هد، nullable). `parse_thresholds` در برابرِ JSONِ
  خراب/کلیدِ ناشناخته/عددِ غیرعدد به پیش‌فرض برمی‌گردد و بیرونِ کران را به نزدیک‌ترین کران می‌چسباند؛
  `dump_thresholds` فقط تفاوت‌ها را می‌نویسد.
- پنلِ سوپرادمین: «⚖️ آستانه‌هایِ عیب‌یاب» در صفحهٔ 🩺 ⇒ فهرستِ یازده‌ردیفه با پرچمِ «(خودت)» ⇒ ویرایشِ
  هر کلید با FSM (`DoctorThresholdStates.waiting_value`) ⇒ ورودیِ بیرونِ کران = پیامِ خطا و **ماندنِ
  حالت** ⇒ ذخیره + ممیزیِ `ADMIN_SETTING_CHANGED` ⇒ «♻️ بازگشت به همهٔ پیش‌فرض‌ها» (ستون ⇒ NULL، نه صفرها).
  کلیدِ دست‌کاری‌شده ⇒ توست و صفر نوشتن؛ اپراتورِ عملاتی ⇒ صفر پیام و صفر ویرایش.
- `window_deltas`: شمارنده‌ها حالا **تفاضلِ پنجره** (`window_minutes`، پیش‌فرض ۶۰دقیقه، کران ۵ تا ۱٬۴۴۰)
  با آستانه مقایسه می‌شوند و یافته برچسب می‌گیرد («در N دقیقهٔ گذشته» / «از شروعِ این پروسه»). دو
  محافظ: snapshotِ کهنه‌تر از دو پنجره ⇒ جمعِ کل؛ شمارندهٔ پایین‌تر از snapshot (ری‌استارت) ⇒ صفر،
  نه عددِ منفی.
- **باگِ واقعیِ همین‌جا:** `_thresholds` برایِ دیسک هنوز ثابتِ `DISK_ALERT_PERCENT` را می‌خواند، پس
  آستانهٔ ۹۵٪ ادمین رویِ دیسک بی‌اثر بود. اصلاح شد و تستِ دوطرفه قفلش کرد (۷۰٪⇒۸۰٪ پیدا شود،
  ۹۵٪⇒۹۰٪ پیدا نشود). ورودیِ عددی هم دقیق‌تر شد: «٫» و «.» ممیز، ویرگول (نیمه‌تمام/لاتین) جداکنندهٔ
  هزار.

**هزینه و مرز:** یکِ `SELECT` رویِ `admin_settings` در هر بازرسی (همان کشِ ۳۰ ثانیه‌ایِ مسیرهایِ دیگر)؛
صفر فراخوانِ AI؛ صفر تماس با مسیرِ پیامِ مشتری و صفر جابه‌جاییِ پول. عیب‌یاب هنوز **فقط تشخیص** می‌دهد
و هیچ اقدامی نمی‌کند؛ آستانه‌ها فقط حساسیتِ *تشخیص* را عوض می‌کنند (همین استثنا در داک‌استرینگِ
`admin_capacity.py` نوشته شد تا ادعایِ «فقط‌خواندنی» گمراه‌کننده نماند).

**عددِ تست:** `tests_manual/test_p72_doctor_thresholds.py` — **MEASURED ۸/۸ · exit=0** (MEASURED).
`test_p62_server_doctor.py` به‌روز شد (امضاهایِ خصوصیِ جدید + ادعایِ نوشتنِ دقیق‌تر) — **MEASURED ۸/۸**.
**سوئیتِ کامل: MEASURED ۱۵۴/۱۵۴ فایل · ۹۹۰ تست · صفر fail · exit=0** رویِ ایمیج
`10f711ea4c8d4c7de002ce0b223613904b8478647548dcc0b8ef069b978c07bd` (buildِ همین فاز، پس ازِ گیت‌ها و
بدونِ هیچ کارِ موازی؛ مبنایِ پ۷۱: ۱۵۳ فایل · ۹۸۲ تست ⇒ +۱ فایل، +۸ تست، صفر حذف).
پنج گیت + ruff: **OK · ۳۳۹ فایل · ۳۸۴ شکلِ `callback_data`** (هر سه شکلِ `doctor_thr*` مصرف‌کننده دارند).

**مستندات:** `docs/changelog-p72.md` · `TEST_RESULTS.md` §۵۶ · `REMAINING_ISSUES.md` §پ۷۲ ·
`docs/admin-guide.md` (زیربخشِ «⚖️ آستانه‌هایِ عیب‌یاب» + اصلاحِ بندِ ۱ِ عیب‌یاب).

**NOT RUN:** دیدنِ چشمیِ صفحه‌ها در تلگرام/بله؛ تغییرِ آستانه رویِ سرورِ واقعی و صبر برایِ جابِ
۳۰ دقیقه‌ای؛ و درستیِ کرانهایِ پیش‌فرض برایِ سخت‌افزارِ واقعیِ مالک.

## ۶۶) پ۷۳ — رویدادِ کامنتِ اینستاگرام + «🗨 گزارشِ کامنت‌ها» در پنلِ فروشگاه‌دار (مواردِ ۱۱-۱۲؛ ۲۰۲۶-۱۱-۱۴)

**خواستهٔ مالک (۲۰۲۶-۱۱-۱۲، حلقهٔ سومِ اینستاگرام):** «گزارشِ کامنت‌ها (چند کامنت آمد، به چندتا جواب
دادیم، خرجِ AIِ کامنت‌ها) و معیارِ چه‌چیزی را جواب ندهیم». پ۶۳ صریح گفته بود کامنت‌ها ذخیره نمی‌شوند،
پس سه سوالِ اول بی‌جواب بود — این فاز همان شکست را بست و حلقهٔ چهارم (فهرستِ «جواب نده») را باز گذاشت.

**چه ساخته شد:**
- جدولِ افزودنیِ `instagram_comment_events` (مایگریشن `a3d7c8e2b510`، مادر `f2c5b9a1d340`، تک‌هد):
  `shop_bot_id`، `comment_id`، `media_id`، `username`، `text` (تا ۱٬۲۰۰ نویسه)، `comment_created_at`،
  `outcome` (`received`/`replied`/`skipped`/`failed` با `server_default="received"`)، `reason`،
  `ai_tokens`، `cost_toman`، `created_at` + `unique (shop_bot_id, comment_id)` + ایندکسِ
  `(shop_bot_id, created_at)`.
- `record_comment` **پیش ازِ درهایِ حسابی** در `_handle_comment` صدا زده می‌شود تا کامنتِ ردشده هم
  شمرده شود؛ داخلِ `begin_nested()` است و سه حالت دارد: ردیفِ تازه / `(ردیف, True)` برایِ ردیفِ
  رسیدگی‌شده (**dedupِ پایدار** — `claim_event` فقط درونِ یکِ پروسه یکتاست و دوباره‌ارسالِ متا بعد ازِ
  ری‌استارت می‌توانست یکِ کامنت را دو بار جواب بدهد و دو بار هزینه بسازد) / `(None, False)` برایِ
  خطایِ نوشتن ⇒ پاسخگویی مثلِ دیروز ادامه می‌یابد.
- `mark_comment` نتیجه را در ۱۲ نقطهٔ خروج ثبت می‌کند: `account_off`، `comments_off`، `muted`،
  `shop_inactive`، `no_owner`، `moderation_block`، `no_ai_key`، `no_ai_pool`، `no_access`،
  `empty_reply` و دو `failed` (`ai_error`، `send_failed`). در مسیرِ موفق `ai_tokens` توکنِ واقعیِ
  سرویس‌دهنده و `cost_toman` **همان مبلغی است که از کیف‌پول کم می‌شود** (تستِ ۳ دو عدد را مقایسه
  می‌کند) ⇒ صفر تخمینِ دوم، صفر جابه‌جاییِ پولِ اضافه.
- پنلِ خودِ فروشگاه: دکمهٔ «🗨 گزارشِ کامنت‌ها» (فقط با اتصال) ⇒ جمعِ پنجره (۲۴س/۷ر/۳۰ر)، خرجِ AIِ
  همان کامنت‌ها، تفکیکِ دلیل‌هایِ جواب‌نرفتن به‌فارسی، فهرستِ ۱۰تایی با صفحه‌گردانی، و خطِ صادقِ
  «این شمارش از همین نسخه به این سو است». `ig_cmt:{window}:{page}` (بلندترین ۱۲ بایت)؛ بازه/صفحهٔ
  خراب ⇒ توست و صفر ویرایش؛ بدونِ اتصال و غریبه ⇒ توستِ خودِ گاردها.

**هزینه:** یکِ `INSERT` + یکِ `UPDATE` به‌ازایِ هرِ کامنت در مسیرِ وب‌هوکِ متا (بی‌اثر بر مسیرِ پیامِ
مشتریِ تلگرام/بله)؛ صفحهٔ گزارش سه `SELECT`. هیچ فراخوانِ AI اضافه نشده است.

**عددِ تست:** `tests_manual/test_p73_instagram_comment_report.py` — **MEASURED ۷/۷ · exit=0**.
`test_p49_b_instagram_comments` (۷/۷) و `test_p63_instagram_management` (۷/۷) **بدونِ تغییرِ هیچ ادعا**
سبز ماندند (درِ سراسری هنوز «بی‌کوئری» است، چون ثبتِ رویداد *پس ازِ* آن در می‌آید).
**سوئیتِ کامل: MEASURED ۱۵۵/۱۵۵ فایل · ۹۹۷ تست · صفر fail · exit=0** رویِ ایمیج
`13bc00e123db1b8263c158aafc0ba024c33d544f0e677fea2d4d9ca0e34b78b2` (مبنایِ پ۷۲: ۱۵۴ فایل · ۹۹۰ تست ⇒
+۱ فایل، +۷ تست، صفر حذف). پنج گیت + ruff: **OK · ۳۳۹ فایل · ۳۸۶ شکلِ `callback_data`**.

**مستندات:** `docs/changelog-p73.md` · `TEST_RESULTS.md` §۵۷ · `REMAINING_ISSUES.md` §پ۷۳ ·
`docs/user-guide.md` (بندِ ۷ِ بخشِ اینستاگرام).

**NOT RUN:** رویدادِ واقعیِ متا (اپِ تأییدشده + App Review + دامنهٔ HTTPS)؛ دیدهٔ چشمیِ صفحه در
تلگرام/بله؛ حجمِ واقعیِ ردیف‌ها رویِ اکانتِ پست‌دار؛ فهرستِ «به این حساب جواب نده» (حلقهٔ چهارم).

## ۶۷) پ۷۴ — دسته‌بندیِ محصولات در مودِ فروشگاهی (۲۰۲۶-۱۱-۱۵)
خواستهٔ مالک (۲۰۲۶-۱۱-۱۴): «امکانِ دسته‌بندیِ محصولات رو در حالتِ فروشگاهی اضافه کن که در صورتِ خواستِ صاحبِ
آنلاین‌شاپ کاربران به صورتِ دسته‌بندی‌شده محصولات را ببینند». مسیرِ انتخاب‌شده ستونِ متنِ ساده رویِ خودِ
محصول است (نه جدولِ many-to-many): درِ محصول یکِ دسته دارد، مهاجرتِ افزودنی است، و کاتالوگِ مشتری بدونِ
JOINِ تازه کار می‌کند. `products.category` با `server_default=""` ⇒ فروشگاه‌هایی که دسته نسازند دقیقاً
همان صفحه‌هایِ دیروز را می‌بینند (ردیفِ فیلتر و خطِ «🗂 دسته» فقط با دادهٔ موجود ظاهر می‌شوند).
تست: ۸/۸ MEASURED. عددها: `docs/changelog-p74.md`.

## ۶۸) پ۷۵ — خوشه‌بندیِ سوال‌هایِ بی‌جواب (۲۰۲۶-۱۱-۱۵)
«چرا این سوال چند بار جواب ندارد» باید از ردیف‌هایِ تکی قابلِ خواندن باشد. امضایِ خوشه از واژه‌هایِ
پُرمحتوا ساخته می‌شود (حرف‌هایِ اضافه و نشانه‌هایِ عربی حذف؛ کمتر از دو واژه ⇒ خوشه نیست، وگرنه هر «سلام»
کوتاه با هر «سلام» دیگر یکی می‌شد). دلیلِ بازنویسیِ انتظارِ تستِ قدیمی در `test_knowledge_gaps.py`: صفحهٔ
شکاف‌ها یکِ ردیفِ دکمهٔ تازه دارد — رفتار عمداً عوض شده، نه باگ.
باگِ واقعیِ گرفته‌شده: نگهبانِ بی‌حالتِ `gap_save_*` کال‌بکِ تازهٔ `gapc_save_confirm` را می‌بلعید (ترتیبِ
ثبتِ روتر) ⇒ بلوکِ تازه بالایِ نگهبان رفت و نام‌هایِ جدا گرفت.
تست: ۶/۶ MEASURED.

## ۶۹) پ۷۶ — ویزاردِ زمان‌بندی + ارسالِ هر روز/هر هفته (۲۰۲۶-۱۱-۱۵)
دو خواستهٔ مالک در یکِ فاز: (۱) ساختِ زمانِ جلالی بدونِ تایپِ تاریخِ میلادی، (۲) کمپینِ تکرارشونده.
تصمیمِ فنیِ مهم: صفِ ارسالی در هر نوبت با کلیدِ `bcast:{id}:{turn}:{chat}:{platform}` یکتا می‌ماند، پس
«هر جمعه» در همان نوبت دوبار نمی‌رود و در نوبتِ بعدی هم سرکوب نمی‌شود. سقفِ ۶۰ occurrence گذاشته شد تا
یکِ ردیفِ تکرارشوندهٔ فراموش‌شده بی‌نهایت پیام نسازد. بازنویسیِ عمدیِ انتظارِ کهنه: `test_p26_bale_handoff_and_ux.py`
دکمه‌هایِ صفحهٔ زمان‌بندی را ۷ پین کرده بود؛ با دکمهٔ «تکرار» ۸ شد (تغییرِ رفتاریِ عمدی، نه باگ).
تست: ۶/۶ MEASURED.

## ۷۰) پ۷۷ — «به این حساب جواب نده» + اکسلِ کامنت‌ها (۲۰۲۶-۱۱-۱۵)
حلقهٔ چهارمِ اینستاگرام (پ۶۳ = مدیریتِ زمان‌دار، پ۷۳ = گزارش). درجۀ جدید جدولِ per-فروشگاهِ نام‌هایِ
کاربری است که فقط نام می‌ماند (نه متن)، و درِ آن در `_handle_comment` پیش ازِ هر AI/کسر قرار گرفته، پس
حسابِ مسدود هیچ هزینهای نمی‌سازد؛ دلیلِ `sender_blocked` در همان گزارشِ پ۷۳ با متنِ فارسی خوانده می‌شود.
خروجیِ اکسل رویِ همانِ صفحه («📥 فایلِ اکسلِ کامنت‌ها») با سقفِ ۵۰۰ ردیف و پرچمِ بریده‌شدن در کپشن.
بازنویسیِ عمدیِ انتظارِ کهنه: `test_p73_instagram_comment_report.py` شمارِ ۷ دکمهٔ کیبوردِ گزارش را پین
کرده بود؛ با دو دکمهٔ تازه ۹ شد (تغییرِ رفتاریِ عمدی).
تست: ۸/۸ MEASURED.

## ۷۱) پ۷۸ — توقفِ ساختنِ محصولِ دیجیتالِ تازه (موردِ ۲۵؛ ۲۰۲۶-۱۱-۱۵)
خواستهٔ مالک «حذفِ کاملِ محصولاتِ دیجیتال» بود. آنچه اجرا شد **توقفِ قابلیت از دیدِ کاربر** است و آنچه
انجام *نشد* حذفِ جدول/ستون است — چون (الف) قاعدهٔ ۴ِ AGENTS.md می‌گوید مایگریشن فقط افزودنی و هیچ ستون/جدولی
حذف نشود، (ب) سفارش‌هایِ پرداخت‌شدهٔ دیجیتال و استخرِ کدهایِ امروزِ چندِ فروشگاه به آن ستون‌ها وصل‌اند و
حذفشان یعنی پولِ گرفته‌شده بی‌تحویل بماند. پس: دکمه برداشته شد، درِ جادوگر با پیامِ صادقانه بسته شد،
و مدل/انبارِ کد/تحویل/ویرایشِ کدِ محصولاتِ موجود دست‌نخورده ماندند (برگشت = یکِ `True`).
تست: ۴/۴ MEASURED؛ دو انتظارِ کهنه در `test_catalog_digital_physical.py` عمداً بازنویسی شد (تغییرِ رفتاریِ
عمدی، ثبت‌شده در همین‌جا طبقِ قاعدهٔ ۸).

## ۷۲) پ۷۹ — جمعِ شمارنده‌ها بینِ پروسه‌ها (۲۰۲۶-۱۱-۱۵)
مهم‌ترینِ خروجیِ این فاز یکِ باگِ واقعی بود: عیب‌یابِ سرور شمارنده‌ها را با *برچسبِ فارسی* می‌خواند و با
*نامِ خام* می‌پرسید ⇒ سه یافتهٔ هشدار (وب‌هوکِ ردشده، سقفِ نرخ، ردِ برداشتِ کیف‌پول) در تولید هیچ‌وقت
شلیک نمی‌کردند. ضمناً شمارنده‌ها در حافظهٔ هرِ پروسه می‌ماندند و صفحه فقط پروسهٔ core را می‌دید؛ حالا هرِ
پروسه هر ۳۰ ثانیه یکِ upsert می‌نویسد (`runtime_counter_snapshots`) و خواننده سهمِ زنده‌ها را جمع
می‌کند و پروسهٔ بی‌ضربان را صریح اعلام می‌کند. تست: ۶/۶ MEASURED.

## ۷۳) پ۸۰ — پرامپتِ سیستمیِ کوتاه‌تر (۲۰۲۶-۱۱-۱۵)
دو خطِ نگهبانِ رفتاری در هرِ درخواست تکرار می‌شد: ۸۵۵ بایت → ۴۶۳ بایت (MEASURED: پرامپتِ فروشگاهی
۱٬۰۸۷←۶۹۵ و مشاوره‌ای ۱٬۱۹۴←۸۰۲ بایت؛ تخمینِ توکن ۱۷۲←۱۱۲). کلیدِ گریز: `CONCISE_GUARD_LINES=False`.
آنچه سنجیده **نشد**: parityِ کیفیتِ پاسخِ مدل (فراخوانِ واقعیِ AI لازم دارد) ⇒ NOT RUN و در changelog
همین‌طور نوشته شده. تست: ۵/۵ MEASURED + دو فایلِ قدیمیِ وابسته به متنِ پرامپت بدونِ تغییر سبز.

## ۷۴) پ۸۱ — لایهٔ اولِ فقط‌خواندنیِ پنلِ عملیاتی (۲۰۲۶-۱۱-۱۵)
از دادهٔ پ۷۹، دو خطِ gauge در `/metrics` (`kasbokar_runtime_processes` / `_stale_processes`) افزوده شد؛
بدونِ درِ تازه، بدونِ تغییرِ احراز، بدونِ کوئری در مسیرِ HTTP. باقیِ پ۵۰ (WebSocketِ چندکاناله،
شاردبندیِ polling، UIِ وب) عمداً انجام **نشد** و به‌عنوانِ فازِ مستقلِ باز ثبت شده است. تست: ۳/۳ MEASURED.

## ۷۵) پ۸۲-الف — اصلاحِ یکِ آزمونِ تاریخ‌وابسته (۲۰۲۶-۱۱-۱۶)
`test_p39_wallet_per_charge_expiry.py` نامِ دو ماهِ جلالی را سخت‌کد کرده بود («آبان ۱۴۰۵» و
«آذر ۱۴۰۵») در حالی که شارژها را «امروز+۶ روز» و «امروز+۲۶ روز» می‌سازد. در ۲۵ آبان، +۶ روز به آذر
می‌افتد ⇒ آزمون سوخت، بدونِ اینکه رفتارِ محصول عوض شده باشد (صفحه همچنان تاریخِ هرِ شارژ را می‌گفت).
انتظار بازنویسی شد تا **خودِ تاریخِ جلالی از همان خطِ خروجی خوانده شود** و دو تاریخ با هم فرق داشته
باشند؛ هیچ کدی در `app/` عوض نشد. علت در فایلِ تست هم کامنت شد (قاعدهٔ ۸: دلیلِ تغییرِ انتظارِ تست
قدیمی مکتوب).

## ۷۶) پ۸۳ — پاک‌سازیِ ردیف‌هایِ بی‌ضربان (۲۰۲۶-۱۱-۱۶)
بدهیِ خودِ پ۷۹ بسته شد: جدولِ ضربان‌ها بی‌نهایت رشد می‌کرد. `prune_counter_snapshots` هرِ ضربان ردیف‌هایِ
قدیمی‌تر از ۷ روز را حذف می‌کند و رابطهٔ «نگهداری > اعتبار» در تست پین شده است. فقط telemetry پاک می‌شود.

## ۷۷) پ۸۴ — حذفِ دادهٔ کامنت‌کننده (۲۰۲۶-۱۱-۱۶)
«حقِ فراموشی» برایِ کامنت‌هایِ اینستاگرام ساخته شد با سه قیدِ عمدی: تاییدِ صریح، شمارشِ واقعیِ ردیف‌ها رویِ
همانِ صفحه، و اعلامِ صریحِ آنچه پاک **نمی‌شود** (دایرکت/CRM/سفارش/کیف‌پول). هیچ جدولی حذف نشد و هیچ
کلیدِ خارجی‌ای نشکست، چون رویدادِ کامنت به هیچ موجودِ دیگری وصل نیست. سقفِ اسکن (۵٬۰۰۰ ردیف) و
نرمال‌سازیِ نام (نقطه/آندرلاین داخلِ نام یکی نمی‌شوند) هر دو در تست پین شده‌اند تا ادعا بزرگ‌تر از کد نباشد.
