"""دفترچه‌آدرسِ مشتری (W5 · C3). هر مشتری در هر فروشگاه (Customer خودش per-shop است) حداکثر
`MAX_ADDRESSES` آدرس دارد؛ حداکثر یکی پیش‌فرض. هیچ commit ی اینجا نیست (فراخوان/میدل‌ور commit می‌کنه)؛
همه‌ی دسترسی‌ها با `customer_id` فیلتر می‌شن ⇒ نشتِ بینِ مشتری‌ها/فروشگاه‌ها ندارد."""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import CustomerAddress

MAX_ADDRESSES = 5


async def list_addresses(session: AsyncSession, customer_id: int) -> list[CustomerAddress]:
    """پیش‌فرض اول، بعد تازه‌ترین‌ها."""
    result = await session.execute(
        select(CustomerAddress)
        .where(CustomerAddress.customer_id == customer_id)
        .order_by(CustomerAddress.is_default.desc(), CustomerAddress.id.desc())
    )
    return list(result.scalars().all())


async def get_owned(session: AsyncSession, address_id: int, customer_id: int) -> CustomerAddress | None:
    result = await session.execute(
        select(CustomerAddress).where(CustomerAddress.id == address_id, CustomerAddress.customer_id == customer_id)
    )
    return result.scalar_one_or_none()


async def add_address(
    session: AsyncSession,
    customer_id: int,
    *,
    province: str | None,
    city: str | None,
    address: str,
    postal_code: str | None,
    label: str | None = None,
) -> CustomerAddress | None:
    """None وقتی سقفِ `MAX_ADDRESSES` پر باشه. اولین آدرسِ مشتری خودکار پیش‌فرض می‌شه."""
    existing = await list_addresses(session, customer_id)
    if len(existing) >= MAX_ADDRESSES:
        return None
    row = CustomerAddress(
        customer_id=customer_id,
        label=(label or city or "")[:64] or None,
        province=province[:64] if province else None,
        city=city[:64] if city else None,
        address=address,
        postal_code=postal_code,
        is_default=not existing,
    )
    session.add(row)
    await session.flush()
    return row


async def set_default(session: AsyncSession, customer_id: int, address_id: int) -> bool:
    """آدرس رو پیش‌فرض می‌کنه (بقیه غیرپیش‌فرض). آدرسِ غیرِ‌متعلق به مشتری ⇒ False و بدونِ اثر."""
    if await get_owned(session, address_id, customer_id) is None:
        return False
    await session.execute(
        update(CustomerAddress).where(CustomerAddress.customer_id == customer_id).values(is_default=False)
    )
    await session.execute(
        update(CustomerAddress)
        .where(CustomerAddress.customer_id == customer_id, CustomerAddress.id == address_id)
        .values(is_default=True)
    )
    return True


async def delete_address(session: AsyncSession, customer_id: int, address_id: int) -> bool:
    """حذف. اگه پیش‌فرض بود، تازه‌ترینِ باقی‌مانده پیش‌فرض می‌شه. متعلق به دیگری ⇒ False."""
    row = await get_owned(session, address_id, customer_id)
    if row is None:
        return False
    was_default = row.is_default
    await session.delete(row)
    await session.flush()
    if was_default:
        remaining = await list_addresses(session, customer_id)
        if remaining:
            await set_default(session, customer_id, remaining[0].id)
    return True


def format_address(row: CustomerAddress) -> str:
    """متنِ تک‌خطیِ خوانا برایِ نمایش/ذخیره روی سفارش: «استان، شهر، آدرس (کدپستی …)»."""
    parts = [p for p in (row.province, row.city) if p]
    head = "، ".join(parts)
    body = (row.address or "").replace("\n", "، ")
    text = f"{head}، {body}" if head else body
    if row.postal_code:
        text += f" (کدپستی {row.postal_code})"
    return text


def short_label(row: CustomerAddress) -> str:
    """برچسبِ کوتاهِ دکمه (≤ ۴۰ نویسه)."""
    base = row.label or row.city or "آدرس"
    star = "⭐ " if row.is_default else ""
    return (star + f"{base} — {(row.address or '')[:20]}")[:40]
