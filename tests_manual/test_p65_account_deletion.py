"""پ۶۵ · موردِ ۲۷/۴۱-ب — «حذفِ حسابِ من» در پنلِ خودِ فروشگاه‌دار.

پیشِ این فقط ادمین می‌توانست حسابی را ببندد (پ۲۲). این تست همان مرزی را قفل می‌کند که مسیرِ
تازه با آن تعریف می‌شود: **هویت و محتوا می‌رود، سندِ مالی و ممیزی می‌ماند** — و هیچ‌کدام با یکِ
تپِ ساده رخ نمی‌دهد.

پوششِ داده‌شده:
۱. `preview` شمارشِ درست می‌دهد (فقطِ همین فروشگاه) و پولِ مانده را به‌عنوانِ مانع می‌شناسد؛
   کمیسیونِ قفل‌شده مانعِ دوم است.
۲. `delete_account`: هویتِ بی‌نام، رازهایِ پاک‌شده، رباتِ خاموش، گفتگو/آدرس/سبد/اینستاگرام/کدِ موقت
   رفته — و در همان حال سفارش‌ها، کاتالوگ، دفترِ کیف‌پول و ردیف‌هایِ ممیزیِ قبلی دست‌نخورده باقی
   می‌مانند. ردیفِ مشتری *می‌ماند* (تا ارجاعِ پول نشکند) ولی با شناسهٔ بی‌نام.
۳. با موجودیِ غیرصفر یا کمیسیونِ قفل‌شده هیچ ردیفی عوض نمی‌شود (بی‌اثر، نه نصفه).
۴. جریانِ واقعیِ پنل: پروفایل ⇒ «🗑 حذفِ حسابِ من» ⇒ پیش‌نمایش ⇒ تاییدِ نخست ⇒ نوشتنِ واژه؛ واژهٔ غلط
   بی‌عمل است، فرارِ منو میانِ جریان حالت را می‌شکند و چیزی حذف نمی‌شود، و واژهٔ درست ⇒ یکِ ممیزی +
   خاموش‌کردنِ رباتِ زنده در `bot_manager` + بسته‌شدنِ دروازهٔ ورود.
۵. صفحهٔ بن‌بست (پولِ مانده) دکمهٔ «بله» ندارد و تاییدِ نخست همان شرط را دوباره می‌سنجد.
۶. قاعدهٔ ۲-۶ با استثنایِ ثبت‌شده: واژهٔ تایید عمداً در `_KNOWN_MENU_BUTTONS` نیست.
۷. کیبورد (بودجهٔ ۶۴ بایتی) و بی‌اثر ماندنِ کاملِ فروشگاهِ دیگر در همان اجرا.

اجرا: python3 tests_manual/run_one.py test_p65_account_deletion.py
"""
from __future__ import annotations

import asyncio
import datetime as dt
import re
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from sqlalchemy import func, select  # noqa: E402
from harness import build_test_dispatchers, reset_database  # noqa: E402
from phase4_helpers import Chat, add_customer, add_order, callbacks  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot import keyboards, texts  # noqa: E402
from app.bots.main_bot import router as main_router  # noqa: E402
from app.database.models import (  # noqa: E402
    AuditEventType,
    AuditLogEntry,
    Cart,
    CartItem,
    ConversationMessage,
    Customer,
    CustomerAddress,
    InstagramAccount,
    OrderConsultation,
    OtpCode,
    Product,
    ShopBot,
    ShopOwner,
    WalletCharge,
    WalletTransaction,
    WalletTransactionReason,
)
from app.database.session import session_scope  # noqa: E402
from app.services import account_deletion_service, audit_log_service, shop_owner_service  # noqa: E402

OWNER_TG_ID = 996_501
SHOP_BOT_TG_ID = 996_502
OTHER_OWNER_TG_ID = 996_503
OTHER_SHOP_TG_ID = 996_504
CUSTOMER_TG_IDS = (777_001, 777_002)
OTHER_CUSTOMER_TG_ID = 777_900
NOW = dt.datetime(2026, 11, 13, 6, 0, tzinfo=dt.timezone.utc)


