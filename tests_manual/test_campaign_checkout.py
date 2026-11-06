"""
تست: تخفیفِ کمپین موقعِ چک‌اوتِ سبدِ خرید (فازِ ۳ — سازنده‌ی کمپین)، از طریقِ دیسپچرِ واقعیِ
ربات فروشگاهی.

پوشش:
۱. فروشگاهِ بدونِ کمپین: پیش‌نمایش، کیبورد، سفارش‌ها و اعلانِ فروشگاه‌دار *دقیقاً مثلِ قبل*.
۲. کمپینِ خودکار: پیش‌نمایشِ «قبل/تخفیف/نهایی»؛ مبلغِ هر ردیفِ سفارش *بعد از تخفیف* ذخیره
   می‌شه، سهمِ تخفیفِ ردیف‌ها دقیقاً جمعِ تخفیفِ کله‌ست، اعلانِ فروشگاه‌دار جداگانه نشون می‌ده.
۳. جریانِ کد: کدِ اشتباه/حداقلِ سبد/اعمال/حذف/برگشت + نرمال‌سازی (ي/ك عربی، رقمِ عربی).
۴. سقفِ هر مشتری + آزادشدنِ سهمیه وقتی فروشگاه‌دار سفارش رو رد می‌کنه.
۵. «ثبتِ نهایی» دوباره اعتبارسنجی می‌کنه: کمپین متوقف/تمام‌شده یا قیمتِ عوض‌شده → سفارش ثبت
   *نمی‌شه*، پیش‌نمایشِ تازه نشون داده می‌شه، و با تاییدِ دوباره با مبلغِ جدید ثبت می‌شه.
۶. رقابتِ دو مشتری رویِ آخرین ظرفیت: فقط یکی تخفیف می‌گیره (قفلِ FOR UPDATE).
۷. بله‌پی با مبلغِ بعد از تخفیف؛ سفارشِ رایگان (۱۰۰٪) پیشنهادِ پرداخت نداره.
۸. اکسل (دو ستونِ جدید) و آمارِ فروشِ تاییدشده (خالصِ بعد از تخفیف).

نکته‌ی هارنس: EditMessageText ثبت نمی‌شه؛ پس برایِ تاییدِ نهایی (که edit_text ـه) دیتابیس رو چک
می‌کنیم، و فقط پیام‌هایِ جدید (SendMessage) از sent_messages خونده می‌شن.

اجرا: python3 tests_manual/test_campaign_checkout.py
"""
from __future__ import annotations

import asyncio
import importlib
import datetime
import io
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
from checkout_helpers import run_checkout  # noqa: E402

from app.bots.shop_bot import keyboards as shop_keyboards  # noqa: E402
from app.bots.shop_bot import texts as shop_texts  # noqa: E402
from app.config import settings  # noqa: E402
from app.database.models import Campaign, CampaignDiscountType, Customer, OrderConsultation, OrderStatus, ShopBot  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import bale_credentials_service, bale_service, campaign_service, excel_export_service, product_service, stats_service  # noqa: E402
from app.services.admin_settings_service import update_setting  # noqa: E402
from openpyxl import load_workbook  # noqa: E402
from sqlalchemy import select  # noqa: E402

# خودِ ماژول (نه نمونه‌ی rate_limiter): حالتِ محدودکننده توی متغیرِ سطحِ ماژوله
rate_limiter_module = importlib.import_module("app.services.rate_limiter")

OWNER_TG_ID = 999951
SHOP_BOT_TG_ID = 999952

PERCENT = CampaignDiscountType.PERCENT
FIXED = CampaignDiscountType.FIXED

_user_counter = 999960
_created_invoices: list[dict] = []


def _fresh_user_id() -> int:
    """هر تست مشتری‌هایِ تازه می‌گیره، تا state (FSM) یه تستِ قبلی به تستِ بعدی نشت نکنه."""
    global _user_counter
    _user_counter += 1
    return _user_counter


async def _fake_create_invoice_link(bot_token, provider_token, title, description, payload, amount_rial) -> str:
    _created_invoices.append({"provider_token": provider_token, "payload": payload, "amount_rial": amount_rial})
    return f"https://fake-bale-pay.test/{payload}"


