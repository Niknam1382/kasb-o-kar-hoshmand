"""پ۵۷ · موردِ ۳۴-الف: هیچ رقمِ لاتین نباید داخلِ متن یا دکمهٔ فارسی بماند (قاعدهٔ ۵).

چرا آزمونِ «رِندرشده» و نه گیتِ متنی: رقمِ لاتین وقتی باگ است که *مقدارِ عددی* داخلِ یکِ
رشتهٔ فارسی بنشیند («خریدار: 3 نفر»). گیتِ `check_text_hygiene.py` عمداً لاتین را نمی‌گیرد،
چون نامِ تابع، URL و `noqa` بخشی از کدند؛ پس اینجا خروجیِ توابعِ متن/کیبورد را می‌سازیم و
می‌گوییم: هر رشته‌ای که نویسهٔ فارسی دارد باید بدونِ رقمِ ASCII باشد.

پوششِ داده‌شده (ساختِ مستقیمِ داده، بدونِ دیتابیس و شبکه):
۱. نمایِ بخش‌های CRM (متن + دکمه‌ها) — شمارِ هر بخش.
۲. کارتِ مشتری — شمارِ سفارشِ موفق و خطِ آخرین سفارش‌ها.
۳. دکمهٔ تاییدِ درون‌ریزیِ انبوه — تعدادِ محصول.
۴. پیامِ سفارشِ سبد (پنلِ فروشگاه‌دار) و خلاصهٔ سبد (مشتری) — تعدادِ هر قلم.
۵. پرامپتِ چک‌اوتِ مرحله‌ای «(۳/۵)» و دکمه‌هایِ مدیریتِ آدرس.
۶. دکمه‌هایِ فهرستِ بی‌جواب‌ها — شمارهٔ ادامه‌دار.
۷. توصیفِ پیشنهادِ ویرایشِ سبد با هوشِ مصنوعی.
۸. پیام‌هایِ خطایِ واردکردنِ اکسل — شمارهٔ ردیف.

اجرا: python3 tests_manual/run_one.py test_p57_persian_digits.py
"""
from __future__ import annotations

import datetime
import re
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from app.bots.main_bot import keyboards as main_keyboards  # noqa: E402
from app.bots.main_bot import texts as main_texts  # noqa: E402
from app.bots.shop_bot import checkout_ui, texts as shop_texts  # noqa: E402
from app.services import cart_proposal_service, excel_import_service  # noqa: E402

LATIN_DIGIT = re.compile(r"[0-9]")
PERSIAN = re.compile(r"[؀-ۿ]")


