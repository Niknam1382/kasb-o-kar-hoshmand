"""
تست: P30 — آمارِ سراسریِ پنلِ ادمین باید «درآمد از کمیسیون» را از «درآمد از فروشِ اعتبارِ AI/API»
جدا نشان دهد (قبلاً هر دو با هم در یک عددِ «اعتبارِ مصرف‌شده» می‌آمدند).

فهرستِ تراکنش‌هایِ کیف‌پول دو منبعِ درآمد دارد:
  · reason=commission  → کمیسیونِ درصدیِ سفارشِ موفق (settle منفی، reverse مثبت)
  · reason‌هایِ مصرفِ AI (چت، عکس، صوت، تشخیصِ سفارش، ویرایشِ سبد، خلاصهٔ CRM، دستیار) ⇒ همان
    چیزی که پلتفرم به‌عنوانِ اعتبارِ فروخته‌شدهٔ هوش‌مصنوعی می‌بیند

اجرا: python3 tests_manual/run_one.py test_p30_platform_revenue_split.py
"""
from __future__ import annotations

import asyncio
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests_manual"))

from harness import reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot import texts  # noqa: E402
from app.database.models import ShopBot, WalletTransaction, WalletTransactionReason  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import stats_service  # noqa: E402
from app.utils.validators import format_toman  # noqa: E402

OWNER_TG_ID = 999931
BOT_TG_ID = 999932


def test_text_shows_the_two_sources_separately() -> None:
    stats = {
        "total_owners": 3,
        "total_active_bots": 2,
        "owners_with_wallet_balance": 2,
        "total_revenue_toman": 250_000,
        "orders_count": 40,
        "consultations_count": 5,
        "total_wallet_consumed_toman": 120_000,
        "total_given_away_toman": 50_000,
        "commission_revenue_toman": 30_000,
        "ai_api_revenue_toman": 90_000,
    }
    body = texts.platform_stats_text(stats)
    assert "— درآمد به تفکیکِ منبع —" in body
    assert f"🧾 کمیسیونِ سفارش‌ها: {format_toman(30_000)}" in body, body
    assert f"🧠 فروشِ اعتبارِ هوش‌مصنوعی (API): {format_toman(90_000)}" in body, body
    assert f"🧮 جمعِ این دو: {format_toman(120_000)}" in body, body
    print("✅ test_text_shows_the_two_sources_separately PASSED")


def test_text_does_not_promise_cash_for_consumed_credit() -> None:
    body = texts.platform_stats_text(
        {
            "total_owners": 0, "total_active_bots": 0, "owners_with_wallet_balance": 0,
            "total_revenue_toman": 0, "orders_count": 0, "consultations_count": 0,
            "total_wallet_consumed_toman": 0, "total_given_away_toman": 0,
            "commission_revenue_toman": 0, "ai_api_revenue_toman": 0,
        }
    )
    assert "اعتبارِ مصرف‌شده" in body, "باید بگوید این رقم پولِ نقدیِ امروز نیست"
    print("✅ test_text_does_not_promise_cash_for_consumed_credit PASSED")


async def _stats_snapshot() -> dict:
    async with session_scope() as session:
        return await stats_service.get_platform_stats(session)


async def _add_tx(owner_id: int, reason: WalletTransactionReason, amount: int, key: str) -> None:
    async with session_scope() as session:
        session.add(
            WalletTransaction(
                shop_owner_id=owner_id, amount_toman=amount, reason=reason, status="settled", idempotency_key=key
            )
        )
        await session.commit()


async def test_commission_is_counted_separately_from_ai() -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, BOT_TG_ID)
    async with session_scope() as session:
        shop_bot = await session.get(ShopBot, shop_bot_id)
        owner_id = shop_bot.shop_owner_id

    before = await _stats_snapshot()
    await _add_tx(owner_id, WalletTransactionReason.COMMISSION, -7_500, "p30-commission-settle")
    await _add_tx(owner_id, WalletTransactionReason.CHAT_MESSAGE, -2_000, "p30-ai-chat")
    after = await _stats_snapshot()

    assert after["commission_revenue_toman"] - before["commission_revenue_toman"] == 7_500, (
        "کمیسیون باید جدا از مصرفِ AI شمرده شود"
    )
    assert after["ai_api_revenue_toman"] - before["ai_api_revenue_toman"] == 2_000, "مصرفِ AI باید جدا باشد"
    assert after["total_wallet_consumed_toman"] - before["total_wallet_consumed_toman"] == 2_000, (
        "کمیسیون نباید داخلِ عددِ مصرفِ هوش‌مصنوعی هم حساب شود (دو‌بارشماری)"
    )
    print("✅ test_commission_is_counted_separately_from_ai PASSED")


async def test_commission_reversal_nets_down() -> None:
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID + 1, BOT_TG_ID + 1)
    async with session_scope() as session:
        shop_bot = await session.get(ShopBot, shop_bot_id)
        owner_id = shop_bot.shop_owner_id

    before = await _stats_snapshot()
    await _add_tx(owner_id, WalletTransactionReason.COMMISSION, -5_000, "p30-rev-settle")
    await _add_tx(owner_id, WalletTransactionReason.COMMISSION, 5_000, "p30-rev-reverse")
    after = await _stats_snapshot()

    assert after["commission_revenue_toman"] == before["commission_revenue_toman"], (
        "settle و reverseِ هم‌مبلغ باید یکدیگر را صفر کنند"
    )
    print("✅ test_commission_reversal_nets_down PASSED")


async def main() -> None:
    test_text_shows_the_two_sources_separately()
    test_text_does_not_promise_cash_for_consumed_credit()
    await test_commission_is_counted_separately_from_ai()
    await test_commission_reversal_nets_down()


if __name__ == "__main__":
    asyncio.run(main())
