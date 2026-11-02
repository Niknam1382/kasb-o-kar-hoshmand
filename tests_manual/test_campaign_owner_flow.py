"""
تست: پنلِ فروشگاه‌دار برایِ «🎯 کمپین‌ها» (فازِ ۳ — سازنده‌ی کمپین) از طریقِ دیسپچرِ واقعیِ
ربات اصلی.

پوشش:
۱. ویزاردِ کامل برایِ کمپینِ درصدی با کد (ورودیِ فارسی: «۱۰»، «۲۰۰٬۰۰۰»، «mehr ۱۰») → ردیفِ
   درستِ دیتابیس؛ دابل‌تپِ «ساخت» دومین کمپین نمی‌سازه.
۲. ویزاردِ مبلغ‌ثابت: حداقلِ مبلغِ سبد اجباریه و باید *بیشتر* از تخفیف باشه.
۳. اعتبارسنجیِ ورودی‌ها (درصدِ نامعتبر، کدِ نامعتبر/تکراری، مدت، سقف‌ها).
۴. فهرست/جزئیات/توقف و ادامه/حذفِ امن/کمپینِ تمام‌شده/اعلام به مشتری‌ها (ارسال از طریقِ
   ربات خودِ فروشگاه، با متنِ آماده‌ی حاویِ کد).
۵. ایزوله‌بودنِ چندمستاجری: فروشگاه‌دارِ دیگه (یا غیرفروشگاه‌دار) نه می‌بینه، نه توقف/حذف/اعلام می‌کنه.
۶. دکمه‌یِ منو وسطِ FSM (هم «🎯 کمپین‌ها» هم دکمه‌هایی که قبلاً تویِ لیستِ escape نبودن) state رو
   پاک می‌کنه.

نکته‌ی هارنس: EditMessageText ثبت نمی‌شه؛ پس برایِ مسیرهایی که edit_text می‌زنن، دیتابیس و
answered_callbacks (toast/alert) رو چک می‌کنیم، و متنِ جزئیات/فهرست رو مستقیم از
_detail_payload/_list_payload می‌گیریم.

اجرا: python3 tests_manual/test_campaign_owner_flow.py
"""
from __future__ import annotations

import asyncio
import datetime
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402

from harness import (  # noqa: E402
    FakeSession,
    build_test_dispatchers,
    make_callback_update,
    make_message_update,
    register_fake_shop_bot,
    reset_database,
)
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot import texts  # noqa: E402
from app.bots.main_bot.handlers import campaigns as campaign_handlers  # noqa: E402
from app.database.models import Campaign, CampaignDiscountType, OrderConsultation, OrderStatus, OrderType, ShopBot  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import campaign_service, customer_service, order_service  # noqa: E402
from sqlalchemy import select  # noqa: E402

OWNER_TG_ID = 999901
SHOP_BOT_TG_ID = 999902
CUSTOMER_1_TG_ID = 999903
CUSTOMER_2_TG_ID = 999904
OTHER_OWNER_TG_ID = 999911
OTHER_SHOP_BOT_TG_ID = 999912
STRANGER_TG_ID = 999921

PERCENT = CampaignDiscountType.PERCENT
FIXED = CampaignDiscountType.FIXED


class _Chat:
    """یه گفتگوی تستی با ربات اصلی: شمارنده‌ی update_id + میان‌برهایِ فرستادنِ متن/دکمه."""

    def __init__(self, dp, user_id: int) -> None:
        self.dp = dp
        self.user_id = user_id
        self.bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())
        self.session: FakeSession = self.bot.session  # type: ignore[assignment]
        self._n = 0

    async def say(self, text: str) -> None:
        self._n += 1
        await self.dp.feed_update(self.bot, make_message_update(self._n, text=text, user_id=self.user_id))

    async def tap(self, data: str) -> None:
        self._n += 1
        await self.dp.feed_update(self.bot, make_callback_update(self._n, data=data, user_id=self.user_id))

    @property
    def last_text(self) -> str:
        return self.session.sent_messages[-1]["text"]

    @property
    def last_markup(self):
        return self.session.sent_messages[-1]["reply_markup"]

    @property
    def last_toast(self) -> dict:
        return self.session.answered_callbacks[-1]


