"""
تست: لایه‌یِ ۲ (W5) — تحلیلِ AIِ رسید (مشورتی)، تاییدِ دیرهنگام، هشدارِ بررسیِ رسید، حدودِ مهلتِ ادمین، برگشتِ موجودی،
توقفِ زمان (K3)، توقفِ جاب‌ها (K4) و هدیه/تمدیدِ گروهیِ ادمین (K1/K2). هیچ AI/شبکه‌یِ واقعی استفاده نمی‌شه.

اجرا: python3 tests_manual/test_w5_layer2.py
"""
from __future__ import annotations

import asyncio
import datetime
import json
import sys
from types import SimpleNamespace

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402
from sqlalchemy import func, select  # noqa: E402

from harness import FakeSession, build_test_dispatchers, make_callback_update, make_message_update  # noqa: E402
from test_admin_rbac import ADMIN_TG_ID, OPERATOR_TG_ID  # noqa: E402
from test_orders_w2 import CUSTOMER, OWNER, _Env, _seed  # noqa: E402
from test_payments_w3w4 import VALID_CARD, _configure, _datas, _payments, _set_deadline  # noqa: E402

from app.bots.main_bot import keyboards as main_keyboards  # noqa: E402
from app.database.models import (  # noqa: E402
    AdminCreditBatchItem,
    OrderConsultation,
    Product,
    ShopOwner,
    Subscription,
    SubscriptionStatus,
    TimeFreeze,
    WalletCharge,
    WalletTransaction,
)
from app.database.session import session_scope  # noqa: E402
from app.services import (  # noqa: E402
    ai_pool_service,
    ai_service,
    credit_batch_service,
    job_gate_service,
    order_payment_service,
    payment_expiry_service,
    payment_settings_service,
    receipt_ai_service,
    scheduler,
    time_freeze_service,
    wallet_service,
)
from app.services.admin_settings_service import get_admin_settings, update_setting  # noqa: E402

NOW = datetime.datetime.now(datetime.timezone.utc)


# ----------------------------------------------------------------------------- ابزارها
class _FakeAi:
    def __init__(self, text: str | None = None, error: Exception | None = None) -> None:
        self.text, self.error, self.calls = text, error, 0

    async def analyze_image(self, prompt: str, data: bytes):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return SimpleNamespace(text=self.text, total_tokens=100)


class _AiPatch:
    def __init__(self, fake: _FakeAi | None) -> None:
        self.fake, self.original = fake, None

    def __enter__(self):
        self.original = ai_pool_service.build_ai_service

        async def build(session, admin_settings, capability):
            return self.fake

        ai_pool_service.build_ai_service = build
        return self.fake

    def __exit__(self, *exc):
        ai_pool_service.build_ai_service = self.original


def _receipt_json(**overrides) -> str:
    data = {"is_receipt": True, "amount": 250_000, "date": None, "time": None, "dest_card_last4": VALID_CARD[-4:],
            "tracking_no": None, "status": "successful", "confidence": 0.9}
    data.update(overrides)
    return json.dumps(data)


async def _owner_balance() -> int:
    async with session_scope() as session:
        return (await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == OWNER))).scalar_one().wallet_balance_toman


async def _submit_photo_receipt(env: _Env, group: str, photo_bytes: bytes) -> None:
    env.shop_bot.session.set_downloaded_file("incoming_photo_id", photo_bytes)
    await env.cust_cb(f"pay_receipt:{group}")
    await env.shop_dp.feed_update(env.shop_bot, make_message_update(env._next(), user_id=CUSTOMER, photo=True))


async def _receipt_tx_count() -> int:
    async with session_scope() as session:
        return (
            await session.execute(select(func.count()).select_from(WalletTransaction).where(WalletTransaction.reason == "receipt_analysis"))
        ).scalar_one()


