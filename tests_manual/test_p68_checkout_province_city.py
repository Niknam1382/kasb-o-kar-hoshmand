"""
تست: پ۶۸ (موردِ ۱۹) — «استان» و «شهر» دو زیرگامِ خاموش‌شدنی از چک‌اوتِ سبد، با پیش‌فرضِ «نپرس».

پوشش:
۱. خالصِ پیکربندی: پیش‌فرضِ خاموش، ستونِ خالی ⇒ همان پیش‌فرض (بدونِ مایگریشن)، round-trip،
   کلیدهایِ دستکاری‌شده و اینکه قاعده‌یِ «آدرس+موبایل هم‌زمان خاموش نشود» دست‌نخورده می‌ماند.
۲. خالصِ گراف: زنجیره‌یِ زیرمرحله‌هایِ آدرس با ترکیب‌هایِ روشن/خاموش (`checkout_flow.address_*`).
۳. راهنمایِ فارسی: فقط همان چیزی که پرسیده نمی‌شود یادآوری می‌شود.
۴. پنلِ «🧾 گام‌هایِ پیش‌فرضِ چک‌اوت»: دو ردیفِ تازه، راهنما، بازگشتِ ستون به خالی، متنِ پرسش.
۵. end-to-end: با پیکربندیِ خالی هیچ پرسشِ استان/شهری نمی‌آید و آدرسِ تازه بی‌region ذخیره می‌شود.
۶. end-to-end: با هر دو روشن زنجیره‌یِ چهارمرحله‌ای برمی‌گردد (رفتارِ قبلیِ محصول).
۷. end-to-end: استان روشن + شهر خاموش ⇒ راهنما فقط شهر را نام می‌برد.
۸. سبدِ فقط‌دیجیتال با region روشن هم هیچ پرسشِ آدرسی ندارد.
۹. آدرسِ دفترچه‌ایِ دارایِ استان/شهر با region خاموش هم کامل نمایش داده می‌شود.

اجرا: python3 tests_manual/test_p68_checkout_province_city.py
"""
from __future__ import annotations

import asyncio
import json
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from sqlalchemy import select  # noqa: E402

from harness import build_test_dispatchers, reset_database  # noqa: E402
from phase4_helpers import Chat  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402
from test_orders_w2 import _Env, _seed  # noqa: E402

from app.bots.main_bot import texts as main_texts  # noqa: E402
from app.bots.shop_bot import checkout_ui  # noqa: E402
from app.database.models import Customer, CustomerAddress, ShopBot  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import (  # noqa: E402
    address_book_service,
    checkout_config_service as cfg,
    checkout_flow,
    product_service,
)

OWNER_TG_ID = 999_941
SHOP_BOT_TG_ID = 999_942
ADDRESS = "خیابانِ آزادی، کوچه‌یِ دوم، پلاکِ ده"
PHONE = "09121112233"
REGION_ON = json.dumps({"province": {"on": True}, "city": {"on": True}}, ensure_ascii=False)


def _datas(markup) -> list[str]:
    return [b.callback_data for row in markup.inline_keyboard for b in row if b.callback_data] if markup else []


async def _set_config(shop_bot_id: int, raw: str | None) -> None:
    async with session_scope() as session:
        row = (await session.execute(select(ShopBot).where(ShopBot.id == shop_bot_id))).scalar_one()
        row.checkout_config = raw


async def _config_of(shop_bot_id: int) -> str | None:
    async with session_scope() as session:
        return (await session.execute(select(ShopBot.checkout_config).where(ShopBot.id == shop_bot_id))).scalar_one()


async def _addresses_of_shop(shop_bot_id: int) -> list[CustomerAddress]:
    async with session_scope() as session:
        rows = list(
            (
                await session.execute(
                    select(CustomerAddress)
                    .join(Customer, Customer.id == CustomerAddress.customer_id)
                    .where(Customer.shop_bot_id == shop_bot_id)
                    .order_by(CustomerAddress.id)
                )
            ).scalars().all()
        )
        return rows


