from __future__ import annotations

import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import OrderConsultation, OrderStatus, OrderType, Product
from app.services.admin_settings_service import get_admin_settings

# وضعیت‌هایی که با دکمه‌ی «مرحله‌ی بعد» می‌شه ازشون جلو رفت، به همین ترتیب.
_ADVANCE_SEQUENCE = [OrderStatus.CONFIRMED, OrderStatus.PROCESSING, OrderStatus.SHIPPED, OrderStatus.COMPLETED]


async def get_recent_duplicate(
    session: AsyncSession,
    customer_id: int,
    order_type: OrderType,
    product_id: int | None,
    minutes: int,
) -> OrderConsultation | None:
    """
    محافظِ dedup: فقط سفارش‌هایی که واقعاً همون «یه سفارش که دوبار تشخیص داده
    شده» به‌نظر می‌رسن رو duplicate حساب می‌کنه — نه هر سفارشِ اخیرِ این
    مشتری رو. قبلاً این چک صرفاً «آیا این مشتری در N دقیقه‌ی اخیر هر سفارشی
    داشته» بود که یه باگِ واقعی بود: مشتری‌ای که واقعاً می‌خواست ظرفِ چند
    دقیقه دو سفارشِ جدا (مثلاً برای دو محصولِ متفاوت) ثبت کنه، سفارشِ دومش
    نادیده گرفته می‌شد. معیارِ «همون سفارش» الان: همون مشتری + همون نوع
    (سفارش/مشاوره) + همون محصول (یا اگه محصولی مشخص نشده، هر دو بدونِ
    محصول باشن).
    """
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=minutes)
    result = await session.execute(
        select(OrderConsultation)
        .where(
            OrderConsultation.customer_id == customer_id,
            OrderConsultation.created_at > cutoff,
            OrderConsultation.type == order_type,
            OrderConsultation.product_id == product_id,
        )
        .order_by(OrderConsultation.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def create_order(
    session: AsyncSession,
    shop_bot_id: int,
    customer_id: int,
    order_type: OrderType,
    summary: str,
    estimated_value_toman: int | None,
    product_id: int | None = None,
    quantity: int | None = None,
) -> OrderConsultation:
    """
    سفارش/مشاوره‌ی جدید می‌سازه. اگه به یه محصولِ موجودی‌دار وصل باشه، تلاش
    می‌کنه همون لحظه موجودی رو رزرو کنه (تا وقتی فروشگاه‌دار تاییدش کنه یا
    رزرو منقضی بشه) — این جلوی اضافه‌فروشیِ آخرین واحدِ یه محصول به چند
    مشتریِ هم‌زمان رو می‌گیره. اگه موجودیِ کافی برای رزرو نبود (مثلاً همین
    الان توسطِ یه سفارشِ دیگه رزرو شده)، سفارش بازم ساخته می‌شه (فروشگاه‌دار
    باید ببینتش) ولی بدونِ رزرو؛ فروشگاه‌دار موقعِ تایید متوجهِ کمبود می‌شه.
    """
    order = OrderConsultation(
        shop_bot_id=shop_bot_id,
        customer_id=customer_id,
        type=order_type,
        summary=summary,
        estimated_value_toman=estimated_value_toman,
        product_id=product_id,
        quantity=quantity,
        status=OrderStatus.PENDING,
    )
    session.add(order)
    await session.flush()

    if product_id is not None:
        product = await session.get(Product, product_id)
        if product is not None and product.stock_quantity is not None:
            qty = quantity or 1
            available = product.stock_quantity - product.reserved_quantity
            if available >= qty:
                admin_settings = await get_admin_settings(session)
                product.reserved_quantity += qty
                order.stock_reserved = True
                order.reservation_expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
                    minutes=admin_settings.order_reservation_minutes
                )

    await session.flush()
    return order


async def get_by_id(session: AsyncSession, order_id: int) -> OrderConsultation | None:
    return await session.get(OrderConsultation, order_id)


async def get_owned_by_id(session: AsyncSession, order_id: int, shop_bot_id: int) -> OrderConsultation | None:
    """
    مثلِ get_by_id ولی مالکیت رو هم چک می‌کنه — برای مسیرهایی که order_id
    از callback_data میاد (مثل تاییدِ سفارش)، تا یه فروشگاه‌دار نتونه با
    حدس‌زدنِ شناسه، سفارشِ فروشگاهِ دیگه‌ای رو تایید کنه.
    """
    result = await session.execute(
        select(OrderConsultation).where(OrderConsultation.id == order_id, OrderConsultation.shop_bot_id == shop_bot_id)
    )
    return result.scalar_one_or_none()


async def _release_reservation(session: AsyncSession, order: OrderConsultation) -> None:
    if not order.stock_reserved:
        return
    if order.product_id is not None:
        product = await session.get(Product, order.product_id)
        if product is not None:
            qty = order.quantity or 1
            product.reserved_quantity = max(0, product.reserved_quantity - qty)
    order.stock_reserved = False


async def confirm_order(session: AsyncSession, order: OrderConsultation) -> bool:
    """
    سفارش رو تاییدشده علامت می‌زنه و اگه به یه محصولِ موجودی‌دار وصل باشه،
    از تعدادِ موجودیش کم می‌کنه (اگه رزروی داشت، رزرو به کسرِ قطعی تبدیل
    می‌شه؛ اگه رزرو نداشت — مثلاً منقضی شده بود — بازم مستقیم کم می‌شه، چون
    فروشگاه‌دار یه انسانِ قابل‌اعتماده که داره دستی تایید می‌کنه). اگه از قبل
    تاییدشده بود، False برمی‌گردونه (برای جلوگیری از کسرِ دوباره‌ی موجودی با
    چندبار زدنِ دکمه).
    """
    if order.confirmed:
        return False

    order.confirmed = True
    order.confirmed_at = datetime.datetime.now(datetime.timezone.utc)
    order.status = OrderStatus.CONFIRMED

    if order.product_id is not None:
        product = await session.get(Product, order.product_id)
        if product is not None and product.stock_quantity is not None:
            qty = order.quantity or 1
            if order.stock_reserved:
                product.reserved_quantity = max(0, product.reserved_quantity - qty)
            product.stock_quantity = max(0, product.stock_quantity - qty)

    order.stock_reserved = False
    await session.flush()
    return True


async def reject_order(session: AsyncSession, order: OrderConsultation) -> bool:
    """
    فروشگاه‌دار سفارش رو رد می‌کنه (مثلاً موجودیِ واقعی نداره یا هوش مصنوعی
    اشتباه تشخیص داده). اگه رزروی روی موجودی داشت، آزادش می‌کنه. فقط برای
    سفارش‌های PENDING کار می‌کنه؛ برای بقیه False برمی‌گردونه.
    """
    if order.status != OrderStatus.PENDING:
        return False
    await _release_reservation(session, order)
    order.status = OrderStatus.REJECTED
    await session.flush()
    return True


async def advance_status(session: AsyncSession, order: OrderConsultation) -> OrderStatus | None:
    """
    وضعیتِ یه سفارشِ تاییدشده رو یه پله جلو می‌بره: تاییدشده → در حالِ
    آماده‌سازی → ارسال‌شده → تکمیل‌شده. اگه سفارش هنوز تاییدنشده یا از قبل
    تکمیل/لغو/ردشده باشه، None برمی‌گردونه (کاری انجام نمی‌شه).
    """
    if order.status not in _ADVANCE_SEQUENCE:
        return None
    idx = _ADVANCE_SEQUENCE.index(order.status)
    if idx == len(_ADVANCE_SEQUENCE) - 1:
        return None
    order.status = _ADVANCE_SEQUENCE[idx + 1]
    await session.flush()
    return order.status


async def expire_stale_reservations(session: AsyncSession) -> list[OrderConsultation]:
    """
    سفارش‌های PENDING که رزروشون منقضی شده رو پیدا می‌کنه، رزروِ موجودیشون
    رو آزاد می‌کنه، و status رو EXPIRED می‌ذاره. برای اجرای دوره‌ای توسطِ
    زمان‌بند (مثلِ الگوی wallet_expiry_service).
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    result = await session.execute(
        select(OrderConsultation).where(
            OrderConsultation.status == OrderStatus.PENDING,
            OrderConsultation.stock_reserved.is_(True),
            OrderConsultation.reservation_expires_at.is_not(None),
            OrderConsultation.reservation_expires_at < now,
        )
    )
    expired = list(result.scalars().all())
    for order in expired:
        await _release_reservation(session, order)
        order.status = OrderStatus.EXPIRED
    if expired:
        await session.flush()
    return expired


async def count_by_type(session: AsyncSession, shop_bot_id: int) -> dict[str, int]:
    result = await session.execute(
        select(OrderConsultation.type, func.count())
        .where(OrderConsultation.shop_bot_id == shop_bot_id)
        .group_by(OrderConsultation.type)
    )
    counts = {"order": 0, "consultation": 0}
    for order_type, count in result.all():
        key = order_type.value if hasattr(order_type, "value") else order_type
        counts[key] = count
    return counts


async def get_recent_summaries(session: AsyncSession, shop_bot_id: int, since: datetime.datetime) -> list[str]:
    result = await session.execute(
        select(OrderConsultation.summary).where(OrderConsultation.shop_bot_id == shop_bot_id, OrderConsultation.created_at > since)
    )
    return [row[0] for row in result.all()]


async def get_recent_for_owner_notification(session: AsyncSession, order_id: int) -> OrderConsultation | None:
    return await session.get(OrderConsultation, order_id)
