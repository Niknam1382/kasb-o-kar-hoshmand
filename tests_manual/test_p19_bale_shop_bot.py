"""
تست: P19 — رباتِ بله‌یِ خودِ فروشگاه (هوشمند روی بله، همان کیف‌پول، با کلیدِ رونماییِ ادمین)

پوشش:
۱. قاعده‌هایِ خالص: اعتبارِ فرمتِ توکن، ماسک‌کردن (هیچ‌جا توکنِ خام بیرون نمی‌آید)، کلیدِ ادمین.
۲. پلتفرم: `build_bot` علامتِ بله می‌گیرد؛ نگاشتِ «شناسه‌یِ ربات → فروشگاه» بین تلگرام و بله
   اشتباه نمی‌شود حتی اگر عددِ رباتِ بله با عددِ رباتِ تلگرامِ فروشگاهِ دیگری برابر باشد.
۳. هویتِ مشتری: یک عددِ یکسان در دو پلتفرم ⇒ دو ردیفِ مشتریِ جدا؛ بلاک هم پلتفرم‌مبنا است.
۴. ShopBotManager: ثبت/حذفِ اتصالِ بله و `customer_bot` (پلتفرمِ درست ⇒ رباتِ درست).
۵. پیامِ همگانی: هر گیرنده روی پلتفرمِ خودش می‌رود؛ گیرنده‌یِ بی‌اتصال رد می‌شود (نه اسپم به غریبه).
۶. پنلِ ادمین: رونمایی/پنهان (ممیزی + ظاهر/مخفی‌شدنِ دکمه + وصل‌شدنِ فروشگاه‌هایِ آماده).
۷. پنلِ فروشگاه‌دار: صفحه‌یِ وضعیت، ثبتِ توکن (ذخیره‌یِ رمزنگاری‌شده + فراخوانیِ اتصال)، ردِّ توکنِ
   تکراری، خاموش/روشن‌کردن و حذفِ اتصال (رباتِ تلگرام دست‌نخورده).

اجرا: python3 tests_manual/test_p19_bale_shop_bot.py
"""
from __future__ import annotations

import asyncio
import sys
from types import SimpleNamespace

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from sqlalchemy import select, text as sql_text  # noqa: E402

from harness import build_test_dispatchers, make_shop_bot, reset_database  # noqa: E402
from phase4_helpers import Chat  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot import keyboards, texts as main_texts  # noqa: E402
from app.bots.main_bot.handlers import panel as panel_handlers  # noqa: E402
from app.bots.shop_bot import middlewares as shop_middlewares  # noqa: E402
from app.database.models import AuditEventType, AuditLogEntry, ShopBot  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import (  # noqa: E402
    bale_bot_service,
    bale_service,
    customer_service,
    platform_service,
    shop_bot_service,
    shop_owner_service,
)
from app.services.admin_settings_service import get_admin_settings  # noqa: E402
from app.utils.encryption import decrypt_token  # noqa: E402

ADMIN_TG_ID = 12345
OWNER_TG_ID = 999_961
SHOP_BOT_TG_ID = 999_962
OTHER_OWNER_TG_ID = 999_971
OTHER_SHOP_BOT_TG_ID = 999_972
BALE_BOT_ID = 555_001
CUSTOMER_ID = 777_001
FAKE_BALE_TOKEN = "1234567:FAKE_BALE_TOKEN_FOR_TESTS_abcdefghijklmnopqrstuvwxyz"
BALE_IDENTITY = {"id": BALE_BOT_ID, "username": "my_shop_bale", "first_name": "فروشگاه من"}


async def _set_flag(enabled: bool) -> None:
    async with session_scope() as session:
        admin = await get_admin_settings(session)
        admin.bale_shop_bots_enabled = enabled
        await session.flush()


async def _flag() -> bool:
    async with session_scope() as session:
        return bool((await get_admin_settings(session)).bale_shop_bots_enabled)


async def _shop_bot(shop_bot_id: int) -> ShopBot:
    async with session_scope() as session:
        return (await session.execute(select(ShopBot).where(ShopBot.id == shop_bot_id))).scalar_one()


