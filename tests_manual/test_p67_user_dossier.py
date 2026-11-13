"""پ۶۷ · موردِ ۲۷/۴۱-پ — «🧾 پروندهٔ کاملِ کاربر» در پنلِ ادمین.

نیمهٔ دومِ خواستهٔ «مدیریتِ جامعِ کاربران»: اطلاعاتِ یکِ فروشگاه‌دار در چهار صفحه پخش بود
(مدیریتِ فروشگاه‌دارها / مصرفِ کاربران / کاربرانِ غیرفعال / اعتبار و زمان). این تست هم نما را
قفل می‌کند، هم سه قولِ طراحی را: **فقط‌خواندنی بودنِ جمع‌آوری**، **بازاستفاده از فعل‌هایِ موجود**
(نه مسیرِ پولیِ دوم)، و **دامنه/سوپر-ادمین** رویِ هر دو.

پوششِ داده‌شده:
۱. `owner_dossier_service.build` هر بخش را از منبعِ درست می‌خواند (ولت/قابل‌مصرف/رزرو/بدهی،
   اشتراک با مهلت، مصرفِ AI ۳۰ روز، پرداخت‌هایِ تاییدشده، اتصالِ بله و اینستاگرام و mute،
   شمارشِ مشتری/سفارش/سفارشِ باز/کمپین/نگهبان/ممیزی).
۲. جمع‌آوری **صفر** INSERT/UPDATE/DELETE دارد و سقفِ جمله‌هایِ SELECT هم بسته است (صفحه‌ای که با
   درخواستِ ادمین باز می‌شود نباید پل‌کُشِ دیتابیس شود).
۳. حسابِ بی‌ربات و حسابِ ناموجود نمی‌شکنند.
۴. متن: ارقامِ جلالی، موبایلِ ماسک‌شده، و **هیچ آیدیِ عددیِ تلگرامی نشت نمی‌کند** (همان قانونِ H2
   که کارتِ قدیمی را قفل کرده بود).
۵. جریانِ واقعیِ پنل: کارتِ جزئیات ⇒ «🧾 پروندهٔ کاملِ کاربر» ⇒ نما ⇒ «🔄 تازه‌سازیِ پرونده» با
   دقیقاً یکِ پاسخِ کال‌بک و یکِ ویرایش.
۶. دامنه: ادمینِ عملیاتی خارج از دامنه ⇒ توستِ بی‌عمل و صفر ویرایش؛ داخلِ دامنه ⇒ نما می‌آید ولی
   ردیف‌هایِ سوپرادمینی (`inact_*`) در کیبوردش نیست.
۷. «➕ تمدیدِ روزِ اشتراک» (تنها فعلِ تازه): عددِ درست ⇒ `end_date` به‌اندازهٔ همان روز جلو می‌رود
   و یکِ ردیفِ ممیزیِ `SUBSCRIPTION_EXTENDED` با `shop_bot_id` ثبت می‌شود؛ عددِ غلط و `/cancel`
   بی‌اثرند.
۸. شناسهٔ دست‌کاری‌شده در کال‌بک رد می‌شود؛ حسابِ بسته‌شده تمدید نمی‌شود و کیبوردش به‌جای
   «غیرفعال‌کردن»، «بازگرداندن/حذفِ قطعی» را نشان می‌دهد.

اجرا: python3 tests_manual/run_one.py test_p67_user_dossier.py
"""
from __future__ import annotations

import asyncio
import contextlib
import datetime as dt
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from sqlalchemy import event, func, select  # noqa: E402
from harness import build_test_dispatchers, reset_database  # noqa: E402
from phase4_helpers import Chat, add_customer, add_order, callbacks  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot import keyboards, texts  # noqa: E402
from app.database.models import (  # noqa: E402
    AiUsageDebt,
    AuditEventType,
    AuditLogEntry,
    Campaign,
    CampaignDiscountType,
    InstagramAccount,
    ModerationReport,
    OrderStatus,
    Payment,
    PaymentMethod,
    PaymentPurpose,
    PaymentStatus,
    ShopBot,
    ShopOwner,
    SubscriptionStatus,
    WalletTransaction,
    WalletTransactionReason,
)
from app.database.session import engine, session_scope  # noqa: E402
from app.services import (  # noqa: E402
    admin_role_service,
    audit_log_service,
    owner_dossier_service,
    shop_owner_service,
    subscription_service,
)

