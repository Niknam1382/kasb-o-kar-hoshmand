"""
تست: سرویسِ کمپین (فازِ ۳ — سازنده‌ی کمپین، تخفیفِ مخصوصِ مشتری) — بدونِ ربات/دیسپچر،
مستقیم رویِ PostgreSQL واقعی.

پوشش:
۱. منطقِ خالص: نرمال‌سازیِ کد، محاسبه‌ی تخفیف، پخشِ تخفیف بینِ ردیف‌ها (property test:
   جمعِ سهم‌ها دقیقاً برابرِ تخفیف و هیچ ردیفی منفی نمی‌شه)، تاریخِ شمسی.
۲. ساخت + اعتبارسنجی + یکتاییِ کد (در سطحِ سرویس *و* قیدِ دیتابیس؛ NULLها تداخل ندارن).
۳. انتخابِ بهترین تخفیف، سقفِ کل/هر مشتری، آزادشدنِ سهمیه با ردِ سفارش/انقضا/لغو،
   پنجره‌ی زمانی، حداقلِ مبلغِ سبد، آمارِ مصرف.
۴. حذفِ امن (فقط کمپینِ بی‌استفاده) و ایزوله‌بودنِ مالکیت (get_owned).
۵. قفلِ FOR UPDATE: چک‌اوتِ هم‌زمان نمی‌تونه از سقفِ کل/سقفِ هر مشتری رد بشه.

اجرا: python3 tests_manual/test_campaigns.py
"""
from __future__ import annotations

import asyncio
import importlib
import datetime
import random
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from harness import reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.database.models import (  # noqa: E402
    Campaign,
    CampaignDiscountType,
    OrderConsultation,
    OrderStatus,
    OrderType,
)
from app.database.session import session_scope  # noqa: E402
from app.services import campaign_service, customer_service, order_service  # noqa: E402
from app.services.campaign_service import CampaignError, RejectReason  # noqa: E402
from app.utils import jalali  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402

# خودِ ماژول (نه نمونه‌ی rate_limiter): حالتِ محدودکننده توی متغیرِ سطحِ ماژوله
rate_limiter_module = importlib.import_module("app.services.rate_limiter")

OWNER_A_TG_ID = 999801
SHOP_A_BOT_TG_ID = 999802
OWNER_B_TG_ID = 999811
SHOP_B_BOT_TG_ID = 999812
CUSTOMER_TG_IDS = [999821, 999822, 999823, 999824, 999825]

PERCENT = CampaignDiscountType.PERCENT
FIXED = CampaignDiscountType.FIXED


def _utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


async def _seed_shop_with_customers(count: int = 3) -> tuple[int, list[int]]:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_A_TG_ID, SHOP_A_BOT_TG_ID)
    customer_ids: list[int] = []
    async with session_scope() as session:
        for index in range(count):
            customer = await customer_service.get_or_create_customer(
                session, shop_bot_id, CUSTOMER_TG_IDS[index], f"مشتری {index + 1}", None
            )
            customer_ids.append(customer.id)
    return shop_bot_id, customer_ids


async def _make_used_order(
    session,
    shop_bot_id: int,
    customer_id: int,
    campaign_id: int,
    group_id: str,
    *,
    status: OrderStatus = OrderStatus.PENDING,
    discount: int = 10_000,
    value: int = 90_000,
) -> OrderConsultation:
    """یه ردیفِ سفارشِ سبد که کمپین گرفته (مثلِ چیزی که چک‌اوتِ واقعی می‌سازه)."""
    order = await order_service.create_order(session, shop_bot_id, customer_id, OrderType.ORDER, "تست", value)
    order.campaign_id = campaign_id
    order.discount_toman = discount
    order.cart_checkout_group_id = group_id
    order.status = status
    await session.flush()
    return order


async def _new_campaign(session, shop_bot_id: int, **overrides) -> Campaign:
    args = dict(name="کمپین تست", discount_type=PERCENT, discount_value=10, duration_days=7)
    args.update(overrides)
    return await campaign_service.create_campaign(session, shop_bot_id, **args)


