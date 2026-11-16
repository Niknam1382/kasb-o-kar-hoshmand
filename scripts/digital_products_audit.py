"""پ۸۵ · شمارشِ دادهٔ دیجیتال (فقط‌خواندنی) — قبلِ هر تصمیمِ پاک‌سازی.

خواستهٔ مالک (موردِ ۲۵) «حذفِ کاملِ محصولاتِ دیجیتال» بود. پ۷۸ *درِ ساختنِ تازه* را بست؛ آنچه باقی
مانده تصمیمِ پاک‌سازیِ داده است، و آن:

• قابلِ بازگشت نیست ⇒ طبقِ قاعدهٔ ۳ِ AGENTS.md اول باید `pg_dump` گرفته شود،
• به قاعدهٔ ۴ («هیچ ستون/جدولی حذف نشود») می‌خورد ⇒ حذفِ داده با مایگریشنِ ستون فرقی نمی‌کند و
  اجازهٔ صریحِ مالک لازم دارد.

پس این اسکریپت **هیچ چیز را عوض نمی‌کند** و فقط می‌گوید اگر پاک‌سازی برواد، چه چیزی درگیر می‌شود:
تعدادِ محصولاتِ دیجیتال به تفکیکِ فروشگاه، تعدادِ کدهایِ دیجیتال (و چندتایِشان مصرف‌نشده)،
سفارش‌هایِ دارایِ آیتمِ دیجیتال به تفکیکِ وضعیت، و اینکه آیا هیچ ردیفِ «پرداخت‌شده ولی تحویل‌نشده»
هست که پاک‌کردنش یعنی پولِ گرفته‌شده بی‌تحویل.

نحوهٔ اجرا (رویِ همان ایمیجِ ربات):
    docker compose run --rm bot python3 scripts/digital_products_audit.py
    docker compose run --rm bot python3 scripts/digital_products_audit.py --shop 42

خروجی: جدولِ فارسی + یکِ خطِ جمعِ نهایی + کدِ خروج (۰ = همیشه؛ این اسکریپت تصمیم نمی‌گیرد).
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import func, select

sys.path.insert(0, ".")

from app.database.models import (  # noqa: E402
    DigitalCode,
    OrderConsultation,
    OrderStatus,
    Product,
    ShopBot,
)
from app.database.session import session_scope  # noqa: E402
from app.utils.validators import fa_number  # noqa: E402


async def report(shop_bot_id: int | None) -> int:
    async with session_scope() as session:
        scope = [Product.kind == "digital"]
        if shop_bot_id is not None:
            scope.append(Product.shop_bot_id == shop_bot_id)
        products = list(
            (
                await session.execute(
                    select(Product.shop_bot_id, func.count())
                    .where(*scope)
                    .group_by(Product.shop_bot_id)
                    .order_by(func.count().desc(), Product.shop_bot_id)
                )
            ).all()
        )
        product_ids = [row[0] for row in (await session.execute(select(Product.id).where(*scope))).all()]
        codes_total = codes_free = 0
        if product_ids:
            codes_total = (
                await session.execute(select(func.count()).select_from(DigitalCode).where(DigitalCode.product_id.in_(product_ids)))
            ).scalar_one()
            codes_free = (
                await session.execute(
                    select(func.count())
                    .select_from(DigitalCode)
                    .where(DigitalCode.product_id.in_(product_ids), DigitalCode.status == "available")
                )
            ).scalar_one()
        # «دیجیتال بودن» رویِ خودِ سفارش نیست (OrderType فقط order/consultation دارد)، پس با پیوستن
        # به محصول شمرده می‌شود — همان چیزی که در مسیرِ تحویل خوانده می‌شود.
        orders_stmt = (
            select(OrderConsultation.status, func.count())
            .join(Product, OrderConsultation.product_id == Product.id)
            .where(Product.kind == "digital")
            .group_by(OrderConsultation.status)
        )
        if shop_bot_id is not None:
            orders_stmt = orders_stmt.where(OrderConsultation.shop_bot_id == shop_bot_id)
        orders = dict((await session.execute(orders_stmt)).all())
        paid_undelivered = sum(
            count for status, count in orders.items() if status in (OrderStatus.PAID, OrderStatus.CONFIRMED)
        )
        shops = {row.id: row for row in (await session.execute(select(ShopBot.id, ShopBot.bot_username))).all()}

        print("محصولاتِ دیجیتال به تفکیکِ فروشگاه:")
        if not products:
            print("  • هیچ محصولِ دیجیتالی پیدا نشد.")
        for sid, count in products:
            shop = shops.get(sid)
            label = getattr(shop, "bot_username", "") or "?"
            print(f"  • فروشگاه {fa_number(sid)} (@{label}): {fa_number(count)} محصول")
        print(f"کدهایِ دیجیتالِ این محصولات: {fa_number(codes_total)} (مصرف‌نشده: {fa_number(codes_free)})")
        print("سفارش‌هایِ دیجیتال به تفکیکِ وضعیت:")
        if not orders:
            print("  • هیچ سفارشِ دیجیتالی ثبت نشده است.")
        for status, count in sorted(orders.items(), key=lambda item: -item[1]):
            print(f"  • {status.value}: {fa_number(count)}")
        print(
            "⚠️ اگر پاک‌سازی کنی، "
            + (
                f"{fa_number(paid_undelivered)} سفارشِ پرداخت‌شده/تاییدشده بی‌تحویل می‌ماند ⇒ اول تحویل بده."
                if paid_undelivered
                else "هیچ سفارشِ پرداخت‌شدهٔ بی‌تحویلی نیست؛ پاک‌سازی از این نظرِ تحویل، بی‌خطر است."
            )
        )
        print(
            "یادآوری: این اسکریپت چیزی را پاک نمی‌کند. برایِ پاک‌سازی: اول pg_dump، بعد اجازهٔ صریحِ مالک،"
            " بعد حذفِ داده (ستون‌ها و جدول‌ها طبقِ قاعدهٔ ۴ حذف نمی‌شوند)."
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="شمارشِ فقط‌خواندنیِ دادهٔ دیجیتال")
    parser.add_argument("--shop", type=int, default=None, help="فقطِ یکِ فروشگاه (شناسهٔ shop_bot)")
    args = parser.parse_args()
    return asyncio.run(report(args.shop))


if __name__ == "__main__":
    raise SystemExit(main())