def _callbacks(markup) -> list[str]:
    if markup is None:
        return []
    return [button.callback_data for row in markup.inline_keyboard for button in row if button.callback_data]


async def _campaigns_in_db(shop_bot_id: int | None = None) -> list[Campaign]:
    async with session_scope() as session:
        query = select(Campaign).order_by(Campaign.id)
        if shop_bot_id is not None:
            query = query.where(Campaign.shop_bot_id == shop_bot_id)
        return list((await session.execute(query)).scalars().all())


async def _seed() -> int:
    await reset_database()
    return await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)


async def _new_campaign(shop_bot_id: int, **overrides) -> int:
    args = dict(name="کمپین تست", discount_type=PERCENT, discount_value=10, duration_days=7)
    args.update(overrides)
    async with session_scope() as session:
        return (await campaign_service.create_campaign(session, shop_bot_id, **args)).id


# =============================================================================
# ۱. ویزارد — درصدی با کد
# =============================================================================
async def test_wizard_creates_percent_campaign_with_code(main_dp) -> None:
    shop_bot_id = await _seed()
    owner = _Chat(main_dp, OWNER_TG_ID)

    await owner.say("🎯 کمپین‌ها")
    assert owner.last_text == texts.CAMPAIGNS_EMPTY
    assert _callbacks(owner.last_markup) == ["campaign_new"]

    await owner.tap("campaign_new")
    assert owner.last_text == texts.CAMPAIGN_ASK_NAME
    await owner.say("جشنواره‌ی مهر")
    assert owner.last_text == texts.CAMPAIGN_ASK_TYPE
    assert _callbacks(owner.last_markup) == ["campaign_type:percent", "campaign_type:fixed"]

    await owner.tap("campaign_type:percent")
    assert owner.last_text == texts.CAMPAIGN_ASK_PERCENT
    await owner.say("۱۰")
    assert owner.last_text == texts.CAMPAIGN_ASK_MAX_DISCOUNT
    await owner.say("۵۰٬۰۰۰")
    assert owner.last_text == texts.CAMPAIGN_ASK_CODE_CHOICE

    await owner.tap("campaign_code_choice:code")
    assert owner.last_text == texts.CAMPAIGN_ASK_CODE
    await owner.say("mehr ۱۰")
    assert owner.last_text == texts.CAMPAIGN_ASK_MIN_CART, "برایِ درصدی، حداقلِ سبد اختیاریه (دکمه‌ی «ندارد» هست)"
    assert "campaign_skip_min_cart" in _callbacks(owner.last_markup)
    await owner.say("۲۰۰٬۰۰۰")
    assert owner.last_text == texts.CAMPAIGN_ASK_DURATION
    await owner.tap("campaign_duration:7")
    assert owner.last_text == texts.CAMPAIGN_ASK_TOTAL_LIMIT
    await owner.say("100")
    assert owner.last_text == texts.CAMPAIGN_ASK_PER_CUSTOMER
    await owner.tap("campaign_percustomer:2")

    summary = owner.last_text
    for expected in ("MEHR10", "۱۰ درصد", "۵۰٬۰۰۰", "۲۰۰٬۰۰۰", "جشنواره‌ی مهر", "۱۰۰ بار", "۲ بار"):
        assert expected in summary, f"خلاصه باید «{expected}» رو داشته باشه:\n{summary}"
    assert _callbacks(owner.last_markup) == ["campaign_create_confirm", "campaign_create_cancel"]
    assert await _campaigns_in_db() == [], "تا «تایید» نزده، چیزی ساخته نمی‌شه"

    await owner.tap("campaign_create_confirm")
    campaigns = await _campaigns_in_db()
    assert len(campaigns) == 1
    campaign = campaigns[0]
    assert campaign.shop_bot_id == shop_bot_id and campaign.name == "جشنواره‌ی مهر"
    assert campaign.code == "MEHR10", "کد باید نرمال‌شده (حروفِ بزرگ، رقمِ انگلیسی، بدونِ فاصله) ذخیره بشه"
    assert campaign.discount_type == PERCENT and campaign.discount_value == 10
    assert campaign.max_discount_toman == 50_000 and campaign.min_cart_total_toman == 200_000
    assert campaign.total_usage_limit == 100 and campaign.per_customer_limit == 2
    assert campaign.is_active
    assert campaign.ends_at - campaign.starts_at == datetime.timedelta(days=7)
    assert abs((campaign.starts_at - datetime.datetime.now(datetime.timezone.utc)).total_seconds()) < 120

    # دابل‌تپِ «ساخت»: state پاک شده، پس دکمه‌ی کهنه فقط alert می‌ده و کمپینِ دومی ساخته نمی‌شه
    await owner.tap("campaign_create_confirm")
    assert owner.last_toast["text"] == texts.CAMPAIGN_WIZARD_STALE and owner.last_toast["show_alert"]
    assert len(await _campaigns_in_db()) == 1

    print("✅ test_wizard_creates_percent_campaign_with_code PASSED")


