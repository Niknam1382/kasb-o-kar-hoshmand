# پ۹۲ — پاک‌سازیِ راند ۲ (بخشِ دوم): توابعِ باقی‌مانده و حذفِ چندپاسه (۲۰۲۶-۱۱-۱۶)

۱) سه کمک‌تابعِ بی‌مصرفِ `order_state` (`is_open`، `is_paid_or_later`، `is_deliverable`) حذف شدند.
   این بار تأیید دستی انجام شد: در کلِ مخزن هیچ ارجاعی به `order_state.<name>` وجود ندارد و تنها
   matching‌ها نام‌هایِ بی‌ربط بودند (`ai_service._circuit_is_open`،
   `instagram_service.comment_reply_is_open`). پس ازِ حذف، گیت‌ها و `ruff F,E9` تمیزند.
۲) `instagram_service.erase_comment_sender_data` و `comment_sender_event_count` چندپاسه شدند
   (`ERASE_SCAN_LIMIT=5000` در هر پاس، سقفِ `ERASE_MAX_PASSES=40`) ⇒ کاستیِ ثبت‌شده در پ۸۴ («اگر یکِ
   حساب بیش از ۵٬۰۰۰ کامنت داشته باشد، بقیه در این پاس نمی‌آید») برطرف شد و عددِ صفحهٔ تایید با عددِ
   پاک‌شده می‌خواند.
۳) `capacity_service.prune_counter_snapshots` همان‌جا ماند (پ۸۳) و در تست، کوئریِ آن هم ثابت شد (۱ statement).

تست: `test_p84_comment_erasure.py` ⇒ **۵/۵** (تستِ تازهٔ `test_erase_loops_past_one_scan_batch` با
`ERASE_SCAN_LIMIT=2` چرخشِ پاس‌ها را می‌سنجد) و `test_p77_instagram_comment_blocks.py` ⇒ ۷/۷.
