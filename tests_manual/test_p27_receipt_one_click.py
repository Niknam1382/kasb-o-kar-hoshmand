"""
تست: P27 — «تاییدِ رسید» باید با یکِ کلیک تمام شود (نه دو تا)

۱. اگر پاسخِ کالبک رد شود («Bad Request: query is too old…» — همان خطایی که در لاگِ زندهٔ این پروژه
   دیده شد) یا کارِ جانبیِ بعد ازِ تایید (اعلانِ مشتری/فاکتور/تحویلِ دیجیتال) بترکد، پیامِ
   فروشگاه‌دار باید همان‌جا به‌روز شود. پیش ازِ این رفع، هندلر همان‌جا می‌مرد و دکمهٔ «✅ تایید» رویِ
   پیام می‌ماند ⇒ فروشگاه‌دار دو بار می‌زد (بارِ دوم فقط پیام را عوض می‌کرد).
۲. پیامِ رسیدِ عکس/فایلی با edit_caption به‌روز می‌شود؛ تلگرام edit_text را رویِ آن نوعِ پیام رد
   می‌کند و کیبوردِ کهنه رویِ پیامِ اصلی می‌ماند.
۳. رگرسیون: یکِ کلیک ⇒ paid + برداشتنِ کیبوردِ رسید + یکِ فاکتور؛ کلیکِ دوم ⇒ بی‌اثر.

اجرا: python3 tests_manual/run_one.py test_p27_receipt_one_click.py
"""
from __future__ import annotations

import asyncio
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests_manual"))

from aiogram.exceptions import TelegramBadRequest  # noqa: E402

from harness import build_test_dispatchers  # noqa: E402
from test_orders_w2 import _Env, _seed  # noqa: E402
from test_payments_w3w4 import _configure, _datas, _payments  # noqa: E402

from app.bots.main_bot import texts as main_texts  # noqa: E402
from app.bots.main_bot.handlers import order_ops, payment_ops  # noqa: E402
from app.database.models import OrderPayment  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import order_payment_service, order_state  # noqa: E402


async def _receipt_ready(shop_dp, main_dp, bot_manager, main_bot):
    """سفارش را تا مرحلهٔ «رسید ثبت شد» می‌برد و (env, payment_id) برمی‌گرداند."""
    shop_bot_id, p1, p2 = await _seed()
    await _configure(shop_bot_id, card=True)
    env = _Env(shop_dp, main_dp, bot_manager, main_bot, shop_bot_id, p1, p2)
    group = await env.checkout([p1, p2])
    await env.cust_cb(f"pm_card:{group}")
    await env.cust_cb(f"pay_receipt:{group}")
    await env.cust_say("۱۲۳۴۵۶۷۸۹۰۱۲")
    assert await env.statuses() == {order_state.RECEIPT_SUBMITTED}
    rows = await _payments()
    assert len(rows) == 1 and rows[0].status == order_payment_service.P_SUBMITTED, rows
    review = next(m for m in reversed(main_bot.session.sent_messages) if f"rcpt_ok:{rows[0].id}" in _datas(m["reply_markup"]))
    assert f"rcpt_no:{rows[0].id}" in _datas(review["reply_markup"])
    return env, rows[0].id


# ============================================================================= ۱ — پاسخِ دیرهنگامِ کالبک
async def test_late_callback_answer_still_updates_owner_message(shop_dp, main_dp, bot_manager, main_bot) -> None:
    env, payment_id = await _receipt_ready(shop_dp, main_dp, bot_manager, main_bot)
    owner_session = env.owner_bot.session
    owner_session.fail_answer_callbacks = True
    try:
        await env.owner_cb(f"rcpt_ok:{payment_id}")
    finally:
        owner_session.fail_answer_callbacks = False

    assert await env.statuses() == {order_state.PAID}, "تایید باید انجام شده باشد"
    assert owner_session.edited_texts, "بدونِ ویرایشِ پیام، دکمهٔ «✅ تایید» می‌ماند و کاربر دوباره می‌زند"
    assert main_texts.PAYS_APPROVED_SUFFIX in owner_session.edited_texts[-1]["text"]
    buttons = [b.text for row in owner_session.edited_texts[-1]["reply_markup"].inline_keyboard for b in row]
    assert not any("تایید" in label for label in buttons), f"کیبوردِ رسید باید عوض شود: {buttons}"
    print("✅ test_late_callback_answer_still_updates_owner_message PASSED")


