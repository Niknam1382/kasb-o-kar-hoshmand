"""
تست: «💬 دستیارِ مدیریتی» (فازِ ۴-د) — گفتگویِ فقط‌خواندنیِ فروشگاه‌دار با AI درباره‌یِ آمارِ فروشگاهش.

پوشش:
۱. منطقِ خالص: متنِ «گزارشِ آماری»، حافظه‌یِ کوتاه (۶ نوبت، آیتم‌هایِ بلند کوتاه، نقش‌هایِ نامعتبر حذف)، سقفِ جواب،
   پرامپتِ سیستمِ فقط‌خواندنی.
۲. ورودیِ AI فقط آمارِ تجمیعیِ *همین* فروشگاهه: هیچ نام/یوزرنیم/تلفن/آدرس/یادداشتِ CRM/متنِ مکالمه/متنِ آزادِ
   سفارش/متنِ سوالِ بی‌جواب/آیدیِ تلگرام و هیچ دیتایی از فروشگاهِ دیگه.
۳. مسیرِ کامل: ورود (نمایِ هزینه)، پرسش، حافظه‌یِ گفتگو (قدیمی‌ها حذف می‌شن)، کسرِ دقیق با دلیلِ OWNER_ASSISTANT، پایان.
۴. شکست = بدونِ هزینه (کیف‌پولِ خالی، خطایِ AI، جوابِ خالی)؛ پرسشِ بلند؛ محدودیتِ نرخ.
۵. فقط‌خواندنی: حتی اگه AI ادعا کنه «سفارش‌ها رو تایید کردم»، هیچ سفارش/کیف‌پولی تغییر نمی‌کنه.
۶. دکمه‌یِ منو از گفتگو خارج می‌کنه؛ فروشگاه‌دارِ دیگه فقط دیتایِ خودش رو می‌بینه؛ غیرفروشگاه‌دار ورود نداره.

اجرا: python3 tests_manual/test_owner_assistant.py
"""
from __future__ import annotations

import asyncio
import datetime
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from sqlalchemy import select  # noqa: E402

from harness import build_test_dispatchers, reset_database  # noqa: E402
from phase4_helpers import (  # noqa: E402
    Chat,
    FakeAi,
    add_customer,
    add_order,
    owner_balance,
    patched_ai,
    reply_keyboard_texts,
    set_ai,
    wallet_transactions,
)
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot import texts  # noqa: E402
from app.database.models import CampaignDiscountType, OrderConsultation, OrderStatus, ShopOwner, WalletTransactionReason  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import (  # noqa: E402
    accounting_service,
    ai_billing,
    campaign_service,
    conversation_service,
    knowledge_service,
    owner_assistant_service as oas,
    product_service,
    shop_bot_service,
    wallet_service,
)
from app.services import rate_limiter as rate_limiter_module  # noqa: E402
from app.services.admin_settings_service import get_admin_settings  # noqa: E402

OWNER_TG_ID = 996001
SHOP_BOT_TG_ID = 996002
CUSTOMER_TG_ID = 996003
OTHER_OWNER_TG_ID = 996011
OTHER_SHOP_BOT_TG_ID = 996012
STRANGER_TG_ID = 996021
UTC = datetime.timezone.utc
REASON = WalletTransactionReason.OWNER_ASSISTANT
PHASE4_BUTTONS = {"🧩 سوال‌هایِ بی‌جواب", "📚 پرسش‌وپاسخ‌هایِ تاییدشده", "👥 مشتری‌ها", "🧮 حسابداری", "💬 دستیارِ مدیریتی"}

SECRETS = (
    "نامِ محرمانه",
    "secret_username",
    "996101",
    "SECRET_NOTE_ABC",
    "secret_tag",
    "09125556677",
    "SECRET_ADDR",
    "SECRET_SUMMARY_TEXT",
    "SECRET_CHAT_LINE",
    "SECRET_GAP_QUESTION",
    "OTHER_SHOP_PRODUCT",
    "OTHER_SHOP_CUSTOMER",
    "OTHER_SHOP_CAMPAIGN",
    "OTHER_SHOP_GAP",
    "۸۸۸٬۸۸۸",
    "888888",
    str(CUSTOMER_TG_ID),
)


