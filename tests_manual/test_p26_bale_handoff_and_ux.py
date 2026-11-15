"""
تست: P26 — پلِ پرداختِ بله (`/start`)، متنِ خوشامدِ مشاوره‌ای و دکمه‌هایِ آمادهٔ زمان‌بندی

۱. `/start <payload>` رویِ رباتِ پرداختِ بله باید صورتحسابِ بومی (`sendInvoice`) را با همان
   `invoice_payload` و مبلغِ ریالیِ درست به همان چت بفرستد؛ اگر پرداخت تسویه/منقضی شده باشد یا
   payload جعلی باشد، هیچ صورتحسابی نمی‌رود و فقط یکِ پیامِ توضیحی.
۲. خوشامدِ حالتِ مشاوره‌ای نباید به دکمه‌ای اشاره کند که P25 حذفشان کرد («ما دکمه نداریم»);
   فقط وقتی «📞 ارتباط با پشتیبانی» روشن است همان یک دکمه معرفی می‌شود.
۳. «کی ارسال بشه؟» حالا پنج گزینهٔ آماده دارد و هر کد دقیقاً به همان رشته‌ای نگاشت می‌شود که
   `parse_when` می‌فهمد (یکِ منطقِ زمانی، نه دو تا).
۴. صفحهٔ «🔑 تنظیمات کلیدها» باید نامِ رباتِ پرداخت را نشان بدهد و «قالبِ لینک» را نه.
۵. لینکِ پرداخت همیشه به رباتی می‌رود که آپدیتش را می‌خوانیم (پلتفرم)، نه رباتِ بلهٔ فروشگاه؛
   و برچسبِ دکمه در بله «صفحه» نمی‌گوید، چون صفحه‌ای وجود ندارد.

اجرا: python3 tests_manual/run_one.py test_p26_bale_handoff_and_ux.py
"""
from __future__ import annotations

import datetime
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests_manual"))

from sqlalchemy import select  # noqa: E402

from harness import reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app import main as app_main  # noqa: E402
from app.bots.main_bot import keyboards as main_keyboards  # noqa: E402
from app.bots.main_bot import texts as main_texts  # noqa: E402
from app.bots.main_bot.handlers import panel as panel_handlers  # noqa: E402
from app.bots.shop_bot import keyboards as shop_keyboards  # noqa: E402
from app.bots.shop_bot import texts as shop_texts  # noqa: E402
from app.database.models import Payment, PaymentPurpose, PaymentStatus  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import bale_credentials_service, bale_service, scheduled_broadcast_service  # noqa: E402
from app.services.admin_settings_service import get_admin_settings  # noqa: E402

OWNER_TG_ID = 999_811
SHOP_BOT_TG_ID = 999_812
PAY_BOT_USERNAME = "platform_pay_bot"
BALE_CHAT_ID = 555_000_111


async def _configure_pay_bot() -> None:
    original_get_me = bale_service.get_me

    async def fake_get_me(token: str) -> dict:
        return {"id": 42, "username": PAY_BOT_USERNAME}

    bale_service.get_me = fake_get_me
    try:
        async with session_scope() as session:
            admin = await get_admin_settings(session)
            admin.bale_bot_token = "111111:fake-bale-bot-token-for-tests"
            admin.bale_provider_token = "provider-token-77"
            admin.bale_pay_enabled = True
            await session.flush()
            await bale_credentials_service.refresh(session)
    finally:
        bale_service.get_me = original_get_me


def _start_update(payload: str) -> dict:
    return {"update_id": 1, "message": {"message_id": 5, "chat": {"id": BALE_CHAT_ID}, "from": {"id": BALE_CHAT_ID}, "text": f"/start {payload}"}}


async def _record_invoice_calls() -> tuple[list, list]:
    invoices: list[dict] = []
    texts_sent: list[tuple] = []

    async def fake_send_invoice(bot_token, chat_id, provider_token, *, title, description, payload, amount_rial):
        invoices.append({"chat_id": chat_id, "provider": provider_token, "payload": payload, "rial": amount_rial, "title": title})

    async def fake_send_text(bot_token, chat_id, text):
        texts_sent.append((chat_id, text))

    bale_service.send_invoice = fake_send_invoice
    bale_service.send_text = fake_send_text
    return invoices, texts_sent


