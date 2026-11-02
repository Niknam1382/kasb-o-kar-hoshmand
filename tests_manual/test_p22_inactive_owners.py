"""
تست: P22 — دستهٔ «🧹 کاربرانِ غیرفعال» و حذفِ حسابِ فروشگاه‌دار (مشکلِ ۸ کاربر)

پوشش:
۱. `owner_activity_service.touch` میانه‌بند دارد (نه هر پیام، یک UPDATE).
۲. میدل‌ورِ هویت واقعاً `last_seen_at` را نو می‌کند و دو پیامِ پشتِ‌سرِ هم یک نوشتن دارد.
۳. `list_inactive`: پنجرهٔ ۳۰ روزه، «بدونِ سابقه» اولِ فهرست، دامنهٔ ادمینِ عملیاتی
   (None ⇒ همه، [] ⇒ هیچ، فهرست ⇒ فقط همان‌ها) و بیرون‌ماندنِ حسابِ پاک‌شده.
۴. دروازهٔ حسابِ پاک‌شده: فروشگاه‌دارِ حذف‌شده هیچ صفحه‌ای از پنل نمی‌بیند؛ ادمین‌هایِ پلتفرم
   (سوپر یا عملیاتی) استثنا هستند، وگرنه پنلِ مدیریتِ خودشان قفل می‌شد.
۵. صفحهٔ ادمین: فهرست با ارقامِ فارسی، کارتِ حساب، تاییدِ دو مرحله‌ای، ممیزیِ هر سه عمل،
   و ردِّ دسترسیِ سوپرادمین-فقط از راهِ callbackِ دست‌سازی‌شده.
۶. حذفِ قطعی: فقط رویِ حسابِ غیرفعال‌شده، با نوشتنِ عبارتِ «حذفِ قطعی»؛ محتوا می‌رود و
   پوسته اگر ردیفِ ممیزی داشته باشد می‌ماند (زنجیرهٔ هشِ ممیزی پاک‌شدنی نیست).

اجرا: python3 tests_manual/run_one.py test_p22_inactive_owners.py
"""
from __future__ import annotations

import asyncio
import datetime
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests_manual"))

from sqlalchemy import func, select  # noqa: E402

from harness import build_test_dispatchers, reset_database  # noqa: E402
from phase4_helpers import Chat  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot import texts as main_texts  # noqa: E402
from app.config import settings  # noqa: E402
from app.database.models import (  # noqa: E402
    AuditEventType,
    AuditLogEntry,
    Customer,
    OrderConsultation,
    OrderEvent,
    OrderStatus,
    OrderType,
    Product,
    ShopBot,
    ShopOwner,
    WalletTransaction,
)  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import admin_role_service, audit_log_service, owner_activity_service, shop_purge_service  # noqa: E402

ADMIN_TG_ID = 12345
OPERATOR_TG_ID = 999_811
STALE_OWNER_TG_ID = 999_812
FRESH_OWNER_TG_ID = 999_813
REF = datetime.datetime.now(datetime.timezone.utc)  # لنگرِ تست: همه‌چیز نسبت به ساعتِ واقعیِ ظرف


def _edit_labels(chat: Chat) -> list[str]:
    """دکمه‌هایِ آخرین edit_text (چون صفحه‌هایِ داخلِ پنل با ویرایشِ پیام نشان داده می‌شوند)."""
    markup = chat.edits[-1]["reply_markup"]
    return [btn.text for row in markup.inline_keyboard for btn in row]


async def _owner(telegram_id: int) -> ShopOwner:
    async with session_scope() as session:
        return (await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == telegram_id))).scalar_one()


async def _bot_id(owner_id: int) -> int | None:
    async with session_scope() as session:
        return (await session.execute(select(ShopBot.id).where(ShopBot.shop_owner_id == owner_id))).scalar_one_or_none()


async def _set_last_seen(telegram_id: int, moment) -> None:
    async with session_scope() as session:
        owner = (await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == telegram_id))).scalar_one()
        owner.last_seen_at = moment
        await session.flush()


