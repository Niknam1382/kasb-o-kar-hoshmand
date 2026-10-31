"""
تست: P18 · B6 — فاکتورِ PDFِ فارسیِ راست‌به‌چپ (به‌جایِ HTML).

پوششِ داده‌شده:
* شکل‌دهیِ حروف + bidi (نتیجه باید «فرم‌هایِ ارائه‌یِ عربی» داشته باشد، نه کِدینگِ خام).
* پیدا شدنِ فونت (Vazirmatnِ باندل‌شده یا DejaVuِ سیستمی).
* بایت‌هایِ خروجی با %PDF شروع و با %%EOF تمام می‌شوند، اندازه معقول، و فونت واقعاً امبد شده.
* فاکتورِ دیجیتال / فیزیکی / گروهی(چند قلم) / با تخفیف و ارسال — هیچ‌کدام استثنا نمی‌دهند.
* تزریقِ HTML/اسکریپت و نامِ خیلی‌بلند فاکتور را نمی‌شکند.
* هر مانعی در مسیرِ PDF ⇒ None (فراخواننده به HTML برمی‌گردد) و هیچ‌وقت کرش نمی‌کند.
* هندلرِ واقعی: وقتی PDF ساخته می‌شود فایلِ .pdf و وقتی نمی‌شود فایلِ .html می‌رود.

اجرا: python3 tests_manual/test_p18_pdf_invoice.py
"""
from __future__ import annotations

import asyncio
import datetime
import json
import pathlib
import sys
import types

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402
from harness import FakeSession, build_test_dispatchers, reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.shop_bot.handlers import orders as orders_handlers  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import invoice_service  # noqa: E402

OWNER_TG_ID = 999_771
SHOP_BOT_TG_ID = 999_772
Row = types.SimpleNamespace


def _row(**kw):
    base = dict(
        id=1, product_id=1, quantity=1, estimated_value_toman=100_000, discount_toman=0, summary="خلاصه",
        shipping_fee_toman=0, shipping_method_name=None, customer_phone="+989121234567", customer_address=None,
        checkout_answers=None, payment_method="card", status="paid", cart_checkout_group_id=None,
    )
    base.update(kw)
    return Row(**base)


def _data(rows, products, **over):
    data = invoice_service.build_invoice_data(
        over.pop("number", "INV-7-202611-1"),
        datetime.datetime.now(datetime.timezone.utc),
        rows,
        products,
        Row(first_name="مریم", last_name="رضایی", username=None, phone_number=None),
        over.pop("shop", "گالریِ گلِ مریم"),
        platform_signature=over.pop("signature", True),
    )
    return {**data, **over}


# ============================================================================= ۱ — فونت و شکل‌دهی
def test_font_is_available() -> None:
    font = invoice_service.font_path()
    assert font is not None, "B6: باید حداقل یک فونتِ فارسی (باندل‌شده یا DejaVuِ سیستمی) پیدا شود"
    assert font.lower().endswith(".ttf"), font
    print(f"✅ test_font_is_available PASSED ({font})")


def test_shape_text_reorders_and_presents() -> None:
    shaped = invoice_service.shape_text("سلام دنیا")
    assert shaped, "ورودیِ فارسی نباید خالی بشود"
    # فرم‌هایِ ارائه‌یِ عربی (U+FB50–FDFF و U+FE70–FEFF) نشانه‌یِ شکل‌گرفتنِ حروف است.
    assert any(0xFB50 <= ord(ch) <= 0xFDFF or 0xFE70 <= ord(ch) <= 0xFEFF for ch in shaped), repr(shaped)
    assert invoice_service.shape_text("") == "" and invoice_service.shape_text(None) == ""
    assert invoice_service.shape_text("ABC") == "ABC"
    print("✅ test_shape_text_reorders_and_presents PASSED")