# =============================================================================
# ۲. ویزارد — مبلغ‌ثابت
# =============================================================================
async def test_wizard_fixed_requires_min_cart_above_discount(main_dp) -> None:
    await _seed()
    owner = _Chat(main_dp, OWNER_TG_ID)

    await owner.say("🎯 کمپین‌ها")
    await owner.tap("campaign_new")
    await owner.say("تخفیفِ ثابت")
    await owner.tap("campaign_type:fixed")
    assert owner.last_text == texts.CAMPAIGN_ASK_FIXED
    await owner.say("۲۰۰۰۰")
    assert owner.last_text == texts.CAMPAIGN_ASK_CODE_CHOICE
    await owner.tap("campaign_code_choice:auto")

    assert owner.last_text == texts.campaign_ask_min_cart_fixed(20_000)
    assert owner.last_markup is None, "برایِ مبلغ‌ثابت، حداقلِ سبد اجباریه و دکمه‌ی «ندارد» نباید باشه"

    # دفاعِ دوم: callbackِ دستکاری‌شده‌ی «ندارد» نباید رد بشه
    await owner.tap("campaign_skip_min_cart")
    assert owner.last_toast["show_alert"] and owner.last_toast["text"] == texts.campaign_ask_min_cart_fixed(20_000)

    await owner.say("10000")
    assert owner.last_text == texts.campaign_min_cart_too_low(20_000)
    await owner.say("20000")
    assert owner.last_text == texts.campaign_min_cart_too_low(20_000), "حداقلِ سبد باید *بیشتر* از تخفیف باشه، نه مساوی"
    await owner.say("50000")
    assert owner.last_text == texts.CAMPAIGN_ASK_DURATION

    await owner.tap("campaign_duration:3")
    await owner.tap("campaign_skip_total_limit")
    assert owner.last_text == texts.CAMPAIGN_ASK_PER_CUSTOMER
    await owner.tap("campaign_percustomer:0")
    assert "نامحدود" in owner.last_text and "خودکار" in owner.last_text
    await owner.tap("campaign_create_confirm")

    (campaign,) = await _campaigns_in_db()
    assert campaign.discount_type == FIXED and campaign.discount_value == 20_000
    assert campaign.min_cart_total_toman == 50_000 and campaign.code is None
    assert campaign.total_usage_limit is None and campaign.per_customer_limit is None
    assert campaign.max_discount_toman is None
    assert campaign.ends_at - campaign.starts_at == datetime.timedelta(days=3)

    print("✅ test_wizard_fixed_requires_min_cart_above_discount PASSED")


