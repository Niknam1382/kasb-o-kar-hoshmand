"""
تست: P39 · باگِ ۴ — کیف‌پول انقضایِ *هر شارژ* را جدا می‌گوید (مصرفِ FIFO)

سناریویِ واقعیِ مالکِ محصول: یکم ۵۰۰٬۰۰۰ تومان شارژ، بیستم ۴۰۰٬۰۰۰ تومان شارژ، بیست‌وپنجم
مصرف. متنِ قدیمی فقط می‌گفت «تا ۳۰ روزِ دیگر منقضی می‌شود» — یعنی هم مبلغِ دو شارژ را با هم
می‌شمرد هم روزِ شارژِ دوم را به شارژِ اول تعمیم می‌داد.

پوشش:
۱. `wallet_service.expiry_lots` / `credit_summary`: یکِ SELECT، به تفکیکِ روزِ انقضا، مرتب
   به همان ترتیبی که مصرف می‌شود، با مبلغِ *باقی‌مانده* (نه مبلغِ اصلیِ شارژ).
۲. صفحهٔ واقعیِ «💰 کیف‌پول» (مسیرِ هندلر): هر شارژ یک خط با روزهایِ باقی‌مانده و تاریخِ
   جلالی، و هیچ ادعایِ تکِ «تا ۳۰ روزِ دیگر» باقی نمانده است.
۳. دو شارژِ هم‌روز ⇒ یک خطِ جمع‌شده؛ شارژِ بیش از سقفِ نمایش ⇒ خطِ «و N شارژِ دیگر».
۴. گزارشِ شبانه: «نزدیک‌ترین انقضا» + جمعِ آنچه تا ۳۰ روزِ دیگر می‌رود (نه یک عددِ قاطی).

اجرا: python3 tests_manual/run_one.py test_p39_wallet_per_charge_expiry.py
"""
from __future__ import annotations

import asyncio
import datetime
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from sqlalchemy import select  # noqa: E402

from harness import build_test_dispatchers, reset_database  # noqa: E402
from phase4_helpers import Chat  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot import texts  # noqa: E402
from app.database.models import ShopOwner, WalletTransactionReason  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import wallet_service  # noqa: E402

OWNER_TG_ID = 7_390_000_021
SHOP_BOT_TG_ID = 7_390_000_022


async def _add_charge(owner_id: int, amount: int, days: int) -> int:
    """شارژ با انقضایِ روزشده (درِ تست، تاریخِ انقضا را دستی تنظیم می‌کنیم تا سناریویِ مالک
    دقیقاً بازسازی شود؛ `add_charge` خودش موجودیِ کش‌شده را زیاد می‌کند)."""
    async with session_scope() as session:
        owner = await session.get(ShopOwner, owner_id)
        charge = await wallet_service.add_charge(session, owner, amount, reason=WalletTransactionReason.TOPUP)
        charge.expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=days)
        await session.flush()
        charge_id = charge.id
        await session.commit()
        return charge_id


async def _owner_id() -> int:
    async with session_scope() as session:
        return (await session.execute(select(ShopOwner.id).where(ShopOwner.telegram_id == OWNER_TG_ID))).scalar_one()


# ============================================================================= ۱ — انقضایِ هر شارژ
async def test_lots_are_per_charge_and_ordered_by_spend() -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID, initial_balance_toman=0)
    owner_id = await _owner_id()
    await _add_charge(owner_id, 500_000, 6)   # شارژِ یکم: ۵-۶ روزِ دیگر می‌رود
    await _add_charge(owner_id, 400_000, 26)  # شارژِ بیستم: دست‌نخورده و ۲۶ روزِ دیگر

    async with session_scope() as session:
        owner = await session.get(ShopOwner, owner_id)
        assert await wallet_service.deduct(session, owner, 100_000, WalletTransactionReason.CHAT_MESSAGE)
        await session.commit()

    async with session_scope() as session:
        owner = await session.get(ShopOwner, owner_id)
        usable, lots = await wallet_service.credit_summary(session, owner)
    assert [(lot.remaining_toman, lot.days_left) for lot in lots] == [(400_000, 6), (400_000, 26)], lots
    assert usable == 800_000, usable  # ۹۰۰٬۰۰۰ باقی‌مانده، ۱۰۰٬۰۰۰ مصرف‌شده از کشِ موجودی
    assert lots[0].expires_at < lots[1].expires_at, "ترتیب = ترتیبِ مصرفِ FIFO"
    print("✅ test_lots_are_per_charge_and_ordered_by_spend PASSED")


