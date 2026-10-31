"""
تست: P1-S3 / B2 — کاتالوگِ فیزیکی/دیجیتال: افزودنِ محصولِ دیجیتال (فایل/لینک/متن/کدِ یکتا)، استخرِ کد،
تحویلِ ایدمپوتنت و رقابتی، «📥 دریافتِ دوباره»، گاردِ مود/نوع، روش‌هایِ ارسال، پرامپتِ AI، اکسلِ قدیمی/تازه،
سوال‌هایِ چک‌اوتِ سبدِ فقط‌دیجیتال.

اجرا: python3 tests_manual/test_catalog_digital_physical.py
"""
from __future__ import annotations

import asyncio
import io
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402
from openpyxl import Workbook  # noqa: E402
from sqlalchemy import func, select  # noqa: E402

from harness import FakeSession, build_test_dispatchers, make_callback_update, register_fake_shop_bot, reset_database  # noqa: E402
from phase4_helpers import Chat, callbacks  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot import keyboards, texts  # noqa: E402
from app.bots.shop_bot import texts as shop_texts  # noqa: E402
from app.bots.shop_bot.handlers import customer as customer_handlers  # noqa: E402
from app.database.models import Customer, DigitalCode, OrderConsultation, OrderStatus, OrderType, Product, ShippingMethod, ShopBot, TenantMode  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import ai_context, digital_service, excel_import_service, order_service, product_service, shipping_service  # noqa: E402
from app.utils.encryption import decrypt_token  # noqa: E402
from app.utils.validators import parse_nonneg_int  # noqa: E402

OWNER_TG_ID = 7_100_000_001
SHOP_BOT_TG_ID = 7_100_000_002
CUSTOMER_TG_ID = 7_100_000_003
OTHER_CUSTOMER_TG_ID = 7_100_000_004

_ctx: dict = {}


async def _setup() -> tuple[int, Chat, Bot]:
    """دیتابیسِ تمیز + فروشگاه + چتِ مالک + رباتِ فروشگاهیِ جعلی (ثبت‌شده در bot_manager)."""
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    owner = Chat(_ctx["main_dp"], OWNER_TG_ID)
    shop_bot = Bot(token=f"{SHOP_BOT_TG_ID}:SHOP_FAKE_TOKEN", session=FakeSession())
    register_fake_shop_bot(_ctx["bot_manager"], shop_bot_id, shop_bot)
    return shop_bot_id, owner, shop_bot


async def _seed_customer(shop_bot_id: int, telegram_id: int) -> int:
    async with session_scope() as session:
        customer = Customer(shop_bot_id=shop_bot_id, telegram_id=telegram_id, first_name="مشتری")
        session.add(customer)
        await session.flush()
        return customer.id


async def _seed_digital(shop_bot_id: int, delivery: str, **kwargs) -> int:
    async with session_scope() as session:
        product = await product_service.create_digital_product(session, shop_bot_id, "دوره‌یِ آموزشی", None, 50_000, None, delivery, **kwargs)
        return product.id


async def _add_codes(product_id: int, codes: list[str]) -> None:
    async with session_scope() as session:
        product = await session.get(Product, product_id)
        await digital_service.add_codes(session, product, codes)
        await digital_service.sync_pool_stock(session, product)


async def _order(shop_bot_id: int, customer_id: int, product_id: int, qty: int = 1) -> int:
    async with session_scope() as session:
        order = await order_service.create_order(
            session, shop_bot_id, customer_id, OrderType.ORDER, "سفارش", 50_000 * qty, product_id=product_id, quantity=qty
        )
        return order.id


def _customer_texts(shop_bot: Bot) -> list[str]:
    return [m["text"] for m in shop_bot.session.sent_messages if m["chat_id"] == CUSTOMER_TG_ID]


async def _run_add_flow(owner: Chat, steps: list) -> None:
    for kind, value in steps:
        if kind == "tap":
            await owner.tap(value)
        else:
            await owner.say(value)