class _Manager:
    """فیکِ `ShopBotManager`: فقط یادداشت می‌کند کدامِ ربات‌ها خاموش شدند."""

    def __init__(self) -> None:
        self.telegram: list[tuple[int, bool]] = []
        self.bale: list[int] = []

    async def unregister(self, shop_bot_id: int, disable_in_db: bool = True) -> None:
        self.telegram.append((shop_bot_id, disable_in_db))

    async def unregister_bale(self, shop_bot_id: int) -> None:
        self.bale.append(shop_bot_id)


async def _owner_id(user_id: int) -> int:
    async with session_scope() as session:
        return int((await session.execute(select(ShopOwner.id).where(ShopOwner.telegram_id == user_id))).scalar_one())


async def _owner_row(user_id: int) -> ShopOwner:
    async with session_scope() as session:
        return (await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == user_id))).scalar_one()


async def _bot_row(shop_bot_id: int) -> ShopBot:
    async with session_scope() as session:
        return await session.get(ShopBot, shop_bot_id)


async def _rows(session, model, *conditions) -> int:
    query = select(func.count()).select_from(model)
    if conditions:
        query = query.where(*conditions)
    return int((await session.execute(query)).scalar_one())


async def _seed_full_shop(*, balance: int = 0, zero_wallet_after: bool = False) -> tuple[int, int]:
    """دو فروشگاهِ سالم؛ اولی با مشتری، گفتگو، آدرس، سبد، اینستاگرام، کدِ موقت، سفارش و دفتر.

    `balance` همان شارژِ اولِ کیف‌پول است؛ `zero_wallet_after` موجودی را *صفر* می‌کند در حالی که
    ردیف‌هایِ دفترِ کیف‌پول می‌مانند (یعنی «اعتبار خرج شده») ⇒ مانعِ پول از بین می‌رود و مسیرِ
    حذف باز می‌شود. `(shop_bot_id, other_shop_bot_id)` برمی‌گرداند.
    """
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID, initial_balance_toman=balance)
    other_shop_bot_id = await seed_usable_shop(OTHER_OWNER_TG_ID, OTHER_SHOP_TG_ID, initial_balance_toman=balance)
    customer_ids = [await add_customer(shop_bot_id, tg, "سارا", "sara.shop") for tg in CUSTOMER_TG_IDS]
    await add_customer(other_shop_bot_id, OTHER_CUSTOMER_TG_ID, "نگار", "negar.shop")
    async with session_scope() as session:
        owner = await shop_owner_service.get_by_telegram_id(session, OWNER_TG_ID)
        if zero_wallet_after:
            owner.wallet_balance_toman = 0
            session.add(owner)
        product = Product(shop_bot_id=shop_bot_id, name="چسبِ چوب", price_toman=50_000)
        session.add(product)
        await session.flush()
        for customer_id in customer_ids:
            session.add(ConversationMessage(customer_id=customer_id, role="user", content="قیمت چند است؟"))
            session.add(CustomerAddress(customer_id=customer_id, address="تهران، خیابانِ تست، پلاک ۱", postal_code="1234567890"))
            cart = Cart(shop_bot_id=shop_bot_id, customer_id=customer_id)
            session.add(cart)
            await session.flush()
            session.add(CartItem(cart_id=cart.id, product_id=product.id, quantity=1))
        for shop_id, ig_id in ((shop_bot_id, "1784140001"), (other_shop_bot_id, "1784140002")):
            session.add(
                InstagramAccount(
                    shop_bot_id=shop_id, ig_account_id=ig_id, ig_username="my.shop",
                    access_token="IGQVJ6fake.token.for.tests", is_active=True,
                )
            )
        session.add(
            OtpCode(
                shop_owner_id=owner.id, code="12345", purpose="phone",
                phone_number="09125550001", expires_at=NOW + dt.timedelta(minutes=5),
            )
        )
        session.add(
            WalletTransaction(
                shop_owner_id=owner.id, amount_toman=-1_200, reason=WalletTransactionReason.CHAT_MESSAGE,
                idempotency_key="p65-consumption",
            )
        )
        # همان مصرف باید در موجودی هم دیده شود، تا دفترِ سید با موجودِ حسابِ تست قفل نشود.
        owner.wallet_balance_toman = max(0, int(owner.wallet_balance_toman) - 1_200)
        session.add(owner)
        await audit_log_service.log(session, AuditEventType.SHOP_SUSPENDED, shop_bot_id=shop_bot_id, details="ردیفِ ممیزیِ پیشِ حذف")
        await session.flush()
    for customer_id in customer_ids:
        await add_order(shop_bot_id, customer_id, phone="09125550001", address="تهران، تست")
    return shop_bot_id, other_shop_bot_id


