"""
تست: CRMِ فروشگاه‌دار (فازِ ۴-ج) — بخش‌بندیِ قاعده‌محور، کارتِ مشتری، یادداشت/برچسب، «پیام به این بخش».

پوشش:
۱. قاعده‌هایِ بخش‌بندی دقیقاً روی مرزها: ۴۵ روز (هنوز فعال) در برابرِ ۴۵ روز و یک ثانیه (ریزش)، ۳ سفارش
   (وفادار) در برابرِ ۲، ۷ روزِ اولین حضور (جدید) در برابرِ ۷ روز و یک ثانیه (بدونِ خرید).
۲. افراز بودن: هر مشتری دقیقاً توی یه بخش؛ جمعِ شمارش‌ها = تعدادِ مشتری‌ها.
۳. فقط سفارشِ «موفق» (تاییدشده/در حالِ آماده‌سازی/ارسال‌شده/تکمیل‌شده) حساب می‌شه؛ ردشده/منقضی/لغو/در
   انتظار/منتظرِ تاییدِ مشتری نه. دیتایِ فروشگاهِ دیگه هیچ‌وقت قاطی نمی‌شه.
۴. اعتبارسنجیِ یادداشت (≤۱۰۰۰) و برچسب (≤۵ تا، هر کدوم ≤۲۰ حرف، نرمال‌سازی و حذفِ تکراری).
۵. پنل: نمایِ کلی، فهرستِ بخش (صفحه‌بندی، صفحه‌یِ خارج از محدوده clamp می‌شه)، کارتِ مشتری، یادداشت/برچسب
   (اعتبارسنجی، پاک‌کردن)، دکمه‌یِ منو وسطِ FSM.
۶. یادداشت/برچسبِ CRM هیچ‌وقت به پرامپتِ رباتِ مشتری نمی‌رسه.
۷. «📣 پیام به این بخش»: فقط اعضایِ همون بخش پیام می‌گیرن؛ فهرستِ بخش به «📣 پیام به مشتری‌ها»یِ بعدی نشت نمی‌کنه.
۸. ایزوله‌یِ چندمستاجری + غیرفروشگاه‌دار؛ شناسه/بخشِ جعلی بی‌خطر رد می‌شه.
۹. همه‌یِ دکمه‌هایِ پنل (از جمله دکمه‌هایِ تازه) توی لیستِ escape هستن.

اجرا: python3 tests_manual/test_crm.py
"""
from __future__ import annotations

import asyncio
import datetime
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402
from sqlalchemy import select  # noqa: E402

from harness import FakeSession, build_test_dispatchers, register_fake_shop_bot, reset_database  # noqa: E402
from phase4_helpers import Chat, FakeAi, add_customer, add_order, callbacks, patched_ai, reply_keyboard_texts, set_ai, wallet_transactions  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot import keyboards, texts  # noqa: E402
from app.bots.main_bot import router as main_router  # noqa: E402
from app.bots.main_bot.handlers import crm as crm_handlers  # noqa: E402
from app.bots.shop_bot.handlers import customer as customer_handlers  # noqa: E402
from app.database.models import Customer, OrderStatus, TenantMode, WalletTransactionReason  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import crm_service, shop_bot_service  # noqa: E402

OWNER_TG_ID = 994001
SHOP_BOT_TG_ID = 994002
CUSTOMER_TG_ID = 994003
OTHER_OWNER_TG_ID = 994011
OTHER_SHOP_BOT_TG_ID = 994012
STRANGER_TG_ID = 994021

UTC = datetime.timezone.utc
TG = {
    "loyal": 994101,
    "active": 994102,
    "churning": 994103,
    "new": 994104,
    "no_purchase": 994105,
    "failed_only": 994106,
    "dormant_loyal": 994107,
    "boundary_loyal": 994108,
}
EXPECTED_SEGMENT = {
    "loyal": "loyal",
    "active": "active",
    "churning": "churning",
    "new": "new",
    "no_purchase": "no_purchase",
    "failed_only": "no_purchase",
    "dormant_loyal": "churning",
    "boundary_loyal": "loyal",
}
EXPECTED_COUNTS = {"loyal": 2, "active": 1, "new": 1, "churning": 2, "no_purchase": 2}
PHASE4_BUTTONS = {"🧩 سوال‌هایِ بی‌جواب", "📚 پرسش‌وپاسخ‌هایِ تاییدشده", "👥 مشتری‌ها", "🧮 حسابداری", "💬 دستیارِ مدیریتی"}


async def _seed() -> int:
    await reset_database()
    return await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)