# ============================================================================= 2.1
async def test_receipt_parse_and_compare_pure() -> None:
    parse, compare = receipt_ai_service.parse_receipt_json, receipt_ai_service.compare
    ok = parse('```json\n{"is_receipt": true, "amount": "1,200,000", "dest_card_last4":"6274","status":"successful","confidence":0.9}\n```')
    assert ok and ok.amount == 1_200_000 and ok.dest_card_last4 == "6274"
    for bad in (None, "", "not json", "[]", '{"is_receipt":"yes"}', '{"amount":5}', "{"):
        assert parse(bad) is None, bad
    odd = parse('{"is_receipt": true,"amount":-5,"confidence":7,"status":"weird","dest_card_last4":"12"}')
    assert odd.amount is None and odd.confidence == 1.0 and odd.status == "unknown" and odd.dest_card_last4 is None

    created = NOW - datetime.timedelta(minutes=20)
    kw = dict(expected_toman=120_000, expected_last4="6274", order_created_at=created, now=NOW)

    def make(**o):
        base = dict(is_receipt=True, amount=120_000, date=None, time=None, dest_card_last4="6274", tracking_no=None, status="successful", confidence=0.9)
        base.update(o)
        return receipt_ai_service.ReceiptAnalysis(**base)

    assert compare(make(), **kw) == [] and compare(make(amount=1_200_000), **kw) == []
    assert compare(make(amount=5), **kw) == ["amount_mismatch"] and compare(make(amount=None), **kw) == ["amount_unreadable"]
    assert compare(make(dest_card_last4="1111"), **kw) == ["card_mismatch"]
    assert compare(make(is_receipt=False), **kw) == ["not_receipt"] and compare(make(status="failed"), **kw) == ["tx_failed"]
    assert "date_out_of_window" in compare(make(date="1390/01/01"), **kw)
    today = receipt_ai_service._jalali_str(NOW)
    assert compare(make(date=today.replace("/", "-")), **kw) == []
    verdict = receipt_ai_service.verdict_for
    assert verdict(None, []) == "error" and verdict(make(), []) == "ok" and verdict(make(), ["x"]) == "warn"
    assert verdict(make(is_receipt=False), ["not_receipt"]) == "bad"
    assert "تصمیم با توئه" in receipt_ai_service.advisory_line("ok", []) and "ناموفق" in receipt_ai_service.advisory_line("error", [])
    print("✅ test_receipt_parse_and_compare_pure PASSED")


async def test_receipt_ai_advisory_cost_and_failures(shop_dp, main_dp, bot_manager, main_bot) -> None:
    shop_bot_id, p1, p2 = await _seed()
    await _configure(shop_bot_id, card=True, max_attempts=9)
    env = _Env(shop_dp, main_dp, bot_manager, main_bot, shop_bot_id, p1, p2)
    async with session_scope() as session:
        cost = (await get_admin_settings(session)).wallet_cost_receipt_analysis_toman
        for product_id in (p1, p2):  # چند چک‌اوتِ پشت‌سرهم؛ موجودی نباید تمام بشه (وگرنه group_id قدیمی برمی‌گرده)
            (await session.get(Product, product_id)).stock_quantity = 50
    assert cost > 0

    # الف) هم‌خوان ⇒ خطِ مشورتی + هزینه
    g = await env.checkout([p1, p2])
    await env.cust_cb(f"pm_card:{g}")
    before = await _owner_balance()
    with _AiPatch(_FakeAi(_receipt_json())) as fake:
        await _submit_photo_receipt(env, g, b"receipt-bytes-A")
    assert fake.calls == 1
    caption = main_bot.session.sent_photos[-1]["caption"]
    assert "تحلیلِ خودکار" in caption and "هم‌خوان" in caption and "تصمیم با توئه" in caption
    pay = (await _payments())[0]
    assert pay.ai_verdict == "ok" and json.loads(pay.ai_json)["flags"] == []
    assert await _owner_balance() == before - cost and await _receipt_tx_count() == 1
    assert await env.statuses() == {"receipt_submitted"}, "مشورتی است؛ هرگز خودکار تایید/رد نمی‌شه"

    # ب) مبلغِ ناهم‌خوان ⇒ هشدار، باز هم فقط مشورتی
    await env.owner_cb(f"rcpt_nr:0:{pay.id}")
    with _AiPatch(_FakeAi(_receipt_json(amount=99_000))):
        await _submit_photo_receipt(env, g, b"receipt-bytes-B")
    caption = main_bot.session.sent_photos[-1]["caption"]
    assert "⚠️" in caption and "مبلغِ رسید با مبلغِ سفارش نمی‌خونه" in caption
    assert (await _payments())[-1].ai_verdict == "warn"

    # ج) خطایِ AI ⇒ بدونِ خط، بدونِ هزینه؛ رسید به فروشگاه‌دار می‌رسه
    g2 = await env.checkout([p1])
    await env.cust_cb(f"pm_card:{g2}")
    txs, photos = await _receipt_tx_count(), len(main_bot.session.sent_photos)
    with _AiPatch(_FakeAi(error=ai_service.AiServiceError("down"))):
        await _submit_photo_receipt(env, g2, b"receipt-bytes-C")
    assert len(main_bot.session.sent_photos) == photos + 1 and "تحلیلِ خودکار" not in main_bot.session.sent_photos[-1]["caption"]
    assert await _receipt_tx_count() == txs

    # د) JSONِ خراب ⇒ «ناموفق»، verdict=error، بدونِ هزینه
    g3 = await env.checkout([p1])
    await env.cust_cb(f"pm_card:{g3}")
    with _AiPatch(_FakeAi("این یک رسید است ولی JSON نیست")):
        await _submit_photo_receipt(env, g3, b"receipt-bytes-D")
    assert "ناموفق" in main_bot.session.sent_photos[-1]["caption"]
    assert (await _payments())[-1].ai_verdict == "error" and await _receipt_tx_count() == txs

    # ه) غیرفعال و اعتبارِ ناکافی ⇒ AI اصلاً صدا زده نمی‌شه
    async with session_scope() as session:
        (await payment_settings_service.get_or_create(session, shop_bot_id)).receipt_ai_enabled = False
    g4 = await env.checkout([p1])
    await env.cust_cb(f"pm_card:{g4}")
    with _AiPatch(_FakeAi(_receipt_json())) as fake:
        await _submit_photo_receipt(env, g4, b"receipt-bytes-E")
    assert fake.calls == 0
    async with session_scope() as session:
        (await payment_settings_service.get_or_create(session, shop_bot_id)).receipt_ai_enabled = True
        await update_setting(session, "wallet_cost_receipt_analysis_toman", 5_000_000)  # بیشتر از موجودی
    g5 = await env.checkout([p1])
    await env.cust_cb(f"pm_card:{g5}")
    with _AiPatch(_FakeAi(_receipt_json())) as fake:
        await _submit_photo_receipt(env, g5, b"receipt-bytes-F")
    assert fake.calls == 0
    print("✅ test_receipt_ai_advisory_cost_and_failures PASSED")


