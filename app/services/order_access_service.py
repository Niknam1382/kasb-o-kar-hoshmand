"""سیاستِ «ادامهٔ سفارش با اعتبارِ صفر» (P30).

با خالی‌شدنِ کیف‌پول، امروز همه‌چیزِ آن فروشگاه می‌ایستد: ربات به مشتری جواب نمی‌دهد و
سفارشی ثبت نمی‌شود. ادمین می‌تواند سوییچِ سراسری را روشن کند تا فروش ادامه یابد؛ بدهیِ
ناشی از کمیسیون در `commission_receivables` با وضعیتِ `open` می‌نشیند و همان‌جا وصول
می‌شود (`collect_due`). `commission_debt_ceiling_toman` سقفِ همان بدهی است (۰ = بی‌سقف).

سه وضعیتِ ممکن:
* `ALLOWED` — موجودی دارد، یا اعتبارِ صفر است ولی سوییچ روشن و بدهی زیرِ سقف.
* `NO_CREDIT` — اعتبارِ صفر و سوییچ خاموش ⇒ مثلِ امروز: همه‌چیز می‌ایستد.
* `DEBT_CEILING` — سوییچ روشن ولی بدهی از سقف گذشته ⇒ چت ادامه می‌یابد،
  سفارش و پرداختِ آنلاین می‌ایستند (درخواستِ کاربر: فقط دکمه‌ها از کار بیفتند).

هیچ مبلغی در این سرویس کسر یا ثبت نمی‌شود؛ فقط خواندن است. پول در
`commission_service` و `wallet_service` می‌ماند (قاعدهٔ پروژه: پول ایدبمپوتنت).
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.services import shop_bot_service, shop_owner_service
from app.services.admin_settings_service import get_admin_settings
from app.services.commission_receivable_service import open_totals_by_owner

ALLOWED = "allowed"
NO_CREDIT = "no_credit"
DEBT_CEILING = "debt_ceiling"


async def open_debt_toman(session: AsyncSession, owner_id: int) -> int:
    """جمعِ بدهیِ وصول‌نشدهٔ کمیسیونِ یکِ فروشگاه‌دار (ردیف‌های `open`)."""
    totals = await open_totals_by_owner(session, {owner_id})
    return int(totals.get(owner_id, 0) or 0)


async def evaluate(session: AsyncSession, owner, admin_settings) -> str:
    if owner is None:
        return NO_CREDIT
    if owner.wallet_balance_toman > 0:
        return ALLOWED
    if not admin_settings.orders_allowed_when_wallet_empty:
        return NO_CREDIT
    ceiling = int(admin_settings.commission_debt_ceiling_toman or 0)
    if ceiling > 0 and await open_debt_toman(session, owner.id) > ceiling:
        return DEBT_CEILING
    return ALLOWED


async def state_for_shop_bot(session: AsyncSession, shop_bot) -> str:
    """همان `evaluate` برایِ جاهایی که فقط `shop_bot` را دارند (سبد، چک‌اوت، پرداخت)."""
    owner = await shop_owner_service.get_by_id(session, shop_bot.shop_owner_id)
    return await evaluate(session, owner, await get_admin_settings(session))


async def state_for_bot(session: AsyncSession, bot) -> str:
    shop_bot = await shop_bot_service.get_by_bot(session, bot)
    if shop_bot is None:
        return NO_CREDIT
    return await state_for_shop_bot(session, shop_bot)


def chat_continues(state: str) -> bool:
    """چتِ AI تنها در وضعیتِ NO_CREDIT می‌ایستد (رفتارِ همیشگیِ پروژه)."""
    return state != NO_CREDIT