# =============================================================================
# منطقِ خالص
# =============================================================================
async def test_pure_helpers() -> None:
    codes, ignored = digital_service.parse_codes("A1\r\n  A2 \n\nA1\n" + "x" * 300 + "\n\u200cB3\u200c")
    assert codes == ["A1", "A2", "B3"], codes
    assert ignored == 2, "تکراری + بلندتر از ۲۵۵"
    assert digital_service.parse_codes(None) == ([], 0) and digital_service.parse_codes("") == ([], 0)
    big, ign = digital_service.parse_codes("\n".join(f"c{i}" for i in range(digital_service.MAX_CODES_PER_BATCH + 7)))
    assert len(big) == digital_service.MAX_CODES_PER_BATCH and ign == 7

    assert digital_service.validate_link("https://example.com/x") == "https://example.com/x"
    for bad in (None, "", "example.com", "ftp://x.com/a", "https://a b.com", "https://", "javascript:alert(1)", "https://x.com/\nevil"):
        assert digital_service.validate_link(bad) is None, bad

    assert parse_nonneg_int("۱۲۰۰") == 1200 and parse_nonneg_int("1,200") == 1200 and parse_nonneg_int(" ٣ ") == 3
    for bad in ("²", "①", "¹⁰", "-2", "", None, "abc", "1.5", "99999999999999"):
        assert parse_nonneg_int(bad) is None, bad
    assert parse_nonneg_int("0") == 0 and parse_nonneg_int("0", allow_zero=False) is None

    assert digital_service.code_hash(" abc ") == digital_service.code_hash("abc")
    assert digital_service.truncate_for_prompt("a  b\n c", 100) == "a b c"
    assert len(digital_service.truncate_for_prompt("x" * 500, 300)) == 300
    assert digital_service.truncate_for_prompt("   ") is None

    product = Product(kind="digital", digital_delivery="code_pool", name="لایسنس", digital_max_downloads=3, digital_instructions="فعال‌سازی: …")
    assert digital_service.can_download_again(product, 2) and not digital_service.can_download_again(product, 3)
    product.digital_max_downloads = None
    assert digital_service.can_download_again(product, 10_000)
    text = digital_service.build_delivery_text(product, ["K1", "K2"])
    assert "K1" in text and "K2" in text and "فعال‌سازی" in text and "کدهایِ شما" in text
    assert "دریافتِ دوباره" in digital_service.build_delivery_text(product, ["K1"], again=True)
    link = Product(kind="digital", digital_delivery="link", name="ک", digital_link="https://x.test/d")
    assert "https://x.test/d" in digital_service.build_delivery_text(link, [])
    txt = Product(kind="digital", digital_delivery="text", name="ک", digital_instructions="متنِ ثابت")
    assert digital_service.build_delivery_text(txt, []).count("متنِ ثابت") == 1, "متنِ تحویل دوبار تکرار نمی‌شه"

    method = ShippingMethod(name="پست", fee_toman=30_000, free_over_toman=500_000)
    assert shipping_service.fee_for_subtotal(method, 100_000) == 30_000
    assert shipping_service.fee_for_subtotal(method, 500_000) == 0
    method.free_over_toman = None
    assert shipping_service.fee_for_subtotal(method, 10**9) == 30_000

    assert customer_handlers._split_checkout_questions(None) == ["شماره تماس", "آدرس"]
    assert customer_handlers._split_checkout_questions(None, digital_only=True) == ["شماره تماس"]
    assert customer_handlers._split_checkout_questions("  \n ", digital_only=True) == ["شماره تماس"]
    assert customer_handlers._split_checkout_questions("نام\nکدملی", digital_only=True) == ["نام", "کدملی"], "سوال‌هایِ سفارشیِ فروشگاه‌دار دست‌نخورده"

    print("✅ test_pure_helpers PASSED")


async def test_callback_data_within_telegram_limit() -> None:
    kb = keyboards.edit_product_field_keyboard(2_000_000_000, "digital", "code_pool")
    kb2 = keyboards.shipping_list_keyboard([ShippingMethod(id=2_000_000_000, name="ن" * 64, fee_toman=0, is_active=True)])
    kb3 = digital_service.again_keyboard(2_000_000_000)
    for markup in (kb, kb2, kb3, keyboards.digital_mode_keyboard(), keyboards.dg_skip_keyboard("instructions")):
        for data in callbacks(markup):
            assert len(data.encode("utf-8")) <= 64, data
    for row in kb2.inline_keyboard:
        assert len(row[0].text) <= 60
    print("✅ test_callback_data_within_telegram_limit PASSED")


