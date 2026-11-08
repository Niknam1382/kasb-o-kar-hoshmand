"""
تست: P42 · گروه‌هایِ A/B — جداسازیِ «هوشمندسازیِ بله» از «بله‌پی» + باگ‌هایِ پول و ثبت

پوششِ درخواست‌هایِ مالکِ محصول (شماره‌ها همان فهرستِ ۵۱‌تایی است):
۱ و ۲۸. منویِ پنل هیچ دکمهٔ سبزی ندارد و چینشِ دونفره دست‌نخورده می‌ماند؛ «🟢 هوشمندسازیِ بله»
   داخلِ همان «🔑 ثبت/ویرایش توکن ربات» انتخاب می‌شود.
۲. «💳 پرداختِ آنلاینِ سفارش‌ها» اول گزینه‌ها را نشان می‌دهد و توکنی که آن‌جا نوشته می‌شود
   رباتِ بله را *هوشمند نمی‌کند* — ولی پرداخت با همان توکن فعال می‌ماند؛ «خاموش‌کردنِ
   هوشمندسازی» هم اتصالِ پرداخت را نمی‌کُشد.
۴. تاییدِ ادمین رویِ رسیدِ *متنی* (بی‌کپشن) دیگر با `edit_caption` نمی‌ترکد و تصمیم می‌ماند؛
   ردیفِ شارژِ کیف‌پول دیگر «None ماه» نشان نمی‌دهد.
۵. تمدیدِ روزِ دسته‌ای روی *همهٔ* بسته‌هایِ فعال می‌نشیند (نه «۰ اعمال، ۱ رد») و اعتبارِ هدیه به
   دیرترین شارژِ زنده اضافه می‌شود.
۷. عددِ «سقفِ بدهیِ کمیسیون» بعد ازِ زدنِ سوییچ واقعاً ذخیره می‌شود.
۲۱. دو شارژِ هم‌انقضا دو خطِ جدا می‌مانند.
۳۲. تایم‌اوتِ AI از تنظیمات می‌آید و همان بارِ پولی بی‌مقدمه تکرار نمی‌شود.
۳۳. در پنلِ مشاوره‌ای «پیام به کاربران» نوشته می‌شود، نه «پیام به مشتری‌ها».
۳۵. سوئیچِ «تشخیصِ سوال‌هایِ بی‌جواب» هر دو دکمه را از *هر دو* پنل برمی‌دارد.
۴۲. با درِ بستهٔ ثبت‌نام، نه `/start` و نه گیتِ کانال حسابِ تازه نمی‌سازد.

اجرا: python3 tests_manual/run_one.py test_p42_bale_split_and_money.py
"""
from __future__ import annotations

import ast
import asyncio
import datetime
import io
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from sqlalchemy import select  # noqa: E402

from harness import FakeSession, build_test_dispatchers, make_callback_update, reset_database  # noqa: E402
from phase4_helpers import Chat  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot import keyboards, texts  # noqa: E402
from app.bots.main_bot.handlers import panel as panel_handlers  # noqa: E402
from app.config import settings  # noqa: E402
from app.database.models import (  # noqa: E402
    Payment,
    PaymentPurpose,
    PaymentStatus,
    ShopBot,
    ShopOwner,
    WalletCharge,
    WalletTransactionReason,
)
from app.database.session import session_scope  # noqa: E402
from app.services import ai_service, bale_credentials_service as creds, credit_batch_service, payment_settings_service, payment_service, shop_owner_service, wallet_service  # noqa: E402
from app.services.admin_settings_service import get_admin_settings, update_setting  # noqa: E402

OWNER_TG_ID = 7_442_000_001
SHOP_BOT_TG_ID = 7_442_000_002
STRANGER_TG_ID = 7_442_000_003
BALE_BOT_ID = 7_442_000_004
BALE_TOKEN = f"{BALE_BOT_ID}:P42SHOPBALEFAKETOKEN0000000000"
SHOP_PROVIDER = "SHOP-P42-PROVIDER-TOKEN-0001"


async def _set(**pairs) -> None:
    async with session_scope() as session:
        for key, value in pairs.items():
            await update_setting(session, key, value)


async def _patch_shop(shop_bot_id: int, **columns) -> None:
    async with session_scope() as session:
        shop_bot = await session.get(ShopBot, shop_bot_id)
        for column, value in columns.items():
            setattr(shop_bot, column, value)
        await session.flush()