class _Shopper:
    """یه مشتریِ تستی با رباتِ فروشگاهیِ خودش (FakeSession جدا)، تا پیام‌هایِ مشتری‌ها قاطی نشن."""

    def __init__(self, shop_dp) -> None:
        self.dp = shop_dp
        self.user_id = _fresh_user_id()
        self.bot = Bot(token=f"{SHOP_BOT_TG_ID}:FAKE", session=FakeSession())
        self.session: FakeSession = self.bot.session  # type: ignore[assignment]
        self._n = self.user_id * 1000
        self._addr_saved = False  # بعد از اولین پیش‌نمایش آدرس در دفترچه ذخیره می‌شه (W5/C3)

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

    async def reach_preview(self, product_ids: list[int]) -> str:
        """محصول‌ها رو به سبد اضافه می‌کنه و تا پیش‌نمایشِ نهایی (بعد از دو سوالِ پیش‌فرض) می‌ره."""
        for product_id in product_ids:
            await self.tap(f"cart_add:{product_id}")
        await run_checkout(self.tap, self.say, has_saved_addresses=self._addr_saved)
        self._addr_saved = True  # W5/C3: چک‌اوتِ مرحله‌ایِ جدید (نام ← موبایل ← آدرس ← ... ← پیش‌نمایش)
        return self.last_text


def _has_url_button(markup) -> bool:
    return markup is not None and any(button.url for row in markup.inline_keyboard for button in row)


def _callbacks(markup) -> list[str]:
    if markup is None:
        return []
    # دکمه‌هایِ «✏️ ویرایش» (ck_edit:*) در W5/C3 به پیش‌نمایش اضافه شدن؛ این تست‌ها روی بقیه‌یِ دکمه‌ها قفلن.
    return [
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
        if button.callback_data and not button.callback_data.startswith("ck_edit:")
    ]


def _button(markup, callback_data: str):
    return next((b for row in markup.inline_keyboard for b in row if b.callback_data == callback_data), None)


# برچسبِ دکمه‌یِ کد رو از خودِ تابعِ کیبورد می‌گیریم (نه حروفِ دستی‌تایپ‌شده) تا به نیم‌فاصله/اعراب حساس نباشه
CODE_BUTTON_IDLE = _button(shop_keyboards.checkout_confirm_keyboard(show_code_button=True), "cart_discount_code").text
CODE_BUTTON_APPLIED = _button(shop_keyboards.checkout_confirm_keyboard(code_applied=True), "cart_discount_code").text


async def _seed() -> tuple[int, int, int]:
    """(shop_bot_id, برنج ۲۰۰٬۰۰۰، چای ۵۰٬۰۰۰) — هر دو بدونِ محدودیتِ موجودی، تا سفارش‌ها
    هیچ‌وقت به‌خاطرِ انقضایِ رزرو دخالت نکنن."""
    await reset_database()
    rate_limiter_module._windows.clear()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    async with session_scope() as session:
        rice = await product_service.create_product(session, shop_bot_id, "برنج", None, 200_000, None, stock_quantity=None)
        tea = await product_service.create_product(session, shop_bot_id, "چای", None, 50_000, None, stock_quantity=None)
    return shop_bot_id, rice.id, tea.id


async def _new_campaign(shop_bot_id: int, **overrides) -> int:
    args = dict(name="کمپین تست", discount_type=PERCENT, discount_value=10, duration_days=7)
    args.update(overrides)
    async with session_scope() as session:
        return (await campaign_service.create_campaign(session, shop_bot_id, **args)).id


async def _orders(shop_bot_id: int) -> list[OrderConsultation]:
    async with session_scope() as session:
        result = await session.execute(
            select(OrderConsultation).where(OrderConsultation.shop_bot_id == shop_bot_id).order_by(OrderConsultation.id)
        )
        return list(result.scalars().all())


def _owner_bot() -> Bot:
    return Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())


# =============================================================================
# ۱. بدونِ کمپین: هیچ چیزی عوض نشده
# =============================================================================
async def test_checkout_without_campaigns_is_unchanged(shop_dp, main_bot) -> None:
    shop_bot_id, rice, tea = await _seed()
    main_bot.session.sent_messages.clear()
    shopper = _Shopper(shop_dp)

    preview = await shopper.reach_preview([rice, tea])
    assert "۲۵۰٬۰۰۰" in preview
    assert "تخفیف" not in preview and "مبلغِ نهایی" not in preview
    assert _callbacks(shopper.last_markup) == ["cart_checkout_confirm", "cart_checkout_cancel"], "بدونِ کمپین، کیبوردِ پیش‌نمایش مثلِ قبله"

    await shopper.tap("cart_checkout_confirm")
    orders = await _orders(shop_bot_id)
    assert sorted(o.estimated_value_toman for o in orders) == [50_000, 200_000]
    assert all(o.campaign_id is None and o.discount_toman is None for o in orders)
    owner_text = main_bot.session.sent_messages[0]["text"]
    assert "جمعِ کل: ۲۵۰٬۰۰۰" in owner_text and "تخفیف" not in owner_text and "جمعِ اقلام" not in owner_text

    print("✅ test_checkout_without_campaigns_is_unchanged PASSED")