# =============================================================================
# ۱. منطقِ خالص
# =============================================================================
async def test_pure_logic_code_discount_distribution_and_jalali() -> None:
    n = campaign_service.normalize_code
    assert n("mehr10") == n("MEHR10") == n(" Mehr 10 ") == "MEHR10"
    assert n("مهر۱۴۰۵") == n("مهر١٤٠٥") == "مهر1405", "رقمِ فارسی/عربی باید به انگلیسی تبدیل بشه"
    assert n("يلدا") == "یلدا" and n("كد") == "کد", "ي/ك عربی باید به ی/ک فارسی تبدیل بشن"
    assert n("   ") is None and n(None) is None
    assert campaign_service.is_valid_code("OFF-10_X") and campaign_service.is_valid_code("یلدا1405")
    assert not campaign_service.is_valid_code("AB") and not campaign_service.is_valid_code("A" * 21)
    assert not campaign_service.is_valid_code("A B") and not campaign_service.is_valid_code("A$B")

    cd = campaign_service.compute_discount
    assert cd(PERCENT, 10, None, 250_000) == 25_000
    assert cd(PERCENT, 10, 20_000, 250_000) == 20_000, "سقفِ مبلغِ تخفیف"
    assert cd(PERCENT, 100, None, 5_000) == 5_000
    assert cd(FIXED, 400_000, None, 250_000) == 250_000, "تخفیفِ ثابت هیچ‌وقت از جمعِ سبد بیشتر نمی‌شه"
    assert cd(PERCENT, 10, None, 0) == 0

    # property test: جمعِ سهم‌ها دقیقاً برابرِ تخفیف، و هیچ سهمی منفی یا بیشتر از مبلغِ ردیف نیست
    rnd = random.Random(20261002)
    for _ in range(20_000):
        lines = [rnd.randint(1, 30) * rnd.choice([1, 1000, 5000]) for _ in range(rnd.randint(1, 7))]
        total = sum(lines)
        discount = rnd.randint(1, total)
        shares = campaign_service.distribute_discount(lines, discount)
        assert sum(shares) == discount, (lines, discount, shares)
        assert all(0 <= share <= line for share, line in zip(shares, lines)), (lines, discount, shares)
    # همون حالتی که روشِ «باقی‌مانده رو یکجا به یه ردیف بده» قیمتِ یه ردیف رو منفی می‌کرد
    assert campaign_service.distribute_discount([2, 2, 2, 2, 2], 9) == [2, 2, 2, 2, 1]

    assert jalali.gregorian_to_jalali(2026, 3, 21) == (1405, 1, 1)
    assert jalali.gregorian_to_jalali(2025, 3, 20) == (1403, 12, 30)
    assert jalali.gregorian_to_jalali(2026, 10, 2) == (1405, 7, 10)
    moment = datetime.datetime(2026, 10, 2, 14, 5, tzinfo=datetime.timezone.utc)
    assert jalali.format_jalali_datetime(moment) == "۱۰ مهر ۱۴۰۵، ساعت ۱۷:۳۵", "ساعتِ تهران = UTC+03:30"

    print("✅ test_pure_logic_code_discount_distribution_and_jalali PASSED")