async def test_preview_counts_and_money_blockers() -> None:
    await reset_database()
    shop_bot_id, _other = await _seed_full_shop(balance=1_000_000)
    async with session_scope() as session:
        owner = await shop_owner_service.get_by_telegram_id(session, OWNER_TG_ID)
        data = await account_deletion_service.preview(session, owner)
        assert data.blockers == (account_deletion_service.BLOCK_WALLET,), data.blockers
        assert data.customers == 2 and data.messages == 2 and data.addresses == 2, data
        assert data.orders == 2 and data.open_orders == 2, data
        assert data.instagram_accounts == 1 and data.bot_count == 1, data
        assert data.pending_notifications == 0, data

        owner.commission_reserved_toman = 5_000
        session.add(owner)
        await session.flush()
        data = await account_deletion_service.preview(session, owner)
        assert data.blockers == (account_deletion_service.BLOCK_WALLET, account_deletion_service.BLOCK_RESERVED), data.blockers

        owner.wallet_balance_toman = 0
        owner.commission_reserved_toman = 0
        session.add(owner)
        await session.flush()
        data = await account_deletion_service.preview(session, owner)
        assert data.blockers == (), data.blockers

        other = await shop_owner_service.get_by_telegram_id(session, OTHER_OWNER_TG_ID)
        other_data = await account_deletion_service.preview(session, other)
        assert other_data.customers == 1 and other_data.messages == 0, other_data
        assert shop_bot_id and other_data.bot_count == 1
    print("PASS test_preview_counts_and_money_blockers")