async def _seed_customers(shop_bot_id: int) -> tuple[dict[str, int], datetime.datetime]:
    """۸ مشتری با زمان‌ها و سفارش‌هایِ کنترل‌شده (نگاشتِ مورد انتظار: EXPECTED_SEGMENT). now رو هم برمی‌گردونه."""
    now = datetime.datetime.now(UTC)

    def d(days: int) -> datetime.datetime:
        return now - datetime.timedelta(days=days)

    ids: dict[str, int] = {}
    ids["loyal"] = await add_customer(shop_bot_id, TG["loyal"], "مشتریِ وفادار", "loyal_user", first_seen_at=d(60), last_message_at=d(2))
    for days in (10, 8, 5):
        await add_order(shop_bot_id, ids["loyal"], status=OrderStatus.CONFIRMED, value=100_000, created_at=d(days))

    ids["active"] = await add_customer(shop_bot_id, TG["active"], "مشتریِ فعال", None, first_seen_at=d(30), last_message_at=d(20))
    await add_order(shop_bot_id, ids["active"], status=OrderStatus.COMPLETED, value=50_000, created_at=d(20))

    ids["churning"] = await add_customer(
        shop_bot_id, TG["churning"], "مشتریِ در حالِ ریزش", None, first_seen_at=d(150), last_message_at=d(90)
    )
    for _ in range(2):
        await add_order(shop_bot_id, ids["churning"], status=OrderStatus.SHIPPED, value=80_000, created_at=d(100))

    ids["new"] = await add_customer(shop_bot_id, TG["new"], "مشتریِ جدید", None, first_seen_at=d(2), last_message_at=d(1))
    ids["no_purchase"] = await add_customer(
        shop_bot_id, TG["no_purchase"], "مشتریِ بدونِ خرید", None, first_seen_at=d(30), last_message_at=d(29)
    )

    ids["failed_only"] = await add_customer(
        shop_bot_id, TG["failed_only"], "فقط سفارشِ ناموفق", None, first_seen_at=d(40), last_message_at=d(1)
    )
    for status in (
        OrderStatus.REJECTED,
        OrderStatus.EXPIRED,
        OrderStatus.CANCELLED,
        OrderStatus.PENDING,
        OrderStatus.AWAITING_CUSTOMER_CONFIRMATION,
    ):
        await add_order(shop_bot_id, ids["failed_only"], status=status, value=500_000, created_at=d(3))

    ids["dormant_loyal"] = await add_customer(
        shop_bot_id, TG["dormant_loyal"], "وفادارِ خوابیده", None, first_seen_at=d(200), last_message_at=d(60)
    )
    for days in (70, 65, 60):
        await add_order(shop_bot_id, ids["dormant_loyal"], status=OrderStatus.CONFIRMED, value=10_000, created_at=d(days))

    ids["boundary_loyal"] = await add_customer(
        shop_bot_id, TG["boundary_loyal"], "وفادارِ مرزی", None, first_seen_at=d(200), last_message_at=d(44)
    )
    for _ in range(3):
        await add_order(shop_bot_id, ids["boundary_loyal"], status=OrderStatus.CONFIRMED, value=20_000, created_at=d(100))
    return ids, now