def _datas(markup) -> set[str]:
    return {b.callback_data for row in markup.inline_keyboard for b in row if b.callback_data}


# ============================================================================= ۱ و ۲۸ — منو و انتخابگرِ توکن
async def test_panel_has_no_green_button_and_token_section_offers_bale(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    await _set(bale_shop_bots_enabled=True)

    kb = keyboards.shop_owner_panel_keyboard("sales")
    labels = {b.text for row in kb.keyboard for b in row}
    assert texts.BALE_SHOP_BOT_BUTTON not in labels, "دکمهٔ سبزِ منو باید برداشته شود (موردِ ۱)"
    assert max(len(row) for row in kb.keyboard) <= 2, "چینشِ دونفره"

    owner = Chat(main_dp, OWNER_TG_ID)
    await owner.say("🔑 ثبت/ویرایش توکن ربات")
    assert owner.last_text == texts.SHOP_BOT_TOKEN_CHOICE_TEXT, owner.last_text
    assert {"tok_telegram", "tok_bale"} <= _datas(owner.last_markup), _datas(owner.last_markup)

    await owner.tap("tok_bale")
    assert "هوشمندسازی" in owner.last_text and "توکنِ رباتِ بله" in owner.last_text, owner.last_text

    # ویژگیِ پنهان ⇒ همان رفتارِ قدیمی (یکِ پرسشِ توکن، بدونِ انتخابگر)
    await _set(bale_shop_bots_enabled=False)
    await owner.say("🔑 ثبت/ویرایش توکن ربات")
    assert owner.last_text == texts.ASK_SHOP_BOT_TOKEN, owner.last_text
    print("✅ test_panel_has_no_green_button_and_token_section_offers_bale PASSED")


# ============================================================================= ۲ — توکنِ صفحهٔ پرداخت هوشمند نمی‌کند
async def test_payment_screen_shows_options_and_token_does_not_smartern(main_dp) -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    await _set(bale_shop_bots_enabled=True, bale_pay_enabled=True)
    await _patch_shop(shop_bot_id, bale_provider_token=SHOP_PROVIDER, bale_bot_enabled=False)

    owner = Chat(main_dp, OWNER_TG_ID)
    await owner.say("💳 پرداختِ آنلاینِ سفارش‌ها")
    datas = _datas(owner.last_markup)
    assert {"pays_tog:card", "pays_bale_token"} <= datas, f"اول گزینه‌ها، بعد توکن (موردِ ۲): {datas}"

    fetches: list[str] = []

    async def fake_fetch(token: str):
        fetches.append(token)
        return {"id": BALE_BOT_ID, "username": "shop_p42_bot"}

    original = panel_handlers.bale_bot_service.fetch_identity
    panel_handlers.bale_bot_service.fetch_identity = fake_fetch  # type: ignore[method-assign]
    try:
        await owner.tap("pays_bale_token")
        await owner.say(BALE_TOKEN)
        assert fetches == [BALE_TOKEN], fetches
        assert owner.sent[-2]["text"] == texts.BALE_TOKEN_SAVED_FOR_PAY_ONLY, owner.sent[-2]
        assert "توکنِ درگاه" in owner.last_text, "بعد ازِ ربات، سراغِ توکنِ درگاه می‌رود"
    finally:
        panel_handlers.bale_bot_service.fetch_identity = original  # type: ignore[method-assign]

    shop_bot = await _read_shop(shop_bot_id)
    assert shop_bot.bale_encrypted_token == BALE_TOKEN, "توکنِ پرداخت ثبت شده است"
    assert shop_bot.bale_bot_enabled is False, "و هوشمندسازی *روشن نشده* (موردِ ۲)"

    # با همین حالت، پرداختِ بله‌پی برایِ مشتری فعال است (پول به حسابِ خودِ فروشگاه)
    async with session_scope() as session:
        row = await session.get(ShopBot, shop_bot_id)
        pay_row = await payment_settings_service.get_or_create(session, shop_bot_id)
        pay_row.bale_enabled = True
        status = await creds.shop_status(session, row, pay_row)
        assert status.available, status.missing
    print("✅ test_payment_screen_shows_options_and_token_does_not_smartern PASSED")


async def _read_shop(shop_bot_id: int) -> ShopBot:
    async with session_scope() as session:
        return await session.get(ShopBot, shop_bot_id)


# ============================================================================= ۲ — «خاموش» یعنی هوشمندسازی، نه قطعِ پرداخت
async def test_bale_off_keeps_payment_connection(bot_manager) -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    await _patch_shop(
        shop_bot_id, bale_encrypted_token=BALE_TOKEN, bale_bot_id=BALE_BOT_ID, bale_bot_username="shop_p42_bot", bale_bot_enabled=True
    )

    real_poll = bot_manager._poll

    async def fake_poll(self_shop_bot_id, bot, *, bale=False):
        await asyncio.sleep(3600)

    bot_manager._poll = fake_poll  # type: ignore[method-assign]
    try:
        await bot_manager.register_bale(await _read_shop(shop_bot_id))
        assert bot_manager._bale_smarten[shop_bot_id] is True
        await _patch_shop(shop_bot_id, bale_bot_enabled=False)
        await bot_manager.register_bale(await _read_shop(shop_bot_id))
        assert bot_manager._bale_smarten[shop_bot_id] is False, "هوشمندسازی خاموش"
        assert shop_bot_id in bot_manager._bale_bots, "اتصالِ پرداخت نباید کشته شود (موردِ ۲)"
    finally:
        for task in list(bot_manager._bale_polling_tasks.values()):
            task.cancel()
        bot_manager._bale_polling_tasks.clear()
        bot_manager._bale_bots.clear()
        bot_manager._bale_smarten.clear()
        bot_manager._poll = real_poll  # type: ignore[method-assign]
    print("✅ test_bale_off_keeps_payment_connection PASSED")


# ============================================================================= ۴ — تاییدِ رسیدِ متنی + «None ماه»
async def test_admin_approve_text_receipt_and_validity_label(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    await _set(wallet_topup_validity_months=1)
    admin_id = next(iter(settings.admin_ids))

    async with session_scope() as session:
        owner = (await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == OWNER_TG_ID))).scalar_one()
        # ردیفِ پرداخت از *سرویس* ساخته می‌شود، نه از constructor: همان جایی که
        # `wallet_topup_validity_months` رویِ ردیف می‌نشیند (موردِ ۴).
        payment = await payment_service.create_card_to_card_payment(
            session, owner, 500_000, None, purpose=PaymentPurpose.WALLET_TOPUP
        )
        payment.receipt_text = "رسیدِ متنیِ آزمایشی P42"
        await session.flush()
        payment_id = payment.id

    admin = Chat(main_dp, admin_id)
    await admin.dp.feed_update(admin.bot, make_callback_update(1, data=f"admin_approve_payment:{payment_id}", user_id=admin_id))

    async with session_scope() as session:
        payment = await session.get(Payment, payment_id)
        assert payment.status == PaymentStatus.APPROVED, "تصمیمِ ادمین باید مانده باشد (موردِ ۴)"
        assert payment.duration_months == 1, payment.duration_months
        owner = (await session.execute(select(ShopOwner).where(ShopOwner.id == payment.shop_owner_id))).scalar_one()
        notice = texts.admin_new_payment_notification(payment, owner)
        assert "اعتبارِ شارژ: ۱ ماه" in notice, notice
        assert "None" not in notice, notice
        assert "اعتبارِ شارژ: ۱ ماه" in texts.payment_history_item(payment)

    session_obj: FakeSession = admin.bot.session  # type: ignore[assignment]
    assert session_obj.edited_captions == [], "رویِ پیامِ متنی نباید edit_caption فرستاده شود (موردِ ۴)"
    assert any("تایید" in (e.get("text") or "") for e in session_obj.edited_texts), session_obj.edited_texts
    print("✅ test_admin_approve_text_receipt_and_validity_label PASSED")