async def _set_bale_bot_id(shop_bot_id: int, bale_bot_id: int | None) -> None:
    """فقط شناسه (برایِ تستِ نگاشتِ ربات → فروشگاه، بدونِ توکن)."""
    async with session_scope() as session:
        row = (await session.execute(select(ShopBot).where(ShopBot.id == shop_bot_id))).scalar_one()
        row.bale_bot_id = bale_bot_id
        await session.flush()


async def _attach_bale_token(shop_bot_id: int) -> None:
    async with session_scope() as session:
        row = (await session.execute(select(ShopBot).where(ShopBot.id == shop_bot_id))).scalar_one()
        await bale_bot_service.apply_token(session, row, FAKE_BALE_TOKEN, BALE_IDENTITY)


def _bale_bot(token: str):
    """رباتِ جعلیِ بله: جلسه‌یِ تستی + علامتِ پلتفرم، بدونِ هیچ درخواستِ واقعی."""
    bot = make_shop_bot(token)
    bot.bale_platform = True
    return bot


class _RecordingManager:
    """فقط چیزی که مسیرهایِ ارسالِ مشتری لازم دارد: customer_bot."""

    def __init__(self, bots: dict[str, object]) -> None:
        self.bots = bots
        self.registered: list[int] = []
        self.unregistered: list[int] = []

    def customer_bot(self, shop_bot_id: int, platform: str | None):
        return self.bots.get(platform or platform_service.TELEGRAM)


# ============================================================================= ۱ — قاعده‌هایِ خالص
async def test_token_and_flag_rules() -> None:
    assert bale_bot_service.valid_token_input(FAKE_BALE_TOKEN)
    assert not bale_bot_service.valid_token_input("  ")
    assert not bale_bot_service.valid_token_input("short")
    assert not bale_bot_service.valid_token_input("1234567:WITH SPACE INSIDE")
    assert not bale_bot_service.valid_token_input(None)

    shop_bot = ShopBot(bale_encrypted_token=FAKE_BALE_TOKEN, bale_bot_enabled=True)
    masked = bale_bot_service.token_masked(shop_bot)
    assert FAKE_BALE_TOKEN not in masked and masked.startswith("●●●●"), masked
    assert bale_bot_service.connectable(shop_bot) is True
    shop_bot.bale_bot_enabled = False
    assert bale_bot_service.connectable(shop_bot) is False, "سوییچِ خودِ فروشگاه ⇒ اتصال نمی‌شود"
    assert bale_bot_service.connectable(ShopBot(bale_bot_enabled=True)) is False, "بدونِ توکن"
    assert bale_bot_service.connectable(None) is False

    assert bale_bot_service.enabled(SimpleNamespace(bale_shop_bots_enabled=False)) is False
    assert bale_bot_service.enabled(SimpleNamespace(bale_shop_bots_enabled=True)) is True

    await reset_database()
    assert await _flag() is False, "پیش‌فرض ⇒ ویژگی پنهان است"
    async with session_scope() as session:
        assert await bale_bot_service.visible_for(session) is False
        admin = await get_admin_settings(session)
        admin.bale_shop_bots_enabled = True
        await session.flush()
    async with session_scope() as session:
        assert await bale_bot_service.visible_for(session) is True
    print("✅ test_token_and_flag_rules PASSED")


# ============================================================================= ۲ — پلتفرم و نگاشتِ ربات
async def test_platform_marker_and_shop_resolution() -> None:
    await reset_database()
    first = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    second = await seed_usable_shop(OTHER_OWNER_TG_ID, OTHER_SHOP_BOT_TG_ID)

    assert platform_service.platform_of(make_shop_bot("111111:PLAIN_FAKE")) == platform_service.TELEGRAM
    assert platform_service.of_event(SimpleNamespace(bot=make_shop_bot("111111:PLAIN_FAKE"))) == platform_service.TELEGRAM

    built = bale_bot_service.build_bot(FAKE_BALE_TOKEN)
    try:
        assert platform_service.is_bale(built) is True
        assert built.session.api.base == f"{bale_api_base()}/bot{{token}}/{{method}}"
    finally:
        await built.session.close()

    # عددِ رباتِ بله‌یِ فروشگاهِ اول = عددِ رباتِ تلگرامِ فروشگاهِ دوم ⇒ هر دو باید به جایِ خودشان بروند
    await _set_bale_bot_id(first, OTHER_SHOP_BOT_TG_ID)
    async with session_scope() as session:
        as_bale = await shop_bot_service.get_by_bot(session, _bale_bot(f"{OTHER_SHOP_BOT_TG_ID}:FAKE_TG"))
        as_telegram = await shop_bot_service.get_by_bot(session, make_shop_bot(f"{OTHER_SHOP_BOT_TG_ID}:FAKE_TG"))
        not_found = await shop_bot_service.get_by_platform_bot_id(session, 888_888, bale=True)
    assert as_bale is not None and as_bale.id == first, "رباتِ بله باید به فروشگاهِ خودش برسد"
    assert as_telegram is not None and as_telegram.id == second, "همان عدد از تلگرام فروشگاهِ دیگری است"
    assert not_found is None
    print("✅ test_platform_marker_and_shop_resolution PASSED")


