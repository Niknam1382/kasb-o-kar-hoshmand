"""پ۱۱۸ · سقفِ حافظهٔ ساختارهایِ سراسری + شمارشِ اتمیکِ کدِ تخفیف + ماسکِ رازِ `.env`.

یافته‌هایِ ۵ و ۱۲ِ بازرسیِ ۱۴۰۵-۰۸-۱۴ (فقط بخشِ بی‌ریسکِ پولی):
۱. `rate_limiter._windows` بی‌سقف بود (یکِ deque به‌ازایِ هر مشتری) ⇒ حالا `MAX_TRACKED_KEYS`.
۲. `admin_alert_service._events/_details/_last_alert` با کلیدِ «نوع + چکیدهٔ پیام» بی‌سقف رشد
   می‌کردند ⇒ حالا `_prune_keys()` با `MAX_TRACKED_KEYS`.
۳. `discount_service.record_usage` با `used_count += 1` رویِ ORM ⇒ دو پرداختِ هم‌زمان یکِ شمارش
   می‌ساختند و سقفِ `max_uses` رد می‌شد. حالا یکِ `UPDATE … WHERE (max_uses IS NULL OR used_count < max_uses)`.
۴. `observability.scrub` فقط *شکل‌های* شناخته‌شده را می‌ماسک کرد؛ حالا خودِ مقدارِ
   `ENCRYPTION_KEY`/`MAIN_BOT_TOKEN`/`WEB_PANEL_SECRET`/`METRICS_TOKEN`/`BALE_BOT_TOKEN` هم ماسک می‌شود.

قیدِ صادقانه: سقفِ حجمِ دانلودِ ویس (MAX_VOICE_BYTES در `customer.py::customer_voice`) پیاده شد ولی
در این فایل **تست نشده** (NOT RUN) — هندلرِ ویس برایِ صدا زده‌شدنِ مستقیم به Botِ توکن‌مت تطبیق‌داده‌شده
نیاز دارد؛ در `docs/changelog-p118.md` هم همین قید آمده است.

اجرا: python3 tests_manual/run_one.py test_p118_resource_bounds.py
"""
from __future__ import annotations

import asyncio
import datetime as dt
import sys
from decimal import Decimal

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from sqlalchemy import select  # noqa: E402

from app import observability  # noqa: E402
from app.config import settings  # noqa: E402
from app.database.models import DiscountCode, DiscountType  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import admin_alert_service, discount_service  # noqa: E402
from app.services.rate_limiter import InMemoryRateLimiter  # noqa: E402
from harness import reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

FAKE_SECRET = "unit-test-encryption-key-1234567890"
OWNER_TG = 11_800_001
SHOP_TG = 11_800_002


async def test_rate_limiter_windows_are_bounded() -> None:
    from app.services import rate_limiter as rl_module  # خودِ ماژود، نه نمونهٔ rate_limiter

    saved_cap = rl_module.MAX_TRACKED_KEYS
    try:
        rl_module.MAX_TRACKED_KEYS = 40
        limiter = InMemoryRateLimiter()
        for index in range(500):
            limiter.check_and_record(shop_bot_id=index % 7, customer_telegram_id=index, max_messages=3, window_seconds=60)
        assert len(rl_module._windows) <= 60, len(rl_module._windows)
        assert limiter.check_and_record(shop_bot_id=1, customer_telegram_id=999, max_messages=3, window_seconds=60) is True
    finally:
        rl_module.MAX_TRACKED_KEYS = saved_cap
        rl_module._windows.clear()
    print(f"✅ test_rate_limiter_windows_are_bounded PASSED (سقفِ {saved_cap} → تستِ ۴۰)")