OWNER_TG_ID = 996_801
SHOP_BOT_TG_ID = 996_802
OTHER_OWNER_TG_ID = 996_803
OTHER_SHOP_BOT_TG_ID = 996_804
ADMIN_TG_ID = 12345
OPERATOR_TG_ID = 996_805
NOW = dt.datetime(2026, 11, 13, 9, 0, tzinfo=dt.timezone.utc)
RAW_PHONE = "09123334455"


@contextlib.contextmanager
def _counted():
    seen: list[str] = []

    def _listener(_conn, _cursor, statement, _params, _context, _executemany):
        seen.append(" ".join(statement.split()).upper())

    event.listen(engine.sync_engine, "before_cursor_execute", _listener)
    try:
        yield seen
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", _listener)


async def _seed_rich_shop() -> tuple[int, int]:
    """فروشگاهِ کامل: ولت + شارژِ تاریخ‌دار + رزرو + بدهی + پرداخت + اشتراک + بله + اینستاگرام + داده‌ها."""
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID, initial_balance_toman=0)
    other_shop_bot_id = await seed_usable_shop(OTHER_OWNER_TG_ID, OTHER_SHOP_BOT_TG_ID, initial_balance_toman=0)
    customer_id = await add_customer(shop_bot_id, 779_001, "سارا", "sara.x")
    await add_order(shop_bot_id, customer_id, status=OrderStatus.CONFIRMED, value=200_000,
                    created_at=NOW - dt.timedelta(days=2), confirmed_at=NOW - dt.timedelta(days=2))
    await add_order(shop_bot_id, customer_id, status=OrderStatus.PENDING, value=90_000,
                    created_at=NOW - dt.timedelta(hours=2), confirmed=False)
    async with session_scope() as session:
        owner = await shop_owner_service.get_by_telegram_id(session, OWNER_TG_ID)
        owner.phone_number = RAW_PHONE
        owner.email = "sara@example.test"
        owner.last_seen_at = NOW - dt.timedelta(days=3)
        bot = await session.get(ShopBot, shop_bot_id)
        bot.bale_encrypted_token = "123456:FAKE_BALE_TOKEN_FOR_P67_TEST_RUNS"
        bot.bale_bot_id = 996_899
        bot.bale_bot_username = "sara_bale_bot"
        bot.bale_bot_enabled = True
        bot.bale_provider_token = "provider-token"
        bot.knowledge_channel_id = "-100123"
        other_bot = await session.get(ShopBot, other_shop_bot_id)
        session.add(
            InstagramAccount(
                shop_bot_id=shop_bot_id, ig_account_id="1784140900", ig_username="sara.shop",
                access_token="IGQVJ6fake.token.for.p67", is_active=True, muted_until=NOW + dt.timedelta(hours=6),
            )
        )
        session.add(
            WalletTransaction(
                shop_owner_id=owner.id, amount_toman=500_000, reason=WalletTransactionReason.TOPUP,
                idempotency_key="p67-topup", created_at=NOW - dt.timedelta(days=4),
            )
        )
        session.add(
            WalletTransaction(
                shop_owner_id=owner.id, amount_toman=-45_000, reason=WalletTransactionReason.CHAT_MESSAGE,
                idempotency_key="p67-usage", created_at=NOW - dt.timedelta(days=1),
            )
        )
        session.add(
            WalletTransaction(
                shop_owner_id=owner.id, amount_toman=-9_000, reason=WalletTransactionReason.OWNER_ASSISTANT,
                idempotency_key="p67-usage-2", created_at=NOW - dt.timedelta(days=90),
            )
        )
        session.add(
            AiUsageDebt(
                shop_owner_id=owner.id, amount_toman=7_500, reason="chat_message", status="open",
                idempotency_key="p67-debt",
            )
        )
        session.add(
            Payment(
                shop_owner_id=owner.id, purpose=PaymentPurpose.SUBSCRIPTION, duration_months=1,
                base_amount=1_200_000, final_amount=1_000_000, method=PaymentMethod.ZARINPAL,
                status=PaymentStatus.APPROVED,
            )
        )
        session.add(
            Campaign(
                shop_bot_id=shop_bot_id, name="تخفیفِ تست", discount_type=CampaignDiscountType.PERCENT,
                discount_value=10, starts_at=NOW - dt.timedelta(days=1), ends_at=NOW + dt.timedelta(days=3),
                is_active=True,
            )
        )
        session.add(
            ModerationReport(
                shop_bot_id=shop_bot_id, pattern="کلمهٔ ممنوعه", action="block", scope="chat",
                excerpt="نمونهٔ متنِ گزارش‌شده", reviewed=False,
            )
        )
        await subscription_service.purchase_or_renew(session, owner.id, 1)
        await audit_log_service.log(session, AuditEventType.SHOP_SUSPENDED, shop_bot_id=shop_bot_id, details="ردیفِ ممیزیِ تست")
        await session.flush()
        owner.wallet_balance_toman = 446_000
        owner.commission_reserved_toman = 20_000
        session.add(owner)
        await session.flush()
    return shop_bot_id, other_shop_bot_id


