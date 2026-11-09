"""
تست: P44 · موردِ ۵۱ — «ماه» با انتخابِ ادمین + بکاپِ خودکارِ دیتابیس

۱. قاعدهٔ ماه: ۰ = تقویمی (با clampِ سرِ ماه)، ۳۰/۳۱ = روزشمارِ دقیقِ ۲۴ ساعته.
۲. فقط ردیفِ **تازه**: با عوض‌شدنِ تنظیم، شارژ و اشتراکِ تازه انقضایِ جدید می‌گیرند و ردیفِ
   قدیمی همان تاریخِ خودش را نگه می‌دارد (نه جلو، نه عقب) — خواستِ صریحِ مالکِ محصول.
۳. گزارشِ شبانه: عددِ پنجرهِ انقضا از متنِ ثابت نمی‌آید؛ `window_days` همان چیزی است که
   `wallet_service.EXPIRING_SOON_DAYS` می‌گوید.
۴. پنلِ ادمین: دستهٔ تازهٔ «🗄 بکاپ و نگهداریِ دیتابیس» + اعتبارِ ورودیِ ۰/۳۰/۳۱ (۴۵ رد می‌شود).
۵. جابِ بکاپ: تازه‌ترین فایل یک‌بار به ادمین‌ها می‌رود، دورِ بعد تکراری نمی‌فرستد، فقط
   فایل‌هایِ خودش را پاک می‌کند و با سوییچِ خاموش نه پوشه را می‌خواند نه چیزی پاک می‌کند.
۶. فایلِ بزرگ‌تر از سقفِ ربات ⇒ پیامِ جای‌نما می‌رود و فایل رویِ دیسک می‌ماند.

اجرا: python3 tests_manual/run_one.py test_p44_month_length_and_backup.py
"""
from __future__ import annotations

import asyncio
import datetime
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from sqlalchemy import select  # noqa: E402

from harness import build_test_dispatchers, reset_database  # noqa: E402
from phase4_helpers import Chat, callbacks  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot import texts as main_texts  # noqa: E402
from app.config import settings  # noqa: E402
from app.database.models import ShopOwner, Subscription, WalletCharge, WalletTransactionReason  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import backup_service, subscription_service, wallet_service  # noqa: E402
from app.services.admin_settings_service import get_admin_settings, update_setting  # noqa: E402
from app.utils.dates import add_validity_months  # noqa: E402

OWNER_TG_ID = 7_444_000_001
SHOP_BOT_TG_ID = 7_444_000_002
DAY_SECONDS = 86400


def _utc(y: int, m: int, d: int, hh: int = 6, mm: int = 0) -> datetime.datetime:
    return datetime.datetime(y, m, d, hh, mm, tzinfo=datetime.timezone.utc)


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _days_between(a: datetime.datetime, b: datetime.datetime) -> float:
    if a.tzinfo is None:
        a = a.replace(tzinfo=datetime.timezone.utc)
    if b.tzinfo is None:
        b = b.replace(tzinfo=datetime.timezone.utc)
    return (b - a).total_seconds() / DAY_SECONDS


async def _set(**pairs) -> None:
    async with session_scope() as session:
        for key, value in pairs.items():
            await update_setting(session, key, value)


async def _settings():
    async with session_scope() as session:
        return await get_admin_settings(session)


async def _owner_id() -> int:
    async with session_scope() as session:
        return (await session.execute(select(ShopOwner.id).where(ShopOwner.telegram_id == OWNER_TG_ID))).scalar_one()


# ============================================================================= ۱ — قاعدهٔ ماه
def test_month_length_rule() -> None:
    # تقویمی: ۳۱ ژانویه + ۱ ماه ⇒ سرِ ماهِ بعد clamp می‌شود (۲۸ فوریه)، خطا نمی‌گیرد.
    calendar = add_validity_months(_utc(2026, 1, 31), 1, 0)
    assert (calendar.year, calendar.month, calendar.day) == (2026, 2, 28), calendar
    # ۳۰ و ۳۱ ⇒ دقیقاً همان تعدادِ ۲۴ ساعته، بدونِ توجه به طولِ ماه‌هایِ میانی.
    assert _days_between(_utc(2026, 1, 31), add_validity_months(_utc(2026, 1, 31), 1, 30)) == 30
    assert _days_between(_utc(2026, 1, 31), add_validity_months(_utc(2026, 1, 31), 1, 31)) == 31
    assert _days_between(_utc(2026, 1, 15), add_validity_months(_utc(2026, 1, 15), 2, 31)) == 62
    print("✅ test_month_length_rule PASSED")


