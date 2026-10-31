from __future__ import annotations

import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import OrderConsultation, OrderStatus, OrderType, Product
from app.services import order_state
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


async def create_order_awaiting_confirmation(
    session: AsyncSession,
    shop_bot_id: int,
    customer_id: int,
    order_type: OrderType,
    summary: str,
    estimated_value_toman: int | None,
    product_id: int | None,
    quantity: int | None,
    customer_phone: str | None,
    customer_address: str | None,
) -> OrderConsultation:
    """
    بازطراحیِ سفارش‌گیری: وقتی هوش مصنوعی یه سفارش/مشاوره‌ی «کامل» تشخیص می‌ده،
    دیگه مستقیم PENDING ساخته نمی‌شه — چون خودِ مشتری هنوز درستیِ اطلاعات رو
    تایید نکرده. این تابع یه ردیفِ کاندید با status=AWAITING_CUSTOMER_CONFIRMATION
    می‌سازه: نه رزروِ موجودی انجام می‌ده، نه فروشگاه‌دار خبردار می‌شه. این دو تا
    فقط بعدِ customer_confirm_order (یعنی تاییدِ واقعیِ مشتری) اتفاق می‌افتن —
    دقیقاً همون‌جا که create_order قبلاً رزرو رو انجام می‌داد.
    """
    order = OrderConsultation(
        shop_bot_id=shop_bot_id,
        customer_id=customer_id,
        type=order_type,
        summary=summary,
        estimated_value_toman=estimated_value_toman,
        product_id=product_id,
        quantity=quantity,
        customer_phone=customer_phone,
        customer_address=customer_address,
        status=OrderStatus.AWAITING_CUSTOMER_CONFIRMATION,
    )
    session.add(order)
    await session.flush()
    return order


async def get_awaiting_confirmation_for_customer(session: AsyncSession, order_id: int, customer_id: int) -> OrderConsultation | None:
    """
    مثلِ get_owned_by_id ولی برایِ مسیرهایی که order_id از callback_dataیِ خودِ
    مشتری میاد (دکمه‌های تاییدِ سفارش توی رباتِ فروشگاهی) — مالکیت رو با
    customer_id چک می‌کنه (نه shop_bot_id)، و فقط سفارش‌هایی که هنوز واقعاً
    منتظرِ همین تاییدن رو برمی‌گردونه؛ تا یه مشتری نتونه با حدسِ id، سفارشِ
    مشتریِ دیگه‌ای رو تایید/لغو کنه یا یه سفارشِ از‌قبل‌حل‌شده رو دوباره تغییر بده.
    """
    result = await session.execute(
        select(OrderConsultation).where(
            OrderConsultation.id == order_id,
            OrderConsultation.customer_id == customer_id,
            OrderConsultation.status == OrderStatus.AWAITING_CUSTOMER_CONFIRMATION,
        )
    )
    return result.scalar_one_or_none()


async def customer_confirm_order(session: AsyncSession, order: OrderConsultation) -> None:
    """
    خودِ مشتری صحتِ اطلاعاتِ تشخیص‌داده‌شده رو تایید کرد: سفارش از حالتِ کاندید
    خارج می‌شه و وارد چرخه‌ی عادیِ PENDING می‌شه (از همین‌جا به بعد، فروشگاه‌دار
    مثلِ قبل با دکمه‌ی «تایید/رد» تصمیم می‌گیره). رزروِ موجودی هم دقیقاً همینجا
    (نه زودتر، وقتِ تشخیصِ هوش مصنوعی) انجام می‌شه — الگوش عیناً از create_order
    گرفته شده، فقط جابه‌جا شده به بعدِ تاییدِ واقعیِ مشتری.
    """
    order.status = OrderStatus.PENDING

    if order.product_id is not None:
        product = await session.get(Product, order.product_id)
        if product is not None and product.stock_quantity is not None:
            qty = order.quantity or 1
            available = product.stock_quantity - product.reserved_quantity
            if available >= qty:
                admin_settings = await get_admin_settings(session)
                product.reserved_quantity += qty
                order.stock_reserved = True
                order.reservation_expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
                    minutes=admin_settings.order_reservation_minutes
                )

    await session.flush()