# =============================================================================
# ۲. کمپینِ خودکار
# =============================================================================
async def test_auto_campaign_applies_in_preview_orders_and_owner_notification(shop_dp, main_bot) -> None:
    shop_bot_id, rice, tea = await _seed()
    campaign_id = await _new_campaign(shop_bot_id, name="جشنواره‌ی خودکار")  # ۱۰٪ برایِ همه
    main_bot.session.sent_messages.clear()
    shopper = _Shopper(shop_dp)

    preview = await shopper.reach_preview([rice, tea])
    assert "جمعِ کل: ۲۵۰٬۰۰۰" in preview
    assert "🎁 تخفیفِ «جشنواره‌ی خودکار»: ۲۵٬۰۰۰ تومان" in preview
    assert "💰 مبلغِ نهایی: ۲۲۵٬۰۰۰ تومان" in preview
    assert _callbacks(shopper.last_markup) == ["cart_checkout_confirm", "cart_checkout_cancel"], "کمپینِ بدونِ کد دکمه‌ی «کد دارم» نمی‌خواد"

    await shopper.tap("cart_checkout_confirm")
    orders = await _orders(shop_bot_id)
    assert len(orders) == 2
    by_product = {o.product_id: o for o in orders}
    # مبلغِ هر ردیف *بعد از تخفیف* ذخیره می‌شه؛ سهمِ تخفیفِ هر ردیف متناسب با مبلغشه
    assert by_product[rice].estimated_value_toman == 180_000 and by_product[rice].discount_toman == 20_000
    assert by_product[tea].estimated_value_toman == 45_000 and by_product[tea].discount_toman == 5_000
    assert all(o.campaign_id == campaign_id for o in orders)
    assert sum(o.discount_toman for o in orders) == 25_000
    assert orders[0].cart_checkout_group_id == orders[1].cart_checkout_group_id

    assert len(main_bot.session.sent_messages) == 1
    owner_text = main_bot.session.sent_messages[0]["text"]
    for expected in ("جمعِ اقلام: ۲۵۰٬۰۰۰", "جشنواره‌ی خودکار", "۲۵٬۰۰۰", "جمعِ نهایی: ۲۲۵٬۰۰۰"):
        assert expected in owner_text, f"اعلانِ فروشگاه‌دار باید «{expected}» رو داشته باشه:\n{owner_text}"
    assert "جمعِ کل" not in owner_text

    async with session_scope() as session:
        assert await campaign_service.usage_stats(session, campaign_id) == (1, 25_000)

    print("✅ test_auto_campaign_applies_in_preview_orders_and_owner_notification PASSED")


async def test_fixed_campaign_applies_when_min_cart_reached(shop_dp) -> None:
    shop_bot_id, rice, tea = await _seed()
    await _new_campaign(shop_bot_id, name="ثابت", discount_type=FIXED, discount_value=30_000, min_cart_total_toman=100_000)

    small = _Shopper(shop_dp)
    preview = await small.reach_preview([tea])  # ۵۰٬۰۰۰ < حداقلِ ۱۰۰٬۰۰۰
    assert "تخفیف" not in preview and "۵۰٬۰۰۰" in preview

    big = _Shopper(shop_dp)
    preview = await big.reach_preview([rice, tea])  # ۲۵۰٬۰۰۰
    assert "🎁 تخفیفِ «ثابت»: ۳۰٬۰۰۰ تومان" in preview and "💰 مبلغِ نهایی: ۲۲۰٬۰۰۰ تومان" in preview
    await big.tap("cart_checkout_confirm")
    orders = [o for o in await _orders(shop_bot_id) if o.campaign_id is not None]
    assert len(orders) == 2 and sum(o.estimated_value_toman for o in orders) == 220_000
    assert sum(o.discount_toman for o in orders) == 30_000

    print("✅ test_fixed_campaign_applies_when_min_cart_reached PASSED")