# =============================================================================
# ۱ و ۴. منطقِ خالص
# =============================================================================
def test_pure_classification_boundaries_and_partition() -> None:
    now = datetime.datetime(2026, 10, 5, 12, 0, tzinfo=UTC)

    def ago(days: int, seconds: int = 0) -> datetime.datetime:
        return now - datetime.timedelta(days=days, seconds=seconds)

    classify = crm_service.classify
    assert crm_service.ACTIVITY_WINDOW_DAYS == 45 and crm_service.NEW_WINDOW_DAYS == 7 and crm_service.LOYAL_MIN_ORDERS == 3
    # وفادار/فعال/ریزش روی مرزِ ۴۵ روز و ۳ سفارش
    assert classify(3, ago(45), ago(60), now) == "loyal", "دقیقاً ۴۵ روز هنوز فعاله"
    assert classify(3, ago(45, 1), ago(60), now) == "churning", "۴۵ روز و یک ثانیه = ریزش"
    assert classify(2, ago(1), ago(60), now) == "active" and classify(1, ago(45), ago(60), now) == "active"
    assert classify(1, ago(46), ago(60), now) == "churning"
    assert classify(7, None, ago(60), now) == "churning", "سابقه‌یِ خرید ولی بدونِ هیچ فعالیتِ ثبت‌شده"
    assert classify(5, ago(0), None, now) == "loyal"
    # جدید/بدونِ خرید روی مرزِ ۷ روز
    assert classify(0, ago(1), ago(7), now) == "new", "دقیقاً ۷ روز هنوز جدیده"
    assert classify(0, ago(1), ago(7, 1), now) == "no_purchase"
    assert classify(0, None, None, now) == "no_purchase"
    # بدونِ سفارشِ موفق، فعالیتِ تازه هم کمکی نمی‌کنه
    assert classify(0, ago(0), ago(300), now) == "no_purchase"

    assert crm_service.latest_activity(None, None) is None
    assert crm_service.latest_activity(ago(5), ago(2)) == ago(2) and crm_service.latest_activity(ago(1), ago(9)) == ago(1)
    naive = datetime.datetime(2026, 10, 1, 0, 0)
    assert crm_service.latest_activity(naive, None).tzinfo is not None, "زمانِ بدونِ منطقه‌یِ زمانی UTC فرض می‌شه"

    # افراز: هر مشتری دقیقاً یه بخش؛ جمعِ شمارش‌ها = کل
    members = [
        crm_service.make_stat(
            i, 1000 + i, f"n{i}", None, ago(60 if i % 2 else 3), ago(i), i % 4, i * 1000, ago(i + 1) if i % 4 else None, now
        )
        for i in range(1, 41)
    ]
    parts = crm_service.partition(members)
    assert set(parts) == set(crm_service.SEGMENT_KEYS)
    assert sum(len(v) for v in parts.values()) == 40
    assert sorted(s.customer_id for v in parts.values() for s in v) == list(range(1, 41)), "هیچ مشتری‌ای تکراری یا گم نمی‌شه"
    assert crm_service.segment_counts(members) == {key: len(parts[key]) for key in crm_service.SEGMENT_KEYS}
    for segment_members in parts.values():
        stamps = [(s.last_activity or datetime.datetime(1970, 1, 1, tzinfo=UTC)).timestamp() for s in segment_members]
        assert stamps == sorted(stamps, reverse=True), "داخلِ هر بخش تازه‌ترین فعالیت اول"

    # صفحه‌بندی
    twenty = [crm_service.make_stat(i, 1000 + i, None, None, ago(60), ago(i), 0, 0, None, now) for i in range(1, 21)]
    page, number, total_pages = crm_service.paginate(twenty, 0)
    assert (len(page), number, total_pages) == (8, 0, 3)
    page, number, total_pages = crm_service.paginate(twenty, 99)
    assert (len(page), number, total_pages) == (4, 2, 3), "صفحه‌یِ خارج از محدوده به آخرین صفحه clamp می‌شه"
    assert crm_service.paginate(twenty, -3)[1] == 0
    assert crm_service.paginate([], 5) == ([], 0, 1)

    print("✅ test_pure_classification_boundaries_and_partition PASSED")


def test_pure_tags_and_notes_validation() -> None:
    parse = crm_service.parse_tags
    assert parse("vip, پرمصرف، #تهران") == ["vip", "پرمصرف", "تهران"], "جداکننده‌هایِ فارسی/انگلیسی و # اولِ برچسب"
    assert parse("VIP,vip") == ["vip"], "تکراری (بعد از نرمال‌سازی) یکی می‌شه"
    assert parse("a;b؛c\nd") == ["a", "b", "c", "d"]
    assert parse("۱۲۳, ك") == ["123", "ک"], "رقمِ فارسی و «ك» عربی نرمال می‌شن"
    assert parse("#a, ##b, # ,c") == ["a", "b", "c"] and parse("x#y") == ["x#y"]
    assert parse("") == [] and parse(None) == [] and parse(" , ,; ") == []
    assert len(parse("a,b,c,d,e")) == crm_service.TAGS_MAX_COUNT == 5
    assert crm_service.normalize_tag("  #VIP  ") == "vip" and crm_service.normalize_tag("a   b") == "a b"
    for raw, code in (("a,b,c,d,e,f", "too_many_tags"), ("x" * 21, "tag_too_long")):
        try:
            parse(raw)
            raise AssertionError("باید خطا می‌داد")
        except crm_service.CrmError as exc:
            assert exc.code == code
    assert parse("x" * 20) == ["x" * 20]
    assert crm_service.split_stored_tags("a,b,,c") == ["a", "b", "c"] and crm_service.split_stored_tags(None) == []

    note = crm_service.validate_note
    assert note("  hi\nthere  ") == "hi\nthere", "فاصله‌یِ اطراف بریده، خطِ جدیدِ داخلی حفظ می‌شه"
    assert note(None) is None and note("") is None and note("   \n ") is None, "خالی = پاک‌کردن"
    assert note("a\x00b\x07c") == "abc", "کاراکترِ کنترلی حذف می‌شه"
    assert len(note("ن" * 1000)) == 1000
    try:
        note("ن" * 1001)
        raise AssertionError("باید خطا می‌داد")
    except crm_service.CrmError as exc:
        assert exc.code == "note_too_long", "یادداشتِ بلند بریده نمی‌شه؛ رد می‌شه تا فروشگاه‌دار بی‌صدا چیزی از دست نده"

    print("✅ test_pure_tags_and_notes_validation PASSED")


