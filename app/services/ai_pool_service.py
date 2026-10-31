from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import AdminSettings, AiApiKeyPoolEntry, AiKeyCapability
from app.services import ai_service

# P18 · A4: سقفِ مدل‌هایِ پشتیبانِ هر کلید. هر مدلِ اضافه یعنی تا ۳ تلاشِ HTTPِ دیگر؛
# بدونِ سقف، یک کلیدِ خراب می‌تواند تأخیر و هزینه‌یِ یک درخواست را چند برابر کند.
MAX_FALLBACK_MODELS = 5
MAX_MODEL_NAME_LENGTH = 100  # هم‌اندازه‌یِ ستون `model`؛ جلویِ رشته‌یِ هزارنویسه‌ای در payload را می‌گیرد
_MODEL_SPLIT = re.compile(r"[,\n،;]+")


def parse_model_list(raw: str | None) -> list[str]:
    """فهرستِ مدل‌ها از رشته‌یِ خامِ ادمین (ویرگول/فارسی/سمیکالن/خطِ جدید) ⇒ نام‌هایِ یکتا و مرتب."""
    if not raw:
        return []
    out: list[str] = []
    for piece in _MODEL_SPLIT.split(raw):
        name = piece.strip()[:MAX_MODEL_NAME_LENGTH]
        if name and name not in out:
            out.append(name)
    return out[:MAX_FALLBACK_MODELS]


def model_chain(entry: AiApiKeyPoolEntry) -> list[str]:
    """مدلِ اصلی اول، بعد پشتیبان‌هایِ همان کلید به همان ترتیبی که ادمین نوشته."""
    primary = (entry.model or "").strip()
    fallbacks = [name for name in parse_model_list(entry.fallback_models) if name != primary]
    return [primary, *fallbacks] if primary else fallbacks


async def get_all_entries(session: AsyncSession) -> list[AiApiKeyPoolEntry]:
    result = await session.execute(select(AiApiKeyPoolEntry).order_by(AiApiKeyPoolEntry.id))
    return list(result.scalars().all())


async def get_active_entries_for_capability(session: AsyncSession, capability: str) -> list[AiApiKeyPoolEntry]:
    if capability == AiKeyCapability.STT.value:
        # `both` یعنی «چت + بینایی» (معنایِ همیشگی‌اش)؛ کلیدهایِ چت نباید ناگهانی به /audio بروند.
        wanted = [AiKeyCapability.STT.value]
    else:
        wanted = [capability, AiKeyCapability.BOTH.value]
    result = await session.execute(
        select(AiApiKeyPoolEntry).where(AiApiKeyPoolEntry.is_active.is_(True), AiApiKeyPoolEntry.capability.in_(wanted))
    )
    return list(result.scalars().all())


async def add_entry(
    session: AsyncSession,
    label: str,
    api_key: str,
    model: str,
    base_url: str,
    capability: str,
    fallback_models: str | None = None,
) -> AiApiKeyPoolEntry:
    entry = AiApiKeyPoolEntry(
        label=label,
        api_key=api_key,
        model=model,
        base_url=base_url,
        capability=capability,
        fallback_models=", ".join(parse_model_list(fallback_models)),
    )
    session.add(entry)
    await session.flush()
    return entry


async def set_fallback_models(session: AsyncSession, entry: AiApiKeyPoolEntry, raw: str | None) -> list[str]:
    """فهرست را ذخیره و نرمال می‌کند؛ فهرستِ بازگشتی همان چیزی است که واقعاً استفاده می‌شود."""
    entry.fallback_models = ", ".join(parse_model_list(raw))
    await session.flush()
    return parse_model_list(entry.fallback_models)


async def get_by_id(session: AsyncSession, entry_id: int) -> AiApiKeyPoolEntry | None:
    return await session.get(AiApiKeyPoolEntry, entry_id)


async def toggle_active(session: AsyncSession, entry: AiApiKeyPoolEntry) -> None:
    entry.is_active = not entry.is_active
    await session.flush()


async def delete_entry(session: AsyncSession, entry: AiApiKeyPoolEntry) -> None:
    await session.delete(entry)
    await session.flush()


async def build_ai_service(session: AsyncSession, admin_settings: AdminSettings, capability: str) -> ai_service.BaseAiService | None:
    """
    سرویسِ AI مناسب برای این فراخوانی رو می‌سازه — با در نظرگرفتنِ هم استخرِ
    کلیدها، هم روشِ قدیمیِ تک‌کلیدی (برای سازگاریِ عقب، اگه ادمین هنوز به
    استخر منتقل نشده). اگه هیچ کلیدی (نه قدیمی، نه استخر) پیدا نشد، None
    برمی‌گرده — caller باید این حالت رو مدیریت کنه.

    نکته‌ی مهمِ پیاده‌سازی: وقتی استخر خالیه (که برای همه‌ی تست‌ها و اکثرِ
    استقرارهای فعلی صادقه)، عیناً همون ai_service.get_ai_service(...) صدا
    زده می‌شه — نه یه ساختِ مستقیمِ OpenAiCompatibleAiService. این عمداً
    این‌جوریه: تست‌های موجود (mocking از طریقِ ai_service.get_ai_service =
    lambda ...) باید بدونِ تغییر کار کنن؛ فقط وقتی ادمین واقعاً یه کلید به
    استخر اضافه کنه، مسیرِ جدید فعال می‌شه.
    """
    pool_entries = await get_active_entries_for_capability(session, capability)
    is_voice = capability == AiKeyCapability.STT.value

    if not pool_entries:
        if not admin_settings.ai_api_key:
            return None
        return ai_service.get_ai_service(
            admin_settings.ai_api_key,
            ai_service.DEFAULT_STT_MODEL if is_voice else admin_settings.ai_model,
            admin_settings.ai_base_url,
            admin_settings.ai_fallback_api_key,
            None if not admin_settings.ai_fallback_api_key else (ai_service.DEFAULT_STT_MODEL if is_voice else admin_settings.ai_fallback_model),
            admin_settings.ai_fallback_base_url,
        )

    entries: list[tuple[int, ai_service.BaseAiService]] = []
    if admin_settings.ai_api_key and not is_voice:
        entries.append((0, ai_service.OpenAiCompatibleAiService(admin_settings.ai_api_key, admin_settings.ai_model, admin_settings.ai_base_url)))
    if admin_settings.ai_fallback_api_key and admin_settings.ai_fallback_model and not is_voice:
        entries.append(
            (
                -1,
                ai_service.OpenAiCompatibleAiService(
                    admin_settings.ai_fallback_api_key,
                    admin_settings.ai_fallback_model,
                    admin_settings.ai_fallback_base_url or ai_service.DEFAULT_AI_BASE_URL,
                ),
            )
        )
    for pool_entry in pool_entries:
        entries.append(
            (
                pool_entry.id,
                ai_service.ModelChainAiService(
                    pool_entry.id, pool_entry.api_key, pool_entry.base_url, model_chain(pool_entry)
                ),
            )
        )

    if not entries:
        return None
    if len(entries) == 1:
        return entries[0][1]
    return ai_service.PooledAiService(entries)
