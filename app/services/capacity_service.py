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

import datetime
import json
import os
import shutil
from dataclasses import dataclass

from sqlalchemy import delete as sa_delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app import observability
from app.database.models import AiApiKeyPoolEntry, RuntimeCounterSnapshot
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
    """وضعیتِ استخرِ SQLAlchemy — بدونِ هیچ کوئری (فقط شمارنده‌هایِ درونِ استخر).

    پ۱۰۱: استخرِ بدونِ اندازه (مثلِ `NullPool` که سوئیتِ تست و بعضی استقرارها انتخاب می‌کنند)
    `checkedout()` ندارد ⇒ نباید با AttributeError بمیرد؛ در آن حالت «بدونِ استخر» گزارش می‌شود.
    """
    pool = engine.sync_engine.pool
    if not hasattr(pool, "checkedout"):
        return {"size": 0, "checked_out": 0, "overflow": 0, "capacity": 1, "percent": 0.0, "mode": "null"}
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
        "mode": "pool",
    }


# ------------------------------------------------------------------ پ۷۹ · شمارنده‌هایِ چندپروسه‌ای
SNAPSHOT_STALE_SECONDS = 150  # ردیفِ قدیمی‌تر از این، «پروسهٔ مرده» است و در جمع نمی‌آید
SNAPSHOT_RETENTION_DAYS = 7  # پ۸۳ · پاک‌کردنِ ردیفِ پروسه‌هایی که دیگر هرگز ضربان نمی‌دهند
_counter_started_at: datetime.datetime | None = None


def process_key() -> str:
    """یکتایِ اینِ پروسه: نامِ میزبان (در داکر = نامِ کانتینر) + pid. بدونِ RDB/کشِ تازه."""
    return f"{os.uname().nodename if hasattr(os, 'uname') else os.environ.get('HOSTNAME', '?')}:{os.getpid()}"


def local_counters() -> dict[str, int]:
    """شمارنده‌هایِ عملیاتیِ *همینِ* پروسه با نامِ فنی (برچسبِ فارسی فقط برایِ نمایش ساخته می‌شود)."""
    return {name: value for name, value in observability.snapshot().items() if name.startswith(_COUNTER_PREFIXES)}


async def publish_counters(session: AsyncSession) -> dict[str, object]:
    """ضربانِ اینِ پروسه: یکِ upsert رویِ ردیفِ خودش (نه به‌ازایِ هرِ پیام ⇒ بارِ ناچیز)."""
    global _counter_started_at
    if _counter_started_at is None:
        _counter_started_at = datetime.datetime.now(datetime.timezone.utc)
    payload = json.dumps(local_counters(), sort_keys=True)
    statement = insert(RuntimeCounterSnapshot).values(
        process_key=process_key(), hostname=process_key().split(":")[0][:64], counters=payload,
        started_at=_counter_started_at, updated_at=func.now(),
    )
    await session.execute(statement.on_conflict_do_update(
        index_elements=[RuntimeCounterSnapshot.process_key],
        set_={"counters": statement.excluded.counters, "hostname": statement.excluded.hostname,
              "updated_at": func.now()},
    ))
    totals, processes, stale_rows = await aggregate_counters(session)
    observability.set_peer_summary(processes, stale_rows)
    return {"processes": processes, "stale": stale_rows, "totals": totals}


async def prune_counter_snapshots(session: AsyncSession, *, keep_days: int = SNAPSHOT_RETENTION_DAYS) -> int:
    """حذفِ ردیف‌هایِ بی‌ضربانی که از پنجرهٔ نگهداری بیرون‌اند ⇒ جمعِ شمارنده‌ها کوئریِ رشدکرده نمی‌شود.

    فقط telemetry عملیاتی پاک می‌شود (نه دادهٔ کاربر). `keep_days` بزرگ‌تر از پنجرهٔ اعتبار است، پس هیچ
    ردیفِ «شاید برگردد» حذف نمی‌شود و عددی از جمعِ زنده‌ها کم نمی‌کند.
    """
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=keep_days)
    result = await session.execute(sa_delete(RuntimeCounterSnapshot).where(RuntimeCounterSnapshot.updated_at < cutoff))
    return int(result.rowcount or 0)


