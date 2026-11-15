"""پ۶۲ · خواستهٔ مالکِ محصول (۲۰۲۶-۱۱-۱۲): «به یکِ ایجنتِ در حالِ کار در محیطِ سرور برایِ
لاگ‌ها و بررسیِ مشکلات نیاز دارم».

این فایل همان ایجنت است، با دو قیدِ آگاهانه:

۱) **قوانینِ ثابت، نه هوشِ مصنوعی.** هر تشخیص از اعدادِ زنده (`capacity_service`) و از بافرِ
   لاگِ خودش (`observability.recent_logs`) ساخته می‌شود. فراخوانِ AI برایِ «تحلیلِ لاگ» هم
   هزینه دارد و هم نتیجه‌اش هر دو بار فرق می‌کند؛ برایِ «چرا سرور خوابید» عددِ دقیق لازم است،
   نه متنِ قشنگ. اگر بعداً تحلیلِ زبانی خواسته شد، باید مثلِ خلاصهٔ CRM با تایید و هزینهٔ
   نمایش‌داده‌شده باشد.
۲) **هیچ اقدامی نمی‌کند.** خروجی فقط «یافت شد + اینجا اقدام کن» است. ری‌استارت، پاک‌کردنِ
   فایل، تغییرِ تنظیمات یا خاموش‌کردنِ جاب همه از همان دکمه‌هایِ موجودِ پنلِ ادمین انجام
   می‌شوند و در ممیزی ثبت می‌شوند؛ این ایجنت هیچ‌کدام را خودش فشار نمی‌دهد.

اجرایِ دوره‌ای: داخلِ `scheduler._run_periodic_pass_locked` (هر ~۳۰ دقیقه، زیرِ قفلِ advisoryِ
دیتابیس ⇒ با چند نسخهٔ اپ هم دوباره‌ارسال نمی‌شود) و با دروازهٔ `job_gate_service` در گروهِ
`doctor` ⇒ ادمین می‌تواند از همان صفحهٔ «⏱ اعتبار و زمان» خاموشش کند. برایِ هرِ شناسهٔ یافته یکِ
خنک‌کردنِ یک‌ساعته دارد تا هشدارِ تکراری صفِ ادمین را پر نکند.

هزینه: یکِ `SELECT` رویِ استخرِ کلیدها (همان که پنلِ ظرفیت می‌زند) + خواندنِ `/proc` و شمارنده‌هایِ
درون‌پردازه‌ای. مسیرِ پیامِ مشتری دست‌نخورده است.
"""
from __future__ import annotations

import datetime
import json
import logging
import time
from dataclasses import dataclass

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from app import observability
from app.config import settings
from app.services import capacity_service
from app.services.admin_settings_service import get_admin_settings
from app.utils.validators import fa_number, fa_percent

PERSIAN_DIGITS = {"۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4", "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9"}
ARABIC_DIGITS = {"٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4", "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9"}

logger = logging.getLogger(__name__)

ERROR = "error"
WARN = "warn"
INFO = "info"

SEVERITY_ICON = {ERROR: "🔴", WARN: "🟠", INFO: "🔵"}

# پیش‌فرض‌ها همان عددِ پ۶۲ است تا با پنلِ ظرفیت یکی بماند و در تستِ ۱ قفل شود.
# پ۷۲: این‌ها دیگر ثابتِ غیرقابلِ تغییر نیستند؛ هر کدام کلید، پیش‌فرض، کران و نوع دارد و
# ادمین از «⚖️ آستانه‌هایِ عیب‌یاب» عوضشان می‌کند (ذخیره در `admin_settings.doctor_thresholds`).
DISK_ALERT_PERCENT = 85.0
MEMORY_ALERT_PERCENT = 90.0
LOAD_ALERT_PERCENT = 150.0
DB_POOL_ALERT_PERCENT = 90.0
AI_PRESSURE_ALERT_PERCENT = 80.0
WEBHOOK_REJECTED_ALERT = 20
WEBHOOK_RATE_LIMIT_ALERT = 50
WALLET_DENIAL_ALERT = 5
LOG_ERRORS_ALERT = 5
AI_FAILURE_LOGS_ALERT = 3
WINDOW_MINUTES_DEFAULT = 60

