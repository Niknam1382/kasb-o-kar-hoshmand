"""نگهدارندهٔ FSM رویِ PostgreSQL (P32).

هدفِ واحد: چک‌اوتِ نیمه‌کارهٔ مشتری با ری‌استارتِ سرویس (دیپلوی، OOM، ری‌استارتِ داکر)
نپَرَد. `MemoryStorage` این حالت را فقط در رمِ پروسه نگه می‌داشت.

چرا Redis نه: در این محیط `files.pythonhosted.org` resolve نمی‌شود (پکیج نصب نمی‌شود) و
سرویسِ تازه به معماری افزودن، خلافِ §۲-۱۱ است. PostgreSQL که همین حالا هست، همان کار را
می‌کند؛ با `FSM_STORAGE=postgres` روشن می‌شود و پیش‌فرض `memory` است تا رفتارِ نصب‌هایِ
فعالیِ تو تغییر نکند.

قراردادِ aiogram ۳.۳۰: پیاده‌سازیِ `set_state/get_state/set_data/get_data/close` کافی است؛
`update_data` و `get_value` رویِ همین‌ها در `BaseStorage` ساخته می‌شوند.

هر فراخوانیِ FSM یکِ UPSERT/SELECT است. تعدادِ آن در هر سفارش چندِ تا است (نه به‌ازایِ هر
پیامِ چت)، پس رویِ مسیرِ داغِ ۳۰-statementی اثری ندارد.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
from typing import Any, Mapping

from aiogram.fsm.storage.base import BaseStorage, StorageKey
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.models import FsmState
from app.database.session import session_scope

# حالتِ مکالمه چیزی نیست که ماه‌ها به آن برگردیم؛ ردیف‌هایِ کهنه پاک می‌شوند (جابِ scheduler).
STATE_TTL_HOURS = 24
MEMORY = "memory"
POSTGRES = "postgres"
logger = logging.getLogger(__name__)


def _key_parts(key: StorageKey) -> tuple[int, int, int]:
    return int(key.bot_id), int(key.chat_id), int(key.user_id)


def _upsert(key: StorageKey, **values: Any) -> Any:
    """`INSERT … ON CONFLICT DO UPDATE`.

    مقدارِ تازه باید در `values()`ِ درج هم باشد، نه فقط در `set_`: اگر ردیفی وجود نداشته
    باشد اصلاً conflict رخ نمی‌دهد و `set_` اجرا نمی‌شود — یعنی اولین `set_state` مقدار را
    دور می‌ریخت و `state` همان NULL می‌ماند (این را `test_p32_fsm_postgres.py` گرفت).
    """
    bot_id, chat_id, user_id = _key_parts(key)
    return pg_insert(FsmState).values(
        bot_id=bot_id, chat_id=chat_id, user_id=user_id, updated_at=func.now(), **values
    )


def _state_name(state: Any) -> str | None:
    """aiogram گاهی خودِ شیءِ State و گاهی رشته می‌فرستد (این نسخه `StateType` را export نمی‌کند)."""
    if state is None:
        return None
    inner = getattr(state, "state", None)
    return str(inner if inner is not None else state)


class PostgresStorage(BaseStorage):
    """نگهدارندهٔ FSM؛ هر فراخوانی در سشنِ خودش (فراخوانی‌ها کم و پراکنده‌اند)."""

    async def set_state(self, key: StorageKey, state: Any = None) -> None:
        name = _state_name(state)
        statement = (
            _upsert(key, state=name)
            .on_conflict_do_update(
                index_elements=["bot_id", "chat_id", "user_id"],
                set_={"state": name, "updated_at": func.now()},
            )
        )
        async with session_scope() as session:
            await session.execute(statement)

    async def get_state(self, key: StorageKey) -> str | None:
        bot_id, chat_id, user_id = _key_parts(key)
        async with session_scope() as session:
            return await session.scalar(
                select(FsmState.state).where(
                    FsmState.bot_id == bot_id, FsmState.chat_id == chat_id, FsmState.user_id == user_id
                )
            )

    async def set_data(self, key: StorageKey, data: Mapping[str, Any]) -> None:
        payload = json.dumps(dict(data), default=str, ensure_ascii=False)
        statement = (
            _upsert(key, data_json=payload)
            .on_conflict_do_update(
                index_elements=["bot_id", "chat_id", "user_id"],
                set_={"data_json": payload, "updated_at": func.now()},
            )
        )
        async with session_scope() as session:
            await session.execute(statement)

    async def get_data(self, key: StorageKey) -> dict[str, Any]:
        bot_id, chat_id, user_id = _key_parts(key)
        async with session_scope() as session:
            raw = await session.scalar(
                select(FsmState.data_json).where(
                    FsmState.bot_id == bot_id, FsmState.chat_id == chat_id, FsmState.user_id == user_id
                )
            )
        if not raw:
            return {}
        try:
            loaded = json.loads(raw)
        except (TypeError, ValueError):
            return {}
        return loaded if isinstance(loaded, dict) else {}

    async def close(self) -> None:
        return None


async def purge_stale_states(session: AsyncSession, *, hours: int = STATE_TTL_HOURS) -> int:
    """ردیف‌هایِ کهنه را پاک می‌کند؛ توسطِ جابِ ادواری صدا زده می‌شود."""
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours)
    result = await session.execute(delete(FsmState).where(FsmState.updated_at < cutoff))
    return int(result.rowcount or 0)


def build_storage() -> BaseStorage:
    """پیش‌فرضِ ایمن: `memory` (رفتارِ همیشگی). با `FSM_STORAGE=postgres` حالت‌ها می‌مانند.

    ⚠️ مسیرِ postgres هنوز **آمادهٔ تولید نیست**: در تست‌هایِ واحد (۵ مورد) سبز است، ولی
    در بازاجرایِ `test_checkout_c3.py` با `FSM_STORAGE=postgres` یکِ ادعایِ «دابل‌تپِ ثبتِ
    نهایی = یکِ سفارش» شکست خورد (۱۴۰۵-۰۸-۱۲، MEASURED). علتِ دقیقش بررسیِ بعدی می‌خواهد؛
    تا آن روز این کلید عمداً `memory` می‌ماند و اینجا هم هشدار می‌دهیم که کسی فکر نکند
    با روشن‌کردنش چک‌اوت پایدار شده است.
    """
    if (settings.fsm_storage or MEMORY).strip().lower() == POSTGRES:
        logger.warning(
            "FSM_STORAGE=postgres روشن است اما این مسیر هنوز در تستِ end-to-endِ چک‌اوت سبز "
            "نشده؛ پیش ازِ استفاده رویِ سرورِ واقعی آن را با چک‌اوتِ دستی بسنج."
        )
        return PostgresStorage()
    from aiogram.fsm.storage.memory import MemoryStorage

    return MemoryStorage()