# ============================================================================= ۷ — عددِ سقفِ بدهی ذخیره می‌شود
async def test_commission_debt_ceiling_input_is_consumed(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    admin_id = next(iter(settings.admin_ids))

    admin = Chat(main_dp, admin_id)
    await admin.tap("admin_toggle_zero_credit_orders")
    assert admin.last_text == texts.ADMIN_ASK_COMMISSION_DEBT_CEILING, admin.last_text
    await admin.say("12000000")
    async with session_scope() as session:
        row = await get_admin_settings(session)
        assert row.orders_allowed_when_wallet_empty is True
        assert row.commission_debt_ceiling_toman == 12_000_000, row.commission_debt_ceiling_toman
    print("✅ test_commission_debt_ceiling_input_is_consumed PASSED")


# ============================================================================= ۵ و ۲۱ — بسته‌ها جدا، تمدیدِ همه، هدیه به دیرترین
async def _owner_id() -> int:
    async with session_scope() as session:
        return (await session.execute(select(ShopOwner.id).where(ShopOwner.telegram_id == OWNER_TG_ID))).scalar_one()


async def test_charges_stay_separate_and_extend_and_gift_joins_latest() -> None:
    await reset_database()
    # موجودیِ اولیه صفر: وگرنه سیدِ پیش‌فرض یکِ شارژِ ۱٬۰۰۰٬۰۰۰ تومانی می‌سازد و شمارشِ خطوط
    # (که خودِ موضوعِ موردِ ۲۱ است) بی‌معنا می‌شود.
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID, initial_balance_toman=0)
    owner_id = await _owner_id()

    async with session_scope() as session:
        owner = await session.get(ShopOwner, owner_id)
        near = await wallet_service.add_charge(session, owner, 150_000, reason=WalletTransactionReason.TOPUP)
        far = await wallet_service.add_charge(session, owner, 250_000, reason=WalletTransactionReason.TOPUP)
        session.add(
            WalletCharge(
                shop_owner_id=owner_id,
                amount_toman=90_000,
                remaining_toman=90_000,
                expires_at=near.expires_at,  # «دو شارژ در یکِ لحظه»
            )
        )
        await session.flush()
        near_id, far_id = near.id, far.id

    async with session_scope() as session:
        owner = await session.get(ShopOwner, owner_id)
        lots = await wallet_service.expiry_lots(session, owner)
        assert len(lots) == 3, f"موردِ ۲۱: دو شارژِ هم‌انقضا ترکیب نمی‌شوند → {[lot.remaining_toman for lot in lots]}"

    # هدیه ⇒ رویِ دیرترین شارژِ زنده، نه بستهٔ تازه و نه شارژِ در حالِ مصرف (موردِ ۵)
    async with session_scope() as session:
        owner = await session.get(ShopOwner, owner_id)
        balance_before = owner.wallet_balance_toman
        lot = await wallet_service.add_charge(
            session, owner, 70_000, reason=WalletTransactionReason.ADMIN_GRANT, reference="p42-gift", merge_into_latest=True
        )
        assert lot.id == far_id, f"هدیه باید به دیرترین شارژ برود → {lot.id} != {far_id}"
    async with session_scope() as session:
        rows = (await session.execute(select(WalletCharge).where(WalletCharge.shop_owner_id == owner_id))).scalars().all()
        assert len(rows) == 3, "موردِ ۵: هدیه ردیفِ تازه نساخته است"
        assert sum(r.remaining_toman for r in rows) == 150_000 + 250_000 + 90_000 + 70_000
        latest = max(rows, key=lambda r: r.expires_at)
        assert latest.remaining_toman == 320_000, [(r.remaining_toman, r.expires_at) for r in rows]
        owner = await session.get(ShopOwner, owner_id)
        assert owner.wallet_balance_toman == balance_before + 70_000

    # تمدیدِ دسته‌ایِ «روز» ⇒ رویِ *همهٔ* بسته‌ها، بدونِ ردیفِ اشتراک
    before = {}
    async with session_scope() as session:
        rows = (await session.execute(select(WalletCharge).where(WalletCharge.shop_owner_id == owner_id))).scalars().all()
        for row in rows:
            before[row.id] = (row.remaining_toman, row.expires_at)

    async with session_scope() as session:
        batch = await credit_batch_service.create_batch(session, kind="extend", flt="all", by="p42-test", days=5)
        assert batch is not None
        batch_id = batch.batch_id
    async with session_scope() as session:
        result = await credit_batch_service.execute(session, batch_id, by="p42-test")
        assert result.applied_owner_ids == [owner_id], (result.applied_owner_ids, result.skipped)
    async with session_scope() as session:
        rows = (await session.execute(select(WalletCharge).where(WalletCharge.shop_owner_id == owner_id))).scalars().all()
        assert len(rows) == 3
        for row in rows:
            amount, old_expiry = before[row.id]
            assert row.remaining_toman == amount, "تمدید نباید مبلغ را دست بزند"
            assert row.expires_at == old_expiry + datetime.timedelta(days=5), (row.id, row.expires_at, old_expiry)
        # دو بستهٔ هم‌انقضا هر دو جابه‌جا شده‌اند (حلقهٔ بالا تک‌تک بررسی کرد)؛ دو ردیفِ تازه
        # نساخته شده و مبلغِ هیچ‌کدام عوض نشده است.
        assert len(rows) == 3, [(r.remaining_toman, r.expires_at) for r in rows]
    print("✅ test_charges_stay_separate_and_extend_and_gift_joins_latest PASSED")