# =============================================================================
# ۳. جریانِ کد
# =============================================================================
async def test_code_flow_errors_apply_remove_back_and_confirm(shop_dp) -> None:
    shop_bot_id, rice, tea = await _seed()
    code_campaign_id = await _new_campaign(shop_bot_id, name="جشنواره‌ی مهر", code="MEHR10")
    await _new_campaign(shop_bot_id, name="سبدِ بزرگ", code="BIG", discount_value=30, min_cart_total_toman=500_000)
    shopper = _Shopper(shop_dp)

    base_preview = await shopper.reach_preview([rice, tea])
    assert "تخفیف" not in base_preview, "کمپینِ کددار بدونِ کد اعمال نمی‌شه"
    button = _button(shopper.last_markup, "cart_discount_code")
    assert button is not None and button.text == CODE_BUTTON_IDLE

    retry = shop_texts.DISCOUNT_CODE_RETRY_HINT
    await shopper.tap("cart_discount_code")
    await shopper.say("WRONG")
    assert shopper.last_text == shop_texts.discount_code_problem("not_found") + retry
    await shopper.say("a b")
    assert shopper.last_text == shop_texts.discount_code_problem("not_found") + retry
    await shopper.say("big")
    assert shopper.last_text == shop_texts.discount_code_problem("min_cart", 500_000) + retry

    await shopper.say("mehr10")  # حروفِ کوچیک هم اوکیه
    text = shopper.last_text
    assert text.startswith(shop_texts.DISCOUNT_CODE_APPLIED)
    assert "(کدِ MEHR10)" in text and "💰 مبلغِ نهایی: ۲۲۵٬۰۰۰ تومان" in text
    assert _button(shopper.last_markup, "cart_discount_code").text == CODE_BUTTON_APPLIED

    await shopper.tap("cart_discount_code")
    await shopper.say("حذف")
    assert shopper.last_text.startswith(shop_texts.DISCOUNT_CODE_REMOVED)
    assert "مبلغِ نهایی" not in shopper.last_text
    assert _button(shopper.last_markup, "cart_discount_code").text == CODE_BUTTON_IDLE

    await shopper.tap("cart_discount_code")
    await shopper.say("برگشت")
    # ترتیبِ ردیف‌هایِ سبد (SELECT بدونِ ORDER BY) تضمین‌شده نیست؛ پس خط‌به‌خط و بدونِ توجه به ترتیب مقایسه می‌کنیم
    same_lines = sorted(shopper.last_text.splitlines()) == sorted(base_preview.splitlines())
    assert same_lines, "«برگشت» همون پیش‌نمایشِ قبلی رو بدونِ تغییر نشون می‌ده"

    await shopper.tap("cart_discount_code")
    await shopper.say("MEHR10")
    assert shopper.last_text.startswith(shop_texts.DISCOUNT_CODE_APPLIED)
    await shopper.tap("cart_checkout_confirm")

    orders = await _orders(shop_bot_id)
    assert len(orders) == 2 and all(o.campaign_id == code_campaign_id for o in orders)
    assert sum(o.estimated_value_toman for o in orders) == 225_000 and sum(o.discount_toman for o in orders) == 25_000

    print("✅ test_code_flow_errors_apply_remove_back_and_confirm PASSED")


async def test_code_normalization_arabic_variants_and_best_offer_wins(shop_dp) -> None:
    shop_bot_id, rice, tea = await _seed()
    await _new_campaign(shop_bot_id, name="یلدا", code="یلدا1405", discount_value=10)
    await _new_campaign(shop_bot_id, name="خودکارِ بهتر", discount_value=20)  # بدونِ کد، ۲۰٪
    shopper = _Shopper(shop_dp)

    preview = await shopper.reach_preview([rice, tea])
    assert "«خودکارِ بهتر»" in preview and "💰 مبلغِ نهایی: ۲۰۰٬۰۰۰ تومان" in preview, "خودکار از اول اعمال شده"

    # «ي» و «ك» عربی و رقمِ عربی-هندی: \u064a\u0644\u062f\u0627 + \u0661\u0664\u0660\u0665 = «يلدا١٤٠٥»
    await shopper.tap("cart_discount_code")
    await shopper.say("\u064a\u0644\u062f\u0627\u0661\u0664\u0660\u0665")
    text = shopper.last_text
    assert shop_texts.discount_code_problem("not_found") not in text, "کدِ عربی‌نویسی‌شده باید نرمال بشه و معتبر باشه"
    assert "کمپینِ «خودکارِ بهتر» تخفیفِ بیشتری می‌ده" in text, "کد معتبره ولی کمپینِ بهتری هست؛ باید همون اعمال بشه و به مشتری گفته بشه"
    assert "💰 مبلغِ نهایی: ۲۰۰٬۰۰۰ تومان" in text

    print("✅ test_code_normalization_arabic_variants_and_best_offer_wins PASSED")