def bale_api_base() -> str:
    from app.config import settings

    return settings.bale_api_base.rstrip("/")


# ============================================================================= ۳ — هویتِ مشتری
async def test_customer_identity_is_per_platform() -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    # رباتِ بله‌یِ همین فروشگاه عمداً همان عددِ رباتِ تلگرام را می‌گیرد تا فقط پلتفرم متمایزکننده باشد
    await _set_bale_bot_id(shop_bot_id, SHOP_BOT_TG_ID)

    async with session_scope() as session:
        tg = await customer_service.get_or_create_customer(session, shop_bot_id, CUSTOMER_ID, "علی", "ali_t", None)
        bale = await customer_service.get_or_create_customer(
            session, shop_bot_id, CUSTOMER_ID, "مریم", "m_bale", None, platform=platform_service.BALE
        )
        assert tg.id != bale.id, "یک عدد در دو پلتفرم ⇒ دو مشتری"
        assert tg.platform == platform_service.TELEGRAM and bale.platform == platform_service.BALE
        assert (await customer_service.get_by_shop_bot_and_telegram_id(session, shop_bot_id, CUSTOMER_ID)).id == tg.id
        found = await customer_service.get_by_shop_bot_and_telegram_id(
            session, shop_bot_id, CUSTOMER_ID, platform=platform_service.BALE
        )
        assert found.id == bale.id
        assert sorted(await customer_service.recipients_by_shop_bot(session, shop_bot_id)) == [
            (CUSTOMER_ID, platform_service.BALE),
            (CUSTOMER_ID, platform_service.TELEGRAM),
        ]
        assert await customer_service.recipients_by_ids(session, shop_bot_id, []) == []
        assert await customer_service.recipients_by_ids(session, shop_bot_id, [bale.id]) == [
            (CUSTOMER_ID, platform_service.BALE)
        ]
        tg.is_blocked = True
        await session.flush()

    async with session_scope() as session:
        blocked = await shop_middlewares.is_blocked(
            session, ShopBot.bale_bot_id, SHOP_BOT_TG_ID, CUSTOMER_ID, platform_service.BALE
        )
        other = await shop_middlewares.is_blocked(
            session, ShopBot.bot_telegram_id, SHOP_BOT_TG_ID, CUSTOMER_ID, platform_service.TELEGRAM
        )
    assert blocked is False and other is True, "بلاکِ مشتریِ تلگرام نباید مشتریِ بله را بخواباند"
    print("✅ test_customer_identity_is_per_platform PASSED")


