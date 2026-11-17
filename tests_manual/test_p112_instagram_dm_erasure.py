"""پ۱۱۲ · حقِ فراموشی رویِ دایرکتِ اینستاگرام + تمرینِ واقعیِ `alembic downgrade`

ادعاها:
۱. `direct_senders` فقط مخاطبانِ *همین* فروشگاه با پلتفرمِ اینستاگرام را می‌آورد، با شمارِ پیام‌ها،
   پُرمصام‌ها اول و با سقفِ فهرست — و هیچ متنِ گفتگویی در خروجی نیست.
۲. `erase_direct_sender_data` متنِ همهٔ پیام‌های *همان* مخاطب را پاک می‌کند، هویت و CRM را بی‌نام
   می‌کند، یکِ ردیفِ ممیزی از نوعِ `instagram_data_erased` می‌گذارد و به هیچ مشتریِ دیگری دست نمی‌زند.
۳. ردیفِ مشتری و سفارش‌هایش **می‌مانند** (زنجیرهٔ مالی نشکسته می‌شود) — این دقیقاً همان چیزی است که
   در متنِ صفحه به فروشگاه‌دار گفته می‌شود؛ پس باید با عدد ثابت شود.
۴. شناسهٔ مشتریِ فروشگاهِ دیگر یا پلتفرمِ دیگر ⇒ `not-found` و صفرِ حذف (دروازهٔ مالکیت).
۵. دکمهٔ تازه در کیبوردِ صفحه (فقط با اتصال)، کال‌بک‌هایش کوتاه‌تر از ۶۴ بایت و برچسبِ فارسیِ
   نوعِ ممیزیِ تازه ثبت شده (نگهبانِ پ۲۲).
۶. زنجیرهٔ مایگریشن تک‌هد است و رِویشنِ پ۱۰۹ `downgrade` دارد (تمرینِ واقعیِ آن در گزارشِ پ۱۱۲).

اجرا: python3 tests_manual/run_one.py test_p112_instagram_dm_erasure.py
"""
from __future__ import annotations

import asyncio
import pathlib
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from sqlalchemy import func, select  # noqa: E402

from app.bots.main_bot import keyboards, texts  # noqa: E402
from app.database.models import (  # noqa: E402
    AuditEventType,
    AuditLogEntry,
    ConversationMessage,
    Customer,
    InstagramAccount,
    OrderConsultation,
    OrderStatus,
    OrderType,
)
from app.database.session import session_scope  # noqa: E402
from app.services import customer_service, instagram_service, platform_service  # noqa: E402
from harness import reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

OWNER_A = 11_120_000_001
BOT_A = 11_120_000_002
OWNER_B = 11_120_000_011
BOT_B = 11_120_000_012
IG_ID = 11_120_000_101
IG_ID_2 = 11_120_000_102
TG_ID = 11_120_000_103

ACTOR = 11_120_000_999


async def _seed() -> dict:
    await reset_database()
    shop_a = await seed_usable_shop(OWNER_A, BOT_A)
    shop_b = await seed_usable_shop(OWNER_B, BOT_B)
    async with session_scope() as session:
        session.add(
            InstagramAccount(
                shop_bot_id=shop_a,
                ig_account_id="1784100000000001",
                ig_username="shopfirst",
                access_token="ig-token-placeholder-value",
            )
        )
        first = await customer_service.get_or_create_customer(
            session, shop_a, IG_ID, "سارا", "sara.test", platform=platform_service.INSTAGRAM
        )
        second = await customer_service.get_or_create_customer(
            session, shop_a, IG_ID_2, "کاوه", "kaveh", platform=platform_service.INSTAGRAM
        )
        telegram_customer = await customer_service.get_or_create_customer(
            session, shop_a, TG_ID, "مشتریِ تلگرام", "tg_buyer"
        )
        other_shop_customer = await customer_service.get_or_create_customer(
            session, shop_b, IG_ID, "دزد", "thief", platform=platform_service.INSTAGRAM
        )
        first_id, second_id, telegram_id, other_id = (
            first.id,
            second.id,
            telegram_customer.id,
            other_shop_customer.id,
        )
        for customer_id, count in ((first_id, 3), (second_id, 1), (telegram_id, 5), (other_id, 4)):
            for index in range(count):
                session.add(
                    ConversationMessage(
                        customer_id=customer_id, role="user", content=f"سلامِ شماره {index} با شمارهٔ ۰۹۱۲"
                    )
                )
        first.crm_notes = "یادداشتِ داخلی: قراردادِ بزرگ"
        first.crm_tags = "ویژه,قدیمی"
        first.phone_number = "+989120000000"
        order = OrderConsultation(
            shop_bot_id=shop_a,
            customer_id=first_id,
            type=OrderType.ORDER,
            summary="سفارشِ قدیمی",
            status=OrderStatus.COMPLETED,
            confirmed=True,
            estimated_value_toman=250_000,
        )
        session.add(order)
        await session.flush()
        order_id = order.id
        await session.commit()
    return {
        "shop_a": shop_a,
        "shop_b": shop_b,
        "first": first_id,
        "second": second_id,
        "telegram": telegram_id,
        "other": other_id,
        "order": order_id,
    }


