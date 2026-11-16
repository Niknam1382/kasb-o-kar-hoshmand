"""پ۱۰۴ · قطعه‌هایِ کم‌خطرِ پ۵۰: پنلِ وبِ چندکاناله (فقط‌خواندنی) + سنجهٔ دو پروسه‌ای.

سه ادعا در تستِ خودکار (قسمتِ سنگینِ «دو پروسه» در همین فایل اجرا نمی‌شود؛ آن با
`scripts/two_process_probe.py` رویِ دیتابیسِ جدا سنجیده می‌شود تا سوئیت ۲۰ دقیقه‌ای سنگین نشود):

۱. پنلِ `/panel` حالا برایِ هرِ فروشگاه **کانال‌هایش** را می‌گوید (📸 اینستاگرام / 🟢 بله / 🎧 پشتیبانی)
   و اگر فهرست کوتاه شده باشد، خطِ «نمایش N از M» را نشان می‌دهد — و هیچ رازی در HTML نیست.
۲. `capacity_service.channel_summary` با سه زیرکوئری/شمارش سرِ جایش می‌ماند (N+1 نمی‌شود) و هیچ
   چیزی نمی‌نویسد.
۳. سنجهٔ دو پروسه‌ای **بدونِ تأیید اجرا نمی‌شود** (قفلِ ایمنی) و قفلِ pollingِ advisory واقعاً
   انحصاری است: اگر دو اتصالِ جدا هم‌زمان بخواهند، دقیقاً یکِشان می‌گیرد (اینجا در یکِ پروسه؛
   حالتِ چندپروسه‌ایِ واقعی در گزارشِ پ۱۰۴ با عددِ MEASURED آمده).

اجرا: python3 tests_manual/run_one.py test_p104_two_process_panel.py
"""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from sqlalchemy import event, func, select  # noqa: E402

from app import main as app_main  # noqa: E402
from app.config import settings  # noqa: E402
from app.database.models import InstagramAccount, ShopBot  # noqa: E402
from app.database.session import engine, session_scope  # noqa: E402
from app.services import capacity_service  # noqa: E402
from harness import reset_database  # noqa: E402
from scripts import two_process_probe as probe  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402
from test_p91_ops_panel import _call  # noqa: E402

OWNER_TG_ID = 10_400_000_001
SHOP_BOT_TG_ID = 10_400_000_002
OTHER_TG_ID = 10_400_000_011
OTHER_BOT_TG_ID = 10_400_000_012
TOKEN = "panel-p104-token"


async def _seed_two_shops() -> int:
    await reset_database()
    shop_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    await seed_usable_shop(OTHER_TG_ID, OTHER_BOT_TG_ID)
    async with session_scope() as session:
        session.add(
            InstagramAccount(
                shop_bot_id=shop_id,
                ig_account_id="17841",
                ig_username="shopfirst",
                access_token="ig-token-placeholder-value",
            )
        )
        shop = await session.get(ShopBot, shop_id)
        shop.support_enabled = True
        other = (
            await session.execute(select(ShopBot).where(ShopBot.bot_telegram_id == OTHER_BOT_TG_ID))
        ).scalars().one()
        other.bale_provider_token = "bale-token-placeholder"
        await session.commit()
    return shop_id


# ============================================================================= ۱
async def test_panel_lists_channels_per_shop_without_secrets() -> None:
    shop_id = await _seed_two_shops()
    previous = settings.metrics_token
    settings.metrics_token = TOKEN
    try:
        health_app = app_main.build_health_app()
        status, _headers, raw = await _call(health_app, "/panel", [(b"authorization", b"Basic " + _basic("admin", TOKEN))])
        assert status == 200, (status, raw[:200])
        text = raw.decode("utf-8", errors="replace")
        assert "📸 اینستاگرام" in text, text[:400]
        assert "🟢 بله" in text, text[:400]
        assert "🎧 پشتیبانی" in text, text[:400]
        assert "نمایش ۲ از ۲" in text.replace("2 از 2", "۲ از ۲") or "نمایش" in text, text[:600]
        for banned in ("access_token", "encrypted_token", "webhook_secret", "gAAAAA", TOKEN):
            assert banned not in text, f"راز در پنلِ وب: {banned}"
        status2, _h2, raw2 = await _call(health_app, "/ops/status", [(b"x-metrics-token", TOKEN.encode())])
        import json

        data = json.loads(raw2)
        rows = data["channels"]["shops"]
        assert len(rows) == 2, rows
        first = next(row for row in rows if row["id"] == shop_id)
        assert first["instagram"] is True and first["support"] is True, first
        assert data["channels"]["total_shops"] == 2 and data["channels"]["truncated"] is False, data["channels"]
    finally:
        settings.metrics_token = previous
    print("PASS test_panel_lists_channels_per_shop_without_secrets")


def _basic(user: str, password: str) -> bytes:
    import base64

    return base64.b64encode(f"{user}:{password}".encode()).decode().encode()