# ============================================================================= ۲ — چهار شکلِ فاکتور
def _assert_pdf(payload: bytes, label: str) -> None:
    assert payload.startswith(b"%PDF"), f"{label}: امضایِ جادوییِ PDF"
    assert payload.rstrip().endswith(b"%%EOF"), f"{label}: پایانِ استانداردِ PDF"
    assert len(payload) > 1_200, f"{label}: اندازه‌یِ غیرمنطقی ({len(payload)} بایت)"
    assert b"/Type /Font" in payload or b"/Type/Font" in payload, f"{label}: هیچ فونتی در PDF نیست"
    assert b"/FontFile2" in payload, f"{label}: فونتِ TTF امبد نشده ⇒ حروفِ فارسی رویِ دستگاهِ گیرنده خراب می‌شود"


def test_pdf_for_digital_physical_group_and_discounted() -> None:
    cases = {
        "digital": _data(
            [_row(product_id=1, shipping_fee_toman=0)],
            {1: Row(name="دفترچه الکترونیکی", kind="digital")},
        ),
        "physical": _data(
            [_row(product_id=2, shipping_fee_toman=25_000, shipping_method_name="پست", customer_address="تهران، خیابان ولیعصر، کوچه ۵، پلاک ۱۲")],
            {2: Row(name="کتاب", kind="physical")},
        ),
        "group": _data(
            [
                _row(id=1, product_id=3, quantity=2, estimated_value_toman=60_000, cart_checkout_group_id="0a1b2c3d4e5f0a1b2c3d4e5f"),
                _row(id=2, product_id=4, quantity=1, estimated_value_toman=90_000, cart_checkout_group_id="0a1b2c3d4e5f0a1b2c3d4e5f"),
                _row(id=3, product_id=5, quantity=7, estimated_value_toman=14_000, cart_checkout_group_id="0a1b2c3d4e5f0a1b2c3d4e5f"),
            ],
            {3: Row(name="صندل", kind="physical"), 4: Row(name="شارژر", kind="digital"), 5: Row(name="کیبل", kind="physical")},
            number="INV-7-202611-2",
        ),
        "discounted": _data(
            [_row(product_id=6, quantity=3, estimated_value_toman=270_000, discount_toman=30_000, shipping_fee_toman=40_000, shipping_method_name="تیپاکس")],
            {6: Row(name="شالِ نخی", kind="physical")},
            number="INV-7-202611-3",
        ),
    }
    for label, data in cases.items():
        payload = invoice_service.build_invoice_pdf(data)
        assert payload is not None, label
        _assert_pdf(payload, label)

    discounted = cases["discounted"]
    assert discounted["list_total"] == 300_000 and discounted["discount"] == 30_000 and discounted["total"] == 310_000, discounted
    assert cases["group"]["shipping"] == 0
    print("✅ test_pdf_for_digital_physical_group_and_discounted PASSED")


def test_pdf_survives_injection_and_huge_names() -> None:
    evil = "<script>alert('x')</script>\" OR 1=1-- \\n\n۱۲۳"
    data = _data(
        [
            _row(id=1, product_id=1, quantity=1, estimated_value_toman=1_000, summary=evil),
            _row(id=2, product_id=2, quantity=99, estimated_value_toman=10**15, summary="ا" * 400),
        ],
        {1: Row(name=evil, kind="physical"), 2: Row(name="ی" * 300, kind="digital")},
        address=evil * 4,
        phone=evil,
    )
    payload = invoice_service.build_invoice_pdf(data)
    assert payload is not None and payload.startswith(b"%PDF"), "متنِ مخرب نباید رندر را بشکند"
    # متنِ خامِ تزریقی نباید به‌شکلِ دستورِ PDF در فایل باقی بماند
    assert b"<script>" not in payload

    # فاکتورِ بدونِ قلم (ردیف‌هایِ خالی) هم نباید بسازد را بترکاند
    assert invoice_service.build_invoice_pdf(_data([], {})) is not None
    print("✅ test_pdf_survives_injection_and_huge_names PASSED")