async def test_code_attempts_are_rate_limited(shop_dp) -> None:
    shop_bot_id, rice, _tea = await _seed()
    await _new_campaign(shop_bot_id, name="جشنواره", code="MEHR10")
    shopper = _Shopper(shop_dp)
    await shopper.reach_preview([rice])
    await shopper.tap("cart_discount_code")

    for _ in range(campaign_service.CODE_ATTEMPTS_MAX):
        await shopper.say("NOPE")
        assert shopper.last_text.startswith(shop_texts.discount_code_problem("not_found"))
    await shopper.say("MEHR10")  # حتی کدِ درست هم بعد از سقفِ تلاش پذیرفته نمی‌شه
    assert shopper.last_text == shop_texts.DISCOUNT_CODE_TOO_MANY_ATTEMPTS

    print("✅ test_code_attempts_are_rate_limited PASSED")


# =============================================================================
# ۴. سقفِ هر مشتری + آزادشدنِ سهمیه با ردِ فروشگاه‌دار
# =============================================================================
async def test_per_customer_limit_and_reject_releases_quota(shop_dp, main_dp, bot_manager) -> None:
    shop_bot_id, rice, tea = await _seed()
    campaign_id = await _new_campaign(shop_bot_id, name="یک‌بارمصرف", code="ONCE10")  # هر مشتری ۱ بار
    shopper = _Shopper(shop_dp)
    register_fake_shop_bot(bot_manager, shop_bot_id, shopper.bot)

    await shopper.reach_preview([rice, tea])
    await shopper.tap("cart_discount_code")
    await shopper.say("once10")
    assert shopper.last_text.startswith(shop_texts.DISCOUNT_CODE_APPLIED)
    await shopper.tap("cart_checkout_confirm")
    first_orders = await _orders(shop_bot_id)
    assert len(first_orders) == 2 and all(o.campaign_id == campaign_id for o in first_orders)
    group_id = first_orders[0].cart_checkout_group_id

    # چک‌اوتِ دوم با همون کد: قبلاً استفاده کرده
    await shopper.reach_preview([rice])
    await shopper.tap("cart_discount_code")
    await shopper.say("once10")
    assert shopper.last_text == shop_texts.discount_code_problem("customer_limit") + shop_texts.DISCOUNT_CODE_RETRY_HINT

    # فروشگاه‌دار سفارشِ اول رو رد می‌کنه → یه استفاده آزاد می‌شه
    await main_dp.feed_update(_owner_bot(), make_callback_update(1, data=f"reject_cart_group:{group_id}", user_id=OWNER_TG_ID))
    async with session_scope() as session:
        assert await campaign_service.count_uses(session, campaign_id) == 0, "سفارشِ ردشده نباید یه استفاده حساب بشه"

    await shopper.say("once10")  # هنوز توی حالتِ واردکردنِ کد هست
    assert shopper.last_text.startswith(shop_texts.DISCOUNT_CODE_APPLIED)
    await shopper.tap("cart_checkout_confirm")

    orders = await _orders(shop_bot_id)
    rejected = [o for o in orders if o.status == OrderStatus.REJECTED]
    discounted_alive = [o for o in orders if o.campaign_id == campaign_id and o.status != OrderStatus.REJECTED]
    assert len(rejected) == 2 and len(discounted_alive) == 1
    async with session_scope() as session:
        assert await campaign_service.count_uses(session, campaign_id) == 1

    print("✅ test_per_customer_limit_and_reject_releases_quota PASSED")


# =============================================================================
# ۵. «ثبتِ نهایی» دوباره اعتبارسنجی می‌کنه
# =============================================================================
async def test_confirm_revalidates_when_campaign_is_paused(shop_dp) -> None:
    shop_bot_id, rice, tea = await _seed()
    campaign_id = await _new_campaign(shop_bot_id, name="خودکار")
    shopper = _Shopper(shop_dp)

    preview = await shopper.reach_preview([rice, tea])
    assert "💰 مبلغِ نهایی: ۲۲۵٬۰۰۰ تومان" in preview

    async with session_scope() as session:  # فروشگاه‌دار وسطِ کار کمپین رو متوقف می‌کنه
        await campaign_service.set_active(session, await session.get(Campaign, campaign_id), False)

    await shopper.tap("cart_checkout_confirm")
    assert await _orders(shop_bot_id) == [], "مشتری مبلغِ ۲۲۵٬۰۰۰ رو دیده؛ با کمپینِ متوقف نباید سفارش ثبت بشه"

    await shopper.tap("cart_checkout_confirm")  # تاییدِ دوباره، این‌بار با مبلغِ جدید (بدونِ تخفیف)
    orders = await _orders(shop_bot_id)
    assert len(orders) == 2 and sum(o.estimated_value_toman for o in orders) == 250_000
    assert all(o.campaign_id is None and o.discount_toman is None for o in orders)

    print("✅ test_confirm_revalidates_when_campaign_is_paused PASSED")