# =============================================================================
# ۳. اعتبارسنجیِ ورودی‌ها
# =============================================================================
async def test_wizard_input_validation_and_duplicate_code(main_dp) -> None:
    shop_bot_id = await _seed()
    await _new_campaign(shop_bot_id, name="قدیمی", code="MEHR10")
    owner = _Chat(main_dp, OWNER_TG_ID)

    await owner.say("🎯 کمپین‌ها")
    await owner.tap("campaign_new")
    await owner.say("ن" * 61)
    assert owner.last_text == texts.CAMPAIGN_NAME_INVALID
    await owner.say("یلدا")
    assert owner.last_text == texts.CAMPAIGN_ASK_TYPE

    await owner.say("یه متنِ بی‌ربط")
    assert owner.last_text == texts.CAMPAIGN_USE_BUTTONS, "وسطِ مرحله‌ی دکمه‌ای، متنِ آزاد نباید قبول بشه"

    await owner.tap("campaign_type:percent")
    for bad in ("0", "101", "abc", "-5", "10.5"):
        await owner.say(bad)
        assert owner.last_text == texts.CAMPAIGN_PERCENT_INVALID, f"«{bad}» باید رد بشه"
    await owner.say("۵۰")
    assert owner.last_text == texts.CAMPAIGN_ASK_MAX_DISCOUNT
    await owner.tap("campaign_skip_max")
    assert owner.last_text == texts.CAMPAIGN_ASK_CODE_CHOICE

    await owner.tap("campaign_code_choice:code")
    await owner.say("a$")
    assert owner.last_text == texts.CAMPAIGN_CODE_INVALID
    await owner.say("ab")
    assert owner.last_text == texts.CAMPAIGN_CODE_INVALID
    await owner.say("mehr۱۰")
    assert owner.last_text == texts.CAMPAIGN_CODE_TAKEN, "کدِ تکراری (حتی با حروف/رقمِ متفاوت) باید رد بشه"
    await owner.say("یلدا۱۴۰۵")
    assert owner.last_text == texts.CAMPAIGN_ASK_MIN_CART

    await owner.tap("campaign_skip_min_cart")
    assert owner.last_text == texts.CAMPAIGN_ASK_DURATION
    for bad in ("0", "366", "abc"):
        await owner.say(bad)
        assert owner.last_text == texts.CAMPAIGN_DURATION_INVALID, f"مدتِ «{bad}» باید رد بشه"
    await owner.say("30")
    assert owner.last_text == texts.CAMPAIGN_ASK_TOTAL_LIMIT
    await owner.say("abc")
    assert owner.last_text == texts.CAMPAIGN_LIMIT_INVALID
    await owner.tap("campaign_skip_total_limit")
    await owner.tap("campaign_percustomer:1")
    await owner.tap("campaign_create_confirm")

    campaigns = await _campaigns_in_db(shop_bot_id)
    assert [c.name for c in campaigns] == ["قدیمی", "یلدا"]
    new = campaigns[1]
    assert new.code == "یلدا1405", "رقمِ فارسی توی کد باید انگلیسی ذخیره بشه"
    assert new.min_cart_total_toman is None and new.total_usage_limit is None and new.per_customer_limit == 1
    assert new.ends_at - new.starts_at == datetime.timedelta(days=30)

    print("✅ test_wizard_input_validation_and_duplicate_code PASSED")


async def test_wizard_cancel_creates_nothing(main_dp) -> None:
    await _seed()
    owner = _Chat(main_dp, OWNER_TG_ID)
    await owner.say("🎯 کمپین‌ها")
    await owner.tap("campaign_new")
    await owner.say("لغوی")
    await owner.tap("campaign_type:fixed")
    await owner.say("1000")
    await owner.tap("campaign_code_choice:auto")
    await owner.say("5000")
    await owner.tap("campaign_duration:1")
    await owner.tap("campaign_skip_total_limit")
    await owner.tap("campaign_percustomer:1")
    await owner.tap("campaign_create_cancel")
    assert await _campaigns_in_db() == []

    await owner.tap("campaign_create_confirm")  # دکمه‌ی کهنه بعد از لغو
    assert owner.last_toast["text"] == texts.CAMPAIGN_WIZARD_STALE
    assert await _campaigns_in_db() == []

    print("✅ test_wizard_cancel_creates_nothing PASSED")


