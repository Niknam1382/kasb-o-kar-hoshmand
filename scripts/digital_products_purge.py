"""پ۹۴ · پاک‌سازیِ دادهٔ دیجیتال — با قفلِ دو-stage، فقط‌خواندنی به‌صورتِ پیش‌فرض.

چرا این‌قدر محتاط: مالکِ محصول خواست محصولاتِ دیجیتال حذف شوند (موردِ ۲۵). پ۷۸ درِ *ساختنِ* تازه را
بست و پ۸۵-الف ابزارِ شمارش را داد. این اسکریپت مرحلهٔ بعد است و به‌عمد:

• بدونِ کلیدواژهٔ تایید **هیچ چیز** حذف نمی‌کند (حالتِ پیش‌فرض: dry-run با شمارشِ دقیق).
• اگر حتی یکِ سفارش به محصولِ دیجیتال وصل باشد، **خارج می‌شود** (نه حذفِ تاریخچهٔ مالی، نه بی‌صاحب
  گذاشتنِ سفارشِ پرداخت‌شده). در آن حالت اول باید تکلیفِ سفارش‌ها روشن شود.
• هیچ ستون یا جدولی را حذف نمی‌کند (قاعدهٔ ۴ِ AGENTS.md)؛ فقط ردیفِ داده.
• قبلِ اجرایِ واقعی باید `pg_dump` گرفته شود — خودِ اسکریپت هم همین را یادآوری می‌کند و اگر
  متغیرِ محیطِ `PURGE_BACKUP_CONFIRMED=1` نباشد، اجرایِ واقعی را انجام نمی‌دهد.

    # فقط ببین چه چیزی درگیر است (بی‌خطر):
    docker compose run --rm bot python3 scripts/digital_products_purge.py

    # اجرایِ واقعی (با بکاپِ تأییدشده، رویِ دیتابیسِ درست):
    PURGE_BACKUP_CONFIRMED=1 docker compose run --rm bot python3 scripts/digital_products_purge.py --execute --confirm delete-digital-data
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from sqlalchemy import delete, func, select

sys.path.insert(0, ".")

from app.database.models import DigitalCode, OrderConsultation, Product  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.utils.validators import fa_grouped  # noqa: E402

CONFIRM_PHRASE = "delete-digital-data"


async def plan(session) -> tuple[list[int], int, int, int]:
    product_ids = [
        row[0]
        for row in (await session.execute(select(Product.id).where(Product.kind == "digital"))).all()
    ]
    codes = orders = 0
    if product_ids:
        codes = (
            await session.execute(
                select(func.count()).select_from(DigitalCode).where(DigitalCode.product_id.in_(product_ids))
            )
        ).scalar_one()
        orders = (
            await session.execute(
                select(func.count())
                .select_from(OrderConsultation)
                .where(OrderConsultation.product_id.in_(product_ids))
            )
        ).scalar_one()
    return product_ids, int(codes), int(orders), len(product_ids)


async def run(execute: bool, confirm: str) -> int:
    async with session_scope() as session:
        product_ids, codes, orders, products = await plan(session)
        print(f"محصولاتِ دیجیتال: {fa_grouped(products)} · کدهایِ دیجیتال: {fa_grouped(codes)} · سفارش‌هایِ وصل‌شده: {fa_grouped(orders)}")
        if not product_ids:
            print("چیزی برایِ پاک‌کردن نیست (محصولِ دیجیتالی در این دیتابیس نیست).")
            return 0
        if orders:
            print("⛔ توقف: این محصولات در سفارش‌ها ثبت شده‌اند. پاک‌کردنِ آن‌ها تاریخچهٔ مالی/تحویل را می‌شکند.")
            print("   اول تکلیفِ سفارش‌ها روشن شود (تحویل، یا بازگرداندنِ آن‌ها به محصولِ فیزیکی/مشاوره).")
            return 2
        if not execute:
            print("dry-run: هیچ ردیفی حذف نشد. برایِ حذفِ واقعی هم --execute هم --confirm لازم است.")
            return 0
        if confirm != CONFIRM_PHRASE:
            print(f"⛔ عبارتِ تایید درست نیست؛ باید بنویسی: {CONFIRM_PHRASE}")
            return 2
        if os.environ.get("PURGE_BACKUP_CONFIRMED") != "1":
            print("⛔ بدونِ بکاپِ تأییدشده اجرا نمی‌شود: اول `pg_dump`، بعد PURGE_BACKUP_CONFIRMED=1.")
            return 2
        deleted_codes = await session.execute(delete(DigitalCode).where(DigitalCode.product_id.in_(product_ids)))
        deleted_products = await session.execute(delete(Product).where(Product.id.in_(product_ids)))
        await session.commit()
        print(
            "پاک شد:",
            fa_grouped(int(deleted_codes.rowcount or 0)),
            "کد و",
            fa_grouped(int(deleted_products.rowcount or 0)),
            "محصولِ دیجیتال (ستون/جدول حذف نشده است).",
        )
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="پاک‌سازیِ دادهٔ دیجیتال با قفلِ تایید")
    parser.add_argument("--execute", action="store_true", help="اجرایِ واقعی (بدونِ این فقط گزارش)")
    parser.add_argument("--confirm", default="", help=f"عبارتِ تایید: {CONFIRM_PHRASE}")
    args = parser.parse_args()
    return asyncio.run(run(args.execute, args.confirm))


if __name__ == "__main__":
    raise SystemExit(main())
