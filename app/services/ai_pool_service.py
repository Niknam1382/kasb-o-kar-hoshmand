from __future__ import annotations

import re

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import AdminSettings, AiApiKeyPoolEntry, AiKeyCapability
from app.services import ai_service
from app.utils.validators import fa_number

# P18 · A4: سقفِ مدل‌هایِ پشتیبانِ هر کلید. هر مدلِ اضافه یعنی تا ۳ تلاشِ HTTPِ دیگر؛
# بدونِ سقف، یک کلیدِ خراب می‌تواند تأخیر و هزینه‌یِ یک درخواست را چند برابر کند.
MAX_FALLBACK_MODELS = 5
MAX_MODEL_NAME_LENGTH = 100  # هم‌اندازه‌یِ ستون `model`؛ جلویِ رشته‌یِ هزارنویسه‌ای در payload را می‌گیرد
# P47 · سقفِ تعدادِ کلیدها و بازه‌یِ مجازِ سقفِ همزمانیِ هرِ کلید. عددِ کلیدها را پنلِ ادمین
# نشان می‌دهد («کلید ۱ … کلید ۱۰»)، و عددِ همزمانی *همین‌جا* وارد می‌شود، نه در `.env`.
MAX_KEYS = 10
MIN_KEY_CAP = 1
MAX_KEY_CAP = 500
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


def parse_key_cap(raw: str | None) -> tuple[int | None, str | None]:
    """ورودیِ متنیِ ادمین ⇒ (سقفِ همزمانی، پیامِ خطا). «خالی» یعنی سهمِ مساوی از سقفِ پلتفرم.

    None/رشتهٔ خالی = «اینِ خط را ننوشته» (در فرمِ افزودن، خطِ هفتم اختیاری است) ⇒ نه عدد، نه خطا.
    """
    text = (raw or "").strip()
    if not text:
        return None, None
    if text in ("خالی", "پاک کن", "-", "سهمِ مساوی"):
        return None, None
    normalized = text.replace("٫", ".").replace(",", "")
    try:
        value = int(float(normalized))
    except (TypeError, ValueError):
        return None, f"«{text}» عدد نیست. یکِ عددِ صحیح بینِ {fa_number(MIN_KEY_CAP)} تا {fa_number(MAX_KEY_CAP)} بنویس."
    if not MIN_KEY_CAP <= value <= MAX_KEY_CAP:
        return None, f"سقفِ هرِ کلید باید بینِ {fa_number(MIN_KEY_CAP)} تا {fa_number(MAX_KEY_CAP)} باشد."
    return value, None


def key_cap_label(entry: AiApiKeyPoolEntry) -> str:
    """نمایشِ فارسیِ سقفِ یکِ کلید (ارقام جلالی، بدونِ عددِ انگلیسی قاطیِ متنِ ادمین)."""
    if entry.max_concurrent:
        return f"{fa_number(entry.max_concurrent)} درخواستِ هم‌زمان"
    return "سهمِ مساوی از سقفِ پلتفرم"


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


async def count_entries(session: AsyncSession) -> int:
    result = await session.execute(select(func.count()).select_from(AiApiKeyPoolEntry))
    return int(result.scalar_one())


async def add_entry(
    session: AsyncSession,
    label: str,
    api_key: str,
    model: str,
    base_url: str,
    capability: str,
    fallback_models: str | None = None,
    max_concurrent: int | None = None,
) -> AiApiKeyPoolEntry:
    entry = AiApiKeyPoolEntry(
        label=label,
        api_key=api_key,
        model=model,
        base_url=base_url,
        capability=capability,
        fallback_models=", ".join(parse_model_list(fallback_models)),
        max_concurrent=max_concurrent,
    )
    session.add(entry)
    await session.flush()
    return entry


