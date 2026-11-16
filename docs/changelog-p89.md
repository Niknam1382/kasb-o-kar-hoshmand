# پ۸۹ — پاک‌سازیِ کد و متنِ اضافی (بازرسیِ راند ۲؛ ۲۰۲۶-۱۱-۱۶)

خواستهٔ مالک: در مرحلهٔ بازبینی، متن و کدِ اضافی هم حذف شود.

## روش (بدونِ حدس)
۱) همهٔ فایل‌هایِ Python مخزن (کد + تست + اسکریپت) خوانده می‌شود و نامِ هر ثابتِ بزرگِ سطح‌ماژول و هر
   تابعِ عمومیِ `app/services` و `keyboards` شمرده می‌شود؛ نامی که **فقط در سطرِ تعریفِ خودش** می‌آید،
   کشته شده است. دقتِ لازم: جست‌وجویِ `getattr` رویِ ماژول‌هایِ متن انجام می‌شود و هیچ‌کجا چنین
   الگویی نیست ⇒ حذف با ارجاعِ داینامیک نمی‌شکند.
۲) حذف با AST انجام شد (نه regex) تا بلوکِ چندخطی و کامنتِ بالایِ تابع هم درست برداشته شود؛ بعد ازِ
   هر فایل، مجدد `ast.parse` شد تا ساختارِ فایل نشکند.
۳) `ruff --select F,E9` + پنج گیتِ ایستایی + کامپایلِ کاملِ `app/` ⇒ همه تمیز.

## آنچه حذف شد
• **۳۵ ثابتِ متنِ بی‌مصرف** از `app/bots/main_bot/texts.py` و `app/bots/shop_bot/texts.py`
  (مثلِ `ADMIN_ASK_AI_API_KEY`، `PAYS_DONE`، `ORDER_RESTOCK_BUTTON`، `MY_ORDER_DIGITAL_AGAIN`،
  `INSTAGRAM_BLOCK_BACK_BUTTON` — همه متن‌هایی که هندلری دیگر آن‌ها را نشان نمی‌داد).
• **۱۵ تابعِ بی‌استفاده در سرویس‌ها**: `wallet_service.get_balance`، `payment_service.get_pending_payments`،
  `cart_service.count_items`، `customer_service.get_by_shop_bot`، `shipping_service.describe_method`،
  `search_service.require_term`، `platform_service.is_instagram`، `subscription_service.has_ever_had_subscription`،
  `order_service.get_recent_for_owner_notification`، `order_access_service.state_for_bot`،
  `moderation_service.get_active_rules`، `moderation_notify_service.block_customer`،
  `owner_activity_service.count_active`، `owner_dossier_service.extend_allowed`، `bot_branding_service.expected_bio`.
• **۳ کیبوردِ بی‌مصرف**: `request_phone_keyboard`، `doctor_threshold_detail_keyboard`،
  `ai_usage_shop_filter_keyboard` (صفحه‌هایِ واقعی کیبوردِ دیگری می‌سازند).
• دو import که پس ازِ حذف‌ها بی‌مصرف شدند.

## آنچه عمداً دست نخورد
• `order_state.is_open/is_paid_or_later/is_deliverable` — نام‌هایشان در جاهایِ دیگر (فیلدهایِ هم‌نام)
  هم استفاده می‌شود و ابزارِ ساده نمی‌تواند تفکیک کند؛ ریسکِ حذفِ اشتباه بالاتر از benefitِ پاک‌سازی.
• هیچ جدول/ستونی حذف نشد (قاعدهٔ ۴). هیچ رفتارِ محصولی عوض نشد: همهٔ حذف‌ها جایی بودند که صفر
  مصرف‌کننده داشتند، پس سوئیتِ کاملِ پیشین هم همان مقدار سبز می‌ماند.

## اثرِ اندازه‌گرفته‌شده
پس ازِ حذف، سنجشِ مقیاس دوباره گرفته شد: **۱۱ statement به‌ازایِ هرِ پیام** (بدونِ تغییر)، جابِ گرم
۳۳ statement (از ۳۶ ⇒ −۳)، بالا آمدنِ ۲۰۰ فروشگاه ۲٫۲۷ ثانیه، ۵۰۰ فروشگاه ۵٫۲۹ ثانیه،
rss در ۵۰۰ فروشگاه ۳۶۵٫۳MiB.