def _digest(**overrides) -> oas.Digest:
    data = dict(
        generated_on="1405/07/13",
        today_net=150_000,
        today_orders=2,
        week_net=400_000,
        week_orders=5,
        month_net=1_200_000,
        month_orders=12,
        month_discount=90_000,
        month_average=100_000,
        status_counts_30d={"pending": 1, "confirmed": 11},
        pending_total=3,
        top_products_30d=[("چایِ ممتاز", 20, 800_000)],
        campaigns=[("جشنواره‌یِ مهر", "active", 4, 60_000)],
        customers_total=30,
        segment_counts={"loyal": 5, "active": 10, "new": 3, "churning": 7, "no_purchase": 5},
        open_gaps=2,
        wallet_balance=75_000,
    )
    data.update(overrides)
    return oas.Digest(**data)


# =============================================================================
# ۱. منطقِ خالص
# =============================================================================
def test_pure_digest_history_clamp_and_prompt() -> None:
    rendered = oas.render_digest(_digest())
    for expected in (
        "تاریخِ گزارش: ۱۴۰۵/۰۷/۱۳",
        "- امروز: ۱۵۰٬۰۰۰ تومان (۲ سفارش)",
        "- ۷ روزِ اخیر: ۴۰۰٬۰۰۰ تومان (۵ سفارش)",
        "- ۳۰ روزِ اخیر: ۱٬۲۰۰٬۰۰۰ تومان (۱۲ سفارش)",
        "- جمعِ تخفیف‌هایِ ۳۰ روزِ اخیر: ۹۰٬۰۰۰ تومان",
        "- میانگینِ هر سفارشِ ۳۰ روزِ اخیر: ۱۰۰٬۰۰۰ تومان",
        "- ⏳ در انتظارِ بررسی: ۱",
        "- ✅ تاییدشده: ۱۱",
        "کلِ سفارش‌هایِ منتظرِ بررسیِ فروشگاه‌دار (فارغ از بازه): ۳",
        "- چایِ ممتاز: ۲۰ عدد، فروشِ خالص ۸۰۰٬۰۰۰ تومان",
        "- جشنواره‌یِ مهر (فعال): ۴ بار مصرف، تخفیفِ داده‌شده ۶۰٬۰۰۰ تومان",
        "مشتری‌ها: کل ۳۰ نفر",
        "- وفادار: ۵",
        "- در حالِ ریزش: ۷",
        "- بدونِ خرید: ۵",
        "سوال‌هایِ بی‌جوابِ بازِ ربات: ۲",
        "موجودیِ کیف‌پولِ فروشگاه‌دار: ۷۵٬۰۰۰ تومان",
    ):
        assert expected in rendered, f"گزارش باید «{expected}» رو داشته باشه:\n{rendered}"

    empty = oas.render_digest(_digest(status_counts_30d={}, top_products_30d=[], campaigns=[], customers_total=0, segment_counts={}))
    assert "- سفارشی ثبت نشده" in empty and "- فروشی ثبت نشده" in empty and "- کمپینی تعریف نشده" in empty
    assert "- وفادار: ۰" in empty, "بخشی که مشتری نداره صفر نشون داده می‌شه، نه حذف"

    prompt = oas.build_system_prompt(_digest())
    assert prompt.startswith(oas.SYSTEM_PROMPT) and f"گزارشِ آماری:\n{rendered}" in prompt
    for rule in ("هیچ تغییری نمی‌تونی بدی", "هیچ عددی از خودت نساز", "رو نداری و نباید حدس بزنی", "اجرا نکن", "«📦 محصولات»"):
        assert rule in oas.SYSTEM_PROMPT, rule

    # حافظه‌یِ کوتاه
    long_history = [{"role": "user" if index % 2 == 0 else "assistant", "content": f"پیامِ {index}"} for index in range(30)]
    trimmed = oas.trim_history(long_history)
    assert len(trimmed) == 2 * oas.HISTORY_TURNS == 12
    assert trimmed[0]["content"] == "پیامِ 18" and trimmed[-1]["content"] == "پیامِ 29", "فقط ۶ نوبتِ آخر"
    messy = [
        {"role": "system", "content": "نقشِ نامعتبر"},
        {"role": "user", "content": "   "},
        {"role": "user", "content": "ک" * 900},
        {"role": "assistant"},
        {"role": "assistant", "content": "  جواب  "},
    ]
    cleaned = oas.trim_history(messy)
    assert [item["role"] for item in cleaned] == ["user", "assistant"]
    assert len(cleaned[0]["content"]) == oas.HISTORY_ITEM_MAX_CHARS == 600 and cleaned[0]["content"].endswith("…")
    assert cleaned[1]["content"] == "جواب"
    assert oas.trim_history(None) == [] and oas.trim_history([]) == []

    clamped = oas.clamp_reply("الف" * 5000)
    assert len(clamped) == oas.REPLY_MAX_CHARS == 3500 and clamped.endswith("…")
    assert oas.clamp_reply(None) == "" and oas.clamp_reply("  متن  ") == "متن"
    assert oas.segment_label("churning") == "در حالِ ریزش" and oas.segment_label("nope") == "nope"

    print("✅ test_pure_digest_history_clamp_and_prompt PASSED")


