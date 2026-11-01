"""گذارِ وضعیتِ سفارش در سطحِ «گروه» (C4/C9).

واحدِ وضعیت = گروهِ چک‌اوت (`cart_checkout_group_id`)؛ سفارشِ تک‌محصولی = گروهِ یک‌ردیفی.
همه‌یِ گذارهایِ تازه (پرداخت/پردازش/ارسال/تکمیل/ردّ/استرداد/لغو) از `transition_group`
می‌گذرند: قفلِ سطری (`FOR UPDATE`) ← اعتبارسنجیِ گذار با `order_state` ← اثرِ رزرو ←
یک ردیفِ `order_events`. فراخوانیِ دوباره با همان مقصد بی‌اثر است (ایدمپوتنت).

این سرویس **هیچ پیامی نمی‌فرستد** و commit نمی‌کند؛ فراخوان (هندلر) بعد از commit به
مشتری/فروشگاه‌دار اطلاع می‌دهد (اعلان‌ها بعد از commit).
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import OrderConsultation, OrderEvent, OrderStatus, Product, ShopBot
from app.services import admin_settings_service, commission_service, order_state


async def apply_commission(session: AsyncSession, rows: list[OrderConsultation], to: str) -> None:
    """
    PHASE 5D — چرخهٔ عمرِ کمیسیون در تنها نقطهٔ گذارِ گروه:

    ورود به جریانِ پرداخت (`awaiting_payment` / `receipt_submitted`) ← رزرو
    تاییدِ پرداخت (`paid`)                                            ← تسویه
    رد/انقضا/لغو                                                     ← آزادسازیِ رزرو
    استرداد (`refunded`)                                             ← برگشتِ گرفته‌شده یا آزادسازی

    مسیرِ چک‌اوت که ردیف‌ها را مستقیم در `awaiting_payment` می‌سازد هم همین تابع را صدا
    می‌زند (چون `transition_group` آنجا اجرا نمی‌شود). کمیسیون خاموش ⇒ همه‌یِ تابع‌ها
    بی‌اثرند. این تابع commit نمی‌کند؛ با گذارِ وضعیت در همان transaction می‌آید یا هیچ‌کدام.
    """
    if not rows:
        return
    owner_id = (
        await session.execute(select(ShopBot.shop_owner_id).where(ShopBot.id == rows[0].shop_bot_id))
    ).scalar_one_or_none()
    if owner_id is None:
        return
    admin_settings = await admin_settings_service.get_admin_settings(session)
    key = group_key(rows[0])

    if to in (order_state.AWAITING_PAYMENT, order_state.RECEIPT_SUBMITTED):
        await commission_service.reserve(
            session, owner_id=owner_id, group_key=key, rows=rows, admin_settings=admin_settings
        )
    elif to == order_state.PAID:
        await commission_service.settle(
            session, owner_id=owner_id, group_key=key, rows=rows, admin_settings=admin_settings
        )
    elif to == order_state.REFUNDED:
        reversed_result = await commission_service.reverse(session, owner_id=owner_id, group_key=key, rows=rows)
        if not reversed_result.changed:
            await commission_service.release(session, owner_id=owner_id, group_key=key, rows=rows)
    elif to in order_state.RELEASES_RESERVATION:
        await commission_service.release(session, owner_id=owner_id, group_key=key, rows=rows)


@dataclass
class TransitionResult:
    ok: bool
    changed: bool = False
    reason: str | None = None  # illegal | empty
    rows: list[OrderConsultation] = field(default_factory=list)
    from_status: str | None = None
    to_status: str | None = None


def group_key(order: OrderConsultation) -> str:
    """کلیدِ پایدارِ گروه برایِ نمایش/فاکتور (تک‌محصولی: o{id})."""
    return order.cart_checkout_group_id or f"o{order.id}"


async def get_group_rows(session: AsyncSession, order: OrderConsultation, *, lock: bool = True) -> list[OrderConsultation]:
    """همه‌یِ ردیف‌هایِ گروهِ این سفارش (با قفلِ سطری و داده‌یِ تازه از DB وقتی lock=True)."""
    query = select(OrderConsultation)
    if order.cart_checkout_group_id:
        query = query.where(
            OrderConsultation.cart_checkout_group_id == order.cart_checkout_group_id,
            OrderConsultation.shop_bot_id == order.shop_bot_id,
        )
    else:
        query = query.where(OrderConsultation.id == order.id)
    query = query.order_by(OrderConsultation.id)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    result = await session.execute(query)
    return list(result.scalars().all())


async def record_event(
    session: AsyncSession,
    order: OrderConsultation,
    from_status,
    to_status,
    *,
    actor_type: str = "system",
    actor_ref: str | None = None,
    reason: str | None = None,
) -> OrderEvent:
    event = OrderEvent(
        order_id=order.id,
        group_id=order.cart_checkout_group_id,
        from_status=order_state.value_of(from_status) if from_status is not None else None,
        to_status=order_state.value_of(to_status),
        actor_type=actor_type if actor_type in order_state.ACTOR_TYPES else "system",
        actor_ref=(actor_ref or None) and str(actor_ref)[:64],
        reason=(reason or None) and reason[:1000],
    )
    session.add(event)
    await session.flush()
    return event


async def _release_reservation(session: AsyncSession, row: OrderConsultation) -> None:
    if not row.stock_reserved:
        return
    if row.product_id is not None:
        product = await session.get(Product, row.product_id)
        if product is not None:
            product.reserved_quantity = max(0, product.reserved_quantity - (row.quantity or 1))
    row.stock_reserved = False


async def _consume_stock(session: AsyncSession, row: OrderConsultation) -> None:
    """مثلِ order_service.confirm_order: رزرو آزاد و موجودیِ واقعی کم می‌شود (فقط محصولِ موجودی‌دار)."""
    if row.product_id is not None:
        product = await session.get(Product, row.product_id)
        if product is not None and product.stock_quantity is not None:
            qty = row.quantity or 1
            if row.stock_reserved:
                product.reserved_quantity = max(0, product.reserved_quantity - qty)
            product.stock_quantity = max(0, product.stock_quantity - qty)
    row.stock_reserved = False


async def _apply_side_effects(
    session: AsyncSession,
    row: OrderConsultation,
    to: str,
    now: datetime.datetime,
    *,
    reason: str | None,
    tracking_code: str | None,
    carrier_name: str | None,
) -> None:
    if to in order_state.RELEASES_RESERVATION:
        await _release_reservation(session, row)
        if reason and to in (order_state.CANCELLED, order_state.REJECTED):
            row.cancel_reason = reason[:1000]
    elif to in (order_state.PAID, order_state.CONFIRMED):
        if not row.confirmed:
            await _consume_stock(session, row)
            row.confirmed = True
            row.confirmed_at = now
        if to == order_state.PAID and row.paid_at is None:
            row.paid_at = now
    elif to == order_state.SHIPPED:
        if tracking_code:
            row.tracking_code = tracking_code[:128]
        if carrier_name:
            row.carrier_name = carrier_name[:64]
    elif to == order_state.COMPLETED:
        if row.delivered_at is None:
            row.delivered_at = now
    elif to == order_state.REFUND_PENDING and reason:
        row.cancel_reason = reason[:1000]


async def transition_group(
    session: AsyncSession,
    order: OrderConsultation,
    to_status,
    *,
    actor_type: str = "system",
    actor_ref: str | None = None,
    reason: str | None = None,
    tracking_code: str | None = None,
    carrier_name: str | None = None,
) -> TransitionResult:
    """گذارِ اتمیِ کلِ گروه به `to_status`.

    - همه‌یِ ردیف‌ها قبلاً در مقصدند ⇒ `ok=True, changed=False` (ایدمپوتنت، بدونِ رویداد).
    - هر ردیفِ غیرمجاز ⇒ `ok=False, reason="illegal"` و هیچ ردیفی تغییر نمی‌کند.
    """
    to = order_state.value_of(to_status)
    rows = await get_group_rows(session, order, lock=True)
    if not rows:
        return TransitionResult(ok=False, reason="empty", to_status=to)

    current = [order_state.value_of(r.status) for r in rows]
    if all(c == to for c in current):
        return TransitionResult(ok=True, changed=False, rows=rows, from_status=to, to_status=to)

    movable = [r for r in rows if order_state.value_of(r.status) != to]
    for r in movable:
        if not order_state.can_transition(r.status, to):
            return TransitionResult(
                ok=False, reason="illegal", rows=rows, from_status=order_state.value_of(r.status), to_status=to
            )

    from_status = order_state.value_of(movable[0].status)
    now = datetime.datetime.now(datetime.timezone.utc)
    for r in movable:
        r.status = OrderStatus(to)
        await _apply_side_effects(
            session, r, to, now, reason=reason, tracking_code=tracking_code, carrier_name=carrier_name
        )
    await session.flush()
    await apply_commission(session, rows, to)  # PHASE 5D: رزرو/تسویه/آزادسازی/برگشتِ کمیسیون
    await record_event(session, rows[0], from_status, to, actor_type=actor_type, actor_ref=actor_ref, reason=reason)
    return TransitionResult(ok=True, changed=True, rows=rows, from_status=from_status, to_status=to)


async def reject_or_refund_group(
    session: AsyncSession,
    order: OrderConsultation,
    *,
    reason: str | None,
    actor_type: str = "owner",
    actor_ref: str | None = None,
) -> TransitionResult:
    """ردِ فروشگاه‌دار (C9): قبل از پرداخت ⇒ rejected؛ بعد از پرداخت/تایید ⇒ refund_pending؛ وگرنه illegal."""
    rows = await get_group_rows(session, order, lock=True)
    if not rows:
        return TransitionResult(ok=False, reason="empty")
    statuses = {order_state.value_of(r.status) for r in rows}
    if statuses <= {order_state.REJECTED, order_state.REFUND_PENDING}:
        # قبلاً رد شده (دابل‌تپ) — بی‌اثر
        return TransitionResult(ok=True, changed=False, rows=rows, from_status=next(iter(statuses)), to_status=next(iter(statuses)))
    if statuses <= order_state.REJECTABLE:
        target = order_state.REJECTED
    elif statuses <= order_state.REFUNDABLE:
        target = order_state.REFUND_PENDING
    else:
        return TransitionResult(ok=False, reason="illegal", rows=rows, from_status=sorted(statuses)[0])
    return await transition_group(
        session, rows[0], target, actor_type=actor_type, actor_ref=actor_ref, reason=reason
    )


async def customer_cancel_group(
    session: AsyncSession, order: OrderConsultation, *, customer_id: int, reason: str | None = None
) -> TransitionResult:
    """لغوِ مشتری — فقط قبل از پرداخت (awaiting_payment) و فقط سفارشِ خودش."""
    if order.customer_id != customer_id:
        return TransitionResult(ok=False, reason="illegal")
    rows = await get_group_rows(session, order, lock=True)
    if not rows or any(r.customer_id != customer_id for r in rows):
        return TransitionResult(ok=False, reason="illegal")
    if not all(order_state.value_of(r.status) in order_state.CUSTOMER_CANCELLABLE for r in rows):
        statuses = {order_state.value_of(r.status) for r in rows}
        if statuses == {order_state.CANCELLED}:
            return TransitionResult(ok=True, changed=False, rows=rows, from_status=order_state.CANCELLED, to_status=order_state.CANCELLED)
        return TransitionResult(ok=False, reason="illegal", rows=rows)
    return await transition_group(
        session, rows[0], order_state.CANCELLED, actor_type="customer", actor_ref=str(customer_id), reason=reason
    )


async def get_timeline(session: AsyncSession, order: OrderConsultation) -> list[OrderEvent]:
    """رویدادهایِ گروه/سفارش به ترتیبِ زمان (قدیمی‌ترین اول)."""
    if order.cart_checkout_group_id:
        cond = OrderEvent.group_id == order.cart_checkout_group_id
    else:
        cond = OrderEvent.order_id == order.id
    result = await session.execute(select(OrderEvent).where(cond).order_by(OrderEvent.id))
    return list(result.scalars().all())


async def list_groups_for_customer(
    session: AsyncSession, shop_bot_id: int, customer_id: int, *, limit: int = 5, offset: int = 0
) -> tuple[list[list[OrderConsultation]], int]:
    """گروه‌هایِ سفارشِ مشتری، تازه‌ترین اول (فقط type=order)، با صفحه‌بندی. برمی‌گرداند (گروه‌ها, کلِ گروه‌ها)."""
    from app.database.models import OrderType

    result = await session.execute(
        select(OrderConsultation)
        .where(
            OrderConsultation.shop_bot_id == shop_bot_id,
            OrderConsultation.customer_id == customer_id,
            OrderConsultation.type == OrderType.ORDER,
        )
        .order_by(OrderConsultation.id.desc())
    )
    all_rows = list(result.scalars().all())
    groups: dict[str, list[OrderConsultation]] = {}
    for r in all_rows:
        groups.setdefault(group_key(r), []).append(r)
    ordered = list(groups.values())  # دیکشنری به ترتیبِ اولین دیدن = تازه‌ترین اول
    total = len(ordered)
    page = ordered[offset : offset + limit]
    for g in page:
        g.sort(key=lambda x: x.id)
    return page, total


def group_total_toman(rows: list[OrderConsultation]) -> int:
    """جمعِ مبلغِ گروه = اقلام (بعد از تخفیف) + هزینه‌یِ ارسال (اگه ثبت شده)."""
    items = sum(r.estimated_value_toman or 0 for r in rows)
    shipping = max((r.shipping_fee_toman or 0) for r in rows) if rows else 0
    return items + shipping


async def restock_group(session: AsyncSession, rows: list[OrderConsultation]) -> int:
    """W5 · 2.2: بعد از «استرداد انجام شد» (گزینه‌یِ فروشگاه‌دار) موجودیِ اقلام به انبار برمی‌گرده؛ هر ردیف حداکثر یک‌بار
    (`restocked_at`) و فقط محصولِ موجودی‌دار. ردیف‌ها قفل می‌شن ⇒ دابل‌تپ اثرِ دوم ندارد. برمی‌گردونه چند ردیف برگشت خورد."""
    if not rows:
        return 0
    locked = (
        await session.execute(
            select(OrderConsultation)
            .where(OrderConsultation.id.in_([r.id for r in rows]))
            .order_by(OrderConsultation.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalars().all()
    restocked = 0
    for row in locked:
        if row.restocked_at is not None or order_state.value_of(row.status) != order_state.REFUNDED or row.product_id is None:
            continue
        product = await session.get(Product, row.product_id)
        if product is None or product.stock_quantity is None:
            continue
        product.stock_quantity += row.quantity or 1
        row.restocked_at = datetime.datetime.now(datetime.timezone.utc)
        restocked += 1
    if restocked:
        await session.flush()
    return restocked