# =============================================================================
# ۲. ساخت + اعتبارسنجی + یکتایی
# =============================================================================
async def test_create_campaign_validation_and_code_uniqueness() -> None:
    await reset_database()
    shop_a = await seed_usable_shop(OWNER_A_TG_ID, SHOP_A_BOT_TG_ID)
    shop_b = await seed_usable_shop(OWNER_B_TG_ID, SHOP_B_BOT_TG_ID)

    async with session_scope() as session:
        campaign = await _new_campaign(session, shop_a, code=" mehr ۱۰ ", discount_value=15, max_discount_toman=50_000)
        assert campaign.code == "MEHR10", "کد باید نرمال‌شده ذخیره بشه"
        assert campaign.is_active and campaign.per_customer_limit == 1, "پیش‌فرضِ هر مشتری = ۱ بار"
        assert campaign.ends_at - campaign.starts_at == datetime.timedelta(days=7)
        assert abs((campaign.starts_at - _utc_now()).total_seconds()) < 60, "کمپین همون لحظه‌ی ساخت شروع می‌شه"

        async def error_code(**overrides) -> str | None:
            try:
                await _new_campaign(session, shop_a, **overrides)
            except CampaignError as exc:
                return exc.code
            return None

        assert await error_code(code="MEHR10") == "code_taken"
        assert await error_code(code="mehr۱۰") == "code_taken", "کدِ تکراری با حروف/رقمِ متفاوت هم باید رد بشه"
        assert await error_code(code="ab") == "bad_code"
        assert await error_code(name="  ") == "bad_name"
        assert await error_code(discount_value=0) == "bad_value"
        assert await error_code(discount_value=101) == "bad_value"
        assert await error_code(duration_days=0) == "bad_duration"
        assert await error_code(total_usage_limit=0) == "bad_limit"
        assert await error_code(discount_type=FIXED, discount_value=20_000) == "fixed_needs_min_cart"
        assert await error_code(discount_type=FIXED, discount_value=20_000, min_cart_total_toman=20_000) == "fixed_needs_min_cart"
        fixed = await _new_campaign(session, shop_a, discount_type=FIXED, discount_value=20_000, min_cart_total_toman=20_001)
        assert fixed.min_cart_total_toman == 20_001 and fixed.code is None

        # کمپین‌هایِ خودکار (code=None) هرچندتا که بخوان می‌تونن باشن (NULL ها یکتایی رو نقض نمی‌کنن)
        await _new_campaign(session, shop_a, name="خودکار ۱")
        await _new_campaign(session, shop_a, name="خودکار ۲")

        # همون کد توی فروشگاهِ دیگه مجازه
        other = await _new_campaign(session, shop_b, code="MEHR10")
        assert other.code == "MEHR10" and other.shop_bot_id == shop_b

    # قیدِ دیتابیس (دفاعِ دوم): حتی اگه کسی سرویس رو دور بزنه، (فروشگاه، کد) یکتاست
    raised = False
    try:
        async with session_scope() as session:
            session.add(
                Campaign(
                    shop_bot_id=shop_a,
                    name="تکراری",
                    code="MEHR10",
                    discount_type=PERCENT,
                    discount_value=5,
                    starts_at=_utc_now(),
                    ends_at=_utc_now() + datetime.timedelta(days=1),
                )
            )
            await session.flush()
    except IntegrityError:
        raised = True
    assert raised, "قیدِ یکتاییِ (shop_bot_id, code) توی دیتابیس باید جلوی کدِ تکراری رو بگیره"

    print("✅ test_create_campaign_validation_and_code_uniqueness PASSED")