async def test_delete_anonymizes_identity_and_keeps_finance() -> None:
    await reset_database()
    shop_bot_id, _other = await _seed_full_shop(balance=1_000_000, zero_wallet_after=True)
    owner_pk = await _owner_id(OWNER_TG_ID)
    async with session_scope() as session:
        first_hash = (await session.execute(select(AuditLogEntry.row_hash).order_by(AuditLogEntry.id))).scalars().first()
        before = await _rows(session, AuditLogEntry)
    async with session_scope() as session:
        owner = await shop_owner_service.get_by_telegram_id(session, OWNER_TG_ID)
        result = await account_deletion_service.delete_account(session, owner, actor_telegram_id=OWNER_TG_ID)
        assert result["blocked"] == [] and result["bot_ids"] == [shop_bot_id], result
        assert result["erased"]["customers_anonymized"] == 2, result["erased"]
        assert result["erased"]["conversation_messages"] == 2, result["erased"]
        assert result["preview"].wallet_toman == 0, result["preview"]

    async with session_scope() as session:
        bot = await session.get(ShopBot, shop_bot_id)
        closed = await session.get(ShopOwner, owner_pk)
        # هویتِ فروشگاه‌دار رفته؛ شناسهٔ تلگرام و کدِ معرف ماندنی‌اند (دلیلش در سرِصفحهٔ سرویس).
        assert closed.is_deleted is True and closed.deleted_at is not None
        assert (closed.first_name, closed.last_name, closed.phone_number, closed.email, closed.username) == (None,) * 5
        assert closed.telegram_id == OWNER_TG_ID and closed.referral_code
        # رازها و وضعیتِ ربات.
        assert bot.is_active is False and bot.disabled_reason == "حذفِ حسابِ فروشگاه‌دار"
        assert bot.encrypted_token == account_deletion_service.SECRET_WIPED, bot.encrypted_token
        assert bot.webhook_secret_token == account_deletion_service.SECRET_WIPED
        assert (bot.bale_encrypted_token, bot.bale_bot_id, bot.bale_bot_username, bot.bale_bot_enabled) == (None, None, None, False)
        assert bot.bale_provider_token is None and bot.zarinpal_merchant_id is None
        assert bot.support_enabled is False and bot.knowledge_channel_id is None
        # مشتری: ردیف می‌ماند، هویت می‌رود، و شناسهٔ بی‌نام *منفی* است (هرگز با شناسهٔ واقعیِ کسی نمی‌جنگد).
        rows = list((await session.execute(select(Customer).where(Customer.shop_bot_id == shop_bot_id).order_by(Customer.id))).scalars())
        assert len(rows) == 2
        for row in rows:
            assert row.telegram_id == -row.id, row.telegram_id
            assert (row.first_name, row.last_name, row.username, row.phone_number, row.crm_notes, row.crm_tags) == (None,) * 6
        # رفتنی‌ها.
        assert await _rows(session, ConversationMessage) == 0
        assert await _rows(session, CustomerAddress) == 0
        assert await _rows(session, Cart) == 0 and await _rows(session, CartItem) == 0
        assert await _rows(session, InstagramAccount, InstagramAccount.shop_bot_id == shop_bot_id) == 0
        assert await _rows(session, OtpCode) == 0
        # ماندنی‌ها: اسنادِ مالی، کاتالوگ و ممیزی.
        assert await _rows(session, OrderConsultation) == 2
        assert await _rows(session, Product) == 1
        assert (
            await _rows(session, WalletTransaction, WalletTransaction.shop_owner_id == owner_pk) == 2
            and await _rows(session, WalletCharge, WalletCharge.shop_owner_id == owner_pk) == 1
        ), "دفترِ کیف‌پولِ همین حساب دست‌نخورده ماند"
        assert await _rows(session, AuditLogEntry) == before + 1
        new = (await session.execute(select(AuditLogEntry).where(AuditLogEntry.event_type == AuditEventType.OWNER_SELF_DELETED))).scalar_one()
        assert new.prev_hash and new.row_hash, "زنجیرهٔ هشِ ممیزی با حذفِ حساب هم ادامه دارد"
        assert (await session.execute(select(AuditLogEntry.row_hash).order_by(AuditLogEntry.id))).scalars().first() == first_hash
        assert "اسنادِ مالی و ممیزی نگه داشته شد" in (new.details or "")
        assert "09125550001" not in (new.details or ""), "شمارهٔ تلفن در ممیزیِ حذف ثبت نمی‌شود"
    print("PASS test_delete_anonymizes_identity_and_keeps_finance")


async def test_money_blocks_and_nothing_changes() -> None:
    await reset_database()
    shop_bot_id, _other = await _seed_full_shop(balance=1_000_000)
    owner_pk = await _owner_id(OWNER_TG_ID)
    async with session_scope() as session:
        audit_before = await _rows(session, AuditLogEntry)
    async with session_scope() as session:
        owner = await shop_owner_service.get_by_telegram_id(session, OWNER_TG_ID)
        result = await account_deletion_service.delete_account(session, owner, actor_telegram_id=OWNER_TG_ID)
        assert result["blocked"] == [account_deletion_service.BLOCK_WALLET], result["blocked"]
        assert result["erased"] == {} and result["bot_ids"] == []

    async with session_scope() as session:
        closed = await session.get(ShopOwner, owner_pk)
        bot = await session.get(ShopBot, shop_bot_id)
        assert closed.is_deleted is False and closed.phone_number, "با مانع، هیچچیز عوض نمی‌شود"
        assert bot.is_active is True and bot.encrypted_token != account_deletion_service.SECRET_WIPED
        assert await _rows(session, ConversationMessage) == 2
        assert await _rows(session, AuditLogEntry) == audit_before, "ممیزیِ حذف ثبت نشد"
    print("PASS test_money_blocks_and_nothing_changes")