# =============================================================================
# ۴. فهرست / جزئیات / توقف / حذف / اعلام
# =============================================================================
async def test_list_view_toggle_delete_and_ended(main_dp) -> None:
    shop_bot_id = await _seed()
    unused_id = await _new_campaign(shop_bot_id, name="بی‌استفاده")
    used_id = await _new_campaign(shop_bot_id, name="استفاده‌شده", code="USED", discount_value=20)
    now = datetime.datetime.now(datetime.timezone.utc)
    ended_id = await _new_campaign(shop_bot_id, name="تمام‌شده", now=now - datetime.timedelta(days=9), duration_days=2)

    async with session_scope() as session:
        customer = await customer_service.get_or_create_customer(session, shop_bot_id, CUSTOMER_1_TG_ID, "مشتری", None)
        order = await order_service.create_order(session, shop_bot_id, customer.id, OrderType.ORDER, "تست", 80_000)
        order.campaign_id, order.discount_toman, order.cart_checkout_group_id = used_id, 20_000, "grp-1"

    owner = _Chat(main_dp, OWNER_TG_ID)
    await owner.say("🎯 کمپین‌ها")
    assert owner.last_text == texts.CAMPAIGNS_LIST_INTRO
    callbacks = _callbacks(owner.last_markup)
    for campaign_id in (unused_id, used_id, ended_id):
        assert f"campaign_view:{campaign_id}" in callbacks
    assert callbacks[-1] == "campaign_new"

    # متنِ جزئیات/فهرست (که با edit_text می‌رن) رو مستقیم از همون توابعِ هندلر می‌گیریم
    async with session_scope() as session:
        used = await campaign_service.get_owned(session, used_id, shop_bot_id)
        detail_text, detail_markup = await campaign_handlers._detail_payload(session, used)
        assert "استفاده‌شده" in detail_text and "USED" in detail_text and "🟢 فعال" in detail_text
        assert "استفاده‌شده: ۱ بار" in detail_text and "۲۰٬۰۰۰" in detail_text, detail_text
        assert f"campaign_toggle:{used_id}" in _callbacks(detail_markup) and f"campaign_delete:{used_id}" in _callbacks(detail_markup)
        ended = await campaign_service.get_owned(session, ended_id, shop_bot_id)
        ended_text, ended_markup = await campaign_handlers._detail_payload(session, ended)
        assert "⏹ تمام‌شده" in ended_text
        assert not any(c.startswith(("campaign_toggle:", "campaign_announce:")) for c in _callbacks(ended_markup)), (
            "کمپینِ تمام‌شده نباید دکمه‌ی توقف/اعلام داشته باشه"
        )

    await owner.tap(f"campaign_view:{used_id}")
    assert owner.session.answered_callbacks, "callback باید answer بشه"

    # --- توقف و ادامه ---
    await owner.tap(f"campaign_toggle:{unused_id}")
    assert owner.last_toast["text"] == texts.CAMPAIGN_PAUSED_TOAST
    assert not next(c for c in await _campaigns_in_db() if c.id == unused_id).is_active
    await owner.tap(f"campaign_toggle:{unused_id}")
    assert owner.last_toast["text"] == texts.CAMPAIGN_RESUMED_TOAST
    assert next(c for c in await _campaigns_in_db() if c.id == unused_id).is_active

    # --- کمپینِ تمام‌شده: نه توقف می‌شه، نه ادامه ---
    await owner.tap(f"campaign_toggle:{ended_id}")
    assert owner.last_toast["text"] == texts.CAMPAIGN_ALREADY_ENDED and owner.last_toast["show_alert"]
    assert next(c for c in await _campaigns_in_db() if c.id == ended_id).is_active, "وضعیتِ کمپینِ تمام‌شده نباید عوض بشه"

    # --- حذف: استفاده‌شده نه، بی‌استفاده آره ---
    await owner.tap(f"campaign_delete:{used_id}")
    assert owner.last_toast["text"] == texts.CAMPAIGN_CANNOT_DELETE_USED and owner.last_toast["show_alert"]
    assert used_id in {c.id for c in await _campaigns_in_db()}

    await owner.tap(f"campaign_delete:{unused_id}")
    assert owner.last_toast["text"] == texts.CAMPAIGN_DELETED_TOAST
    assert unused_id not in {c.id for c in await _campaigns_in_db()}

    async with session_scope() as session:
        list_text, list_markup = await campaign_handlers._list_payload(session, await session.get(ShopBot, shop_bot_id))
        assert list_text == texts.CAMPAIGNS_LIST_INTRO and f"campaign_view:{unused_id}" not in _callbacks(list_markup)

    print("✅ test_list_view_toggle_delete_and_ended PASSED")