async def _owner_pk(user_id: int) -> int:
    async with session_scope() as session:
        owner = await shop_owner_service.get_by_telegram_id(session, user_id)
        return int(owner.id)


async def test_build_reads_every_section() -> None:
    await _seed_rich_shop()
    owner_pk = await _owner_pk(OWNER_TG_ID)
    async with session_scope() as session:
        data = await owner_dossier_service.build(session, owner_pk, now=NOW)
    assert data is not None
    assert data["wallet_toman"] == 446_000 and data["usable_toman"] == 426_000, data
    assert data["reserved_toman"] == 20_000 and data["debt_toman"] == 7_500, data
    assert data["payments"] == {"count": 1, "total_toman": 1_000_000}, data["payments"]
    assert data["usage"] == {"days": 30, "toman": 45_000, "calls": 1}, data["usage"]
    assert data["business_mode"] == "sales" and data["registration_completed"] is True
    assert data["phone_masked"] and RAW_PHONE not in data["phone_masked"], data["phone_masked"]
    assert data["last_seen_days"] == 3, data["last_seen_days"]
    assert data["shop_bot"]["bot_username"] and data["shop_bot"]["is_active"] is True
    assert data["connections"]["bale"] is True and data["connections"]["bale_enabled"] is True
    ig = data["connections"]["instagram"]
    assert ig["ig_username"] == "sara.shop" and ig["muted"] is True and ig["muted_until"] > NOW, ig
    assert data["activity"]["customers"] == 1 and data["activity"]["orders"] == 2, data["activity"]
    assert data["activity"]["open_orders"] == 2, data["activity"]
    assert data["activity"]["campaigns"] == 1 and data["activity"]["moderation_open"] == 1, data["activity"]
    assert data["activity"]["audit_rows"] >= 1, data["activity"]
    assert data["subscription"]["status"] in {s.value for s in SubscriptionStatus}, data["subscription"]
    assert data["subscription"]["usable"] is True and data["subscription"]["days_left"] > 0, data["subscription"]
    print("PASS test_build_reads_every_section")


async def test_build_is_read_only_and_bounded() -> None:
    await _seed_rich_shop()
    owner_pk = await _owner_pk(OWNER_TG_ID)
    with _counted() as seen:
        async with session_scope() as session:
            data = await owner_dossier_service.build(session, owner_pk, now=NOW)
            await owner_dossier_service.recent_audit(session, data["shop_bot"]["id"])
    writes = [s for s in seen if s.startswith(("INSERT", "UPDATE", "DELETE")) or " INSERT " in s or " UPDATE " in s or " DELETE " in s]
    selects = [s for s in seen if s.startswith("SELECT")]
    assert not writes, writes[:3]
    assert len(selects) <= 16, (len(selects), selects[:4])
    print(f"PASS test_build_is_read_only_and_bounded · {len(selects)} جملهٔ SELECT")


