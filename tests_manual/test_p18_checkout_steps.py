"""
تست: P18 · B9 — گام‌هایِ پیش‌فرضِ چک‌اوت قابلِ مدیریت توسطِ فروشگاه‌دار.

پوشش:
۱. خالص: parse/dump، JSONِ خراب ⇒ پیش‌فرض، متنِ بلند ⇒ بریده، «خالی» ⇒ بازگشت به پیش‌فرض،
   و قاعده‌یِ «آدرس و موبایل هم‌زمان خاموش نمی‌شوند».
۲. خالص: ترتیبِ گام‌ها با گام‌هایِ خاموش (`checkout_flow.step_order/next_position/first_position`)
   و حذفِ جفت‌هایِ «پرسش ← پاسخ»ِ گامِ خاموش.
۳. پنلِ «🛒 سوال‌هایِ چک‌اوتِ سبد › 🧾 گام‌هایِ پیش‌فرضِ چک‌اوت»: toggle، متنِ پرسش، ورودیِ نامعتبر،
   کلیدهایِ دستکاری‌شده، دابل‌تپ و بازگشت.
۴. end-to-end: چک‌اوتِ مشتری واقعاً گام‌هایِ خاموش را رد می‌کند، متنِ پرسشِ فروشگاه‌دار را می‌بیند و
   جفت‌هایِ سفارش/اعلانِ فروشگاه‌دار بدونِ آن گام‌ها ساخته می‌شوند؛ با پیکربندیِ خالی رفتارِ today حفظ است.
۵. ایزولاسیونِ فروشگاه‌ها.

اجرا: python3 tests_manual/test_p18_checkout_steps.py
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
from test_orders_w2 import CUSTOMER, _Env, _seed  # noqa: E402

from app.bots.main_bot import texts as main_texts  # noqa: E402
from app.bots.shop_bot import checkout_ui  # noqa: E402
from app.database.models import OrderConsultation, ShopBot  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import checkout_config_service as cfg, checkout_flow, product_service  # noqa: E402

OWNER_TG_ID = 999_871
SHOP_BOT_TG_ID = 999_872
OTHER_OWNER_TG_ID = 999_881
OTHER_SHOP_BOT_TG_ID = 999_882
CUSTOM_PHONE = "09121112233"


def _datas(markup) -> list[str]:
    return [b.callback_data for row in markup.inline_keyboard for b in row if b.callback_data] if markup else []


def _defaults() -> dict:
    return cfg.parse(None)


async def _set_config(shop_bot_id: int, raw: str | None) -> None:
    async with session_scope() as session:
        row = (await session.execute(select(ShopBot).where(ShopBot.id == shop_bot_id))).scalar_one()
        row.checkout_config = raw


async def _config_of(shop_bot_id: int) -> str | None:
    async with session_scope() as session:
        return (await session.execute(select(ShopBot.checkout_config).where(ShopBot.id == shop_bot_id))).scalar_one()


# ============================================================================= ۱ — خالصِ پیکربندی
def test_config_parsing_dumping_and_guards() -> None:
    steps = _defaults()
    assert [steps[k].enabled for k in cfg.STEP_KEYS] == [True] * 5
    assert steps["phone"].question == checkout_ui.ASK_PHONE
    assert cfg.dump(steps) is None, "همه‌چیز پیش‌فرض ⇒ ستونِ خالی ⇒ رفتارِ امروز"
    assert cfg.disabled_positions(steps) == frozenset()

    steps = cfg.set_enabled(steps, "note", False)
    stored = cfg.dump(steps)
    assert stored and '"note":{"on":false' in stored.replace(" ", "")
    reloaded = cfg.parse(stored)
    assert reloaded["note"].enabled is False and reloaded["name"].enabled is True
    assert cfg.dump(reloaded) == stored, "round-trip پایدار"

    # JSONِ خراب/ناقص ⇒ پیش‌فرض، بدونِ استثناء
    for bad in ("", "   ", "{not json", "[]", "null", "5", '{"note": 3}', '{"note": {"on": "x"}}'):
        parsed = cfg.parse(bad)
        assert parsed["name"].enabled is True, bad
        assert parsed["phone"].question == checkout_ui.ASK_PHONE, bad
    assert cfg.parse('{"note": {"on": false}}')["note"].enabled is False, "کلیدِ ناقص بقیه را پیش‌فرض می‌گذارد"
    assert cfg.parse('{"bogus": {"on": false}}') == _defaults(), "کلیدِ ناشناخته نادیده گرفته می‌شود"

    # قاعده‌یِ ایمنی: آدرس و موبایل هم‌زمان خاموش نمی‌شوند
    both = cfg.set_enabled(_defaults(), "address", False)
    assert both is not None and cfg.set_enabled(both, "phone", False) is None
    assert cfg.set_enabled(_defaults(), "phone", False) is not None
    assert cfg.set_enabled(_defaults(), "address", False) is not None
    assert cfg.set_enabled(_defaults(), "bogus", False) is None

    # متنِ پرسش: حدِ طول، «خالی» ⇒ پیش‌فرض
    steps = cfg.set_question(_defaults(), "phone", "شماره‌ت رو بفرست تا هماهنگ کنیم")
    assert steps["phone"].question == "شماره‌ت رو بفرست تا هماهنگ کنیم"
    assert cfg.set_question(_defaults(), "phone", "ی" * (cfg.MAX_QUESTION_LENGTH + 1)) is None
    assert cfg.set_question(steps, "phone", "خالی")["phone"].question == checkout_ui.ASK_PHONE
    assert cfg.set_question(_defaults(), "bogus", "هرچی") is None
    assert cfg.questions(_defaults())["note"] == checkout_ui.ASK_NOTE

    decoded = json.loads(cfg.dump(cfg.set_question(_defaults(), "note", "یادآوری")))
    assert decoded["note"] == {"on": True, "q": "یادآوری"}, decoded
    print("✅ test_config_parsing_dumping_and_guards PASSED")


# ============================================================================= ۲ — ترتیبِ گام‌ها
def test_flow_order_and_qa_pairs_skip_disabled() -> None:
    none = frozenset()
    assert checkout_flow.first_position(physical=True, ship_choice=True, has_questions=True, disabled=none) == "name"
    assert checkout_flow.step_order(physical=True, ship_choice=True, has_questions=True, disabled=none) == [
        "name", "phone", "addr", "ship", "qa", "note"
    ]
    # بدونِ نام
    assert checkout_flow.first_position(physical=True, disabled=frozenset({"name"})) == "phone"
    assert checkout_flow.step_order(physical=False, disabled=frozenset({"name", "note"})) == ["phone"]
    # گامِ آخرِ خاموش ⇒ رفتن به پیش‌نمایش
    assert checkout_flow.next_position("note", physical=False, ship_choice=False, has_questions=False, disabled=frozenset({"note"})) == "preview"
    assert checkout_flow.next_position("phone", physical=False, ship_choice=False, has_questions=False, disabled=frozenset({"note"})) == "preview"
    # آدرس خاموش ⇒ بعد از موبایل مستقیم ship/qa/note
    assert checkout_flow.next_position("phone", physical=True, ship_choice=True, has_questions=False, disabled=frozenset({"addr"})) == "ship"
    # همه خاموش ⇒ first_position = preview
    assert checkout_flow.first_position(disabled=frozenset({"name", "phone", "addr", "ship", "note"})) == "preview"

    pairs = checkout_flow.build_qa_pairs(
        name="علی", phone_display="+989121112233", address_text=None, ship_label=None,
        questions=["سوال"], answers=["جواب"], note="توضیح", disabled=frozenset({"name", "note"}),
    )
    assert [label for label, _ in pairs] == ["شماره‌یِ تماس", "سوال"], pairs
    full = checkout_flow.build_qa_pairs(
        name="علی", phone_display="+989121112233", address_text=None, ship_label=None,
        questions=[], answers=[], note="توضیح",
    )
    assert [label for label, _ in full] == ["نامِ تحویل‌گیرنده", "شماره‌یِ تماس", "توضیحِ سفارش"], "بدونِ disabled مثلِ قبل"
    print("✅ test_flow_order_and_qa_pairs_skip_disabled PASSED")


# ============================================================================= ۳ — پنلِ فروشگاه‌دار
async def test_owner_checkout_steps_panel(main_dp) -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    owner = Chat(main_dp, OWNER_TG_ID)

    await owner.say("📝 سوال‌هایِ چک‌اوتِ سبد")
    assert _datas(owner.last_markup) == ["cs_open"], _datas(owner.last_markup)

    await owner.tap("cs_open")
    assert "گام‌هایِ پیش‌فرضِ چک‌اوت" in owner.last_edit_text
    assert "• 📝 توضیحِ سفارش: روشن" in owner.last_edit_text, owner.last_edit_text
    data = _datas(owner.last_edit_markup)
    assert "cs_toggle:note" in data and "cs_ask:phone" in data and data[-1] == "cs_back", data

    await owner.tap("cs_toggle:note")
    stored = await _config_of(shop_bot_id)
    assert stored and json.loads(stored)["note"]["on"] is False, stored
    assert "• 📝 توضیحِ سفارش: خاموش" in owner.last_edit_text

    # دابل‌تپ ⇒ همان وضعیت (روشن)
    await owner.tap("cs_toggle:note")
    await owner.tap("cs_toggle:note")
    assert json.loads(await _config_of(shop_bot_id))["note"]["on"] is False

    # قاعده‌یِ آدرس+موبایل
    await owner.tap("cs_toggle:address")
    await owner.tap("cs_toggle:phone")
    assert owner.last_toast["text"] == main_texts.CHECKOUT_STEPS_GUARD
    assert json.loads(await _config_of(shop_bot_id))["phone"]["on"] is True, "خاموش‌شدنی که قاعده را می‌شکند ذخیره نمی‌شود"

    # متنِ پرسش: بلندتر از سقف ⇒ رد می‌شود و state می‌ماند
    await owner.tap("cs_ask:phone")
    assert owner.sent[-1]["text"] == main_texts.CHECKOUT_STEP_QUESTION_ASK
    await owner.say("ی" * 151)
    assert owner.last_text == main_texts.CHECKOUT_STEP_QUESTION_TOO_LONG
    await owner.say("شماره‌ای بفرست که جوابگو باشی")
    assert json.loads(await _config_of(shop_bot_id))["phone"]["q"] == "شماره‌ای بفرست که جوابگو باشی"

    # «خالی» ⇒ بازگشت به متنِ پیش‌فرض
    await owner.tap("cs_ask:phone")
    await owner.say("خالی")
    stored = json.loads(await _config_of(shop_bot_id))
    assert stored["phone"]["q"] == checkout_ui.ASK_PHONE, stored

    # کلیدهایِ دستکاری‌شده
    for bad in ("cs_toggle:bogus", "cs_ask:bogus"):
        await owner.tap(bad)
        assert owner.last_toast["text"] == main_texts.CHECKOUT_STEPS_STALE, bad

    await owner.tap("cs_back")
    assert "سوال" in owner.last_edit_text and _datas(owner.last_edit_markup) == ["cs_open"]
    print("✅ test_owner_checkout_steps_panel PASSED")


# ============================================================================= ۴ — چک‌اوتِ واقعیِ مشتری
async def test_customer_flow_uses_the_shops_config(shop_dp, main_dp, bot_manager, main_bot) -> None:
    shop_bot_id, p1, _p2 = await _seed()
    async with session_scope() as session:
        digital = await product_service.create_product(session, shop_bot_id, "لایسنس", None, 50_000, None, stock_quantity=None)
        digital.kind = "digital"
        digital_id = digital.id

    # ۴-الف) سبدِ فیزیکی با نام و توضیح خاموش و متنِ پرسشِ سفارشیِ موبایل
    await _set_config(
        shop_bot_id,
        json.dumps(
            {
                "name": {"on": False, "q": checkout_ui.ASK_NAME_PLAIN},
                "phone": {"on": True, "q": "شماره‌ای بفرست که جوابگو باشی"},
                "address": {"on": True, "q": checkout_ui.ASK_ADDRESS_TEXT},
                "shipping": {"on": True, "q": checkout_ui.ASK_SHIPPING},
                "note": {"on": False, "q": checkout_ui.ASK_NOTE},
            },
            ensure_ascii=False,
        ),
    )
    env = _Env(shop_dp, main_dp, bot_manager, main_bot, shop_bot_id, p1, digital_id)
    await env.cust_cb(f"cart_add:{p1}")
    await env.cust_cb("cart_checkout_start")
    assert env.customer_msgs()[-1] == "شماره‌ای بفرست که جوابگو باشی", env.customer_msgs()[-1]

    await env.cust_say(CUSTOM_PHONE)
    assert env.customer_msgs()[-1] == checkout_ui.ASK_PROVINCE, "گامِ آدرس روشن است"
    await env.cust_say("تهران")
    await env.cust_say("تهران")
    await env.cust_say("خیابانِ آزادی، کوچه‌یِ دوم، پلاکِ ده")
    await env.cust_cb("ck_skip")  # کدپستی
    # P22 (مشکلِ ۵): فروشگاه روشِ ارسالی ندارد ⇒ گام حذف نمی‌شود؛ «هماهنگیِ ارسال» پرسیده می‌شود
    assert "هماهنگی" in env.customer_msgs()[-1], env.customer_msgs()[-1]
    await env.cust_cb("ck_ship:0")
    assert "💳 مبلغِ قابلِ پرداخت" in env.customer_msgs()[-1], env.customer_msgs()[-1]
    assert "توضیحِ سفارش" not in env.customer_msgs()[-1], "گامِ توضیح خاموش ⇒ در پیش‌نمایش هم نیست"
    await env.cust_cb("cart_checkout_confirm")

    rows = await env.rows()
    assert len(rows) == 1, f"orders={len(rows)} last_msg={env.customer_msgs()[-1]!r}"
    order = rows[0]
    assert order.customer_phone == "+989121112233", order.customer_phone
    answers = order.checkout_answers or ""
    assert "شماره‌یِ تماس" in answers, answers
    for label in ("نامِ تحویل‌گیرنده", "توضیحِ سفارش"):
        assert label not in answers, f"گامِ خاموش نباید در سفارش ثبت شود: {answers}"

    # ۴-ب) پیکربندیِ خالی ⇒ دقیقاً رفتارِ امروز (نام اول، توضیح پرسیده می‌شود)
    await _set_config(shop_bot_id, None)
    await env.cust_cb(f"cart_add:{p1}")
    await env.cust_cb("cart_checkout_start")
    assert "نامِ تحویل‌گیرنده" in env.customer_msgs()[-1], env.customer_msgs()[-1]

    # ۴-پ) موبایل خاموش و آدرس روشن (قاعده اجازه می‌دهد): سفارش بدونِ شماره ثبت می‌شود و نمی‌ترکد
    await _set_config(
        shop_bot_id,
        json.dumps(
            {
                "name": {"on": True, "q": checkout_ui.ASK_NAME_PLAIN},
                "phone": {"on": False, "q": checkout_ui.ASK_PHONE},
                "address": {"on": True, "q": "آدرس و پلاکت رو کامل بنویس"},
                "shipping": {"on": True, "q": checkout_ui.ASK_SHIPPING},
                "note": {"on": True, "q": checkout_ui.ASK_NOTE},
            },
            ensure_ascii=False,
        ),
    )
    before = len(await env.rows())
    await env.cust_cb("cart_checkout_start")
    assert "نامِ تحویل‌گیرنده" in env.customer_msgs()[-1], env.customer_msgs()[-1]
    await env.cust_say("مریم محمدی")
    # چک‌اوت‌هایِ قبلی آدرس ذخیره کرده‌اند ⇒ گامِ آدرس با فهرستِ آدرس‌ها شروع می‌شود، نه با استان
    assert env.customer_msgs()[-1] == checkout_ui.ASK_ADDRESS_PICK, "موبایل خاموش ⇒ مستقیم آدرس"
    await env.cust_cb("ck_addr_new")
    assert env.customer_msgs()[-1] == checkout_ui.ASK_PROVINCE, env.customer_msgs()[-1]
    await env.cust_say("تهران")
    await env.cust_say("کرج")
    assert env.customer_msgs()[-1] == "آدرس و پلاکت رو کامل بنویس", env.customer_msgs()[-1]
    await env.cust_say("میدانِ آزادی، پلاکِ ۱۲")
    await env.cust_cb("ck_skip")  # کدپستی
    assert "هماهنگی" in env.customer_msgs()[-1], env.customer_msgs()[-1]  # P22: گامِ ارسال همیشه هست
    await env.cust_cb("ck_ship:0")
    assert env.customer_msgs()[-1] == checkout_ui.ASK_NOTE, "گامِ توضیح دوباره روشن است"
    await env.cust_say("لطفاً زنگ بزنید")
    assert "💳 مبلغِ قابلِ پرداخت" in env.customer_msgs()[-1], env.customer_msgs()[-1]
    await env.cust_cb("cart_checkout_confirm")

    rows = await env.rows()
    assert len(rows) == before + 1, f"orders={len(rows)} expected={before + 1}"
    newest = rows[-1]
    assert newest.customer_phone is None, newest.customer_phone
    answers = newest.checkout_answers or ""
    assert "نامِ تحویل‌گیرنده" in answers and "توضیحِ سفارش" in answers, answers
    assert "شماره‌یِ تماس" not in answers, answers
    print("✅ test_customer_flow_uses_the_shops_config PASSED")


# ============================================================================= ۵ — ایزولاسیون
async def test_config_is_per_shop(main_dp) -> None:
    await reset_database()
    mine = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    theirs = await seed_usable_shop(OTHER_OWNER_TG_ID, OTHER_SHOP_BOT_TG_ID)
    mine_before = json.dumps({"note": {"on": True, "q": "پیش‌فرض"}, "name": {"on": False, "q": "پیش‌فرض"}})
    await _set_config(mine, mine_before)

    owner = Chat(main_dp, OTHER_OWNER_TG_ID)
    await owner.say("📝 سوال‌هایِ چک‌اوتِ سبد")
    await owner.tap("cs_open")
    assert "• 📝 توضیحِ سفارش: روشن" in owner.last_edit_text, owner.last_edit_text
    await owner.tap("cs_toggle:note")

    assert json.loads(await _config_of(theirs))["note"]["on"] is False, "فروشگاهِ خودش عوض شد"
    assert await _config_of(mine) == mine_before, "پیکربندیِ من دست‌نخورده ماند"
    assert (await _config_of(theirs)) != (await _config_of(mine))
    print("✅ test_config_is_per_shop PASSED")


async def main() -> None:
    main_dp, shop_dp, bot_manager, main_bot = build_test_dispatchers()
    test_config_parsing_dumping_and_guards()
    test_flow_order_and_qa_pairs_skip_disabled()
    await test_owner_checkout_steps_panel(main_dp)
    await test_customer_flow_uses_the_shops_config(shop_dp, main_dp, bot_manager, main_bot)
    await test_config_is_per_shop(main_dp)


if __name__ == "__main__":
    asyncio.run(main())