# =============================================================================
# ۲ و ۳. دیتابیس
# =============================================================================
async def test_db_segments_failed_orders_and_isolation() -> None:
    shop_bot_id = await _seed()
    other_shop_bot_id = await seed_usable_shop(OTHER_OWNER_TG_ID, OTHER_SHOP_BOT_TG_ID)
    ids, now = await _seed_customers(shop_bot_id)
    other_customer = await add_customer(other_shop_bot_id, 994999, "مشتریِ فروشگاهِ دیگه", None, first_seen_at=now, last_message_at=now)
    await add_order(other_shop_bot_id, other_customer, status=OrderStatus.CONFIRMED, value=777_000, created_at=now)

    async with session_scope() as session:
        stats, truncated = await crm_service.load_stats(session, shop_bot_id, now)
        single, _ = await crm_service.load_stats(session, shop_bot_id, now, customer_id=ids["loyal"])
        foreign, _ = await crm_service.load_stats(session, shop_bot_id, now, customer_id=other_customer)
    assert not truncated and len(stats) == 8, "فقط ۸ مشتریِ همین فروشگاه"
    by_telegram = {stat.telegram_id: stat for stat in stats}
    for name, expected_segment in EXPECTED_SEGMENT.items():
        actual = by_telegram[TG[name]].segment
        assert actual == expected_segment, f"{name} باید «{expected_segment}» باشه، نه «{actual}»"

    loyal = by_telegram[TG["loyal"]]
    assert loyal.success_count == 3 and loyal.net_toman == 300_000
    failed = by_telegram[TG["failed_only"]]
    assert failed.success_count == 0 and failed.net_toman == 0, "ردشده/منقضی/لغو/معلق/منتظرِ تاییدِ مشتری موفق حساب نمی‌شن"
    assert by_telegram[TG["dormant_loyal"]].last_activity == now - datetime.timedelta(days=60), "فعالیت = دیرتریِن بینِ پیام و سفارش"
    assert by_telegram[TG["churning"]].success_count == 2 and by_telegram[TG["churning"]].net_toman == 160_000

    assert crm_service.segment_counts(stats) == EXPECTED_COUNTS | {"no_purchase": 2}
    assert sum(crm_service.segment_counts(stats).values()) == len(stats)
    assert len(single) == 1 and single[0].customer_id == ids["loyal"]
    assert foreign == [], "مشتریِ فروشگاهِ دیگه با شناسه‌اش هم از این فروشگاه خونده نمی‌شه"

    print("✅ test_db_segments_failed_orders_and_isolation PASSED")