# ============================================================================= ۲ — شکستِ کارِ جانبی
async def test_side_task_failure_still_updates_owner_message(shop_dp, main_dp, bot_manager, main_bot) -> None:
    env, payment_id = await _receipt_ready(shop_dp, main_dp, bot_manager, main_bot)

    async def explode(*_args, **_kwargs):
        raise RuntimeError("ساختِ فاکتور شکست خورد (شبیه‌سازی)")

    original = payment_ops.send_invoice_to_customer
    payment_ops.send_invoice_to_customer = explode
    try:
        await env.owner_cb(f"rcpt_ok:{payment_id}")
    finally:
        payment_ops.send_invoice_to_customer = original

    assert await env.statuses() == {order_state.PAID}, "تایید نباید به کارِ جانبی گره بخورد"
    edits = env.owner_bot.session.edited_texts
    assert edits, "پیامِ فروشگاه‌دار به‌روز نشده ⇒ کلیکِ دوم لازم می‌شود"
    assert main_texts.PAYS_APPROVED_SUFFIX in edits[-1]["text"]
    assert main_texts.PAYS_CUSTOMER_NOTIFY_FAILED in edits[-1]["text"], "شکستِ ارسال باید صادقانه گفته شود"
    async with session_scope() as session:
        payment = await session.get(OrderPayment, payment_id)
    assert payment.status == order_payment_service.P_APPROVED, payment.status
    print("✅ test_side_task_failure_still_updates_owner_message PASSED")


# ============================================================================= ۳ — رسیدِ عکس/فایلی
async def test_document_receipt_message_is_edited_by_caption() -> None:
    """رویِ پیامِ document یا photo تلگرام edit_text را رد می‌کند؛ هندلر باید edit_caption برود."""

    class StubMessage:
        def __init__(self) -> None:
            self.photo = None
            self.document = object()
            self.caption = "رسیدِ مشتری"
            self.text = None
            self.edited_captions: list[tuple] = []
            self.edited_texts: list[str] = []
            self.answered: list[str] = []

        async def edit_caption(self, *, caption, reply_markup=None):
            self.edited_captions.append((caption, reply_markup))

        async def edit_text(self, text, *, reply_markup=None):
            raise TelegramBadRequest(method="editMessageText", message="Bad Request: message is not of type text")

        async def answer(self, text, *, reply_markup=None):
            self.answered.append(text)

    class StubCallback:
        def __init__(self) -> None:
            self.message = StubMessage()

    callback = StubCallback()
    await order_ops._edit_owner_message(callback, "✅ پرداخت تایید شد", None)
    assert callback.message.edited_captions == [("✅ پرداخت تایید شد", None)], callback.message.edited_captions
    assert callback.message.edited_texts == [] and callback.message.answered == [], "پیامِ تکراری نساز؛ کیبوردِ کهنه رویِ پیامِ اصلی می‌ماند"
    print("✅ test_document_receipt_message_is_edited_by_caption PASSED")


# ============================================================================= ۴ — یک‌کلیک کافی است + دابل‌تپ
async def test_single_click_approves_and_replaces_keyboard(shop_dp, main_dp, bot_manager, main_bot) -> None:
    env, payment_id = await _receipt_ready(shop_dp, main_dp, bot_manager, main_bot)
    messages_before = len(env.customer_msgs())
    documents_before = len(env.shop_bot.session.sent_documents)
    edits_before = len(env.owner_bot.session.edited_texts)

    await env.owner_cb(f"rcpt_ok:{payment_id}")

    assert await env.statuses() == {order_state.PAID}
    edits = env.owner_bot.session.edited_texts
    assert len(edits) == edits_before + 1, "یکِ کلیک ⇒ دقیقاً یکِ ویرایشِ پیامِ فروشگاه‌دار"
    assert main_texts.PAYS_APPROVED_SUFFIX in edits[-1]["text"]
    fresh = env.customer_msgs()[messages_before:]
    assert any("تایید شد" in m for m in fresh), f"مشتری باید خبرِ تایید را ببیند: {fresh}"
    assert any(m.startswith("🧾 فاکتورِ") for m in fresh), f"فاکتور هم همان‌جا فرستاده می‌شود: {fresh}"
    assert len(env.shop_bot.session.sent_documents) == documents_before + 1, env.shop_bot.session.sent_documents

    messages_after = len(env.customer_msgs())
    documents_after = len(env.shop_bot.session.sent_documents)
    edits_after = len(env.owner_bot.session.edited_texts)
    await env.owner_cb(f"rcpt_ok:{payment_id}")  # دابل‌تپ
    assert len(env.customer_msgs()) == messages_after, "کلیکِ دوم نباید دوباره به مشتری پیام بدهد"
    assert len(env.shop_bot.session.sent_documents) == documents_after
    assert len(env.owner_bot.session.edited_texts) == edits_after + 1, "کلیکِ دوم فقط پیام را به‌روز می‌کند (تایید ایدمپوتنت است)"
    assert main_texts.PAYS_APPROVED_SUFFIX in env.owner_bot.session.edited_texts[-1]["text"]
    print("✅ test_single_click_approves_and_replaces_keyboard PASSED")


async def main() -> None:
    main_dp, shop_dp, bot_manager, main_bot = build_test_dispatchers()
    await test_single_click_approves_and_replaces_keyboard(shop_dp, main_dp, bot_manager, main_bot)
    await test_late_callback_answer_still_updates_owner_message(shop_dp, main_dp, bot_manager, main_bot)
    await test_side_task_failure_still_updates_owner_message(shop_dp, main_dp, bot_manager, main_bot)
    await test_document_receipt_message_is_edited_by_caption()
    print("\n✅ همهٔ تست‌هایِ P27ِ «تاییدِ رسید با یکِ کلیک» پاس شدند")


if __name__ == "__main__":
    asyncio.run(main())