async def _env(shop_dp, main_dp, bot_manager, main_bot) -> _Env:
    shop_bot_id, p1, p2 = await _seed()
    return _Env(shop_dp, main_dp, bot_manager, main_bot, shop_bot_id, p1, p2)


async def _up_to_address(env: _Env) -> None:
    """سبدِ فیزیکی ← نام ← موبایل؛ بعد از این، نوبتِ زیرگام‌هایِ آدرس است."""
    await env.cust_cb(f"cart_add:{env.p1}")
    await env.cust_cb("cart_checkout_start")
    await env.cust_say("علی رضایی")
    await env.cust_say(PHONE)


async def _finish_checkout(env: _Env) -> None:
    """کدپستی ← ارسال (هماهنگی) ← توضیح ← پیش‌نمایش ← ثبتِ نهایی."""
    await env.cust_cb("ck_skip")  # کدپستی
    assert "هماهنگی" in env.customer_msgs()[-1], env.customer_msgs()[-1]
    await env.cust_cb("ck_ship:0")
    await env.cust_cb("ck_skip")  # توضیح
    assert "ثبت بشه؟" in env.customer_msgs()[-1], env.customer_msgs()[-1]
    await env.cust_cb("cart_checkout_confirm")


# ============================================================================= ۱ — خالصِ پیکربندی
def test_region_steps_default_to_off() -> None:
    steps = cfg.parse(None)
    assert steps["province"].enabled is False and steps["city"].enabled is False, "پیش‌فرضِ موردِ ۱۹: نپرس"
    assert steps["address"].enabled is True and steps["phone"].enabled is True, "گام‌هایِ اصلی دست‌نخورده‌اند"
    assert cfg.dump(steps) is None, "پیش‌فرضِ تازه هم ستون را خالی می‌گذارد ⇒ هیچ مایگریشنی لازم نیست"
    assert cfg.disabled_positions(steps) == frozenset({"prov", "city"})
    assert cfg.DEFAULT_QUESTIONS["province"] == checkout_ui.ASK_PROVINCE
    assert cfg.DEFAULT_QUESTIONS["city"] == checkout_ui.ASK_CITY

    on = cfg.set_enabled(steps, "province", True)
    assert on is not None and on["province"].enabled is True
    stored = cfg.dump(on)
    assert stored and json.loads(stored)["province"] == {"on": True, "q": checkout_ui.ASK_PROVINCE}
    assert cfg.dump(cfg.parse(stored)) == stored, "round-trip پایدار"
    assert cfg.dump(cfg.set_enabled(on, "province", False)) is None, "برگشت به پیش‌فرض ⇒ ستون دوباره خالی"

    # زیرگام‌ها قاعده‌یِ ایمنیِ آدرس+موبایل را نمی‌شکنند و ورودیِ ناشناخته نادیده گرفته می‌شود
    assert cfg.set_enabled(steps, "province", False) is not None
    assert cfg.set_enabled(cfg.set_enabled(steps, "address", False), "phone", False) is None
    assert cfg.parse('{"prov": {"on": true}, "substep": {"on": true}}') == steps, "کلیدِ ناشناخته ⇒ پیش‌فرض"

    edited = cfg.set_question(steps, "city", "شهرتان را بنویسید")
    assert edited["city"].question == "شهرتان را بنویسید"
    assert cfg.set_question(steps, "city", "ی" * (cfg.MAX_QUESTION_LENGTH + 1)) is None
    assert cfg.set_question(edited, "city", "خالی")["city"].question == checkout_ui.ASK_CITY
    print("✅ test_region_steps_default_to_off PASSED")