# ============================================================================= ۲ — فقط ردیفِ تازه
async def test_only_new_rows_follow_the_setting() -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID, initial_balance_toman=0)
    owner_id = await _owner_id()

    await _set(wallet_topup_validity_months=1, month_length_days=0)
    async with session_scope() as session:
        owner = await session.get(ShopOwner, owner_id)
        before = await wallet_service.add_charge(session, owner, 100_000, reason=WalletTransactionReason.TOPUP)
        before_id, before_expiry = before.id, before.expires_at

    await _set(month_length_days=31)
    made_at = _now()
    async with session_scope() as session:
        owner = await session.get(ShopOwner, owner_id)
        after = await wallet_service.add_charge(session, owner, 200_000, reason=WalletTransactionReason.TOPUP)
        after_expiry = after.expires_at
    assert 30.9 < _days_between(made_at, after_expiry) < 31.1, _days_between(made_at, after_expiry)

    async with session_scope() as session:
        old = await session.get(WalletCharge, before_id)
        assert old.expires_at == before_expiry, "ردیفِ قدیمی نباید جابه‌جا شود"

    # اشتراک هم همان قاعده را می‌گیرد (پیش‌ازاین فقط کیف‌پول این انتخاب را داشت).
    async with session_scope() as session:
        sub = await subscription_service.purchase_or_renew(session, owner_id, 1)
        sub_days = _days_between(sub.start_date, sub.end_date)
    assert 30.9 < sub_days < 31.1, sub_days

    await _set(month_length_days=0)
    async with session_scope() as session:
        await subscription_service.purchase_or_renew(session, owner_id, 1)
    async with session_scope() as session:
        subs = list((await session.execute(select(Subscription).order_by(Subscription.id))).scalars().all())
    assert len(subs) == 2, subs
    assert subs[0].end_date > subs[0].start_date, "اشتراکِ روزشمارِ ۳۱ روزه سرِ جایش مانده است"
    print("✅ test_only_new_rows_follow_the_setting PASSED")


# ============================================================================= ۳ — متنِ صادقِ گزارشِ شبانه
def test_digest_line_uses_the_real_window() -> None:
    default = main_texts.digest_wallet_line(500_000, 500_000, 90_000, 12, 0)
    assert "ظرفِ ۳۰ روزِ آینده" in default, default
    derived = main_texts.digest_wallet_line(500_000, 500_000, 90_000, 12, 0, window_days=31)
    assert "ظرفِ ۳۱ روزِ آینده" in derived, derived
    assert "ظرفِ ۳۰" not in derived, "عددِ پنجره باید از فراخوان بیاید، نه از متنِ ثابت"
    print("✅ test_digest_line_uses_the_real_window PASSED")


# ============================================================================= ۴ — دستهٔ تازه در پنلِ ادمین
async def test_admin_ops_page_and_validation(main_dp) -> None:
    await reset_database()
    admin_id = next(iter(settings.admin_ids))
    admin = Chat(main_dp, admin_id)

    await admin.tap("admin_settings_menu")
    assert "admin_settings_group:ops" in callbacks(admin.last_edit_markup), callbacks(admin.last_edit_markup)

    await admin.tap("admin_settings_group:ops")
    body = admin.last_edit_text
    assert "بکاپ و نگهداریِ دیتابیس" in body, body
    assert "پوشهٔ بکاپ" in body, "وضعیتِ زندهٔ پوشه در همین صفحه دیده می‌شود"
    page = callbacks(admin.last_edit_markup)
    assert "admin_setting_edit:month_length_days" in page, page
    assert "admin_setting_edit:backup_retention_days" in page, page
    assert "admin_toggle_nightly_backup" in page, page
    assert "admin_send_last_backup" in page, page

    await admin.tap("admin_setting_edit:month_length_days")
    assert admin.last_text == main_texts.ADMIN_ASK_MONTH_LENGTH_DAYS, admin.last_text
    await admin.say("45")
    assert admin.last_text == main_texts.ADMIN_INVALID_MONTH_LENGTH, admin.last_text
    assert (await _settings()).month_length_days == 0, "ورودیِ ردشده نباید ذخیره شود"

    await admin.say("31")
    # این مسیر دو پیام می‌فرستد: «ذخیره شد» و سپسِ تازه‌شدنِ همان صفحه (برچسبِ دکمه عددِ جدید را نشان می‌دهد).
    assert admin.sent[-2]["text"] == main_texts.ADMIN_SETTING_SAVED, admin.sent[-2]
    labels = [b.text for row in admin.last_markup.inline_keyboard for b in row]
    assert any("دقیقاً ۳۱ روزِ کامل" in label for label in labels), labels
    assert (await _settings()).month_length_days == 31

    await admin.tap("admin_setting_edit:backup_retention_days")
    await admin.say("90")
    assert admin.last_text == main_texts.ADMIN_INVALID_NUMBER, admin.last_text
    await admin.say("14")
    assert (await _settings()).backup_retention_days == 14

    await admin.tap("admin_toggle_nightly_backup")
    assert admin.last_toast["text"] == main_texts.switch_toast("ارسالِ خودکارِ بکاپ", True), admin.last_toast
    assert (await _settings()).nightly_backup_enabled is True
    print("✅ test_admin_ops_page_and_validation PASSED")