# ============================================================================= ۳۲ — تایم‌اوتِ AI
async def test_ai_timeout_is_not_retried() -> None:
    calls: list[int] = []

    class _TimeoutPost:
        def __init__(self, *args, **kwargs):
            calls.append(1)

        async def __aenter__(self):
            raise asyncio.TimeoutError

        async def __aexit__(self, *exc):
            return False

    class _FakeHttp:
        def post(self, *args, **kwargs):
            return _TimeoutPost()

    real_session = ai_service._get_http_session
    ai_service._get_http_session = lambda: _FakeHttp()  # type: ignore[assignment]
    service = ai_service.OpenAiCompatibleAiService(api_key="k", model="m", base_url="https://example.invalid/v1/chat/completions")
    try:
        raised = False
        try:
            await service._post_chat({"messages": []})
        except ai_service.AiServiceError as exc:
            raised = True
            assert "دیر رسید" in str(exc), str(exc)
        assert raised, "تایم‌اوت باید به AiServiceError تبدیل شود"
        assert len(calls) == 1, f"تایم‌اوت نباید دوباره به سرویس پولی فرستاده شود: {len(calls)}"
    finally:
        ai_service._get_http_session = real_session  # type: ignore[assignment]
    assert settings.ai_timeout_seconds >= 60, settings.ai_timeout_seconds
    print("✅ test_ai_timeout_is_not_retried PASSED")