async def _seed_two_shops() -> tuple[int, int]:
    """یکِ حسابِ ۴۰ روزهٔ بی‌خبر و یکِ حسابِ تازه (۲ روزِ پیش)."""
    await reset_database()
    stale = await seed_usable_shop(STALE_OWNER_TG_ID, 999_821)
    fresh = await seed_usable_shop(FRESH_OWNER_TG_ID, 999_822)
    # ۴۰ روز و یک ساعت (نه دقیقاً ۴۰ روز): کفِ تقسیمِ روزها نباید با چند ثانیه کشیده شود
    await _set_last_seen(STALE_OWNER_TG_ID, REF - datetime.timedelta(days=40, hours=1))
    await _set_last_seen(FRESH_OWNER_TG_ID, REF - datetime.timedelta(days=2))
    return stale, fresh


async def _content_counts(owner_id: int) -> dict[str, int]:
    bot_id = await _bot_id(owner_id)
    async with session_scope() as session:
        async def _count(model, *criteria) -> int:
            return int((await session.execute(select(func.count()).select_from(model).where(*criteria))).scalar_one())

        return {
            "products": await _count(Product, Product.shop_bot_id == bot_id) if bot_id else 0,
            "customers": await _count(Customer, Customer.shop_bot_id == bot_id) if bot_id else 0,
            "orders": await _count(OrderConsultation, OrderConsultation.shop_bot_id == bot_id) if bot_id else 0,
            "events": await _count(OrderEvent, OrderEvent.order_id.is_not(None)) if bot_id else 0,
            "wallet": await _count(WalletTransaction, WalletTransaction.shop_owner_id == owner_id),
            "bots": await _count(ShopBot, ShopBot.shop_owner_id == owner_id),
            "owners": await _count(ShopOwner, ShopOwner.id == owner_id),
        }


async def _fill_content(owner_id: int) -> None:
    bot_id = await _bot_id(owner_id)
    async with session_scope() as session:
        product = Product(shop_bot_id=bot_id, name="کیف", price_toman=100_000, stock_quantity=3, kind="physical")
        customer = Customer(shop_bot_id=bot_id, telegram_id=777_001, platform="telegram", first_name="مشتری")
        session.add_all([product, customer])
        await session.flush()
        order = OrderConsultation(
            shop_bot_id=bot_id,
            customer_id=customer.id,
            product_id=product.id,
            type=OrderType.ORDER,
            summary="کیف",
            status=OrderStatus.CONFIRMED,
            quantity=1,
            estimated_value_toman=100_000,
        )
        session.add(order)
        await session.flush()
        session.add(OrderEvent(order_id=order.id, to_status="confirmed"))
        await session.flush()


# ============================================================================= ۱ — میانه‌بند
async def test_touch_is_throttled() -> None:
    await reset_database()
    await seed_usable_shop(999_830, 999_831)
    async with session_scope() as session:
        owner = (await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == 999_830))).scalar_one()
        assert await owner_activity_service.touch(session, owner, now=REF) is True, "اولین دیدار باید بنویسد"
        assert await owner_activity_service.touch(session, owner, now=REF + datetime.timedelta(minutes=3)) is False, "سه دقیقه بعد ⇒ میانه‌بند"
        assert await owner_activity_service.touch(session, owner, now=REF + datetime.timedelta(minutes=11)) is True, "۱۱ دقیقه بعد ⇒ می‌نویسد"
        stored = (await session.execute(select(ShopOwner.last_seen_at).where(ShopOwner.id == owner.id))).scalar_one()
        assert stored is not None and abs((stored - (REF + datetime.timedelta(minutes=11))).total_seconds()) < 2, stored
    print("✅ test_touch_is_throttled PASSED")