async def test_ai_context_lines_per_kind() -> None:
    shop_bot = ShopBot(tenant_mode=TenantMode.SALES, ai_instructions=None)
    plain = Product(name="کتاب", price_toman=100_000, description="چاپِ دوم", stock_quantity=3, kind="physical")
    assert ai_context._product_line(plain) == "- کتاب (100,000 تومان): چاپِ دوم [موجودی: 3 عدد]", "فیزیکیِ ساده بایت‌به‌بایت مثلِ قبل"

    rich = Product(name="کتاب", price_toman=100_000, kind="physical", weight_grams=400, delivery_note="۲ تا ۳ روز", return_policy="۷ روز", ai_instructions="ضمانت ۱۸ ماهه " + "ی" * 400)
    line = ai_context._product_line(rich)
    assert "نیازمندِ آدرس" in line and "وزن 400 گرم" in line and "۲ تا ۳ روز" in line and "مرجوعی: ۷ روز" in line
    custom = line.split("[دستورِ ویژه‌یِ این محصول: ", 1)[1].rstrip("]")
    assert len(custom) <= ai_context.PRODUCT_AI_INSTRUCTIONS_PROMPT_LEN, "دستورِ اختصاصی به N نویسه کوتاه می‌شه"

    digital = Product(name="دوره", price_toman=10_000, kind="digital", digital_delivery="link", digital_max_downloads=2, digital_instructions="با VPN باز کن")
    line = ai_context._product_line(digital)
    assert "تحویلِ آنی" in line and "بدونِ نیاز به آدرس" in line and "سقفِ دریافت 2" in line and "با VPN باز کن" in line
    text_product = Product(name="متن", price_toman=1, kind="digital", digital_delivery="text", digital_instructions="متنِ مخفی که نباید در پرامپت بیاد")
    assert "متنِ مخفی" not in ai_context._product_line(text_product), "محتوایِ تحویلِ نوعِ «متن» نباید به AI نشت کنه"
    prompt = ai_context.build_system_prompt(shop_bot, [plain, digital])
    assert "تحویلِ آنی" in prompt
    print("✅ test_ai_context_lines_per_kind PASSED")


async def test_excel_kind_column_and_legacy_rows() -> None:
    wb = Workbook()
    ws = wb.active
    ws.append(list(excel_import_service.TEMPLATE_HEADERS))
    ws.append(["قدیمی", "توضیح", 1000, 5])  # ۴ ستونه (فایلِ قدیمی)
    ws.append(["دوره", None, 2000, None, "دیجیتال"])
    ws.append(["کالا", None, 3000, 2, "فیزیکی"])
    ws.append(["بد", None, 4000, None, "نامربوط"])
    buffer = io.BytesIO()
    wb.save(buffer)
    result = excel_import_service.parse_workbook(buffer.getvalue())
    assert result.valid_rows[0] == {"name": "قدیمی", "description": "توضیح", "price_toman": 1000, "stock_quantity": 5}
    assert result.valid_rows[1]["kind"] == "digital"
    assert "kind" not in result.valid_rows[2]
    assert len(result.valid_rows) == 3 and len(result.errors) == 1 and "نوعِ محصول" in result.errors[0]

    shop_bot_id, _owner, _shop = await _setup()
    async with session_scope() as session:
        created = await excel_import_service.bulk_create(session, shop_bot_id, result.valid_rows)
        kinds = {p.name: (p.kind, p.digital_delivery, p.stock_quantity) for p in created}
    assert kinds["قدیمی"] == ("physical", None, 5)
    assert kinds["دوره"] == ("digital", "code_pool", 0), "دیجیتال از اکسل = استخرِ کدِ خالی ⇒ ناموجود تا کد بیاد"
    print("✅ test_excel_kind_column_and_legacy_rows PASSED")


# =============================================================================
# افزودنِ محصولِ دیجیتال (جریانِ کامل از دیسپچر)
# =============================================================================
async def test_add_digital_link_product_flow_and_double_tap() -> None:
    shop_bot_id, owner, _shop = await _setup()
    await _run_add_flow(
        owner,
        [
            ("tap", "product_add_digital"),
            ("say", "دوره‌یِ پایتون"),
            ("tap", "dg_skip:description"),
            ("say", "۱،۵۰۰،۰۰۰"),
            ("tap", "dg_skip:photo"),
            ("tap", "dg_mode:link"),
            ("say", "نه-لینک"),  # نامعتبر ⇒ همون مرحله
        ],
    )
    assert owner.last_text == texts.DG_INVALID_LINK
    await _run_add_flow(owner, [("say", "https://example.com/course"), ("say", "اول وارد شو و فعالش کن"), ("say", "²"), ("say", "۳")])
    assert texts.DG_INVALID_MAX in [m["text"] for m in owner.sent], "«²» سقفِ دریافتِ معتبر نیست"

    async with session_scope() as session:
        rows = list((await session.execute(select(Product).where(Product.shop_bot_id == shop_bot_id))).scalars().all())
    assert len(rows) == 1
    product = rows[0]
    assert product.kind == "digital" and product.digital_delivery == "link" and product.digital_link == "https://example.com/course"
    assert product.price_toman == 1_500_000 and product.digital_max_downloads == 3
    assert product.digital_instructions == "اول وارد شو و فعالش کن" and product.stock_quantity is None
    assert texts.digital_product_added("دوره‌یِ پایتون", "link") in [m["text"] for m in owner.sent]

    # دابل‌تپِ آخرین دکمه/متن بعد از ساخت ⇒ دکمه‌یِ کهنه، نه محصولِ دوم
    await owner.tap("dg_skip:max")
    assert owner.last_toast["text"] == texts.DG_STALE
    async with session_scope() as session:
        assert (await session.execute(select(func.count()).select_from(Product))).scalar_one() == 1
    print("✅ test_add_digital_link_product_flow_and_double_tap PASSED")