# =============================================================================
# ۳. انتخابِ بهترین تخفیف + محدودیت‌ها + آزادشدنِ سهمیه
# =============================================================================
async def test_best_offer_selection_and_code_problems() -> None:
    shop, (cust_a, cust_b, _cust_c) = await _seed_shop_with_customers(3)
    async with session_scope() as session:
        auto10 = (await _new_campaign(session, shop, name="خودکار ۱۰", discount_value=10)).id
        vip15 = (await _new_campaign(session, shop, name="کد ۱۵", discount_value=15, code="VIP15")).id
        vip10 = (await _new_campaign(session, shop, name="کد ۱۰", discount_value=10, code="TIE10")).id
        big = (await _new_campaign(session, shop, name="حداقل", discount_value=20, code="BIG", min_cart_total_toman=100_000)).id

    async with session_scope() as session:
        find = campaign_service.find_best_offer
        r = await find(session, shop, cust_a, 100_000)
        assert r.offer.campaign_id == auto10 and r.offer.discount_toman == 10_000 and r.offer.code is None
        assert r.offer.final_total_toman == 90_000

        r = await find(session, shop, cust_a, 100_000, code="VIP15")
        assert r.offer.campaign_id == vip15 and r.offer.discount_toman == 15_000 and not r.code_outranked

        r = await find(session, shop, cust_a, 100_000, code="TIE10")
        assert r.offer.campaign_id == vip10, "تساوی بینِ کد و خودکار → کد برنده‌ست"

        r = await find(session, shop, cust_a, 50_000, code="BIG")
        assert r.offer.campaign_id == auto10 and r.code_problem == RejectReason.MIN_CART and r.code_min_cart_toman == 100_000
        r = await find(session, shop, cust_a, 100_000, code="BIG")
        assert r.offer.campaign_id == big and r.code_problem is None, "حداقلِ سبد دقیقاً برابر → معتبره"

        r = await find(session, shop, cust_a, 100_000, code="NOPE")
        assert r.offer.campaign_id == auto10 and r.code_problem == RejectReason.NOT_FOUND, "کدِ ناموجود: خودکار همچنان اعمال می‌شه"

        # خودکارِ بهتر از کد → خودکار، با علامتِ outranked
        await _new_campaign(session, shop, name="خودکار ۳۰", discount_value=30)
        r = await find(session, shop, cust_a, 100_000, code="VIP15")
        assert r.offer.discount_toman == 30_000 and r.code_outranked and r.code_problem is None

    print("✅ test_best_offer_selection_and_code_problems PASSED")


async def test_limits_release_and_usage_stats() -> None:
    shop, (cust_a, cust_b, cust_c) = await _seed_shop_with_customers(3)
    async with session_scope() as session:
        auto = (await _new_campaign(session, shop, name="خودکار", discount_value=10)).id  # هر مشتری ۱ بار
        capped = (
            await _new_campaign(
                session, shop, name="ظرفیت‌دار", discount_value=20, code="CAP", total_usage_limit=2, per_customer_limit=None
            )
        ).id

    find = campaign_service.find_best_offer

    # --- سقفِ هر مشتری + آزادشدن/نشدن بر اساسِ وضعیتِ سفارش ---
    async with session_scope() as session:
        await _make_used_order(session, shop, cust_a, auto, "g1")
    cases = [
        (OrderStatus.REJECTED, True),
        (OrderStatus.EXPIRED, True),
        (OrderStatus.CANCELLED, True),
        (OrderStatus.PENDING, False),
        (OrderStatus.CONFIRMED, False),
        (OrderStatus.PROCESSING, False),
        (OrderStatus.SHIPPED, False),
        (OrderStatus.COMPLETED, False),
    ]
    for status, expect_released in cases:
        async with session_scope() as session:
            order = (await session.execute(select(OrderConsultation).where(OrderConsultation.cart_checkout_group_id == "g1"))).scalar_one()
            order.status = status
        async with session_scope() as session:
            result = await find(session, shop, cust_a, 100_000)
            released = result.offer is not None
            assert released == expect_released, f"وضعیتِ {status.value}: آزادشدنِ سهمیه باید {expect_released} باشه"
            other_customer = await find(session, shop, cust_b, 100_000)
            assert other_customer.offer is not None, "سقفِ هر مشتری فقط خودِ همون مشتری رو محدود می‌کنه"

    # --- یه گروه با دو ردیف: تا وقتی حداقل یه ردیفِ زنده داره، یه «استفاده» حساب می‌شه ---
    async with session_scope() as session:
        await _make_used_order(session, shop, cust_b, auto, "g2", status=OrderStatus.REJECTED)
        await _make_used_order(session, shop, cust_b, auto, "g2", status=OrderStatus.PENDING)
    async with session_scope() as session:
        assert await campaign_service.count_uses(session, auto, cust_b) == 1, "گروهِ نیمه‌زنده = ۱ استفاده (نه ۲، نه ۰)"
        assert (await find(session, shop, cust_b, 100_000)).offer is None
    async with session_scope() as session:
        rows = (await session.execute(select(OrderConsultation).where(OrderConsultation.cart_checkout_group_id == "g2"))).scalars().all()
        for row in rows:
            row.status = OrderStatus.REJECTED
    async with session_scope() as session:
        assert await campaign_service.count_uses(session, auto, cust_b) == 0, "وقتی همه‌ی ردیف‌ها آزاد شدن، استفاده‌ای باقی نمی‌مونه"
        assert (await find(session, shop, cust_b, 100_000)).offer is not None

    # --- سقفِ کلِ استفاده (۲ بار) ---
    async with session_scope() as session:
        await _make_used_order(session, shop, cust_a, capped, "c1", discount=20_000, value=80_000)
        await _make_used_order(session, shop, cust_b, capped, "c2", discount=20_000, value=80_000)
    async with session_scope() as session:
        result = await find(session, shop, cust_c, 100_000, code="CAP")
        assert result.code_problem == RejectReason.TOTAL_LIMIT
        # کدِ CAP پر شده؛ ولی کمپینِ خودکار هنوز برایِ این مشتری آزاده، پس همون اعمال می‌شه (نه CAP)
        assert result.offer is not None and result.offer.campaign_id == auto
        uses, discount_total = await campaign_service.usage_stats(session, capped)
        assert uses == 2 and discount_total == 40_000
    async with session_scope() as session:  # یکی رد می‌شه → یه ظرفیت آزاد می‌شه و جمعِ تخفیف کم می‌شه
        order = (await session.execute(select(OrderConsultation).where(OrderConsultation.cart_checkout_group_id == "c2"))).scalar_one()
        order.status = OrderStatus.REJECTED
    async with session_scope() as session:
        result = await find(session, shop, cust_c, 100_000, code="CAP")
        assert result.offer is not None and result.offer.campaign_id == capped
        uses, discount_total = await campaign_service.usage_stats(session, capped)
        assert uses == 1 and discount_total == 20_000, "ردشده‌ها توی آمارِ مصرف و جمعِ تخفیف حساب نمی‌شن"

    print("✅ test_limits_release_and_usage_stats PASSED")