# =============================================================================
# ۵. پنل
# =============================================================================
async def test_overview_segment_screens_card_and_pagination(main_dp) -> None:
    shop_bot_id = await _seed()
    ids, now = await _seed_customers(shop_bot_id)
    owner = Chat(main_dp, OWNER_TG_ID)

    await owner.say("👥 مشتری‌ها")
    assert owner.last_text == texts.crm_overview_text(EXPECTED_COUNTS, 8, False)
    assert callbacks(owner.last_markup) == [f"crm_seg:{key}:0" for key in EXPECTED_COUNTS]
    button_texts = [button.text for row in owner.last_markup.inline_keyboard for button in row]
    assert "💎 وفادار (2)" in button_texts and "⚠️ در حالِ ریزش (2)" in button_texts and "🆕 جدید (1)" in button_texts

    # callbackهایِ بخش: معتبر، خارج از محدوده (clamp) و جعلی
    assert crm_handlers._parse_segment_callback("crm_seg:loyal:2") == ("loyal", 2)
    for bad in ("crm_seg:evil:0", "crm_seg:loyal:x", "crm_seg:loyal", "crm_seg:loyal:-1", "crm_seg:loyal:1:2", "", None):
        assert crm_handlers._parse_segment_callback(bad) is None, bad
    for good in ("crm_seg:loyal:0", "crm_seg:loyal:99", "crm_seg:new:0", "crm_home"):
        await owner.tap(good)
        assert owner.last_toast.get("show_alert") in (None, False), good
    for bad in ("crm_seg:evil:0", "crm_seg:loyal:x"):
        await owner.tap(bad)
        assert owner.last_toast["text"] == texts.CRM_STALE_BUTTON and owner.last_toast["show_alert"], bad

    # متنِ فهرست و ترتیبِ اعضا (تازه‌ترین فعالیت اول)
    async with session_scope() as session:
        stats, _ = await crm_service.load_stats(session, shop_bot_id, now)
        shop_bot = await shop_bot_service.get_by_id(session, shop_bot_id)
        card_text, card_keyboard = await crm_handlers._card_payload(session, shop_bot, ids["loyal"])
        missing = await crm_handlers._card_payload(session, shop_bot, 999_999)
    loyal_members = crm_service.partition(stats)["loyal"]
    assert [m.telegram_id for m in loyal_members] == [TG["loyal"], TG["boundary_loyal"]]
    listing = texts.crm_segment_text("loyal", loyal_members, 2, 0, 1, crm_service.PAGE_SIZE)
    assert "مشتریِ وفادار (@loyal_user)" in listing and "وفادارِ مرزی" in listing and "300,000 تومان" in listing
    assert listing.index("مشتریِ وفادار") < listing.index("وفادارِ مرزی")

    # کارتِ مشتری
    for expected in (
        "👤 مشتریِ وفادار (@loyal_user)",
        "بخش: 💎 وفادار",
        "🧾 سفارشِ موفق: 3 — 💰 خریدِ خالص: 300,000 تومان",
        "🏷 برچسب‌ها: —",
        "📝 یادداشت: —",
        "آخرین سفارش‌ها:",
        "✅ تاییدشده — سفارش — 100,000 تومان",
    ):
        assert expected in card_text, f"کارت باید «{expected}» رو داشته باشه:\n{card_text}"
    loyal_id = ids["loyal"]
    # P18 · B4: «💬 دیدنِ گفتگو» و «🚫 بلاک» به کارتِ مشتری اضافه شدند
    assert callbacks(card_keyboard) == [
        f"crm_note:{loyal_id}",
        f"crm_tags:{loyal_id}",
        f"crm_conv:{loyal_id}:0",
        f"crm_block:{loyal_id}",
        f"crm_sum:{loyal_id}",
        "crm_seg:loyal:0",
    ]
    assert missing is None

    # صفحه‌بندی: ۲۰ مشتریِ «بدونِ خرید» دیگه → ۲۲ نفر = ۳ صفحه
    for index in range(20):
        await add_customer(
            shop_bot_id,
            994200 + index,
            f"بدونِ خریدِ {index}",
            None,
            first_seen_at=now - datetime.timedelta(days=30),
            last_message_at=now - datetime.timedelta(days=29, hours=index),
        )
    async with session_scope() as session:
        stats, _ = await crm_service.load_stats(session, shop_bot_id, now)
    members = crm_service.partition(stats)["no_purchase"]
    assert len(members) == 22
    page_members, page, total_pages = crm_service.paginate(members, 1)
    keyboard = keyboards.crm_segment_keyboard("no_purchase", page_members, page, total_pages, crm_service.PAGE_SIZE)
    page_callbacks = callbacks(keyboard)
    assert sum(1 for data in page_callbacks if data.startswith("crm_card:")) == 8
    assert "crm_seg:no_purchase:0" in page_callbacks and "crm_seg:no_purchase:2" in page_callbacks and "noop" in page_callbacks
    assert page_callbacks[-2:] == ["crm_bcast:no_purchase", "crm_home"]
    await owner.tap("crm_seg:no_purchase:1")
    assert owner.last_toast.get("show_alert") in (None, False)

    print("✅ test_overview_segment_screens_card_and_pagination PASSED")


async def test_card_notes_and_tags_flow(main_dp) -> None:
    shop_bot_id = await _seed()
    ids, _now = await _seed_customers(shop_bot_id)
    cid = ids["loyal"]
    owner = Chat(main_dp, OWNER_TG_ID)

    async def stored() -> Customer:
        async with session_scope() as session:
            return (await session.execute(select(Customer).where(Customer.id == cid))).scalar_one()

    # --- یادداشت ---
    await owner.tap(f"crm_note:{cid}")
    assert owner.last_text == texts.CRM_NOTE_ASK and callbacks(owner.last_markup) == [f"crm_note_clear:{cid}"]
    await owner.say("ن" * 1001)
    assert owner.last_text == texts.CRM_NOTE_TOO_LONG and (await stored()).crm_notes is None, "رد می‌شه و state می‌مونه"
    await owner.say("  مشتریِ پرسروصدا\nهمیشه تخفیف می‌خواد  ")
    assert owner.sent[-2]["text"] == texts.CRM_NOTE_SAVED
    assert (await stored()).crm_notes == "مشتریِ پرسروصدا\nهمیشه تخفیف می‌خواد"
    assert "📝 یادداشت: مشتریِ پرسروصدا\nهمیشه تخفیف می‌خواد" in owner.last_text, "بعد از ذخیره کارتِ به‌روز فرستاده می‌شه"
    assert callbacks(owner.last_markup)[0] == f"crm_note:{cid}"

    await owner.tap(f"crm_note:{cid}")
    await owner.say("   ")  # فقط فاصله = پاک‌کردن
    assert owner.sent[-2]["text"] == texts.CRM_NOTE_CLEARED and (await stored()).crm_notes is None

    await owner.tap(f"crm_note:{cid}")
    await owner.say("یادداشتِ دوباره")
    await owner.tap(f"crm_note_clear:{cid}")
    assert owner.last_toast["text"] == texts.CRM_NOTE_CLEARED and (await stored()).crm_notes is None
    assert "📝 یادداشت: —" in owner.last_text

    # --- برچسب ---
    await owner.tap(f"crm_tags:{cid}")
    assert owner.last_text == texts.CRM_TAGS_ASK and callbacks(owner.last_markup) == [f"crm_tags_clear:{cid}"]
    await owner.say("a,b,c,d,e,f")
    assert owner.last_text == texts.CRM_TOO_MANY_TAGS
    await owner.say("x" * 21)
    assert owner.last_text == texts.CRM_TAG_TOO_LONG and (await stored()).crm_tags is None
    await owner.say("vip، پرمصرف، #تهران، VIP")
    assert owner.sent[-2]["text"] == texts.CRM_TAGS_SAVED
    assert (await stored()).crm_tags == "vip,پرمصرف,تهران"
    assert "🏷 برچسب‌ها: #vip #پرمصرف #تهران" in owner.last_text

    await owner.tap(f"crm_tags_clear:{cid}")
    assert owner.last_toast["text"] == texts.CRM_TAGS_CLEARED and (await stored()).crm_tags is None
    await owner.tap(f"crm_tags:{cid}")
    await owner.say(" , ; ")
    assert owner.sent[-2]["text"] == texts.CRM_TAGS_CLEARED, "ورودیِ بدونِ برچسب = پاک‌کردن"

    print("✅ test_card_notes_and_tags_flow PASSED")


