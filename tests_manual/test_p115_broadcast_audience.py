"""پ۱۱۵ · برابریِ مخاطبِ «پیام به بخش» در دو مود + احترامِ جدی به فهرستِ «جواب نده».

چرا این فایل هست (REMAINING_ISSUES.md §پ۶۶، مواردِ ۱ و ۲):
۱. نسخهٔ فروشگاهی شمارش را با مخاطبِ بلاک‌شده می‌گرفت و نسخهٔ مشاوره‌ای نه ⇒ فروشگاه‌دار عددی
   می‌دید که با تعدادِ واقعیِ گیرنده‌ها فرق داشت.
۲. سقفِ ۲۰۰۰ نفر فقط در مشاوره بود و اخطارش هم فقط همان‌جا نوشته می‌شد.

تصمیمِ فاز: «بلاک» یعنی **هیچ پیامِ فعالی از این فروشگاه نه** (پاسخِ خودکار به پیامِ خودِ کاربر
چیزِ دیگری است و دست‌نخورده). چون «همه»، «بخش»، «کمپین» و «زمان‌بندی‌شده» همه از
`customer_service.recipients_by_shop_bot` / `recipients_by_ids` می‌گذرند، فیلتر همان‌جا نشسته است.

ادعاها:
۱. هر دو حل‌کنندهٔ گیرنده، مخاطبِ بلاک‌شده را بیرون می‌گذارند (با شناسه و بدونِ شناسه).
۲. `audience_for_segment` همان چیزی را می‌شمارد که ارسال می‌کند: (شناسه‌ها، تعدادِ کل، بریده‌شدن).
۳. پیامِ «این بخش N نفر دارد» در مودِ فروشگاهی دقیقاً N گیرنده دارد (نه N+بلاک‌شده).
۴. با سقفِ کوچک‌شده، هر دو مود **همان** جملهٔ اخطار را می‌گیرند و فهرستشان دقیقاً به همان اندازه است.
۵. در مودِ مشاوره‌ای هم شمارش، بلاک‌شده را نمی‌شمارد (رفتارِ پ۶۶ حفظ شد).

اجرا: python3 tests_manual/run_one.py test_p115_broadcast_audience.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from sqlalchemy import select  # noqa: E402

from harness import build_test_dispatchers, reset_database  # noqa: E402
from phase4_helpers import Chat, add_customer  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot import texts  # noqa: E402
from app.database.models import Customer, ShopBot, TenantMode  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import crm_service, customer_service  # noqa: E402

OWNER_TG = 11_500_001
SHOP_TG = 11_500_002
CONSULT_OWNER_TG = 11_500_011
CONSULT_SHOP_TG = 11_500_012
BLOCKED_TG = 11_500_021

main_dp = None


async def _seed_shop(mode: str, owner_tg: int, shop_tg: int, *, plain: int = 0, blocked: int = 0) -> int:
    """فروشگاه با mودِ خواسته‌شده + n مشتریِ عادی + k مشتریِ بلاک‌شده (همه در یکِ بازهٔ زمانی)."""
    shop_bot_id = await seed_usable_shop(owner_tg, shop_tg)
    blocked_ids = []
    for index in range(plain):
        await add_customer(shop_bot_id, 11_500_300 + index)
    for index in range(blocked):
        blocked_ids.append(await add_customer(shop_bot_id, BLOCKED_TG + index))
    async with session_scope() as session:
        shop = await session.get(ShopBot, shop_bot_id)
        shop.tenant_mode = mode
        rows = (await session.execute(select(Customer).where(Customer.id.in_(blocked_ids)))).scalars().all()
        for customer in rows:
            customer.is_blocked = True
        await session.commit()
    return shop_bot_id


async def _segment_with_members(shop_bot_id: int, exclude_blocked: bool) -> tuple[str, int]:
    async with session_scope() as session:
        stats, _ = await crm_service.load_stats(session, shop_bot_id, exclude_blocked=exclude_blocked)
    parts = crm_service.partition(stats)
    for key, members in parts.items():
        if len(members) >= 2:
            return key, len(members)
    raise AssertionError(f"بخشی با دو عضو پیدا نشد: { {k: len(v) for k, v in parts.items()} }")


async def test_resolvers_skip_blocked() -> None:
    shop_bot_id = await _seed_shop("sales", OWNER_TG, SHOP_TG, plain=2, blocked=1)
    async with session_scope() as session:
        everyone = await customer_service.recipients_by_shop_bot(session, shop_bot_id)
        rows = (
            await session.execute(
                select(Customer.id, Customer.telegram_id).where(Customer.shop_bot_id == shop_bot_id)
            )
        ).all()
        by_ids = await customer_service.recipients_by_ids(session, shop_bot_id, [int(r[0]) for r in rows])
    assert len(everyone) == 2, everyone
    assert len(by_ids) == 2, by_ids
    assert BLOCKED_TG not in {chat_id for chat_id, _ in everyone}, "مخاطبِ بلاک‌شده در «همه» نباید باشد"
    assert BLOCKED_TG not in {chat_id for chat_id, _ in by_ids}, "مخاطبِ بلاک‌شده در «بخش» نباید باشد"
    print("✅ test_resolvers_skip_blocked PASSED")


async def test_audience_for_segment_matches_send_list() -> None:
    shop_bot_id = await _seed_shop("sales", OWNER_TG + 1, SHOP_TG + 1, plain=3, blocked=2)
    segment, _ = await _segment_with_members(shop_bot_id, exclude_blocked=False)
    async with session_scope() as session:
        ids, total, truncated = await crm_service.audience_for_segment(session, shop_bot_id, segment)
        sendable = await customer_service.recipients_by_ids(session, shop_bot_id, ids)
    assert truncated is False, (total, len(ids))
    assert len(ids) == len(sendable), (ids, sendable)
    assert total >= len(ids)
    print(f"✅ test_audience_for_segment_matches_send_list PASSED (بخشِ {segment} · {len(ids)} گیرنده)")


async def test_sales_ask_message_count_equals_recipients() -> None:
    shop_bot_id = await _seed_shop("sales", OWNER_TG + 2, SHOP_TG + 2, plain=2, blocked=1)
    segment, _ = await _segment_with_members(shop_bot_id, exclude_blocked=False)
    owner = Chat(main_dp, OWNER_TG + 2)
    await owner.say("👥 مشتری‌ها")
    await owner.tap(f"crm_bcast:{segment}")
    body = owner.last_text or ""
    expected = texts.crm_broadcast_ask(texts.CRM_SEGMENT_LABELS[segment], 2)
    assert body == expected, f"شمارشِ پیام باید فقط غیربلاک‌ها را بگوید:\nدیده: {body!r}\nانتظار: {expected!r}"
    assert "⚠️" not in body, "با سه نفر نباید اخطارِ سقف بیاید"
    print("✅ test_sales_ask_message_count_equals_recipients PASSED")


async def test_both_modes_share_cap_and_warning() -> None:
    saved_limit = crm_service.AUDIENCE_LIMIT
    try:
        crm_service.AUDIENCE_LIMIT = 2
        sales_shop = await _seed_shop("sales", OWNER_TG + 3, SHOP_TG + 3, plain=3, blocked=0)
        consult_shop = await _seed_shop(TenantMode.CONSULTATION.value, CONSULT_OWNER_TG, CONSULT_SHOP_TG, plain=3)
        segment, total = await _segment_with_members(sales_shop, exclude_blocked=True)

        async with session_scope() as session:
            sales_ids, sales_total, sales_truncated = await crm_service.audience_for_segment(session, sales_shop, segment)
        assert sales_truncated and len(sales_ids) == 2, (sales_ids, sales_total)

        owner = Chat(main_dp, OWNER_TG + 3)
        await owner.say("👥 مشتری‌ها")
        await owner.tap(f"crm_bcast:{segment}")
        sales_note = texts.audience_truncated_note(2, total)
        assert sales_note in (owner.last_text or ""), owner.last_text

        consult_segment, consult_total = await _segment_with_members(consult_shop, exclude_blocked=True)
        consultant = Chat(main_dp, CONSULT_OWNER_TG)
        await consultant.say("💬 گفتگوها و کاربران")
        await consultant.tap("cret_open")
        await consultant.tap(f"cret_seg:{consult_segment}")
        assert texts.audience_truncated_note(2, consult_total) in (consultant.last_text or ""), consultant.last_text
    finally:
        crm_service.AUDIENCE_LIMIT = saved_limit
    print("✅ test_both_modes_share_cap_and_warning PASSED")


async def test_consult_still_excludes_blocked() -> None:
    consult_shop = await _seed_shop(TenantMode.CONSULTATION.value, CONSULT_OWNER_TG + 1, CONSULT_SHOP_TG + 1, plain=2, blocked=1)
    segment, _ = await _segment_with_members(consult_shop, exclude_blocked=False)
    async with session_scope() as session:
        ids, _total, _ = await crm_service.audience_for_segment(session, consult_shop, segment)
        sendable = await customer_service.recipients_by_ids(session, consult_shop, ids)
    assert BLOCKED_TG not in {chat_id for chat_id, _ in sendable}, "پ۶۶ نباید برگردد"
    print("✅ test_consult_still_excludes_blocked PASSED")


async def main() -> None:
    global main_dp
    await reset_database()
    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    await test_resolvers_skip_blocked()
    await test_audience_for_segment_matches_send_list()
    await test_sales_ask_message_count_equals_recipients()
    await test_both_modes_share_cap_and_warning()
    await test_consult_still_excludes_blocked()
    await asyncio.sleep(0)


if __name__ == "__main__":
    asyncio.run(main())