async def test_announce_sends_default_text_through_shop_bot(main_dp, bot_manager) -> None:
    shop_bot_id = await _seed()
    shop_bot_instance = Bot(token=f"{SHOP_BOT_TG_ID}:FAKE", session=FakeSession())
    register_fake_shop_bot(bot_manager, shop_bot_id, shop_bot_instance)
    campaign_id = await _new_campaign(shop_bot_id, name="جشنواره‌ی مهر", code="MEHR10", discount_value=15, max_discount_toman=40_000)
    paused_id = await _new_campaign(shop_bot_id, name="متوقف", code="PAUSED")
    async with session_scope() as session:
        await campaign_service.set_active(session, await campaign_service.get_owned(session, paused_id, shop_bot_id), False)

    owner = _Chat(main_dp, OWNER_TG_ID)

    # بدونِ مشتری: اعلام معنی نداره
    await owner.tap(f"campaign_announce:{campaign_id}")
    assert owner.last_toast["text"] == texts.CUSTOMER_BROADCAST_NO_CUSTOMERS and owner.last_toast["show_alert"]

    async with session_scope() as session:
        await customer_service.get_or_create_customer(session, shop_bot_id, CUSTOMER_1_TG_ID, "مشتری یک", None)
        await customer_service.get_or_create_customer(session, shop_bot_id, CUSTOMER_2_TG_ID, "مشتری دو", None)

    # کمپینِ متوقف: فقط کمپینِ فعال قابلِ اعلامه
    await owner.tap(f"campaign_announce:{paused_id}")
    assert owner.last_toast["text"] == texts.CAMPAIGN_ANNOUNCE_ONLY_ACTIVE and owner.last_toast["show_alert"]
    assert shop_bot_instance.session.sent_messages == []

    async with session_scope() as session:
        campaign = await campaign_service.get_owned(session, campaign_id, shop_bot_id)
        announcement = texts.campaign_announcement_text(campaign)
    for expected in ("جشنواره‌ی مهر", "MEHR10", "۱۵ درصد", "۴۰٬۰۰۰", "کد تخفیف دارم"):
        assert expected in announcement, f"متنِ اعلام باید «{expected}» رو داشته باشه:\n{announcement}"

    await owner.tap(f"campaign_announce:{campaign_id}")
    expected_preview = texts.customer_broadcast_preview(announcement, 2)
    assert owner.last_text == expected_preview, "پیش‌نمایش باید همون متنِ آماده و تعدادِ درستِ مشتری رو نشون بده"
    # P21-D (F2): دکمهٔ «⏰ برایِ بعد از» به این کیبورد اضافه شد ⇒ تایید و لغو دیگر تنها دکمه‌ها نیستند
    assert _callbacks(owner.last_markup) == [
        "customer_broadcast_confirm",
        "customer_broadcast_schedule",
        "customer_broadcast_cancel",
    ]
    assert shop_bot_instance.session.sent_messages == [], "تا تایید نشده نباید چیزی برایِ مشتری‌ها بره"

    await owner.tap("customer_broadcast_confirm")
    await asyncio.sleep(0.5)  # صبر برایِ تسکِ پس‌زمینه‌ی ارسال
    sent = shop_bot_instance.session.sent_messages
    assert {m["chat_id"] for m in sent} == {CUSTOMER_1_TG_ID, CUSTOMER_2_TG_ID} and len(sent) == 2
    assert all(m["text"] == announcement for m in sent)
    assert owner.last_text == texts.customer_broadcast_sent_confirmation(2, 2)

    # لغو: چیزی نمی‌ره
    shop_bot_instance.session.sent_messages.clear()
    await owner.tap(f"campaign_announce:{campaign_id}")
    await owner.tap("customer_broadcast_cancel")
    await asyncio.sleep(0.2)
    assert shop_bot_instance.session.sent_messages == []

    print("✅ test_announce_sends_default_text_through_shop_bot PASSED")