async def test_crm_notes_and_tags_never_reach_customer_ai_prompt(main_bot) -> None:
    shop_bot_id = await _seed()
    await add_customer(shop_bot_id, CUSTOMER_TG_ID, "مشتری", "someone", crm_notes="SECRET_NOTE_XYZ", crm_tags="secret_tag")
    fake = set_ai(FakeAi(chat_reply="سلام! چه کمکی از من برمیاد؟"))
    bot = Bot(token=f"{SHOP_BOT_TG_ID}:FAKE", session=FakeSession())

    for text in ("سلام", "یه سوال دیگه"):
        async with session_scope() as session:
            await customer_handlers._generate_and_send_reply(session, shop_bot_id, CUSTOMER_TG_ID, text, bot, main_bot)
        await asyncio.sleep(0.2)

    assert len(fake.chat_calls) == 2
    for system_prompt, history, user_message in fake.chat_calls:
        everything = system_prompt + user_message + " ".join(item["content"] for item in history)
        assert "SECRET_NOTE_XYZ" not in everything and "secret_tag" not in everything, "یادداشت/برچسبِ CRM فقط برایِ فروشگاه‌داره"
    assert all("SECRET_NOTE_XYZ" not in m["text"] for m in bot.session.sent_messages)

    print("✅ test_crm_notes_and_tags_never_reach_customer_ai_prompt PASSED")


async def test_other_owner_and_strangers_cannot_touch_crm(main_dp) -> None:
    shop_bot_id = await _seed()
    other_shop_bot_id = await seed_usable_shop(OTHER_OWNER_TG_ID, OTHER_SHOP_BOT_TG_ID)
    ids, _now = await _seed_customers(shop_bot_id)
    cid = ids["loyal"]

    intruder = Chat(main_dp, OTHER_OWNER_TG_ID)
    for action in ("crm_card", "crm_note", "crm_tags", "crm_note_clear", "crm_tags_clear", "crm_sum", "crm_sum_go"):
        await intruder.tap(f"{action}:{cid}")
        assert intruder.last_toast["text"] == texts.CRM_NOT_FOUND and intruder.last_toast["show_alert"], action
    for forged in ("crm_card:abc", "crm_card:-1", "crm_note:", "crm_sum_go:999999"):
        await intruder.tap(forged)
        assert intruder.last_toast["text"] == texts.CRM_NOT_FOUND, forged
    await intruder.tap("crm_bcast:loyal")
    assert intruder.last_toast["text"] == texts.CRM_BROADCAST_EMPTY and intruder.last_toast["show_alert"], (
        "مشتری‌هایِ فروشگاهِ دیگه به این فروشگاه‌دار نمی‌رسه"
    )
    await intruder.tap("crm_seg:loyal:0")
    assert intruder.last_toast["text"] == texts.CRM_SEGMENT_EMPTY and intruder.last_toast["show_alert"]
    await intruder.say("👥 مشتری‌ها")
    assert intruder.last_text == texts.CRM_EMPTY

    stranger = Chat(main_dp, STRANGER_TG_ID)
    await stranger.tap(f"crm_card:{cid}")
    assert stranger.last_toast["show_alert"]
    await stranger.say("👥 مشتری‌ها")
    assert stranger.last_text == texts.SHOP_BOT_NOT_SET_UP

    owner = Chat(main_dp, OWNER_TG_ID)
    await owner.tap("crm_bcast:evil")
    assert owner.last_toast["text"] == texts.CRM_STALE_BUTTON and owner.last_toast["show_alert"]

    async with session_scope() as session:
        customer = (await session.execute(select(Customer).where(Customer.id == cid))).scalar_one()
        assert customer.crm_notes is None and customer.crm_tags is None
    assert await wallet_transactions(WalletTransactionReason.CRM_SUMMARY) == []
    assert other_shop_bot_id

    print("✅ test_other_owner_and_strangers_cannot_touch_crm PASSED")


