from __future__ import annotations

import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Product

_KIND_DIGITAL = "digital"  # همان مقدارِ `digital_service.KIND_DIGITAL` (بدونِ importِ متقابل)


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


async def create_digital_product(
    session: AsyncSession,
    shop_bot_id: int,
    name: str,
    description: str | None,
    price_toman: int,
    photo_file_id: str | None,
    delivery: str,
    file_id: str | None = None,
    file_name: str | None = None,
    link: str | None = None,
    instructions: str | None = None,
    max_downloads: int | None = None,
) -> Product:
    """محصولِ دیجیتال (B2). موجودی: file/link/text نامحدود (None)؛ code_pool با تعدادِ کدها
    (فراخوان بعد از افزودنِ کدها `digital_service.sync_pool_stock` رو صدا می‌زنه؛ شروع از ۰)."""
    product = Product(
        shop_bot_id=shop_bot_id,
        name=name,
        description=description,
        price_toman=price_toman,
        photo_file_id=photo_file_id,
        stock_quantity=0 if delivery == "code_pool" else None,
        kind="digital",
        digital_delivery=delivery,
        digital_file_id=file_id,
        digital_file_name=file_name,
        digital_link=link,
        digital_instructions=instructions,
        digital_max_downloads=max_downloads,
    )
    session.add(product)
    await session.flush()
    return product


async def get_active_by_shop_bot(session: AsyncSession, shop_bot_id: int) -> list[Product]:
    result = await session.execute(
        select(Product)
        .where(
            Product.shop_bot_id == shop_bot_id,
            Product.is_active.is_(True),
            Product.retired_at.is_(None),
        )
        .order_by(Product.id)
    )
    return list(result.scalars().all())


async def count_digital(session: AsyncSession, shop_bot_id: int, *, retired: bool | None = None) -> int:
    """چند محصولِ دیجیتال (بایگانی‌شده یا نه) اینِ فروشگاه دارد — برایِ صفحهٔ تاییدِ بایگانی."""
    scope = [Product.shop_bot_id == shop_bot_id, Product.kind == _KIND_DIGITAL]
    if retired is True:
        scope.append(Product.retired_at.is_not(None))
    elif retired is False:
        scope.append(Product.retired_at.is_(None))
    return (await session.execute(select(func.count()).select_from(Product).where(*scope))).scalar_one()


async def retire_digital(session: AsyncSession, shop_bot_id: int, *, now=None) -> int:
    """پ۹۷ · بایگانیِ همهٔ محصول‌هایِ دیجیتالِ همینِ فروشگاه ⇒ صفر حذفِ داده، فقط `retired_at`.

    کدها، سفارش‌ها و مسیرِ تحویل دست‌نخورده‌اند؛ اگر بعداً پشیمان شدی `unretire_digital` برمی‌گرداندشان.
    """
    moment = now or datetime.datetime.now(datetime.timezone.utc)
    result = await session.execute(
        update(Product)
        .where(
            Product.shop_bot_id == shop_bot_id,
            Product.kind == _KIND_DIGITAL,
            Product.retired_at.is_(None),
        )
        .values(retired_at=moment)
    )
    await session.flush()
    return int(result.rowcount or 0)


async def unretire_digital(session: AsyncSession, shop_bot_id: int) -> int:
    result = await session.execute(
        update(Product)
        .where(
            Product.shop_bot_id == shop_bot_id,
            Product.kind == _KIND_DIGITAL,
            Product.retired_at.is_not(None),
        )
        .values(retired_at=None)
    )
    await session.flush()
    return int(result.rowcount or 0)