# ============================================================================= ۲ — خالصِ گرافِ آدرس
def test_address_chain_follows_the_toggles() -> None:
    full = frozenset()
    off = frozenset({"prov", "city"})
    assert checkout_flow.address_chain(full) == ["prov", "city", "addr_text", "postal"]
    assert checkout_flow.address_chain(off) == ["addr_text", "postal"]
    assert checkout_flow.address_chain(frozenset({"city"})) == ["prov", "addr_text", "postal"]
    assert checkout_flow.address_first(full) == "prov"
    assert checkout_flow.address_first(off) == "addr_text"
    assert checkout_flow.address_next("addr_text", off) == "postal"
    assert checkout_flow.address_next("postal", off) == "postal", "آخرین زیرمرحله جایش می‌ماند (فراخوانی نمی‌شود)"
    assert checkout_flow.address_next("prov", off) == "addr_text", "آپدیتِ کهنه از اولِ زنجیره ادامه می‌دهد"
    assert checkout_flow.address_next("prov", full) == "city"
    assert checkout_flow.address_next("city", full) == "addr_text"
    # گامِ «آدرس» خودش خاموش باشد زنجیره هیچ‌وقت پرسیده نمی‌شود ⇒ گرافِ ماکرو دست‌نخورده است
    assert checkout_flow.step_order(physical=True, disabled=off | {"addr"}) == ["name", "phone", "note"]
    print("✅ test_address_chain_follows_the_toggles PASSED")


# ============================================================================= ۳ — راهنمایِ فارسی
def test_region_hint_names_only_what_is_not_asked() -> None:
    assert checkout_ui.region_hint([]) == ""
    assert checkout_ui.region_hint(["استان", "شهر"]) == checkout_ui.ADDRESS_REGION_HINT
    only_city = checkout_ui.region_hint(["شهر"])
    assert only_city == "🧾 شهر را جدا نمی‌پرسیم؛ آن را هم داخلِ همین آدرس بنویس.", only_city
    print("✅ test_region_hint_names_only_what_is_not_asked PASSED")


# ============================================================================= ۴ — پنلِ فروشگاه‌دار
async def test_owner_panel_shows_the_two_substeps(main_dp) -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    owner = Chat(main_dp, OWNER_TG_ID)

    await owner.say("📝 سوال‌هایِ چک‌اوتِ سبد")
    await owner.tap("cs_open")
    page = owner.last_edit_text
    assert "• 🗺 استان: خاموش (زیرِ گامِ «آدرسِ تحویل»)" in page, page
    assert "• 🏙 شهر: خاموش (زیرِ گامِ «آدرسِ تحویل»)" in page, page
    assert main_texts.CHECKOUT_STEP_REGION_HINT in page, page
    data = _datas(owner.last_edit_markup)
    assert "cs_toggle:province" in data and "cs_ask:city" in data and data[-1] == "cs_back", data

    await owner.tap("cs_toggle:province")
    stored = json.loads(await _config_of(shop_bot_id))
    assert stored["province"]["on"] is True and stored["city"]["on"] is False, stored
    assert "• 🗺 استان: روشن (زیرِ گامِ «آدرسِ تحویل»)" in owner.last_edit_text, owner.last_edit_text

    await owner.tap("cs_toggle:city")
    assert json.loads(await _config_of(shop_bot_id))["city"]["on"] is True
    # دابل‌تپ‌ها ⇒ بازگشت به پیش‌فرض ⇒ ستون دوباره خالی (نه JSONِ «همه روشن»)
    await owner.tap("cs_toggle:province")
    await owner.tap("cs_toggle:city")
    assert await _config_of(shop_bot_id) is None, "پیش‌فرضِ جدید با ستونِ خالی یکی است"

    # متنِ پرسشِ زیرگام هم ویرایش‌شدنی است و روشن/خاموش از همان صفحه‌یِ جزئیات
    await owner.tap("cs_ask:province")
    await owner.say("استانِ محلِ سکونت؟")
    assert json.loads(await _config_of(shop_bot_id))["province"] == {"on": False, "q": "استانِ محلِ سکونت؟"}
    await owner.tap("cs_toggle:province")
    assert json.loads(await _config_of(shop_bot_id))["province"]["on"] is True
    await owner.tap("cs_back")
    assert _datas(owner.last_edit_markup) == ["cs_open"]
    print("✅ test_owner_panel_shows_the_two_substeps PASSED")