# =============================================================================
# دیتایِ مشترک
# =============================================================================
async def _seed(*, balance: int | None = None) -> int:
    await reset_database()
    rate_limiter_module._windows.clear()
    if balance is None:
        return await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    return await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID, initial_balance_toman=balance)


async def _seed_data(shop_bot_id: int, other_shop_bot_id: int) -> dict:
    now = datetime.datetime.now(UTC)
    today = accounting_service.build_periods(now)["today"]
    ts = max(today.start + datetime.timedelta(seconds=1), now - datetime.timedelta(seconds=5))
    old = ts - datetime.timedelta(days=3)

    async with session_scope() as session:
        tea = await product_service.create_product(session, shop_bot_id, "چایِ ممتاز", None, 50_000, None)
        await product_service.create_product(session, other_shop_bot_id, "OTHER_SHOP_PRODUCT", None, 1_000, None)
        await campaign_service.create_campaign(
            session, shop_bot_id, name="جشنواره‌یِ ویژه", discount_type=CampaignDiscountType.PERCENT, discount_value=10, duration_days=7
        )
        await campaign_service.create_campaign(
            session,
            other_shop_bot_id,
            name="OTHER_SHOP_CAMPAIGN",
            discount_type=CampaignDiscountType.PERCENT,
            discount_value=50,
            duration_days=7,
        )
        tea_id = tea.id

    c1 = await add_customer(
        shop_bot_id,
        996101,
        "نامِ محرمانه ۱",
        "secret_username_1",
        first_seen_at=now - datetime.timedelta(days=60),
        last_message_at=now - datetime.timedelta(days=1),
        crm_notes="SECRET_NOTE_ABC",
        crm_tags="secret_tag",
    )
    await add_customer(shop_bot_id, 996102, "نامِ محرمانه ۲", None, first_seen_at=now - datetime.timedelta(days=2), last_message_at=now)
    pii = dict(phone="09125556677", address="SECRET_ADDR خیابانِ ۱", summary="سفارشِ SECRET_SUMMARY_TEXT")
    await add_order(
        shop_bot_id,
        c1,
        status=OrderStatus.CONFIRMED,
        value=100_000,
        discount=10_000,
        product_id=tea_id,
        quantity=2,
        created_at=ts,
        confirmed_at=ts,
        **pii,
    )
    await add_order(shop_bot_id, c1, status=OrderStatus.COMPLETED, value=50_000, product_id=tea_id, created_at=ts, confirmed_at=ts)
    await add_order(shop_bot_id, c1, status=OrderStatus.PENDING, value=70_000, created_at=ts)
    await add_order(shop_bot_id, c1, status=OrderStatus.CONFIRMED, value=30_000, product_id=tea_id, created_at=old, confirmed_at=old)
    async with session_scope() as session:
        await conversation_service.save_turn(session, c1, "SECRET_CHAT_LINE سلام", "جوابِ ربات")
        assert await knowledge_service.record_gap(session, shop_bot_id, "SECRET_GAP_QUESTION چقدره؟") is True
        assert await knowledge_service.record_gap(session, other_shop_bot_id, "OTHER_SHOP_GAP چیه؟") is True

    other_customer = await add_customer(other_shop_bot_id, 996201, "OTHER_SHOP_CUSTOMER", None, first_seen_at=now, last_message_at=now)
    await add_order(other_shop_bot_id, other_customer, status=OrderStatus.CONFIRMED, value=888_888, created_at=ts, confirmed_at=ts)
    return {"now": now, "c1": c1}