# ============================================================================= ۲ — صفحهٔ واقعیِ کیف‌پول
async def test_wallet_screen_names_every_charge_expiry(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID, initial_balance_toman=0)
    owner_id = await _owner_id()
    await _add_charge(owner_id, 500_000, 6)
    await _add_charge(owner_id, 400_000, 26)
    async with session_scope() as session:
        owner = await session.get(ShopOwner, owner_id)
        await wallet_service.deduct(session, owner, 100_000, WalletTransactionReason.CHAT_MESSAGE)
        await session.commit()

    owner_chat = Chat(main_dp, OWNER_TG_ID)
    await owner_chat.say("💰 کیف‌پول")
    screen = owner_chat.last_text
    assert "⏳ شارژها به ترتیبِ مصرف" in screen, screen
    assert "۴۰۰٬۰۰۰ تومان — ۶ روزِ دیگر" in screen, screen
    assert "۴۰۰٬۰۰۰ تومان — ۲۶ روزِ دیگر" in screen, screen
    assert screen.count("۴۰۰٬۰۰۰ تومان — ") == 2, screen
    assert "آبان ۱۴۰۵" in screen and "آذر ۱۴۰۵" in screen, "تاریخِ جلالیِ هر شارژ هم گفته می‌شود"
    # ادعایِ تکِ قبلی («۸۰۰٬۰۰۰ از این مبلغ تا ۳۰ روزِ دیگر منقضی می‌شود») نباید بماند
    assert "از این مبلغ تا" not in screen, screen
    assert "تا ۳۰ روزِ دیگر منقضی می‌شود" not in screen, screen
    print("✅ test_wallet_screen_names_every_charge_expiry PASSED")


# ============================================================================= ۳ — شارژها جدا و فهرست‌هایِ بلند تا‌شده
async def test_same_day_charges_stay_separate_and_long_lists_fold() -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID, initial_balance_toman=0)
    owner_id = await _owner_id()
    await _add_charge(owner_id, 100_000, 9)
    await _add_charge(owner_id, 50_000, 9)  # P42 · موردِ ۲۱: همان روزِ انقضا ⇒ دو خطِ جدا
    for day in (12, 20, 40, 55, 70, 90, 120):
        await _add_charge(owner_id, 10_000, day)

    async with session_scope() as session:
        owner = await session.get(ShopOwner, owner_id)
        _usable, lots = await wallet_service.credit_summary(session, owner)
    assert [(lot.remaining_toman, lot.days_left) for lot in lots[:2]] == [(100_000, 9), (50_000, 9)], lots
    assert len(lots) == 9, len(lots)

    body = texts.wallet_status_text(340_000, lots=lots)
    assert "۱۰۰٬۰۰۰ تومان — ۹ روزِ دیگر" in body and "۵۰٬۰۰۰ تومان — ۹ روزِ دیگر" in body, body
    assert body.count("\n• ") == texts.WALLET_LOT_DISPLAY_LIMIT + 1, body  # ۶ خط + خطِ جمعِ بقیه
    assert "و ۳ شارژِ دیگر" in body, body
    assert "۱۲۰ روزِ دیگر" in body, "دیرترینِ انقضایِ فهرستِ جمع‌شده گفته می‌شود"
    assert "۹۰ روزِ دیگر" not in body, "پس ازِ سقفِ نمایش، تک‌تکِ ردیف‌ها تکرار نشوند"
    print("✅ test_same_day_charges_stay_separate_and_long_lists_fold PASSED")


# ============================================================================= ۴ — گزارشِ شبانه
def test_digest_line_is_honest_about_nearest_expiry() -> None:
    line = texts.digest_wallet_line(500_000, 420_000, 90_000, 12, 30_000)
    assert "نزدیک‌ترین انقضا: ۱۲ روزِ دیگر" in line, line
    assert "۹۰٬۰۰۰ تومان تا ۳۰ روزِ دیگر منقضی می‌شود" in line, line
    assert "انقضایِ خودش" in line, line
    none_due = texts.digest_wallet_line(500_000, 500_000, 0, None, 0)
    assert "انقضا" not in none_due, none_due
    print("✅ test_digest_line_is_honest_about_nearest_expiry PASSED")


async def main() -> None:
    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    await test_lots_are_per_charge_and_ordered_by_spend()
    await test_wallet_screen_names_every_charge_expiry(main_dp)
    await test_same_day_charges_stay_separate_and_long_lists_fold()
    test_digest_line_is_honest_about_nearest_expiry()


if __name__ == "__main__":
    asyncio.run(main())