# ============================================================================= ۲ — میدل‌ور
async def test_middleware_records_the_visit(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(999_832, 999_833)
    await _set_last_seen(999_832, None)
    chat = Chat(main_dp, 999_832)
    await chat.say("/start")
    first = (await _owner(999_832)).last_seen_at
    assert first is not None, "میدل‌ور باید آخرین دیدار را ثبت کند"
    await chat.say("/start")
    assert (await _owner(999_832)).last_seen_at == first, "دو پیامِ پشتِ‌سرِ هم ⇒ یکِ نوشتن (میانه‌بند)"
    print("✅ test_middleware_records_the_visit PASSED")


# ============================================================================= ۳ — پنجره و دامنه
async def test_inactive_window_and_scope() -> None:
    await _seed_two_shops()
    stale_id = (await _owner(STALE_OWNER_TG_ID)).id
    # یکِ سومِ حساب بدونِ هیچ سابقه ⇒ «بدونِ سابقه» اول فهرست می‌آید (نبودِ داده ≠ ادعایِ غیرفعال بودن)
    await seed_usable_shop(OPERATOR_TG_ID, 999_823)
    await _set_last_seen(OPERATOR_TG_ID, None)
    async with session_scope() as session:
        await admin_role_service.grant_operator(session, OPERATOR_TG_ID, granted_by_telegram_id=ADMIN_TG_ID)
        role = await admin_role_service.get_by_telegram_id(session, OPERATOR_TG_ID)
        await admin_role_service.set_scope(session, role, [stale_id])

    async with session_scope() as session:
        rows = await owner_activity_service.list_inactive(session, 30, now=REF)
        ids = [row.owner.id for row in rows]
        assert stale_id in ids, ids
        assert (await _owner(FRESH_OWNER_TG_ID)).id not in ids, "دو روزِ پیش در پنجرهٔ ۳۰ روزه نیست"
        assert rows[0].since_days is None and rows[0].bot_username is not None, "بی‌سابقه باید اول باشد"
        assert any(row.since_days == 40 for row in rows), [row.since_days for row in rows]

        scoped = await owner_activity_service.list_inactive(session, 30, allowed_owner_ids=[stale_id], now=REF)
        assert [row.owner.id for row in scoped] == [stale_id], scoped
        assert await owner_activity_service.list_inactive(session, 30, allowed_owner_ids=[], now=REF) == []
        assert await owner_activity_service.count_inactive(session, 30, now=REF) == len(rows)
        # پنجرهٔ درشت‌تر = «مدتِ بیشتری خبری نشده» ⇒ آدم‌هایِ *کمتر* (نه بیشتر)
        assert await owner_activity_service.count_inactive(session, 90, now=REF) <= len(rows)
        assert await owner_activity_service.count_inactive(session, 7, now=REF) >= len(rows) - 1
    print("✅ test_inactive_window_and_scope PASSED")


# ============================================================================= ۴ — دروازه
async def test_soft_delete_gates_the_owner(main_dp) -> None:
    await _seed_two_shops()
    async with session_scope() as session:
        owner = (await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == STALE_OWNER_TG_ID))).scalar_one()
        await owner_activity_service.soft_delete(session, owner)

    chat = Chat(main_dp, STALE_OWNER_TG_ID)
    await chat.say("/start")
    assert "غیرفعال شده" in chat.last_text, chat.last_text
    assert len(chat.sent) == 1, f"بعد از دروازه نباید صفحه‌ای از پنل برود: {[m['text'][:40] for m in chat.sent]}"

    async with session_scope() as session:
        rows = await owner_activity_service.list_inactive(session, 30, now=REF)
        assert (await _owner(STALE_OWNER_TG_ID)).id not in [row.owner.id for row in rows], "حسابِ پاک‌شده دوباره «غیرفعال» شمرده نمی‌شود"
    print("✅ test_soft_delete_gates_the_owner PASSED")