async def _message_count(customer_id: int) -> int:
    async with session_scope() as session:
        return int(
            (
                await session.execute(
                    select(func.count()).select_from(ConversationMessage).where(
                        ConversationMessage.customer_id == customer_id
                    )
                )
            ).scalar_one()
        )


async def _audit_count() -> int:
    async with session_scope() as session:
        return int(
            (
                await session.execute(
                    select(func.count()).select_from(AuditLogEntry).where(
                        AuditLogEntry.event_type == AuditEventType.INSTAGRAM_DATA_ERASED
                    )
                )
            ).scalar_one()
        )


# ============================================================================= ۱
async def test_direct_senders_lists_only_instagram_customers_of_this_shop() -> None:
    ids = await _seed()
    async with session_scope() as session:
        rows = await instagram_service.direct_senders(session, ids["shop_a"], limit=10)
    labels = {row["id"] for row in rows}
    assert ids["first"] in labels and ids["second"] in labels, rows
    assert ids["telegram"] not in labels, "مشتریِ تلگرامی نباید در فهرستِ دایرکت باشد"
    assert ids["other"] not in labels, "مشتریِ فروشگاهِ دیگر نباید دیده شود"
    counts = {row["id"]: row["messages"] for row in rows}
    assert counts[ids["first"]] == 3 and counts[ids["second"]] == 1, counts
    assert [row["messages"] for row in rows] == sorted((row["messages"] for row in rows), reverse=True), rows
    assert all("سلامِ شماره" not in str(row) for row in rows), "متنِ گفتگو نباید در این فهرست باشد"
    async with session_scope() as session:
        one = await instagram_service.direct_senders(session, ids["shop_a"], limit=1)
    assert len(one) == 1, one
    print("PASS test_direct_senders_lists_only_instagram_customers_of_this_shop")


# ============================================================================= ۲ و ۳
async def test_erase_removes_text_and_identity_but_keeps_the_financial_row() -> None:
    ids = await _seed()
    before = await _audit_count()
    async with session_scope() as session:
        result = await instagram_service.erase_direct_sender_data(
            session, ids["shop_a"], ids["first"], actor_telegram_id=ACTOR
        )
        await session.commit()
    assert result == {"ok": True, "reason": "erased", "messages": 3}, result
    assert await _message_count(ids["first"]) == 0, "متنِ پیام‌ها پاک نشد"
    assert await _message_count(ids["second"]) == 1, "گفتگویِ مخاطبِ دیگر دست‌خورد"
    assert await _message_count(ids["telegram"]) == 5, "گفتگویِ تلگرامی دست‌خورد"
    assert await _audit_count() == before + 1, "هر حذف باید یکِ ردیفِ ممیزی بگذارد"

    async with session_scope() as session:
        customer = await session.get(Customer, ids["first"])
        order = await session.get(OrderConsultation, ids["order"])
        assert customer.first_name is None and customer.username is None, "هویت بی‌نام نشد"
        assert customer.phone_number is None, "شماره پاک نشد"
        assert customer.crm_notes is None and customer.crm_tags is None, "CRM پاک نشد"
        assert order is not None and order.status == OrderStatus.COMPLETED, "ردیفِ سفارش باید بماند"
        assert order.customer_id == customer.id
        audit = (
            await session.execute(
                select(AuditLogEntry).where(AuditLogEntry.event_type == AuditEventType.INSTAGRAM_DATA_ERASED)
            )
        ).scalars().all()
        assert audit and "messages" not in audit[0].details and "پیام=3" in (audit[0].details or ""), audit[0].details
        assert audit[0].row_hash and audit[0].prev_hash, "ردیفِ ممیزی باید در زنجیرهٔ هش باشد"
    print("PASS test_erase_removes_text_and_identity_but_keeps_the_financial_row")


# ============================================================================= ۴
async def test_foreign_or_wrong_platform_ids_are_rejected_without_deleting() -> None:
    ids = await _seed()
    async with session_scope() as session:
        foreign = await instagram_service.erase_direct_sender_data(
            session, ids["shop_b"] + 999_999, ids["first"], actor_telegram_id=ACTOR
        )
        wrong_platform = await instagram_service.erase_direct_sender_data(
            session, ids["shop_a"], ids["telegram"], actor_telegram_id=ACTOR
        )
        missing = await instagram_service.erase_direct_sender_data(session, ids["shop_a"], -1, actor_telegram_id=ACTOR)
        await session.rollback()
    assert foreign["ok"] is False and foreign["reason"] == "not-found", foreign
    assert wrong_platform["ok"] is False, "مشتریِ تلگرامی از درِ دایرکت پاک نمی‌شود"
    assert missing["ok"] is False, "شناسهٔ نبودنی باید not-found بدهد، نه حذفِ بی‌ربط"
    assert await _message_count(ids["first"]) == 3, "ردِ نامعتبر چیزی را پاک کرد"
    assert await _message_count(ids["telegram"]) == 5
    print("PASS test_foreign_or_wrong_platform_ids_are_rejected_without_deleting")