async def test_add_digital_code_pool_flow_dedupes_and_syncs_stock() -> None:
    shop_bot_id, owner, _shop = await _setup()
    await _run_add_flow(
        owner,
        [
            ("tap", "product_add_digital"),
            ("say", "لایسنس"),
            ("say", "توضیحِ کوتاه"),
            ("say", "50000"),
            ("tap", "dg_skip:photo"),
            ("tap", "dg_mode:code_pool"),
            ("tap", "dg_skip:instructions"),
            ("tap", "dg_skip:max"),
            ("say", "A1\nA2\nA1\n\nB3"),
        ],
    )
    async with session_scope() as session:
        product = (await session.execute(select(Product).where(Product.shop_bot_id == shop_bot_id))).scalar_one()
        assert product.kind == "digital" and product.digital_delivery == "code_pool"
        assert product.stock_quantity == 3, "موجودی = تعدادِ کدهایِ available"
        stored = list((await session.execute(select(DigitalCode).where(DigitalCode.product_id == product.id))).scalars().all())
        assert sorted(decrypt_token(c.code) for c in stored) == ["A1", "A2", "B3"]
        assert all("A1" != c.code for c in stored), "کد رمزنگاری‌شده ذخیره می‌شه، نه متنِ ساده"
        pid = product.id

    # افزودنِ دوباره از ویرایش: A2 تکراری، C4 تازه
    await owner.tap(f"product_edit_field:{pid}:codes")
    await owner.say("A2\nC4")
    assert texts.dg_codes_result(1, 1, 0, 4) in [m["text"] for m in owner.sent]
    async with session_scope() as session:
        assert (await session.get(Product, pid)).stock_quantity == 4
    print("✅ test_add_digital_code_pool_flow_dedupes_and_syncs_stock PASSED")


async def test_digital_blocked_in_consultation_mode_and_stale_buttons() -> None:
    shop_bot_id, owner, _shop = await _setup()
    async with session_scope() as session:
        shop_bot = await session.get(ShopBot, shop_bot_id)
        assert "product_add_digital" in callbacks(keyboards.products_list_keyboard([], sales_mode=(shop_bot.tenant_mode == TenantMode.SALES)))
        shop_bot.tenant_mode = TenantMode.CONSULTATION
    assert "product_add_digital" not in callbacks(keyboards.products_list_keyboard([], sales_mode=False))
    assert "shipping_list" not in callbacks(keyboards.products_list_keyboard([], sales_mode=False))

    await owner.tap("product_add_digital")
    assert owner.last_toast["text"] == texts.DG_ONLY_SALES and owner.last_toast["show_alert"] is True
    await owner.tap("shipping_list")
    assert owner.last_toast["text"] == texts.DG_ONLY_SALES

    # دکمه‌هایِ کهنه (بدونِ state)
    for data in ("dg_mode:file", "dg_skip:codes", "dg_mode:bogus"):
        await owner.tap(data)
        assert owner.last_toast["text"] == texts.DG_STALE, data
    await owner.tap("ship_skip:eta")
    assert owner.last_toast["text"] == texts.SHIP_STALE
    print("✅ test_digital_blocked_in_consultation_mode_and_stale_buttons PASSED")


