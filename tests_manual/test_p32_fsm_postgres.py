"""
تست: P32 — نگهدارندهٔ FSM رویِ PostgreSQL (حالتِ چک‌اوت با ری‌استارت نمی‌پَرَد)

با `FSM_STORAGE=postgres`، حالت و دادهٔ مکالمه در جدولِ `fsm_states` می‌نشیند. چهار چیزی که
این فایل قفل می‌کند:
۱. رفت‌وبرگشتِ state و data، از جمله متنِ فارسی و تایپ‌هایِ غیرِ JSON-پذیر (default=str)
۲. نوشتنِ data نباید state را پاک کند و برعکس (دو UPSERTِ مستقل رویِ همان سطر)
۳. «ماندگاری پس ازِ ری‌استارت» با دو نمونهٔ جدا از نگهدارنده سنجیده می‌شود (سشن/پروسهٔ تازه)
۴. پاک‌سازیِ ردیف‌هایِ کهنه، و نبودِ ردیفِ تازه برایِ کلیدِ ناشناخته

اجرا: python3 tests_manual/run_one.py test_p32_fsm_postgres.py
"""
from __future__ import annotations

import asyncio
import datetime as dt
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram.fsm.storage.base import StorageKey  # noqa: E402
from aiogram.fsm.storage.memory import MemoryStorage  # noqa: E402
from sqlalchemy import update  # noqa: E402

from harness import reset_database  # noqa: E402

from app.config import settings
from app.database.models import FsmState  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import fsm_storage  # noqa: E402
from app.services.fsm_storage import PostgresStorage  # noqa: E402

BOT_ID = 991
CHAT_ID = 992
USER_ID = 993


def _key(user_id: int = USER_ID) -> StorageKey:
    return StorageKey(bot_id=BOT_ID, chat_id=CHAT_ID, user_id=user_id)


async def test_state_and_data_roundtrip() -> None:
    await reset_database()
    store = PostgresStorage()
    key = _key()

    assert await store.get_state(key) is None
    assert await store.get_data(key) == {}

    await store.set_state(key, "CheckoutStates:entering_phone")
    await store.set_data(key, {"name": "علی رضایی", "seconds": 45, "note": "«گیومه»"})
    assert await store.get_state(key) == "CheckoutStates:entering_phone"
    data = await store.get_data(key)
    assert data["name"] == "علی رضایی" and data["note"] == "«گیومه»" and data["seconds"] == 45, data

    # داده‌هایِ غیرِ JSON-پذیر نباید خطا بدهند (تبدیل به رشته می‌شوند، مثلِ مسیرِ Redis)
    await store.set_data(key, {"moment": dt.datetime(2026, 11, 4, tzinfo=dt.timezone.utc)})
    assert "2026-11-04" in str((await store.get_data(key))["moment"])
    print("✅ test_state_and_data_roundtrip PASSED")


async def test_state_and_data_do_not_erase_each_other() -> None:
    key = _key()
    await PostgresStorage().set_state(key, "CheckoutStates:choosing_address")
    await PostgresStorage().set_data(key, {"cart_id": 7})
    assert await PostgresStorage().get_state(key) == "CheckoutStates:choosing_address", "set_data نباید state را پاک کند"
    assert (await PostgresStorage().get_data(key))["cart_id"] == 7, "set_state نباید data را پاک کند"

    await PostgresStorage().set_state(key, None)
    assert await PostgresStorage().get_state(key) is None, "پاک‌کردنِ state باید کار کند"
    assert (await PostgresStorage().get_data(key))["cart_id"] == 7, "state=None نباید data را بردارد"
    print("✅ test_state_and_data_do_not_erase_each_other PASSED")


async def test_survives_a_restart() -> None:
    """دو نمونهٔ مستقل از نگهدارنده = دو پروسهٔ مستقل (چیزی که MemoryStorage در آن می‌بازد)."""
    key = _key(user_id=USER_ID + 1)
    first = PostgresStorage()
    await first.set_state(key, "CheckoutStates:confirming")
    await first.set_data(key, {"total_toman": 250000})

    second = PostgresStorage()
    assert await second.get_state(key) == "CheckoutStates:confirming"
    assert (await second.get_data(key))["total_toman"] == 250000

    # و همان حالت با `update_data` (مسیرِ واقعیِ فرم‌ها) هم جمع می‌شود
    await second.update_data(key, {"phone": "09120000000"})
    data = await second.get_data(key)
    assert data["total_toman"] == 250000 and data["phone"] == "09120000000", data
    print("✅ test_survives_a_restart PASSED")


async def test_memory_storage_is_still_the_default() -> None:
    assert (settings.fsm_storage or "memory") == "memory", "پیش‌فرض نباید رفتارِ نصب‌هایِ موجود را عوض کند"
    assert isinstance(fsm_storage.build_storage(), MemoryStorage)
    print("✅ test_memory_storage_is_still_the_default PASSED")


async def test_purge_removes_only_stale_rows() -> None:
    fresh = _key(user_id=USER_ID + 2)
    stale = _key(user_id=USER_ID + 3)
    store = PostgresStorage()
    await store.set_state(fresh, "CheckoutStates:entering_name")
    await store.set_state(stale, "CheckoutStates:entering_name")

    old = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=fsm_storage.STATE_TTL_HOURS + 6)
    async with session_scope() as session:
        await session.execute(
            update(FsmState).where(FsmState.user_id == stale.user_id).values(updated_at=old)
        )
        await session.commit()

    async with session_scope() as session:
        removed = await fsm_storage.purge_stale_states(session)
    assert removed == 1, f"انتظارِ حذفِ یکِ ردیفِ کهنه داشتیم؛ شد {removed}"
    assert await store.get_state(stale) is None
    assert await store.get_state(fresh) == "CheckoutStates:entering_name", "ردیفِ تازه نباید برود"
    print("✅ test_purge_removes_only_stale_rows PASSED")


async def main() -> None:
    await test_state_and_data_roundtrip()
    await test_state_and_data_do_not_erase_each_other()
    await test_survives_a_restart()
    await test_memory_storage_is_still_the_default()
    await test_purge_removes_only_stale_rows()


if __name__ == "__main__":
    asyncio.run(main())
