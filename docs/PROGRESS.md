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