# ============================================================================= ۱ — `/start`ِ معتبر صورتحساب می‌فرستد
async def test_start_handoff_sends_native_invoice() -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    await _configure_pay_bot()
    invoices, texts_sent = await _record_invoice_calls()

    async with session_scope() as session:
        from app.services import payment_service
        from app.database.models import ShopOwner

        owner = (await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == OWNER_TG_ID))).scalar_one()
        payment = await payment_service.create_bale_payment(
            session, owner, 250_000, None, "payment-9-aaaaaaaaaaaaaaaa", purpose=PaymentPurpose.WALLET_TOPUP
        )
        payment_id = payment.id
        payload = payment.bale_invoice_payload

    await app_main._dispatch_bale_update(_start_update(payload))

    assert len(invoices) == 1, invoices
    assert invoices[0]["payload"] == payload, "همان payload ⇒ همان ردیفِ پرداخت در successful_payment"
    assert invoices[0]["rial"] == 2_500_000, f"۲۵۰٬۰۰۰ تومان ⇒ ۲٬۵۰۰٬۰۰۰ ریال: {invoices[0]}"
    assert invoices[0]["chat_id"] == BALE_CHAT_ID
    assert invoices[0]["provider"] == "provider-token-77"
    assert texts_sent == []

    async with session_scope() as session:
        still = await session.get(Payment, payment_id)
    assert still.status == PaymentStatus.PENDING, "دست‌نزدن به وضعیت (تایید فقط با پرداختِ واقعی)"
    print("✅ test_start_handoff_sends_native_invoice PASSED")


# ============================================================================= ۲ — payload جعلی یا تسویه‌شده
async def test_start_handoff_rejects_unknown_and_settled() -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    await _configure_pay_bot()
    invoices, texts_sent = await _record_invoice_calls()

    await app_main._dispatch_bale_update(_start_update("payment-9-deadbeefdeadbeef"))
    assert invoices == [], "payloadِ ناشناس نباید صورتحساب بسازد"
    assert len(texts_sent) == 1 and "پیدا نکردم" in texts_sent[0][1], texts_sent

    async with session_scope() as session:
        from app.services import payment_service
        from app.database.models import ShopOwner

        owner = (await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == OWNER_TG_ID))).scalar_one()
        payment = await payment_service.create_bale_payment(session, owner, 120_000, None, "payment-9-bbbbbbbbbbbbbbbb")
        payment.status = PaymentStatus.APPROVED
        await session.flush()

    invoices.clear()
    texts_sent.clear()
    await app_main._dispatch_bale_update(_start_update("payment-9-bbbbbbbbbbbbbbbb"))
    assert invoices == [], "پرداختِ تسویه‌شده دوباره صورتحساب نمی‌گیرد"
    assert len(texts_sent) == 1 and "قبلاً" in texts_sent[0][1], texts_sent

    # `/start` بی‌payload (کسی که خودش ربات را باز می‌کند) ⇒ خوشامدِ معنادار، نه سکوت
    invoices.clear()
    texts_sent.clear()
    await app_main._dispatch_bale_update(_start_update(""))
    assert invoices == [] and len(texts_sent) == 1, texts_sent
    assert texts_sent[0][1] == main_texts.BALE_PAY_BOT_IDLE, texts_sent[0][1]

    # payloadهایِ بی‌ربط/ناشناس ⇒ هیچ صورتحسابی نه، و دقیقاً یکِ پیامِ صادقانه (نه انبوه، نه سکوت)
    for junk, expected in (
        ("hello", "برایِ پرداخت نیست"),
        ("order-xyz", "پیدا نکردم"),
        ("cartgroup-deadbeef-aaaaaaaaaaaaaaaa", "پیدا نکردم"),
    ):
        invoices.clear()
        texts_sent.clear()
        await app_main._dispatch_bale_update(_start_update(junk))
        assert invoices == [], junk
        assert len(texts_sent) == 1 and expected in texts_sent[0][1], (junk, texts_sent)
    print("✅ test_start_handoff_rejects_unknown_and_settled PASSED")


# ============================================================================= ۳ — خوشامدِ مشاوره‌ای بدونِ دکمه
async def test_consultation_welcome_mentions_no_buttons() -> None:
    assert "دکمه" not in shop_texts.SHOP_WELCOME_CONSULTATION, shop_texts.SHOP_WELCOME_CONSULTATION
    for removed in ("خدمات و بسته‌ها", "سفارش‌هایِ من", "محصولات"):
        assert removed not in shop_texts.SHOP_WELCOME_CONSULTATION, removed
    plain = shop_texts.shop_welcome_consultation(support_enabled=False)
    assert plain == shop_texts.SHOP_WELCOME_CONSULTATION
    with_support = shop_texts.shop_welcome_consultation(support_enabled=True)
    assert shop_texts.BTN_SUPPORT in with_support and with_support != plain, with_support
    print("✅ test_consultation_welcome_mentions_no_buttons PASSED")