# ============================================================================= ۴-ب — ادمین قفل نمی‌شود
async def test_platform_admin_is_not_locked_out(main_dp) -> None:
    """درِوازه نباید ادمینِ پلتفرم را از پنلِ خودش بیرون بیندازد.

    سوپرادمین/ادمینِ عملیاتی ممکن است روزی فروشگاهِ خودش را داشته باشد و همان حسابِ
    فروشگاهی پاک‌شده باشد؛ قفل‌کردنِ او یعنی از دست دادنِ دسترسیِ مدیریتِ پلتفرم."""
    assert ADMIN_TG_ID in settings.admin_ids, "محیطِ تست باید این شناسه را سوپرادمین بداند"
    await _seed_two_shops()
    operator_id = 999_850
    await seed_usable_shop(ADMIN_TG_ID, 999_851)
    await seed_usable_shop(operator_id, 999_852)
    async with session_scope() as session:
        await admin_role_service.grant_operator(session, operator_id, granted_by_telegram_id=ADMIN_TG_ID)
    for tg in (ADMIN_TG_ID, operator_id, STALE_OWNER_TG_ID):
        async with session_scope() as session:
            owner = (await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == tg))).scalar_one()
            await owner_activity_service.soft_delete(session, owner)
            assert owner.is_deleted is True

    admin = Chat(main_dp, ADMIN_TG_ID)
    await admin.say(main_texts.INACTIVE_BUTTON)
    assert main_texts.ACCOUNT_DELETED_NOTICE not in admin.last_text, admin.last_text
    # هر سه حسابِ بی‌خبرِ این آزمون پاک شده ⇒ صفحه باید «خالی» بگوید، نه دروازهٔ حساب
    assert "غیرفعالی نیست" in admin.last_text, admin.last_text
    assert admin.last_markup is not None, "پنجره‌هایِ ۷/۳۰/۹۰ باید رویِ صفحهٔ خالی هم باشند"

    operator = Chat(main_dp, operator_id)
    await operator.say(main_texts.INACTIVE_BUTTON)
    assert operator.last_text != main_texts.ACCOUNT_DELETED_NOTICE, operator.last_text
    assert operator.last_markup is not None, "صفحهٔ ادمین باید برایِ ادمینِ عملیاتی هم باز شود"

    # و فروشگاه‌دارِ معمولی همان‌جا می‌ماند (تضادِ رفتار، تا دروازه سرِ‌جایِ خودش باشد)
    plain = Chat(main_dp, STALE_OWNER_TG_ID)
    await plain.say(main_texts.INACTIVE_BUTTON)
    assert plain.last_text == main_texts.ACCOUNT_DELETED_NOTICE, plain.last_text
    assert len(plain.sent) == 1, [m["text"][:40] for m in plain.sent]
    print("✅ test_platform_admin_is_not_locked_out PASSED")


# ============================================================================= ۵ — صفحهٔ ادمین
async def test_admin_screen_deactivates_and_restores(main_dp) -> None:
    await _seed_two_shops()
    stale = await _owner(STALE_OWNER_TG_ID)
    admin = Chat(main_dp, ADMIN_TG_ID)

    await admin.say(main_texts.INACTIVE_BUTTON)
    assert "۳۰ روز" in admin.last_text, admin.last_text  # ارقامِ فارسی، مثلِ بقیهٔ پنل
    labels = [btn.text for row in admin.last_markup.inline_keyboard for btn in row]
    assert any("۴۰ روزِ پیش" in label for label in labels), labels
    assert not any("۲ روزِ پیش" in label for label in labels), labels

    await admin.tap(f"inact_view:{stale.id}")
    detail = admin.last_edit_text
    assert stale.first_name in detail and "۴۰ روزِ پیش" in detail, detail
    assert "🧊 غیرفعال‌کردنِ حساب" in _edit_labels(admin), _edit_labels(admin)

    await admin.tap(f"inact_deactivate:{stale.id}")
    assert "غیرفعال شود؟" in admin.last_edit_text, admin.last_edit_text
    await admin.tap(f"inact_deactivate_yes:{stale.id}")
    assert "غیرفعال شد" in admin.last_toast["text"], admin.last_toast
    assert (await _owner(STALE_OWNER_TG_ID)).is_deleted is True
    async with session_scope() as session:
        entries = list(
            (await session.execute(select(AuditLogEntry).where(AuditLogEntry.event_type == AuditEventType.OWNER_DEACTIVATED))).scalars().all()
        )
        assert len(entries) == 1, entries
        assert f"tg={STALE_OWNER_TG_ID}" in (entries[0].details or ""), entries[0].details

    await admin.tap("inact_deleted")
    labels = _edit_labels(admin)
    assert any(stale.first_name in label for label in labels), labels
    await admin.tap(f"inact_view:{stale.id}")
    assert "غیرفعال شده است" in admin.last_edit_text, admin.last_edit_text
    await admin.tap(f"inact_restore:{stale.id}")
    await admin.tap(f"inact_restore_yes:{stale.id}")
    assert "برگشت" in admin.last_toast["text"], admin.last_toast
    restored = await _owner(STALE_OWNER_TG_ID)
    assert restored.is_deleted is False and restored.deleted_at is None
    async with session_scope() as session:
        count = int(
            (
                await session.execute(
                    select(func.count()).select_from(AuditLogEntry).where(AuditLogEntry.event_type == AuditEventType.OWNER_RESTORED)
                )
            ).scalar_one()
        )
        assert count == 1
    print("✅ test_admin_screen_deactivates_and_restores PASSED")