async def lock_for_update(session: AsyncSession, product_id: int) -> Product | None:
    """قفلِ سطریِ ردیفِ محصول *پیش* از خواندن/نوشتنِ موجودی.

    موجودیِ محصول (stock/reserved) تنها چیزی است که دو مشتریِ هم‌زمان رویِ آن رقابت می‌کنند.
    هر READ-modify-WRITE‌ای که این تابع را صدا نزند می‌تواند آخرینِ واحد را دو بار بفروشد
    یا شمارنده را برای همیشه خراب بگذارد. `populate_existing` هم لازم است: همان session
    ممکن است محصول را از قبل در حافظه داشته باشد (فهرستِ محصولات) و بدونِ بازخوانی عددِ
    قدیمی برگردانده شود. ردیف‌ها تا commit قفل می‌مانند ⇒ فقط برنده رقابت می‌نویسد."""
    result = await session.execute(
        select(Product).where(Product.id == product_id).with_for_update().execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


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


# ------------------------------------------------------------------ پ۷۴ · دسته‌بندیِ محصولات
# خواستهٔ مالک: صاحبِ فروشگاه دسته بسازد و کاربر محصولات را دسته‌به‌دسته ببیند. دسته یکِ رشتهٔ
# کوتاه رویِ خودِ محصول است (مثلِ `kind`)، پس فهرستِ دسته‌ها از همان ردیف‌هایِ فروشگاه ساخته می‌شود
# و هیچ ردیفِ یتیم/همگام‌سازیِ جدولِ دوم وجود ندارد. «» همیشه یعنی «بی‌دسته».
CATEGORY_MAX_LEN = 64


def normalize_category(raw: str | None) -> str | None:
    """ورودیِ متنیِ فروشگاه‌دار ⇒ نامِ دسته، یا None برایِ «بی‌دسته»/«رد شد».

    None فقط وقتی که واقعاً چیزی برایِ دسته نمانده باشد («خالی»، «-»، فقط فاصله)؛ نامِ خیلی بلند
    بریده می‌شود، نه اینکه رد شود، چون فروشگاه‌دار قصدِ درست داشته و فقط طول را ندانسته است.
    """
    text = " ".join((raw or "").split())
    if not text or text in {"خالی", "پاک کن", "پاکش کن", "-", "بی‌دسته", "بدون دسته", "بدون دسته‌بندی"}:
        return None
    return text[:CATEGORY_MAX_LEN]


async def set_category(session: AsyncSession, product: Product, name: str | None) -> str:
    """مقدارِ نرمال‌شده را می‌نویسد و همان مقدار را برمی‌گرداند (برایِ پیامِ تایید)."""
    value = normalize_category(name) or ""
    product.category = value
    await session.flush()
    return value


def category_view(products: list[Product]) -> tuple[tuple[str, ...], dict[str, list[Product]], list[Product]]:
    """دسته‌ها از خودِ ردیف‌هایِ فروشگاه ساخته می‌شوند (یکِ SELECT، بدونِ کوئریِ دوم).

    بازگشتی: (نام‌هایِ مرتب‌شده، نگاشتِ نام به محصولاتِ فعالِ همان دسته، محصولاتِ بی‌دسته).
    ترتیبِ نام‌ها همان ترتیبِ پایتون (کدپوینت) است و **پایدار** می‌ماند ⇒ شمارهٔ دسته در
    `callback_data` بینِ دو صفحه معنا دارد (الفبایِ فارسی اینجا هدف نیست، تکرارپذیری هدف است).
    """
    groups: dict[str, list[Product]] = {}
    unassigned: list[Product] = []
    for product in products:
        name = getattr(product, "category", "") or ""
        if name:
            groups.setdefault(name, []).append(product)
        else:
            unassigned.append(product)
    return tuple(sorted(groups)), groups, unassigned


async def rename_category(session: AsyncSession, shop_bot_id: int, old: str, new: str) -> int:
    """تغییرِ نامِ دسته رویِ همهٔ ردیف‌هایِ همان فروشگاه (یکِ UPDATE، فعال و غیرفعال).

    صفر یعنی چیزی عوض نشد (نامِ خالی، همان نامِ قبلی، یا دسته‌ای که دیگر وجود ندارد). شمارِ
    بازگشتی از خودِ پایگاهِ داده می‌آید، نه از فهرستِ خوانده‌شده در حافظه.
    """
    value = normalize_category(new) or ""
    if not value or value == old:
        return 0
    result = await session.execute(
        update(Product).where(Product.shop_bot_id == shop_bot_id, Product.category == old).values(category=value)
    )
    await session.flush()
    return int(result.rowcount or 0)


async def clear_category(session: AsyncSession, shop_bot_id: int, category: str) -> int:
    """همهٔ محصولاتِ آن دسته را «بی‌دسته» می‌کند (هیچ محصولی حذف نمی‌شود) و شمار را برمی‌گرداند."""
    result = await session.execute(
        update(Product).where(Product.shop_bot_id == shop_bot_id, Product.category == category).values(category="")
    )
    await session.flush()
    return int(result.rowcount or 0)