# ============================================================================= ۴ — اتصالِ بله در منیجر
async def test_manager_bale_transport_and_customer_bot() -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    await _attach_bale_token(shop_bot_id)
    shop_bot = await _shop_bot(shop_bot_id)

    from app.services.bot_manager import ShopBotManager

    manager = ShopBotManager(_DispatcherStub())
    started: list[tuple[int, bool]] = []

    async def _no_poll(shop_id, bot, *, bale=False) -> None:  # حلقه‌یِ pollingِ واقعی در تست اجرا نمی‌شود
        started.append((shop_id, bale))

    manager._poll = _no_poll  # type: ignore[method-assign]
    built: list[object] = []
    original_build = bale_bot_service.build_bot
    bale_bot_service.build_bot = lambda token: _built_bot(built)  # type: ignore[assignment]
    telegram_bot = make_shop_bot(f"{SHOP_BOT_TG_ID}:FAKE_TG")
    manager._bots[shop_bot_id] = telegram_bot
    try:
        await manager.register_bale(shop_bot)
        await asyncio.sleep(0)  # تسکِ polling در اولین گردشِ event loop اجرا می‌شود
        assert manager.registered_bale_bot_ids() == [shop_bot_id]
        assert started == [(shop_bot_id, True)], f"اتصالِ بله باید با فلگِ bale شروع شود: {started}"
        assert manager.get_bale_bot(shop_bot_id) is built[0]
        assert manager.customer_bot(shop_bot_id, platform_service.BALE) is built[0]
        assert manager.customer_bot(shop_bot_id, platform_service.TELEGRAM) is telegram_bot
        assert manager.customer_bot(shop_bot_id, None) is telegram_bot

        shop_bot.bale_bot_enabled = False
        await manager.register_bale(shop_bot)
        assert manager.registered_bale_bot_ids() == [], "خاموش ⇒ اتصالِ کهنه هم بسته می‌شود"

        shop_bot.bale_bot_enabled = True
        await manager.register_bale(shop_bot)
        assert manager.registered_bale_bot_ids() == [shop_bot_id]
        assert len(built) == 2, "ثبتِ دوباره ⇒ اتصالِ تازه"

        shop_bot.bale_encrypted_token = None
        await manager.register_bale(shop_bot)
        assert manager.registered_bale_bot_ids() == []

        await manager.register_bale(await _shop_bot(shop_bot_id))
        await manager.unregister_bale(shop_bot_id)
        assert manager.registered_bale_bot_ids() == [] and manager.get_bale_bot(shop_bot_id) is None
    finally:
        bale_bot_service.build_bot = original_build
        manager._bots.pop(shop_bot_id, None)
    print("✅ test_manager_bale_transport_and_customer_bot PASSED")


class _DispatcherStub:
    def resolve_used_update_types(self) -> list[str]:
        return []


def _built_bot(box: list):
    bot = _bale_bot(f"{BALE_BOT_ID}:FAKE_TG")
    box.append(bot)
    return bot


# ============================================================================= ۵ — پیامِ همگانی روی پلتفرمِ درست
async def test_broadcast_routes_by_platform() -> None:
    class _SendBot:
        def __init__(self, name: str, recorder: list) -> None:
            self.name = name
            self.recorder = recorder

        async def send_message(self, chat_id: int, text: str, **_kwargs):
            self.recorder.append((self.name, chat_id))

    sent: list[tuple[str, int]] = []
    manager = _RecordingManager({platform_service.TELEGRAM: _SendBot("telegram", sent)})
    main_bot = make_shop_bot("000000:MAIN_FAKE")

    pace = panel_handlers.CUSTOMER_BROADCAST_PACE_SECONDS
    panel_handlers.CUSTOMER_BROADCAST_PACE_SECONDS = 0.0
    try:
        await panel_handlers._run_customer_broadcast(
            manager, 7, [(101, "telegram"), (102, "bale"), (103, "telegram")], "سلام", main_bot, 555
        )
    finally:
        panel_handlers.CUSTOMER_BROADCAST_PACE_SECONDS = pace
    assert sent == [("telegram", 101), ("telegram", 103)], f"گیرنده‌یِ بی‌اتصال باید رد شود، نه اشتباه فرستاده: {sent}"
    summary = main_bot.session.sent_messages[-1]
    assert summary["chat_id"] == 555 and summary["text"].startswith("✅"), summary
    print("✅ test_broadcast_routes_by_platform PASSED")