async def test_confirm_revalidates_when_price_changes(shop_dp) -> None:
    shop_bot_id, rice, tea = await _seed()
    shopper = _Shopper(shop_dp)
    await shopper.reach_preview([rice, tea])

    async with session_scope() as session:  # فروشگاه‌دار وسطِ کار قیمتِ برنج رو عوض می‌کنه
        (await product_service.get_by_id(session, rice)).price_toman = 210_000

    await shopper.tap("cart_checkout_confirm")
    assert await _orders(shop_bot_id) == [], "قیمت بعد از پیش‌نمایش عوض شده؛ مشتری باید مبلغِ جدید رو ببینه و دوباره تایید کنه"
    await shopper.tap("cart_checkout_confirm")
    orders = await _orders(shop_bot_id)
    assert sum(o.estimated_value_toman for o in orders) == 260_000

    print("✅ test_confirm_revalidates_when_price_changes PASSED")


async def test_confirm_drops_code_when_campaign_ended(shop_dp) -> None:
    shop_bot_id, rice, tea = await _seed()
    campaign_id = await _new_campaign(shop_bot_id, name="در حالِ تموم‌شدن", code="MEHR10")
    shopper = _Shopper(shop_dp)

    await shopper.reach_preview([rice, tea])
    await shopper.tap("cart_discount_code")
    await shopper.say("MEHR10")
    assert "💰 مبلغِ نهایی: ۲۲۵٬۰۰۰ تومان" in shopper.last_text

    now = datetime.datetime.now(datetime.timezone.utc)
    async with session_scope() as session:  # بینِ پیش‌نمایش و ثبتِ نهایی، مدتش تموم می‌شه
        campaign = await session.get(Campaign, campaign_id)
        campaign.starts_at = now - datetime.timedelta(days=2)
        campaign.ends_at = now - datetime.timedelta(minutes=1)

    await shopper.tap("cart_checkout_confirm")
    assert await _orders(shop_bot_id) == [], "با کمپینِ تمام‌شده نباید سفارشِ تخفیف‌دار ثبت بشه"
    await shopper.tap("cart_checkout_confirm")
    orders = await _orders(shop_bot_id)
    assert len(orders) == 2 and sum(o.estimated_value_toman for o in orders) == 250_000
    assert all(o.campaign_id is None for o in orders), "کدِ تمام‌شده باید از چک‌اوت برداشته شده باشه"

    print("✅ test_confirm_drops_code_when_campaign_ended PASSED")


# =============================================================================
# ۶. رقابتِ دو مشتری رویِ آخرین ظرفیت
# =============================================================================
async def test_last_slot_race_between_two_customers(shop_dp) -> None:
    shop_bot_id, rice, tea = await _seed()
    campaign_id = await _new_campaign(shop_bot_id, name="آخرین ظرفیت", code="LAST", total_usage_limit=1, per_customer_limit=None)
    shoppers = [_Shopper(shop_dp), _Shopper(shop_dp)]
    for shopper in shoppers:
        await shopper.reach_preview([rice, tea])
        await shopper.tap("cart_discount_code")
        await shopper.say("last")
        assert "💰 مبلغِ نهایی: ۲۲۵٬۰۰۰ تومان" in shopper.last_text, "هر دو (هنوز) تخفیف رو می‌بینن؛ ظرفیت فقط ۱ ـه"

    # هر دو هم‌زمان «ثبتِ نهایی» رو می‌زنن
    await asyncio.gather(*[shopper.tap("cart_checkout_confirm") for shopper in shoppers])

    orders = await _orders(shop_bot_id)
    assert len(orders) == 2, f"فقط سفارشِ برنده (۲ ردیف) باید ثبت شده باشه؛ ولی {len(orders)} ردیف هست"
    assert all(o.campaign_id == campaign_id for o in orders)
    async with session_scope() as session:
        assert await campaign_service.count_uses(session, campaign_id) == 1
        customers = {c.telegram_id: c.id for c in (await session.execute(select(Customer))).scalars().all()}
    winner_customer_id = orders[0].customer_id
    loser = next(s for s in shoppers if customers[s.user_id] != winner_customer_id)

    # بازنده هنوز می‌تونه (با مبلغِ کاملِ بدونِ تخفیف) ثبت کنه
    await loser.tap("cart_checkout_confirm")
    orders = await _orders(shop_bot_id)
    assert len(orders) == 4 and sum(1 for o in orders if o.campaign_id == campaign_id) == 2
    loser_orders = [o for o in orders if o.customer_id == customers[loser.user_id]]
    assert sum(o.estimated_value_toman for o in loser_orders) == 250_000 and all(o.campaign_id is None for o in loser_orders)

    print("✅ test_last_slot_race_between_two_customers PASSED")


