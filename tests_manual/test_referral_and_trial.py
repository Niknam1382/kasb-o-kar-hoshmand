"""
تست: قابلیتِ #1 (یادآوریِ آزمایشی با لینکِ کانال) + قابلیتِ #3 (پورسانتِ
معرف، وقتی زیرِمجموعه‌ش اولین پرداختش رو تایید می‌کنه).

مدلِ پاداش عوض شده: قبلاً یه مبلغِ *ثابت* به *هر دو طرف* بود (قابلِ‌سوءاستفاده
با حساب‌های فیک)؛ الان فقط معرف، درصدی (پیش‌فرض ٪۱۰) از مبلغِ واقعیِ اولین
شارژِ زیرمجموعه‌ش رو می‌گیره.

اجرا: python3 tests_manual/test_referral_and_trial.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402

from harness import FakeSession, build_test_dispatchers, make_message_update, reset_database  # noqa: E402

from app.bots.main_bot import texts  # noqa: E402
from app.database.models import PaymentPurpose  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import payment_service, shop_owner_service  # noqa: E402
from app.services.admin_settings_service import get_admin_settings  # noqa: E402

REFERRER_TG_ID = 999801
REFERRED_TG_ID = 999802


def test_trial_offer_includes_channel_link_when_set() -> None:
    text_with_link = texts.trial_offer_text("https://t.me/kasbokar_channel")
    assert "https://t.me/kasbokar_channel" in text_with_link, "لینکِ کانال باید توی متنِ پیشنهادِ آزمایشی باشه"

    text_without_link = texts.trial_offer_text(None)
    assert "https://t.me/kasbokar_channel" not in text_without_link, "بدونِ تنظیمِ لینک، نباید لینکی توی متن باشه"
    assert len(text_without_link) > 0, "حتی بدونِ لینک، متن نباید خالی باشه"

    print("✅ test_trial_offer_includes_channel_link_when_set PASSED")


async def _seed_referrer_and_referred(main_dp) -> tuple[int, int]:
    admin_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())

    await main_dp.feed_update(admin_bot, make_message_update(1, text="/start", user_id=REFERRER_TG_ID))
    await main_dp.feed_update(admin_bot, make_message_update(2, text="معرف", user_id=REFERRER_TG_ID))
    await main_dp.feed_update(admin_bot, make_message_update(3, text="اول", user_id=REFERRER_TG_ID))
    await main_dp.feed_update(admin_bot, make_message_update(4, text="09121111111", user_id=REFERRER_TG_ID))
    await main_dp.feed_update(admin_bot, make_message_update(5, text="referrer@example.com", user_id=REFERRER_TG_ID))

    async with session_scope() as session:
        referrer = await shop_owner_service.get_by_telegram_id(session, REFERRER_TG_ID)
        referral_code = referrer.referral_code
        referrer_id = referrer.id

    await main_dp.feed_update(admin_bot, make_message_update(10, text=f"/start {referral_code}", user_id=REFERRED_TG_ID))
    await main_dp.feed_update(admin_bot, make_message_update(11, text="زیرمجموعه", user_id=REFERRED_TG_ID))
    await main_dp.feed_update(admin_bot, make_message_update(12, text="دوم", user_id=REFERRED_TG_ID))
    await main_dp.feed_update(admin_bot, make_message_update(13, text="09122222222", user_id=REFERRED_TG_ID))
    await main_dp.feed_update(admin_bot, make_message_update(14, text="referred@example.com", user_id=REFERRED_TG_ID))

    async with session_scope() as session:
        referred = await shop_owner_service.get_by_telegram_id(session, REFERRED_TG_ID)
        return referrer_id, referred.id


async def test_referrer_gets_percentage_of_first_payment(main_dp) -> None:
    await reset_database()
    referrer_id, referred_id = await _seed_referrer_and_referred(main_dp)

    async with session_scope() as session:
        admin_settings = await get_admin_settings(session)
        admin_settings.referral_reward_value = 10  # ٪۱۰

        referred = await shop_owner_service.get_by_id(session, referred_id)
        assert referred.wallet_balance_toman == 0
        payment = await payment_service.create_card_to_card_payment(
            session, referred, 300_000, None, purpose=PaymentPurpose.WALLET_TOPUP
        )
        payment_id, expected_topup = payment.id, payment.final_amount

    expected_reward = round(expected_topup * 10 / 100)  # ٪۱۰ از ۳۰۰٬۰۰۰ = ۳۰٬۰۰۰

    async with session_scope() as session:
        payment = await payment_service.get_by_id(session, payment_id)
        _effect, reward_info = await payment_service.approve_payment(session, payment, 12345)
        assert reward_info is not None, "برای اولین پرداختِ زیرمجموعه، معرف باید پورسانت بگیره"
        assert reward_info["amount_toman"] == expected_reward, f"باید {expected_reward} تومن باشه، نه {reward_info['amount_toman']}"
        assert reward_info["referrer_telegram_id"] == REFERRER_TG_ID
        assert "referred_telegram_id" not in reward_info, "دیگه نباید به معرفی‌شده هم پاداشِ جدا بدیم"

        referrer = await shop_owner_service.get_by_id(session, referrer_id)
        assert referrer.wallet_balance_toman == expected_reward, (
            f"معرف باید {expected_reward} تومن پورسانت بگیره، نه {referrer.wallet_balance_toman}"
        )

        # معرفی‌شده فقط همون مبلغِ شارژِ خودش رو داره — دیگه پاداشِ اضافه نمی‌گیره
        referred = await shop_owner_service.get_by_id(session, referred_id)
        assert referred.wallet_balance_toman == expected_topup, (
            f"معرفی‌شده فقط باید مبلغِ شارژِ خودش ({expected_topup}) رو داشته باشه، نه {referred.wallet_balance_toman}"
        )

    print("✅ test_referrer_gets_percentage_of_first_payment PASSED")


async def test_second_payment_does_not_trigger_reward_again(main_dp) -> None:
    await reset_database()
    referrer_id, referred_id = await _seed_referrer_and_referred(main_dp)

    async with session_scope() as session:
        referred = await shop_owner_service.get_by_id(session, referred_id)
        payment1 = await payment_service.create_card_to_card_payment(
            session, referred, 300_000, None, purpose=PaymentPurpose.WALLET_TOPUP
        )
        payment1_id = payment1.id

    async with session_scope() as session:
        payment1 = await payment_service.get_by_id(session, payment1_id)
        await payment_service.approve_payment(session, payment1, 12345)

    async with session_scope() as session:
        referred = await shop_owner_service.get_by_id(session, referred_id)
        payment2 = await payment_service.create_card_to_card_payment(
            session, referred, 300_000, None, purpose=PaymentPurpose.WALLET_TOPUP
        )
        payment2_id = payment2.id

    async with session_scope() as session:
        payment2 = await payment_service.get_by_id(session, payment2_id)
        _effect, reward_info = await payment_service.approve_payment(session, payment2, 12345)
        assert reward_info is None, "برای پرداختِ دومِ به‌بعد نباید دوباره پورسانتی داده بشه"

    print("✅ test_second_payment_does_not_trigger_reward_again PASSED")


async def test_zero_percent_disables_referral_reward(main_dp) -> None:
    await reset_database()
    referrer_id, referred_id = await _seed_referrer_and_referred(main_dp)

    async with session_scope() as session:
        admin_settings = await get_admin_settings(session)
        admin_settings.referral_reward_value = 0

        referred = await shop_owner_service.get_by_id(session, referred_id)
        payment = await payment_service.create_card_to_card_payment(
            session, referred, 300_000, None, purpose=PaymentPurpose.WALLET_TOPUP
        )
        payment_id = payment.id

    async with session_scope() as session:
        payment = await payment_service.get_by_id(session, payment_id)
        _effect, reward_info = await payment_service.approve_payment(session, payment, 12345)
        assert reward_info is None, "با درصدِ صفر، نباید پورسانتی داده بشه"

    print("✅ test_zero_percent_disables_referral_reward PASSED")


async def main() -> None:
    test_trial_offer_includes_channel_link_when_set()
    main_dp, shop_dp, bot_manager, main_bot = build_test_dispatchers()
    await test_referrer_gets_percentage_of_first_payment(main_dp)
    await test_second_payment_does_not_trigger_reward_again(main_dp)
    await test_zero_percent_disables_referral_reward(main_dp)


if __name__ == "__main__":
    asyncio.run(main())
