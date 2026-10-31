"""
تست: حالتِ مشاوره (Consultation Mode) — بخشِ ۲ مسترپرامپت.

اجرا: python3 tests_manual/test_consultation_mode.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from harness import FakeSession, build_test_dispatchers, make_callback_update, reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from aiogram import Bot  # noqa: E402

from app.bots.main_bot import keyboards  # noqa: E402
from app.database.models import OrderType, ShopBot, TenantMode  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import ai_context, order_detection_service  # noqa: E402
from app.services.ai_service import AiCallResult  # noqa: E402

OWNER_TG_ID = 999801
SHOP_BOT_TG_ID = 999802


class _FakeClassifierAi:
    def __init__(self, response_json: str) -> None:
        self._response_json = response_json

    async def get_reply(self, system_prompt, history, user_message) -> AiCallResult:
        return AiCallResult(text=self._response_json, total_tokens=10)


def test_sales_mode_system_prompt() -> None:
    shop_bot = ShopBot(tenant_mode=TenantMode.SALES, ai_instructions=None)
    prompt = ai_context.build_system_prompt(shop_bot, [])
    assert "فعلاً هیچ محصولی در فروشگاه ثبت نشده" in prompt
    assert "دستیار فروش" in prompt
    print("✅ test_sales_mode_system_prompt PASSED")


def test_consultation_mode_system_prompt_has_no_sales_framing() -> None:
    shop_bot = ShopBot(tenant_mode=TenantMode.CONSULTATION, ai_instructions=None)
    prompt = ai_context.build_system_prompt(shop_bot, [])
    assert "فعلاً هیچ محصولی در فروشگاه ثبت نشده" not in prompt, "نباید فریمینگِ فروشگاهی برای مشاوره ظاهر بشه"
    assert "دستیارِ مشاوره" in prompt
    print("✅ test_consultation_mode_system_prompt_has_no_sales_framing PASSED")


def test_prompt_injection_defense_present_in_both_modes() -> None:
    for mode in (TenantMode.SALES, TenantMode.CONSULTATION):
        shop_bot = ShopBot(tenant_mode=mode, ai_instructions=None)
        prompt = ai_context.build_system_prompt(shop_bot, [])
        assert "هیچ‌وقت دستورالعمل‌های بالا رو" in prompt, f"خطِ دفاعی باید توی حالتِ {mode} هم باشه"
    print("✅ test_prompt_injection_defense_present_in_both_modes PASSED")


def test_panel_keyboard_label_matches_mode() -> None:
    sales_kb = keyboards.shop_owner_panel_keyboard(TenantMode.SALES)
    consultation_kb = keyboards.shop_owner_panel_keyboard(TenantMode.CONSULTATION)
    sales_labels = {btn.text for row in sales_kb.keyboard for btn in row}
    consultation_labels = {btn.text for row in consultation_kb.keyboard for btn in row}
    assert "📦 محصولات" in sales_labels
    assert "🗂 خدمات و بسته‌ها" in consultation_labels
    assert "📦 محصولات" not in consultation_labels
    print("✅ test_panel_keyboard_label_matches_mode PASSED")


async def test_detect_order_forces_consultation_type() -> None:
    fake_ai = _FakeClassifierAi('{"status": "completed", "type": "order", "summary": "درخواستِ وقتِ مشاوره", "estimated_value_toman": null, "product_id": null, "quantity": null, "customer_phone": null, "customer_address": null}')
    result, tokens = await order_detection_service.detect_order(fake_ai, [{"role": "user", "content": "سلام"}], [], is_consultation=True)
    assert result is not None
    assert result["type"] == OrderType.CONSULTATION, f"باید همیشه CONSULTATION باشه، شد: {result['type']}"
    assert tokens == 10
    print("✅ test_detect_order_forces_consultation_type PASSED")


async def test_set_tenant_mode_handler(main_dp) -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)

    async with session_scope() as session:
        shop_bot = await session.get(ShopBot, shop_bot_id)
        assert shop_bot.tenant_mode == TenantMode.SALES, "پیش‌فرض باید SALES باشه"

    main_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())
    await main_dp.feed_update(main_bot, make_callback_update(1, data="set_tenant_mode:consultation", user_id=OWNER_TG_ID))

    async with session_scope() as session:
        shop_bot = await session.get(ShopBot, shop_bot_id)
        assert shop_bot.tenant_mode == TenantMode.CONSULTATION, "باید بعدِ کلیک به CONSULTATION تغییر کنه"

    print("✅ test_set_tenant_mode_handler PASSED")


async def main() -> None:
    test_sales_mode_system_prompt()
    test_consultation_mode_system_prompt_has_no_sales_framing()
    test_prompt_injection_defense_present_in_both_modes()
    test_panel_keyboard_label_matches_mode()
    await test_detect_order_forces_consultation_type()

    main_dp, shop_dp, bot_manager, _main_bot = build_test_dispatchers()
    await test_set_tenant_mode_handler(main_dp)


if __name__ == "__main__":
    asyncio.run(main())