# =============================================================================
# ۵. ایزوله‌بودنِ چندمستاجری
# =============================================================================
async def test_other_shop_owner_and_strangers_cannot_touch_campaigns(main_dp, bot_manager) -> None:
    shop_bot_id = await _seed()
    other_shop_bot_id = await seed_usable_shop(OTHER_OWNER_TG_ID, OTHER_SHOP_BOT_TG_ID)
    register_fake_shop_bot(bot_manager, shop_bot_id, Bot(token=f"{SHOP_BOT_TG_ID}:FAKE", session=FakeSession()))
    campaign_id = await _new_campaign(shop_bot_id, name="کمپینِ فروشگاهِ اول")
    async with session_scope() as session:
        await customer_service.get_or_create_customer(session, shop_bot_id, CUSTOMER_1_TG_ID, "مشتری", None)

    intruder = _Chat(main_dp, OTHER_OWNER_TG_ID)
    for action in ("campaign_view", "campaign_toggle", "campaign_delete", "campaign_announce"):
        await intruder.tap(f"{action}:{campaign_id}")
        assert intruder.last_toast["text"] == texts.CAMPAIGN_NOT_FOUND and intruder.last_toast["show_alert"], action
    await intruder.tap("campaign_view:abc")
    assert intruder.last_toast["text"] == texts.CAMPAIGN_NOT_FOUND, "شناسه‌ی نامعتبر هم بی‌خطر رد می‌شه"

    await intruder.say("🎯 کمپین‌ها")
    assert intruder.last_text == texts.CAMPAIGNS_EMPTY, "فروشگاه‌دارِ دیگه نباید کمپین‌هایِ این فروشگاه رو توی فهرستش ببینه"

    stranger = _Chat(main_dp, STRANGER_TG_ID)
    await stranger.tap(f"campaign_toggle:{campaign_id}")
    assert stranger.last_toast["show_alert"], "کسی که فروشگاه‌دار نیست هم نباید بتونه"
    await stranger.say("🎯 کمپین‌ها")
    assert stranger.last_text == texts.SHOP_BOT_NOT_SET_UP

    campaigns = await _campaigns_in_db()
    assert len(campaigns) == 1 and campaigns[0].is_active and campaigns[0].shop_bot_id == shop_bot_id
    assert await _campaigns_in_db(other_shop_bot_id) == []

    print("✅ test_other_shop_owner_and_strangers_cannot_touch_campaigns PASSED")