async def test_admin_alert_buckets_are_bounded() -> None:
    saved_cap = admin_alert_service.MAX_TRACKED_KEYS
    try:
        admin_alert_service.MAX_TRACKED_KEYS = 25
        admin_alert_service.reset()
        for index in range(400):
            admin_alert_service.record_event(admin_alert_service.KIND_ERROR, f"خطایِ تستِ شمارهٔ {index} در ماژولِ X")
        assert len(admin_alert_service._events) <= 40, len(admin_alert_service._events)
        assert len(admin_alert_service._details) <= 40, len(admin_alert_service._details)
        assert len(admin_alert_service._last_alert) <= 40, len(admin_alert_service._last_alert)
    finally:
        admin_alert_service.MAX_TRACKED_KEYS = saved_cap
        admin_alert_service.reset()
    print(f"✅ test_admin_alert_buckets_are_bounded PASSED (سطل‌ها: {len(admin_alert_service._events)})")


async def test_discount_usage_increment_is_atomic_and_capped() -> None:
    await reset_database()
    from app.database.models import Payment, PaymentMethod, PaymentPurpose
    from app.services import shop_owner_service

    await seed_usable_shop(OWNER_TG, SHOP_TG)
    code = f"P118CAP{dt.datetime.now().strftime('%H%M%S')}"
    async with session_scope() as session:
        discount = DiscountCode(
            code=code, type=DiscountType.FIXED, value=Decimal("1000"), max_uses=2, used_count=0, is_active=True
        )
        session.add(discount)
        await session.flush()
        discount_id = int(discount.id)
        await session.commit()

    async def _use(tag: int) -> None:
        """مصرفِ کد توسطِ یکِ صاحبِ حسابِ *متفاوت* (قیدِ `uq_discount_code_usages` یکِ مصرف به‌ازایِ
        هر (کد، صاحبِ حساب) را می‌گذارد؛ مسابقهٔ واقعی رویِ `max_uses` بینِ صاحب‌حساب‌هایِ گوناگون است)."""
        async with session_scope() as session:
            buyer = await shop_owner_service.get_or_create_shop_owner(session, 11_800_100 + tag)
            payment = Payment(
                shop_owner_id=int(buyer.id),
                purpose=PaymentPurpose.SUBSCRIPTION,
                base_amount=50_000,
                final_amount=49_000,
                method=PaymentMethod.ZARINPAL,
                discount_code_id=discount_id,
            )
            session.add(payment)
            await session.flush()
            payment_id = int(payment.id)
            await discount_service.record_usage(session, discount_id, int(buyer.id), payment_id)
            await session.commit()

    await asyncio.gather(*[_use(i) for i in range(6)])

    async with session_scope() as session:
        row = (await session.execute(select(DiscountCode).where(DiscountCode.id == discount_id))).scalar_one()
        assert int(row.used_count) == 2, f"سقفِ max_uses رد شد: {row.used_count}"

    async with session_scope() as session:
        row = (await session.execute(select(DiscountCode).where(DiscountCode.id == discount_id))).scalar_one()
        row.max_uses = None
        await session.commit()
    await asyncio.gather(*[_use(100 + i) for i in range(5)])
    async with session_scope() as session:
        row = (await session.execute(select(DiscountCode).where(DiscountCode.id == discount_id))).scalar_one()
        assert int(row.used_count) == 7, row.used_count
    print("✅ test_discount_usage_increment_is_atomic_and_capped PASSED")


async def test_scrub_masks_literal_env_secrets() -> None:
    saved = settings.encryption_key
    try:
        settings.encryption_key = FAKE_SECRET
        line = f"کلیدِ رمزنگاری: {FAKE_SECRET} در فیلدِ custom_data"
        cleaned = observability.scrub(line)
        assert FAKE_SECRET not in cleaned, "مقدارِ راز در لاگ ماند"
        assert "کلیدِ رمزنگاری" in cleaned, cleaned
        assert "●●●●" in cleaned, cleaned
    finally:
        settings.encryption_key = saved
    print("✅ test_scrub_masks_literal_env_secrets PASSED")


async def main() -> None:
    await test_rate_limiter_windows_are_bounded()
    await test_admin_alert_buckets_are_bounded()
    await test_discount_usage_increment_is_atomic_and_capped()
    await test_scrub_masks_literal_env_secrets()
    await asyncio.sleep(0)


if __name__ == "__main__":
    asyncio.run(main())