async def test_time_window_and_pause() -> None:
    shop, (cust_a, _b, _c) = await _seed_shop_with_customers(3)
    now = _utc_now()
    async with session_scope() as session:
        await _new_campaign(session, shop, name="تمام‌شده", code="OLD", now=now - datetime.timedelta(days=10), duration_days=3)
        paused = await _new_campaign(session, shop, name="متوقف", code="PAUSED")
        await campaign_service.set_active(session, paused, False)
        future = await _new_campaign(session, shop, name="آینده", code="FUTURE")
        future.starts_at = now + datetime.timedelta(days=1)
        future.ends_at = now + datetime.timedelta(days=3)
        auto_old = await _new_campaign(session, shop, name="خودکارِ تمام‌شده", now=now - datetime.timedelta(days=10), duration_days=3)

    async with session_scope() as session:
        find = campaign_service.find_best_offer
        assert (await find(session, shop, cust_a, 100_000, code="OLD")).code_problem == RejectReason.ENDED
        assert (await find(session, shop, cust_a, 100_000, code="PAUSED")).code_problem == RejectReason.INACTIVE
        assert (await find(session, shop, cust_a, 100_000, code="FUTURE")).code_problem == RejectReason.NOT_STARTED
        silent = await find(session, shop, cust_a, 100_000)
        assert silent.offer is None and silent.code_problem is None, "خودکارِ تمام‌شده بی‌صدا نادیده گرفته می‌شه"
        assert await campaign_service.has_open_code_campaign(session, shop) is False, "OLD/PAUSED/FUTURE همه بسته‌ن"

        # مرزِ زمانی: ends_at خودش دیگه معتبر نیست؛ starts_at خودش معتبره
        assert campaign_service.check_availability(auto_old, auto_old.ends_at) == RejectReason.ENDED
        assert campaign_service.check_availability(auto_old, auto_old.starts_at) is None

    async with session_scope() as session:
        live = await _new_campaign(session, shop, name="زنده", code="LIVE")
        assert campaign_service.campaign_status(live, _utc_now()) == "active"
        assert await campaign_service.has_open_code_campaign(session, shop) is True

    print("✅ test_time_window_and_pause PASSED")