async def test_empty_shop_overview_and_segments(main_dp) -> None:
    await _seed()
    owner = Chat(main_dp, OWNER_TG_ID)

    await owner.say("👥 مشتری‌ها")
    assert owner.last_text == texts.CRM_EMPTY and owner.last_markup is None
    await owner.tap("crm_seg:loyal:0")
    assert owner.last_toast["text"] == texts.CRM_SEGMENT_EMPTY and owner.last_toast["show_alert"]
    await owner.tap("crm_bcast:loyal")
    assert owner.last_toast["text"] == texts.CRM_BROADCAST_EMPTY and owner.last_toast["show_alert"]
    await owner.tap("crm_home")
    assert owner.last_toast.get("show_alert") in (None, False)

    print("✅ test_empty_shop_overview_and_segments PASSED")


# =============================================================================
# ۷. پیام به این بخش
# =============================================================================
async def test_segment_broadcast_reaches_only_that_segment(main_dp, bot_manager) -> None:
    shop_bot_id = await _seed()
    await _seed_customers(shop_bot_id)
    shop_bot_instance = Bot(token=f"{SHOP_BOT_TG_ID}:FAKE", session=FakeSession())
    register_fake_shop_bot(bot_manager, shop_bot_id, shop_bot_instance)
    owner = Chat(main_dp, OWNER_TG_ID)
    message = "پیشنهادِ ویژه برایِ مشتریانِ وفادار 🎁"

    await owner.tap("crm_bcast:loyal")
    assert owner.last_text == texts.crm_broadcast_ask(texts.CRM_SEGMENT_LABELS["loyal"], 2)
    await owner.say(message)
    assert owner.last_text == texts.customer_broadcast_preview(message, 2), "پیش‌نمایش تعدادِ اعضایِ بخش رو نشون می‌ده، نه کلِ مشتری‌ها"
    # P21-D (F2): «⏰ برایِ بعد از» به این کیبورد اضافه شد
    assert callbacks(owner.last_markup) == [
        "customer_broadcast_confirm",
        "customer_broadcast_schedule",
        "customer_broadcast_cancel",
    ]
    assert shop_bot_instance.session.sent_messages == [], "تا تایید نشده چیزی نمی‌ره"

    await owner.tap("customer_broadcast_confirm")
    await asyncio.sleep(0.6)
    sent = shop_bot_instance.session.sent_messages
    assert len(sent) == 2 and {m["chat_id"] for m in sent} == {TG["loyal"], TG["boundary_loyal"]}, "فقط اعضایِ بخشِ وفادار"
    assert all(m["text"] == message for m in sent)
    assert owner.last_text == texts.customer_broadcast_sent_confirmation(2, 2)

    # لغو: چیزی نمی‌ره
    shop_bot_instance.session.sent_messages.clear()
    await owner.tap("crm_bcast:active")
    await owner.say("پیامِ لغوشده")
    await owner.tap("customer_broadcast_cancel")
    await asyncio.sleep(0.2)
    assert shop_bot_instance.session.sent_messages == []

    print("✅ test_segment_broadcast_reaches_only_that_segment PASSED")


async def test_segment_ids_never_leak_into_all_customers_broadcast(main_dp, bot_manager) -> None:
    shop_bot_id = await _seed()
    await _seed_customers(shop_bot_id)
    register_fake_shop_bot(bot_manager, shop_bot_id, Bot(token=f"{SHOP_BOT_TG_ID}:FAKE", session=FakeSession()))
    owner = Chat(main_dp, OWNER_TG_ID)

    await owner.tap("crm_bcast:new")  # فهرستِ ۱ نفره توی state می‌مونه
    await owner.say("📣 پیام به مشتری‌ها")  # دکمه‌یِ منو: state پاک می‌شه و جریانِ «همه» از صفر شروع می‌شه
    await owner.say("پیامِ همگانی")
    assert owner.last_text == texts.customer_broadcast_preview("پیامِ همگانی", 8), "«همه» باید ۸ مشتری رو بگیره، نه ۱ نفرِ بخشِ قبلی"

    print("✅ test_segment_ids_never_leak_into_all_customers_broadcast PASSED")


