"""پ۱۱۶ · سه یافتهٔ بازرسیِ ۱۴۰۵-۰۸-۱۴ که به پولِ واقعی دست می‌زدند.

پوششِ همین فایل:
۱. یافتهٔ ۱۱ — `wallet_service.deduct` با `idempotency_keyِ` یکسان **یک بار** کم می‌کند؛ بازپخشِ
   یکِ batchِ نیمه‌کارهٔ polling (یا هر دوباره‌کوشی) دیگر موجودی را دو بار نمی‌خورد، و با کلیدِ
   *متفاوت* دوباره کم می‌کند (کلیدِ اشتباه نباید جلویِ هزینهٔ واقعی را بگیرد).
۲. یافتهٔ ۱۱ در مسیرِ مشتری — `chat_billing_service.deduct_and_notify` کلید را به `deduct`
   می‌رساند (قبلاً هیچ‌جا کلید نمی‌رسید) و فقط یکِ ردیفِ دفتری با آن کلید نوشته می‌شود.
۳. یافتهٔ ۲ — پاداشِ معرف: دو فراخوانیِ پیاپی برایِ یکِ حسابِ معرفی‌شده فقط **یکِ** شارژ می‌سازد
   (قفلِ سطرِ `Referral` + `reference=referral:{id}` ⇒ کلیدِ ایدبمپوتنسیِ پایدار).
۴. یافتهٔ ۹ — رزروِ کمیسیون با سوییچِ خاموش: نرخِ همان لحظه (صفر) رویِ ردیف‌ها مُهر می‌شود، پس اگر
   ادمین بعداً نرخ را بالا ببرد، تسویهٔ همان سفارشِ باز گران‌تر نمی‌شود.
۵. یافتهٔ ۹ — رزروِ ناموفق به‌خاطرِ موجودیِ کم: نرخ مُهر می‌شود تا تسویه با نرخِ سفارش حساب کند،
   نه با نرخِ زندهٔ ادمین.

اجرا: python3 tests_manual/run_one.py test_p116_money_idempotency.py
"""
from __future__ import annotations

import asyncio
import datetime as dt
import sys
from decimal import Decimal

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.database.models import (  # noqa: E402
    OrderConsultation,
    OrderStatus,
    Referral,
    ShopOwner,
    WalletCharge,
    WalletTransactionReason,
)
from app.database.session import session_scope  # noqa: E402
from app.services import (  # noqa: E402
    chat_billing_service,
    commission_service,
    order_transition_service,
    referral_service,
    shop_owner_service,
    wallet_service,
)
from app.services.admin_settings_service import get_admin_settings  # noqa: E402
from harness import FakeSession, reset_database  # noqa: E402
from phase4_helpers import add_customer, add_order, owner_balance, wallet_transactions  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

OWNER_TG = 11_600_001
SHOP_TG = 11_600_002
CUSTOMER_TG = 11_600_003
REFERRED_TG = 11_600_009
GROUP = "p116group00000000000000000000ab"


async def _owner_id() -> int:
    async with session_scope() as session:
        owner = await shop_owner_service.get_by_telegram_id(session, OWNER_TG)
        return int(owner.id)


async def _set_commission(*, enabled: bool, percent: str) -> None:
    async with session_scope() as session:
        admin = await get_admin_settings(session)
        admin.commission_enabled = enabled
        admin.commission_percent = Decimal(percent)
        await session.commit()


async def _seed_shop(*, balance_toman: int = 1_000_000) -> int:
    shop_bot_id = await seed_usable_shop(OWNER_TG, SHOP_TG, initial_balance_toman=balance_toman)
    customer_id = await add_customer(shop_bot_id, CUSTOMER_TG, first_name="خریدار")
    await add_order(
        shop_bot_id,
        customer_id,
        status=OrderStatus.AWAITING_PAYMENT,
        value=200_000,
        group_id=GROUP,
        summary="کیف",
    )
    return shop_bot_id


async def _group_rows():
    async with session_scope() as session:
        return list(
            (
                await session.execute(
                    select(OrderConsultation).where(OrderConsultation.cart_checkout_group_id == GROUP)
                )
            ).scalars().all()
        )


async def _deduct(amount: int, key: str) -> bool:
    async with session_scope() as session:
        owner = await session.get(ShopOwner, await _owner_id())
        done = await wallet_service.deduct(
            session, owner, amount, WalletTransactionReason.CHAT_MESSAGE, idempotency_key=key
        )
        await session.commit()
    return done