async def set_max_concurrent(session: AsyncSession, entry: AiApiKeyPoolEntry, value: int | None) -> None:
    """سقفِ همزمانیِ همینِ کلید. `None` ⇒ سهمِ مساوی از سقفِ پلتفرم (رفتارِ پیش‌فرض)."""
    entry.max_concurrent = None if value is None else max(MIN_KEY_CAP, min(MAX_KEY_CAP, int(value)))
    await session.flush()


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


async def import_legacy_key(session: AsyncSession, admin_settings: AdminSettings) -> AiApiKeyPoolEntry | None:
    """«کلیدِ قدیمیِ سراسری» را به یکِ کلیدِ شمارش‌شده در همین استخر تبدیل می‌کند.

    تا استخر خالی است، همان `admin_settings.ai_api_key` کار می‌کرد (و همچنان کار می‌کند). این
    تابع فقط یکِ «پلِ عبور» است: کلید را (با رمزنگاریِ همان ستون) به استخر می‌برد، بعدِ
    انتقال مقدارِ سراسری را پاک می‌کند تا *دو بار* در گردشِ درخواست‌ها نیفتد. هیچ داده‌ای از
    دست نمی‌رود: ستون‌هایِ قدیمی در دیتابیس می‌مانند و فقط مقدارِ آنِ کلید خالی می‌شود.
    """
    if not admin_settings.ai_api_key:
        return None
    entry = await add_entry(
        session,
        "کلیدِ قدیمی",
        admin_settings.ai_api_key,
        (admin_settings.ai_model or "").strip()[:MAX_MODEL_NAME_LENGTH],
        (admin_settings.ai_base_url or "").strip()[:255],
        AiKeyCapability.CHAT.value,
    )
    admin_settings.ai_api_key = None
    await session.flush()
    return entry


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
    # P47: سهمِ پیش‌فرضِ هرِ کلید = تقسیمِ مساویِ سقفِ پلتفرم؛ کلیدی که عددِ خودش را نوشته
    # همان عدد را می‌گیرد. این dict فقط «سقف» است، نه اولویت — انتخابِ خودِ سرویس‌دهنده
    # کم‌بارترینِ کلید در `PooledAiService` انجام می‌شود.
    explicit_caps = {
        pool_entry.id: max(MIN_KEY_CAP, min(MAX_KEY_CAP, int(pool_entry.max_concurrent)))
        for pool_entry in pool_entries
        if pool_entry.max_concurrent
    }
    default_share = ai_service.equal_share_cap(ai_service.platform_ceiling(), len(entries))
    caps = {key_id: explicit_caps.get(key_id, default_share) for key_id, _service in entries}
    return ai_service.PooledAiService(entries, caps)


def capacity_report(entries: list[AiApiKeyPoolEntry]) -> dict[str, int]:
    """عددهایِ ظرفیت برایِ پنلِ ادمین: سقفِ پلتفرم، جمعِ سقفِ کلیدها، و اینکه گلوگاه کدام است.

    فقط شمارش است — هیچ کلید یا مدلی در خروجی نیست. `bottleneck` دو مقدار دارد:
    `keys` یعنی سقفِ خودِ کلیدها کمتر از پلتفرم است (باید عددِ کلیدها بالا برود)،
    `platform` یعنی `AI_MAX_CONCURRENT_CALLS` گلوگاه است (باید همان یک عدد در `.env` برود).
    """
    active = [entry for entry in entries if entry.is_active]
    ceiling = ai_service.platform_ceiling()
    if not active:
        return {"keys": 0, "ceiling": ceiling, "sum_caps": 0, "bottleneck": "keys"}
    default_share = ai_service.equal_share_cap(ceiling, len(active))
    total = sum(
        max(MIN_KEY_CAP, min(MAX_KEY_CAP, int(entry.max_concurrent))) if entry.max_concurrent else default_share
        for entry in active
    )
    return {"keys": len(active), "ceiling": ceiling, "sum_caps": total, "bottleneck": "keys" if total < ceiling else "platform"}