# ============================================================================= ۳۵ و ۳۳ — سوئیچِ دانش و واژهٔ مشاوره‌ای
async def test_knowledge_gap_switch_hides_both_buttons(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    for mode in ("sales", "consultation"):
        on = {b.text for row in keyboards.shop_owner_panel_keyboard(mode, knowledge_gap=True).keyboard for b in row}
        off = {b.text for row in keyboards.shop_owner_panel_keyboard(mode, knowledge_gap=False).keyboard for b in row}
        assert {"🧩 سوال‌هایِ بی‌جواب", "📚 پرسش‌وپاسخ‌هایِ تاییدشده"} <= on, (mode, on)
        assert not ({"🧩 سوال‌هایِ بی‌جواب", "📚 پرسش‌وپاسخ‌هایِ تاییدشده"} & off), (mode, off)

    # «بازگشت به پنل» هم همان سوئیچ را می‌خواند (نه نسخهٔ فراموش‌شده در یکِ صفحهٔ خاص)
    await _set(knowledge_gap_enabled=False)
    owner = Chat(main_dp, OWNER_TG_ID)
    await owner.tap("main_menu")
    labels = {b.text for row in owner.last_markup.keyboard for b in row}
    assert "🧩 سوال‌هایِ بی‌جواب" not in labels, labels

    # موردِ ۳۳: مودِ مشاوره‌ای مخاطب را «کاربر» می‌خواند
    await _set(knowledge_gap_enabled=True)
    async with session_scope() as session:
        owner_row = (await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == OWNER_TG_ID))).scalar_one()
        await shop_owner_service.set_business_mode(session, owner_row, "consultation")
    await owner.tap("main_menu")
    labels = {b.text for row in owner.last_markup.keyboard for b in row}
    assert texts.BROADCAST_SALES_BUTTON not in labels, labels
    assert texts.BROADCAST_CONSULT_BUTTON in labels, labels
    # دکمهٔ مشاوره‌ای باید همان جریان را باز کند (نه «دکمهٔ ناشناخته» و نه state یِ گروگان‌رفته).
    # متنِ داخلِ این صفحه هنوز «مشتری» می‌گوید؛ جارویِ کاملِ واژه‌ها در همان پنل = ادامهٔ موردِ ۳۳
    # که در صفِ extra-high نشسته است (`docs/WORK-ORDER-P42.md`).
    await owner.say(texts.BROADCAST_CONSULT_BUTTON)
    assert "ارسال" in owner.last_text or "چت" in owner.last_text, owner.last_text
    print("✅ test_knowledge_gap_switch_hides_both_buttons PASSED")