# ============================================================================= ۵ تا ۷ — چک‌اوتِ مشتری
async def test_default_checkout_does_not_ask_region(shop_dp, main_dp, bot_manager, main_bot) -> None:
    env = await _env(shop_dp, main_dp, bot_manager, main_bot)
    await _up_to_address(env)
    prompt = env.customer_msgs()[-1]
    assert prompt == f"{checkout_ui.ASK_ADDRESS_TEXT}\n\n{checkout_ui.ADDRESS_REGION_HINT}", prompt
    assert not any(checkout_ui.ASK_PROVINCE in m for m in env.customer_msgs()), "با پیش‌فرضِ تازه پرسشِ استان ندارد"
    await env.cust_say(ADDRESS)
    assert "کدپستی" in env.customer_msgs()[-1]
    await _finish_checkout(env)

    rows = await _addresses_of_shop(env.shop_bot_id)
    assert len(rows) == 1 and rows[0].address == ADDRESS, rows
    assert rows[0].province is None and rows[0].city is None and rows[0].label is None, "بی‌region ذخیره می‌شود"
    orders = await env.rows()
    assert orders and all(o.customer_address == ADDRESS for o in orders), orders[0].customer_address
    print("✅ test_default_checkout_does_not_ask_region PASSED")


async def test_region_on_restores_the_full_chain(shop_dp, main_dp, bot_manager, main_bot) -> None:
    env = await _env(shop_dp, main_dp, bot_manager, main_bot)
    await _set_config(env.shop_bot_id, REGION_ON)
    await _up_to_address(env)
    assert env.customer_msgs()[-1] == checkout_ui.ASK_PROVINCE
    await env.cust_say("تهران")
    assert env.customer_msgs()[-1] == checkout_ui.ASK_CITY
    await env.cust_say("کرج")
    assert env.customer_msgs()[-1] == checkout_ui.ASK_ADDRESS_TEXT, "با هر دو روشن راهنما لازم نیست"
    await env.cust_say(ADDRESS)
    await _finish_checkout(env)

    rows = await _addresses_of_shop(env.shop_bot_id)
    assert (rows[0].province, rows[0].city, rows[0].label) == ("تهران", "کرج", "کرج"), rows[0]
    orders = await env.rows()
    assert orders and all(f"تهران، کرج، {ADDRESS}" == o.customer_address for o in orders), orders[0].customer_address
    print("✅ test_region_on_restores_the_full_chain PASSED")


async def test_province_only_reminds_about_the_city(shop_dp, main_dp, bot_manager, main_bot) -> None:
    env = await _env(shop_dp, main_dp, bot_manager, main_bot)
    await _set_config(env.shop_bot_id, json.dumps({"province": {"on": True}}, ensure_ascii=False))
    await _up_to_address(env)
    assert env.customer_msgs()[-1] == checkout_ui.ASK_PROVINCE
    await env.cust_say("تهران")
    prompt = env.customer_msgs()[-1]
    assert prompt == f"{checkout_ui.ASK_ADDRESS_TEXT}\n\n{checkout_ui.region_hint(['شهر'])}", prompt
    assert "استان" not in prompt.split("\n\n")[1], "راهنما چیزِ پرسیده‌شده را دوباره نمی‌خواهد"
    await env.cust_say(ADDRESS)
    await _finish_checkout(env)

    rows = await _addresses_of_shop(env.shop_bot_id)
    assert rows[0].province == "تهران" and rows[0].city is None
    orders = await env.rows()
    assert orders[0].customer_address == f"تهران، {ADDRESS}", orders[0].customer_address
    print("✅ test_province_only_reminds_about_the_city PASSED")


