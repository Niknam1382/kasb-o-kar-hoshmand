from __future__ import annotations

import hashlib

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Cart, CartItem, Product


async def get_or_create_cart(session: AsyncSession, shop_bot_id: int, customer_id: int) -> Cart:
    result = await session.execute(select(Cart).where(Cart.shop_bot_id == shop_bot_id, Cart.customer_id == customer_id))
    cart = result.scalar_one_or_none()
    if cart is not None:
        return cart
    cart = Cart(shop_bot_id=shop_bot_id, customer_id=customer_id)
    session.add(cart)
    await session.flush()
    return cart


def cart_fingerprint(items_with_products: list[tuple[CartItem, Product]]) -> str:
    """یه امضای کوتاه از «محتوایِ» سبد (شناسه‌ی محصول + تعداد، مستقل از ترتیب). وقتی
    سبد بینِ نمایشِ یه پیام/دکمه و فشرده‌شدنِ اون دکمه تغییر کرده باشه، امضا فرق می‌کنه
    و می‌فهمیم اون دکمه/پیش‌نمایش دیگه مالِ سبدِ فعلی نیست."""
    ordered = sorted(items_with_products, key=lambda pair: pair[0].product_id)
    raw = ";".join(f"{item.product_id}x{item.quantity}" for item, _product in ordered)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:10]


async def get_cart(session: AsyncSession, shop_bot_id: int, customer_id: int) -> Cart | None:
    """مثلِ get_or_create_cart، ولی هیچ‌وقت سبدِ تازه نمی‌سازه — برایِ مسیرهایی که فقط
    می‌خوان بدونن مشتری سبدِ فعالی داره یا نه (مثلاً ویرایشِ سبد با AI)."""
    result = await session.execute(select(Cart).where(Cart.shop_bot_id == shop_bot_id, Cart.customer_id == customer_id))
    return result.scalar_one_or_none()


async def get_item_by_product(session: AsyncSession, cart_id: int, product_id: int) -> CartItem | None:
    result = await session.execute(select(CartItem).where(CartItem.cart_id == cart_id, CartItem.product_id == product_id))
    return result.scalar_one_or_none()


async def get_items_with_products(session: AsyncSession, cart_id: int) -> list[tuple[CartItem, Product]]:
    """آیتم‌هایِ سبد به‌همراهِ خودِ محصول (برایِ نمایشِ نام/قیمتِ فعلی — قیمت
    موقعِ افزودن به سبد snapshot نمی‌شه، همیشه قیمتِ الانِ محصول حساب می‌شه،
    دقیقاً مثلِ رفتارِ استانداردِ یه سبدِ خریدِ e-commerce)."""
    result = await session.execute(select(CartItem, Product).join(Product, CartItem.product_id == Product.id).where(CartItem.cart_id == cart_id))
    return list(result.all())




def available_stock(product: Product) -> int | None:
    """None یعنی نامحدود. وگرنه موجودیِ واقعاً قابل‌فروش (رزروشده‌ها کم شده)."""
    if product.stock_quantity is None:
        return None
    return max(0, product.stock_quantity - product.reserved_quantity)


async def add_item(session: AsyncSession, cart: Cart, product: Product, quantity: int = 1) -> tuple[CartItem | None, int]:
    """
    quantity واحد به سبد اضافه می‌کنه (یا اگه از قبل بود، جمع می‌زنه). مقدارِ
    نهایی به سقفِ موجودیِ الان محدود می‌شه — فقط یه راهنمایی برای تجربه‌ی
    کاربریه؛ رزروِ واقعی و امنِ موجودی (حتی زیرِ همزمانی) موقعِ چک‌اوت توسطِ
    order_service.create_order انجام می‌شه، نه اینجا.

    برمی‌گردونه: (ردیفِ سبد، مقدارِ واقعاً اضافه‌شده). اگه سقفِ موجودی مانعِ
    افزودنِ کاملِ مقدارِ خواسته‌شده بشه، عددِ برگشتی از quantityِ ورودی کمتره؛
    اگه موجودی صفر بود و آیتم تازه‌ست، ردیف None و عدد صفره.
    """
    result = await session.execute(select(CartItem).where(CartItem.cart_id == cart.id, CartItem.product_id == product.id))
    item = result.scalar_one_or_none()
    current = item.quantity if item is not None else 0

    cap = available_stock(product)
    target = current + quantity if cap is None else min(current + quantity, cap)
    target = max(target, current)  # هیچ‌وقت کمتر از چیزی که از قبل تو سبده نشه
    added = target - current

    if item is None:
        if target == 0:
            return None, 0
        item = CartItem(cart_id=cart.id, product_id=product.id, quantity=target)
        session.add(item)
    else:
        item.quantity = target

    await session.flush()
    return item, added


async def set_quantity(session: AsyncSession, cart_item: CartItem, quantity: int) -> None:
    if quantity <= 0:
        await session.delete(cart_item)
    else:
        cart_item.quantity = quantity
    await session.flush()


async def remove_item(session: AsyncSession, cart_item: CartItem) -> None:
    await session.delete(cart_item)
    await session.flush()


async def clear_cart(session: AsyncSession, cart_id: int) -> None:
    result = await session.execute(select(CartItem).where(CartItem.cart_id == cart_id))
    for item in result.scalars().all():
        await session.delete(item)
    await session.flush()


async def get_cart_item_owned(session: AsyncSession, cart_item_id: int, cart_id: int) -> CartItem | None:
    """مالکیت رو هم چک می‌کنه — یه مشتری نتونه با حدس‌زدنِ id، سبدِ یه مشتریِ
    دیگه رو دستکاری کنه (همون الگویی که order_service.get_owned_by_id داره)."""
    result = await session.execute(select(CartItem).where(CartItem.id == cart_item_id, CartItem.cart_id == cart_id))
    return result.scalar_one_or_none()

async def claim_submit_token(cart_id: int, nonce: str) -> bool:
    """P33-B: ادعایِ «این پیش‌نمایش را من ثبت می‌کنم» — در تراکنشِ *کوتاهِ خودش*.

    چرا سشنِ جدا: تلاشِ اول این ادعا را داخلِ همان تراکنشی گذاشت که بعداً ردیف‌هایِ محصول
    را `FOR UPDATE` می‌گیرد؛ دو تپِ هم‌زمان یکی قفلِ سبد و دیگری قفلِ محصول را نگه داشتند و
    PostgreSQL بن‌بست اعلام کرد (`DeadlockDetectedError`، §P33). این‌جا فقط یکِ سطرِ واحد با
    کلیدِ اصلی قفل و فوراً commit می‌شود، پس هیچ چرخه‌ای ساخته نمی‌شود.
    """
    from app.database.session import session_scope

    if not nonce:
        return False
    async with session_scope() as session:
        result = await session.execute(
            update(Cart)
            .where(Cart.id == cart_id, Cart.submit_token.is_distinct_from(nonce))
            .values(submit_token=nonce)
        )
        await session.commit()
        return int(result.rowcount or 0) == 1