# ============================================================================= ۴۲ — درِ بستهٔ ثبت‌نام
async def test_registration_gate_covers_every_path(main_dp) -> None:
    await reset_database()
    await _set(allow_new_registrations=False)

    stranger = Chat(main_dp, STRANGER_TG_ID)
    await stranger.say("/start")
    assert "ثبت‌نام" in stranger.last_text, stranger.last_text
    assert await _stranger_rows() == [], "درِ بسته نباید ShopOwner بسازد"

    # مسیرِ گیتِ کانال (که پیش از این درِ بسته را دور می‌زد)
    await stranger.dp.feed_update(stranger.bot, make_callback_update(9, data="check_channels_membership", user_id=STRANGER_TG_ID))
    assert await _stranger_rows() == [], "گیتِ کانال نباید حساب بسازد (موردِ ۴۲)"

    await _set(allow_new_registrations=True)
    await stranger.say("/start")
    assert len(await _stranger_rows()) == 1, "با درِ باز همان کاربر ثبت می‌شود"
    print("✅ test_registration_gate_covers_every_path PASSED")


async def _stranger_rows() -> list[int]:
    async with session_scope() as session:
        return list((await session.execute(select(ShopOwner.id).where(ShopOwner.telegram_id == STRANGER_TG_ID))).scalars().all())


# ============================================================================= ۳ — گرهِ ماژولِ زنده (ریشهٔ «تایید نشدنِ پرداخت»)
def test_live_module_alias_is_installed() -> None:
    """`python -m app.main` ماژول را `__main__` می‌کند؛ هر `from app import main` در
    `bot_manager` یکِ کپیِ دوم با `_state` خالی می‌ساخت و بعد ازِ commitِ پرداخت،
    `KeyError: 'main_bot'` می‌داد ⇒ اعلان و فاکتور هرگز نمی‌رفتند (موردِ ۳).

    خودِ بلوکِ `__main__` را نمی‌شود در سوئیت اجرا کرد (چون ربات را بالا می‌آورد)، پس این تست
    یکِ نگهبانِ ساختاری است: اگر روزی این سه خط از داخلِ گاردِ `__main__` بیرون برود یا حذف
    شود، همین‌جا می‌شکند. رفتارِ «پرداختِ تاییدشده ⇒ اعلان + فاکتور» مثلِ قبل در
    `test_p34_bale_own_payment_surface` و `test_w5_bale_hardening` پوشش دارد.
    """
    tree = ast.parse(io.open("app/main.py", encoding="utf-8").read())
    guard = [node for node in tree.body if isinstance(node, ast.If)]
    live = [
        node
        for node in guard
        if isinstance(node.test, ast.Compare) and getattr(node.test.left, "id", None) == "__name__"
    ]
    assert live, "بلوکِ `if __name__ == '__main__':` پیدا نشد"
    body = ast.dump(live[0])
    assert 'app.main' in body and "setdefault" in body, "گره‌زدنِ sys.modules['app.main'] حذف شده است"
    assert "setattr" in body, "اتصالِ app.main رویِ پکیجِ app حذف شده است"
    print("✅ test_live_module_alias_is_installed PASSED")


async def main() -> None:
    test_live_module_alias_is_installed()
    main_dp, shop_dp, bot_manager, main_bot = build_test_dispatchers()
    await test_panel_has_no_green_button_and_token_section_offers_bale(main_dp)
    await test_payment_screen_shows_options_and_token_does_not_smartern(main_dp)
    await test_bale_off_keeps_payment_connection(bot_manager)
    await test_admin_approve_text_receipt_and_validity_label(main_dp)
    await test_commission_debt_ceiling_input_is_consumed(main_dp)
    await test_charges_stay_separate_and_extend_and_gift_joins_latest()
    await test_ai_timeout_is_not_retried()
    await test_knowledge_gap_switch_hides_both_buttons(main_dp)
    await test_registration_gate_covers_every_path(main_dp)


if __name__ == "__main__":
    asyncio.run(main())
