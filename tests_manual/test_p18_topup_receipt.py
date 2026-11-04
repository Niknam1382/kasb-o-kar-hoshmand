"""
تست: P18 · A7 — شارژِ اعتبارِ پلتفرم (کیفِ پولِ فروشگاه‌دار).

پوشش:
۱. مبلغِ تصادفی فقط در کارت‌به‌کارت ساخته می‌شود (بله‌پی مبلغِ دقیقِ خودش را دارد) و حسابداریِ فعلی حفظ می‌شود.
۲. متنِ راهنمایِ کارت‌به‌کارت دلیلِ درست دارد («راحت‌تر شدنِ بررسیِ واریزها توسطِ مدیر») نه «تشخیصِ خودکار».
۳. رسیدِ *متنی* هم کنارِ عکس پذیرفته می‌شود، برایِ ادمین نمایش داده می‌شود و تکراری فقط پرچم می‌خورد.
۴. «⬅️ برگشت» در حالتِ انتظارِ رسید: state پاک می‌شود ولی ردیفِ پرداخت می‌ماند و از «📂 پرداخت‌هایِ باز» ادامه پیدا می‌کند.
۵. مالکیت: فروشگاه‌دارِ دیگر نمی‌تواند پرداختِ من را ادامه دهد یا برگرداند.

اجرا: python3 tests_manual/test_p18_topup_receipt.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from harness import build_test_dispatchers, reset_database  # noqa: E402
from phase4_helpers import Chat  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot import texts as main_texts  # noqa: E402
from app.config import settings  # noqa: E402
from app.database.models import Payment, PaymentStatus  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import payment_service  # noqa: E402
from app.services.admin_settings_service import get_admin_settings  # noqa: E402
from app.utils.validators import format_toman  # noqa: E402
from sqlalchemy import select  # noqa: E402

OWNER_TG_ID = 7_300_000_001
SHOP_TG_ID = 7_300_000_002
OTHER_OWNER_TG_ID = 7_300_000_011
OTHER_SHOP_TG_ID = 7_300_000_012
TOPUP_AMOUNT = 100_000
RECEIPT_TEXT = "کارت به کارت انجام شد مبلغ 100,042 تومان ساعت 14:32 شماره پیگیری 987654321"


def _datas(markup) -> list[str]:
    return [b.callback_data for row in markup.inline_keyboard for b in row if b.callback_data] if markup else []


def _chat(owner: Chat, chat_id: int) -> list[dict]:
    """FakeSession همه‌یِ مقصدها را در یک فهرست می‌ریزد؛ پیام‌هایِ یک چتِ مشخص را جدا می‌کنیم."""
    return [m for m in owner.sent if m["chat_id"] == chat_id]


def _admin_id() -> int:
    return next(iter(settings.admin_ids))


async def _setup() -> int:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_TG_ID)
    async with session_scope() as session:
        admin_settings = await get_admin_settings(session)
        admin_settings.platform_card_number = "6037991234567890"
        admin_settings.platform_card_holder_name = "مدیرِ پلتفرم"
        admin_settings.allow_wallet_topups = True
    return shop_bot_id


async def _payments() -> list[Payment]:
    async with session_scope() as session:
        return list((await session.execute(select(Payment).order_by(Payment.id))).scalars().all())


async def _start_card_topup(owner: Chat) -> int:
    """از «💰 کیف‌پول» تا رسیدن به حالتِ انتظارِ رسید؛ شناسه‌یِ پرداخت را برمی‌گرداند."""
    await owner.say("💰 کیف‌پول")
    await owner.tap("topup_start")
    await owner.tap(f"topup_amount:{TOPUP_AMOUNT}")
    await owner.tap("skip_discount")
    await owner.tap("payment_method:card")
    payments = await _payments()
    assert len(payments) == 1
    return payments[0].id


# ============================================================================= ۱ و ۲ — مبلغِ تصادفی و متن
async def test_random_amount_only_for_card_and_wording() -> None:
    await _setup()
    async with session_scope() as session:
        admin_settings = await get_admin_settings(session)
        instructions = main_texts.card_to_card_payment_instructions(
            admin_settings.platform_card_number, admin_settings.platform_card_holder_name, 100_042
        )
    assert "بررسیِ واریزها توسطِ مدیر" in instructions, instructions
    assert "تشخیص خودکار" not in instructions and "تشخیصِ خودکار" not in instructions, "A7: دلیلِ اشتباه نماند"

    from app.services.shop_owner_service import get_by_telegram_id

    async with session_scope() as session:
        owner = await get_by_telegram_id(session, OWNER_TG_ID)
        card = await payment_service.create_card_to_card_payment(session, owner, TOPUP_AMOUNT, None)
        bale = await payment_service.create_bale_payment(session, owner, TOPUP_AMOUNT, None, "payment-x-1")
    assert card.final_amount > TOPUP_AMOUNT, "کارت‌به‌کارت مبلغِ منحصربه‌فرد می‌سازد"
    assert 10 <= card.final_amount - TOPUP_AMOUNT <= 99, "دو رقمِ آخر"
    assert bale.final_amount == TOPUP_AMOUNT, "A7: بله‌پی هرگز رقمِ تصادفی نمی‌سازد"
    print("✅ test_random_amount_only_for_card_and_wording PASSED")


# ============================================================================= ۳ و ۴ — رسیدِ متنی و برگشت
async def test_text_receipt_back_button_and_open_list(main_dp) -> None:
    await _setup()
    owner = Chat(main_dp, OWNER_TG_ID)
    payment_id = await _start_card_topup(owner)

    # متنِ راهنما و دکمه‌یِ برگشت
    prompt = next(m["text"] for m in owner.sent if m["text"] == main_texts.ASK_TOPUP_RECEIPT)
    assert prompt == main_texts.ASK_TOPUP_RECEIPT
    card_message = next(m["text"] for m in owner.sent if "بررسیِ واریزها توسطِ مدیر" in m["text"])
    assert card_message, "راهنمایِ کارت‌به‌کارت باید دلیلِ درست داشته باشد"
    assert f"topup_pay_back:{payment_id}" in _datas(owner.last_markup), owner.last_markup

    # «⬅️ برگشت» ⇒ state پاک، ردیفِ پرداخت سالم
    await owner.tap(f"topup_pay_back:{payment_id}")
    amount = (await _payments())[0].final_amount
    assert owner.last_text.startswith("⬅️ برگشتی") and format_toman(amount) in owner.last_text
    assert "کدِ پرداخت" not in owner.last_text, "شناسه‌یِ عددیِ داخلی هرگز به کاربر نشان داده نمی‌شود"
    rows = await _payments()
    assert len(rows) == 1 and rows[0].status == PaymentStatus.PENDING and rows[0].receipt_text is None

    # «📂 پرداخت‌هایِ باز» ⇒ همان پرداخت در فهرست است و قابلِ ادامه
    await owner.say("💰 کیف‌پول")
    assert "topup_open_list" in _datas(owner.last_markup)
    await owner.tap("topup_open_list")
    assert f"topup_pay_resume:{payment_id}" in _datas(owner.last_markup), owner.last_markup
    assert format_toman(amount) in owner.last_text and "کدِ پرداخت" not in owner.last_text
    await owner.tap(f"topup_pay_resume:{payment_id}")
    assert owner.last_text == main_texts.topup_receipt_resume_text((await _payments())[0])

    # رسیدِ متنی پذیرفته می‌شود و به ادمین می‌رسد
    admin_id = _admin_id()
    await owner.say(RECEIPT_TEXT)
    assert _chat(owner, OWNER_TG_ID)[-1]["text"] == main_texts.RECEIPT_RECEIVED_PENDING_APPROVAL
    rows = await _payments()
    assert rows[0].receipt_text == RECEIPT_TEXT and rows[0].receipt_tracking_ref == "987654321"
    assert rows[0].receipt_flags is None, "اولین رسید پرچمِ تکراری نمی‌گیرد"
    assert rows[0].status == PaymentStatus.PENDING, "بدونِ تاییدِ ادمین اعتبار داده نمی‌شود"
    admin_notice = _chat(owner, admin_id)[-1]["text"]
    assert "رسیدِ متنی" in admin_notice and RECEIPT_TEXT in admin_notice, "ادمین باید متنِ رسید را ببیند"
    assert "987654321" in admin_notice
    print("✅ test_text_receipt_back_button_and_open_list PASSED")


async def _start_another_card_topup(chat: Chat) -> None:
    await chat.tap("topup_start")
    await chat.tap(f"topup_amount:{TOPUP_AMOUNT}")
    await chat.tap("skip_discount")
    await chat.tap("payment_method:card")


async def test_duplicate_text_receipt_is_flagged_not_rejected(main_dp) -> None:
    await _setup()
    first = Chat(main_dp, OWNER_TG_ID)
    await _start_card_topup(first)
    await first.say(RECEIPT_TEXT)
    assert (await _payments())[0].receipt_flags is None

    # همان متنِ رسید رویِ یک پرداختِ تازه ⇒ هم پرچمِ متنِ تکراری هم پرچمِ پیگیریِ تکراری، ولی ردِ خودکار نه
    second = Chat(main_dp, OWNER_TG_ID)
    await _start_another_card_topup(second)
    sent_before = len(second.sent)
    await second.say(RECEIPT_TEXT)
    rows = await _payments()
    assert len(rows) == 2
    assert rows[1].receipt_flags == "dup_file,dup_tracking", rows[1].receipt_flags
    assert rows[1].status == PaymentStatus.PENDING, "پرچم هرگز باعثِ ردِ خودکار نمی‌شود"
    admin_notice = next(
        (m["text"] for m in second.sent[sent_before:] if m["chat_id"] == _admin_id()), None
    )
    assert admin_notice and "پرچم" in admin_notice and "رسیدِ تکراری" in admin_notice, "ادمین باید پرچم را ببیند"
    assert "پیگیریِ تکراری" in admin_notice

    # متنِ متفاوت با همان شماره‌یِ پیگیری ⇒ فقط پرچمِ پیگیری
    third = Chat(main_dp, OWNER_TG_ID)
    await _start_another_card_topup(third)
    await third.say("واریز انجام شد مبلغ 100,042 تومان کد رهگیری 987654321")
    rows = await _payments()
    assert len(rows) == 3
    assert rows[2].receipt_flags == "dup_tracking", rows[2].receipt_flags
    assert rows[2].status == PaymentStatus.PENDING
    print("✅ test_duplicate_text_receipt_is_flagged_not_rejected PASSED")


async def test_invalid_text_receipt_and_ownership(main_dp) -> None:
    await _setup()
    await seed_usable_shop(OTHER_OWNER_TG_ID, OTHER_SHOP_TG_ID)
    owner = Chat(main_dp, OWNER_TG_ID)
    payment_id = await _start_card_topup(owner)

    for bad in ("سلام", "abc 12", "پرداخت کردم", "x" * 1001 + "1234"):
        await owner.say(bad)
        assert owner.last_text == main_texts.TOPUP_RECEIPT_TEXT_INVALID, bad
    rows = await _payments()
    assert rows[0].receipt_text is None and rows[0].status == PaymentStatus.PENDING, "رسیدِ نامعتبر ثبت نمی‌شود"

    # فروشگاه‌دارِ دیگر نه می‌تواند برگرداند، نه ادامه دهد، نه در فهرستِ خودش ببیند
    stranger = Chat(main_dp, OTHER_OWNER_TG_ID)
    await stranger.tap(f"topup_pay_back:{payment_id}")
    assert stranger.last_text == main_texts.TOPUP_PAYMENT_GONE
    await stranger.tap(f"topup_pay_resume:{payment_id}")
    assert stranger.last_text == main_texts.TOPUP_PAYMENT_GONE
    await stranger.tap("topup_open_list")
    assert stranger.last_text == main_texts.OPEN_TOPUP_PAYMENTS_EMPTY
    rows = await _payments()
    assert rows[0].status == PaymentStatus.PENDING and rows[0].receipt_text is None

    # کلیدِ جعلی/نامعتبر
    for data in ("topup_pay_back:999999", "topup_pay_back:abc", "topup_pay_resume:999999", "topup_pay_resume:"):
        await stranger.tap(data)
        assert stranger.last_text == main_texts.TOPUP_PAYMENT_GONE, data
    print("✅ test_invalid_text_receipt_and_ownership PASSED")


async def main() -> None:
    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    assert settings.admin_ids, "این تست به ADMIN_TELEGRAM_IDS نیاز دارد"
    await test_random_amount_only_for_card_and_wording()
    await test_text_receipt_back_button_and_open_list(main_dp)
    await test_duplicate_text_receipt_is_flagged_not_rejected(main_dp)
    await test_invalid_text_receipt_and_ownership(main_dp)


if __name__ == "__main__":
    asyncio.run(main())