async def test_deduct_is_idempotent_per_key() -> None:
    key = "ai:chat:1:2:3"
    start = await owner_balance(OWNER_TG)
    assert await _deduct(1000, key) is True
    middle = await owner_balance(OWNER_TG)
    assert await _deduct(1000, key) is True, "فراخوانیِ تکراری باید موفق گزارش شود"
    assert await owner_balance(OWNER_TG) == middle, "کلیدِ تکراری دوباره کم کرد (یافتهٔ ۱۱)"

    assert await _deduct(1000, "ai:chat:1:2:4") is True
    assert await owner_balance(OWNER_TG) == middle - 1000, "کلیدِ تازه باید هزینه‌اش را کم کند"
    assert start - middle == 1000, (start, middle)
    print("✅ test_deduct_is_idempotent_per_key PASSED")


async def test_chat_billing_helper_passes_the_key() -> None:
    key = "ai:voice:1:2:77"
    before = await owner_balance(OWNER_TG)
    async with session_scope() as session:
        admin = await get_admin_settings(session)
        owner = await session.get(ShopOwner, await _owner_id())
        bot = Bot(token="123456:" + "A" * 32, session=FakeSession())
        await chat_billing_service.deduct_and_notify(
            session, owner, admin, 500, WalletTransactionReason.VOICE_TRANSCRIPTION, bot, idempotency_key=key
        )
        await chat_billing_service.deduct_and_notify(
            session, owner, admin, 500, WalletTransactionReason.VOICE_TRANSCRIPTION, bot, idempotency_key=key
        )
        await session.commit()
    after = await owner_balance(OWNER_TG)
    assert after == before - 500, (before, after)
    rows = await wallet_transactions(WalletTransactionReason.VOICE_TRANSCRIPTION)
    stamped = [r for r in rows if (r.idempotency_key or "").startswith(key)]
    assert len(stamped) <= 1, f"دو ردیفِ دفتری با یکِ کلید: {len(stamped)}"
    print("✅ test_chat_billing_helper_passes_the_key PASSED")


async def test_multi_lot_spend_keeps_one_plain_key() -> None:
    """قراردادِ کلیدِ مصرفِ چندبسته‌ای (چون تستِ پ۵ دیگر شکلِ «همه با :lot:» را پین نمی‌کند).

    یکِ مصرفِ بزرگ بینِ چند بسته پخش می‌شود و به‌ازایِ هر بسته یکِ ردیفِ دفتری ساخته می‌شود.
    بستهٔ *نخست* کلیدِ خام را نگه می‌دارد و بقیه پسوندِ `:lot:{charge_id}` می‌گیرند، چون
    پیش‌بازبینیِ ایدبمپوتنسی در `wallet_service.deduct` با `=` رویِ ایندکسِ ستون انجام می‌شود
    (پیش‌بازبینیِ LIKE نمی‌تواند از ایندکسِ btree این ستون استفاده کند).
    """
    owner_id = await _owner_id()
    async with session_scope() as session:
        owner = await session.get(ShopOwner, owner_id)
        await wallet_service.add_charge(session, owner, 10_000, reference="lot:a")
        await wallet_service.add_charge(session, owner, 10_000, reference="lot:b")
        await session.commit()

    # مصرف را «اولینِ سرِ بسته + ۵٬۰۰۰» می‌گیریم تا پخش‌شدن بینِ دو بسته قطعی باشد
    # (بسته‌ها به ترتیبِ انقضا خرج می‌شوند و بستهٔ سیدِ فروشگاه از همه زودتر می‌سوزد).
    async with session_scope() as session:
        earliest = (
            await session.execute(
                select(WalletCharge)
                .where(
                    WalletCharge.shop_owner_id == owner_id,
                    WalletCharge.is_expired.is_(False),
                    WalletCharge.remaining_toman > 0,
                )
                .order_by(WalletCharge.expires_at.asc())
                .limit(1)
            )
        ).scalar_one()
        spend = int(earliest.remaining_toman) + 5_000

    async with session_scope() as session:
        owner = await session.get(ShopOwner, owner_id)
        assert await wallet_service.deduct(
            session, owner, spend, WalletTransactionReason.CHAT_MESSAGE, idempotency_key="spend:multi"
        )
        await session.commit()

    rows = [
        r
        for r in await wallet_transactions(WalletTransactionReason.CHAT_MESSAGE)
        if str(r.idempotency_key or "").startswith("spend:multi")
    ]
    keys = sorted(str(r.idempotency_key) for r in rows)
    assert len(keys) >= 2, f"مصرف باید بینِ چند بسته پخش می‌شد: {keys}"
    assert "spend:multi" in keys, f"کلیدِ خامِ بستهٔ نخست لازم است: {keys}"
    assert any(k.startswith("spend:multi:lot:") for k in keys), keys

    before = len(await wallet_transactions(WalletTransactionReason.CHAT_MESSAGE))
    assert await _deduct(5_000, "spend:multi") is True, "بازپخش باید «انجام‌شده» برگردد نه شکست"
    assert len(await wallet_transactions(WalletTransactionReason.CHAT_MESSAGE)) == before, "بازپخش ردیفِ تازه ساخت"
    print("✅ test_multi_lot_spend_keeps_one_plain_key PASSED")