async def customer_cancel_order(session: AsyncSession, order: OrderConsultation) -> None:
    """
    مشتری گفته اطلاعاتِ تشخیص‌داده‌شده اشتباهه. چون هنوز رزروِ موجودی‌ای انجام
    نشده (create_order_awaiting_confirmation هیچ رزروی نمی‌کنه)، لغو کردن فقط
    یه تغییرِ status ه — چیزی برای آزادسازی نیست. فروشگاه‌دار اصلاً از وجودِ این
    کاندید خبردار نشده بود، پس نیازی به اطلاع‌رسانی هم نیست.
    """
    order.status = OrderStatus.CANCELLED
    await session.flush()


async def expire_stale_customer_confirmations(session: AsyncSession, minutes: int) -> list[OrderConsultation]:
    """
    کاندیدهایی که مشتری ظرفِ minutes دقیقه جوابِ تایید/لغو نداده رو خودکار لغو
    می‌کنه، تا برای همیشه توی حالتِ نامشخص نمونن. برای اجرای دوره‌ای توسطِ
    زمان‌بند، کنارِ expire_stale_reservations (order_expiry_service.py).
    """
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=minutes)
    result = await session.execute(
        select(OrderConsultation).where(
            OrderConsultation.status == OrderStatus.AWAITING_CUSTOMER_CONFIRMATION,
            OrderConsultation.created_at < cutoff,
        )
    )
    stale = list(result.scalars().all())
    for order in stale:
        order.status = OrderStatus.CANCELLED
    if stale:
        await session.flush()
    return stale


async def get_by_id(session: AsyncSession, order_id: int) -> OrderConsultation | None:
    return await session.get(OrderConsultation, order_id)


async def get_by_bale_payload(session: AsyncSession, payload: str) -> OrderConsultation | None:
    """برایِ وب‌هوکِ بله‌پی (main.py): پیداکردنِ سفارشی که این payload برایِ
    پرداختِ آنلاینش ساخته شده. مشابهِ payment_service.get_by_bale_payload،
    ولی رویِ جدولِ سفارش‌ها به‌جایِ جدولِ پرداخت‌هایِ فروشگاه‌دار — این دو
    مکانیزم کاملاً جدا هستن (پیشوندِ payload هم فرق داره: 'order-' در برابرِ
    'payment-')."""
    result = await session.execute(select(OrderConsultation).where(OrderConsultation.bale_invoice_payload == payload))
    return result.scalar_one_or_none()


async def get_by_cart_checkout_group(
    session: AsyncSession, group_id: str, shop_bot_id: int | None = None, *, lock: bool = False
) -> list[OrderConsultation]:
    """همه‌ی سفارش‌هایِ حاصل از یه چک‌اوتِ سبدِ خریدِ مشخص (سبد، فازِ ۳) — برایِ
    تاییدِ گروهیِ فروشگاه‌دار و پرداختِ آنلاینِ گروهی. shop_bot_id اختیاریه:
    مسیرهایی که از دستِ یه فروشگاه‌دار میان (panel.py) حتماً پاسش می‌دن، تا
    فروشگاه‌دار نتونه با حدس‌زدنِ group_id، سفارشِ فروشگاهِ دیگه‌ای رو تایید/رد
    کنه (همون الگویِ get_owned_by_id)؛ مسیرِ وب‌هوکِ پرداخت (main.py) نیازی
    بهش نداره چون خودِ payload + استعلامِ مستقل از بله، مرجعِ اعتباره."""
    query = select(OrderConsultation).where(OrderConsultation.cart_checkout_group_id == group_id)
    if shop_bot_id is not None:
        query = query.where(OrderConsultation.shop_bot_id == shop_bot_id)
    if lock:
        # B10: قفلِ ردیف‌ها + خوانشِ تازه (populate_existing)، تا وب‌هوکِ هم‌زمان/تکراری یا getUpdates بعد از commit برنده، وضعیتِ نهایی رو ببینه
        query = query.order_by(OrderConsultation.id).with_for_update().execution_options(populate_existing=True)
    result = await session.execute(query)
    return list(result.scalars().all())


