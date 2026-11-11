"""پ۵۶ · مواردِ ۲۷ و ۴۱: جست‌وجویِ فروشگاه‌دارها (پنلِ ادمین) و مشتری‌ها (پنلِ فروشگاه‌دار).

پوششِ داده‌شده:
۱. `search_service.normalize_term`: ارقامِ فارسی/عربی، ي/ك/ة، کشیده، ZWNJ، فاصله‌هایِ تکراری،
   حروفِ بزرگ، سقفِ ۶۴ نویسه؛ و فرار‌دادنِ `%`/`_` تا عبارتِ کاربر الگویِ LIKE نسازد.
۲. `crm_service.search_customers`: فقط مشتری‌هایِ *همین* فروشگاه، تطبیقِ نام/نامِ خانوادگی/
   نام‌کاربری/تلفن/شناسهٔ تلگرام، ترتیب، صفحه‌بندی، عبارتِ خالی ⇒ هیچ (نه «همه»).
۳. `shop_owner_service.search_registered`: دامنهٔ ادمینِ عملیاتی پیش ازِ صفحه‌بندی، دامنهٔ تهی
   ⇒ صفر، و ردِ صفحه/اندازهٔ نامعتبر.
۴. جریانِ واقعیِ پنلِ فروشگاه‌دار: دکمه ← پرسش ← نتیجه ← صفحهٔ دوم ← بازِکردنِ کارتِ همان
   مشتری؛ ورودیِ بی‌معنا و «انصراف».
۵. نشتِ بین‌فروشگاهی: عبارتِ مختصِ مشتریِ فروشگاهِ دیگر ⇒ «پیدا نشد»، و کارتِ آن مشتری از راهِ
   کال‌بکِ ساختگی هم باز نمی‌شود.
۶. جریانِ پنلِ ادمین: فهرست ← دکمهٔ جست‌وجو ← نتیجه با صفحه‌گردانیِ جدا ← بازگشت به فهرستِ
   کامل؛ ادمینِ دامنه‌دار فقط دامنهٔ خودش را می‌بیند و شمارِ همان دامنه را.
۷. کیبورد: بودجهٔ ۶۴ بایتی و شماره‌گذاریِ ادامه‌دار در صفحه‌هایِ بعد.
۸. دسترسی: کاربرِ معمولی با کال‌بک‌هایِ ادمین هیچ چیزی نمی‌گیرد.
۹. دکمهٔ بازگشت: «بازگشت به پنل» و «فهرستِ کاملِ فروشگاه‌دارها» حالتِ جست‌وجو را می‌بندند، تا
   متنِ بعدیِ کاربر دوباره جست‌وجو حساب نشود.

اجرا: python3 tests_manual/run_one.py test_p56_search.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402
from sqlalchemy import select  # noqa: E402

from harness import FakeSession, build_test_dispatchers, make_callback_update, make_message_update, reset_database  # noqa: E402
from phase4_helpers import Chat, callbacks  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot import keyboards, texts as main_texts  # noqa: E402
from app.database.models import Customer, ShopOwner  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import admin_role_service, crm_service, customer_service, search_service, shop_owner_service  # noqa: E402

ADMIN_TG_ID = 12345
OPERATOR_TG_ID = 995643
OWNER_A_TG_ID = 995641
SHOP_A_TG_ID = 995651
OWNER_B_TG_ID = 995642
SHOP_B_TG_ID = 995652
OUTSIDER_TG_ID = 995649
MAIN_TOKEN = "560000:FAKE_MAIN_BOT_TOKEN_FOR_P56_TESTING"


async def seed_two_shops() -> tuple[int, int]:
    """دو فروشگاه، هر کدام با مشتری‌هایِ خودش؛ یکی از نام‌ها فقط در فروشگاهِ B است.

    یکِ مشتری هم بدونِ هیچ زیرخطی در نام/نامِ کاربری ساخته می‌شود تا «_» مثلِ نویسهٔ واقعی
    بسنجده شود، نه مثلِ کاراکترِ عامِ LIKE.
    """
    await reset_database()
    shop_a = await seed_usable_shop(OWNER_A_TG_ID, SHOP_A_TG_ID)
    shop_b = await seed_usable_shop(OWNER_B_TG_ID, SHOP_B_TG_ID)
    async with session_scope() as session:
        for index in range(12):
            await customer_service.get_or_create_customer(
                session, shop_a, 6000 + index, f"مشتری{index}", f"shop_a_user_{index}",
                last_name="رضایی" if index % 2 else None,
            )
        await customer_service.get_or_create_customer(session, shop_a, 6200, "بی‌نام", "plainname")
        ali = await customer_service.get_or_create_customer(session, shop_a, 6100, "علی", "ali_rezayi", last_name="محمدی")
        ali.phone_number = "09121234567"
        hidden = await customer_service.get_or_create_customer(session, shop_b, 7000, "سارا", "sara_hidden", last_name="کمالی")
        hidden.phone_number = "09129998877"
        shop_b_id = shop_b
    return shop_a, shop_b_id


async def test_normalization_and_like_escaping() -> None:
    assert search_service.normalize_term("  علی‌  رضایی ") == "علی رضایی"
    # «ي/ك/ة/ى» و کشیده و ZWNJ نرمال می‌شوند؛ «ئ» عمداً دست‌نخورده می‌ماند، چون در فارسی
    # حرفِ مستقلی است («مسئله» با تبدیلِ آن به «مسلیه» غلط می‌شد).
    assert search_service.normalize_term("علي‌رضائى") == "علیرضائی"
    assert search_service.normalize_term("ABC") == "abc"
    assert search_service.normalize_term("۵۰۰۰۰") == "50000"
    assert search_service.normalize_term("٥٠٠٠٠") == "50000"
    assert search_service.normalize_term("a" * 200) == "a" * 64
    assert search_service.normalize_term("   ") == ""

    shop_a, _shop_b = await seed_two_shops()
    async with session_scope() as session:
        for wildcard in ("%", "%%", "%_%", "\\%"):
            rows, total = await crm_service.search_customers(session, shop_a, wildcard)
            assert rows == [] and total == 0, f"کاراکترِ LIKE مثلِ الگو عمل کرد: {wildcard}"
        # «_» یکِ نویسهٔ واقعی در نامِ کاربری است ⇒ فقط همان‌ها را می‌دهد، نه کلِ فهرست.
        rows, total = await crm_service.search_customers(session, shop_a, "_")
        assert total == 13, total
        assert all("_" in (customer.username or "") for customer in rows), [c.username for c in rows]
        plain = (
            await session.execute(select(Customer).where(Customer.shop_bot_id == shop_a, Customer.username == "plainname"))
        ).scalar_one()
        assert plain.id not in {customer.id for customer in rows}, "زیرخط مثلِ کاراکترِ عام رفتار کرد"
        rows, total = await crm_service.search_customers(session, shop_a, "100%مشتری")
        assert total == 0, rows
    print("PASS test_normalization_and_like_escaping")


async def test_customer_search_scoping_and_pages() -> None:
    shop_a, shop_b = await seed_two_shops()
    async with session_scope() as session:
        by_name, name_total = await crm_service.search_customers(session, shop_a, "مشتری۱")
        assert name_total == 3, name_total  # مشتری۱، مشتری۱۰، مشتری۱۱
        by_persian_name, _ = await crm_service.search_customers(session, shop_a, "مشتری1")
        assert {c.id for c in by_persian_name} == {c.id for c in by_name}

        compact, compact_total = await crm_service.search_customers(session, shop_a, "علی محمدی")
        spaced, spaced_total = await crm_service.search_customers(session, shop_a, "علی‌محمدی")
        reversed_order, _ = await crm_service.search_customers(session, shop_a, "محمدی علی")
        assert compact_total == 1 and spaced_total == 1, (compact_total, spaced_total)
        assert [c.id for c in compact] == [c.id for c in spaced] == [c.id for c in reversed_order]

        by_user, user_total = await crm_service.search_customers(session, shop_a, "ALI_REZAYI")
        assert user_total == 1 and by_user[0].username == "ali_rezayi"

        for phone in ("09121234567", "+989121234567", "۰۹۱۲۱۲۳۴۵۶۷", "9121234567"):
            found, found_total = await crm_service.search_customers(session, shop_a, phone)
            assert found_total == 1 and found[0].id == compact[0].id, phone

        by_id, id_total = await crm_service.search_customers(session, shop_a, "6100")
        assert id_total == 1 and by_id[0].telegram_id == 6100

        first_page, total = await crm_service.search_customers(session, shop_a, "مشتری", page=0)
        second_page, _ = await crm_service.search_customers(session, shop_a, "مشتری", page=1)
        assert total == 12 and len(first_page) == crm_service.PAGE_SIZE and len(second_page) == 4
        assert not ({c.id for c in first_page} & {c.id for c in second_page})

        other, other_total = await crm_service.search_customers(session, shop_a, "سارا")
        assert other == [] and other_total == 0, "مشتریِ فروشگاهِ دیگر در جست‌وجو نیست"
        in_b, b_total = await crm_service.search_customers(session, shop_b, "سارا")
        assert b_total == 1 and in_b[0].username == "sara_hidden"

        empty, empty_total = await crm_service.search_customers(session, shop_a, "   ")
        assert empty == [] and empty_total == 0, "عبارتِ خالی نباید کلِ فهرست را برگرداند"
        for bad_page in (-1, "0", None, True):
            try:
                await crm_service.search_customers(session, shop_a, "مشتری", page=bad_page)
            except ValueError:
                pass
            else:
                raise AssertionError(f"صفحهٔ نامعتبر پذیرفته شد: {bad_page!r}")
    print("PASS test_customer_search_scoping_and_pages")


async def test_owner_search_respects_scope() -> None:
    await seed_two_shops()
    async with session_scope() as session:
        owner_a = (await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == OWNER_A_TG_ID))).scalar_one()
        owner_b = (await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == OWNER_B_TG_ID))).scalar_one()

        everyone, everyone_total = await shop_owner_service.search_registered(session, "فروشنده")
        assert everyone_total == 2, everyone_total
        only_a, a_total = await shop_owner_service.search_registered(session, "فروشنده", allowed_owner_ids={owner_a.id})
        assert a_total == 1 and only_a[0].id == owner_a.id
        none, none_total = await shop_owner_service.search_registered(session, "فروشنده", allowed_owner_ids=set())
        assert (none, none_total) == ([], 0)

        by_tg, tg_total = await shop_owner_service.search_registered(session, str(OWNER_B_TG_ID))
        assert tg_total == 1 and by_tg[0].id == owner_b.id
        by_phone, phone_total = await shop_owner_service.search_registered(session, owner_a.phone_number)
        assert phone_total == 1, phone_total
        miss, miss_total = await shop_owner_service.search_registered(session, "چنین کسی نیست")
        assert (miss, miss_total) == ([], 0)
        for bad_page in (-1, "2", None):
            try:
                await shop_owner_service.search_registered(session, "فروشنده", page=bad_page)
            except ValueError:
                pass
            else:
                raise AssertionError("صفحهٔ نامعتبر پذیرفته شد")
    print("PASS test_owner_search_respects_scope")


async def test_crm_search_panel_flow(main_dp) -> None:
    await seed_two_shops()
    owner = Chat(main_dp, OWNER_A_TG_ID)
    await owner.say("👥 مشتری‌ها")
    assert main_texts.CRM_SEARCH_BUTTON in [b.text for row in owner.last_markup.inline_keyboard for b in row]

    await owner.tap("crm_search")
    assert "چه چیزی را بگردم" in owner.last_text, owner.last_text
    await owner.say("علی")
    screen = owner.last_text
    assert "نتیجهٔ جست‌وجویِ «علی»" in screen and "۱ مشتری" in screen, screen
    flat = callbacks(owner.last_markup)
    assert any(value.startswith("crm_card:") for value in flat), flat

    await owner.say("   ")
    assert main_texts.CRM_SEARCH_INVALID in owner.last_text, owner.last_text
    await owner.say("سارا")
    assert "پیدا نشد" in owner.last_text and "بخش‌بندی" not in owner.last_text.splitlines()[0], owner.last_text

    await owner.tap("crm_search")
    await owner.say("مشتری")
    flat = callbacks(owner.last_markup)
    assert "crm_search_page:1" in flat, flat
    await owner.tap("crm_search_page:1")
    second = owner.last_edit_text
    assert "صفحه‌یِ ۲ از ۲" in second and "۹. " in second, second
    target_card = [value for value in callbacks(owner.last_edit_markup) if value.startswith("crm_card:")][0]

    await owner.tap("crm_search")
    await owner.say("انصراف")
    assert main_texts.CRM_SEARCH_CANCELLED in owner.last_text, owner.last_text
    await owner.tap("crm_search_page:0")
    assert owner.last_toast["text"] == main_texts.CRM_STALE_BUTTON, owner.last_toast

    await owner.tap("crm_search")
    await owner.say("مشتری")
    await owner.tap(target_card)
    assert "کارت" in owner.last_edit_text or "👤" in owner.last_edit_text, owner.last_edit_text
    print("PASS test_crm_search_panel_flow")


async def test_search_does_not_cross_shops(main_dp) -> None:
    _shop_a, shop_b = await seed_two_shops()
    async with session_scope() as session:
        hidden = (await session.execute(select(Customer).where(Customer.shop_bot_id == shop_b))).scalars().all()
        hidden_id = hidden[0].id

    owner = Chat(main_dp, OWNER_A_TG_ID)
    await owner.say("👥 مشتری‌ها")
    await owner.tap("crm_search")
    await owner.say("sara_hidden")
    assert "پیدا نشد" in owner.last_text, owner.last_text
    await owner.tap(f"crm_card:{hidden_id}")
    # گاردِ مالکیتِ موجودِ CRM (CRM_NOT_FOUND) جواب می‌دهد، نه متنِ «دکمهٔ کهنه» — هر دو
    # بی‌خطرند؛ مهم این است که کارتِ مشتریِ فروشگاهِ دیگر باز نشود.
    assert owner.last_toast["text"] == main_texts.CRM_NOT_FOUND, owner.last_toast
    assert not owner.edits, "کارتِ مشتریِ فروشگاهِ دیگر ویرایش/باز نشد"
    async with session_scope() as session:
        still_there = await session.get(Customer, hidden_id)
    assert still_there is not None
    print("PASS test_search_does_not_cross_shops")


async def test_admin_owner_search_flow(main_dp) -> None:
    await seed_two_shops()
    admin = Chat(main_dp, ADMIN_TG_ID)
    await admin.say("👥 مدیریت فروشگاه‌دارها")
    labels = [b.text for row in admin.last_markup.inline_keyboard for b in row]
    assert main_texts.ADMIN_OWNER_SEARCH_BUTTON in labels, labels

    await admin.tap("admin_owner_search")
    assert "چه چیزی را بگردم" in admin.last_text, admin.last_text
    await admin.say("فروشنده")
    screen = admin.last_text
    assert "۲ نفر" in screen, screen
    assert any(value.startswith("admin_owner_view:") for value in callbacks(admin.last_markup))

    await admin.say("چنین کسی نیست")
    assert "پیدا نشد" in admin.last_text, admin.last_text
    flat = callbacks(admin.last_markup)
    assert "admin_owner_search" in flat and "admin_owners_list:0" in flat, flat

    await admin.say("انصراف")
    assert main_texts.ADMIN_OWNER_SEARCH_CANCELLED in admin.last_text, admin.last_text
    await admin.tap("admin_owner_search:0")
    assert admin.last_toast["text"] == main_texts.ADMIN_OWNER_SEARCH_INVALID, admin.last_toast

    async with session_scope() as session:
        await admin_role_service.grant_operator(session, OPERATOR_TG_ID, granted_by_telegram_id=ADMIN_TG_ID)
        role = await admin_role_service.get_by_telegram_id(session, OPERATOR_TG_ID)
        owner_a = (await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == OWNER_A_TG_ID))).scalar_one()
        await admin_role_service.set_scope(session, role, [owner_a.id])

    operator = Chat(main_dp, OPERATOR_TG_ID)
    await operator.say("👥 مدیریت فروشگاه‌دارها")
    await operator.tap("admin_owner_search")
    await operator.say("فروشنده")
    screen = operator.last_text
    assert "۱ نفر" in screen and "۲ نفر" not in screen, screen
    for bad in ("admin_owner_search:abc", "admin_owner_search:-1", "admin_owner_search:100001"):
        await operator.tap(bad)
        assert operator.last_toast["text"] == main_texts.ADMIN_OWNER_SEARCH_INVALID, (bad, operator.last_toast)
    # صفحه‌ای که از دامنه بیرون است «خطا» نیست، به آخرین صفحهٔ واقعی می‌چسبد (تجربهٔ کاربریِ نرم).
    await operator.tap("admin_owner_search:5")
    assert "صفحه‌یِ ۱ از ۱" in operator.last_edit_text, operator.last_edit_text
    print("PASS test_admin_owner_search_flow")


async def test_keyboard_bounds_and_numbering() -> None:
    items = [type("R", (), {"id": 5_000_000 + i, "first_name": "نام", "last_name": None, "username": None})() for i in range(2)]
    kb = keyboards.crm_search_keyboard(items, 1, 3, crm_service.PAGE_SIZE)
    flat = callbacks(kb)
    assert all(len(value.encode("utf-8")) <= 64 for value in flat), flat
    labels = [b.text for row in kb.inline_keyboard for b in row]
    assert labels[0].startswith("۹. "), labels
    assert "crm_search_page:0" in flat and "crm_search_page:2" in flat, flat
    assert flat[-1] == "crm_home", flat

    owners = [type("O", (), {"id": 7_000_000 + i, "first_name": "ف", "last_name": None, "username": None,
                             "telegram_id": 1, "phone_number": None, "wallet_balance_toman": 0})() for i in range(2)]
    admin_kb = keyboards.admin_owners_list_keyboard(owners, 2, {}, callback_prefix="admin_owner_search", total_pages=4)
    admin_flat = callbacks(admin_kb)
    assert "admin_owner_search:1" in admin_flat and "admin_owner_search:3" in admin_flat, admin_flat
    assert all(len(value.encode("utf-8")) <= 64 for value in admin_flat), admin_flat
    print("PASS test_keyboard_bounds_and_numbering")


async def test_outsider_gets_nothing(main_dp) -> None:
    await seed_two_shops()
    bot = Bot(token=MAIN_TOKEN, session=FakeSession())
    for index, data in enumerate(
        ("admin_owner_search", "admin_owner_search:0", "crm_search", "crm_search_page:0"), 500
    ):
        await main_dp.feed_update(bot, make_callback_update(index, data=data, user_id=OUTSIDER_TG_ID))
    await main_dp.feed_update(bot, make_message_update(520, text="علی", user_id=OUTSIDER_TG_ID))
    # کاربرِ ثبت‌نام‌نکرده ممکن است پیامِ عمومیِ «اول ثبت‌نام کن» را بگیرد (رفتارِ درستِ محصول)؛
    # آنچه امنیتی است این است که هیچ خروجیِ جست‌وجو یا نتیجهٔ فهرستی به او نرسد.
    leaked = [
        row["text"] for row in bot.session.sent_messages + bot.session.edited_texts
        if "جست‌وجو" in row["text"]
    ]
    assert not leaked, leaked
    assert not bot.session.edited_texts, "ویرایشِ صفحهٔ ادمین/پنل برایِ غیرصاحبِ حساب"
    # ادعایِ ساختاری: هیچ کال‌بک دو بار answer نشود (پاسخِ دوم در تلگرام «query is already
    # answered» است و در لاگِ زنده خطا می‌سازد) — گاردِ مالکیت خودش پاسخ را می‌دهد.
    answered = [row["callback_query_id"] for row in bot.session.answered_callbacks]
    assert len(answered) == len(set(answered)), answered
    await bot.session.close()
    print("PASS test_outsider_gets_nothing")


async def test_back_button_exits_search_mode(main_dp) -> None:
    """«بازگشت به پنل» / «بازگشت به فهرستِ کامل» باید حالتِ جست‌وجو را ببندد.

    بدونِ این، کاربرِ بعد ازِ بازگشت هر متنی می‌نوشت دوباره «عبارتِ جست‌وجو» حساب می‌شد — همان
    دامِ «FSM گیرکرده» که این مخزن برایِ دکمه‌هایِ منو نگهبانی دارد، اما از راهِ دکمهٔ بازگشتِ خودِ
    صفحهٔ جست‌وجو.
    """
    await seed_two_shops()

    owner = Chat(main_dp, OWNER_A_TG_ID)
    await owner.say("👥 مشتری‌ها")
    await owner.tap("crm_search")
    await owner.say("مشتری")
    assert "نتیجهٔ جست‌وجویِ «مشتری»" in owner.last_text, owner.last_text
    await owner.tap("crm_home")
    assert "مشتری‌هایِ فروشگاهت" in owner.last_edit_text, owner.last_edit_text
    before = len(owner.sent)
    await owner.say("مشتری")
    assert all("نتیجهٔ جست‌وجویِ" not in row["text"] for row in owner.sent[before:]), owner.sent[before:]

    admin = Chat(main_dp, ADMIN_TG_ID)
    await admin.say("👥 مدیریت فروشگاه‌دارها")
    await admin.tap("admin_owner_search")
    await admin.say("فروشنده")
    assert "نتیجهٔ جست‌وجویِ «فروشنده»" in admin.last_text, admin.last_text
    await admin.tap("admin_owners_list:0")
    assert "فهرستِ فروشگاه‌دارها" in admin.last_edit_text, admin.last_edit_text
    before = len(admin.sent)
    await admin.say("فروشنده")
    assert all("نتیجهٔ جست‌وجویِ" not in row["text"] for row in admin.sent[before:]), admin.sent[before:]
    print("PASS test_back_button_exits_search_mode")


async def main() -> None:
    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    await test_normalization_and_like_escaping()
    await test_customer_search_scoping_and_pages()
    await test_owner_search_respects_scope()
    await test_crm_search_panel_flow(main_dp)
    await test_search_does_not_cross_shops(main_dp)
    await test_admin_owner_search_flow(main_dp)
    await test_keyboard_bounds_and_numbering()
    await test_outsider_gets_nothing(main_dp)
    await test_back_button_exits_search_mode(main_dp)
    print("📊 نتیجه: ۹ تستِ پ۵۶ (جست‌وجویِ فروشگاه‌دارها و مشتری‌ها) پاس شد · نرمال‌سازی/دامنه/مالکیت/صفحه‌بندی/دسترسی/خروجِ حالت")


if __name__ == "__main__":
    asyncio.run(main())
