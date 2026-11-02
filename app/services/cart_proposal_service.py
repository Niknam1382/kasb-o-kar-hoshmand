"""پیشنهادِ ویرایشِ سبد با AI + تاییدِ یک‌ضربه‌ای (W5 · C2). AI هیچ‌وقت سبد رو مستقیم عوض نمی‌کنه:
عملیاتِ اعتبارسنجی‌شده در `cart_ai_proposals` ذخیره می‌شه و فقط با دکمه‌یِ «✅ اعمال» (یک‌بارمصرف، ۱۰ دقیقه، با
اثرانگشتِ سبد) اجرا می‌شه. `claim` اتمی است (UPDATE … WHERE used=false) ⇒ دابل‌تپ = یک اثر."""

from __future__ import annotations

import datetime
import json
from typing import Iterable

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import CartAiProposal
from app.services import cart_edit_service
from app.services.cart_edit_service import CartOperation
from app.utils.validators import fa_number

PROPOSAL_TTL_MINUTES = 10

CLAIM_OK = "ok"
CLAIM_NOT_FOUND = "not_found"
CLAIM_ALREADY_USED = "already_used"
CLAIM_EXPIRED = "expired"

_APPLICABLE_ACTIONS = tuple(a for a in cart_edit_service.ACTIONS if a != "clear")


def serialize_ops(operations: Iterable[CartOperation]) -> str:
    return json.dumps(
        [{"a": op.action, "p": op.product_id, "q": op.quantity} for op in operations if op.action != "clear"],
        ensure_ascii=False,
    )


def deserialize_ops(raw: str | None) -> list[CartOperation]:
    """بازخوانیِ دوباره‌اعتبارسنجی‌شده (دیتابیس هم قابلِ اعتماد نیست): فقط action/شناسه/تعدادِ معتبر."""
    try:
        data = json.loads(raw or "[]")
    except (TypeError, ValueError):
        return []
    result: list[CartOperation] = []
    if not isinstance(data, list):
        return []
    for entry in data[: cart_edit_service.MAX_OPERATIONS]:
        if not isinstance(entry, dict):
            continue
        action, product_id, quantity = entry.get("a"), entry.get("p"), entry.get("q")
        if action not in _APPLICABLE_ACTIONS or not isinstance(product_id, int) or isinstance(product_id, bool):
            continue
        if quantity is not None and (
            not isinstance(quantity, int) or isinstance(quantity, bool) or not (1 <= quantity <= cart_edit_service.MAX_QUANTITY)
        ):
            continue
        result.append(CartOperation(action=action, product_id=product_id, quantity=quantity))
    return result


def describe_op(operation: CartOperation, product_name: str) -> str:
    """یک خطِ خوانا برایِ پیشنهاد (بدونِ ادعایِ «انجام شد»)."""
    name = f"«{product_name}»"
    qty = operation.quantity or 1
    if operation.action == "add":
        return f"➕ {name}: {fa_number(qty)} عدد اضافه بشه"
    if operation.action == "decrease":
        return f"➖ {name}: {fa_number(qty)} عدد کم بشه"
    if operation.action == "set":
        return f"🔢 {name}: تعداد بشه {qty}"
    return f"🗑 {name}: از سبد حذف بشه"


async def supersede_open(session: AsyncSession, cart_id: int) -> None:
    """پیشنهادهایِ بازِ قبلیِ همین سبد از رده خارج می‌شن (فقط آخرین پیشنهاد قابلِ اعمال است)."""
    await session.execute(
        update(CartAiProposal).where(CartAiProposal.cart_id == cart_id, CartAiProposal.used.is_(False)).values(used=True)
    )


async def create(session: AsyncSession, cart_id: int, operations: list[CartOperation], fingerprint: str) -> CartAiProposal:
    await supersede_open(session, cart_id)
    row = CartAiProposal(cart_id=cart_id, ops_json=serialize_ops(operations), fingerprint=fingerprint[:16], used=False)
    session.add(row)
    await session.flush()
    return row


async def claim(
    session: AsyncSession, proposal_id: int, cart_id: int, *, now: datetime.datetime | None = None
) -> tuple[str, CartAiProposal | None]:
    """(وضعیت, ردیف). اتمی: فقط اولین تماس CLAIM_OK می‌گیره؛ بعدی‌ها CLAIM_ALREADY_USED.
    منقضی‌شده هم «مصرف» می‌شه (دکمه‌یِ کهنه دوباره کار نکنه) و CLAIM_EXPIRED برمی‌گرده."""
    result = await session.execute(
        update(CartAiProposal)
        .where(CartAiProposal.id == proposal_id, CartAiProposal.cart_id == cart_id, CartAiProposal.used.is_(False))
        .values(used=True)
        .returning(CartAiProposal.id)
    )
    claimed = result.first() is not None
    row = (
        await session.execute(
            select(CartAiProposal)
            .where(CartAiProposal.id == proposal_id, CartAiProposal.cart_id == cart_id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if row is None:
        return CLAIM_NOT_FOUND, None
    if not claimed:
        return CLAIM_ALREADY_USED, row
    now = now or datetime.datetime.now(datetime.timezone.utc)
    created = row.created_at
    if created is not None and created.tzinfo is None:
        created = created.replace(tzinfo=datetime.timezone.utc)
    if created is not None and now - created > datetime.timedelta(minutes=PROPOSAL_TTL_MINUTES):
        return CLAIM_EXPIRED, row
    return CLAIM_OK, row


async def reject(session: AsyncSession, proposal_id: int, cart_id: int) -> bool:
    """ردِ پیشنهاد (idempotent). True فقط اگه همین تماس مصرفش کرد."""
    result = await session.execute(
        update(CartAiProposal)
        .where(CartAiProposal.id == proposal_id, CartAiProposal.cart_id == cart_id, CartAiProposal.used.is_(False))
        .values(used=True)
        .returning(CartAiProposal.id)
    )
    return result.first() is not None