async def aggregate_counters(session: AsyncSession) -> tuple[dict[str, int], int, int]:
    """⇒ (جمعِ شمارنده‌ها، پروسه‌هایِ زندهٔ شمرده‌شده، ردیف‌هایِ بی‌اعتبارِ قدیمی).

    سهمِ خودِ اینِ پروسه از *حافظه* خوانده می‌شود (ردیفِ خودش می‌تواند تا یکِ ضربان کهنه باشد)، و
    ردیفِ هرِ پروسهٔ دیگر فقط تا `SNAPSHOT_STALE_SECONDS` اعتبار دارد تا عددِ «مرده» زنده نشود.
    """
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=SNAPSHOT_STALE_SECONDS)
    rows = list(
        (
            await session.execute(
                select(RuntimeCounterSnapshot.process_key, RuntimeCounterSnapshot.counters,
                       RuntimeCounterSnapshot.updated_at)
            )
        ).all()
    )
    own = process_key()
    own_live = local_counters()
    totals: dict[str, int] = dict(own_live)
    live = 1  # خودِ اینِ پروسه همیشه شمرده می‌شود (سهمش از حافظه است)
    stale = 0
    for key, payload, updated_at in rows:
        if key == own:
            continue
        moment = updated_at
        if moment is not None and moment.tzinfo is None:
            moment = moment.replace(tzinfo=datetime.timezone.utc)
        if moment is not None and moment < cutoff:
            stale += 1
            continue
        try:
            values = json.loads(payload or "{}")
        except (TypeError, ValueError):
            stale += 1
            continue
        live += 1
        for name, value in (values or {}).items():
            if isinstance(value, int):
                totals[name] = totals.get(name, 0) + value
    return totals, live, stale


def counters_lines(counters: dict[str, int] | None = None) -> list[tuple[str, int]]:
    snapshot = dict(counters) if counters is not None else local_counters()
    return [
        (_COUNTER_LABELS.get(name, name), int(value))
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
    counters, processes, stale_rows = await aggregate_counters(session)
    return {
        "ai": await ai_lines(session), "db": db_pool_lines(), "system": system_lines(),
        "counters": counters_lines(counters), "processes": processes, "stale_processes": stale_rows,
    }


async def channel_summary(session: AsyncSession, limit: int = 12) -> dict[str, object]:
    """پ۹۱ · خلاصهٔ فقط‌خواندنیِ کانال‌ها برایِ پنلِ وب: چندِ فروشگاه فعال، چندتایشان اینستاگرام/بله دارند.

    هیچ رازی (توکن، کلید، merchant_id) و هیچ دادهٔ مشتری‌ای در خروجی نیست؛ فقط نامِ کاربریِ ربات و
    وضعیت‌ها. `limit` نگهبانِ حجمِ صفحه است، نه سقفِ داده.
    """
    from app.database.models import InstagramAccount, ShopBot

    rows = list(
        (
            await session.execute(
                select(ShopBot.id, ShopBot.bot_username, ShopBot.tenant_mode, ShopBot.is_active)
                .order_by(ShopBot.id)
                .limit(limit)
            )
        ).all()
    )
    shops = [
        {
            "id": int(shop_id),
            "bot_username": username,
            "tenant_mode": (mode.value if hasattr(mode, "value") else str(mode)),
            "status": "فعال" if active else "غیرفعال",
        }
        for shop_id, username, mode, active in rows
    ]
    total_active = (
        await session.execute(select(func.count()).select_from(ShopBot).where(ShopBot.is_active.is_(True)))
    ).scalar_one()
    ig = (await session.execute(select(func.count()).select_from(InstagramAccount))).scalar_one()
    # «چند فروشگاه کانالِ بله دارند» از رویِ *وجودِ* کلید خوانده می‌شود، نه مقدارش (رمزنگاری مهم نیست)
    bale = (
        await session.execute(
            select(func.count())
            .select_from(ShopBot)
            .where(ShopBot.bale_provider_token.is_not(None), ShopBot.bale_provider_token != "")
        )
    ).scalar_one()
    return {
        "shops": shops,
        "total_active_shops": int(total_active),
        "instagram_connections": int(ig),
        "bale_connections": int(bale),
        "shown": len(shops),
        "limit": limit,
    }