async def test_referral_reward_is_charged_once() -> None:
    async with session_scope() as session:
        admin = await get_admin_settings(session)
        admin.referral_reward_value = Decimal("10")
        referrer = await shop_owner_service.get_by_telegram_id(session, OWNER_TG)
        referred = await shop_owner_service.get_or_create_shop_owner(session, REFERRED_TG)
        session.add(Referral(referrer_id=int(referrer.id), referred_id=int(referred.id), reward_status="pending"))
        referred_id = int(referred.id)
        await session.commit()

    async with session_scope() as session:
        first = await referral_service.process_referral_reward(session, referred_id, 100_000)
        await session.commit()
    async with session_scope() as session:
        second = await referral_service.process_referral_reward(session, referred_id, 100_000)
        await session.commit()

    assert first is not None, "پاداشِ نخست ثبت نشد (referral_reward_value را ببین)"
    assert second is None, "پاداشِ دوم هم داده شد ⇒ رقابتِ یافتهٔ ۲ باز است"
    charges = await wallet_transactions(WalletTransactionReason.REFERRAL_REWARD)
    assert len(charges) == 1, [c.idempotency_key for c in charges]
    print("✅ test_referral_reward_is_charged_once PASSED")


async def test_disabled_rate_is_stamped_and_honoured() -> None:
    await _set_commission(enabled=False, percent="0.00")
    async with session_scope() as session:
        fresh = list(
            (
                await session.execute(
                    select(OrderConsultation).where(OrderConsultation.cart_checkout_group_id == GROUP)
                )
            ).scalars().all()
        )
        await order_transition_service.apply_commission(session, fresh, "awaiting_payment")
        await session.commit()

    stamped = await _group_rows()
    assert all(row.commission_percent is not None for row in stamped), [r.commission_percent for r in stamped]
    assert Decimal(str(stamped[0].commission_percent)) == Decimal("0"), stamped[0].commission_percent

    await _set_commission(enabled=True, percent="5.00")
    async with session_scope() as session:
        admin = await get_admin_settings(session)
        fresh = list(
            (
                await session.execute(
                    select(OrderConsultation).where(OrderConsultation.cart_checkout_group_id == GROUP)
                )
            ).scalars().all()
        )
        result = await commission_service.settle(
            session,
            owner_id=await _owner_id(),
            group_key=GROUP,
            rows=fresh,
            admin_settings=admin,
            now=dt.datetime.now(dt.timezone.utc),
        )
        await session.commit()
    assert result.amount_toman == 0, f"نرخِ تازه رویِ سفارشِ باز اعمال شد: {result}"
    print("✅ test_disabled_rate_is_stamped_and_honoured PASSED")


async def test_insufficient_reserve_still_stamps_rate() -> None:
    await reset_database()
    await _set_commission(enabled=True, percent="7.00")
    await _seed_shop(balance_toman=0)
    async with session_scope() as session:
        admin = await get_admin_settings(session)
        fresh = list(
            (
                await session.execute(
                    select(OrderConsultation).where(OrderConsultation.cart_checkout_group_id == GROUP)
                )
            ).scalars().all()
        )
        result = await commission_service.reserve(
            session, owner_id=await _owner_id(), group_key=GROUP, rows=fresh, admin_settings=admin
        )
        await session.commit()
    assert result.changed is False and result.reason == "insufficient", result
    stamped = await _group_rows()
    assert all(row.commission_percent is not None for row in stamped), [r.commission_percent for r in stamped]
    assert Decimal(str(stamped[0].commission_percent)) == Decimal("7.00"), stamped[0].commission_percent
    print("✅ test_insufficient_reserve_still_stamps_rate PASSED")


async def main() -> None:
    await reset_database()
    await _seed_shop()
    await test_deduct_is_idempotent_per_key()
    await test_multi_lot_spend_keeps_one_plain_key()
    await test_chat_billing_helper_passes_the_key()
    await test_referral_reward_is_charged_once()
    await test_disabled_rate_is_stamped_and_honoured()
    await test_insufficient_reserve_still_stamps_rate()
    await asyncio.sleep(0)


if __name__ == "__main__":
    asyncio.run(main())
