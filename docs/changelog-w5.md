# changelog — W5 (چتِ B: لایه‌یِ ۱ و ۲)

## لایه‌یِ ۱ (هسته‌یِ فروش)
- **C3 چک‌اوتِ مرحله‌ای** (`handlers/checkout.py`، `checkout_flow.py`، `checkout_ui.py`، `address_book_service.py`): نام ← موبایل ← آدرس (دفترچه تا ۵ آدرس) ← ارسال ← سوال‌ها ← توضیح ← پیش‌فاکتور با ارسال؛ برگشت/رد/انصراف، ویرایش از پیش‌نمایش، دکمه‌یِ کهنه ⇒ پیامِ مودبانه؛ `main.py` مبلغِ webhookِ سبد را با `group_total_toman` (اقلام+ارسال) می‌سنجد.
- **wizard_nav** (`bots/common/wizard_nav.py`) مشترک؛ در چک‌اوت استفاده شد. ⏩ فرمِ افزودنِ محصولِ دیجیتال/فیزیکی هنوز با دکمه‌هایِ قبلی (دلیل: مایگریشنِ جریانِ FSMِ چندمرحله‌ایِ پنل ریسکِ بدونِ Docker داشت).
- **C2** ویرایشِ سبد با AI فقط پیشنهاد: `cart_proposal_service` (claim اتمی، TTL ۱۰ دقیقه، اثرانگشتِ سبد) + `handlers/cart_proposals.py`.
- **1.4/1.5** اعلانِ خودکار به مشتری روی تایید/ردِ دستی؛ دکمه‌یِ «✉️ پیام به مشتری» روی اعلانِ تک‌سفارش؛ **B6** getUpdatesِ بله (`bale_updates_service`)، **B7** رمزنگاریِ شفافِ `bale_provider_token` (`EncryptedToken`)، **B10** قفلِ ردیف + ردِ بازپخشِ تراکنش روی مسیرِ قدیمیِ `bale_paid_at`.

## لایه‌یِ ۲
- **تحلیلِ AIِ رسید** (`receipt_ai_service`): مشورتی، JSONِ دفاعی، پرچم‌هایِ مبلغ/کارت/تاریخ/شماره‌پیگیریِ تکراری، هزینه بعد از موفقیت.
- **2.2** تاییدِ دیرهنگامِ رسیدِ منقضی (با رزروِ دوباره و پرچمِ فروشِ بیش‌ازموجودی)، هشدارِ ۲ ساعته‌یِ بررسیِ رسید (یک‌بار)، حدودِ مهلتِ تنظیم‌شونده توسطِ ادمین، «📦 برگردانِ موجودی» بعد از استرداد.
- **K1–K4** (`credit_batch_service`، `time_freeze_service`، `job_gate_service`، `handlers/admin_time.py`).
- مایگریشن‌ها: `b7c1e4a9d2f3`، `c8d2f5a7e1b4`.

## ضمیمه — پس از Dockerِ اول
- اصلاحِ ۵ فایلِ تست (بخش ۹ PROGRESS) — بدونِ تغییر در رفتارِ محصول، جز سقفِ سخت‌ِ `clamp_*` که از قبل طراحی‌شده بود.
- **تازه:** «🧾 مدیریتِ سفارش‌ها (جاری)» برایِ فروشگاه‌دار (`orders_manage_service.py`، `handlers/orders_manage.py`، تست `test_orders_manage.py`، دکمه در `shop_owner_panel_keyboard` برایِ حالتِ فروشگاهی و در `_KNOWN_MENU_BUTTONS`).

## ضمیمه ۲ — باگ‌هایِ گزارش‌شده و امنیت
- رسیدِ متنی برایِ کارت‌به‌کارت (`parse_receipt_text`، `OrderPayment.receipt_text`).
- عکسِ محصول برایِ مشتری (`product_photo_service`، `handlers/product_photos.py`، `Product.photo_shop_file_id`، دکمه‌یِ «🖼»).
- امنیت: بخشِ «در W5 اصلاح شد» در `docs/security-review-w5.md`.
- مایگریشنِ `d9e3a6b8c2f5`.