# =============================================================================
# ۷. تایید و آمار + اکسل
# =============================================================================
async def test_owner_confirm_stats_and_excel_use_discounted_values(shop_dp, main_dp, bot_manager) -> None:
    shop_bot_id, rice, tea = await _seed()
    campaign_id = await _new_campaign(shop_bot_id, name="جشنواره‌ی اکسل")
    shopper = _Shopper(shop_dp)
    register_fake_shop_bot(bot_manager, shop_bot_id, shopper.bot)

    await shopper.reach_preview([rice, tea])
    await shopper.tap("cart_checkout_confirm")
    group_id = (await _orders(shop_bot_id))[0].cart_checkout_group_id
    await main_dp.feed_update(_owner_bot(), make_callback_update(1, data=f"confirm_cart_group:{group_id}", user_id=OWNER_TG_ID))
    assert all(o.status == OrderStatus.CONFIRMED for o in await _orders(shop_bot_id))

    now = datetime.datetime.now(datetime.timezone.utc)
    async with session_scope() as session:
        stats = await stats_service.get_shop_daily_stats(
            session, shop_bot_id, now - datetime.timedelta(days=1), now + datetime.timedelta(minutes=5)
        )
        assert stats["confirmed_revenue_today_toman"] == 225_000, "فروشِ آمار باید خالصِ بعد از تخفیف باشه، نه ۲۵۰٬۰۰۰"
        raw = await excel_export_service.build_orders_workbook(session, shop_bot_id)

    sheet = load_workbook(io.BytesIO(raw)).active
    headers = [cell.value for cell in sheet[1]]
    assert headers[-2:] == ["تخفیفِ کمپین (تومان)", "کمپین"], "ستون‌هایِ کمپین باید *آخرِ* برگه اضافه شده باشن"
    value_col = headers.index("ارزشِ تخمینی (تومان)")
    all_rows = [[cell.value for cell in row] for row in sheet.iter_rows(min_row=2)]
    # P22: ردیفِ آخر «جمعِ کل» است و از ردیف‌هایِ داده جدا می‌شود
    totals_row = all_rows[-1]
    assert totals_row[0] == "جمعِ کل", totals_row
    assert totals_row[value_col] == 225_000, totals_row
    rows = all_rows[:-1]
    assert len(rows) == 2
    assert sorted(row[value_col] for row in rows) == [45_000, 180_000], "ارزش تخمینی توی اکسل بعد از تخفیفه"
    assert sorted(row[-2] for row in rows) == [5_000, 20_000]
    assert all(row[-1] == "جشنواره‌ی اکسل" for row in rows)
    assert campaign_id is not None

    print("✅ test_owner_confirm_stats_and_excel_use_discounted_values PASSED")