# ============================================================================= 2.2
async def _card_group_with_receipt(env: _Env, product_ids: list[int]) -> tuple[str, int]:
    g = await env.checkout(product_ids)
    await env.cust_cb(f"pm_card:{g}")
    await env.cust_cb(f"pay_receipt:{g}")
    await env.cust_say("۱۲۳۴۵۶۷۸۹۰۱۲")
    return g, (await _payments())[-1].id


async def test_late_receipt_approval(shop_dp, main_dp, bot_manager, main_bot) -> None:
    shop_bot_id, p1, p2 = await _seed()
    await _configure(shop_bot_id, card=True)
    env = _Env(shop_dp, main_dp, bot_manager, main_bot, shop_bot_id, p1, p2)
    g, pid = await _card_group_with_receipt(env, [p1])
    await _set_deadline(-1)
    assert await payment_expiry_service.process_payment_expiry(main_bot, bot_manager) == 1
    assert await env.statuses() == {"expired"} and (await _payments())[0].status == "expired"

    await env.owner_cb(f"rcpt_ok:{pid}")  # رسیدِ ثبت‌شده، بررسیِ دیرهنگام
    assert await env.statuses() == {"paid"}, "فروشگاه‌دار هنوز می‌تونه تایید کنه"
    assert (await _payments())[0].status == "approved"
    edited = env.owner_bot.session.edited_texts[-1]["text"] if env.owner_bot.session.edited_texts else ""
    assert "مهلتِ این سفارش تموم شده بود" in edited
    async with session_scope() as session:
        product = await session.get(Product, p1)
        assert product.stock_quantity == 2 and product.reserved_quantity == 0, "دوباره رزرو و مصرف شد"
    count = len(env.customer_msgs())
    await env.owner_cb(f"rcpt_ok:{pid}")  # دابل‌تپ
    assert len(env.customer_msgs()) == count and await env.statuses() == {"paid"}

    # بدونِ رسید: پرداختِ منقضیِ بدونِ رسید قابلِ تایید نیست
    g2 = await env.checkout([p1])
    await env.cust_cb(f"pm_card:{g2}")
    await _set_deadline(-1)
    await payment_expiry_service.process_payment_expiry(main_bot, bot_manager)
    pay2 = (await _payments())[-1]
    async with session_scope() as session:
        result = await order_payment_service.approve_payment(session, pay2.id, shop_bot_id, decided_by="1")
    assert not result.ok and result.reason == "illegal"
    print("✅ test_late_receipt_approval PASSED")