# ============================================================================= ۶ — رونمایی/پنهان از پنلِ ادمین
async def test_admin_reveal_and_hide(main_dp, bot_manager) -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    await _attach_bale_token(shop_bot_id)
    calls: list[str] = []

    async def fake_register(shop_bot):
        calls.append(f"register:{shop_bot.id}")
        bot_manager._bale_bots[shop_bot.id] = object()  # جایِ اتصالِ واقعی، فقط برایِ ردیابیِ حذف

    async def fake_unregister(shop_id):
        calls.append(f"unregister:{shop_id}")
        bot_manager._bale_bots.pop(shop_id, None)

    bot_manager.register_bale = fake_register  # type: ignore[method-assign]
    bot_manager.unregister_bale = fake_unregister  # type: ignore[method-assign]

    admin = Chat(main_dp, ADMIN_TG_ID)
    await admin.tap("admin_toggle_bale_bots")
    assert await _flag() is True
    assert calls == [f"register:{shop_bot_id}"], f"فروشگاهِ آماده باید بی‌درنگ وصل شود: {calls}"
    async with session_scope() as session:
        entries = list(
            (
                await session.execute(
                    select(AuditLogEntry).where(AuditLogEntry.event_type == AuditEventType.KILL_SWITCH_TOGGLED.value)
                )
            )
            .scalars()
            .all()
        )
    assert any("bale_shop_bots_enabled -> True" in (e.details or "") for e in entries), entries

    with_bale = keyboards.shop_owner_panel_keyboard("sales", bale_visible=True)
    assert main_texts.BALE_SHOP_BOT_BUTTON in {b.text for row in with_bale.keyboard for b in row}
    without = keyboards.shop_owner_panel_keyboard("sales", bale_visible=False)
    assert main_texts.BALE_SHOP_BOT_BUTTON not in {b.text for row in without.keyboard for b in row}

    owner = Chat(main_dp, OWNER_TG_ID)
    await owner.say(main_texts.BALE_SHOP_BOT_BUTTON)
    assert "رباتِ بله‌یِ فروشگاه" in owner.last_text, owner.last_text

    await admin.tap("admin_toggle_bale_bots")
    assert await _flag() is False
    assert calls == [f"register:{shop_bot_id}", f"unregister:{shop_bot_id}"], calls
    await owner.say(main_texts.BALE_SHOP_BOT_BUTTON)
    assert owner.last_text == main_texts.BALE_SHOP_BOT_UNAVAILABLE, "پنهان ⇒ حتی با دکمه‌یِ باز هم توکن ثبت نمی‌شود"
    print("✅ test_admin_reveal_and_hide PASSED")


