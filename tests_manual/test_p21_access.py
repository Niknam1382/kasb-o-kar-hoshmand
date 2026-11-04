"""
تست: P21-E — دامنهٔ دسترسی، فیلتر/خروجیِ دفترِ ممیزی، سلامتِ استخرِ AI، CSVِ امن

پوشش:
۱. `csv_export`: هر مقدارِ شروع‌شونده با `=`/`+`/`-`/`@` بی‌خطر می‌شود (CSV injection) و BOMِ فارسی حفظ است.
۲. `admin_role_service`: دامنهٔ None ⇒ بدونِ محدودیت؛ فهرست ⇒ فقط همان‌ها؛ ورودیِ خام ⇒ clamp.
۳. ادمینِ عملیاتیِ دامنه‌دار نمی‌تواند فروشگاه‌دارِ خارج از دامنه را باز/معلق/هدیه دهد
   (تستِ سطحِ هندلر، نه فقط تابع — چون حملۀ واقعی با callbackِ دست‌سازی‌شده می‌آید).
۴. `audit_log_service.query`: فیلترِ دسته و بازهٔ زمانی؛ خروجیِ CSVِ همان فیلتر ممیزی می‌شود.
۵. `ai_service.circuit_health`: پس از شکست‌هایِ پیاپی، شمارشِ کلیدهایِ کنارگذاشته‌شده بالا می‌رود
   (failover از قبل بود؛ چیزی که نبود «دیده‌شدن»ش بود).

اجرا: python3 tests_manual/test_p21_access.py
"""
from __future__ import annotations

import asyncio
import datetime
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from sqlalchemy import select  # noqa: E402

from harness import build_test_dispatchers, reset_database  # noqa: E402
from phase4_helpers import Chat  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot import texts as main_texts  # noqa: E402
from app.database.models import AuditEventType, AuditLogEntry, ShopOwner, ShopBot  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import admin_role_service, ai_service, audit_log_service  # noqa: E402
from app.utils import csv_export  # noqa: E402

ADMIN_TG_ID = 12345
OPERATOR_TG_ID = 999_791
OWNER_A_TG_ID = 999_792
OWNER_B_TG_ID = 999_793


# ============================================================================= ۱ — CSVِ امن
def test_csv_neutralizes_formulas() -> None:
    assert csv_export.safe_cell("=SUM(A1:A9)") == "'=SUM(A1:A9)"
    assert csv_export.safe_cell("+1234567") == "'+1234567"
    assert csv_export.safe_cell("-abc") == "'-abc"
    assert csv_export.safe_cell("@cmd|'/C calc'!A0").startswith("'")
    assert csv_export.safe_cell("معمولی") == "معمولی"
    assert csv_export.safe_cell(None) == ""
    assert csv_export.safe_cell(123) == "123", "عدد فرمول نیست و نباید نقل‌قول بگیرد"

    payload = csv_export.build_csv(["id", "details"], [[1, "=1+1"], [2, "a,b"], [3, "سلام، دنیا"]])
    text = payload.decode("utf-8-sig")
    assert payload.startswith(b"\xef\xbb\xbf"), "BOM برایِ فارسیِ اکسل"
    assert "'=1+1" in text, text
    assert '"a,b"' in text, "ویرگولِ ASCIIِ داخلِ مقدار باید نقل‌قول‌دار شود"
    assert "سلام، دنیا" in text, "ویرگولِ فارسی جداکنندهٔ CSV نیست و نباید نقل‌قول بگیرد"
    print("✅ test_csv_neutralizes_formulas PASSED")


