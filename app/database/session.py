from __future__ import annotations

from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings

# پ۱۰۱: حالتِ `null` فقط برایِ سوئیتِ تست است — اتصالِ ماندگار در استخر نمی‌ماند تا در پایانِ
# پروسه، GCِ اتصالِ بازِاده‌شده warning نسازد (تولید مثلِ قبل با استخرِ کامل کار می‌کند).
_pool_kwargs: dict = (
    {"poolclass": NullPool} if settings.db_pool_class.strip().lower() == "null"
    else {
        "pool_pre_ping": True,
        "pool_size": settings.db_pool_size,
        "max_overflow": settings.db_max_overflow,
        "pool_timeout": settings.db_pool_timeout,
    }
)

engine = create_async_engine(settings.database_url, **_pool_kwargs)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@asynccontextmanager
async def session_scope():
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
