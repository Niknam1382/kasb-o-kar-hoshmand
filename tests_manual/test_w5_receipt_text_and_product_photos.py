"""
تست: دو باگِ گزارش‌شده‌یِ W5 —
  ۱) رسیدِ *متنی* (متنِ کپی‌شده از اپ بانک/پیامک) برایِ کارت‌به‌کارت پذیرفته می‌شه (قبلاً فقط عکس/فایل/«فقط شماره‌پیگیری»).
  ۲) عکسِ محصول (آپلودِ فروشگاه‌دار در رباتِ اصلی) برایِ مشتری در رباتِ فروشگاه قابلِ دیدن/درخواست است:
     دکمه‌یِ «🖼» در مرورِ محصولات، درخواستِ متنیِ «عکسِ X»، کشِ file_id و ابطالِ خودکار با تغییرِ عکس، ایزولاسیونِ فروشگاه‌ها.

اجرا: python3 tests_manual/test_w5_receipt_text_and_product_photos.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from sqlalchemy import select  # noqa: E402

from harness import build_test_dispatchers, make_callback_update  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402
from test_orders_w2 import CUSTOMER, OTHER_OWNER, OTHER_SHOP_TG, _Env, _seed  # noqa: E402
from test_payments_w3w4 import _configure, _datas, _payments  # noqa: E402

from app.bots.shop_bot import texts as shop_texts  # noqa: E402
from app.bots.shop_bot.handlers import product_photos  # noqa: E402
from app.database.models import Product  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import order_payment_service, product_photo_service, product_service  # noqa: E402

RECEIPT = "کارت به کارت انجام شد مبلغ 200,000 تومان ساعت 14:32 شماره پیگیری 123456789"


async def test_parse_receipt_text_pure() -> None:
    parse = order_payment_service.parse_receipt_text
    text, tracking = parse(RECEIPT)
    assert text == RECEIPT and tracking == "123456789"
    text, tracking = parse("مبلغ ۱٬۲۰۰٬۰۰۰ تومان به کارت 6037991234567890 واریز شد")
    assert tracking is None, "مبلغ و شماره‌کارت هرگز پیگیری حساب نمی‌شن"
    assert parse("رهگیری: ۹۸۷۶۵۴۳۲۱ پرداخت شد 25000")[1] == "987654321"
    for bad in (None, "", "سلام این رسیده", "abc 12", "پرداخت کردم", "x" * 1001 + "1234"):
        assert parse(bad) is None, bad
    assert order_payment_service.extract_tracking_ref("123456") == "123456", "فقط شماره‌پیگیری مثلِ قبل"
    print("✅ test_parse_receipt_text_pure PASSED")


async def test_text_receipt_flow(shop_dp, main_dp, bot_manager, main_bot) -> None:
    shop_bot_id, p1, p2 = await _seed()
    await _configure(shop_bot_id, card=True, max_attempts=9)
    async with session_scope() as session:
        (await session.get(Product, p1)).stock_quantity = 50
    env = _Env(shop_dp, main_dp, bot_manager, main_bot, shop_bot_id, p1, p2)

    async def start(product_ids: list[int]) -> str:
        g = await env.checkout(product_ids)
        await env.cust_cb(f"pm_card:{g}")
        await env.cust_cb(f"pay_receipt:{g}")
        return g

    # الف) متنِ رسید پذیرفته می‌شه؛ برایِ فروشگاه‌دار متن و پیگیریِ برچسب‌دار می‌آید
    g1 = await start([p1])
    await env.cust_say(RECEIPT)
    assert await env.statuses() == {"receipt_submitted"}
    assert env.customer_msgs()[-1] == shop_texts.PAY_RECEIPT_RECEIVED
    pay1 = (await _payments())[0]
    assert pay1.receipt_text == RECEIPT and pay1.tracking_ref == "123456789" and pay1.receipt_sha256
    owner_text = main_bot.session.sent_messages[-1]["text"]
    assert "📝 متنِ رسید" in owner_text and RECEIPT in owner_text and "شماره‌پیگیری: 123456789" in owner_text
    assert any(d.startswith("rcpt_ok:") for d in _datas(main_bot.session.sent_messages[-1]["reply_markup"]))

    # ب) متنِ بی‌ربط/کوتاه/بدونِ رقم ⇒ همان پیامِ راهنما و بدونِ ثبت
    g2 = await start([p1])
    for junk in ("سلام این رسیده", "12 ab", "تمام شد"):
        await env.cust_say(junk)
        assert env.customer_msgs()[-1] == shop_texts.PAY_RECEIPT_INVALID, junk
    assert len(await _payments()) == 2 and (await _payments())[1].receipt_text is None

    # ج) همان متنِ تکراری برایِ سفارشِ دیگر ⇒ پرچم (نه ردِ خودکار)
    await env.cust_say(RECEIPT)
    notice = main_bot.session.sent_messages[-1]["text"]
    assert "فایل/متنِ رسید قبلاً هم ارسال شده" in notice and "شماره‌پیگیری قبلاً هم ثبت شده" in notice

    # د) مبلغ/شماره‌کارت در متن ⇒ پیگیری استخراج نمی‌شه
    g3 = await start([p1])
    await env.cust_say("مبلغ 1,200,000 تومان به کارت 6037991234567890 واریز شد")
    pay3 = (await _payments())[2]
    assert pay3.tracking_ref is None and pay3.receipt_text and "6037991234567890" in pay3.receipt_text

    # ه) تاییدِ فروشگاه‌دار برایِ رسیدِ متنی مثلِ قبل کار می‌کند
    await env.owner_cb(f"rcpt_ok:{pay1.id}")
    async with session_scope() as session:
        from app.database.models import OrderConsultation

        rows = (await session.execute(select(OrderConsultation).where(OrderConsultation.cart_checkout_group_id == g1))).scalars().all()
        assert {r.status.value if hasattr(r.status, "value") else r.status for r in rows} == {"paid"}
    assert g2 != g3
    print("✅ test_text_receipt_flow PASSED")


async def test_photo_pure_helpers() -> None:
    from types import SimpleNamespace as NS

    make = lambda i, name, photo="f": NS(id=i, name=name, photo_file_id=photo, is_active=True, photo_shop_file_id=None)  # noqa: E731
    products = [make(1, "برنج طارم"), make(2, "چای"), make(3, "روغن", None), make(4, "برنج ياسمين")]
    assert product_photo_service.looks_like_photo_request("عکس برنج رو بفرست") and product_photo_service.looks_like_photo_request("تصویر دارید؟")
    assert not product_photo_service.looks_like_photo_request("قیمت برنج چنده") and not product_photo_service.looks_like_photo_request(None)
    assert not product_photo_service.looks_like_photo_request("عکس " + "x" * 200)
    match = product_photo_service.match_products
    assert [p.id for p in match("عکسِ برنج طارم رو بفرست", products)] == [1] and [p.id for p in match("عکس چای", products)] == [2]
    assert match("عکس روغن", products) == [] and match("عکس ماشین", products) == [], "بدونِ عکس/ناشناخته ⇒ تطبیق نداره"
    assert [p.id for p in match("عکس برنج یاسمین", products)] == [4], "ي/ی یکی حساب می‌شه"
    p = make(5, "x", "main1")
    assert product_photo_service.cached_shop_file_id(p) is None
    p.photo_shop_file_id = product_photo_service.source_tag("main1") + "|shopid"
    assert product_photo_service.cached_shop_file_id(p) == "shopid"
    p.photo_file_id = "main2"
    assert product_photo_service.cached_shop_file_id(p) is None, "عوضِ عکس کش رو باطل می‌کنه"
    print("✅ test_photo_pure_helpers PASSED")


async def test_product_photo_flow(shop_dp, main_dp, bot_manager, main_bot) -> None:
    shop_bot_id, p1, p2 = await _seed()
    env = _Env(shop_dp, main_dp, bot_manager, main_bot, shop_bot_id, p1, p2)
    main_bot.session.set_downloaded_file("main_photo_1", b"jpg-bytes-1")
    main_bot.session.set_downloaded_file("main_photo_2", b"jpg-bytes-2")
    async with session_scope() as session:
        (await session.get(Product, p1)).photo_file_id = "main_photo_1"
    other_shop = await seed_usable_shop(OTHER_OWNER, OTHER_SHOP_TG)  # محصولِ فروشگاهِ دیگه (با عکس) — نباید از این ربات قابلِ درخواست باشه
    async with session_scope() as session:
        foreign = await product_service.create_product(session, other_shop, "کالایِ بیگانه", None, 1_000, "main_photo_1", stock_quantity=5)
        foreign_id = foreign.id
    photos = env.shop_bot.session.sent_photos

    # الف) مرورِ محصولات: «🖼» فقط برایِ محصولِ عکس‌دار
    await env.cust_say(shop_texts.BTN_PRODUCTS)
    browse = _datas(env.shop_bot.session.sent_messages[-1]["reply_markup"])
    assert f"cart_photo:{p1}" in browse and f"cart_photo:{p2}" not in browse and f"cart_add:{p2}" in browse

    # ب) درخواستِ متنی ⇒ کارتِ عکس‌دار (بدونِ AI)، آپلودِ دوباره از رباتِ اصلی
    await env.cust_say("عکسِ برنج رو بفرست لطفاً")
    assert len(photos) == 1 and "برنج" in photos[0]["caption"] and "200,000" in photos[0]["caption"]
    assert photos[0]["photo"] != "fake_photo_id", "بار اول بافرِ آپلود است"
    async with session_scope() as session:
        product = await session.get(Product, p1)
        cached = product_photo_service.cached_shop_file_id(product)
        assert cached == "fake_photo_id", "file_idِ رباتِ فروشگاه کش شد"
        assert product.photo_file_id == "main_photo_1"

    # ج) بار دوم با file_idِ کش‌شده (بدونِ آپلودِ دوباره)؛ دکمه هم همین را می‌دهد
    await env.cust_say("تصویر برنج")
    assert len(photos) == 2 and photos[1]["photo"] == "fake_photo_id"
    await env.cust_cb(f"cart_photo:{p1}")
    assert len(photos) == 3 and photos[2]["photo"] == "fake_photo_id"

    # د) تغییرِ عکس توسطِ فروشگاه‌دار ⇒ کش باطل و آپلودِ تازه
    async with session_scope() as session:
        (await session.get(Product, p1)).photo_file_id = "main_photo_2"
    await env.cust_say("عکس برنج")
    assert len(photos) == 4 and photos[3]["photo"] != "fake_photo_id"

    # ه) «عکس» بدونِ نامِ محصول / نامِ ناشناخته ⇒ می‌پرسه کدوم محصول (فقط عکس‌دارها)
    before = len(photos)
    await env.cust_say("عکس دارید؟")
    ask = env.shop_bot.session.sent_messages[-1]
    assert ask["text"] == product_photos.ASK_WHICH and _datas(ask["reply_markup"]) == [f"cart_photo:{p1}"]
    await env.cust_say("عکس ماشین")
    assert env.shop_bot.session.sent_messages[-1]["text"] == product_photos.ASK_WHICH and len(photos) == before

    # و) دکمه‌یِ بدونِ عکس / ناموجود / جعلی / محصولِ فروشگاهِ دیگه ⇒ هشدار، بدونِ عکس
    for data in (f"cart_photo:{p2}", "cart_photo:999999", "cart_photo:abc", f"cart_photo:{foreign_id}", "cart_photo:"):
        await env.cust_cb(data)
        assert env.cust_alerts()[-1].get("show_alert") is True, data
        assert len(photos) == before, data
    print("✅ test_product_photo_flow PASSED")


async def test_cart_button_on_photo_card_works(shop_dp, main_dp, bot_manager, main_bot) -> None:
    """B2: «🛒 دیدنِ سبدِ خرید» رویِ *کارتِ عکسِ* محصول قبلاً بی‌اثر بود — پیامِ عکسی با `edit_text`
    ویرایش نمی‌شود و استثنا بی‌صدا می‌مرد. حالا هندلر پیامِ تازه می‌فرستد و سبد واقعاً نشان داده می‌شود."""
    shop_bot_id, p1, p2 = await _seed()
    env = _Env(shop_dp, main_dp, bot_manager, main_bot, shop_bot_id, p1, p2)
    await env.cust_cb(f"cart_add:{p1}")

    sent_before = len(env.shop_bot.session.sent_messages)
    edits_before = len(env.shop_bot.session.edited_texts)
    await shop_dp.feed_update(
        env.shop_bot,
        make_callback_update(
            env._next(), data="cart_view", user_id=CUSTOMER, message_text=None, message_caption="برنج — ۲۰۰٬۰۰۰ تومان"
        ),
    )
    sent = env.shop_bot.session.sent_messages
    assert len(sent) == sent_before + 1, "دکمه رویِ پیامِ عکسی باید پیامِ تازه بفرستد، نه اینکه بی‌اثر بماند"
    assert len(env.shop_bot.session.edited_texts) == edits_before, "پیامِ عکسی نباید ویرایش شود"
    assert "برنج" in sent[-1]["text"], sent[-1]["text"]
    assert _datas(sent[-1]["reply_markup"]), "سبد باید دکمه‌هایِ خودش را داشته باشد"

    # رویِ پیامِ متنی همچنان ویرایش می‌شود (بدونِ پیامِ اضافه)
    edits_before_text = len(env.shop_bot.session.edited_texts)
    await env.cust_cb("cart_view")
    assert len(env.shop_bot.session.edited_texts) == edits_before_text + 1, "رویِ پیامِ متنی باید ویرایش شود"
    assert len(env.shop_bot.session.sent_messages) == sent_before + 1, "رویِ پیامِ متنی پیامِ اضافه نمی‌رود"
    print("✅ test_cart_button_on_photo_card_works PASSED")


async def main() -> None:
    main_dp, shop_dp, bot_manager, main_bot = build_test_dispatchers()
    await test_parse_receipt_text_pure()
    await test_text_receipt_flow(shop_dp, main_dp, bot_manager, main_bot)
    await test_photo_pure_helpers()
    await test_product_photo_flow(shop_dp, main_dp, bot_manager, main_bot)
    await test_cart_button_on_photo_card_works(shop_dp, main_dp, bot_manager, main_bot)


if __name__ == "__main__":
    asyncio.run(main())