# =============================================================================
# ۴. حذفِ امن + مالکیت
# =============================================================================
async def test_delete_only_when_unused_and_ownership_is_enforced() -> None:
    shop_a, (cust_a, _b, _c) = await _seed_shop_with_customers(3)
    shop_b = await seed_usable_shop(OWNER_B_TG_ID, SHOP_B_BOT_TG_ID)

    async with session_scope() as session:
        unused = (await _new_campaign(session, shop_a, name="بی‌استفاده")).id
        used = (await _new_campaign(session, shop_a, name="استفاده‌شده", code="USED")).id
        await _make_used_order(session, shop_a, cust_a, used, "u1", status=OrderStatus.REJECTED)  # حتی ردشده هم «سابقه» حساب می‌شه

    async with session_scope() as session:
        assert await campaign_service.get_owned(session, unused, shop_b) is None, "فروشگاهِ دیگه نباید کمپینِ این فروشگاه رو ببینه"
        assert await campaign_service.get_owned(session, unused, shop_a) is not None
        assert [c.id for c in await campaign_service.list_for_shop(session, shop_b)] == []
        assert {c.id for c in await campaign_service.list_for_shop(session, shop_a)} == {unused, used}

    async with session_scope() as session:
        used_campaign = await campaign_service.get_owned(session, used, shop_a)
        assert await campaign_service.delete_if_unused(session, used_campaign) is False, "کمپینِ استفاده‌شده نباید حذف بشه"
    async with session_scope() as session:
        assert await session.get(Campaign, used) is not None

        unused_campaign = await campaign_service.get_owned(session, unused, shop_a)
        assert await campaign_service.delete_if_unused(session, unused_campaign) is True
    async with session_scope() as session:
        assert await session.get(Campaign, unused) is None

    print("✅ test_delete_only_when_unused_and_ownership_is_enforced PASSED")


# =============================================================================
# ۵. قفلِ FOR UPDATE — چک‌اوتِ هم‌زمان
# =============================================================================
async def _claim_slot(shop_bot_id: int, customer_id: int, group_id: str, code: str | None, outcomes: list[tuple[str, int]]) -> None:
    """شبیه‌سازیِ «ثبتِ نهایی»: اعتبارسنجیِ قفل‌دار → (کمی صبر، مثلِ بقیه‌ی هندلر) → ساختِ سفارش."""
    async with session_scope() as session:
        quote = await campaign_service.find_best_offer(session, shop_bot_id, customer_id, 100_000, code=code, lock=True)
        if quote.offer is None:
            outcomes.append(("lost", customer_id))
            return
        # قفل رو نگه می‌داریم تا چک‌اوتِ دیگه‌ای که هم‌زمان رسیده مجبور بشه منتظر بمونه؛ بدونِ قفل،
        # هر دو شمارشِ ۰ رو می‌بینن و هر دو برنده می‌شن (و این تست fail می‌شه).
        await asyncio.sleep(0.4)
        await _make_used_order(
            session, shop_bot_id, customer_id, quote.offer.campaign_id, group_id, discount=quote.offer.discount_toman
        )
        outcomes.append(("won", customer_id))


async def test_concurrent_checkouts_cannot_exceed_total_limit_with_code() -> None:
    shop, customer_ids = await _seed_shop_with_customers(4)
    async with session_scope() as session:
        campaign_id = (await _new_campaign(session, shop, code="LAST", total_usage_limit=1, per_customer_limit=None)).id

    outcomes: list[tuple[str, int]] = []
    await asyncio.gather(*[_claim_slot(shop, cid, f"race-{cid}", "LAST", outcomes) for cid in customer_ids])
    wins = [o for o in outcomes if o[0] == "won"]
    assert len(outcomes) == 4 and len(wins) == 1, f"با ظرفیتِ ۱، دقیقاً یک نفر باید برنده بشه؛ نتیجه: {outcomes}"
    async with session_scope() as session:
        assert await campaign_service.count_uses(session, campaign_id) == 1

    print("✅ test_concurrent_checkouts_cannot_exceed_total_limit_with_code PASSED")