async def test_menu_buttons_escape_crm_states(main_dp) -> None:
    shop_bot_id = await _seed()
    ids, _now = await _seed_customers(shop_bot_id)
    owner = Chat(main_dp, OWNER_TG_ID)

    await owner.tap(f"crm_note:{ids['loyal']}")
    await owner.say("🧮 حسابداری")  # دکمه‌یِ منو وسطِ ثبتِ یادداشت
    assert owner.last_text.startswith("🧮 حسابداری — امروز"), "دکمه‌یِ منو باید کار کنه، نه اینکه به‌عنوانِ یادداشت ذخیره بشه"
    async with session_scope() as session:
        assert (await session.execute(select(Customer).where(Customer.id == ids["loyal"]))).scalar_one().crm_notes is None

    await owner.tap(f"crm_tags:{ids['loyal']}")
    await owner.say("👥 مشتری‌ها")
    assert owner.last_text.startswith("👥 مشتری‌هایِ فروشگاهت")
    async with session_scope() as session:
        assert (await session.execute(select(Customer).where(Customer.id == ids["loyal"]))).scalar_one().crm_tags is None

    print("✅ test_menu_buttons_escape_crm_states PASSED")


def test_all_panel_buttons_are_in_menu_escape_set() -> None:
    owner_buttons: set[str] = set()
    # P18 · C2/C3: «👥 مشتری‌ها» (CRMِ فروش) و «🧮 حسابداری» فقط در پنلِ فروشگاهی‌اند؛
    # پنلِ مشاوره به‌جایشان «💬 گفتگوها و کاربران» را دارد.
    shared_buttons = {"🧩 سوال‌هایِ بی‌جواب", "📚 پرسش‌وپاسخ‌هایِ تاییدشده", "💬 دستیارِ مدیریتی"}
    sales_only_buttons = {"👥 مشتری‌ها", "🧮 حسابداری"}
    for mode in (TenantMode.SALES, TenantMode.CONSULTATION, None):
        mode_buttons = reply_keyboard_texts(keyboards.shop_owner_panel_keyboard(mode))
        assert shared_buttons <= mode_buttons, "دکمه‌هایِ مشترکِ پنلِ هر دو مود"
        if mode == TenantMode.CONSULTATION:
            assert "💬 گفتگوها و کاربران" in mode_buttons
            assert not sales_only_buttons & mode_buttons, "این دو دکمه نباید در مشاوره باشن"
        else:
            assert "👥 مشتری‌ها" in mode_buttons and "🧮 حسابداری" in mode_buttons
        owner_buttons |= mode_buttons
    assert PHASE4_BUTTONS <= reply_keyboard_texts(keyboards.shop_owner_panel_keyboard(TenantMode.SALES))
    admin_buttons = reply_keyboard_texts(keyboards.admin_panel_keyboard(True)) | reply_keyboard_texts(keyboards.admin_panel_keyboard(False))

    missing = (owner_buttons | admin_buttons) - set(main_router._KNOWN_MENU_BUTTONS)
    assert not missing, f"این دکمه‌ها توی _KNOWN_MENU_BUTTONS نیستن و وسطِ FSM به‌عنوانِ متن ذخیره می‌شن: {sorted(missing)}"
    assert "📤 دفترِ کیف‌پول (اکسل)" in reply_keyboard_texts(keyboards.admin_panel_keyboard(True))
    assert "📤 دفترِ کیف‌پول (اکسل)" not in reply_keyboard_texts(keyboards.admin_panel_keyboard(False)), "فقط سوپرادمین"

    print("✅ test_all_panel_buttons_are_in_menu_escape_set PASSED")


async def main() -> None:
    test_pure_classification_boundaries_and_partition()
    test_pure_tags_and_notes_validation()
    test_all_panel_buttons_are_in_menu_escape_set()
    main_dp, _shop_dp, bot_manager, main_bot = build_test_dispatchers()
    with patched_ai():
        await test_db_segments_failed_orders_and_isolation()
        await test_overview_segment_screens_card_and_pagination(main_dp)
        await test_card_notes_and_tags_flow(main_dp)
        await test_crm_notes_and_tags_never_reach_customer_ai_prompt(main_bot)
        await test_other_owner_and_strangers_cannot_touch_crm(main_dp)
        await test_empty_shop_overview_and_segments(main_dp)
        await test_segment_broadcast_reaches_only_that_segment(main_dp, bot_manager)
        await test_segment_ids_never_leak_into_all_customers_broadcast(main_dp, bot_manager)
        await test_menu_buttons_escape_crm_states(main_dp)


if __name__ == "__main__":
    asyncio.run(main())