async def test_edit_fields_respect_product_kind() -> None:
    shop_bot_id, owner, _shop = await _setup()
    async with session_scope() as session:
        physical = await product_service.create_product(session, shop_bot_id, "کتاب", None, 100_000, None, 5)
        physical_id = physical.id
    digital_id = await _seed_digital(shop_bot_id, "link", link="https://x.test/a")

    assert "stock" not in "".join(callbacks(keyboards.edit_product_field_keyboard(digital_id, "digital", "link")))
    assert any(c.endswith(":dlink") for c in callbacks(keyboards.edit_product_field_keyboard(digital_id, "digital", "link")))
    assert not any(c.endswith(":dlink") for c in callbacks(keyboards.edit_product_field_keyboard(physical_id, "physical", None)))

    await owner.tap(f"product_edit_field:{digital_id}:stock")
    assert owner.last_toast["text"] == texts.EDIT_NOT_FOR_KIND
    await owner.tap(f"product_edit_field:{physical_id}:dlink")
    assert owner.last_toast["text"] == texts.EDIT_NOT_FOR_KIND
    await owner.tap(f"product_edit_field:{digital_id}:codes")  # لینک‌دار، استخرِ کد نیست
    assert owner.last_toast["text"] == texts.EDIT_NOT_FOR_KIND
    await owner.tap(f"product_edit_field:{physical_id}:bogus")
    assert owner.last_toast["text"] == texts.GENERIC_ERROR

    await owner.tap(f"product_edit_field:{physical_id}:weight")
    await owner.say("²")
    assert owner.last_text == texts.INVALID_WEIGHT
    await owner.say("۱۲۰۰")
    await owner.tap(f"product_edit_field:{physical_id}:delivery")
    await owner.say("۲ تا ۳ روزِ کاری")
    await owner.tap(f"product_edit_field:{digital_id}:dmax")
    await owner.say("۵")
    await owner.tap(f"product_edit_field:{digital_id}:dlink")
    await owner.say("javascript:alert(1)")
    assert owner.last_text == texts.DG_INVALID_LINK
    await owner.say("https://new.example/d")
    async with session_scope() as session:
        p = await session.get(Product, physical_id)
        d = await session.get(Product, digital_id)
        assert p.weight_grams == 1200 and p.delivery_note == "۲ تا ۳ روزِ کاری" and p.kind == "physical"
        assert d.digital_max_downloads == 5 and d.digital_link == "https://new.example/d" and d.kind == "digital"

    text_id = await _seed_digital(shop_bot_id, "text", instructions="متنِ اول")
    await owner.tap(f"product_edit_field:{text_id}:dinstr")
    await owner.say("رد شدن")
    assert owner.last_text == texts.DG_TEXT_CANNOT_BE_EMPTY, "متنِ تحویلِ نوعِ «متن» نمی‌تونه خالی بشه"
    print("✅ test_edit_fields_respect_product_kind PASSED")


# =============================================================================
# تحویل
# =============================================================================
async def test_code_pool_delivery_on_owner_confirm_is_idempotent() -> None:
    shop_bot_id, owner, shop_bot = await _setup()
    customer_id = await _seed_customer(shop_bot_id, CUSTOMER_TG_ID)
    product_id = await _seed_digital(shop_bot_id, "code_pool", instructions="کد رو در برنامه وارد کن")
    await _add_codes(product_id, ["KEY-1", "KEY-2"])
    order_id = await _order(shop_bot_id, customer_id, product_id)

    await owner.tap(f"confirm_order:{order_id}")
    got = _customer_texts(shop_bot)
    assert len(got) == 1 and "KEY-1" in got[0] and "کد رو در برنامه وارد کن" in got[0], got
    assert texts.digital_delivery_owner_note("delivered") in owner.last_edit_text

    async with session_scope() as session:
        order = await session.get(OrderConsultation, order_id)
        assert order.status == OrderStatus.CONFIRMED and order.digital_delivered_at is not None and order.digital_download_count == 1
        product = await session.get(Product, product_id)
        assert product.stock_quantity == 1, "یک کد مصرف شد، یکی مونده"
        delivered = list((await session.execute(select(DigitalCode).where(DigitalCode.order_id == order_id))).scalars().all())
        assert len(delivered) == 1 and delivered[0].status == "delivered" and decrypt_token(delivered[0].code) == "KEY-1"
        assert await digital_service.count_available_codes(session, product_id) == 1

        # تحویلِ دوباره‌یِ همون سفارش = هیچ اثری
        result = await digital_service.prepare_delivery(session, order)
        assert result.status == "already"
    await owner.tap(f"confirm_order:{order_id}")
    assert len(_customer_texts(shop_bot)) == 1, "تاییدِ دوباره = تحویلِ دوباره نیست"
    print("✅ test_code_pool_delivery_on_owner_confirm_is_idempotent PASSED")