async def _charged() -> int:
    return sum(tx.amount_toman for tx in await wallet_transactions(REASON))


async def _expected_cost(tokens: int | None) -> int:
    async with session_scope() as session:
        return wallet_service.estimate_owner_assistant_cost(await get_admin_settings(session), tokens)


# =============================================================================
# ۲. ورودیِ AI فقط آمارِ تجمیعیِ همین فروشگاهه
# =============================================================================
async def test_digest_has_only_aggregates_never_pii_or_other_shops() -> None:
    shop_bot_id = await _seed()
    other_shop_bot_id = await seed_usable_shop(OTHER_OWNER_TG_ID, OTHER_SHOP_BOT_TG_ID)
    await _seed_data(shop_bot_id, other_shop_bot_id)

    async with session_scope() as session:
        shop_bot = await shop_bot_service.get_by_id(session, shop_bot_id)
        owner = (await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == OWNER_TG_ID))).scalar_one()
        # now تازه (بعد از ساختِ کمپین‌ها): کمپین‌ها همون لحظه‌یِ ساخت شروع شدن، پس با now قدیمی «زمان‌بندی‌شده» می‌شدن.
        digest_now = datetime.datetime.now(UTC)
        digest = await oas.build_digest(session, shop_bot, owner, digest_now)
        other_shop_bot = await shop_bot_service.get_by_id(session, other_shop_bot_id)
        other_owner = (await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == OTHER_OWNER_TG_ID))).scalar_one()
        other_digest = await oas.build_digest(session, other_shop_bot, other_owner, digest_now)

    assert (digest.today_net, digest.today_orders) == (150_000, 2)
    assert (digest.week_net, digest.week_orders) == (180_000, 3), "سفارشِ ۳ روز قبل توی هفته هست"
    assert (digest.month_net, digest.month_orders, digest.month_discount, digest.month_average) == (180_000, 3, 10_000, 60_000)
    assert list(digest.status_counts_30d.items()) == [("pending", 1), ("confirmed", 2), ("completed", 1)]
    assert digest.pending_total == 1
    assert digest.top_products_30d == [("چایِ ممتاز", 4, 180_000)]
    assert digest.campaigns == [("جشنواره‌یِ ویژه", "active", 0, 0)]
    assert digest.customers_total == 2 and digest.segment_counts["loyal"] == 1 and digest.segment_counts["new"] == 1
    assert digest.open_gaps == 1, "فقط تعدادِ سوال‌هایِ بی‌جواب، نه متنِ سوالِ مشتری"
    assert digest.wallet_balance == owner.wallet_balance_toman

    rendered = oas.render_digest(digest)
    prompt = oas.build_system_prompt(digest)
    for expected in ("چایِ ممتاز", "- جشنواره‌یِ ویژه (فعال): ۰ بار مصرف", "- امروز: ۱۵۰٬۰۰۰ تومان (۲ سفارش)"):
        assert expected in rendered, f"گزارش باید «{expected}» رو داشته باشه:\n{rendered}"
    for secret in SECRETS:
        assert secret not in rendered and secret not in prompt, f"«{secret}» هیچ‌وقت نباید توی ورودیِ AI باشه"

    # فروشگاهِ دیگه: فقط دیتایِ خودش
    assert (other_digest.today_net, other_digest.today_orders) == (888_888, 1)
    assert other_digest.customers_total == 1 and other_digest.open_gaps == 1
    other_rendered = oas.render_digest(other_digest)
    for foreign in ("چایِ ممتاز", "جشنواره‌یِ ویژه", "۱۵۰٬۰۰۰", "نامِ محرمانه"):
        assert foreign not in other_rendered, f"دیتایِ فروشگاهِ اول («{foreign}») نباید توی گزارشِ فروشگاهِ دوم بیاد"

    print("✅ test_digest_has_only_aggregates_never_pii_or_other_shops PASSED")


