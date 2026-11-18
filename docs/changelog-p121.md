# چنجلاگِ پ۱۲۱ — بن‌بستِ واقعیِ «Charges ↔ Owner» که رفعِ پ۱۷ جا گذاشته بود (۲۰۲۶-۱۱-۱۸)

## چی شد
در سوئیتِ کاملِ پایانِ پ۱۱۹/پ۱۲۰، تستِ دست‌نخوردهٔ `test_p117_lock_order_and_expiry.py`
(حالتِ ۴: `test_concurrent_wallet_and_commission_do_not_deadlock`) با
`asyncpg.exceptions.DeadlockDetectedError` شکست — **MEASURED، لاگِ سوئیتِ ۲۰۲۶-۱۱-۱۸،
`187/189 فایل، ۱٬۱۴۷ تستِ پاس` و دو fail**. flaky خوانده نشد؛ سه اجرایِ پشتِ همِ همان فایل بعد ازِ
رفع ⇒ **MEASURED ۴/۴، ۴/۴، ۴/۴**.

## ریشه
پ۱۷ برایِ بستنِ یافتهٔ ۶ (حلقهٔ مرگِ Charges↔Owner) ترتیبِ «اولِ ShopOwner، بعدِ WalletCharge» را
در `deduct` و `add_charge` گذاشت. نسخهٔ `deduct` برایِ اینکه سقفِ ۲۹ statementِ مسیرِ پیام (پ۳۱)
نشکند، در یکِ statement جمع شده بود:

    SELECT wallet_charges JOIN shop_owners … FOR UPDATE OF wallet_charges, shop_owners

`FOR UPDATE` چندجدولی **ترتیبِ تضمینی ندارد** — آنِ Postgres است که با planِ join تعیین می‌کند کدام
سطر زودتر قفل شود. در عمل سطرهایِ `wallet_charges` (که پویشِ بیرونی بودند) پیش ازِ سطرِ
`shop_owners` قفل می‌شدند، یعنی ترتیبِ واقعیِ `deduct` برعکسِ `commission_service.settle` (که با
`_lock_owner` تک‌جدولی *همیشه* اولِ owner را قفل می‌کند). دو کسر و دو تسویهٔ هم‌زمان ⇒ دورِ قفل ⇒ بن‌بست.
قربانیِ این بن‌بست در تولید همان چیزی است که پ۱۷ می‌خواست نجاتش دهد: rollbackِ کلِ گذارِ `paid`.

نکتهٔ دوم که همان را بدتر می‌کرد: `_apply_balance_delta` در انتهایِ `deduct` یکِ
`UPDATE shop_owners` می‌زند — یعنی حتی در نسخهٔ تک‌statement هم سطرِ owner **بعد ازِ** بسته‌ها
قفل می‌شد؛ پس «ترتیبِ یکتا» در `deduct` عملاً برقرار نبود، نه فقط plan-وابسته.

## رفع
`wallet_service.deduct` دوباره دو مرحله‌ای شد، با ترتیبِ دستوریِ روشن:

    SELECT shop_owners.id … FOR UPDATE          # ۱) قفلِ صاحبِ حساب (بدونِ کشیدنِ سطرِ ORM)
    SELECT wallet_charges … FOR UPDATE OF wallet_charges   # ۲) بعدِ بسته‌ها

`SELECT id` به‌جایِ `SELECT ShopOwner` عمدی است: `deduct` عددِ موجودی را از رویِ **بسته‌ها** می‌شمارد و
موجودیِ کش‌شده را با UPDATE عبارت‌محور می‌نویسد، پس برخلافِ `_lock_owner` (که رویِ
`commission_reserved_toman` مقدارِ تازه لازم دارد) به `populate_existing` نیاز ندارد ⇒ یکِ statement
هزینه می‌دهد، ولی آنِ خودِ ترتیبِ قفل است. `add_charge` از پ۱۷ همین شکلِ دو-مرحله‌ای را داشت و دست‌
نخورده ماند؛ `commission_service` هم همین‌جا رها شده (Owner → ردیف‌هایِ گروه → Charges).

## بهایِ اندازه‌گیری‌شده
`MAX_STATEMENTS_PER_MESSAGE` در تستِ پ۳۱ از ۳۱ به **۳۳** رفت (**MEASURED**: `PASSED (count=33)`) —
یکِ SELECTِ ایندکسی‌نشده‌یِ سطرِ owner به‌ازایِ هر کسر، و در مسیرِ یکِ پیامِ متنی دو کسر داریم
(چت + تشخیصِ سفارش). این عدد با سه قلمِ دیگرِ «تغییرِ عمدیِ انتظار» در `docs/PROGRESS.md` §۱۱۰
ثبت شده است.

## دو انتظارِ دیگر که همین‌جا اصلاح شد
• `test_p114_web_panel_visibility.py` عددِ head را پین کرده بود (`heads == {"c9e2f4a7b135"}`) و با
  مایگریشنِ افزودنیِ پ۱۲۰ می‌شکست. قاعدهٔ واقعیِ پروژه «همیشه یکِ head» است؛ حالا تست
  `len(heads) == 1` را می‌بیند و جداگانه می‌سنجد که رِویشنِ پ۱۱۴ هنوز در تاریخچه هست ⇒ با هر
  مایگریشنِ افزودنیِ آینده نمی‌شکند.
• `test_p5_ledger_integrity.py` و `test_p5_commission.py` و `MAX_STATEMENTS_PER_MESSAGE` در پ۱۱۶
  توضیح داده شده بودند (§۱۱۰).

## فایل‌ها
`app/services/wallet_service.py` · `tests_manual/test_p31_message_statement_bounds.py` ·
`tests_manual/test_p114_web_panel_visibility.py` · `docs/PROGRESS.md` §۱۱۰ و §۱۱۳ ·
`REMAINING_ISSUES.md` §پ۱۲۱