# ============================================================================= ۵
async def test_kb_buttons_callbacks_and_audit_label() -> None:
    ids = await _seed()
    rows = [{"id": ids["first"], "label": "sara.test", "messages": 3}]
    kb = keyboards.instagram_dm_keyboard(rows)
    flat = [button.callback_data for line in kb.inline_keyboard for button in line if button.callback_data]
    assert any(item == f"ig_dm_erase:{ids['first']}" for item in flat), flat
    assert all(len(str(item).encode("utf-8")) <= 64 for item in flat), flat

    class _Account:
        auto_reply_dm = True
        auto_reply_comments = True
        private_reply_enabled = True

    connected = [button.callback_data for line in keyboards.instagram_panel_keyboard(_Account()).inline_keyboard for button in line]
    assert "ig_dm" in connected, connected
    disconnected = [button.callback_data for line in keyboards.instagram_panel_keyboard(None).inline_keyboard for button in line]
    assert "ig_dm" not in disconnected, "بدونِ اتصال، دادهٔ دایرکت هم معنایی ندارد"

    confirm = keyboards.instagram_dm_erase_confirm_keyboard(rows[0])
    confirm_flat = [button.callback_data for line in confirm.inline_keyboard for button in line]
    assert confirm_flat == [f"ig_dm_erase_yes:{ids['first']}", "ig_dm_erase_no"], confirm_flat

    from app.bots.main_bot.texts import _AUDIT_EVENT_LABELS  # noqa: PLC0415

    assert AuditEventType.INSTAGRAM_DATA_ERASED.value in _AUDIT_EVENT_LABELS, "برچسبِ فارسیِ نوعِ ممیزی لازم است"
    assert texts.INSTAGRAM_DM_BUTTON.startswith("🧾"), texts.INSTAGRAM_DM_BUTTON
    note = _changelog_text()
    if note is None:
        print("اسکنِ docs/changelog-p112.md: NOT RUN (پوشهٔ docs در ایمیج نیست؛ `.dockerignore`)")
    else:
        assert "پ۱۱۲" in note and "downgrade" in note, "تمرینِ downgrade باید در مستنداتِ همین فاز باشد"
    print("PASS test_kb_buttons_callbacks_and_audit_label")


def _changelog_text() -> str | None:
    path = pathlib.Path("docs/changelog-p112.md")
    return path.read_text(encoding="utf-8") if path.is_file() else None


# ============================================================================= ۶
def test_single_alembic_head_and_p109_downgrade_exists() -> None:
    """نگهبانِ «فقط یکِ alembic head» + داشتنِ `downgrade` رویِ رِویشنِ پ۱۰۹.

    سبکِ نوشتنِ `revision` در این مخزن یکی نیست (`revision = 'x'` قدیمی و `revision: str = "x"`
    تازه)، پس هر دو با regex خوانده می‌شوند؛ اگر روزی دوِ سر باز شود همین تست می‌گوید.
    """
    import re

    directory = pathlib.Path("migrations/versions")
    files = sorted(path for path in directory.glob("*.py") if not path.name.startswith("__"))
    assert len(files) > 40, len(files)
    revisions, parents = set(), set()
    for path in files:
        text = path.read_text(encoding="utf-8")
        found = re.search(r"^revision(?:\s*:\s*str)?\s*=\s*[\"']([^\"']+)[\"']", text, re.M)
        assert found, path.name
        revisions.add(found.group(1))
        down = re.search(r"^down_revision[^=]*=\s*(.+)$", text, re.M)
        if down:
            parents.update(re.findall(r"[\"']([0-9a-f]{8,})[\"']", down.group(1)))
    heads = revisions - parents
    assert len(heads) == 1, f"باید فقط یکِ alembic head باشد: {sorted(heads)}"
    p109 = [path for path in files if "p109_web_panel_sessions" in path.name]
    assert len(p109) == 1, p109
    body = p109[0].read_text(encoding="utf-8")
    assert "def downgrade() -> None:" in body and "drop_table" in body, "رِویشنِ پ۱۰۹ باید بازگشتِ تمرین‌شده داشته باشد"
    print(f"PASS test_single_alembic_head_and_p109_downgrade_exists (هد: {sorted(heads)[0]} · {len(files)} رِویشن)")


async def main() -> None:
    await test_direct_senders_lists_only_instagram_customers_of_this_shop()
    await test_erase_removes_text_and_identity_but_keeps_the_financial_row()
    await test_foreign_or_wrong_platform_ids_are_rejected_without_deleting()
    await test_kb_buttons_callbacks_and_audit_label()
    test_single_alembic_head_and_p109_downgrade_exists()


if __name__ == "__main__":
    asyncio.run(main())