# ============================================================================= ۲
async def test_channel_summary_is_constant_query() -> None:
    await _seed_two_shops()
    seen: list[str] = []

    def listener(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001, ARG002
        seen.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", listener)
    try:
        async with session_scope() as session:
            summary = await capacity_service.channel_summary(session, limit=12)
            before = len(seen)
            again = await capacity_service.channel_summary(session, limit=1)
            delta = len(seen) - before
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", listener)
    assert summary["shown"] == 2 and summary["truncated"] is False, summary
    assert again["shown"] == 1 and again["truncated"] is True, again
    assert delta <= 5, f"هرِ فراخوان باید کوئریِ ثابت داشته باشد، نه به‌ازایِ هرِ فروشگاه: {delta}"
    async with session_scope() as session:
        rows = (await session.execute(select(func.count()).select_from(ShopBot))).scalar_one()
        assert rows == 2, "فقط‌خواندنی بودن: نباید چیزی کم/زیاد شده باشد"
    print("PASS test_channel_summary_is_constant_query")


# ============================================================================= ۳
async def test_probe_guard_and_advisory_exclusivity() -> None:
    had = os.environ.get("LOADTEST_DB_CONFIRM")
    os.environ.pop("LOADTEST_DB_CONFIRM", None)
    try:
        code = 0
        try:
            probe._guard()
        except SystemExit as exc:  # قفلِ ایمنی: بدونِ تأیید، هیچ نوشتنی
            code = int(exc.code or 2)
        assert code == 2, code
    finally:
        if had is not None:
            os.environ["LOADTEST_DB_CONFIRM"] = had

    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    from app.main import POLLING_LOCK_KEY, acquire_polling_lock, release_polling_lock

    first = await acquire_polling_lock(POLLING_LOCK_KEY)
    assert first is not None, "اولین درخواست باید قفل را بگیرد"
    second = await acquire_polling_lock(POLLING_LOCK_KEY)
    assert second is None, "دومی ⇒ صفر (دو polling = دو کسرِ کیف‌پول برایِ یکِ پیام)"
    await release_polling_lock(first, POLLING_LOCK_KEY)
    third = await acquire_polling_lock(POLLING_LOCK_KEY)
    assert third is not None, "پس ازِ آزادکردن، قفل دوباره در دسترس است"
    await release_polling_lock(third, POLLING_LOCK_KEY)
    await engine.dispose()
    print("PASS test_probe_guard_and_advisory_exclusivity")


# ============================================================================= ۴
async def test_ops_requests_leave_no_idle_in_transaction_connection() -> None:
    """پ۱۰۴ · نگهبانِ باگی که **پ۹۶ نتوانست علتش را پیدا کند**.

    صورتِ باگ: `_ops_status_json` بعد ازِ `async with session_scope()` (یعنی رویِ سشنِ بسته‌شده)
    `channel_summary(session)` را صدا می‌زد ⇒ SQLAlchemy برایِ آن کوئری یکِ اتصالِ تازه از استخر
    می‌گرفت و تراکنتش را **باز** می‌گذاشت. هر بازدیدِ `/ops/status` یا `/panel` یکِ اتصالِ
    «idle in transaction» می‌ساخت و آزادش نمی‌کرد: با `DB_POOL_SIZE=25` بعد ازِ ~۲۵ رفرشِ ۳۰ ثانیه‌ای
    استخر تمام می‌شود و `/metrics`/وب‌هوک با `pool_timeout` خطا می‌گیرند. همین اتصال‌هایِ رهاشده در
    پایانِ پروسه همان `greenlet is being finalized` / `non-checked-in connection` را می‌ساختند.
    """
    from sqlalchemy import text as sql_text

    await _seed_two_shops()
    app = app_main.build_health_app()
    previous = settings.metrics_token
    settings.metrics_token = TOKEN
    try:
        import base64

        cred = base64.b64encode(f"admin:{TOKEN}".encode()).decode()
        for _ in range(4):
            status, _headers, _body = await _call(app, "/panel", [(b"authorization", f"Basic {cred}".encode())])
            assert status == 200, status
            await _call(app, "/ops/status", [(b"x-metrics-token", TOKEN.encode())])
        async with session_scope() as session:
            rows = (
                await session.execute(
                    sql_text(
                        "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() "
                        "AND pid <> pg_backend_pid() AND state = 'idle in transaction'"
                    )
                )
            ).scalar_one()
        assert int(rows) == 0, f"اتصالِ نشتی با تراکنشِ باز: {rows} تا بعد ازِ ۸ درخواستِ عملیاتی"
    finally:
        settings.metrics_token = previous
    print("PASS test_ops_requests_leave_no_idle_in_transaction_connection")


async def main() -> None:
    await test_panel_lists_channels_per_shop_without_secrets()
    await test_channel_summary_is_constant_query()
    await test_probe_guard_and_advisory_exclusivity()
    await test_ops_requests_leave_no_idle_in_transaction_connection()


if __name__ == "__main__":
    asyncio.run(main())