async def test_late_receipt_approval_oversold(shop_dp, main_dp, bot_manager, main_bot) -> None:
    shop_bot_id, p1, p2 = await _seed()
    await _configure(shop_bot_id, card=True)
    env = _Env(shop_dp, main_dp, bot_manager, main_bot, shop_bot_id, p1, p2)
    g, pid = await _card_group_with_receipt(env, [p1])
    await _set_deadline(-1)
    await payment_expiry_service.process_payment_expiry(main_bot, bot_manager)
    async with session_scope() as session:
        (await session.get(Product, p1)).stock_quantity = 0  # بینِ انقضا و تایید فروخته شد
    await env.owner_cb(f"rcpt_ok:{pid}")
    assert await env.statuses() == {"paid"}
    assert "کافی نیست" in env.owner_bot.session.edited_texts[-1]["text"]
    assert (await _payments())[0].needs_review is True
    print("✅ test_late_receipt_approval_oversold PASSED")


async def test_review_warning_sent_once(shop_dp, main_dp, bot_manager, main_bot) -> None:
    shop_bot_id, p1, p2 = await _seed()
    await _configure(shop_bot_id, card=True)
    env = _Env(shop_dp, main_dp, bot_manager, main_bot, shop_bot_id, p1, p2)
    g, pid = await _card_group_with_receipt(env, [p1])
    await _set_deadline(5 * 60)  # ۵ ساعت مانده ⇒ هنوز زود است
    before = len(main_bot.session.sent_messages)
    await payment_expiry_service.process_payment_expiry(main_bot, bot_manager)
    assert len(main_bot.session.sent_messages) == before

    await _set_deadline(90)  # ۱٫۵ ساعت مانده ⇒ هشدار
    await payment_expiry_service.process_payment_expiry(main_bot, bot_manager)
    warning = main_bot.session.sent_messages[-1]
    assert "هنوز بررسی نشده" in warning["text"] and f"rcpt_ok:{pid}" in _datas(warning["reply_markup"])
    count = len(main_bot.session.sent_messages)
    await payment_expiry_service.process_payment_expiry(main_bot, bot_manager)
    await payment_expiry_service.process_payment_expiry(main_bot, bot_manager)
    assert len(main_bot.session.sent_messages) == count, "هر رسید فقط یک‌بار هشدار می‌گیره"
    assert (await _payments())[0].review_warned_at is not None
    print("✅ test_review_warning_sent_once PASSED")


async def test_owner_deadline_bounds_come_from_code(shop_dp, main_dp, bot_manager, main_bot) -> None:
    """P18 · A5: بازه‌یِ مهلتِ پرداخت/بررسیِ رسید دیگر از پنلِ ادمین تنظیم نمی‌شود؛ فقط بازه‌یِ ایمنیِ کد."""
    assert payment_settings_service.deadline_bounds() == (5, 1440)
    assert payment_settings_service.review_hold_bounds() == (60, 4320)

    shop_bot_id, p1, p2 = await _seed()
    await _configure(shop_bot_id, card=True)
    env = _Env(shop_dp, main_dp, bot_manager, main_bot, shop_bot_id, p1, p2)

    await env.owner_cb("pays_dl:card")
    assert "بینِ ۵ و ۱۴۴۰" in env.owner_bot.session.sent_messages[-1]["text"], env.owner_bot.session.sent_messages[-1]["text"]
    await env.owner_say("1441")
    assert "بازه‌یِ مجاز: ۵ تا ۱۴۴۰ دقیقه" in env.owner_bot.session.sent_messages[-1]["text"]
    await env.owner_say("500")
    async with session_scope() as session:
        assert (await payment_settings_service.get_or_create(session, shop_bot_id)).card_deadline_minutes == 500
    await env.owner_cb("pays_hold")
    assert "بینِ ۶۰ و ۴۳۲۰" in env.owner_bot.session.sent_messages[-1]["text"]
    await env.owner_say("4321")  # ۶ ساعت = ۳۶۰ دقیقه دیگر سقفِ ادمین نیست؛ بازه‌یِ کد ۴۳۲۰ است
    assert "بازه‌یِ مجاز: ۶۰ تا ۴۳۲۰ دقیقه" in env.owner_bot.session.sent_messages[-1]["text"]
    await env.owner_say("300")
    async with session_scope() as session:
        assert (await payment_settings_service.get_or_create(session, shop_bot_id)).receipt_review_hold_minutes == 300
    print("✅ test_owner_deadline_bounds_come_from_code PASSED")