# ============================================================================= ۲ — دامنه
def test_scope_parsing_is_pure() -> None:
    assert admin_role_service.parse_owner_ids(None) is None
    # P21-F: رشتهٔ خالی دیگر None نیست — «دامنهٔ تهی» با «بدونِ دامنه» یکی نبود (برعکسِ قبل که
    # دامنهٔ تهی یعنی دسترسیِ کامل). تستِ کاملش در test_p21_security.py است.
    assert admin_role_service.parse_owner_ids("") == set()
    assert admin_role_service.parse_owner_ids("3,7, 9") == {3, 7, 9}
    scope = admin_role_service.parse_owner_ids("3,7")
    assert admin_role_service.is_in_scope(scope, 3) and not admin_role_service.is_in_scope(scope, 4)
    assert admin_role_service.is_in_scope(None, 999), "None ⇒ بدونِ محدودیت"
    print("✅ test_scope_parsing_is_pure PASSED")


async def _operator_with_scope(owner_ids: list[int]) -> int:
    async with session_scope() as session:
        role = await admin_role_service.grant_operator(session, OPERATOR_TG_ID, granted_by_telegram_id=ADMIN_TG_ID)
        await admin_role_service.set_scope(session, role, owner_ids)
        return role.id


async def test_operator_sees_only_scoped_owners(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_A_TG_ID, 999_794)
    shop_b = await seed_usable_shop(OWNER_B_TG_ID, 999_795)
    async with session_scope() as session:
        owner_a = (await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == OWNER_A_TG_ID))).scalar_one()
        owner_b = (await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == OWNER_B_TG_ID))).scalar_one()
        owner_b_id = owner_b.id
        owner_a_id = owner_a.id
    await _operator_with_scope([owner_a_id])

    operator = Chat(main_dp, OPERATOR_TG_ID)
    await operator.say("👥 مدیریت فروشگاه‌دارها")
    listing = operator.last_text
    assert main_texts.ADMIN_SHOP_OWNERS_EMPTY not in listing, listing
    assert "۱" in listing, "فهرست باید فقط فروشگاهِ داخلِ دامنه را بشمارد"

    # داخلِ دامنه ⇒ باز می‌شود
    await operator.tap(f"admin_owner_view:{owner_a_id}")
    assert "🚫" not in operator.last_edit_text, operator.last_edit_text

    # خارج از دامنه ⇒ نه صفحه باز می‌شود، نه تعلیق، نه هدیه
    await operator.tap(f"admin_owner_view:{owner_b_id}")
    assert main_texts.ADMIN_OWNER_OUT_OF_SCOPE in operator.last_edit_text, operator.last_edit_text
    before = len(operator.sent)
    await operator.tap(f"admin_owner_suspend:{owner_b_id}")
    assert len(operator.sent) == before, "تعلیقِ فروشگاهِ خارج از دامنه نباید پیامِ موفقیت بدهد"
    toast = operator.last_toast["text"] if operator.session.answered_callbacks else ""
    assert main_texts.ADMIN_OWNER_OUT_OF_SCOPE_TOAST in toast, toast
    async with session_scope() as session:
        suspended = (await session.execute(select(ShopOwner).where(ShopOwner.id == owner_b_id))).scalar_one()
        bot_b = (await session.execute(select(ShopBot).where(ShopBot.id == shop_b))).scalar_one()
        assert bot_b.is_active is True, "فروشگاهِ خارج از دامنه معلق نشد"
        assert suspended is not None

    # ادمینِ بدونِ دامنه (سوپرادمین) همان کار را می‌تواند بکند
    super_admin = Chat(main_dp, ADMIN_TG_ID)
    await super_admin.tap(f"admin_owner_view:{owner_b_id}")
    assert "🚫" not in super_admin.last_edit_text, super_admin.last_edit_text
    print("✅ test_operator_sees_only_scoped_owners PASSED")


async def test_scope_editor_lists_unknown_ids(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_A_TG_ID, 999_794)
    await _operator_with_scope([])

    admin = Chat(main_dp, ADMIN_TG_ID)
    async with session_scope() as session:
        role = await admin_role_service.get_by_telegram_id(session, OPERATOR_TG_ID)
        role_id = role.id
    await admin.tap(f"admin_role_scope:{role_id}")
    await admin.say(f"{OWNER_A_TG_ID},7777777")
    saved = admin.last_text
    assert "دامنه ذخیره شد" in saved and "۱ فروشگاه" in saved, saved
    assert "7777777" in saved, "شناسهٔ ناشناخته باید گزارش شود، نه بی‌صدا رد"
    print("✅ test_scope_editor_lists_unknown_ids PASSED")