# ============================================================================= ۶ — دامنه و سوپرادمین-فقط
async def test_operator_is_scoped_and_cannot_delete(main_dp) -> None:
    await _seed_two_shops()
    stale_id = (await _owner(STALE_OWNER_TG_ID)).id
    fresh_id = (await _owner(FRESH_OWNER_TG_ID)).id
    async with session_scope() as session:
        await admin_role_service.grant_operator(session, OPERATOR_TG_ID, granted_by_telegram_id=ADMIN_TG_ID)
        role = await admin_role_service.get_by_telegram_id(session, OPERATOR_TG_ID)
        await admin_role_service.set_scope(session, role, [stale_id])

    operator = Chat(main_dp, OPERATOR_TG_ID)
    await operator.say(main_texts.INACTIVE_BUTTON)
    labels = [btn.text for row in operator.last_markup.inline_keyboard for btn in row]
    assert any("۴۰ روز" in label for label in labels), labels

    await operator.tap(f"inact_view:{fresh_id}")  # خارج از دامنه
    assert operator.last_toast["text"] == main_texts.INACTIVE_STALE, operator.last_toast
    await operator.tap(f"inact_deactivate:{stale_id}")  # کارِ سوپرادمین نیست
    assert operator.last_toast["text"] == main_texts.INACTIVE_SUPER_ONLY, operator.last_toast
    await operator.tap(f"inact_deactivate_yes:{stale_id}")
    assert (await _owner(STALE_OWNER_TG_ID)).is_deleted is False, "دکمهٔ تایید هم باید سوپرادمین بخواهد"
    print("✅ test_operator_is_scoped_and_cannot_delete PASSED")


