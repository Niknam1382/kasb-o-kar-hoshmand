"""پ۶۱ · خواستهٔ مالکِ محصول (۲۰۲۶-۱۱-۱۲): «یکِ قسمت در پنلِ ادمین برایِ بررسیِ وضعیتِ ظرفیت
API‌ها و فشارِ سرور به‌صورتِ درصدی و آمارِ دقیق».

سه چیز را یک‌جا نشان می‌دهد، همه **بدونِ شبکه و بدونِ نوشتنِ هیچ چیزی**:

۱. ظرفیتِ AI: برایِ هرِ کلیدِ فعالِ استخر، «چند درخواستِ همینِ کلید الان درِ حالِ اجراست» نسبت به
   سقفِ *خودِ آن کلید* (`AiApiKeyPoolEntry.max_concurrent`)، و جمعِ سقفِ کلیدها در برابرِ
   `AI_MAX_CONCURRENT_CALLS` پلتفرم. شمارنده‌ها زنده‌اند (`ai_service.slots_for`)، نه تخمین.
۲. فشارِ سرور: بارِ میانگینِ ۱/۵/۱۵ دقیقه به‌ازایِ هر هسته، درصدِ RAMِ استفاده‌شده، و درصدِ
   دیسکِ پوشهٔ داده. همه از `/proc` و `shutil.disk_usage` — هیچ وابستگیِ تازه (مثلِ `psutil`)
   اضافه نشد، چون قاعدهٔ ۱۱ می‌گوید وابستگیِ تازه فقط با ضرورتِ روشن.
۳. استخرِ دیتابیس: چند اتصالِ ساخته‌شده، چندتا درِ کار، چندتا اورفلو — چون گلوگاهِ واقعیِ
   «چند فروشگاهِ هم‌زمان» معمولاً همین‌جاست، نه CPU.

صداقتِ عددی (قاعدهٔ ۱۰): هر عددی که *اندازه‌گیریِ زنده* است با برچسبِ MEASURED و هرچه
آستانه/پیکربندی است با برچسبِ «سقفِ تنظیم‌شده» نوشته می‌شود. هیچ‌جا «ظرفیتِ قطعیِ سرویسِ
ارائه‌دهنده» ادعا نمی‌شود — آن همچنان NOT RUN است (سقفِ واقعیِ ارائه‌دهنده را فقط خودِ
ارائه‌دهنده می‌داند).

هیچ مسیرِ مشتری‌ای این فایل را صدا نمی‌زند و هیچ جملهٔ SQLِ تازه‌ای به مسیرِ پیام اضافه نمی‌کند.
"""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import observability
from app.database.models import AiApiKeyPoolEntry
from app.database.session import engine
from app.services import ai_service

# شمارنده‌هایی که برایِ ادمین معنا دارند؛ بقیه (شمارنده‌هایِ داخلیِ لاگ و…) فهرست را شلوغ می‌کند.
_COUNTER_PREFIXES = ("ai.", "webhook.", "telegram.", "bale.", "wallet.", "shop.", "metrics.")
_DISK_PATH = "/backups"
# هر شمارنده یکِ برچسبِ فارسی دارد تا در صفحه هیچ کلمهٔ انگلیسیِ قاطیِ فارسی نیفتد؛
# شمارندهٔ ناشناخته با همان نامِ فنی نشان داده می‌شود تا چیزی پنهان نشود.
_COUNTER_LABELS = {
    "webhook.main": "رویدادِ رباتِ مرکزی",
    "webhook.shop": "رویدادِ رباتِ فروشگاهی",
    "webhook.duplicate": "رویدادِ تکراریِ ردشده",
    "webhook.rejected": "رویدادِ نامعتبرِ ردشده",
    "webhook.rate_limited": "محدودِ نرخِ وب‌هوک",
    "webhook.instagram": "رویدادِ اینستاگرام",
    "webhook.instagram.unknown": "رویدادِ ناشناختهٔ اینستاگرام",
    "shop.update": "بروزرسانیِ رباتِ فروشگاهی",
    "wallet.deduct": "برداشتِ کیف‌پول (تومان)",
    "wallet.deduct_denied": "ردِ برداشتِ کیف‌پول",
    "metrics.denied": "درخواستِ ردشدهٔ متریک",
}


@dataclass(frozen=True)
class KeyLoad:
    label: str
    cap: int
    inflight: int

    @property
    def percent(self) -> float:
        return (self.inflight / self.cap * 100.0) if self.cap else 0.0


def _read_loadavg() -> tuple[float, float, float] | None:
    try:
        with open("/proc/loadavg", encoding="ascii") as handle:
            parts = handle.read().split()
        return float(parts[0]), float(parts[1]), float(parts[2])
    except (OSError, ValueError, IndexError):
        return None


def _read_memory() -> tuple[int, int] | None:
    """(کلِ RAM، RAMِ آزاد‌مانده) به بایت؛ از MemTotal و MemAvailable."""
    try:
        values: dict[str, int] = {}
        with open("/proc/meminfo", encoding="ascii") as handle:
            for line in handle:
                name, _, rest = line.partition(":")
                values[name.strip()] = int(rest.strip().split()[0]) * 1024
        total, available = values.get("MemTotal"), values.get("MemAvailable")
        return (total, available) if total and available is not None else None
    except (OSError, ValueError, IndexError):
        return None