# ============================================================================= ۸ و ۹ — مرزهایِ بی‌تغییر
async def test_digital_cart_never_asks_region_even_when_on(shop_dp, main_dp, bot_manager, main_bot) -> None:
    env = await _env(shop_dp, main_dp, bot_manager, main_bot)
    async with session_scope() as session:
        digital = await product_service.create_product(session, env.shop_bot_id, "لایسنس", None, 50_000, None, stock_quantity=None)
        digital.kind = "digital"
        digital_id = digital.id
    await _set_config(env.shop_bot_id, REGION_ON)
    await env.cust_cb(f"cart_add:{digital_id}")
    await env.cust_cb("cart_checkout_start")
    await env.cust_say("مریم محمدی")
    await env.cust_say(PHONE)
    assert "توضیح" in env.customer_msgs()[-1], env.customer_msgs()[-1]
    await env.cust_cb("ck_skip")
    assert not any(checkout_ui.ASK_PROVINCE in m or checkout_ui.ASK_CITY in m for m in env.customer_msgs())
    assert "آدرسِ تحویل" not in env.customer_msgs()[-1], "گامِ آدرس برایِ کالایِ دیجیتال نیست"
    await env.cust_cb("cart_checkout_confirm")
    orders = await env.rows()
    assert len(orders) == 1 and not orders[0].customer_address
    print("✅ test_digital_cart_never_asks_region_even_when_on PASSED")


async def test_saved_book_address_keeps_its_region_with_steps_off(shop_dp, main_dp, bot_manager, main_bot) -> None:
    env = await _env(shop_dp, main_dp, bot_manager, main_bot)
    await env.cust_cb(f"cart_add:{env.p1}")  # مشتری ساخته می‌شود تا دفترچه‌آدرس داشته باشد
    async with session_scope() as session:
        customer_id = (
            await session.execute(select(Customer.id).where(Customer.shop_bot_id == env.shop_bot_id))
        ).scalars().first()
        await address_book_service.add_address(
            session, customer_id, province="گیلان", city="رشت", address="خیابانِ کوچه‌یِ سیزدهم، پلاکِ ۷", postal_code=None
        )
    await _up_to_address(env)
    assert env.customer_msgs()[-1] == checkout_ui.ASK_ADDRESS_PICK, "دفترچه پر است ⇒ فهرستِ آدرس‌ها"
    selector = next(c for c in _callbacks(env) if c.startswith("ck_addr_sel:"))
    await env.cust_cb(selector)
    assert not any(checkout_ui.ASK_PROVINCE in m for m in env.customer_msgs())
    await _finish_checkout(env)
    assert "گیلان، رشت، خیابانِ کوچه‌یِ سیزدهم، پلاکِ ۷" in env.customer_msgs()[-1]
    orders = await env.rows()
    assert orders[0].customer_address.startswith("گیلان، رشت"), orders[0].customer_address
    print("✅ test_saved_book_address_keeps_its_region_with_steps_off PASSED")


def _callbacks(env: _Env) -> list[str]:
    markup = env.shop_bot.session.sent_messages[-1]["reply_markup"]
    return [b.callback_data for row in (markup.inline_keyboard if markup else []) for b in row]


async def main() -> None:
    main_dp, shop_dp, bot_manager, main_bot = build_test_dispatchers()
    test_region_steps_default_to_off()
    test_address_chain_follows_the_toggles()
    test_region_hint_names_only_what_is_not_asked()
    await test_owner_panel_shows_the_two_substeps(main_dp)
    await test_default_checkout_does_not_ask_region(shop_dp, main_dp, bot_manager, main_bot)
    await test_region_on_restores_the_full_chain(shop_dp, main_dp, bot_manager, main_bot)
    await test_province_only_reminds_about_the_city(shop_dp, main_dp, bot_manager, main_bot)
    await test_digital_cart_never_asks_region_even_when_on(shop_dp, main_dp, bot_manager, main_bot)
    await test_saved_book_address_keeps_its_region_with_steps_off(shop_dp, main_dp, bot_manager, main_bot)


if __name__ == "__main__":
    asyncio.run(main())