# =============================================================================
# ۳. مسیرِ کامل
# =============================================================================
async def test_flow_cost_history_trimming_and_end(main_dp) -> None:
    shop_bot_id = await _seed()
    other_shop_bot_id = await seed_usable_shop(OTHER_OWNER_TG_ID, OTHER_SHOP_BOT_TG_ID)
    await _seed_data(shop_bot_id, other_shop_bot_id)
    fake = set_ai(FakeAi(chat_reply=lambda system_prompt, history, user_message: f"پاسخ به: {user_message}", tokens=1200))
    owner = Chat(main_dp, OWNER_TG_ID)
    balance_before = await owner_balance(OWNER_TG_ID)
    cost = await _expected_cost(1200)
    assert cost > 0

    async with session_scope() as session:
        shown_estimate = wallet_service.estimate_owner_assistant_cost(
            await get_admin_settings(session), wallet_service.OWNER_ASSISTANT_TYPICAL_TOKENS
        )
    await owner.say("💬 دستیارِ مدیریتی")
    assert owner.last_text == texts.assistant_intro(shown_estimate), "ورود: هزینه‌یِ هر پرسش و قولِ فقط‌خواندنی بودن نمایش داده می‌شه"
    assert reply_keyboard_texts(owner.last_markup) == {texts.ASSISTANT_END_BUTTON}
    assert fake.chat_calls == [] and await _charged() == 0, "ورود به‌تنهایی هزینه‌ای نداره"

    for index in range(1, 9):
        await owner.say(f"سوال {index}")
        assert owner.last_text == f"پاسخ به: سوال {index}"

    assert len(fake.chat_calls) == 8 and await _charged() == -8 * cost, "هر پرسش دقیقاً یه بار کسر می‌شه"
    assert await owner_balance(OWNER_TG_ID) == balance_before - 8 * cost

    first_prompt, first_history, first_message = fake.chat_calls[0]
    assert first_prompt.startswith(oas.SYSTEM_PROMPT) and "- امروز: ۱۵۰٬۰۰۰ تومان (۲ سفارش)" in first_prompt
    assert first_history == [] and first_message == "سوال 1"
    assert fake.chat_calls[1][1] == [{"role": "user", "content": "سوال 1"}, {"role": "assistant", "content": "پاسخ به: سوال 1"}]
    last_history = fake.chat_calls[7][1]
    assert len(last_history) == 12 and last_history[0]["content"] == "سوال 2" and last_history[-1]["content"] == "پاسخ به: سوال 7", (
        "حافظه فقط ۶ نوبتِ آخره؛ نوبتِ اول حذف شده"
    )

    # پایان
    await owner.say("🔚 پایان")
    assert owner.last_text == texts.ASSISTANT_END_TEXT
    assert PHASE4_BUTTONS <= reply_keyboard_texts(owner.last_markup), "منویِ اصلیِ فروشگاه‌دار برمی‌گرده"
    await owner.say("سوالِ بعد از پایان")
    assert len(fake.chat_calls) == 8, "بعد از پایان دیگه هیچ پرسشی به AI نمی‌ره"

    print("✅ test_flow_cost_history_trimming_and_end PASSED")


