"""پ۵۴ · موردِ ۱۲: صفِ حرفه‌ایِ تاییدِ پرداخت‌ها.

پوششِ داده‌شده:
۱. `payment_service.pending_queue_page`: کمترین id اول، صفحه‌بندیِ بدونِ OFFSETِ بی‌سقف، شمارِ
   کلِ همان دامنه، دامنهٔ ادمینِ عملیاتی پیش ازِ صفحه‌بندی و ردِ صفحهٔ نامعتبر.
۲. هزینهٔ کوئری: هر صفحه حداکثر سه جمله (شمارشِ کل + ردیف‌ها + نامِ صاحبان).
۳. متن و کیبورد: جلالی/تهران، تومان، برچسبِ هدف و روش، بودجهٔ ۶۴ بایتیِ callback، ردیفِ
   صفحه‌گردانی فقط وقتی بیش از یکِ صفحه است، و دکمهٔ بازگشت به همان صفحه‌ای که از آن آمده‌ایم.
۴. رازها: شمارهٔ پیگیری و رسیدِ متنی برایِ ادمین مجاز است؛ شناسهٔ فایلِ رسید، هشِ رسید،
   authority/refِ زرین‌پال، payload/transactionِ بله و شناسهٔ داخلیِ فروشگاه‌دار هرگز چاپ نمی‌شوند.
۵. جریانِ واقعیِ پنل: فهرست ← صفحهٔ دوم ← کارتِ جزئیات ← تایید (یک‌بار، دقیقاً همان فلویِ قدیمیِ
   پولی) ← دوبارزدنِ همان دکمه ⇒ هیچ اعتبارِ دومی اضافه نمی‌شود.
۶. دامنه در پنل: ادمینِ عملیاتیِ دامنه‌دار فقط پرداخت‌هایِ دامنهٔ خودش را می‌بیند و با شمارِ
   فیلترشده؛ کال‌بکِ جعلیِ بیرونِ دامنه ⇒ اخطارِ «خارج از دامنه» و صفرِ تغییرِ مالی.
۷. ورودیِ خراب و غیرادمین: صفحه/شناسهٔ غیرعددی، شناسهٔ ناموجود و کاربرِ معمولی ⇒ هیچ اثری.

اجرا: python3 tests_manual/test_p54_payment_queue.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402
from sqlalchemy import select  # noqa: E402

from harness import FakeSession, build_test_dispatchers, make_callback_update, make_message_update, reset_database  # noqa: E402
from phase4_helpers import Chat, callbacks  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot import keyboards, texts as main_texts  # noqa: E402
from app.database.models import Payment, PaymentPurpose, PaymentStatus, ShopOwner, WalletCharge  # noqa: E402
from app.database.session import engine, session_scope  # noqa: E402
from app.services import admin_role_service, payment_service, shop_owner_service  # noqa: E402
from app.utils.validators import format_toman  # noqa: E402

ADMIN_TG_ID = 12345
OPERATOR_TG_ID = 995443
OWNER_A_TG_ID = 995441
OWNER_B_TG_ID = 995442
CUSTOMER_TG_ID = 995449
MAIN_TOKEN = "540000:FAKE_MAIN_BOT_TOKEN_FOR_P54_TESTING_ONLY"
SECRET_MARKERS = (
    "receipt-file-id-secret",
    "sha256-secret-value",
    "zarinpal-authority-secret",
    "zarinpal-ref-secret",
    "bale-invoice-payload-secret",
    "bale-transaction-secret",
)


async def seed(count_a: int = 12, count_b: int = 2) -> dict[str, list[int]]:
    """فروشگاه‌دار A و B با پرداخت‌هایِ کارت‌به‌کارتِ در انتظار؛ یکی هم تاییدشده تا از فهرست برود."""
    await reset_database()
    ids: dict[str, list[int]] = {"a": [], "b": [], "approved": []}
    for tg_id, bucket, total in ((OWNER_A_TG_ID, "a", count_a), (OWNER_B_TG_ID, "b", count_b)):
        await seed_usable_shop(tg_id, tg_id + 500)
        async with session_scope() as session:
            owner = await shop_owner_service.get_by_telegram_id(session, tg_id)
            for _ in range(total):
                payment = await payment_service.create_card_to_card_payment(
                    session, owner, 250_000, None, duration_months=1, purpose=PaymentPurpose.WALLET_TOPUP
                )
                ids[bucket].append(payment.id)
    async with session_scope() as session:
        owner = await shop_owner_service.get_by_telegram_id(session, OWNER_A_TG_ID)
        done = await payment_service.create_card_to_card_payment(
            session, owner, 250_000, None, duration_months=1, purpose=PaymentPurpose.WALLET_TOPUP
        )
        done.status = PaymentStatus.APPROVED
        ids["approved"].append(done.id)
        target = await session.get(Payment, ids["a"][0])
        target.receipt_file_id = SECRET_MARKERS[0]
        target.receipt_sha256 = SECRET_MARKERS[1]
        target.receipt_tracking_ref = "TRK-54-0001"
        target.receipt_text = "کارِ 60xxxxxx1234 به مبلغ 250,000 تومان"
        target.receipt_flags = "dup_tracking"
        target.zarinpal_authority = SECRET_MARKERS[2]
        target.zarinpal_ref_id = SECRET_MARKERS[3]
        target.bale_invoice_payload = SECRET_MARKERS[4]
        target.bale_transaction_id = SECRET_MARKERS[5]
    return ids


async def _balance(owner_tg_id: int) -> int:
    async with session_scope() as session:
        owner = await shop_owner_service.get_by_telegram_id(session, owner_tg_id)
        return owner.wallet_balance_toman


async def _charge_count(payment_id: int) -> int:
    async with session_scope() as session:
        rows = (await session.execute(select(WalletCharge).where(WalletCharge.payment_id == payment_id))).scalars().all()
        return len(list(rows))


async def test_pending_queue_page_is_scoped_and_paged() -> None:
    ids = await seed()
    async with session_scope() as session:
        first, total = await payment_service.pending_queue_page(session, page=0)
        second, _ = await payment_service.pending_queue_page(session, page=1)
        beyond, _ = await payment_service.pending_queue_page(session, page=7)
    assert total == len(ids["a"]) + len(ids["b"]), total
    assert [p.id for p in first] == sorted(ids["a"] + ids["b"])[:10], "کمترین id اول"
    assert [p.id for p in second] == sorted(ids["a"] + ids["b"])[10:], "صفحهٔ دومِ باقی‌مانده"
    assert beyond == [], "صفحهٔ بیرونِ دامنه باید خالی باشد نه خطا"
    assert all(p.status == PaymentStatus.PENDING for p in first + second)

    async with session_scope() as session:
        owner_b = await shop_owner_service.get_by_telegram_id(session, OWNER_B_TG_ID)
        scoped, scoped_total = await payment_service.pending_queue_page(session, owner_ids={owner_b.id}, page=0)
        empty_scope, empty_total = await payment_service.pending_queue_page(session, owner_ids=set(), page=0)
    assert scoped_total == len(ids["b"]) == 2 and [p.id for p in scoped] == ids["b"], "دامنهٔ ادمینِ عملیاتی"
    assert (empty_scope, empty_total) == ([], 0), "دامنهٔ تهی ⇒ صفر ردیف و صفر شمار"

    async with session_scope() as session:
        for bad_page in (-1, "0", 1.0, None):
            try:
                await payment_service.pending_queue_page(session, page=bad_page)
            except ValueError:
                pass
            else:
                raise AssertionError(f"صفحهٔ نامعتبر پذیرفته شد: {bad_page!r}")
    print("PASS test_pending_queue_page_is_scoped_and_paged")


async def test_queue_queries_are_bounded() -> None:
    await seed()
    statements = []
    listener = lambda conn, cursor, statement, params, context, executemany: statements.append(statement)  # noqa: E731
    from sqlalchemy import event

    event.listen(engine.sync_engine, "before_cursor_execute", listener)
    try:
        async with session_scope() as session:
            await payment_service.pending_queue_page(session, page=0)
        counted = len(statements)
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", listener)
    assert counted <= 3, f"صفحهٔ فهرست باید حداکثر سه جمله بزند، زده شد {counted}"
    print("PASS test_queue_queries_are_bounded")


async def test_queue_text_and_keyboard() -> None:
    await seed()
    async with session_scope() as session:
        payments, total = await payment_service.pending_queue_page(session, page=0)
        owners = await shop_owner_service.get_by_ids(session, [p.shop_owner_id for p in payments])
    intro = main_texts.admin_payment_queue_intro(total, 0, 2)
    assert "۱۴ پرداخت" in intro and "صفحه" in intro, intro
    first = payments[0]
    line = main_texts.admin_payment_queue_line(first, owners[first.shop_owner_id])
    assert format_toman(first.final_amount) in line, line
    assert "شارژِ کیف‌پول" in line and "کارت‌به‌کارت" in line, line
    assert not any(marker in line for marker in SECRET_MARKERS)

    keyboard = keyboards.admin_payment_queue_keyboard(payments, owners, 0, 2)
    flat = callbacks(keyboard)
    assert flat[:10] == [f"pay_queue_view:0:{p.id}" for p in payments], flat
    assert flat[10:] == ["noop", "pay_queue:1"], f"صفحهٔ اول نباید دکمهٔ قبلی داشته باشد: {flat}"
    assert all(len(value.encode("utf-8")) <= 64 for value in flat), flat
    labels = [b.text for row in keyboard.inline_keyboard for b in row]
    assert labels[0].startswith("۱ · ") and all(len(label) <= 64 for label in labels), labels

    second = callbacks(keyboards.admin_payment_queue_keyboard(payments, owners, 1, 2))
    assert second[-2:] == ["pay_queue:0", "noop"], f"صفحهٔ آخر نباید بعدی داشته باشد: {second}"

    detail = keyboards.admin_payment_detail_keyboard(payments[0].id, page=1)
    detail_flat = callbacks(detail)
    assert f"admin_approve_payment:{payments[0].id}" in detail_flat, detail_flat
    assert f"admin_reject_payment:{payments[0].id}" in detail_flat, detail_flat
    assert "pay_queue:1" in detail_flat, "بازگشت باید به همان صفحهٔ فهرست برود"

    only_one_page = keyboards.admin_payment_queue_keyboard(payments[:3], owners, 0, 1)
    assert not any(value.startswith("pay_queue:") for value in callbacks(only_one_page)), "صفحه‌گردانیِ بی‌مورد"
    print("PASS test_queue_text_and_keyboard")


async def test_detail_card_keeps_secrets_out() -> None:
    ids = await seed()
    async with session_scope() as session:
        payment = await session.get(Payment, ids["a"][0])
        owner = await session.get(ShopOwner, payment.shop_owner_id)
        body = main_texts.admin_payment_detail_text(payment, owner, page=0)
    assert "TRK-54-0001" in body, "شمارهٔ پیگیری برایِ تصمیمِ ادمین لازم است"
    assert "60xxxxxx1234" in body, "رسیدِ متنی فقط به ادمین می‌رسد"
    assert "پرچم" in body and "پیگیریِ تکراری" in body, body
    assert not any(marker in body for marker in SECRET_MARKERS), body
    assert "فروشگاه‌دار:" in body, "هویتِ صاحبِ حساب با نامِ خودش نوشته می‌شود"
    assert format_toman(payment.base_amount) in body and format_toman(payment.final_amount) in body, body
    assert "۲" in body and "صفحهٔ ۱" in body, body
    assert any(0x06F0 <= ord(char) <= 0x06F9 for char in body), "ارقامِ فارسی"
    print("PASS test_detail_card_keeps_secrets_out")


async def test_panel_flow_approves_once(main_dp) -> None:
    ids = await seed()
    before = await _balance(OWNER_A_TG_ID)
    admin = Chat(main_dp, ADMIN_TG_ID)
    await admin.say("🧾 صف تایید پرداخت‌ها")
    screen = admin.last_text
    assert "۱۴ پرداخت" in screen and "کارت‌به‌کارت" in screen, screen
    assert "pay_queue_view" in "".join(callbacks(admin.last_markup))

    await admin.tap("pay_queue:1")
    assert "صفحه" in admin.last_edit_text, admin.last_edit_text

    target = ids["a"][0]
    await admin.tap(f"pay_queue_view:0:{target}")
    detail = admin.last_edit_text
    assert "TRK-54-0001" in detail, detail

    await admin.tap(f"admin_approve_payment:{target}")
    after = await _balance(OWNER_A_TG_ID)
    assert after > before, "تایید از کارتِ جزئیات همان فلویِ پولیِ همیشگی است"
    assert await _charge_count(target) == 1, "دقیقاً یکِ شارژ"
    async with session_scope() as session:
        payment = await session.get(Payment, target)
        assert payment.status == PaymentStatus.APPROVED

    await admin.tap(f"admin_approve_payment:{target}")
    assert await _balance(OWNER_A_TG_ID) == after, "دوبارزدنِ تایید ⇒ صفر تغییرِ مالی"
    assert await _charge_count(target) == 1, "شارژِ دومی ساخته نشد"

    other = ids["a"][1]
    await admin.tap(f"pay_queue_view:0:{other}")
    await admin.tap(f"admin_reject_payment:{other}")
    async with session_scope() as session:
        rejected = await session.get(Payment, other)
        assert rejected.status == PaymentStatus.REJECTED, rejected.status
    assert await _balance(OWNER_A_TG_ID) == after, "رد ⇒ هیچ اعتباری"
    assert await _charge_count(other) == 0
    print("PASS test_panel_flow_approves_once")


async def test_operator_sees_only_its_scope(main_dp) -> None:
    ids = await seed()
    async with session_scope() as session:
        await admin_role_service.grant_operator(session, OPERATOR_TG_ID, granted_by_telegram_id=ADMIN_TG_ID)
        role = await admin_role_service.get_by_telegram_id(session, OPERATOR_TG_ID)
        owner_a = await shop_owner_service.get_by_telegram_id(session, OWNER_A_TG_ID)
        await admin_role_service.set_scope(session, role, [owner_a.id])

    operator = Chat(main_dp, OPERATOR_TG_ID)
    await operator.say("🧾 صف تایید پرداخت‌ها")
    head = " ".join(operator.last_text.splitlines()[:2])
    assert "۱۲ پرداخت" in head, head
    assert "۱۴ پرداخت" not in head, "شمارِ کلِ دامنه نباید از عددِ سراسری پرده بردارد"
    flat = "".join(callbacks(operator.last_markup))
    for payment_id in ids["b"]:
        assert f"pay_queue_view:0:{payment_id}" not in flat, "پرداختِ بیرونِ دامنه در فهرست نیست"

    before = await _balance(OWNER_B_TG_ID)
    await operator.tap(f"pay_queue_view:0:{ids['b'][0]}")
    assert operator.last_toast["text"] == main_texts.ADMIN_OWNER_OUT_OF_SCOPE_TOAST, operator.last_toast
    await operator.tap(f"admin_approve_payment:{ids['b'][0]}")
    assert await _balance(OWNER_B_TG_ID) == before, "تاییدِ بیرونِ دامنه هیچ اعتباری نمی‌سازد"
    print("PASS test_operator_sees_only_its_scope")


async def test_bad_callbacks_and_non_admin_do_nothing(main_dp) -> None:
    await seed()
    before_a = await _balance(OWNER_A_TG_ID)
    admin = Chat(main_dp, ADMIN_TG_ID)
    await admin.say("🧾 صف تایید پرداخت‌ها")
    for data in ("pay_queue:abc", "pay_queue:-3", "pay_queue:999999", "pay_queue_view:abc",
                 "pay_queue_view:0:999999999", "pay_queue_view:0:0", "pay_queue:0:1"):
        await admin.tap(data)
        assert admin.last_toast["text"], f"{data} بی‌جواب ماند"
    assert await _balance(OWNER_A_TG_ID) == before_a

    bot = Bot(token=MAIN_TOKEN, session=FakeSession())
    outsider = bot.session
    for index, data in enumerate(("pay_queue:0", "pay_queue_view:0:1"), 900):
        await main_dp.feed_update(bot, make_callback_update(index, data=data, user_id=CUSTOMER_TG_ID))
    await main_dp.feed_update(bot, make_message_update(950, text="🧾 صف تایید پرداخت‌ها", user_id=CUSTOMER_TG_ID))
    assert not outsider.sent_messages and not outsider.edited_texts, "فقط ادمین"
    await bot.session.close()
    assert await _balance(OWNER_A_TG_ID) == before_a
    print("PASS test_bad_callbacks_and_non_admin_do_nothing")


async def main() -> None:
    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    await test_pending_queue_page_is_scoped_and_paged()
    await test_queue_queries_are_bounded()
    await test_queue_text_and_keyboard()
    await test_detail_card_keeps_secrets_out()
    await test_panel_flow_approves_once(main_dp)
    await test_operator_sees_only_its_scope(main_dp)
    await test_bad_callbacks_and_non_admin_do_nothing(main_dp)
    print("📊 نتیجه: ۷ تستِ پ۵۴ (صفِ تاییدِ پرداخت‌ها) پاس شد · دامنه/صفحه‌بندی/راز/تک‌بارِ پول")


if __name__ == "__main__":
    asyncio.run(main())