async def test_concurrent_checkouts_cannot_exceed_total_limit_with_auto_campaign() -> None:
    shop, customer_ids = await _seed_shop_with_customers(4)
    async with session_scope() as session:
        campaign_id = (await _new_campaign(session, shop, name="خودکارِ ظرفیت‌دار", total_usage_limit=2, per_customer_limit=None)).id

    outcomes: list[tuple[str, int]] = []
    await asyncio.gather(*[_claim_slot(shop, cid, f"auto-race-{cid}", None, outcomes) for cid in customer_ids])
    wins = [o for o in outcomes if o[0] == "won"]
    assert len(wins) == 2, f"با ظرفیتِ ۲، دقیقاً دو نفر باید برنده بشن؛ نتیجه: {outcomes}"
    async with session_scope() as session:
        assert await campaign_service.count_uses(session, campaign_id) == 2

    print("✅ test_concurrent_checkouts_cannot_exceed_total_limit_with_auto_campaign PASSED")


async def test_concurrent_checkouts_cannot_exceed_per_customer_limit() -> None:
    shop, (cust_a, _b, _c) = await _seed_shop_with_customers(3)
    async with session_scope() as session:
        campaign_id = (await _new_campaign(session, shop, code="ONCE", per_customer_limit=1)).id

    outcomes: list[tuple[str, int]] = []
    # یه مشتری، دو چک‌اوتِ هم‌زمان (مثلاً از دو دستگاه): فقط یکی تخفیف می‌گیره
    await asyncio.gather(
        _claim_slot(shop, cust_a, "dev-1", "ONCE", outcomes),
        _claim_slot(shop, cust_a, "dev-2", "ONCE", outcomes),
    )
    assert sum(1 for o in outcomes if o[0] == "won") == 1, f"سقفِ هر مشتری (۱) نباید با چک‌اوتِ هم‌زمان دور زده بشه؛ نتیجه: {outcomes}"
    async with session_scope() as session:
        assert await campaign_service.count_uses(session, campaign_id, cust_a) == 1

    print("✅ test_concurrent_checkouts_cannot_exceed_per_customer_limit PASSED")


async def test_code_attempt_rate_limit() -> None:
    rate_limiter_module._windows.clear()  # حالتِ محدودکننده توی متغیرِ سطحِ ماژوله، نه روی نمونه
    results = [campaign_service.register_code_attempt(1, 424242) for _ in range(12)]
    assert results[: campaign_service.CODE_ATTEMPTS_MAX] == [True] * campaign_service.CODE_ATTEMPTS_MAX
    assert results[campaign_service.CODE_ATTEMPTS_MAX :] == [False, False], "بعد از سقفِ تلاش، امتحانِ کد باید بسته بشه"
    assert campaign_service.register_code_attempt(1, 424243) is True, "مشتریِ دیگه جدا حساب می‌شه"
    assert campaign_service.register_code_attempt(2, 424242) is True, "فروشگاهِ دیگه جدا حساب می‌شه"
    rate_limiter_module._windows.clear()

    print("✅ test_code_attempt_rate_limit PASSED")


async def main() -> None:
    await test_pure_logic_code_discount_distribution_and_jalali()
    await test_create_campaign_validation_and_code_uniqueness()
    await test_best_offer_selection_and_code_problems()
    await test_limits_release_and_usage_stats()
    await test_time_window_and_pause()
    await test_delete_only_when_unused_and_ownership_is_enforced()
    await test_concurrent_checkouts_cannot_exceed_total_limit_with_code()
    await test_concurrent_checkouts_cannot_exceed_total_limit_with_auto_campaign()
    await test_concurrent_checkouts_cannot_exceed_per_customer_limit()
    await test_code_attempt_rate_limit()


if __name__ == "__main__":
    asyncio.run(main())