# ============================================================================= ۵ — جابِ بکاپ
def _make_dumps(base: Path, days_ago: list[int]) -> dict[int, Path]:
    """فایل‌هایِ جعلی با نامِ دقیقاً همان الگویی که سرویسِ بکاپ می‌سازد."""
    out: dict[int, Path] = {}
    for days in days_ago:
        stamp = _now() - datetime.timedelta(days=days)
        path = base / f"kasbokar-{stamp.strftime('%Y%m%d-%H%M%S')}.dump"
        path.write_bytes(b"PGDUMP-fixture")
        out[days] = path
    return out


async def test_backup_job_sends_once_and_prunes_only_its_own(main_dp) -> None:
    await reset_database()
    admin = Chat(main_dp, next(iter(settings.admin_ids)))
    base = Path(tempfile.mkdtemp(prefix="kasbokar-backups-"))
    original_dir = settings.backup_dir
    try:
        settings.backup_dir = str(base)
        await _set(nightly_backup_enabled=True, backup_retention_days=7)
        dumps = _make_dumps(base, [8, 3, 0])
        foreign = base / "not-ours.txt"
        foreign.write_text("این فایلِ ما نیست", encoding="utf-8")

        async with session_scope() as session:
            first = await backup_service.run_nightly(session, admin.bot)
        assert first["status"] == "sent", first
        assert first["sent"] == len(settings.admin_ids), first
        assert len(admin.documents) == 1, admin.documents
        assert dumps[0].name in str(admin.documents[0]["caption"]), admin.documents[0]
        assert first["deleted"] == [dumps[8].name], first["deleted"]
        assert not dumps[8].exists() and dumps[3].exists() and dumps[0].exists(), "فقط مهلت‌گذشته پاک می‌شود"
        assert foreign.exists(), "فایلِ بی‌ربط هرگز پاک نمی‌شود"
        assert (await _settings()).backup_last_sent_at is not None

        async with session_scope() as session:
            second = await backup_service.run_nightly(session, admin.bot)
        assert second["status"] == "already-sent", second
        assert len(admin.documents) == 1, "همان فایل دوباره ارسال نمی‌شود"

        # خاموش ⇒ نه پوشه خوانده می‌شود نه چیزی پاک می‌شود؛ درخواستِ دستی همیشه کار می‌کند.
        await _set(nightly_backup_enabled=False)
        async with session_scope() as session:
            third = await backup_service.run_nightly(session, admin.bot)
        assert third == {"status": "off", "files": 0}, third
        async with session_scope() as session:
            manual = await backup_service.send_latest_now(session, admin.bot)
        assert manual["status"] == "sent", manual
        assert len(admin.documents) == 2, manual
    finally:
        settings.backup_dir = original_dir
        shutil.rmtree(base, ignore_errors=True)
    print("✅ test_backup_job_sends_once_and_prunes_only_its_own PASSED")


async def test_oversized_backup_sends_placeholder(main_dp) -> None:
    await reset_database()
    admin = Chat(main_dp, next(iter(settings.admin_ids)))
    base = Path(tempfile.mkdtemp(prefix="kasbokar-backups-big-"))
    original_dir = settings.backup_dir
    original_limit = backup_service.MAX_SEND_BYTES
    try:
        settings.backup_dir = str(base)
        await _set(nightly_backup_enabled=True, backup_retention_days=7)
        dumps = _make_dumps(base, [0])
        backup_service.MAX_SEND_BYTES = 4  # هر فایلی از این بزرگ‌تر است
        async with session_scope() as session:
            result = await backup_service.run_nightly(session, admin.bot)
        assert result["status"] == "sent", result
        assert not admin.documents, "فایلِ بزرگ‌تر از سقفِ ربات ارسال نمی‌شود"
        assert any("نمی‌تواند چنین فایلی را بفرستد" in (m.get("text") or "") for m in admin.sent), admin.sent
        assert dumps[0].exists(), "فایل رویِ دیسک می‌ماند"
    finally:
        backup_service.MAX_SEND_BYTES = original_limit
        settings.backup_dir = original_dir
        shutil.rmtree(base, ignore_errors=True)
    print("✅ test_oversized_backup_sends_placeholder PASSED")


async def main() -> None:
    assert settings.admin_ids, "این تست به ADMIN_TELEGRAM_IDSِ محیطِ تست نیاز دارد"
    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    test_month_length_rule()
    await test_only_new_rows_follow_the_setting()
    test_digest_line_uses_the_real_window()
    await test_admin_ops_page_and_validation(main_dp)
    await test_backup_job_sends_once_and_prunes_only_its_own(main_dp)
    await test_oversized_backup_sends_placeholder(main_dp)


if __name__ == "__main__":
    asyncio.run(main())