def _strings(value):
    """هر رشتهٔ داخلِ یکِ متن، کیبورد، لیستِ تاپلی یا دیکشنری."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for inner in value.values():
            yield from _strings(inner)
    elif isinstance(value, (list, tuple, set)):
        for inner in value:
            yield from _strings(inner)
    elif hasattr(value, "inline_keyboard"):
        for row in value.inline_keyboard:
            for button in row:
                yield button.text or ""
    elif hasattr(value, "keyboard"):
        for row in value.keyboard:
            for button in row:
                yield button.text or ""


def assert_clean(label: str, value) -> None:
    """هیچ رشتهٔ فارسی نباید رقمِ ASCII داشته باشد؛ رشتهٔ بی‌فارسی (کد/URL/شناسه) آزاد است."""
    offenders = [text for text in _strings(value) if PERSIAN.search(text) and LATIN_DIGIT.search(text)]
    assert not offenders, f"{label}: رقمِ لاتین داخلِ متنِ فارسی ⇒ {offenders}"


def _stat(**overrides):
    base = {
        "customer_id": 41,
        "first_name": "علی",
        "last_name": "محمدی",
        "username": "ali_rezayi",
        "segment": "loyal",
        "success_count": 3,
        "net_toman": 1_250_000,
        "first_seen_at": datetime.datetime(2026, 10, 1, tzinfo=datetime.timezone.utc),
        "last_activity": datetime.datetime(2026, 11, 1, tzinfo=datetime.timezone.utc),
        "order_count": 3,
    }
    base.update(overrides)
    return type("S", (), base)()


def _customer(**overrides):
    base = {"id": 41, "crm_tags": "", "crm_notes": "", "is_blocked": False, "first_name": "علی", "last_name": "محمدی", "username": "ali_rezayi"}
    base.update(overrides)
    return type("C", (), base)()


def _order(**overrides):
    base = {
        "id": 900,
        "product_name": "برنج",
        "type": "product",
        "quantity": 2,
        "value_toman": 250_000,
        "status": "completed",
        "created_at": datetime.datetime(2026, 11, 2, tzinfo=datetime.timezone.utc),
    }
    base.update(overrides)
    return type("O", (), base)()


def test_crm_overview_text_and_buttons() -> None:
    counts = {"loyal": 3, "active": 12, "new": 7, "churning": 1, "no_purchase": 20}
    assert_clean("متنِ نمایِ بخش‌ها", main_texts.crm_overview_text(counts, total=43, truncated=False))
    assert_clean("دکمه‌هایِ نمایِ بخش‌ها", main_keyboards.crm_overview_keyboard(counts))
    # قاعدهٔ ۵ فقط با رقمِ جلالی تأیید نمی‌شود؛ باید عدد *در متن باشد*، نه اینکه رشته خالی بماند
    text = main_texts.crm_overview_text(counts, total=43, truncated=False)
    assert "۳ نفر" in text and "۱۲ نفر" in text, text
    assert "3 نفر" not in text and "12" not in text, text
    print("PASS test_crm_overview_text_and_buttons")


def test_crm_card_text() -> None:
    stat, customer = _stat(), _customer()
    assert_clean("کارتِ مشتری بی‌سفارش", main_texts.crm_card_text(stat, customer, []))
    assert_clean("کارتِ مشتری با سفارش", main_texts.crm_card_text(stat, customer, [_order()]))
    text = main_texts.crm_card_text(stat, customer, [_order(quantity=2)])
    assert "سفارشِ موفق: ۳" in text, text
    assert "×۲" in text, text
    print("PASS test_crm_card_text")


def test_segment_and_search_screens() -> None:
    # نام‌هایِ سیدعمدی رقم ندارند: رقمِ داخلِ *دادهٔ خودِ کاربر* (مثلاً «مشتری12») نقضِ قاعدهٔ ۵
    # نیست و ادعایِ این آزمون هم نیست — آنچه باید جلالی باشد عددی است که *ربات* تولید می‌کند.
    members = [_stat(customer_id=500 + i, first_name=name) for i, name in enumerate(("سیب", "گلاب", "نارنج"), start=1)]
    assert_clean("فهرستِ بخش", main_texts.crm_segment_text("loyal", members, total=12, page=1, total_pages=2, page_size=8))
    seg_kb = main_keyboards.crm_segment_keyboard("loyal", members, 1, 2, 8)
    assert_clean("کیبوردِ بخش", seg_kb)
    labels = [button.text for row in seg_kb.inline_keyboard for button in row]
    assert any(label.startswith("۹. ") for label in labels), labels
    contacts = [_customer(id=900 + i, first_name=name, is_blocked=(i == 1)) for i, name in enumerate(("سیب", "گلاب"), start=1)]
    assert_clean("کیبوردِ مخاطبانِ مشاوره", main_keyboards.consult_contacts_keyboard(contacts, 0, 2))
    assert_clean("سرصفحهٔ جست‌وجو", main_texts.crm_search_intro("علی", total=9, page=1, total_pages=2))
    print("PASS test_segment_and_search_screens")


def test_bulk_import_confirm_button() -> None:
    keyboard = main_keyboards.product_import_confirm_keyboard(12)
    assert_clean("دکمهٔ تاییدِ درون‌ریزی", keyboard)
    labels = [button.text for row in keyboard.inline_keyboard for button in row]
    assert any("۱۲ محصول" in label for label in labels), labels
    print("PASS test_bulk_import_confirm_button")


def test_cart_and_checkout_customer_text() -> None:
    product = type("P", (), {"name": "چای", "price_toman": 120_000, "id": 7})()
    item = type("I", (), {"quantity": 3, "product_id": 7})()
    pairs = [(item, product)]
    assert_clean("خلاصهٔ سبدِ مشتری", shop_texts.cart_summary(pairs))
    assert_clean("پرامپتِ چک‌اوت", shop_texts.checkout_question_prompt("آدرسِ ارسال کجا باشه؟", 3, 5))
    assert_clean("پیامِ سفارشِ سبد به فروشگاه‌دار", main_texts.cart_order_notification(_customer(), pairs, [("توضیح", "سریع")], total_toman=360_000))
    prompt = shop_texts.checkout_question_prompt("آدرسِ ارسال کجا باشه؟", 3, 5)
    assert "(۳/۵)" in prompt, prompt
    print("PASS test_cart_and_checkout_customer_text")


def test_address_manage_buttons() -> None:
    addresses = [
        type("A", (), {"id": 1, "is_default": True, "label": "خانه", "full_name": "علی", "phone": "09120000000", "address_text": "خیابانِ تست"})(),
        type("A", (), {"id": 2, "is_default": False, "label": "محلِ کار", "full_name": "علی", "phone": "09120000001", "address_text": "خیابانِ تست ۲"})(),
    ]
    assert_clean("دکمه‌هایِ مدیریتِ آدرس", checkout_ui.address_manage_keyboard(addresses))
    print("PASS test_address_manage_buttons")


def test_knowledge_gaps_buttons() -> None:
    gaps = [type("G", (), {"id": 10 + i, "question": "قیمت؟"})() for i in range(3)]
    assert_clean("دکمه‌هایِ بی‌جواب‌ها", main_keyboards.gaps_list_keyboard(gaps, page=1, total=12, page_size=8))
    print("PASS test_knowledge_gaps_buttons")


def test_cart_ai_proposal_and_excel_errors() -> None:
    op = cart_proposal_service.CartOperation
    assert_clean("پیشنهادِ حذف", cart_proposal_service.describe_op(op(action="remove", product_id=7, quantity=None), "چای"))
    for action in ("add", "decrease", "set"):
        assert_clean(f"پیشنهادِ {action}", cart_proposal_service.describe_op(op(action=action, product_id=7, quantity=12), "چای"))
    # ردیفِ بی‌نام باید پیامِ خطا با شمارهٔ ردیفِ جلالی بدهد
    _product, error = excel_import_service._parse_row(("", "", "", "", ""), 7)
    assert error is None, error  # ردیفِ کاملاً خالی خطا نیست
    _product, error = excel_import_service._parse_row(("", "توضیح", "120000", "2", "فیزیکی"), 7)
    assert error is not None and "ردیف ۷" in error, error
    assert_clean("خطایِ واردکردنِ اکسل", error)
    print("PASS test_cart_ai_proposal_and_excel_errors")


def main() -> None:
    test_crm_overview_text_and_buttons()
    test_crm_card_text()
    test_segment_and_search_screens()
    test_bulk_import_confirm_button()
    test_cart_and_checkout_customer_text()
    test_address_manage_buttons()
    test_knowledge_gaps_buttons()
    test_cart_ai_proposal_and_excel_errors()
    print("📊 نتیجه: ۸ تستِ پ۵۷ (ارقامِ جلالی در خروجی‌هایِ پنل) پاس شد · CRM، سبد، چک‌اوت، آدرس، بی‌جواب‌ها، اکسل")


if __name__ == "__main__":
    main()