async def test_restock_after_refund(shop_dp, main_dp, bot_manager, main_bot) -> None:
    shop_bot_id, p1, p2 = await _seed()
    env = _Env(shop_dp, main_dp, bot_manager, main_bot, shop_bot_id, p1, p2)
    g = await env.checkout([p1])
    await env.owner_cb(f"confirm_cart_group:{g}")
    async with session_scope() as session:
        assert (await session.get(Product, p1)).stock_quantity == 2
        for row in (await session.execute(select(OrderConsultation))).scalars().all():
            row.status = "refunded"
    keyboard = main_keyboards.order_group_actions_keyboard(g, "refunded")
    assert f"og_restock:{g}" in _datas(keyboard)
    await env.owner_cb(f"og_restock:{g}")
    async with session_scope() as session:
        assert (await session.get(Product, p1)).stock_quantity == 3
    await env.owner_cb(f"og_restock:{g}")  # دابل‌تپ
    async with session_scope() as session:
        assert (await session.get(Product, p1)).stock_quantity == 3, "هر ردیف فقط یک‌بار برمی‌گرده"
        assert (await session.execute(select(OrderConsultation))).scalars().first().restocked_at is not None

    g2 = await env.checkout([p1])  # هنوز refunded نیست
    await env.owner_cb(f"og_restock:{g2}")
    assert env.owner_bot.session.answered_callbacks[-1]["show_alert"] is True
    async with session_scope() as session:
        assert (await session.get(Product, p1)).stock_quantity == 3, "گروهِ استردادنشده برنمی‌گرده"
    print("✅ test_restock_after_refund PASSED")


# ============================================================================= K3 / K4
async def _owner_with_sub(tg: int, *, end_in_days: float, status=SubscriptionStatus.ACTIVE) -> tuple[int, int]:
    async with session_scope() as session:
        owner = (await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == tg))).scalar_one()
        session.add(
            Subscription(
                shop_owner_id=owner.id, status=status, duration_months=1, is_trial=False,
                start_date=NOW - datetime.timedelta(days=20), end_date=NOW + datetime.timedelta(days=end_in_days),
            )
        )
        await session.flush()
        sub = (await session.execute(select(Subscription).where(Subscription.shop_owner_id == owner.id).order_by(Subscription.id.desc()))).scalars().first()
        return owner.id, sub.id


async def test_time_freeze_lifecycle(main_bot) -> None:
    await _seed()
    owner_id, sub_id = await _owner_with_sub(OWNER, end_in_days=5)
    async with session_scope() as session:
        charge = (await session.execute(select(WalletCharge).where(WalletCharge.shop_owner_id == owner_id))).scalars().first()
        charge.expires_at = NOW - datetime.timedelta(hours=1)  # در حالِ عادی همین الان منقضی می‌شد
        charge_id, charge_expiry = charge.id, charge.expires_at

    async with session_scope() as session:
        assert await time_freeze_service.start(session, scope="owner", owner_id=owner_id, max_days=0, reason=None, by="1") is None
        assert await time_freeze_service.start(session, scope="owner", owner_id=owner_id, max_days=31, reason=None, by="1") is None
        assert await time_freeze_service.start(session, scope="owner", owner_id=None, max_days=3, reason=None, by="1") is None
        freeze = await time_freeze_service.start(session, scope="owner", owner_id=owner_id, max_days=3, reason="تست", by="1")
        assert freeze is not None
        assert await time_freeze_service.start(session, scope="owner", owner_id=owner_id, max_days=3, reason=None, by="1") is None, "دابل‌تپ = یک ردیف"
        assert await time_freeze_service.start(session, scope="all", owner_id=None, max_days=3, reason=None, by="1") is None
        freeze_id, started = freeze.id, freeze.started_at

    async with session_scope() as session:
        assert await wallet_service.expire_stale_charges(session) == 0, "در توقف، شارژِ مشمول منقضی نمی‌شه"
        assert await wallet_service.find_charges_needing_reminder(session) == []
    async with session_scope() as session:
        sub = await session.get(Subscription, sub_id)
        sub.end_date = NOW - datetime.timedelta(minutes=5)
    async with session_scope() as session:
        from app.services import grace_period_service

        await grace_period_service.process_grace_transitions(session, main_bot)
        assert (await session.get(Subscription, sub_id)).status == SubscriptionStatus.ACTIVE, "در توقف وارد grace نمی‌شه"
        sub_end_before = (await session.get(Subscription, sub_id)).end_date

    delta = datetime.timedelta(days=2)
    async with session_scope() as session:
        live_charges = (
            await session.execute(
                select(func.count()).select_from(WalletCharge).where(
                    WalletCharge.shop_owner_id == owner_id, WalletCharge.is_expired.is_(False), WalletCharge.remaining_toman > 0
                )
            )
        ).scalar_one()
        resumed, changed = await time_freeze_service.resume(session, freeze_id, by="9", now=started + delta)
        assert changed and resumed.status == "resumed" and resumed.shifted_seconds == int(delta.total_seconds())
        assert resumed.affected_count == live_charges + 1, "همه‌یِ شارژهایِ زنده + اشتراک"
    async with session_scope() as session:
        assert (await session.get(WalletCharge, charge_id)).expires_at == charge_expiry + delta
        assert (await session.get(Subscription, sub_id)).end_date == sub_end_before + delta
        again, changed2 = await time_freeze_service.resume(session, freeze_id, by="9", now=started + datetime.timedelta(days=9))
        assert again is not None and not changed2, "ازسرگیریِ دوباره = بدونِ جابه‌جاییِ دوم"
    async with session_scope() as session:
        assert (await session.get(Subscription, sub_id)).end_date == sub_end_before + delta
        assert (await time_freeze_service.resume(session, 999_999, by="9"))[0] is None
    print("✅ test_time_freeze_lifecycle PASSED")