# =============================================================================
# ۴. شکست = بدونِ هزینه
# =============================================================================
async def test_failures_cost_nothing(main_dp) -> None:
    await _seed(balance=0)
    fake = set_ai(FakeAi(chat_reply="نباید صدا زده بشه"))
    owner = Chat(main_dp, OWNER_TG_ID)
    await owner.say("💬 دستیارِ مدیریتی")
    await owner.say("امروز چقدر فروختم؟")
    assert owner.last_text == texts.ASSISTANT_NO_FUNDS and fake.chat_calls == [], "کیف‌پولِ خالی: AI صدا زده نمی‌شه"
    assert await _charged() == 0

    await _seed()
    owner = Chat(main_dp, OWNER_TG_ID)
    balance_before = await owner_balance(OWNER_TG_ID)
    await owner.say("💬 دستیارِ مدیریتی")

    fake = set_ai(FakeAi(raises=True))
    await owner.say("سوالِ اول")
    assert owner.last_text == texts.GENERIC_ERROR and len(fake.chat_calls) == 1

    fake = set_ai(FakeAi(chat_reply="   "))
    await owner.say("سوالِ دوم")
    assert owner.last_text == texts.ASSISTANT_EMPTY_REPLY and len(fake.chat_calls) == 1

    fake = set_ai(FakeAi(chat_reply="جوابِ اوکی"))
    await owner.say("ی" * (oas.QUESTION_MAX_CHARS + 1))
    assert owner.last_text == texts.ASSISTANT_TOO_LONG and fake.chat_calls == [], "پرسشِ بلند رد می‌شه، AI صدا زده نمی‌شه"

    assert await _charged() == 0 and await owner_balance(OWNER_TG_ID) == balance_before, "هیچ‌کدوم از شکست‌ها هزینه‌ای نداره"

    # شکست‌ها تاریخچه رو خراب نمی‌کنن: پرسشِ بعدی با حافظه‌یِ خالی شروع می‌شه
    await owner.say("سوالِ سالم")
    assert owner.last_text == "جوابِ اوکی" and fake.chat_calls[0][1] == []

    print("✅ test_failures_cost_nothing PASSED")


async def test_rate_limit(main_dp) -> None:
    await _seed()
    fake = set_ai(FakeAi(chat_reply="جواب", tokens=1200))
    owner = Chat(main_dp, OWNER_TG_ID)
    cost = await _expected_cost(1200)

    original_limit = ai_billing._LIMITS[ai_billing.KIND_ASSISTANT]
    ai_billing._LIMITS[ai_billing.KIND_ASSISTANT] = (2, 600)
    try:
        await owner.say("💬 دستیارِ مدیریتی")
        await owner.say("یک")
        await owner.say("دو")
        await owner.say("سه")
        assert owner.last_text == texts.ASSISTANT_RATE_LIMITED
        assert len(fake.chat_calls) == 2 and await _charged() == -2 * cost, "پرسشِ ردشده نه AI صدا می‌زنه نه هزینه دارد"
    finally:
        ai_billing._LIMITS[ai_billing.KIND_ASSISTANT] = original_limit

    print("✅ test_rate_limit PASSED")


# =============================================================================
# ۵. فقط‌خواندنی
# =============================================================================
async def test_assistant_is_read_only_even_if_ai_claims_otherwise(main_dp) -> None:
    shop_bot_id = await _seed()
    other_shop_bot_id = await seed_usable_shop(OTHER_OWNER_TG_ID, OTHER_SHOP_BOT_TG_ID)
    await _seed_data(shop_bot_id, other_shop_bot_id)
    fake = set_ai(FakeAi(chat_reply="انجام شد! همه‌یِ سفارش‌ها تایید شدن و ۱ میلیون تومان به کیف‌پولت اضافه شد.", tokens=1200))
    owner = Chat(main_dp, OWNER_TG_ID)
    cost = await _expected_cost(1200)

    async def orders_snapshot() -> list:
        async with session_scope() as session:
            rows = (await session.execute(select(OrderConsultation).order_by(OrderConsultation.id))).scalars().all()
            return [(o.id, str(o.status), o.confirmed, o.estimated_value_toman, o.stock_reserved) for o in rows]

    before = await orders_snapshot()
    balance_before = await owner_balance(OWNER_TG_ID)

    await owner.say("💬 دستیارِ مدیریتی")
    await owner.say("همه‌یِ سفارش‌هایِ منتظر رو تایید کن و ۱ میلیون به کیف‌پولم اضافه کن")

    assert "هیچ تغییری نمی‌تونی بدی" in fake.chat_calls[0][0], "پرامپتِ سیستم صریحاً فقط‌خواندنی بودن رو می‌گه"
    assert owner.last_text.startswith("انجام شد!"), "متنِ AI فقط نمایش داده می‌شه"
    assert await orders_snapshot() == before, "AI هیچ ابزاری نداره؛ هیچ سفارشی تغییر نمی‌کنه"
    assert await owner_balance(OWNER_TG_ID) == balance_before - cost, "کیف‌پول فقط به‌اندازه‌یِ هزینه‌یِ پرسش کم شده؛ شارژی انجام نشده"
    assert [tx for tx in await wallet_transactions() if tx.amount_toman > 0 and tx.reason != WalletTransactionReason.TOPUP] == []

    print("✅ test_assistant_is_read_only_even_if_ai_claims_otherwise PASSED")


