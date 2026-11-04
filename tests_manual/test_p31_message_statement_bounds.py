"""
تست: P31-A — سقفِ تعدادِ statementهایِ مسیرِ یکِ پیامِ مشتری

پیش ازِ این رفع (MEASURED با `scripts/scale_probe.py` رویِ مسیرِ شبیه‌سازی‌شده): **۱۲٫۰**
statement به‌ازایِ هر پیام، که دو تا از آن‌ها بی‌مصرف بود:
  · `UPDATE shop_owners SET wallet_balance_toman=$1` بی‌درنگ بعد ازِ
    `UPDATE … greatest(...)` رویِ *همان* سطر (ORM مقدارِ بازگشتیِ RETURNING را «تغییرکرده»
    علامت می‌زد و flush دوباره همان عدد را می‌نوشت)
  · `SELECT admin_settings` سه‌بار برایِ یکِ پیام (میدل‌ور، تسکِ پاسخِ AI، تسکِ تشخیصِ سفارش)
    و شش‌بار در هر پاسِ جاب

سه چیزی که این فایل قفل می‌کند:
  ۱. سقفِ statementهایِ یکِ پیام (رگرسیونِ عددیِ مسیرِ واقعی، نه شبیه‌سازی)
  ۲. پیامِ دوم نباید دوباره سطرِ تنظیمات را بخواند (کشِ خواندن کار می‌کند)
  ۳. نوشتنِ یکِ تنظیم بلافاصله دیده می‌شود (باطل‌سازیِ رویداد-محور، نه صبرکردنِ TTL) — وگرنه
     «حالتِ تعمیر» تا دو ثانیه بی‌اثر می‌ماند و این برایِ کلیدِ خاموش‌کننده قابلِ قبول نیست

اجرا: python3 tests_manual/run_one.py test_p31_message_statement_bounds.py
"""
from __future__ import annotations

import asyncio
import contextlib
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402
from sqlalchemy import event  # noqa: E402

from harness import FakeSession, build_test_dispatchers, make_message_update, reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.database.session import engine, session_scope  # noqa: E402
from app.services import admin_settings_service, ai_service  # noqa: E402
from app.services.admin_settings_service import cached_admin_settings, update_setting  # noqa: E402
from app.services.ai_service import AiCallResult  # noqa: E402

OWNER_TG_ID = 999331
SHOP_BOT_TG_ID = 999332
CUSTOMER_TG_ID = 999333

# سقفِ statementهایِ یکِ پیامِ تنها: ۳۰ پیش ازِ P33-D (MEASURED)، ۲۹ بعد ازِ پاس‌دادنِ
# شناسۀ مشتری از میدل‌ور به تسکِ پاسخ. عددِ سنجیده‌شده با همین تست، نه برآورد.
MAX_STATEMENTS_PER_MESSAGE = 29
MAINTENANCE_WORD = "به‌روزرسانی"


class _FakeAi:
    async def get_reply(self, system_prompt, history, user_message) -> AiCallResult:
        return AiCallResult(text="پاسخِ آزمایشی", total_tokens=10)

    async def analyze_image(self, prompt, image_bytes, mime_type="image/jpeg") -> AiCallResult:
        return AiCallResult(text="تحلیلِ آزمایشی", total_tokens=10)

    async def transcribe_audio(self, audio_bytes, filename="voice.ogg") -> str:
        return "متنِ آزمایشی"


@contextlib.contextmanager
def _counted():
    """شمارندهٔ statement رویِ same engine؛ الگویِ test_p29_job_query_bounds (لیستِ محلی)."""
    seen: list[str] = []

    def _listener(_conn, _cursor, statement, _params, _context, _executemany):
        seen.append(" ".join(statement.split()))

    event.listen(engine.sync_engine, "before_cursor_execute", _listener)
    try:
        yield seen
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", _listener)


def _patch_ai() -> object:
    original = ai_service.get_ai_service
    ai_service.get_ai_service = lambda *args, **kwargs: _FakeAi()
    return original


def _shop_bot() -> Bot:
    return Bot(token=f"{SHOP_BOT_TG_ID}:FAKE", session=FakeSession())