# ============================================================================= ۷ — ثبتِ توکن از پنلِ فروشگاه‌دار
async def test_owner_bale_token_flow(main_dp, bot_manager) -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    second = await seed_usable_shop(OTHER_OWNER_TG_ID, OTHER_SHOP_BOT_TG_ID)
    await _set_flag(True)
    calls: list[str] = []

    async def fake_register(shop_bot):
        calls.append(f"register:{shop_bot.id}")

    async def fake_unregister(shop_id):
        calls.append(f"unregister:{shop_id}")

    bot_manager.register_bale = fake_register  # type: ignore[method-assign]
    bot_manager.unregister_bale = fake_unregister  # type: ignore[method-assign]

    async def fake_get_me(token: str) -> dict:
        return dict(BALE_IDENTITY)

    original_get_me = bale_service.get_me
    bale_service.get_me = fake_get_me  # type: ignore[assignment]
    try:
        owner = Chat(main_dp, OWNER_TG_ID)
        await owner.say(main_texts.BALE_SHOP_BOT_BUTTON)
        assert "رباتِ بله‌یِ فروشگاه" in owner.last_text and "هنوز توکنی ثبت نکردی" in owner.last_text, owner.last_text
        data = _callback_data(owner.last_markup)
        assert "bale_edit" in data and "bale_back" in data, data

        await owner.tap("bale_edit")
        assert owner.last_text == main_texts.ASK_BALE_SHOP_BOT_TOKEN
        await owner.say("x")
        assert owner.last_text == main_texts.BALE_SHOP_BOT_TOKEN_INVALID_FORMAT, "ورودیِ بد state را نگه می‌دارد"

        await owner.say(FAKE_BALE_TOKEN)
        assert main_texts.BALE_SHOP_BOT_SAVED in [m["text"] for m in owner.sent], owner.sent[-3:]
        assert calls == [f"register:{shop_bot_id}"], calls
        assert FAKE_BALE_TOKEN not in " ".join(m["text"] for m in owner.sent), "توکنِ خام هیچ‌جا چاپ نمی‌شود"

        row = await _shop_bot(shop_bot_id)
        assert row.bale_bot_id == BALE_BOT_ID and row.bale_bot_username == "my_shop_bale"
        assert row.bale_encrypted_token == FAKE_BALE_TOKEN, "ستونِ رمزنگاری‌شده شفاف خوانده می‌شود"
        async with session_scope() as session:
            raw = await session.scalar(sql_text("SELECT bale_encrypted_token FROM shop_bots WHERE id = :i"), {"i": shop_bot_id})
        assert raw and FAKE_BALE_TOKEN not in str(raw), "در دیتابیس فقط رمز ذخیره می‌شود"
        assert decrypt_token(str(raw)) == FAKE_BALE_TOKEN
        assert "@my_shop_bale" in owner.sent[-1]["text"], owner.sent[-1]

        # همان رباتِ بله برایِ فروشگاهِ دیگر ⇒ رد (بدونِ نوشتنِ توکن)
        other_owner = Chat(main_dp, OTHER_OWNER_TG_ID)
        await other_owner.say(main_texts.BALE_SHOP_BOT_BUTTON)
        await other_owner.tap("bale_edit")
        await other_owner.say(FAKE_BALE_TOKEN)
        assert main_texts.BALE_SHOP_BOT_ALREADY_USED in [m["text"] for m in other_owner.sent], other_owner.sent[-3:]
        assert (await _shop_bot(second)).bale_bot_id is None
        assert calls == [f"register:{shop_bot_id}"], calls

        # خاموش/روشن از همان صفحه
        await owner.say(main_texts.BALE_SHOP_BOT_BUTTON)
        await owner.tap("bale_off")
        assert (await _shop_bot(shop_bot_id)).bale_bot_enabled is False
        assert calls[-1] == f"unregister:{shop_bot_id}", calls
        await owner.say(main_texts.BALE_SHOP_BOT_BUTTON)
        assert "خاموش ⏸" in owner.last_text, owner.last_text
        await owner.tap("bale_on")
        assert (await _shop_bot(shop_bot_id)).bale_bot_enabled is True
        assert calls[-1] == f"register:{shop_bot_id}", calls

        # حذف ⇒ توکن و شناسه پاک، اتصال بسته؛ تلگرام دست‌نخورده
        await owner.say(main_texts.BALE_SHOP_BOT_BUTTON)
        await owner.tap("bale_clear")
        row = await _shop_bot(shop_bot_id)
        assert row.bale_encrypted_token is None and row.bale_bot_id is None and row.bale_bot_username is None
        assert calls[-1] == f"unregister:{shop_bot_id}", calls
        assert row.bot_telegram_id == SHOP_BOT_TG_ID and row.encrypted_token
        await owner.say(main_texts.BALE_SHOP_BOT_BUTTON)
        data = _callback_data(owner.last_markup)
        assert "bale_edit" in data and "bale_clear" not in data, data

        await owner.tap("bale_back")
        assert main_texts.BALE_SHOP_BOT_BUTTON in {b.text for row in owner.last_markup.keyboard for b in row}, "دکمه برمی‌گردد"
    finally:
        bale_service.get_me = original_get_me
    print("✅ test_owner_bale_token_flow PASSED")


def _callback_data(markup) -> list[str]:
    if markup is None:
        return []
    return [b.callback_data for row in markup.inline_keyboard for b in row if b.callback_data]


# ============================================================================= ۸ — فروشگاهِ بدونِ ربات
async def test_owner_without_shop_bot(main_dp) -> None:
    await reset_database()
    await _set_flag(True)
    stranger_id = 999_981
    async with session_scope() as session:
        await shop_owner_service.get_or_create_shop_owner(session, stranger_id)
    stranger = Chat(main_dp, stranger_id)
    await stranger.say(main_texts.BALE_SHOP_BOT_BUTTON)
    assert stranger.last_text == main_texts.SHOP_BOT_NOT_SET_UP, stranger.last_text
    print("✅ test_owner_without_shop_bot PASSED")


async def main() -> None:
    main_dp, _shop_dp, bot_manager, _main_bot = build_test_dispatchers()
    await test_token_and_flag_rules()
    await test_platform_marker_and_shop_resolution()
    await test_customer_identity_is_per_platform()
    await test_manager_bale_transport_and_customer_bot()
    await test_broadcast_routes_by_platform()
    await test_admin_reveal_and_hide(main_dp, bot_manager)
    await test_owner_bale_token_flow(main_dp, bot_manager)
    await test_owner_without_shop_bot(main_dp)


if __name__ == "__main__":
    asyncio.run(main())