# =============================================================================
# ۸. بله‌پی + سفارشِ رایگان (این تست آخره؛ تنظیماتِ بله‌پی رو فعال می‌کنه)
# =============================================================================
async def test_bale_invoice_uses_discounted_amount_and_free_order_skips_payment(shop_dp, main_bot, bot_manager) -> None:
    from app import main as app_main

    shop_bot_id, rice, tea = await _seed()
    shopper = _Shopper(shop_dp)
    register_fake_shop_bot(bot_manager, shop_bot_id, shopper.bot)
    app_main._state["bot_manager"] = bot_manager
    app_main._state["main_bot"] = main_bot

    settings.bale_bot_token = "TEST-PLATFORM-BALE-BOT-TOKEN"
    _created_invoices.clear()
    bale_service.create_invoice_link = _fake_create_invoice_link
    async with session_scope() as session:
        await update_setting(session, "bale_pay_enabled", True)
        # P26: لینکِ پرداخت = چتِ رباتِ پرداخت؛ نامِ کاربری را به‌جایِ getMe می‌گذاریم (تست به شبکه نمی‌زند).
        bale_credentials_service.remember_pay_bot_username('platform_pay_bot')
        shop_bot = await session.get(ShopBot, shop_bot_id)
        shop_bot.bale_provider_token = "SHOP-OWN-PROVIDER-TOKEN"
        # P41: پرداختِ سفارش فقط با جفتِ کاملِ خودِ فروشگاه ساخته می‌شود (رباتِ بله + درگاهِ خودش)
        shop_bot.bale_encrypted_token = "222222:SHOP-OWN-BALE-BOT-TOKEN"
        shop_bot.bale_bot_id = 222222
        shop_bot.bale_bot_username = "shop_own_bale_bot"
        shop_bot.bale_bot_enabled = True
        await session.commit()

    ten_percent_id = await _new_campaign(shop_bot_id, name="۱۰٪")
    await shopper.reach_preview([rice, tea])
    await shopper.tap("cart_checkout_confirm")

    assert shopper.last_text == shop_texts.online_payment_offer(225_000), "پیشنهادِ پرداخت باید مبلغِ بعد از تخفیف باشه"
    assert len(_created_invoices) == 1 and _created_invoices[0]["amount_rial"] == 2_250_000
    assert _created_invoices[0]["payload"].startswith("cartgroup-")

    group_id = (await _orders(shop_bot_id))[0].cart_checkout_group_id

    async def fake_inquire_ok(bot_token, transaction_id):
        return {"status": "successful"}

    bale_service.inquire_transaction = fake_inquire_ok
    main_bot.session.sent_messages.clear()
    await app_main._handle_bale_successful_payment(
        {"invoice_payload": f"cartgroup-{group_id}-abcdef1234", "telegram_payment_charge_id": "chg_campaign_1"}
    )
    assert len(main_bot.session.sent_messages) == 1 and "۲۲۵٬۰۰۰" in main_bot.session.sent_messages[0]["text"]

    # --- سفارشِ رایگان (۱۰۰٪): نه فاکتور ساخته می‌شه، نه پیشنهادِ پرداخت ---
    async with session_scope() as session:
        await campaign_service.set_active(session, await session.get(Campaign, ten_percent_id), False)
    await _new_campaign(shop_bot_id, name="هدیه", discount_value=100)
    _created_invoices.clear()
    messages_before = len(shopper.session.sent_messages)

    preview = await shopper.reach_preview([rice, tea])
    assert "💰 مبلغِ نهایی: ۰ تومان" in preview
    await shopper.tap("cart_checkout_confirm")
    assert _created_invoices == [], "سفارشِ رایگان فاکتورِ بله‌پی نمی‌خواد"
    new_messages = shopper.session.sent_messages[messages_before:]
    assert new_messages[-1]["text"] == preview, "آخرین پیام همون پیش‌نمایشه؛ هیچ پیشنهادِ پرداختی بعدش نیومده"
    assert not any(_has_url_button(m["reply_markup"]) for m in new_messages), "سفارشِ رایگان نباید دکمه‌ی پرداختِ آنلاین داشته باشه"
    free_orders = [o for o in await _orders(shop_bot_id) if o.cart_checkout_group_id != group_id]
    assert len(free_orders) == 2 and all(o.estimated_value_toman == 0 for o in free_orders)
    assert sum(o.discount_toman for o in free_orders) == 250_000

    print("✅ test_bale_invoice_uses_discounted_amount_and_free_order_skips_payment PASSED")


async def main() -> None:
    main_dp, shop_dp, bot_manager, main_bot = build_test_dispatchers()

    await test_checkout_without_campaigns_is_unchanged(shop_dp, main_bot)
    await test_auto_campaign_applies_in_preview_orders_and_owner_notification(shop_dp, main_bot)
    await test_fixed_campaign_applies_when_min_cart_reached(shop_dp)
    await test_code_flow_errors_apply_remove_back_and_confirm(shop_dp)
    await test_code_normalization_arabic_variants_and_best_offer_wins(shop_dp)
    await test_code_attempts_are_rate_limited(shop_dp)
    await test_per_customer_limit_and_reject_releases_quota(shop_dp, main_dp, bot_manager)
    await test_confirm_revalidates_when_campaign_is_paused(shop_dp)
    await test_confirm_revalidates_when_price_changes(shop_dp)
    await test_confirm_drops_code_when_campaign_ended(shop_dp)
    await test_last_slot_race_between_two_customers(shop_dp)
    await test_owner_confirm_stats_and_excel_use_discounted_values(shop_dp, main_dp, bot_manager)
    await test_bale_invoice_uses_discounted_amount_and_free_order_skips_payment(shop_dp, main_bot, bot_manager)


if __name__ == "__main__":
    asyncio.run(main())