# ============================================================================= ۳ — مسیرِ برگشت به HTML
def test_pdf_returns_none_without_font_or_library() -> None:
    data = _data([_row()], {1: Row(name="کالا", kind="physical")})
    original = invoice_service.font_path
    invoice_service.font_path = lambda: None
    try:
        assert invoice_service.build_invoice_pdf(data) is None, "بدونِ فونت ⇒ None، نه استثنا"
    finally:
        invoice_service.font_path = original

    # فونتِ خراب (نه TTF) ⇒ رندر استثنا می‌دهد ⇒ باز هم None
    broken = invoice_service.font_path()
    bogus = pathlib.Path(broken).with_name("nope.ttf")
    invoice_service._FONT_CACHE = str(bogus)
    try:
        assert invoice_service.build_invoice_pdf(data) is None, "فونتِ ناموجود ⇒ None"
    finally:
        invoice_service._FONT_CACHE = None

    # نبودِ کتابخانه هم نباید ماژول را بشکند (shape_text فقط در PDF صدا زده می‌شود)
    assert invoice_service.build_invoice_html(data).startswith("<!DOCTYPE html>")
    print("✅ test_pdf_returns_none_without_font_or_library PASSED")


# ============================================================================= ۴ — هندلر
async def _send_with(main_bot: Bot, invoice_number: str, data: dict) -> FakeSession:
    # دیسپچرها یک‌بار در main() ساخته می‌شن؛ روترهای aiogram قابلِ اتصالِ دوباره نیستن.
    session_obj: FakeSession = main_bot.session  # type: ignore[assignment]
    session_obj.sent_documents.clear()
    fake_invoice = Row(number=invoice_number, data_json=json.dumps(data, ensure_ascii=False))

    async def _fake_ensure(session, rows, customer, title, **kwargs):
        return fake_invoice, True

    original = invoice_service.ensure_invoice
    invoice_service.ensure_invoice = _fake_ensure
    try:
        async with session_scope() as session:
            ok = await orders_handlers.send_invoice_to_customer(
                session,
                Row(bot_username="test_shop"),
                [],
                Row(first_name="مریم", last_name=None, username=None, phone_number=None, telegram_id=1),
                main_bot,
                12345,
            )
    finally:
        invoice_service.ensure_invoice = original
    assert ok is True
    return session_obj


async def test_handler_prefers_pdf_and_falls_back_to_html(main_bot: Bot) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    data = _data([_row()], {1: Row(name="کالا", kind="physical")})

    session_obj = await _send_with(main_bot, "INV-9-202611-1", data)
    assert len(session_obj.sent_documents) == 1, session_obj.sent_documents
    doc = session_obj.sent_documents[0]["document"]
    assert doc.filename == "INV-9-202611-1.pdf", doc.filename
    assert doc.data.startswith(b"%PDF"), "فایلِ ارسالی واقعاً PDF است"

    original = invoice_service.font_path
    invoice_service.font_path = lambda: None
    try:
        session_obj = await _send_with(main_bot, "INV-9-202611-2", data)
    finally:
        invoice_service.font_path = original
    doc = session_obj.sent_documents[0]["document"]
    assert doc.filename == "INV-9-202611-2.html", doc.filename
    assert doc.data.lstrip().startswith(b"<!DOCTYPE html>"), "بدونِ PDF همان HTMLِ قبلی می‌رود (فاکتور هرگز گم نمی‌شود)"
    print("✅ test_handler_prefers_pdf_and_falls_back_to_html PASSED")


async def main() -> None:
    test_font_is_available()
    test_shape_text_reorders_and_presents()
    test_pdf_for_digital_physical_group_and_discounted()
    test_pdf_survives_injection_and_huge_names()
    test_pdf_returns_none_without_font_or_library()
    _main_dp, _shop_dp, _bot_manager, main_bot = build_test_dispatchers()
    await test_handler_prefers_pdf_and_falls_back_to_html(main_bot)


if __name__ == "__main__":
    asyncio.run(main())