async def test_one_message_stays_under_the_bound(shop_dp) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    admin_settings_service.reset_read_cache()
    original = _patch_ai()
    try:
        with _counted() as seen:
            await shop_dp.feed_update(_shop_bot(), make_message_update(1, text="سلام", user_id=CUSTOMER_TG_ID))
            await asyncio.sleep(4.5)
        # P31-A: هر کسرِ موجودی باید *یک* UPDATE رویِ سطرِ owner بزند (فرمِ عبارتِ ستونی).
        # فرمِ ساده‌ی `SET wallet_balance_toman=$1` همان نویسهٔ کثیفِ ORM بود که دوباره
        # همان عدد را می‌نوشت. تعدادِ UPDATEهایِ عبارت‌محور برابرِ تعدادِ کسرهایِ مجاز است
        # (چت + تشخیصِ سفارش)، پس آن را نمی‌شماریم.
        plain_owner_writes = [s for s in seen if s.startswith("UPDATE shop_owners SET wallet_balance_toman=$1")]
        assert len(seen) <= MAX_STATEMENTS_PER_MESSAGE, f"{len(seen)} statement برایِ یکِ پیام: {seen}"
        assert not plain_owner_writes, f"UPDATEِ تکراریِ همان عدد رویِ سطرِ owner برگشته: {plain_owner_writes}"
        print(f"✅ test_one_message_stays_under_the_bound PASSED (count={len(seen)})")
    finally:
        ai_service.get_ai_service = original


async def test_second_message_reuses_the_settings_cache(shop_dp) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID + 1, SHOP_BOT_TG_ID + 1)
    admin_settings_service.reset_read_cache()
    original = _patch_ai()
    try:
        bot = _shop_bot()
        customer = CUSTOMER_TG_ID + 1
        # پیامِ اول: کشِ خواندن پر می‌شود
        await shop_dp.feed_update(bot, make_message_update(1, text="سلام", user_id=customer))
        await asyncio.sleep(4.5)
        with _counted() as seen:
            await shop_dp.feed_update(bot, make_message_update(2, text="قیمت؟", user_id=customer))
            await asyncio.sleep(4.5)
        reads = [s for s in seen if "FROM admin_settings" in s]
        assert not reads, f"پیامِ دوم نباید سطرِ تنظیمات را دوباره بخواند؛ دیده شد {len(reads)}"
        print("✅ test_second_message_reuses_the_settings_cache PASSED")
    finally:
        ai_service.get_ai_service = original


async def test_settings_write_is_visible_without_waiting_for_ttl() -> None:
    """گرانِ پولیِ این کش: نوشتن باید همان لحظه دیده شود، نه بعد ازِ TTL."""
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID + 2, SHOP_BOT_TG_ID + 2)
    async with session_scope() as session:
        first = await cached_admin_settings(session)
        assert first.maintenance_mode is False

    async with session_scope() as session:
        await update_setting(session, "maintenance_mode", True)
        await session.commit()

    async with session_scope() as session:
        after_write = await cached_admin_settings(session)
        assert after_write.maintenance_mode is True, "نوشتن باید کشِ خواندن را باطل کرده باشد"

    async with session_scope() as session:
        await update_setting(session, "maintenance_mode", False)
        await session.commit()

    # مسیرِ نوشتنِ بدونِ update_setting (هندلرهایِ پنل این‌طور می‌نویسند) هم باید باطل کند
    async with session_scope() as session:
        row = await admin_settings_service.get_admin_settings(session)
        row.maintenance_mode = True
        await session.commit()
    async with session_scope() as session:
        assert (await cached_admin_settings(session)).maintenance_mode is True, "flushِ مستقیم هم باید کش را باطل کند"
    async with session_scope() as session:
        await update_setting(session, "maintenance_mode", False)
        await session.commit()
    print("✅ test_settings_write_is_visible_without_waiting_for_ttl PASSED")


async def main() -> None:
    _main_dp, shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    await test_one_message_stays_under_the_bound(shop_dp)
    await test_second_message_reuses_the_settings_cache(shop_dp)
    await test_settings_write_is_visible_without_waiting_for_ttl()


if __name__ == "__main__":
    asyncio.run(main())