async def test_time_freeze_auto_resume_cap_and_all_scope(main_bot) -> None:
    await _seed()
    owner_id, sub_id = await _owner_with_sub(OWNER, end_in_days=10)
    async with session_scope() as session:
        freeze = await time_freeze_service.start(session, scope="all", owner_id=None, max_days=2, reason=None, by="1")
        assert freeze is not None
        assert await time_freeze_service.frozen_filter(session) == (True, set())
        fid, started = freeze.id, freeze.started_at
        end_before = (await session.get(Subscription, sub_id)).end_date
        # هنوز زود است: جابِ خودکار چیزی ازسرنمی‌گیره
        assert await time_freeze_service.auto_resume_due(session, now=started + datetime.timedelta(days=1)) == []
    async with session_scope() as session:
        resumed = await time_freeze_service.auto_resume_due(session, now=started + datetime.timedelta(days=30))  # جابِ خیلی دیرکرده
        assert [f.id for f in resumed] == [fid]
    async with session_scope() as session:
        assert (await session.get(Subscription, sub_id)).end_date == end_before + datetime.timedelta(days=2), "جبران حداکثر تا سقفِ ۲ روز"
        assert await time_freeze_service.frozen_filter(session) == (False, set())
        assert await time_freeze_service.auto_resume_due(session) == []
    print("✅ test_time_freeze_auto_resume_cap_and_all_scope PASSED")


async def test_jobs_pause_gates_scheduler(main_bot) -> None:
    await _seed()
    owner_id, _sub = await _owner_with_sub(OWNER, end_in_days=5)
    async with session_scope() as session:
        charge = (await session.execute(select(WalletCharge).where(WalletCharge.shop_owner_id == owner_id))).scalars().first()
        charge.expires_at = NOW - datetime.timedelta(hours=1)
        cid = charge.id
        await job_gate_service.toggle_group(session, "wallet", "7")
        admin_settings = await get_admin_settings(session)
        assert job_gate_service.is_paused(admin_settings, "wallet") and not job_gate_service.is_paused(admin_settings, "grace")
        assert await job_gate_service.toggle_group(session, "nope", "7") is None
    await scheduler.run_periodic_pass(main_bot)
    async with session_scope() as session:
        assert (await session.get(WalletCharge, cid)).is_expired is False, "گروهِ wallet متوقف است"
    async with session_scope() as session:
        await job_gate_service.toggle_group(session, "wallet", "7")  # ازسرگیری
        await job_gate_service.set_global(session, True, "7")
        admin_settings = await get_admin_settings(session)
        assert admin_settings.jobs_paused and admin_settings.jobs_paused_by == "7" and admin_settings.jobs_paused_at is not None
    await scheduler.run_periodic_pass(main_bot)
    async with session_scope() as session:
        assert (await session.get(WalletCharge, cid)).is_expired is False, "توقفِ کلی"
        await job_gate_service.set_global(session, False, "7")
        assert (await get_admin_settings(session)).jobs_paused_at is None
    await scheduler.run_periodic_pass(main_bot)
    async with session_scope() as session:
        assert (await session.get(WalletCharge, cid)).is_expired is True, "بعد از ازسرگیری جاب‌ها عقب‌افتاده‌ها رو می‌گیرن"
    print("✅ test_jobs_pause_gates_scheduler PASSED")


