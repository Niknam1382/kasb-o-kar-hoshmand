"""پ۶۰ · خواستهٔ مالکِ محصول: هوشمندسازیِ اینستاگرامِ *خودِ هر فروشگاه* + متنِ سراسریِ ادمین.

سه ادعایِ اصلی:
۱. `instagram_service.instruction_directive` سه لایه را درست می‌چیند: متنِ سراسریِ ادمین،
   متنِ خودِ فروشگاه، و قاعدهٔ مود — و در مودِ مشاوره «قیمت/سبد/پرداخت» ممنوع می‌شود ولی
   پاسخِ سؤالات و کامنت آزاد می‌ماند.
۲. `ai_context.build_system_prompt` بدونِ `channel_directive` **بایت‌به‌بایت** مثلِ قبل است
   (یعنی مسیرِ تلگرام/بله هیچ تغییری نمی‌کند) و با آن، دستورِ کانال آخرِ پرامپت می‌نشیند.
۳. جریانِ واقعیِ پنلِ فروشگاه‌دار: دکمه ← پرسش ← ذخیره ← نمایشِ «دارد» ← «خالی» ← «ندارد»؛
   بدونِ اتصال یا با درِ سراسریِ خاموش، هیچ ورودی‌ای باز نمی‌شود.

اجرا: python3 tests_manual/run_one.py test_p60_instagram_panel.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from sqlalchemy import select  # noqa: E402
from harness import build_test_dispatchers, reset_database  # noqa: E402
from phase4_helpers import Chat, callbacks  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot import keyboards, texts  # noqa: E402
from app.bots.main_bot.handlers import instagram as instagram_handlers  # noqa: E402
from app.database.models import InstagramAccount, ShopBot, TenantMode  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import ai_context, instagram_service, shop_owner_service  # noqa: E402

OWNER_TG_ID = 995_901
SHOP_BOT_TG_ID = 995_902
CONSULT_OWNER_TG_ID = 995_903
CONSULT_SHOP_TG_ID = 995_904


async def _enable_channel(shop_owner_tg_id: int, consult_owner_tg_id: int) -> tuple[int, int]:
    """دو فروشگاه (فروشگاهی + مشاوره‌ای) با کانالِ اینستاگرامِ رونمایی‌شده و اتصالِ هرِ دو."""
    shop_a = await seed_usable_shop(shop_owner_tg_id, SHOP_BOT_TG_ID)
    shop_b = await seed_usable_shop(consult_owner_tg_id, CONSULT_SHOP_TG_ID)
    async with session_scope() as session:
        from app.services.admin_settings_service import get_admin_settings

        admin_settings = await get_admin_settings(session)
        admin_settings.instagram_enabled = True
        admin_settings.instagram_app_id = "1234567890"
        owner_b = await shop_owner_service.get_by_telegram_id(session, consult_owner_tg_id)
        await shop_owner_service.set_business_mode(session, owner_b, "consultation")
        for shop_bot_id in (shop_a, shop_b):
            session.add(
                InstagramAccount(
                    shop_bot_id=shop_bot_id,
                    ig_account_id=f"178414{shop_bot_id}",
                    ig_username="my.shop",
                    access_token="tok-123",
                    is_active=True,
                    auto_reply_dm=True,
                    auto_reply_comments=True,
                    private_reply_enabled=True,
                )
            )
        await session.flush()
    return shop_a, shop_b


async def test_instruction_directive_layers() -> None:
    class Account:
        instructions = None

    class Settings:
        instagram_platform_instructions = None

    class Bot:
        tenant_mode = TenantMode.SALES

    account, settings, bot = Account(), Settings(), Bot()
    only_mode = instagram_service.instruction_directive(account, settings, bot)
    assert only_mode and "حالتِ فروش" in only_mode, only_mode
    assert "حالتِ مشاوره" not in only_mode, only_mode

    settings.instagram_platform_instructions = "همیشه اسمِ برند را اولِ پیام بگذار"
    with_platform = instagram_service.instruction_directive(account, settings, bot)
    assert "دستورِ سراسریِ پلتفرم" in with_platform and "اسمِ برند" in with_platform, with_platform

    account.instructions = "سؤالاتِ ارسالِ رایگان را کوتاه جواب بده"
    both = instagram_service.instruction_directive(account, settings, bot)
    assert both.index("دستورِ سراسریِ پلتفرم") < both.index("دستورِ خودِ این فروشگاه") < both.index("قاعدهٔ کانالِ اینستاگرام"), both

    bot.tenant_mode = TenantMode.CONSULTATION
    consult = instagram_service.instruction_directive(account, settings, bot)
    assert "حالتِ مشاوره" in consult and "هیچ قیمتی اعلام نکن" in consult, consult
    assert "حالتِ فروش" not in consult, consult
    print("PASS test_instruction_directive_layers")


async def test_prompt_is_unchanged_without_channel_directive() -> None:
    class Bot:
        tenant_mode = TenantMode.SALES
        ai_instructions = None
        custom_ai_instructions = None

    shop_bot = Bot()
    before = ai_context.build_system_prompt(shop_bot, [])
    with_directive = ai_context.build_system_prompt(shop_bot, [], channel_directive="دستورِ کانالِ آزمایشی")
    assert with_directive.startswith(before), "پرامپتِ اصلی نباید عوض شود — دستورِ کانال فقط *اضافه* می‌شود"
    assert with_directive.endswith("دستورِ کانالِ آزمایشی"), with_directive[-60:]
    print("PASS test_prompt_is_unchanged_without_channel_directive")


async def test_owner_panel_instructions_flow(main_dp) -> None:
    await reset_database()
    await _enable_channel(OWNER_TG_ID, CONSULT_OWNER_TG_ID)
    owner = Chat(main_dp, OWNER_TG_ID)

    await owner.say(texts.INSTAGRAM_BUTTON)
    labels = [button.text for row in owner.last_markup.inline_keyboard for button in row]
    assert texts.INSTAGRAM_INSTRUCTIONS_BUTTON in labels, labels

    await owner.tap("ig_instructions")
    assert "چطور جواب بده" in owner.last_text, owner.last_text
    await owner.say("اگر کسی قیمت پرسید، اول مدل را بپرس بعد قیمت بگو")
    # پیامِ ذخیره و سپسِ صفحهٔ تازه (دو پیام پشتِ هم) ⇒ ادعا رویِ هرِ دو
    recent = " | ".join(row["text"] for row in owner.sent[-2:])
    assert texts.INSTAGRAM_INSTRUCTIONS_SAVED in recent, owner.sent[-2:]
    screen = owner.last_text
    assert "متنِ هوشمندسازیِ اینستاگرام: دارد" in screen, screen

    await owner.tap("ig_instructions")
    await owner.say("خالی")
    recent = " | ".join(row["text"] for row in owner.sent[-2:])
    assert texts.INSTAGRAM_INSTRUCTIONS_CLEARED in recent, owner.sent[-2:]
    assert "متنِ هوشمندسازیِ اینستاگرام: ندارد" in owner.last_text, owner.last_text

    await owner.tap("ig_instructions")
    await owner.say("الف" * 1600)
    assert texts.INSTAGRAM_INSTRUCTIONS_TOO_LONG in owner.last_text, owner.last_text[:120]
    print("PASS test_owner_panel_instructions_flow")


async def test_gates_on_connection_and_master_switch(main_dp) -> None:
    await reset_database()
    await _enable_channel(OWNER_TG_ID, CONSULT_OWNER_TG_ID)

    # فروشگاهِ بدونِ اتصال: همان گاردِ بقیهٔ فعل‌ها (کال‌بکِ ساختگی هم چیزی نمی‌سازد)
    plain_owner = Chat(main_dp, CONSULT_OWNER_TG_ID)
    await plain_owner.say(texts.INSTAGRAM_BUTTON)
    async with session_scope() as session:
        shop_bot = (await session.execute(select(ShopBot).where(ShopBot.bot_telegram_id == CONSULT_SHOP_TG_ID))).scalar_one()
        account = (await session.execute(select(InstagramAccount).where(InstagramAccount.shop_bot_id == shop_bot.id))).scalar_one()
        account_id = account.id
        await session.delete(account)
    await plain_owner.tap("ig_instructions")
    assert plain_owner.last_toast["text"] == texts.INSTAGRAM_NOT_CONNECTED, plain_owner.last_toast

    # درِ سراسریِ خاموش: هیچ ورودیِ تازه‌ای باز نمی‌شود
    async with session_scope() as session:
        from app.services.admin_settings_service import get_admin_settings

        admin_settings = await get_admin_settings(session)
        admin_settings.instagram_enabled = False
        await session.flush()
    await plain_owner.tap("ig_instructions")
    assert plain_owner.last_toast["text"] == texts.INSTAGRAM_TOGGLED_OFF, plain_owner.last_toast
    assert account_id is not None
    print("PASS test_gates_on_connection_and_master_switch")


async def test_keyboard_and_admin_label() -> None:
    class Account:
        auto_reply_dm = True
        auto_reply_comments = True
        private_reply_enabled = True
        instructions = "چیزی"

    labels = [button.text for row in keyboards.instagram_panel_keyboard(Account()).inline_keyboard for button in row]
    assert texts.INSTAGRAM_INSTRUCTIONS_BUTTON in labels, labels
    assert texts.INSTAGRAM_INSTRUCTIONS_BUTTON not in [
        button.text for row in keyboards.instagram_panel_keyboard(None).inline_keyboard for button in row
    ], "دکمهٔ متنِ هوشمندسازی نباید قبلِ اتصال دیده شود"

    # ردیفِ واقعیِ admin_settings (نه فیک): تابعِ برچسب‌ها ده‌ها صفت را می‌خواند و
    # محاسباتِ عددی هم دارد؛ فیکِ ناقص گمراه‌کننده می‌شد.
    async with session_scope() as session:
        from app.services.admin_settings_service import get_admin_settings

        admin_settings = await get_admin_settings(session)
        admin_settings.instagram_platform_instructions = "متنِ ادمین"
        await session.flush()
        entries = dict(texts.admin_settings_button_labels(admin_settings, group="instagram"))
        admin_settings.instagram_platform_instructions = None
        await session.flush()
    assert "instagram_platform_instructions" in entries, sorted(entries)
    assert "تنظیم‌شده" in entries["instagram_platform_instructions"], entries["instagram_platform_instructions"]
    assert texts.ADMIN_SETTING_GROUP["instagram_platform_instructions"] == "instagram"
    print("PASS test_keyboard_and_admin_label")


async def main() -> None:
    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    await test_instruction_directive_layers()
    await test_prompt_is_unchanged_without_channel_directive()
    await test_owner_panel_instructions_flow(main_dp)
    await test_gates_on_connection_and_master_switch(main_dp)
    await test_keyboard_and_admin_label()
    assert instagram_handlers.router is not None
    print("📊 نتیجه: ۵ تستِ پ۶۰ (هوشمندسازیِ اینستاگرامِ هر فروشگاه) پاس شد · لایه‌بندیِ دستور، بی‌تغییریِ پرامپتِ اصلی، جریانِ پنل، دروها، کیبورد و برچسبِ ادمین")


if __name__ == "__main__":
    asyncio.run(main())