# =============================================================================
# ۶. دکمه‌یِ منو وسطِ FSM
# =============================================================================
async def test_menu_buttons_escape_stuck_states(main_dp) -> None:
    await _seed()
    owner = _Chat(main_dp, OWNER_TG_ID)

    # (الف) فروشگاه‌دار وسطِ «سوال‌هایِ چک‌اوت» روی «🎯 کمپین‌ها» می‌زنه: نباید متنِ دکمه
    # به‌عنوانِ سوال‌ها ذخیره بشه (دکمه‌ی جدید باید توی لیستِ escape باشه).
    await owner.say("📝 سوال‌هایِ چک‌اوتِ سبد")
    assert owner.last_text == texts.ASK_CHECKOUT_QUESTIONS
    await owner.say("🎯 کمپین‌ها")
    assert owner.last_text == texts.CAMPAIGNS_EMPTY
    async with session_scope() as session:
        shop_bot = (await session.execute(select(ShopBot))).scalar_one()
        assert shop_bot.checkout_questions is None, "متنِ دکمه نباید به‌عنوانِ سوالِ چک‌اوت ذخیره بشه"

    # (ب) وسطِ ویزاردِ کمپین روی یکی از دکمه‌هایی که *قبلاً* توی لیستِ escape نبود
    # («📣 پیام به مشتری‌ها») می‌زنه: ویزارد باید بسته بشه، نه اینکه متنِ بعدی اسمِ کمپین بشه.
    await owner.tap("campaign_new")
    assert owner.last_text == texts.CAMPAIGN_ASK_NAME
    await owner.say("📣 پیام به مشتری‌ها")
    assert owner.last_text == texts.CUSTOMER_BROADCAST_NO_CUSTOMERS
    await owner.say("یه اسمِ دلخواه")
    assert texts.CAMPAIGN_ASK_TYPE not in [m["text"] for m in owner.session.sent_messages], (
        "ویزارد باید با زدنِ دکمه‌ی منو بسته شده باشه؛ متنِ بعدی نباید اسمِ کمپین حساب بشه"
    )
    assert await _campaigns_in_db() == []

    # (ج) متنِ غیرِ دکمه وسطِ ویزارد همچنان ورودیِ ویزاردِ (نه اینکه state بی‌دلیل پاک بشه)
    await owner.say("🎯 کمپین‌ها")
    await owner.tap("campaign_new")
    await owner.say("اسمِ واقعی")
    assert owner.last_text == texts.CAMPAIGN_ASK_TYPE

    print("✅ test_menu_buttons_escape_stuck_states PASSED")


async def test_new_order_columns_are_nullable_for_old_rows() -> None:
    """ستون‌هایِ جدیدِ سفارش (campaign_id/discount_toman) نال‌پذیرن و ردیف‌هایِ قدیمی دست‌نخورده می‌مونن."""
    shop_bot_id = await _seed()
    async with session_scope() as session:
        customer = await customer_service.get_or_create_customer(session, shop_bot_id, CUSTOMER_1_TG_ID, "مشتری", None)
        order = await order_service.create_order(session, shop_bot_id, customer.id, OrderType.ORDER, "قدیمی", 50_000)
        assert order.campaign_id is None and order.discount_toman is None and order.status == OrderStatus.PENDING
    async with session_scope() as session:
        row = (await session.execute(select(OrderConsultation))).scalar_one()
        assert row.campaign_id is None and row.discount_toman is None and row.estimated_value_toman == 50_000

    print("✅ test_new_order_columns_are_nullable_for_old_rows PASSED")


async def main() -> None:
    main_dp, _shop_dp, bot_manager, _main_bot = build_test_dispatchers()

    await test_wizard_creates_percent_campaign_with_code(main_dp)
    await test_wizard_fixed_requires_min_cart_above_discount(main_dp)
    await test_wizard_input_validation_and_duplicate_code(main_dp)
    await test_wizard_cancel_creates_nothing(main_dp)
    await test_list_view_toggle_delete_and_ended(main_dp)
    await test_announce_sends_default_text_through_shop_bot(main_dp, bot_manager)
    await test_other_shop_owner_and_strangers_cannot_touch_campaigns(main_dp, bot_manager)
    await test_menu_buttons_escape_stuck_states(main_dp)
    await test_new_order_columns_are_nullable_for_old_rows()


if __name__ == "__main__":
    asyncio.run(main())
