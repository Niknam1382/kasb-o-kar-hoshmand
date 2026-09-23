"""
کمک‌کننده‌ی مشترک: ساختِ یه فروشگاه‌دارِ کامل با موجودیِ کیف‌پول + ربات فروشگاهی،
برای تست‌هایی که نیاز به یه «فروشگاهِ قابل‌استفاده» دارن (debounce، عکس، صدا، ...).
"""
from __future__ import annotations

from app.database.models import WalletTransactionReason
from app.database.session import session_scope
from app.services import shop_bot_service, shop_owner_service, wallet_service
from app.services.admin_settings_service import get_admin_settings
from app.utils.encryption import encrypt_token

# مبلغِ بزرگ و گردی که برای تست‌ها کافیه و باعثِ ته‌کشیدنِ موجودی وسطِ تست نمی‌شه.
TEST_WALLET_BALANCE_TOMAN = 1_000_000


async def seed_usable_shop(
    owner_tg_id: int, bot_telegram_id: int, ai_api_key: str = "fake-test-ai-key", *, initial_balance_toman: int = TEST_WALLET_BALANCE_TOMAN
) -> int:
    """یه فروشگاه‌دارِ ثبت‌نام‌شده + موجودیِ کیف‌پول + ربات فروشگاهی می‌سازه و
    شناسه‌ی shop_bot رو برمی‌گردونه. ai_api_key هم توی admin_settings ست می‌شه تا
    چک‌های «آیا هوش مصنوعی تنظیم شده» رد بشن. initial_balance_toman رو می‌شه برای
    تست‌هایی که به یه موجودیِ خاص (مثلاً صفر یا خیلی کم) نیاز دارن override کرد."""
    async with session_scope() as session:
        owner = await shop_owner_service.get_or_create_shop_owner(session, owner_tg_id)
        owner = await shop_owner_service.complete_registration(
            session, owner, "فروشنده", "فعال", f"0912{owner_tg_id % 10_000_000:07d}", f"owner{owner_tg_id}@example.com", True, True
        )
        if initial_balance_toman > 0:
            await wallet_service.add_charge(session, owner, initial_balance_toman, reason=WalletTransactionReason.TOPUP)

        shop_bot = await shop_bot_service.upsert_shop_bot(session, owner, "fake-token", bot_telegram_id, f"shop_{bot_telegram_id}")
        shop_bot.encrypted_token = encrypt_token("fake-token")

        admin_settings = await get_admin_settings(session)
        admin_settings.ai_api_key = ai_api_key

        await session.flush()
        return shop_bot.id