# ============================================================================= K1 / K2
async def test_credit_batches_service(main_bot) -> None:
    await _seed()
    owner_id, sub_id = await _owner_with_sub(OWNER, end_in_days=3)
    async with session_scope() as session:
        assert await credit_batch_service.create_batch(session, kind="gift", flt="all", by="1", amount=10) is None, "کمتر از کف"
        assert await credit_batch_service.create_batch(session, kind="gift", flt="bogus", by="1", amount=5_000) is None
        assert await credit_batch_service.create_batch(session, kind="extend", flt="all", by="1", days=0) is None
        assert await credit_batch_service.create_batch(session, kind="weird", flt="all", by="1") is None
        gift = await credit_batch_service.create_batch(session, kind="gift", flt="all", by="1", amount=5_000)
        assert gift is not None and gift.target_count == 1
        gid = gift.batch_id
    before = await _owner_balance()
    async with session_scope() as session:
        result = await credit_batch_service.execute(session, gid, by="1")
        assert result.changed and result.applied_owner_ids == [owner_id]
    async with session_scope() as session:
        again = await credit_batch_service.execute(session, gid, by="1")  # دابل‌تپ
        assert again.batch.status == "done" and not again.changed and again.applied_owner_ids == []
        refs = (await session.execute(select(func.count()).select_from(WalletTransaction).where(WalletTransaction.reference == f"batch:{gid}"))).scalar_one()
        assert refs == 1
    assert await _owner_balance() == before + 5_000

    # تمدید: اشتراکِ فعال تمدید، grace → active، expired رد می‌شه
    async with session_scope() as session:
        ext = await credit_batch_service.create_batch(session, kind="extend", flt="active", by="1", days=30)
        assert ext is not None and ext.target_count == 1
        eid = ext.batch_id
        end_before = (await session.get(Subscription, sub_id)).end_date
    async with session_scope() as session:
        res = await credit_batch_service.execute(session, eid, by="1")
        assert res.changed and res.applied_owner_ids == [owner_id]
    async with session_scope() as session:
        assert (await session.get(Subscription, sub_id)).end_date == end_before + datetime.timedelta(days=30)
        await credit_batch_service.execute(session, eid, by="1")
    async with session_scope() as session:
        assert (await session.get(Subscription, sub_id)).end_date == end_before + datetime.timedelta(days=30), "تمدیدِ تکراری نداریم"
        sub = await session.get(Subscription, sub_id)
        sub.status, sub.end_date = SubscriptionStatus.EXPIRED, NOW - datetime.timedelta(days=3)
        batch = await credit_batch_service.create_batch(session, kind="extend", flt="all", by="1", days=5)
        bid = batch.batch_id
    async with session_scope() as session:
        res = await credit_batch_service.execute(session, bid, by="1")
        assert res.changed and res.applied_owner_ids == [] and res.batch.skipped_count == 1, "اشتراکِ تمام‌شده تمدید نمی‌شه"
        assert (await session.execute(select(func.count()).select_from(AdminCreditBatchItem).where(AdminCreditBatchItem.batch_id == bid))).scalar_one() == 0

    # لغو، ادامه‌یِ بعد از کرش
    async with session_scope() as session:
        pending = await credit_batch_service.create_batch(session, kind="gift", flt="all", by="1", amount=7_000)
        pid = pending.batch_id
        assert await credit_batch_service.cancel(session, pid)
        assert (await credit_batch_service.execute(session, pid, by="1")).changed is False
        crashed = await credit_batch_service.create_batch(session, kind="gift", flt="all", by="1", amount=9_000)
        cid = crashed.batch_id
        session.add(AdminCreditBatchItem(batch_id=cid, shop_owner_id=owner_id))  # نیمه‌کاره: قبلاً برایِ این نفر انجام شده
        crashed.status = "running"
    before = await _owner_balance()
    async with session_scope() as session:
        res = await credit_batch_service.execute(session, cid, by="1")
        assert res.applied_owner_ids == [] and res.batch.status == "done"
    assert await _owner_balance() == before, "ردیفِ انجام‌شده دوباره اعمال نمی‌شه"
    print("✅ test_credit_batches_service PASSED")