# ============================================================================= ۴ — فیلترِ ممیزی
async def test_audit_filters_and_window() -> None:
    await reset_database()
    now = datetime.datetime(2026, 11, 1, 12, 0, tzinfo=datetime.timezone.utc)
    async with session_scope() as session:
        await audit_log_service.log(session, AuditEventType.PAYMENT_APPROVED, actor_telegram_id=ADMIN_TG_ID, details="تاییدِ پرداخت")
        await audit_log_service.log(session, AuditEventType.ADMIN_SETTING_CHANGED, actor_telegram_id=ADMIN_TG_ID, details="نرخ دلار")
        await audit_log_service.log(session, AuditEventType.SHOP_SUSPENDED, actor_telegram_id=ADMIN_TG_ID, details="تعلیق")
        await session.commit()
    # یکی را «قدیمی» می‌کنیم تا پنجرهٔ زمانی هم سنجیده شود
    async with session_scope() as session:
        row = (await session.execute(select(AuditLogEntry).order_by(AuditLogEntry.id))).scalars().first()
        row.created_at = now - datetime.timedelta(days=40)
        await session.commit()

    async with session_scope() as session:
        all_rows = await audit_log_service.query(session)
        money = await audit_log_service.query(session, group="money")
        settings = await audit_log_service.query(session, group="settings")
        recent = await audit_log_service.query(session, window="24", now=now)
        by_actor = await audit_log_service.query(session, actor_telegram_id=OPERATOR_TG_ID)
    assert len(all_rows) == 3, len(all_rows)
    assert {row.event_type for row in money} == {AuditEventType.PAYMENT_APPROVED.value}, [row.event_type for row in money]
    assert {row.event_type for row in settings} == {AuditEventType.ADMIN_SETTING_CHANGED.value}, [row.event_type for row in settings]
    assert len(recent) == 2, len(recent)  # آن‌که ۴۰ روز پیش است بیرون می‌ماند
    assert by_actor == [], "فاکتورِ Actorِ غلط هیچی نمی‌دهد"
    assert main_texts.audit_report_intro("money", "7d", 1).count("💰") == 1
    print("✅ test_audit_filters_and_window PASSED")


# ============================================================================= ۵ — سلامتِ استخرِ AI
def test_circuit_health_counts_open_keys() -> None:
    ai_service.reset_all_circuits_for_tests()
    try:
        assert ai_service.circuit_health() == {"open_keys": 0, "tracked": 0, "failures": 0}
        for _ in range(ai_service._CIRCUIT_FAILURE_THRESHOLD):
            ai_service._record_circuit_failure(4242, "gpt-x")
        health = ai_service.circuit_health()
        assert health["open_keys"] == 1 and health["failures"] == ai_service._CIRCUIT_FAILURE_THRESHOLD, health
        assert main_texts.ai_pool_health_line(health).startswith("\n\n⚠️"), main_texts.ai_pool_health_line(health)
        assert main_texts.ai_pool_health_line({"open_keys": 0, "tracked": 0, "failures": 0}) == "", "سالم ⇒ بی‌سروصدا"
        ai_service._record_circuit_success(4242, "gpt-x")
        assert ai_service.circuit_health()["open_keys"] == 0
    finally:
        ai_service.reset_all_circuits_for_tests()
    print("✅ test_circuit_health_counts_open_keys PASSED")


async def main() -> None:
    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    test_csv_neutralizes_formulas()
    test_scope_parsing_is_pure()
    test_circuit_health_counts_open_keys()
    await test_operator_sees_only_scoped_owners(main_dp)
    await test_scope_editor_lists_unknown_ids(main_dp)
    await test_audit_filters_and_window()


if __name__ == "__main__":
    asyncio.run(main())