async def test_panel_flow_needs_the_word_and_stops_the_live_bot(main_dp) -> None:
    await reset_database()
    shop_bot_id, _other = await _seed_full_shop()
    manager = _Manager()
    chat = Chat(main_dp, OWNER_TG_ID)
    chat.extra = {"bot_manager": manager}

    await chat.say("👤 پروفایل من")
    assert "acc_delete" in callbacks(chat.last_markup), chat.last_markup
    await chat.tap("acc_delete")
    body = chat.edits[-1]["text"]
    assert "این‌ها پاک یا بی‌نام می‌شوند" in body and "این‌ها می‌مانند" in body, body
    assert "۲ سفارش" in body and not re.search(r"[0-9]", body), body
    assert callbacks(chat.edits[-1]["reply_markup"]) == ["acc_delete_yes", "pf_back"]
    answers = len(chat.session.answered_callbacks)
    await chat.tap("acc_delete_yes")
    assert len(chat.session.answered_callbacks) == answers + 1, "دقیقاً یکِ پاسخِ کال‌بک در هر تپ"
    assert texts.ACCOUNT_DELETE_WORD in chat.sent[-1]["text"]
    assert (await _owner_row(OWNER_TG_ID)).is_deleted is False, "مرحلهٔ دوم بی‌واژه بی‌اثر است"

    await chat.say("حذفِ قطعی")
    assert chat.last_text == texts.ACCOUNT_DELETE_BAD_WORD.format(word=texts.ACCOUNT_DELETE_WORD)
    assert (await _owner_row(OWNER_TG_ID)).is_deleted is False
    assert manager.telegram == [], "هیچ رباتی خاموش نشد"

    # فرارِ منو: میانهٔ جریانِ تایید، یکِ دکمهٔ منو باید حالت را بشکند و حذف نشود.
    await chat.say("📊 آمار")
    assert (await _owner_row(OWNER_TG_ID)).is_deleted is False
    await chat.say(texts.ACCOUNT_DELETE_WORD)
    assert (await _owner_row(OWNER_TG_ID)).is_deleted is False, "بعد ازِ فرار، واژه نباید حذف را انجام دهد"

    await chat.tap("acc_delete")
    await chat.tap("acc_delete_yes")
    await chat.say(texts.ACCOUNT_DELETE_WORD)
    assert "🧊 حساب بسته شد" in chat.last_text, chat.last_text
    assert "ردیف پاک" in chat.last_text and "بی‌نام شد" in chat.last_text, chat.last_text
    assert manager.telegram == [(shop_bot_id, False)], manager.telegram
    assert manager.bale == [shop_bot_id], manager.bale
    assert (await _owner_row(OWNER_TG_ID)).is_deleted is True
    assert (await _bot_row(shop_bot_id)).is_active is False

    # دروازهٔ ورود: بعد ازِ حذف هر پیامی فقط همان اخطار را می‌گیرد و هیچ صفحه‌ای باز نمی‌شود.
    edits_before = len(chat.edits)
    await chat.say("📊 آمار")
    assert chat.last_text == texts.ACCOUNT_DELETED_NOTICE, chat.last_text
    assert len(chat.edits) == edits_before, "پس ازِ بسته‌شدنِ حساب صفحه‌ای ویرایش نمی‌شود"
    print("PASS test_panel_flow_needs_the_word_and_stops_the_live_bot")


async def test_blocked_screen_has_no_confirm_button(main_dp) -> None:
    await reset_database()
    await _seed_full_shop(balance=1_000_000)
    async with session_scope() as session:
        owner = await shop_owner_service.get_by_telegram_id(session, OWNER_TG_ID)
        owner.commission_reserved_toman = 5_000
        session.add(owner)

    chat = Chat(main_dp, OWNER_TG_ID)
    await chat.say("👤 پروفایل من")
    await chat.tap("acc_delete")
    body = chat.edits[-1]["text"]
    assert "اعتبار" in body and "کمیسیون" in body, body
    assert callbacks(chat.edits[-1]["reply_markup"]) == ["pf_back"], "دکمهٔ «بله» رویِ صفحهٔ بن‌بست نیست"
    await chat.tap("acc_delete_yes")
    assert "اعتبار" in chat.edits[-1]["text"], "تاییدِ نخست هم همان شرط را دوباره می‌سنجد"
    assert (await _owner_row(OWNER_TG_ID)).is_deleted is False
    print("PASS test_blocked_screen_has_no_confirm_button")