def _disk_target() -> tuple[str, str]:
    """(مسیر، برچسبِ فارسی) — مسیرِ خام در متن نشان داده نمی‌شود."""
    if os.path.isdir(_DISK_PATH):
        return _DISK_PATH, "بکاپ‌ها"
    return "/", "ریشه"


def _disk_usage() -> tuple[int, int] | None:
    path, _label = _disk_target()
    try:
        usage = shutil.disk_usage(path)
        return usage.total, usage.free
    except OSError:
        return None


def system_lines() -> dict[str, object]:
    cores = os.cpu_count() or 1
    load = _read_loadavg()
    memory = _read_memory()
    disk = _disk_usage()
    return {
        "cores": cores,
        "load1": load[0] if load else None,
        "load5": load[1] if load else None,
        "load15": load[2] if load else None,
        "load_percent": (load[0] / cores * 100.0) if load else None,
        "memory_used_percent": ((memory[0] - memory[1]) / memory[0] * 100.0) if memory else None,
        "disk_used_percent": ((disk[0] - disk[1]) / disk[0] * 100.0) if disk else None,
        "disk_label": _disk_target()[1],
    }


def db_pool_lines() -> dict[str, object]:
    """وضعیتِ استخرِ SQLAlchemy — بدونِ هیچ کوئری (فقط شمارنده‌هایِ درونِ استخر)."""
    pool = engine.sync_engine.pool
    size = int(getattr(pool, "size", lambda: 0)())
    checked_out = int(pool.checkedout())
    overflow = int(pool.overflow())
    capacity = max(1, size + int(getattr(pool, "_max_overflow", 0)))
    return {
        "size": size,
        "checked_out": checked_out,
        "overflow": overflow,
        "capacity": capacity,
        "percent": min(100.0, checked_out / capacity * 100.0),
    }


def counters_lines() -> list[tuple[str, int]]:
    snapshot = observability.snapshot()
    return [
        (_COUNTER_LABELS.get(name, name), value)
        for name, value in sorted(snapshot.items())
        if name.startswith(_COUNTER_PREFIXES)
    ]


def _capability_of(entry: AiApiKeyPoolEntry) -> str:
    value = entry.capability
    return value.value if hasattr(value, "value") else str(value)


async def ai_lines(session: AsyncSession) -> dict[str, object]:
    """بارِ زندهٔ هرِ کلید + جمعِ سقف‌ها در برابرِ سقفِ پلتفرم.

    دو نکته تا عددِ پنل با عددِ واقعیِ governor یکی بماند:
    ۱. فرمولِ سقفِ هرِ کلید **همان** `ai_pool_service.capacity_report` است (کلیدِ بی‌عدد =
       سهمِ مساوی از سقفِ پلتفرم).
    ۲. استخرها در سرویس **به‌ازایِ قابلیت** ساخته می‌شوند (`chat` و `both` در استخرِ پاسخِ
       متنی/کامنت، `stt` در استخرِ صوت) ⇒ سهمِ مساوی هم به‌ازایِ هرِ گروه حساب می‌شود و کلیدهایِ
       صوت در عددِ «ظرفیتِ پاسخِ مشتری» شمرده نمی‌شوند؛ برایِ همان‌ها یکِ خطِ جدا ساخته می‌شود.
    """
    entries = (
        await session.execute(
            select(AiApiKeyPoolEntry)
            .where(AiApiKeyPoolEntry.is_active.is_(True))
            .order_by(AiApiKeyPoolEntry.id)
        )
    ).scalars().all()
    ceiling = ai_service.platform_ceiling()
    chat = [entry for entry in entries if _capability_of(entry) in ("chat", "both")]
    voice = [entry for entry in entries if _capability_of(entry) == "stt"]

    def _loads(group: list[AiApiKeyPoolEntry]) -> list[KeyLoad]:
        share = ai_service.equal_share_cap(ceiling, len(group))
        return [
            KeyLoad(
                label=entry.label or f"کلید {entry.id}",
                cap=max(1, int(entry.max_concurrent) if entry.max_concurrent else share),
                inflight=ai_service.slots_for(entry.id).inflight,
            )
            for entry in group
        ]

    loads = _loads(chat)
    voice_loads = _loads(voice)
    sum_caps = sum(load.cap for load in loads)
    usable = min(sum_caps, ceiling) if sum_caps else 0
    inflight_total = sum(load.inflight for load in loads)
    return {
        "keys": loads,
        "sum_caps": sum_caps,
        "platform_ceiling": ceiling,
        "usable": usable,
        "inflight_total": inflight_total,
        "percent": (inflight_total / usable * 100.0) if usable else 0.0,
        "bottleneck": "keys" if sum_caps and sum_caps < ceiling else "platform",
        "voice": {
            "count": len(voice_loads),
            "sum_caps": sum(load.cap for load in voice_loads),
            "inflight": sum(load.inflight for load in voice_loads),
        },
    }


async def snapshot(session: AsyncSession) -> dict[str, object]:
    return {"ai": await ai_lines(session), "db": db_pool_lines(), "system": system_lines(), "counters": counters_lines()}