async def lock_order(session: AsyncSession, order_id: int) -> OrderConsultation | None:
    """B10: خوانشِ یک سفارش با قفلِ ردیف (FOR UPDATE) و داده‌یِ تازه."""
    result = await session.execute(
        select(OrderConsultation).where(OrderConsultation.id == order_id).with_for_update().execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


async def bale_transaction_used_elsewhere(session: AsyncSession, transaction_id: str, exclude_ids: list[int]) -> bool:
    """B10: آیا همین شناسه‌یِ تراکنشِ بله روی سفارشی *بیرون از* این گروه/سفارش ثبت شده؟ (بازپخشِ تراکنشِ یک پرداخت برایِ سفارشِ دیگر)"""
    query = select(func.count()).select_from(OrderConsultation).where(OrderConsultation.bale_transaction_id == transaction_id)
    if exclude_ids:
        query = query.where(OrderConsultation.id.notin_(exclude_ids))
    return bool((await session.execute(query)).scalar_one())


async def mark_bale_paid(session: AsyncSession, order: OrderConsultation, transaction_id: str) -> None:
    """فقط وضعیتِ پرداختِ آنلاین رو ثبت می‌کنه — status سفارش دست‌نخورده
    می‌مونه (فروشگاه‌دار همچنان از همون مسیرِ همیشگی، سفارش رو تایید/پردازش
    می‌کنه؛ فقط حالا می‌دونه از قبل پول رو گرفته)."""
    order.bale_transaction_id = transaction_id
    order.bale_paid_at = datetime.datetime.now(datetime.timezone.utc)
    await session.flush()


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
    نکته (بازطراحیِ سفارش‌گیری): این تابع فقط برایِ سفارش‌هاییه که از قبل واردِ
    چرخه‌ی عادی (PENDING به بعد) شدن. سفارش‌های کاندیدی که هنوز خودِ مشتری
    تاییدشون نکرده (AWAITING_CUSTOMER_CONFIRMATION) عمداً پایین‌تر رد می‌شن —
    فروشگاه‌دار نباید بتونه زودتر از خودِ مشتری یه کاندید رو قطعی کنه.
    سفارش رو تاییدشده علامت می‌زنه و اگه به یه محصولِ موجودی‌دار وصل باشه،
    از تعدادِ موجودیش کم می‌کنه (اگه رزروی داشت، رزرو به کسرِ قطعی تبدیل
    می‌شه؛ اگه رزرو نداشت — مثلاً منقضی شده بود — بازم مستقیم کم می‌شه، چون
    فروشگاه‌دار یه انسانِ قابل‌اعتماده که داره دستی تایید می‌کنه). اگه از قبل
    تاییدشده بود، False برمی‌گردونه (برای جلوگیری از کسرِ دوباره‌ی موجودی با
    چندبار زدنِ دکمه).
    """
    if order.status == OrderStatus.AWAITING_CUSTOMER_CONFIRMATION:
        return False
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


# سفارش‌هایِ «باز» = هنوز به نتیجه‌یِ نهایی نرسیده‌ن؛ تا وقتی هستن تغییرِ مودِ کسب‌وکار مسدوده (A3، قاعده‌یِ ۸).
# مرجعِ مجموعه‌هایِ وضعیت (فهرستِ ۶-۱ در PROGRESS): P1-S4/S5 مقدارهایِ تازه (awaiting_payment، receipt_submitted،
# paid) رو همین‌جا اضافه می‌کنه.
OPEN_ORDER_STATUS_VALUES = tuple(v for v in order_state.DISPLAY_ORDER if v in order_state.OPEN)


async def count_open_orders(session: AsyncSession, shop_bot_id: int) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(OrderConsultation)
        .where(OrderConsultation.shop_bot_id == shop_bot_id, OrderConsultation.status.in_(OPEN_ORDER_STATUS_VALUES))
    )
    return result.scalar_one()