# ============================================================================= ۴ — دکمه‌هایِ آمادهٔ زمانِ ارسال
def test_schedule_presets_map_to_the_same_parser() -> None:
    markup = main_keyboards.schedule_when_keyboard()
    buttons = [btn for row in markup.inline_keyboard for btn in row]
    datas = [btn.callback_data for btn in buttons]
    assert len(buttons) == 8, datas  # پ۷۶: ردیفِ «🗓 روز و تکرار» به این صفحه اضافه شد
    assert "sched_when:custom" in datas and "customer_broadcast_cancel" in datas, datas
    assert "schedw_day" in datas, datas

    now = datetime.datetime(2026, 11, 2, 12, 0, tzinfo=datetime.timezone.utc)
    for code, raw in panel_handlers.SCHEDULE_PRESETS.items():
        assert any(btn.callback_data == f"sched_when:{code}" for btn in buttons), code
        parsed = scheduled_broadcast_service.parse_when(raw, now=now)
        assert parsed is not None, (code, raw)
        ok, _why = scheduled_broadcast_service.validate_when(parsed, now=now)
        assert ok, (code, raw, parsed)
    one_hour = scheduled_broadcast_service.parse_when(panel_handlers.SCHEDULE_PRESETS["1h"], now=now)
    assert abs((one_hour - now).total_seconds() - 3600) < 5, one_hour
    tomorrow_10 = scheduled_broadcast_service.parse_when(panel_handlers.SCHEDULE_PRESETS["tom10"], now=now)
    assert tomorrow_10.date() == datetime.date(2026, 11, 3), tomorrow_10
    assert set(main_texts.ASK_SCHEDULE_WHEN) and "گزینه" in main_texts.ASK_SCHEDULE_WHEN
    assert not hasattr(main_texts, "BALE_PAY_REDIRECT_TEXT"), "متنِ «رفتن به صفحهٔ پرداخت» بازنویسی شد"
    assert "بله" in main_texts.bale_pay_handoff_text(100_000)
    print("✅ test_schedule_presets_map_to_the_same_parser PASSED")


# ============================================================================= ۵ — رباتِ پرداخت در پنلِ ادمین دیده می‌شود
async def test_admin_settings_screen_names_the_payment_bot() -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    await _configure_pay_bot()
    async with session_scope() as session:
        admin = await get_admin_settings(session)
    pairs = dict(main_texts.admin_settings_button_labels(admin, "bale"))
    assert PAY_BOT_USERNAME in pairs["bale_bot_token"], pairs["bale_bot_token"]
    assert "bale_pay_link_template" not in pairs, "فیلدِ «قالبِ لینک» از پنل برداشته شده است"
    print("✅ test_admin_settings_screen_names_the_payment_bot PASSED")


# ============================================================================= ۶ — لینک به رباتِ polled می‌رود، نه رباتِ send-only
async def test_pay_link_ignores_the_shops_own_bale_bot() -> None:
    """رباتِ بله‌یِ خودِ فروشگاه فقط برایِ فرستادنِ پیام است (set_webhook/getUpdates فقط رویِ
    توکنِ پلتفرم) ⇒ اگر لینک به چتِ او برود، `/start` هرگز به ما نمی‌رسد و لینک مرده است."""
    await reset_database()
    shop_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    await _configure_pay_bot()
    async with session_scope() as session:
        from app.database.models import ShopBot

        shop = await session.get(ShopBot, shop_id)
        shop.bale_bot_username = "my_own_bale_bot"
        shop.bale_bot_enabled = True
        await session.flush()

    async with session_scope() as session:
        link = bale_credentials_service.pay_link_for("payment-9-cccccccccccccccc")
        assert link is not None, "پیش‌نیازها کامل است ⇒ لینک ساخته می‌شود"
        assert link.startswith(f"https://ble.ir/{PAY_BOT_USERNAME}?start="), link
        assert "my_own_bale_bot" not in link, "چتِ رباتی که آپدیتش را نمی‌خوانیم ⇒ لینکِ مرده"
        assert bale_credentials_service.pay_link_available()

    # برچسبِ دکمه هم باید صادق باشد: در بله «صفحه» نیست، چتِ اپِ بله است
    bale_label = [b for row in shop_keyboards.online_pay_keyboard("https://ble.ir/x?start=y", "k1", bale=True).inline_keyboard for b in row][0]
    plain_label = [b for row in shop_keyboards.online_pay_keyboard("https://pay.test/x", "k1").inline_keyboard for b in row][0]
    assert "اپِ بله" in bale_label.text and "صفحه" not in bale_label.text, bale_label.text
    assert "صفحه" in plain_label.text, plain_label.text
    print("✅ test_pay_link_ignores_the_shops_own_bale_bot PASSED")


async def main() -> None:
    await test_start_handoff_sends_native_invoice()
    await test_start_handoff_rejects_unknown_and_settled()
    await test_consultation_welcome_mentions_no_buttons()
    test_schedule_presets_map_to_the_same_parser()
    await test_admin_settings_screen_names_the_payment_bot()
    await test_pay_link_ignores_the_shops_own_bale_bot()
    print("\n✅ همهٔ تست‌هایِ P26 پاس شدند")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