# ============================================================================= ۷ — حذفِ قطعی
async def test_purge_needs_the_word_and_keeps_referenced_shell(main_dp) -> None:
    await _seed_two_shops()
    stale = await _owner(STALE_OWNER_TG_ID)
    await _fill_content(stale.id)
    admin = Chat(main_dp, ADMIN_TG_ID)

    async with session_scope() as session:
        owner = (await session.execute(select(ShopOwner).where(ShopOwner.id == stale.id))).scalar_one()
        await owner_activity_service.soft_delete(session, owner)
        # ردیفِ ممیزیِ وصل به *رباتِ* همین حساب ⇒ پوسته پاک‌شدنی نیست (زنجیرهٔ هش)
        await audit_log_service.log(
            session, AuditEventType.SHOP_SUSPENDED, shop_bot_id=await _bot_id(stale.id), actor_telegram_id=ADMIN_TG_ID, details="تست"
        )

    assert (await _content_counts(stale.id))["products"] == 1
    await admin.say(main_texts.INACTIVE_BUTTON)
    await admin.tap("inact_deleted")
    await admin.tap(f"inact_view:{stale.id}")
    await admin.tap(f"inact_purge:{stale.id}")
    assert main_texts.INACTIVE_PURGE_WORD in admin.last_text, admin.last_text

    await admin.say("اشتباه")
    assert admin.last_text.endswith(main_texts.INACTIVE_PURGE_BAD_WORD.format(word=main_texts.INACTIVE_PURGE_WORD)), admin.last_text
    assert (await _content_counts(stale.id))["products"] == 1, "با عبارتِ غلط هیچ‌چیز پاک نمی‌شود"

    await admin.say(main_texts.INACTIVE_PURGE_WORD)
    assert "پاک شد" in admin.last_text, admin.last_text
    counts = await _content_counts(stale.id)
    assert counts == {"products": 0, "customers": 0, "orders": 0, "events": 0, "wallet": 0, "bots": 1, "owners": 1}, counts
    assert main_texts.INACTIVE_PURGE_SHELL_KEPT in admin.last_text, admin.last_text
    async with session_scope() as session:
        purged = list((await session.execute(select(AuditLogEntry).where(AuditLogEntry.event_type == AuditEventType.OWNER_PURGED))).scalars().all())
        assert len(purged) == 1 and "پوسته=ماند" in (purged[0].details or ""), purged[0].details
        assert int((await session.execute(select(func.count()).select_from(AuditLogEntry))).scalar_one()) >= 2, "زنجیرهٔ ممیزی دست‌نخورده"
    print("✅ test_purge_needs_the_word_and_keeps_referenced_shell PASSED")


async def test_purge_removes_unreferenced_shell() -> None:
    await reset_database()
    await seed_usable_shop(999_840, 999_841)
    owner_id = (await _owner(999_840)).id
    async with session_scope() as session:
        owner = (await session.execute(select(ShopOwner).where(ShopOwner.id == owner_id))).scalar_one()
        assert await shop_purge_service.blocking_references(session, owner) == {}, "حسابِ تازه هیچ ارجاعِ ماندگاری ندارد"
        await owner_activity_service.soft_delete(session, owner)
        result = await shop_purge_service.purge_owner(session, owner)
        assert result["shell_removed"] is True and result["blockers"] == {}, result
    counts = await _content_counts(owner_id)
    assert counts["bots"] == 0 and counts["owners"] == 0, counts
    print("✅ test_purge_removes_unreferenced_shell PASSED")


async def test_purge_refuses_active_account(main_dp) -> None:
    await _seed_two_shops()
    stale = await _owner(STALE_OWNER_TG_ID)
    admin = Chat(main_dp, ADMIN_TG_ID)
    await admin.say(main_texts.INACTIVE_BUTTON)
    await admin.tap(f"inact_view:{stale.id}")
    labels = _edit_labels(admin)
    assert "🧊 غیرفعال‌کردنِ حساب" in labels and "🔥 حذفِ قطعیِ داده" not in labels, labels
    await admin.tap(f"inact_purge:{stale.id}")
    assert admin.last_toast["text"] == main_texts.INACTIVE_NOT_DELETED_FIRST, admin.last_toast
    print("✅ test_purge_refuses_active_account PASSED")


async def main() -> None:
    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    await test_touch_is_throttled()
    await test_middleware_records_the_visit(main_dp)
    await test_inactive_window_and_scope()
    await test_soft_delete_gates_the_owner(main_dp)
    await test_platform_admin_is_not_locked_out(main_dp)
    await test_admin_screen_deactivates_and_restores(main_dp)
    await test_operator_is_scoped_and_cannot_delete(main_dp)
    await test_purge_needs_the_word_and_keeps_referenced_shell(main_dp)
    await test_purge_removes_unreferenced_shell()
    await test_purge_refuses_active_account(main_dp)


if __name__ == "__main__":
    asyncio.run(main())
