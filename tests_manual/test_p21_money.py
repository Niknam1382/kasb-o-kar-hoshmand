"""
تست: P21-C — قیمتِ منصفانهٔ صوت/رسید، طلبِ کمیسیون، و مسیرِ داغِ یک‌گزاره‌ای

پوشش:
۱. `estimate_voice_cost`: خاموش ⇒ همان نرخِ ثابت؛ روشن ⇒ دقیقه_گرد_بالا × نرخ، ولی **هرگز
   کمتر از کفِ فعلی** (هیچ‌کس ارزان‌تر از امروز نمی‌دهد، فقط ویسِ بلند گران‌تر می‌شود).
۲. `estimate_receipt_cost`: با usageِ واقعی توکن‌محور، بدونِ usage ⇒ همان نرخِ ثابت (نه تخمینِ ساختگی).
۳. `commission_receivable_service`: بدهی با قیدِ یکتا یک‌بار ثبت می‌شود، با شارژِ کافی وصول
   می‌شود، holdِ کمیسیونِ سفارشِ دیگر خرج نمی‌شود، و summary عددِ درستی می‌دهد.
۴. `commission_service.settle` با موجودیِ ناکافی ⇒ دیگر فقط لاگ نیست؛ بدهی ثبت می‌شود.
۵. `customer_service.get_or_create_customer` یک‌گزاره‌ای: معنایِ قبلی دست‌نخورده —
   «None ⇒ پاک نکند»، «تازه ⇒ جایگزین کن»، و «پلتفرمِ دیگر ⇒ ردیفِ جدا» (قاعدهٔ P19).
۶. `conversation_service.save_turn` دو ردیفِ user/assistant را به همان ترتیب می‌نویسد.

اجرا: python3 tests_manual/test_p21_money.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from sqlalchemy import func, select  # noqa: E402

from harness import reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.database.models import (  # noqa: E402
    CommissionReceivable,
    ConversationMessage,
    Customer,
    OrderConsultation,
    OrderStatus,
    OrderType,
    ShopOwner,
    WalletTransactionReason,
)
from app.database.session import session_scope  # noqa: E402
from app.services import (  # noqa: E402
    commission_receivable_service,
    commission_service,
    conversation_service,
    customer_service,
    platform_service,
    wallet_service,
)

OWNER_TG_ID = 999_761
SHOP_BOT_TG_ID = 999_762
GROUP = "p21-money-group"


def _settings(**overrides):
    base = {
        "wallet_cost_voice_transcription_toman": 300,
        "wallet_cost_voice_per_minute_toman": 0,
        "wallet_cost_receipt_analysis_toman": 500,
        "wallet_cost_receipt_per_1k_tokens": 0,
    }
    base.update(overrides)
    return type("S", (), base)()


# ============================================================================= ۱ و ۲ — قیمت‌گذاری
def test_voice_cost_is_never_cheaper_than_today() -> None:
    off = _settings()
    assert wallet_service.estimate_voice_cost(off, 120) == 300, "با ۰ ⇒ همان رفتارِ قبل"
    assert wallet_service.estimate_voice_cost(off, None) == 300

    on = _settings(wallet_cost_voice_per_minute_toman=900)
    assert wallet_service.estimate_voice_cost(on, 3) == 900, "رونویسی دقیقه‌ای حساب می‌شود: ۳ ثانیه = یک دقیقه"
    assert wallet_service.estimate_voice_cost(on, 60) == 900
    assert wallet_service.estimate_voice_cost(on, 61) == 1800, "گردِ بالا به دقیقهٔ کامل"
    assert wallet_service.estimate_voice_cost(on, 130) == 2700
    assert wallet_service.estimate_voice_cost(on, 0) == 300, "مدتِ نامعلوم ⇒ کفِ فعلی"
    assert wallet_service.estimate_voice_cost(on, -5) == 300

    # نرخِ دقیقه‌ایِ ارزان‌تر از کف ⇒ کف برنده است: هیچ‌کس ارزان‌تر از امروز نمی‌دهد
    cheap = _settings(wallet_cost_voice_per_minute_toman=100)
    assert wallet_service.estimate_voice_cost(cheap, 3) == 300
    assert wallet_service.estimate_voice_cost(cheap, 180) == 300, "سه دقیقه × ۱۰۰ = ۳۰۰ (همان کف)"
    assert wallet_service.estimate_voice_cost(cheap, 240) == 400
    print("✅ test_voice_cost_is_never_cheaper_than_today PASSED")


def test_receipt_cost_follows_reported_tokens_only() -> None:
    flat = _settings()
    assert wallet_service.estimate_receipt_cost(flat, 4000) == 500, "خاموش ⇒ نرخِ ثابت"
    assert wallet_service.estimate_receipt_cost(flat, None) == 500

    on = _settings(wallet_cost_receipt_per_1k_tokens=250)
    assert wallet_service.estimate_receipt_cost(on, 4000) == 1000
    assert wallet_service.estimate_receipt_cost(on, 1000) == 250
    assert wallet_service.estimate_receipt_cost(on, None) == 500, "بدونِ usageِ ارائه‌دهنده تخمینِ ساختگی نمی‌سازیم"
    assert wallet_service.estimate_receipt_cost(on, 300) == 75, "وزنی ولی نه صفر"
    assert wallet_service.estimate_receipt_cost(_settings(wallet_cost_receipt_per_1k_tokens=1), 10) == 1, "حداقلِ ۱ تومان"
    print("✅ test_receipt_cost_follows_reported_tokens_only PASSED")


# ============================================================================= ۳ — چرخهٔ عمرِ بدهی
async def _owner_id() -> int:
    async with session_scope() as session:
        return (await session.execute(select(ShopOwner.id).where(ShopOwner.telegram_id == OWNER_TG_ID))).scalar_one()


async def test_receivable_lifecycle_records_and_collects() -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID, initial_balance_toman=0)
    owner_id = await _owner_id()

    async with session_scope() as session:
        assert await commission_receivable_service.record(session, owner_id=owner_id, group_key=GROUP, amount_toman=70_000, note="تسویهٔ ناموفق")
        assert not await commission_receivable_service.record(session, owner_id=owner_id, group_key=GROUP, amount_toman=99_999), "همان گروه ⇒ یک ردیف"
        assert not await commission_receivable_service.record(session, owner_id=owner_id, group_key="zero", amount_toman=0), "مبلغِ صفر بدهی نیست"
        summary = await commission_receivable_service.summary(session)
    assert summary == {"open_count": 1, "open_toman": 70_000, "settled_count": 0}, summary

    # بدونِ اعتبار ⇒ دست نمی‌زند
    async with session_scope() as session:
        owner = (await session.execute(select(ShopOwner).where(ShopOwner.id == owner_id))).scalar_one()
        assert await commission_receivable_service.collect_for_owner(session, owner) == 0
    async with session_scope() as session:
        row = (await session.execute(select(CommissionReceivable))).scalar_one()
        assert row.status == "open" and row.amount_toman == 70_000

    # اعتبار هست ولی holdِ کمیسیونِ یکِ سفارشِ دیگر ⇒ قابل‌استفاده ۶۰ هزار است، نه ۸۰ هزار
    async with session_scope() as session:
        owner = (await session.execute(select(ShopOwner).where(ShopOwner.id == owner_id))).scalar_one()
        await wallet_service.add_charge(session, owner, 80_000, reason=WalletTransactionReason.TOPUP, reference="p21-test-charge")
        owner.commission_reserved_toman = 20_000
        await session.flush()
        assert wallet_service.usable_credit(owner) == 60_000, wallet_service.usable_credit(owner)
        assert await commission_receivable_service.collect_for_owner(session, owner) == 0, "بدهی از پولِ رزروشده نمی‌آید"
        await session.commit()

    # آزادشدنِ hold ⇒ وصولِ خودکار از بسته‌هایِ واقعیِ کیف‌پول (نه عددِ کش‌شده)
    async with session_scope() as session:
        owner = (await session.execute(select(ShopOwner).where(ShopOwner.id == owner_id))).scalar_one()
        owner.commission_reserved_toman = 0
        await session.flush()
        settled = await commission_receivable_service.collect_for_owner(session, owner)
        assert settled == 1, settled
        assert owner.wallet_balance_toman == 10_000, owner.wallet_balance_toman
        await session.commit()

    async with session_scope() as session:
        row = (await session.execute(select(CommissionReceivable))).scalar_one()
        assert row.status == "settled" and row.settled_at is not None
        ledger = await wallet_service.get_recent_transactions(session, owner_id, limit=30)
        summary = await commission_receivable_service.summary(session)
    assert summary == {"open_count": 0, "open_toman": 0, "settled_count": 1}, summary
    charged = [t for t in ledger if (t.reference or "").startswith(f"receivable:{row.id}")]
    assert len(charged) == 1 and charged[0].amount_toman == -70_000, [(t.reference, t.amount_toman) for t in ledger]
    assert charged[0].reason == WalletTransactionReason.COMMISSION

    # وصولِ دوباره ⇒ هیچ (نه کسرِ تکراری، نه ردیفِ دفتریِ تکراری)
    async with session_scope() as session:
        owner = (await session.execute(select(ShopOwner).where(ShopOwner.id == owner_id))).scalar_one()
        assert await commission_receivable_service.collect_for_owner(session, owner) == 0
    print("✅ test_receivable_lifecycle_records_and_collects PASSED")


# ============================================================================= ۴ — ریشهٔ بدهی
async def test_failed_settle_records_a_receivable() -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID, initial_balance_toman=10_000)
    owner_id = await _owner_id()

    async with session_scope() as session:
        customer = await customer_service.get_or_create_customer(session, shop_bot_id, 555009, "مشتریِ تست", None)
        order = OrderConsultation(
            shop_bot_id=shop_bot_id,
            customer_id=customer.id,
            type=OrderType.CONSULTATION,
            summary="مشاوره",
            status=OrderStatus.PAID,
            estimated_value_toman=1_000_000,
            commission_status="reserved",
            commission_toman=50_000,
            commission_percent="5",
        )
        session.add(order)
        # یکِ شارژِ کوچک با دفترِ سازگار، تا کسرِ واقعیِ کمیسیون «ناکافی بودن» را نشان دهد
        owner = (await session.execute(select(ShopOwner).where(ShopOwner.id == owner_id))).scalar_one()
        await wallet_service.deduct(session, owner, 9_000, WalletTransactionReason.CHAT_MESSAGE, reference="seed-drain")
        await session.commit()

    admin_settings = type("A", (), {"commission_enabled": True, "commission_percent": "5"})()
    async with session_scope() as session:
        owner = (await session.execute(select(ShopOwner).where(ShopOwner.id == owner_id))).scalar_one()
        owner.wallet_balance_toman = 1_000
        owner.commission_reserved_toman = 50_000
        await session.flush()
        rows = list((await session.execute(select(OrderConsultation))).scalars().all())
        result = await commission_service.settle(session, owner_id=owner_id, group_key=GROUP, rows=rows, admin_settings=admin_settings)
        assert result.changed is False and result.reason == "insufficient", result
        await session.commit()

    async with session_scope() as session:
        report = await commission_receivable_service.open_report(session)
        summary = await commission_receivable_service.summary(session)
    assert summary["open_count"] == 1, summary
    assert report[0]["amount_toman"] == summary["open_toman"] > 0, report
    assert report[0]["owner_label"], "گزارش باید فروشگاه را نام ببرد، نه فقط شناسهٔ عددی"
    print("✅ test_failed_settle_records_a_receivable PASSED")


# ============================================================================= ۵ — مسیرِ داغ
async def test_customer_upsert_keeps_previous_semantics() -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)

    async with session_scope() as session:
        created = await customer_service.get_or_create_customer(session, shop_bot_id, 555001, "سارا", "sara_u", "رضایی")
        assert created.id is not None and created.first_name == "سارا"
        first_seen = created.first_seen_at
        await session.commit()

    # همان مشتری، این‌بار بدونِ نام ⇒ اطلاعاتِ قبلی پاک نمی‌شود (قصدِ اصلیِ این تابع)
    async with session_scope() as session:
        again = await customer_service.get_or_create_customer(session, shop_bot_id, 555001, None, None)
        assert again.id == created.id
        assert again.first_name == "سارا" and again.username == "sara_u" and again.last_name == "رضایی"
        assert again.last_message_at >= first_seen
        await session.commit()

    # نامِ تازه ⇒ جایگزین
    async with session_scope() as session:
        updated = await customer_service.get_or_create_customer(session, shop_bot_id, 555001, "سارا‌یِ تازه", None)
        assert updated.first_name == "سارا‌یِ تازه" and updated.username == "sara_u", "usernameِ None نباید پاک کند"
        await session.commit()

    # پلتفرمِ دیگر با همان عددِ تلگرام ⇒ ردیفِ جدا (قاعدهٔ P19، که upsertِ تازه باید حفظش کند)
    async with session_scope() as session:
        bale = await customer_service.get_or_create_customer(
            session, shop_bot_id, 555001, "سارا روی بله", None, platform=platform_service.BALE
        )
        assert bale.id != created.id and bale.platform == platform_service.BALE
        tg = (await session.execute(select(Customer).where(Customer.id == created.id))).scalar_one()
        assert tg.platform == platform_service.TELEGRAM
        await session.commit()

    # مکالمه: دو ردیف به همان ترتیب، در یکِ گزاره
    async with session_scope() as session:
        before = int((await session.execute(select(func.count()).select_from(ConversationMessage))).scalar_one())
        await conversation_service.save_turn(session, created.id, "سلام", "سلام، در خدمتم")
        rows = list(
            (
                await session.execute(
                    select(ConversationMessage).where(ConversationMessage.customer_id == created.id).order_by(ConversationMessage.id)
                )
            )
            .scalars()
            .all()
        )
        assert int((await session.execute(select(func.count()).select_from(ConversationMessage))).scalar_one()) == before + 2
        assert [row.role for row in rows[-2:]] == ["user", "assistant"], [row.role for row in rows]
        await session.commit()
    print("✅ test_customer_upsert_keeps_previous_semantics PASSED")


async def main() -> None:
    test_voice_cost_is_never_cheaper_than_today()
    test_receipt_cost_follows_reported_tokens_only()
    await test_receivable_lifecycle_records_and_collects()
    await test_failed_settle_records_a_receivable()
    await test_customer_upsert_keeps_previous_semantics()


if __name__ == "__main__":
    asyncio.run(main())