async def test_quantity_two_gets_two_codes_and_partial_is_never_assigned() -> None:
    shop_bot_id, owner, shop_bot = await _setup()
    customer_id = await _seed_customer(shop_bot_id, CUSTOMER_TG_ID)
    product_id = await _seed_digital(shop_bot_id, "code_pool")
    await _add_codes(product_id, ["Q1"])
    short_order = await _order(shop_bot_id, customer_id, product_id, qty=2)
    await owner.tap(f"confirm_order:{short_order}")
    assert texts.digital_delivery_owner_note("insufficient") in owner.last_edit_text
    assert _customer_texts(shop_bot) == []
    async with session_scope() as session:
        assert await digital_service.count_available_codes(session, product_id) == 1, "تحویلِ نصفه ممنوع: کد دست‌نخورده می‌مونه"
        assert (await session.get(OrderConsultation, short_order)).digital_delivered_at is None

    # کدِ بیشتر ⇒ سفارشِ منتظر خودکار تحویل می‌شه (۲ کد)
    await owner.tap(f"product_edit_field:{product_id}:codes")
    await owner.say("Q2\nQ3")
    got = _customer_texts(shop_bot)
    assert len(got) == 1 and "Q1" in got[0] and "Q2" in got[0], got
    async with session_scope() as session:
        assert (await session.get(OrderConsultation, short_order)).digital_delivered_at is not None
        assert (await session.get(Product, product_id)).stock_quantity == 1, "Q3 مونده"
    assert texts.digital_pending_delivered_note(1, 0) in [m["text"] for m in owner.sent]
    print("✅ test_quantity_two_gets_two_codes_and_partial_is_never_assigned PASSED")


async def test_concurrent_delivery_never_double_assigns() -> None:
    shop_bot_id, _owner, _shop = await _setup()
    customer_id = await _seed_customer(shop_bot_id, CUSTOMER_TG_ID)

    # (الف) دو سفارشِ مختلف، یک کد ⇒ دقیقاً یکی ready
    product_id = await _seed_digital(shop_bot_id, "code_pool")
    await _add_codes(product_id, ["ONLY-1"])
    first = await _order(shop_bot_id, customer_id, product_id)
    second = await _order(shop_bot_id, customer_id, product_id)
    async with session_scope() as session:
        for oid in (first, second):
            (await session.get(OrderConsultation, oid)).status = OrderStatus.CONFIRMED

    async def attempt(order_id: int) -> str:
        async with session_scope() as session:
            order = await session.get(OrderConsultation, order_id)
            return (await digital_service.prepare_delivery(session, order)).status

    statuses = await asyncio.gather(attempt(first), attempt(second))
    assert sorted(statuses) == ["insufficient", "ready"], statuses
    async with session_scope() as session:
        assert await digital_service.count_available_codes(session, product_id) == 0
        delivered = (await session.execute(select(func.count()).select_from(DigitalCode).where(DigitalCode.status == "delivered"))).scalar_one()
        assert delivered == 1

    # (ب) یک سفارش، دو تلاشِ هم‌زمان (دابل‌تپ) با کدِ کافی ⇒ یکی ready، یکی already، فقط ۱ کد مصرف
    product2 = await _seed_digital(shop_bot_id, "code_pool")
    await _add_codes(product2, ["P-1", "P-2", "P-3"])
    order2 = await _order(shop_bot_id, customer_id, product2)
    async with session_scope() as session:
        (await session.get(OrderConsultation, order2)).status = OrderStatus.CONFIRMED
    statuses = await asyncio.gather(attempt(order2), attempt(order2))
    assert sorted(statuses) == ["already", "ready"], statuses
    async with session_scope() as session:
        assert await digital_service.count_available_codes(session, product2) == 2
    print("✅ test_concurrent_delivery_never_double_assigns PASSED")