async def test_admin_time_ui_flow(main_dp) -> None:
    await _seed()
    await _owner_with_sub(OWNER, end_in_days=4)
    bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())
    n = [5000]

    async def say(text: str, user: int = ADMIN_TG_ID) -> None:
        n[0] += 1
        await main_dp.feed_update(bot, make_message_update(n[0], text=text, user_id=user))

    async def tap(data: str, user: int = ADMIN_TG_ID) -> None:
        n[0] += 1
        await main_dp.feed_update(bot, make_callback_update(n[0], data=data, user_id=user))

    def last_datas() -> list[str]:
        markup = bot.session.sent_messages[-1]["reply_markup"]
        return _datas(markup) if markup is not None and hasattr(markup, "inline_keyboard") else []

    from app.services import admin_role_service

    async with session_scope() as session:
        await admin_role_service.grant_operator(session, OPERATOR_TG_ID, granted_by_telegram_id=ADMIN_TG_ID)
    await say("⏱ اعتبار و زمان")
    assert {"at_gift", "at_ext", "at_frz", "at_jobs"} <= set(last_datas())
    await say("⏱ اعتبار و زمان", user=OPERATOR_TG_ID)
    assert "at_gift" in last_datas() and "at_frz" not in last_datas() and "at_jobs" not in last_datas(), "ادمینِ عملیاتی: هدیه/تمدید بله، فریز/جاب نه"
    await tap("at_frz", user=OPERATOR_TG_ID)
    assert bot.session.answered_callbacks[-1]["show_alert"] is True and "سوپرادمین" in (bot.session.answered_callbacks[-1]["text"] or "")

    # هدیه‌یِ گروهی: انتخابِ هدف ← مبلغ ← پیش‌نمایش ← تایید (دابل‌تپ = یک اثر)
    await tap("at_gift")
    await tap("at_gf:all")
    await say("خیلی")
    assert "معتبر" in bot.session.sent_messages[-1]["text"]
    before = await _owner_balance()
    await say("۵٬۰۰۰")
    assert "پیش‌نمایشِ هدیه" in bot.session.sent_messages[-1]["text"]
    go = next(d for d in last_datas() if d.startswith("at_go:"))
    await asyncio.gather(tap(go), tap(go))
    assert await _owner_balance() == before + 5_000, "دابل‌تپِ تایید = یک‌بار اعمال"
    assert any("اعتبارِ هدیه" in m["text"] for m in bot.session.sent_messages), "فروشگاه‌دار خبردار می‌شه"

    # توقفِ زمان: شروع ← ازسرگیری
    await tap("at_frz")
    await tap("at_fs:all")
    await say("3")
    await say("-")
    assert "شروع شد" in bot.session.sent_messages[-1]["text"]
    async with session_scope() as session:
        freeze = (await session.execute(select(TimeFreeze))).scalars().one()
        fid = freeze.id
    await tap(f"at_fr:{fid}")
    assert "ازسرگرفته شد" in bot.session.sent_messages[-1]["text"]
    await tap(f"at_fr:{fid}")
    assert bot.session.answered_callbacks[-1]["show_alert"] is True

    # توقفِ جاب‌ها
    await tap("at_jobs")
    await tap("at_jt:wallet")
    async with session_scope() as session:
        assert job_gate_service.is_paused(await get_admin_settings(session), "wallet")
    await tap("at_jt:wallet")
    await tap("at_jt:bogus")
    assert bot.session.answered_callbacks[-1]["show_alert"] is True
    print("✅ test_admin_time_ui_flow PASSED")


async def main() -> None:
    main_dp_shop = build_test_dispatchers()
    _main_dp, shop_dp, bot_manager, main_bot = main_dp_shop
    main_dp = _main_dp
    await test_receipt_parse_and_compare_pure()
    await test_receipt_ai_advisory_cost_and_failures(shop_dp, main_dp, bot_manager, main_bot)
    await test_late_receipt_approval(shop_dp, main_dp, bot_manager, main_bot)
    await test_late_receipt_approval_oversold(shop_dp, main_dp, bot_manager, main_bot)
    await test_review_warning_sent_once(shop_dp, main_dp, bot_manager, main_bot)
    await test_owner_deadline_bounds_come_from_code(shop_dp, main_dp, bot_manager, main_bot)
    await test_restock_after_refund(shop_dp, main_dp, bot_manager, main_bot)
    await test_time_freeze_lifecycle(main_bot)
    await test_time_freeze_auto_resume_cap_and_all_scope(main_bot)
    await test_jobs_pause_gates_scheduler(main_bot)
    await test_credit_batches_service(main_bot)
    await test_admin_time_ui_flow(main_dp)


if __name__ == "__main__":
    asyncio.run(main())