async def test_missing_bot_and_owner_do_not_break() -> None:
    await _seed_rich_shop()
    other_pk = await _owner_pk(OTHER_OWNER_TG_ID)
    async with session_scope() as session:
        bot = (await session.execute(select(ShopBot).where(ShopBot.shop_owner_id == other_pk))).scalar_one()
        bot.bale_bot_id = None
        bot.bale_encrypted_token = None
        session.add(bot)
        await session.flush()
        data = await owner_dossier_service.build(session, other_pk, now=NOW)
    assert data["connections"]["bale"] is False and data["connections"]["instagram"] is None, data["connections"]
    assert data["activity"]["customers"] == 0 and data["usage"]["toman"] == 0, data
    async with session_scope() as session:
        assert await owner_dossier_service.build(session, 999_999_999, now=NOW) is None
    print("PASS test_missing_bot_and_owner_do_not_break")


async def test_text_is_persian_and_leaks_nothing() -> None:
    await _seed_rich_shop()
    owner_pk = await _owner_pk(OWNER_TG_ID)
    async with session_scope() as session:
        data = await owner_dossier_service.build(session, owner_pk, now=NOW)
        recent = await owner_dossier_service.recent_audit(session, data["shop_bot"]["id"])
    body = texts.owner_dossier_text(data, [(texts.audit_event_label(e), w) for e, w in recent])
    assert "🧾 پروندهٔ کاملِ کاربر" in body and "🤖 اتصال‌ها" in body and "💳 اشتراک، کیف‌پول و مصرف" in body
    # ارقامِ جلالی در همه‌جا جز *دادهٔ کاربر* (یوزرنیم/ایمیلِ خودِ حساب، که طبقِ سیاستِ مرزِ ارقام
    # خام می‌مانند): پس خط‌هایِ دارایِ @ را از این ادعا بیرون می‌گذاریم.
    digit_free = "\n".join(line for line in body.splitlines() if "@" not in line)
    assert not any(char.isascii() and char.isdigit() for char in digit_free), digit_free[:300]
    assert RAW_PHONE not in body, "موبایل فقط ماسک‌شده"
    assert str(OWNER_TG_ID) not in body, "آیدیِ عددیِ تلگرام در کارتِ ادمین نشانه نمی‌شود (قانونِ H2)"
    assert "اینستاگرام" in body and "خاموش تا" in body, body
    assert "چند روز" in texts.OWNER_DOSSIER_EXTEND_ASK
    print("PASS test_text_is_persian_and_leaks_nothing")


async def test_panel_flow_from_owner_card(main_dp) -> None:
    shop_bot_id, _other = await _seed_rich_shop()
    owner_pk = await _owner_pk(OWNER_TG_ID)
    admin = Chat(main_dp, ADMIN_TG_ID)
    await admin.say("👥 مدیریت فروشگاه‌دارها")
    await admin.tap(f"admin_owner_view:{owner_pk}")
    assert texts.OWNER_DOSSIER_BUTTON in [b.text for r in admin.last_edit_markup.inline_keyboard for b in r], admin.last_edit_markup
    await admin.tap(f"owner_dossier:{owner_pk}")
    body = admin.last_edit_text
    assert body.startswith("🧾 پروندهٔ کاملِ کاربر"), body[:120]
    flat = callbacks(admin.last_edit_markup)
    assert f"owner_dossier_refresh:{owner_pk}" in flat and f"owner_dossier_extend:{owner_pk}" in flat, flat
    assert f"admin_owner_suspend:{owner_pk}" in flat, "رباتِ فعال ⇒ دکمهٔ تعلیق"
    answers = len(admin.session.answered_callbacks)
    edits = len(admin.edits)
    await admin.tap(f"owner_dossier_refresh:{owner_pk}")
    assert len(admin.session.answered_callbacks) == answers + 1, "دقیقاً یکِ پاسخِ کال‌بک"
    assert len(admin.edits) == edits + 1, "دقیقاً یکِ ویرایش"
    assert shop_bot_id
    print("PASS test_panel_flow_from_owner_card")