async def test_link_delivery_and_download_again_limits_and_ownership() -> None:
    shop_bot_id, owner, shop_bot = await _setup()
    shop_dp = _ctx["shop_dp"]
    customer_id = await _seed_customer(shop_bot_id, CUSTOMER_TG_ID)
    await _seed_customer(shop_bot_id, OTHER_CUSTOMER_TG_ID)
    product_id = await _seed_digital(shop_bot_id, "link", link="https://example.com/get", max_downloads=2)
    order_id = await _order(shop_bot_id, customer_id, product_id)

    # پیش از تحویل، «دریافتِ دوباره» مجاز نیست
    await shop_dp.feed_update(shop_bot, make_callback_update(1, data=f"dl_again:{order_id}", user_id=CUSTOMER_TG_ID))
    assert shop_bot.session.answered_callbacks[-1]["text"] == shop_texts.DL_AGAIN_NOT_READY

    await owner.tap(f"confirm_order:{order_id}")
    got = _customer_texts(shop_bot)
    assert len(got) == 1 and "https://example.com/get" in got[0]
    markup = [m for m in shop_bot.session.sent_messages if m["chat_id"] == CUSTOMER_TG_ID][0]["reply_markup"]
    assert callbacks(markup) == [f"dl_again:{order_id}"]

    # مشتریِ دیگه نمی‌تونه سفارشِ این مشتری رو بگیره
    await shop_dp.feed_update(shop_bot, make_callback_update(2, data=f"dl_again:{order_id}", user_id=OTHER_CUSTOMER_TG_ID))
    assert shop_bot.session.answered_callbacks[-1]["text"] == shop_texts.DL_AGAIN_NOT_FOUND
    # آیدیِ جعلی
    await shop_dp.feed_update(shop_bot, make_callback_update(3, data="dl_again:abc", user_id=CUSTOMER_TG_ID))
    assert shop_bot.session.answered_callbacks[-1]["text"] == shop_texts.DL_AGAIN_NOT_FOUND
    await shop_dp.feed_update(shop_bot, make_callback_update(4, data="dl_again:999999", user_id=CUSTOMER_TG_ID))
    assert shop_bot.session.answered_callbacks[-1]["text"] == shop_texts.DL_AGAIN_NOT_FOUND

    # بارِ دوم (آخرین مجاز) ⇒ ارسال با «دریافتِ دوباره»؛ بارِ سوم ⇒ سقف
    await shop_dp.feed_update(shop_bot, make_callback_update(5, data=f"dl_again:{order_id}", user_id=CUSTOMER_TG_ID))
    assert len(_customer_texts(shop_bot)) == 2 and "دریافتِ دوباره" in _customer_texts(shop_bot)[1]
    await shop_dp.feed_update(shop_bot, make_callback_update(6, data=f"dl_again:{order_id}", user_id=CUSTOMER_TG_ID))
    assert shop_bot.session.answered_callbacks[-1]["text"] == shop_texts.DL_AGAIN_LIMIT
    assert len(_customer_texts(shop_bot)) == 2
    async with session_scope() as session:
        assert (await session.get(OrderConsultation, order_id)).digital_download_count == 2
    print("✅ test_link_delivery_and_download_again_limits_and_ownership PASSED")


async def test_file_delivery_reuploads_to_shop_bot_and_physical_order_untouched() -> None:
    shop_bot_id, owner, shop_bot = await _setup()
    customer_id = await _seed_customer(shop_bot_id, CUSTOMER_TG_ID)
    product_id = await _seed_digital(shop_bot_id, "file", file_id="main_bot_file_1", file_name="course.pdf")
    owner.session.downloaded_files["main_bot_file_1"] = b"%PDF-fake"
    order_id = await _order(shop_bot_id, customer_id, product_id)
    await owner.tap(f"confirm_order:{order_id}")
    docs = [d for d in shop_bot.session.sent_documents if d["chat_id"] == CUSTOMER_TG_ID]
    assert len(docs) == 1, "فایل با رباتِ فروشگاه (نه با file_idِ رباتِ اصلی) آپلود می‌شه"
    assert texts.digital_delivery_owner_note("delivered") in owner.last_edit_text

    # سفارشِ فیزیکی: هیچ تحویلِ دیجیتالی و هیچ یادداشتی
    async with session_scope() as session:
        physical = await product_service.create_product(session, shop_bot_id, "کتاب", None, 10_000, None, 3)
        physical_id = physical.id
    phys_order = await _order(shop_bot_id, customer_id, physical_id)
    before_docs = len(shop_bot.session.sent_documents)
    before = len(_customer_texts(shop_bot))
    await owner.tap(f"confirm_order:{phys_order}")
    assert len(shop_bot.session.sent_documents) == before_docs, "تحویلِ دیجیتالی نداریم"
    # W5/1.4: تاییدِ دستیِ سفارشِ فیزیکی دیگه اعلانِ خودکار به مشتری می‌ده (دقیقاً یکی)
    after = _customer_texts(shop_bot)
    assert len(after) == before + 1 and "تایید شد" in after[-1], after
    assert "💾" not in owner.last_edit_text
    print("✅ test_file_delivery_reuploads_to_shop_bot_and_physical_order_untouched PASSED")