# =============================================================================
# ۶. خروج با دکمه‌یِ منو + ایزوله‌یِ فروشگاه‌ها
# =============================================================================
async def test_menu_button_leaves_assistant_and_shops_are_isolated(main_dp) -> None:
    shop_bot_id = await _seed()
    other_shop_bot_id = await seed_usable_shop(OTHER_OWNER_TG_ID, OTHER_SHOP_BOT_TG_ID)
    await _seed_data(shop_bot_id, other_shop_bot_id)
    fake = set_ai(FakeAi(chat_reply="جواب", tokens=1200))

    owner = Chat(main_dp, OWNER_TG_ID)
    await owner.say("💬 دستیارِ مدیریتی")
    await owner.say("🧮 حسابداری")  # دکمه‌یِ منو وسطِ گفتگو
    assert owner.last_text.startswith("🧮 حسابداری — امروز"), "دکمه‌یِ منو باید از گفتگو خارج کنه و کار کنه، نه اینکه به‌عنوانِ پرسش بره"
    assert fake.chat_calls == []
    await owner.say("یه متنِ معمولی")
    assert fake.chat_calls == [], "بعد از خروج، متنِ معمولی دیگه پرسشِ دستیار حساب نمی‌شه"

    other = Chat(main_dp, OTHER_OWNER_TG_ID)
    await other.say("💬 دستیارِ مدیریتی")
    await other.say("امروز چقدر فروختم؟")
    assert len(fake.chat_calls) == 1
    other_prompt = fake.chat_calls[0][0]
    assert "- امروز: ۸۸۸٬۸۸۸ تومان (۱ سفارش)" in other_prompt, "فروشگاه‌دارِ دوم آمارِ خودش رو می‌گیره"
    for foreign in ("چایِ ممتاز", "جشنواره‌یِ ویژه", "۱۵۰٬۰۰۰"):
        assert foreign not in other_prompt, f"«{foreign}» مالِ فروشگاهِ اوله و نباید به AIِ فروشگاهِ دوم برسه"

    stranger = Chat(main_dp, STRANGER_TG_ID)
    await stranger.say("💬 دستیارِ مدیریتی")
    assert stranger.last_text == texts.SHOP_BOT_NOT_SET_UP
    await stranger.say("امروز چقدر فروختم؟")
    assert len(fake.chat_calls) == 1, "غیرفروشگاه‌دار هیچ‌وقت به AI دسترسی پیدا نمی‌کنه"

    print("✅ test_menu_button_leaves_assistant_and_shops_are_isolated PASSED")


async def main() -> None:
    test_pure_digest_history_clamp_and_prompt()
    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    with patched_ai():
        await test_digest_has_only_aggregates_never_pii_or_other_shops()
        await test_flow_cost_history_trimming_and_end(main_dp)
        await test_failures_cost_nothing(main_dp)
        await test_rate_limit(main_dp)
        await test_assistant_is_read_only_even_if_ai_claims_otherwise(main_dp)
        await test_menu_button_leaves_assistant_and_shops_are_isolated(main_dp)


if __name__ == "__main__":
    asyncio.run(main())