async def test_operator_scope_and_super_rows(main_dp) -> None:
    await _seed_rich_shop()
    owner_pk = await _owner_pk(OWNER_TG_ID)
    other_pk = await _owner_pk(OTHER_OWNER_TG_ID)
    async with session_scope() as session:
        await admin_role_service.grant_operator(session, OPERATOR_TG_ID, granted_by_telegram_id=ADMIN_TG_ID)
        role = await admin_role_service.get_by_telegram_id(session, OPERATOR_TG_ID)
        await admin_role_service.set_scope(session, role, [other_pk])
    operator = Chat(main_dp, OPERATOR_TG_ID)
    await operator.tap(f"owner_dossier:{owner_pk}")
    assert operator.last_toast["text"] == texts.OWNER_DOSSIER_STALE, operator.last_toast
    assert not operator.edits, "خارج از دامنه ⇒ صفر ویرایش"
    await operator.tap(f"owner_dossier:{other_pk}")
    assert operator.last_edit_text.startswith("🧾 پروندهٔ کاملِ کاربر"), operator.last_edit_text
    flat = callbacks(operator.last_edit_markup)
    assert not any(value.startswith("inact_") for value in flat), f"ردیفِ سوپرادمینی برایِ عملیاتی نیست: {flat}"
    async with session_scope() as session:
        role = await admin_role_service.get_by_telegram_id(session, OPERATOR_TG_ID)
        await admin_role_service.set_scope(session, role, None)
    super_admin = Chat(main_dp, ADMIN_TG_ID)
    await super_admin.tap(f"owner_dossier:{owner_pk}")
    flat = callbacks(super_admin.last_edit_markup)
    assert f"inact_deactivate:{owner_pk}" in flat, flat
    print("PASS test_operator_scope_and_super_rows")


async def test_extend_single_owner_flow(main_dp) -> None:
    await _seed_rich_shop()
    owner_pk = await _owner_pk(OWNER_TG_ID)

    async def _end_date() -> dt.datetime:
        async with session_scope() as session:
            sub = await subscription_service.get_latest_subscription_by_owner_id(session, owner_pk)
            return sub.end_date

    before = await _end_date()
    admin = Chat(main_dp, ADMIN_TG_ID)
    await admin.tap(f"owner_dossier:{owner_pk}")
    await admin.tap(f"owner_dossier_extend:{owner_pk}")
    assert "چند روز" in admin.sent[-1]["text"], admin.sent[-1]["text"]

    await admin.say("هفت")
    assert admin.last_text == texts.OWNER_DOSSIER_EXTEND_BAD_DAYS, admin.last_text
    assert await _end_date() == before, "ورودیِ خراب ⇒ صفر تغییر"

    await admin.say("۷")
    assert admin.last_text == texts.OWNER_DOSSIER_EXTEND_DONE.format(days="۷"), admin.last_text
    after = await _end_date()
    assert (after - before).days == 7, (before, after)
    async with session_scope() as session:
        rows = list(
            (
                await session.execute(
                    select(AuditLogEntry).where(AuditLogEntry.event_type == AuditEventType.SUBSCRIPTION_EXTENDED)
                )
            ).scalars()
        )
    assert len(rows) == 1 and rows[0].actor_telegram_id == ADMIN_TG_ID, [(r.event_type, r.details) for r in rows]
    assert rows[0].shop_bot_id is not None, "تمدیدِ تک‌نفری هم به همان ربات وصل است"
    assert "۷ روز" in (rows[0].details or ""), rows[0].details

    # /cancel باید حالت را پاک کند و بی‌اثر باشد
    await admin.tap(f"owner_dossier_extend:{owner_pk}")
    await admin.say("/cancel")
    await admin.say("۳")
    assert await _end_date() == after, "بعد ازِ لغو، عددِ بعدی تمدید نمی‌کند"
    print("PASS test_extend_single_owner_flow")