# =============================================================================
# روش‌هایِ ارسال
# =============================================================================
async def test_shipping_methods_flow_and_ownership() -> None:
    shop_bot_id, owner, _shop = await _setup()
    await owner.tap("shipping_list")
    assert texts.SHIP_NONE in owner.last_edit_text
    await _run_add_flow(
        owner,
        [("tap", "ship_add"), ("say", "پست پیشتاز"), ("say", "x"), ("say", "۴۵،۰۰۰"), ("say", "500000"), ("say", "۲ تا ۴ روز")],
    )
    assert texts.INVALID_SHIP_FEE in [m["text"] for m in owner.sent]
    async with session_scope() as session:
        methods = await shipping_service.list_methods(session, shop_bot_id)
        assert len(methods) == 1
        m = methods[0]
        assert (m.name, m.fee_toman, m.free_over_toman, m.eta_text, m.is_active) == ("پست پیشتاز", 45_000, 500_000, "۲ تا ۴ روز", True)
        mid = m.id
    await _run_add_flow(owner, [("tap", "ship_add"), ("say", "پیک"), ("say", "0"), ("tap", "ship_skip:free_over"), ("tap", "ship_skip:eta")])
    await owner.tap(f"ship_toggle:{mid}")
    async with session_scope() as session:
        methods = await shipping_service.list_methods(session, shop_bot_id)
        assert [x.is_active for x in methods] == [False, True] and methods[1].fee_toman == 0 and methods[1].free_over_toman is None
        assert [x.id for x in await shipping_service.list_methods(session, shop_bot_id, only_active=True)] == [methods[1].id]

    # دکمه‌یِ کهنه/جعلی و روشِ فروشگاهِ دیگه
    await owner.tap("ship_toggle:bogus")
    assert owner.last_toast["text"] == texts.SHIP_STALE
    await owner.tap("ship_del:999999")
    assert owner.last_toast["text"] == texts.SHIP_STALE
    await owner.tap(f"ship_del:{mid}")
    async with session_scope() as session:
        assert len(await shipping_service.list_methods(session, shop_bot_id)) == 1

    # سقفِ ۱۰ روش
    async with session_scope() as session:
        for i in range(9):
            assert await shipping_service.create_method(session, shop_bot_id, f"روش {i}", 0) is not None
        assert await shipping_service.create_method(session, shop_bot_id, "یازدهم", 0) is None
        assert await shipping_service.create_method(session, shop_bot_id, "", 0) is None
        assert await shipping_service.create_method(session, shop_bot_id, "منفی", -1) is None
    await owner.tap("ship_add")
    assert owner.last_toast["text"] == texts.SHIP_LIMIT_REACHED
    print("✅ test_shipping_methods_flow_and_ownership PASSED")


async def test_physical_add_flow_unchanged_default_kind() -> None:
    shop_bot_id, owner, _shop = await _setup()
    await _run_add_flow(
        owner,
        [("tap", "product_add"), ("say", "چایِ ممتاز"), ("say", "رد شدن"), ("say", "۲۰۰۰۰"), ("tap", "product_skip:photo"), ("say", "7")],
    )
    async with session_scope() as session:
        product = (await session.execute(select(Product).where(Product.shop_bot_id == shop_bot_id))).scalar_one()
        assert product.kind == "physical" and product.digital_delivery is None and product.stock_quantity == 7 and product.price_toman == 20_000
    assert texts.product_detail_text(product) == "🏷 چایِ ممتاز\n💰 20,000 تومان\n📦 موجودی: 7 عدد", "جزئیاتِ فیزیکیِ ساده دست‌نخورده"
    print("✅ test_physical_add_flow_unchanged_default_kind PASSED")


async def main() -> None:
    main_dp, shop_dp, bot_manager, _main_bot = build_test_dispatchers()
    _ctx.update(main_dp=main_dp, shop_dp=shop_dp, bot_manager=bot_manager)
    await test_pure_helpers()
    await test_callback_data_within_telegram_limit()
    await test_ai_context_lines_per_kind()
    await test_excel_kind_column_and_legacy_rows()
    await test_add_digital_link_product_flow_and_double_tap()
    await test_add_digital_code_pool_flow_dedupes_and_syncs_stock()
    await test_digital_blocked_in_consultation_mode_and_stale_buttons()
    await test_edit_fields_respect_product_kind()
    await test_code_pool_delivery_on_owner_confirm_is_idempotent()
    await test_quantity_two_gets_two_codes_and_partial_is_never_assigned()
    await test_concurrent_delivery_never_double_assigns()
    await test_link_delivery_and_download_again_limits_and_ownership()
    await test_file_delivery_reuploads_to_shop_bot_and_physical_order_untouched()
    await test_shipping_methods_flow_and_ownership()
    await test_physical_add_flow_unchanged_default_kind()


if __name__ == "__main__":
    asyncio.run(main())