# کلید → (پیش‌فرض، کرانِ پایین، کرانِ بالا، نوع، برچسبِ فارسی)
THRESHOLD_SPECS: dict[str, tuple[float, float, float, str, str]] = {
    "disk_percent": (DISK_ALERT_PERCENT, 50.0, 99.0, "percent", "🗄 دیسکِ بکاپ"),
    "memory_percent": (MEMORY_ALERT_PERCENT, 50.0, 99.0, "percent", "🧠 رمِ سرور"),
    "load_percent": (LOAD_ALERT_PERCENT, 50.0, 500.0, "percent", "⚙️ بارِ پردازنده"),
    "db_pool_percent": (DB_POOL_ALERT_PERCENT, 50.0, 100.0, "percent", "🔌 استخرِ اتصالِ دیتابیس"),
    "ai_pressure_percent": (AI_PRESSURE_ALERT_PERCENT, 20.0, 100.0, "percent", "🤖 فشارِ ظرفیتِ AI"),
    "ai_failures": (float(AI_FAILURE_LOGS_ALERT), 1.0, 1000.0, "count", "🔑 شکستِ کلیدِ AI"),
    "log_errors": (float(LOG_ERRORS_ALERT), 1.0, 1000.0, "count", "🧾 خطایِ تازهٔ لاگ"),
    "webhook_rejected": (float(WEBHOOK_REJECTED_ALERT), 1.0, 100000.0, "count", "📮 وب‌هوکِ ردشده"),
    "webhook_rate_limited": (float(WEBHOOK_RATE_LIMIT_ALERT), 1.0, 100000.0, "count", "🚦 سقفِ نرخِ وب‌هوک"),
    "wallet_denied": (float(WALLET_DENIAL_ALERT), 1.0, 100000.0, "count", "💸 برداشتِ ردشده"),
    "window_minutes": (float(WINDOW_MINUTES_DEFAULT), 5.0, 1440.0, "count", "⏱ پنجرهٔ شمارنده‌ها"),
}
THRESHOLD_KEYS: tuple[str, ...] = tuple(THRESHOLD_SPECS)


def defaults() -> dict[str, float]:
    return {key: spec[0] for key, spec in THRESHOLD_SPECS.items()}


def parse_thresholds(raw: str | None) -> dict[str, float]:
    """`admin_settings.doctor_thresholds` ⇒ نگاشتِ کاملِ آستانه‌ها. خراب/ناشناخته ⇒ پیش‌فرض."""
    values = defaults()
    if not raw:
        return values
    try:
        loaded = json.loads(raw)
    except (ValueError, TypeError):
        return values
    if not isinstance(loaded, dict):
        return values
    for key, spec in THRESHOLD_SPECS.items():
        if key not in loaded:
            continue
        try:
            number = float(loaded[key])
        except (TypeError, ValueError):
            continue
        values[key] = min(spec[2], max(spec[1], number))
    return values