async def test_handcrafted_ids_and_deleted_account(main_dp) -> None:
    await _seed_rich_shop()
    owner_pk = await _owner_pk(OWNER_TG_ID)
    admin = Chat(main_dp, ADMIN_TG_ID)
    for data in ("owner_dossier:abc", "owner_dossier:0", "owner_dossier_refresh:-3", "owner_dossier_extend:1e9"):
        await admin.tap(data)
        assert admin.last_toast["text"] == texts.OWNER_DOSSIER_STALE, (data, admin.last_toast)
    assert not admin.edits, "کال‌بکِ دست‌کاری‌شده هیچ صفحه‌ای نمی‌سازد"

    async with session_scope() as session:
        owner = await session.get(ShopOwner, owner_pk)
        owner.is_deleted = True
        owner.deleted_at = NOW
        session.add(owner)
        await session.flush()
    await admin.tap(f"owner_dossier:{owner_pk}")
    flat = callbacks(admin.last_edit_markup)
    assert f"inact_restore:{owner_pk}" in flat and f"inact_purge:{owner_pk}" in flat, flat
    assert f"inact_deactivate:{owner_pk}" not in flat, "حسابِ بسته دوباره غیرفعال نمی‌شود"
    assert "🧊 حساب بسته شده" in admin.last_edit_text, admin.last_edit_text
    before = len(admin.edits)
    await admin.tap(f"owner_dossier_extend:{owner_pk}")
    assert admin.last_toast["text"] == texts.OWNER_DOSSIER_EXTEND_DELETED, admin.last_toast
    assert len(admin.edits) == before, "تمدید رویِ حسابِ بسته ⇒ صفر پیامِ تازه"
    print("PASS test_handcrafted_ids_and_deleted_account")


async def test_keyboard_budget_and_detail_card_button() -> None:
    await _seed_rich_shop()
    owner_pk = await _owner_pk(OWNER_TG_ID)
    async with session_scope() as session:
        data = await owner_dossier_service.build(session, owner_pk, now=NOW)
    for is_super in (True, False):
        flat = callbacks(keyboards.owner_dossier_keyboard(owner_pk, data, is_super=is_super))
        for value in flat:
            assert len(value.encode("utf-8")) <= 64, value
        widths = [len(row) for row in keyboards.owner_dossier_keyboard(owner_pk, data, is_super=is_super).inline_keyboard]
        assert max(widths) <= 2 and all(width == 2 for width in widths[:-1]), widths
    detail = callbacks(keyboards.admin_owner_detail_keyboard(owner_pk, await _bot_of(owner_pk)))
    assert f"owner_dossier:{owner_pk}" in detail, detail
    from app.bots.main_bot import router as main_router

    labels = {b.text for row in keyboards.admin_panel_keyboard(True).keyboard for b in row}
    assert texts.OWNER_DOSSIER_BUTTON not in labels, "ورودیِ پرونده فقط دکمهٔ اینلاین است، نه دکمهٔ منو"
    assert texts.OWNER_DOSSIER_BUTTON not in main_router._KNOWN_MENU_BUTTONS
    print("PASS test_keyboard_budget_and_detail_card_button")


async def _bot_of(owner_pk: int) -> ShopBot:
    async with session_scope() as session:
        return (await session.execute(select(ShopBot).where(ShopBot.shop_owner_id == owner_pk))).scalar_one()


async def main() -> None:
    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    await test_build_reads_every_section()
    await test_build_is_read_only_and_bounded()
    await test_missing_bot_and_owner_do_not_break()
    await test_text_is_persian_and_leaks_nothing()
    await test_panel_flow_from_owner_card(main_dp)
    await test_operator_scope_and_super_rows(main_dp)
    await test_extend_single_owner_flow(main_dp)
    await test_handcrafted_ids_and_deleted_account(main_dp)
    await test_keyboard_budget_and_detail_card_button()
    print("📊 نتیجه: ۹ تستِ پ۶۷ (پروندهٔ کاملِ کاربر) پاس شد · جمع‌آوری/فقط‌خواندنی/لبه‌ها/متن/پنل/دامنه/تمدید/دست‌کاری/کیبورد")


if __name__ == "__main__":
    asyncio.run(main())
