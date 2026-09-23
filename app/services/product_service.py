from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Product


async def create_product(
    session: AsyncSession,
    shop_bot_id: int,
    name: str,
    description: str | None,
    price_toman: int,
    photo_file_id: str | None,
    stock_quantity: int | None = None,
) -> Product:
    product = Product(
        shop_bot_id=shop_bot_id,
        name=name,
        description=description,
        price_toman=price_toman,
        photo_file_id=photo_file_id,
        stock_quantity=stock_quantity,
    )
    session.add(product)
    await session.flush()
    return product


async def get_active_by_shop_bot(session: AsyncSession, shop_bot_id: int) -> list[Product]:
    result = await session.execute(select(Product).where(Product.shop_bot_id == shop_bot_id, Product.is_active.is_(True)).order_by(Product.id))
    return list(result.scalars().all())


async def get_by_id(session: AsyncSession, product_id: int) -> Product | None:
    """
    توجه: این تابع مالکیت رو چک نمی‌کنه — فقط برای مسیرهایی مناسبه که
    shop_bot_id از قبل به‌صورتِ امن (نه از callback_data) به‌دست اومده،
    مثل customer.py که shop_bot از روی توکنِ ربات مشخص می‌شه. برای هر
    مسیری که product_id از دکمه/callback_data میاد، حتماً از
    get_owned_by_id استفاده کن، نه این تابع.
    """
    return await session.get(Product, product_id)


async def get_owned_by_id(session: AsyncSession, product_id: int, shop_bot_id: int) -> Product | None:
    """
    مثلِ get_by_id ولی مالکیت رو هم چک می‌کنه — اگه محصول متعلق به
    shop_bot_id دیگه‌ای باشه (یا اصلاً وجود نداشته باشه)، None برمی‌گردونه.
    این تابع باید توی هر مسیری که product_id از callback_data یا ورودیِ
    کاربر میاد استفاده بشه، تا یه فروشگاه‌دار نتونه با حدس‌زدنِ شناسه،
    محصولِ فروشگاهِ دیگه‌ای رو ببینه/ویرایش/حذف کنه.
    """
    result = await session.execute(select(Product).where(Product.id == product_id, Product.shop_bot_id == shop_bot_id))
    return result.scalar_one_or_none()


async def soft_delete(session: AsyncSession, product: Product) -> None:
    product.is_active = False
    await session.flush()