def dump_thresholds(values: dict[str, float]) -> str | None:
    """همه پیش‌فرض ⇒ None (ستونِ خالی)؛ وگرنه فقط تفاوت‌ها ذخیره می‌شود."""
    base = defaults()
    changed = {key: values[key] for key in THRESHOLD_KEYS if values.get(key, base[key]) != base[key]}
    if not changed:
        return None
    return json.dumps(changed, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def parse_input(key: str, text: str | None) -> float | None:
    """ورودیِ ادمین ⇒ عددِ کراندار؛ بیرونِ کران ⇒ None.

    ممیز: رقمِ جلالی/عربی یا لاتین با «.» و «٫»؛ ویرگول (نیمه‌تمام و لاتین) جداکنندهٔ هزار است، پس
    «۱,۵۰۰» همان ۱۵۰۰ خوانده می‌شود نه ۱.۵ — برایِ همین آستانهٔ اعشاری را با نقطه بنویسند.
    """
    raw = (text or "").strip().replace(",", "").replace("٬", "").replace("٫", ".").replace(" ", "")
    if not raw:
        return None
    latin = "".join(PERSIAN_DIGITS.get(ch, ARABIC_DIGITS.get(ch, ch)) for ch in raw)
    if not latin.isascii():
        return None
    try:
        number = float(latin)
    except ValueError:
        return None
    _default, low, high, _kind, _label = THRESHOLD_SPECS[key]
    return number if low <= number <= high else None


def window_deltas(counters: dict[str, int], minutes: int) -> tuple[dict[str, int], str]:
    """پ۷۲: شمارنده‌ها «از شروعِ پروسه» جمع می‌شوند؛ برایِ قضاوتِ «الان بد است یا نه» تفاضلِ
    پنجره لازم است. اگر از آخرین snapshot بیشتر از دو پنجره گذشته باشد (جاب خاموش بوده یا
    تازه روشن شده) تفاضل معنی ندارد ⇒ جمعِ کل با برچسبِ خودش."""
    now = time.monotonic()
    previous = dict(_counter_state.get("values") or {})
    previous_at = _counter_state.get("at")
    _counter_state["values"] = dict(counters)
    _counter_state["at"] = now
    window_seconds = max(60.0, minutes * 60.0)
    if previous_at is None or now - previous_at > 2 * window_seconds:
        return dict(counters), "از شروعِ این پروسه"
    deltas = {name: max(0, int(counters.get(name, 0) - previous.get(name, 0))) for name in counters}
    span_minutes = max(1, int(round((now - previous_at) / 60.0)))
    return deltas, f"در {fa_number(span_minutes)} دقیقهٔ گذشته"

_TELEGRAM_MARKERS = ("telegramnetworkerror", "timed out", "timeout", "network is unreachable", "cannot connect to host")
_AI_FAILURE_MARKERS = ("کلیدِ ai", "کلید ai", "ai service error", "صفِ درخواست‌هایِ اینِ کلید")

ALERT_COOLDOWN_SECONDS = 60 * 60
_last_alert_at: dict[str, float] = {}
_counter_state: dict[str, object] = {}


@dataclass(frozen=True)
class Finding:
    key: str
    severity: str
    title: str
    detail: str
    suggestion: str


def reset_alert_clock_for_tests() -> None:
    """فقط برایِ تست: خنک‌کردنِ هشدارها و snapshotِ پنجره صفر می‌شود."""
    _last_alert_at.clear()
    _counter_state.clear()


def _log_matches(rows: list[dict], markers: tuple[str, ...]) -> int:
    """چند ردیفِ لاگ یکی ازِ نشانه‌ها را دارد (پیام + استک‌تریس، بی‌توجهیِ بزرگ/کوچکیِ حرف‌ها)."""
    hits = 0
    for row in rows:
        haystack = f"{row.get('msg', '')} {row.get('exc', '')}".lower()
        if any(marker in haystack for marker in markers):
            hits += 1
    return hits


def _thresholds(system: dict, db: dict, ai: dict, limits: dict[str, float]) -> list[Finding]:
    findings: list[Finding] = []
    disk = system["disk_used_percent"]
    if disk is not None and disk >= limits["disk_percent"]:
        findings.append(
            Finding(
                "disk", ERROR, "دیسکِ بکاپ پر است",
                f"مصرفِ دیسکِ «{system['disk_label']}»: {fa_percent(disk)} (آستانه {fa_percent(limits["disk_percent"])}).",
                "مهلتِ نگهداریِ بکاپ را در «⚙️ تنظیماتِ کلیدها» کم کن یا فایل‌هایِ قدیمی را "
                "از رویِ سرور بردار؛ تا پر شدنِ دیسک، بکاپِ بعدی و فاکتورها می‌ایستند.",
            )
        )
    memory = system["memory_used_percent"]
    if memory is not None and memory >= limits["memory_percent"]:
        findings.append(
            Finding(
                "memory", WARN, "رمِ سرور رو به اتمام است",
                f"رمِ استفاده‌شده: {fa_percent(memory)} (آستانه {fa_percent(limits["memory_percent"])}).",
                "اگر همزمانِ درخواست‌ها بالا رفته، سقفِ همزمانیِ AI را از «🔑 استخرِ کلیدهایِ AI» "
                "کم کن؛ هر درخواستِ باز یکِ تکه رم است.",
            )
        )
    load_percent = system["load_percent"]
    if load_percent is not None and load_percent >= limits["load_percent"]:
        findings.append(
            Finding(
                "load", WARN, "پردازنده زیرِ فشار است",
                f"بارِ میانگینِ ۱ دقیقه {fa_percent(load_percent)} ظرفیتِ "
                f"{fa_number(system['cores'])} هسته است (آستانه {fa_percent(limits["load_percent"])}).",
                "صفِ طولانی‌تر از هسته‌ها یعنی درخواست‌ها منتظر می‌مانند؛ اول ببین گلوگاه "
                "«🗄 دیتابیس» است یا خودِ پردازنده («📡 ظرفیت و فشارِ سرور»).",
            )
        )
    if load_percent is None:
        findings.append(
            Finding(
                "proc", INFO, "فشارِ سرور در این محیط خوانده نمی‌شود",
                "فایل‌هایِ /proc در دسترس نبودند (مثلاً اجرایِ مستقیم رویِ ویندوز) ⇒ اعدادِ "
                "بار/رم در پنل نیستند، نه اینکه صفرند.",
                "برایِ دیدنِ اعدادِ واقعی، ربات را داخلِ کانتینرِ لینوکس اجرا کن.",
            )
        )
    if db["percent"] >= limits["db_pool_percent"]:
        findings.append(
            Finding(
                "db_pool", WARN, "اتصال‌هایِ دیتابیس دارد تمام می‌شود",
                f"{fa_number(db['checked_out'])} اتصالِ در کار از {fa_number(db['capacity'])} "
                f"({fa_percent(db['percent'])}) · اتصال‌هایِ اضافه {fa_number(db['overflow'])}.",
                "این گلوگاهِ کلاسیکِ «چند فروشگاهِ هم‌زمان» است: یا استخر را در تنظیماتِ اتصال "
                "بزرگ‌تر کن، یا کوئری‌هایِ کند را از «🧾 لاگِ سرور» پیدا کن.",
            )
        )
    if not ai["keys"]:
        findings.append(
            Finding(
                "ai_keys", ERROR, "هیچِ کلیدِ فعالی برایِ پاسخِ متنی نیست",
                "استخرِ کلیدها خالی است (یا همه غیرفعال‌اند) ⇒ هیچ رباتِ فروشگاهی جوابِ هوشمند "
                "نمی‌دهد.",
                "از «🔑 استخرِ کلیدهایِ AI» حداقل یکِ کلیدِ فعال با قابلیتِ چت اضافه کن.",
            )
        )
    elif ai["percent"] >= limits["ai_pressure_percent"]:
        bottleneck = "جمعِ سقفِ کلیدها" if ai["bottleneck"] == "keys" else "سقفِ پلتفرم"
        where = (
            "سقفِ همزمانیِ همان کلیدها را از «🔑 استخرِ کلیدهایِ AI» بالا ببر"
            if ai["bottleneck"] == "keys"
            else "عددِ AI_MAX_CONCURRENT_CALLS در `.env` باید بالا برود (بعد ازِ ری‌استارت)"
        )
        findings.append(
            Finding(
                "ai_pressure", WARN, "ظرفیتِ هوشِ مصنوعی دارد پر می‌شود",
                f"{fa_number(ai['inflight_total'])} درخواستِ در حالِ اجرا از "
                f"{fa_number(ai['usable'])} ({fa_percent(ai['percent'])}) · گلوگاه: {bottleneck}.",
                f"درخواست‌هایِ تازه در صف می‌مانند و بعد ازِ مهلتِ صف خطا می‌گیرند؛ {where}.",
            )
        )
    return findings


def _log_findings(ai_failure_logs: int, telegram_logs: int, error_count: int, limits: dict[str, float]) -> list[Finding]:
    findings: list[Finding] = []
    if telegram_logs:
        findings.append(
            Finding(
                "telegram_network", ERROR, "رسیدنِ تلگرام/بله اختلال دارد",
                f"{fa_number(telegram_logs)} ردیفِ لاگِ خطایِ شبکه (حافظهٔ همین پروسه).",
                "DNS/اینترنتِ سرور را بررسی کن؛ پیام‌هایِ نرسیده در صفِ اعلان می‌مانند و "
                "خودکار دوباره تلاش می‌شوند (نباید دستی چیزی فرستاد).",
            )
        )
    if ai_failure_logs >= limits["ai_failures"]:
        findings.append(
            Finding(
                "ai_failures", WARN, "کلیدهایِ AI پاسخ نمی‌دهند",
                f"{fa_number(ai_failure_logs)} ردیفِ لاگ دربارهٔ شکست/مدارِ قطعِ کلیدِ AI.",
                "کلیدِ خراب خودکار کنارِ گذاشته می‌شود؛ اگر همه همین‌طورند، به «🔑 استخرِ "
                "کلیدهایِ AI» سر بزن و اعتبار/آدرسِ همان کلید را درست کن.",
            )
        )
    if error_count >= limits["log_errors"]:
        findings.append(
            Finding(
                "log_errors", WARN, "خطاهایِ تازه در لاگِ همین پروسه",
                f"{fa_number(error_count)} ردیفِ ERROR/CRITICAL در حافظهٔ لاگ.",
                "با «🧾 لاگِ سرور» متنِ کامل را ببین (این‌جا فقط دسته‌بندی آمده).",
            )
        )
    return findings


def _counter_findings(counters: dict[str, int], limits: dict[str, float], window_label: str) -> list[Finding]:
    findings: list[Finding] = []
    rejected = counters.get("webhook.rejected", 0)
    if rejected >= limits["webhook_rejected"]:
        findings.append(
            Finding(
                "webhook_rejected", WARN, "وب‌هوک‌هایِ ردشده زیاد است",
                f"{fa_number(rejected)} رویدادِ ردشده به‌خاطرِ نامعتبربودن ({window_label}).",
                "اگر اخیراً دامنه/توکن عوض شده، آدرسِ وب‌هوک و کلیدِ احراز را در تنظیماتِ "
                "سرور تطبیق بده؛ رد شدنِ همهٔ رویدادها یعنی ربات چیزی دریافت نمی‌کند.",
            )
        )
    rate_limited = counters.get("webhook.rate_limited", 0)
    if rate_limited >= limits["webhook_rate_limited"]:
        findings.append(
            Finding(
                "webhook_rate_limited", INFO, "سقفِ نرخِ وب‌هوک خورده شده",
                f"{fa_number(rate_limited)} رویداد به‌خاطرِ سقفِ نرخِ محافظتی رد شده است ({window_label}).",
                "یا ترافیکِ واقعی بالاست یا عددِ `webhook_rate_limit_per_minute` "
                "(پیش‌فرض ۶۰۰ در دقیقه) برایِ این حجم کم است.",
            )
        )
    denied = counters.get("wallet.deduct_denied", 0)
    if denied >= limits["wallet_denied"]:
        findings.append(
            Finding(
                "wallet_denied", INFO, "چند بار کیف‌پولِ فروشگاه‌ها کافی نبوده",
                f"{fa_number(denied)} برداشتِ ردشده ({window_label}).",
                "به فروشگاه‌دارها یادآوریِ شارژ بفرست؛ این یعنی پاسخِ AI آن‌ها در همان لحظه "
                "ساخته نشده است.",
            )
        )
    return findings


async def inspect(session: AsyncSession) -> list[Finding]:
    """یکِ دورِ کاملِ بازرسی — فقط‌خواندنی، بی‌هیچ نوشتنِ جدیدی."""
    limits = parse_thresholds((await get_admin_settings(session)).doctor_thresholds)
    system = capacity_service.system_lines()
    db = capacity_service.db_pool_lines()
    ai = await capacity_service.ai_lines(session)
    # پ۷۹ · دو اصلاحِ مهم: (۱) نامِ خامِ شمارنده (برچسبِ فارسی کلیدِ `webhook.rejected` را هیچ‌وقت
    # پیدا نمی‌کرد ⇒ سه یافتهٔ آستانه‌محور در تولید هرگز شلیک نمی‌شدند)، (۲) جمعِ سهمِ همهٔ پروسه‌ها
    # (بدونِ آن، سرورِ چندworker فقط شمارندهٔ پروسهٔ core را می‌دید).
    counters, processes, stale_rows = await capacity_service.aggregate_counters(session)
    log_counts = observability.recent_log_counts()
    rows = observability.recent_logs(view="warnings", limit=300)
    deltas, window_label = window_deltas(counters, int(limits["window_minutes"]))
    findings = _thresholds(system, db, ai, limits)
    findings += _log_findings(
        _log_matches(rows, _AI_FAILURE_MARKERS),
        _log_matches(rows, _TELEGRAM_MARKERS),
        log_counts["errors"],
        limits,
    )
    findings += _counter_findings(deltas, limits, window_label)
    if stale_rows:
        findings.append(
            Finding(
                "counters.stale_rows",
                WARN,
                f"{fa_number(stale_rows)} پروسهٔ بی‌ضربان",
                "ردیفِ شمارندهٔ اینِ پروسه‌ها از پنجرهٔ اعتبار بیرون افتاده (خاموش یا گیر کرده) و در جمع "
                "شمرده نشده.",
                "اگر تعدادِ پروسه‌هایِ زنده کمتر از چیزی است که انتظار داری (مثلا `docker compose ps`)، "
                "کانتینرِ از‌دست‌رفته را دوباره روشن کن؛ تا آن موقع عددهایِ این گزارش کم‌گویی است.",
            )
        )
    findings.append(
        Finding(
            "counters.scope",
            INFO,
            f"جمعِ شمارنده‌ها: {fa_number(processes)} پروسه",
            "عددِ شمارنده‌هایِ این گزارش سهمِ همهٔ پروسه‌هایِ زنده است، نه فقط پروسهٔ بازبین.",
            "اگر تک‌پروسه‌ای کار می‌کنی همین خط باید «۱ پروسه» بگوید؛ بیشتر یعنی ضربان‌ها می‌رسند.",
        )
    )
    return findings


async def thresholds(session: AsyncSession) -> dict[str, float]:
    """آستانه‌هایِ *موثرِ* همین لحظه (پیش‌فرض + تغییرهایِ ادمین) — برایِ صفحهٔ پنل."""
    return parse_thresholds((await get_admin_settings(session)).doctor_thresholds)


def alert_text(findings: list[Finding], moment: datetime.datetime) -> str:
    from app.bots.main_bot import texts as main_texts

    return main_texts.doctor_alert_text(findings, moment)


def _ready_to_alert(findings: list[Finding]) -> list[Finding]:
    """یافته‌هایی که تازه‌اند (نه چیزی که همین‌الاخ هشدارش رفته است).

    «هیچ‌وقت هشدار نشده» باید `None` باشد، نه `0.0`: `time.monotonic()` از *مبدأِ دلخواهِ
    سیستم‌عامل* شمرده می‌شود و رویِ ماشین/VM تازه‌روشن (کمتر از یکِ ساعت کارکرد) خودش از
    `ALERT_COOLDOWN_SECONDS` کوچک‌تر است ⇒ با sentinelِ صفری، اولین هشدارِ هرِ بوتِ تازه بی‌صدا
    خفه می‌شد (همین باگ در سوئیتِ پ۶۵ پیدا شد).
    """
    now = time.monotonic()
    fresh: list[Finding] = []
    for finding in findings:
        last = _last_alert_at.get(finding.key)
        if last is None or now - last >= ALERT_COOLDOWN_SECONDS:
            fresh.append(finding)
            _last_alert_at[finding.key] = now
    return fresh


async def run(session: AsyncSession, main_bot: Bot, *, force: bool = False) -> dict[str, object]:
    """جابِ دوره‌ای: بازرسی + (فقط اگر موردِ تازه‌ای بود) یکِ خلاصه به ادمین‌ها.

    `force=True` فقط برایِ تست/اجرایِ دستی: خنک‌کردنِ یک‌ساعته را رد می‌کند.
    """
    findings = await inspect(session)
    targets = sorted(settings.admin_ids)
    fresh = findings if force else _ready_to_alert(findings)
    if not fresh:
        return {"findings": len(findings), "sent": 0, "skipped": bool(findings)}
    body = alert_text(fresh, datetime.datetime.now(datetime.timezone.utc))
    sent = 0
    for admin_id in targets:
        try:
            await main_bot.send_message(chat_id=admin_id, text=body)
            sent += 1
        except Exception:  # noqa: BLE001 - هشدارِ عملیاتی نباید جابِ اصلی را بیندازد
            logger.warning("ارسالِ هشدارِ عیب‌یابِ سرور به ادمین %s نگرفته شد.", admin_id)
    logger.info("عیب‌یابِ سرور: %s مورد · %s تازه · به %s ادمین ارسال شد.", len(findings), len(fresh), sent)
    return {"findings": len(findings), "sent": sent, "fresh": len(fresh), "errors": len([f for f in findings if f.severity == ERROR])}