async def test_confirmation_word_is_not_a_menu_button() -> None:
    assert texts.audit_event_label(AuditEventType.OWNER_SELF_DELETED) != AuditEventType.OWNER_SELF_DELETED.value
    assert "حذفِ حساب" in texts.audit_event_label(AuditEventType.OWNER_SELF_DELETED)

    # قاعدهٔ §۲-۶ با یکِ استثنایِ عمدی: اگر «حذفِ حساب» برچسبِ دکمهٔ منو می‌شد، میدل‌ورِ فرارِ منو
    # پیش ازِ هندلر `state.clear()` می‌کرد و تایپِ واژهٔ تایید هرگز حذف را انجام نمی‌داد.
    assert texts.ACCOUNT_DELETE_WORD not in main_router._KNOWN_MENU_BUTTONS
    assert texts.ACCOUNT_DELETE_BUTTON not in main_router._KNOWN_MENU_BUTTONS
    sales_labels = {button.text for row in keyboards.shop_owner_panel_keyboard("sales").keyboard for button in row}
    assert texts.ACCOUNT_DELETE_WORD not in sales_labels and texts.ACCOUNT_DELETE_BUTTON not in sales_labels
    print("PASS test_confirmation_word_is_not_a_menu_button")


async def test_keyboard_bounds_and_other_shop_untouched(main_dp) -> None:
    flat = callbacks(keyboards.account_delete_keyboard())
    assert flat == ["acc_delete_yes", "pf_back"]
    for value in flat + ["acc_delete"]:
        assert len(value.encode("utf-8")) <= 64, value
    labels = [button.text for row in keyboards.profile_keyboard().inline_keyboard for button in row]
    assert texts.ACCOUNT_DELETE_BUTTON in labels, labels
    assert callbacks(keyboards.account_delete_blocked_keyboard()) == ["pf_back"]

    await reset_database()
    shop_bot_id, other_bot_id = await _seed_full_shop()
    chat = Chat(main_dp, OWNER_TG_ID)
    chat.extra = {"bot_manager": _Manager()}
    await chat.tap("acc_delete")
    await chat.tap("acc_delete_yes")
    await chat.say(texts.ACCOUNT_DELETE_WORD)
    async with session_scope() as session:
        other_bot = await session.get(ShopBot, other_bot_id)
        assert other_bot.is_active is True
        assert other_bot.encrypted_token != account_deletion_service.SECRET_WIPED
        assert await _rows(session, InstagramAccount, InstagramAccount.shop_bot_id == other_bot_id) == 1
        customers = list((await session.execute(select(Customer).where(Customer.shop_bot_id == other_bot_id))).scalars())
        assert len(customers) == 1 and customers[0].first_name == "نگار" and customers[0].telegram_id == OTHER_CUSTOMER_TG_ID
        assert (await shop_owner_service.get_by_telegram_id(session, OTHER_OWNER_TG_ID)).is_deleted is False
        assert (await session.get(ShopBot, shop_bot_id)).is_active is False
    print("PASS test_keyboard_bounds_and_other_shop_untouched")


async def main() -> None:
    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    await test_preview_counts_and_money_blockers()
    await test_delete_anonymizes_identity_and_keeps_finance()
    await test_money_blocks_and_nothing_changes()
    await test_panel_flow_needs_the_word_and_stops_the_live_bot(main_dp)
    await test_blocked_screen_has_no_confirm_button(main_dp)
    await test_confirmation_word_is_not_a_menu_button()
    await test_keyboard_bounds_and_other_shop_untouched(main_dp)
    print("📊 نتیجه: ۷ تستِ پ۶۵ (حذفِ حسابِ خودخدمت) پاس شد · شمارش/مانع/بی‌نام‌سازی/جریانِ پنل/بن‌بست/واژه/کیبورد")


if __name__ == "__main__":
    asyncio.run(main())
