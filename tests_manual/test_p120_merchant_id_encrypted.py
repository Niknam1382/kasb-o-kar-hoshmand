"""پ۱۲۰ · مرچنت‌آیدی زرین‌پالِ پلتفرم دیگر خام در دیتابیس نمی‌خوابد (یافتهٔ ۵ِ بازرسی).

آخرین قلمِ بازِ یافتهٔ ۵: `admin_settings.zarinpal_merchant_id` تنها رازِ هم‌خانواده‌یِ آن جدول بود
که `String(64)` و بی‌رمز بود ⇒ هر `pg_dump` شناسهٔ درگاهِ پلتفرم را با خودش می‌برد. الگو، همانِ
پ۲۴ برایِ `platform_card_number` است: ستون `EncryptedText` (نوعش Text می‌شود، مایگریشنِ افزودنی) +
یکِ پاسِ بوت‌آپ که ردیف‌هایِ خامِ قدیمی را رمز می‌کند (مایگریشن به `ENCRYPTION_KEY` وابسته نمی‌شود).

سه چیزی که این فایل قفل می‌کند:
۱. عرضِ ستون در دیتابیس `text` است (وگرنه نوشتنِ رمزِ Fernet با «value too long» می‌شکند).
۲. نوشتنِ معمولی ⇒ در دیتابیس رمز، در ORM متنِ اصلی (شفاف، بی‌تغییرِ مسیرهایِ پرداخت).
۳. ردیفِ خامِ قدیمی ⇒ `reencrypt_merchant_id` یک‌بار رمزاش می‌کند و اجرایِ دوباره بی‌اثر است.

اجرا: python3 tests_manual/run_one.py test_p120_merchant_id_encrypted.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from sqlalchemy import text as sql_text  # noqa: E402

from app.database.session import session_scope  # noqa: E402
from app.services import admin_settings_service  # noqa: E402
from app.utils.encryption import looks_encrypted  # noqa: E402
from harness import reset_database  # noqa: E402

MERCHANT = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"


async def _raw_value() -> str | None:
    async with session_scope() as session:
        return (await session.execute(sql_text("SELECT zarinpal_merchant_id FROM admin_settings WHERE id = 1"))).scalar()


async def test_column_is_wide_enough_for_ciphertext() -> None:
    async with session_scope() as session:
        data_type = (
            await session.execute(
                sql_text(
                    "SELECT data_type FROM information_schema.columns "
                    "WHERE table_name = 'admin_settings' AND column_name = 'zarinpal_merchant_id'"
                )
            )
        ).scalar()
    assert data_type == "text", f"ستون باید با مایگریشنِ پ۱۲۰ text شده باشد، هست: {data_type}"
    print("✅ test_column_is_wide_enough_for_ciphertext PASSED")


async def test_write_stores_ciphertext_and_reads_plaintext() -> None:
    await reset_database()
    async with session_scope() as session:
        row = await admin_settings_service.get_admin_settings(session)
        row.zarinpal_merchant_id = MERCHANT
        await session.commit()

    admin_settings_service.reset_read_cache()
    stored = await _raw_value()
    assert stored and stored != MERCHANT and looks_encrypted(str(stored)), "مقدارِ خام در دیتابیس مانده"
    async with session_scope() as session:
        row = await admin_settings_service.get_admin_settings(session)
        assert row.zarinpal_merchant_id == MERCHANT, "رمزگشاییِ شفاف کار نمی‌کند"
    print(f"✅ test_write_stores_ciphertext_and_reads_plaintext PASSED (طولِ رمز در DB: {len(str(stored))} نویسه)")


async def test_legacy_plaintext_is_readable_and_gets_encrypted_once() -> None:
    await reset_database()
    async with session_scope() as session:
        await admin_settings_service.get_admin_settings(session)
        await session.commit()
    # یکِ نصبِ قدیمی: مقدارِ خام مستقیم در ستون نوشته می‌شود (بدونِ ORM)
    async with session_scope() as session:
        await session.execute(sql_text("UPDATE admin_settings SET zarinpal_merchant_id = :v WHERE id = 1"), {"v": MERCHANT})
        await session.commit()
    assert await _raw_value() == MERCHANT

    async with session_scope() as session:
        assert await admin_settings_service.reencrypt_merchant_id(session) is True
        await session.commit()
    stored = await _raw_value()
    assert stored and looks_encrypted(str(stored)), "پاسِ بوت‌آپ رمز نکرد"
    async with session_scope() as session:
        row = await admin_settings_service.get_admin_settings(session)
        assert row.zarinpal_merchant_id == MERCHANT, "متنِ اصلی بعد ازِ رمزنگاری گم شد"
    async with session_scope() as session:
        assert await admin_settings_service.reencrypt_merchant_id(session) is False, "اجرایِ دوباره باید بی‌اثر باشد"
        await session.commit()
    print("✅ test_legacy_plaintext_is_readable_and_gets_encrypted_once PASSED")


async def test_empty_value_is_left_alone() -> None:
    await reset_database()
    async with session_scope() as session:
        await admin_settings_service.get_admin_settings(session)
        await session.commit()
    async with session_scope() as session:
        assert await admin_settings_service.reencrypt_merchant_id(session) is False
        rows = list((await session.execute(sql_text("SELECT zarinpal_merchant_id FROM admin_settings"))).scalars().all())
    assert rows in ([None], []), rows
    print("✅ test_empty_value_is_left_alone PASSED")


async def main() -> None:
    await test_column_is_wide_enough_for_ciphertext()
    await test_write_stores_ciphertext_and_reads_plaintext()
    await test_legacy_plaintext_is_readable_and_gets_encrypted_once()
    await test_empty_value_is_left_alone()


if __name__ == "__main__":
    asyncio.run(main())
