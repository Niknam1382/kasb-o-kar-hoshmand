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
import logging
import time
from dataclasses import dataclass

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from app import observability
from app.config import settings
from app.services import capacity_service
from app.utils.validators import fa_number, fa_percent

logger = logging.getLogger(__name__)

ERROR = "error"
WARN = "warn"
INFO = "info"

SEVERITY_ICON = {ERROR: "🔴", WARN: "🟠", INFO: "🔵"}

# آستانه‌ها: عمداً در همین فایل‌اند تا با عددِ پنلِ ظرفیت یکی بمانند و در تستِ ۱ قفل شوند.
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

_TELEGRAM_MARKERS = ("telegramnetworkerror", "timed out", "timeout", "network is unreachable", "cannot connect to host")
_AI_FAILURE_MARKERS = ("کلیدِ ai", "کلید ai", "ai service error", "صفِ درخواست‌هایِ اینِ کلید")

ALERT_COOLDOWN_SECONDS = 60 * 60
_last_alert_at: dict[str, float] = {}


@dataclass(frozen=True)
class Finding:
    key: str
    severity: str
    title: str
    detail: str
    suggestion: str


def reset_alert_clock_for_tests() -> None:
    """فقط برایِ تست: خنک‌کردنِ هشدارها صفر می‌شود."""
    _last_alert_at.clear()


def _log_matches(rows: list[dict], markers: tuple[str, ...]) -> int:
    """چند ردیفِ لاگ یکی ازِ نشانه‌ها را دارد (پیام + استک‌تریس، بی‌توجهیِ بزرگ/کوچکیِ حرف‌ها)."""
    hits = 0
    for row in rows:
        haystack = f"{row.get('msg', '')} {row.get('exc', '')}".lower()
        if any(marker in haystack for marker in markers):
            hits += 1
    return hits


def _thresholds(system: dict, db: dict, ai: dict) -> list[Finding]:
    findings: list[Finding] = []
    disk = system["disk_used_percent"]
    if disk is not None and disk >= DISK_ALERT_PERCENT:
        findings.append(
            Finding(
                "disk", ERROR, "دیسکِ بکاپ پر است",
                f"مصرفِ دیسکِ «{system['disk_label']}»: {fa_percent(disk)} (آستانه {fa_percent(DISK_ALERT_PERCENT)}).",
                "مهلتِ نگهداریِ بکاپ را در «⚙️ تنظیماتِ کلیدها» کم کن یا فایل‌هایِ قدیمی را "
                "از رویِ سرور بردار؛ تا پر شدنِ دیسک، بکاپِ بعدی و فاکتورها می‌ایستند.",
            )
        )
    memory = system["memory_used_percent"]
    if memory is not None and memory >= MEMORY_ALERT_PERCENT:
        findings.append(
            Finding(
                "memory", WARN, "رمِ سرور رو به اتمام است",
                f"رمِ استفاده‌شده: {fa_percent(memory)} (آستانه {fa_percent(MEMORY_ALERT_PERCENT)}).",
                "اگر همزمانِ درخواست‌ها بالا رفته، سقفِ همزمانیِ AI را از «🔑 استخرِ کلیدهایِ AI» "
                "کم کن؛ هر درخواستِ باز یکِ تکه رم است.",
            )
        )
    load_percent = system["load_percent"]
    if load_percent is not None and load_percent >= LOAD_ALERT_PERCENT:
        findings.append(
            Finding(
                "load", WARN, "پردازنده زیرِ فشار است",
                f"بارِ میانگینِ ۱ دقیقه {fa_percent(load_percent)} ظرفیتِ "
                f"{fa_number(system['cores'])} هسته است (آستانه {fa_percent(LOAD_ALERT_PERCENT)}).",
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
    if db["percent"] >= DB_POOL_ALERT_PERCENT:
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
    elif ai["percent"] >= AI_PRESSURE_ALERT_PERCENT:
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


def _log_findings(ai_failure_logs: int, telegram_logs: int, error_count: int) -> list[Finding]:
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
    if ai_failure_logs >= AI_FAILURE_LOGS_ALERT:
        findings.append(
            Finding(
                "ai_failures", WARN, "کلیدهایِ AI پاسخ نمی‌دهند",
                f"{fa_number(ai_failure_logs)} ردیفِ لاگ دربارهٔ شکست/مدارِ قطعِ کلیدِ AI.",
                "کلیدِ خراب خودکار کنارِ گذاشته می‌شود؛ اگر همه همین‌طورند، به «🔑 استخرِ "
                "کلیدهایِ AI» سر بزن و اعتبار/آدرسِ همان کلید را درست کن.",
            )
        )
    if error_count >= LOG_ERRORS_ALERT:
        findings.append(
            Finding(
                "log_errors", WARN, "خطاهایِ تازه در لاگِ همین پروسه",
                f"{fa_number(error_count)} ردیفِ ERROR/CRITICAL در حافظهٔ لاگ.",
                "با «🧾 لاگِ سرور» متنِ کامل را ببین (این‌جا فقط دسته‌بندی آمده).",
            )
        )
    return findings


def _counter_findings(counters: dict[str, int]) -> list[Finding]:
    findings: list[Finding] = []
    rejected = counters.get("webhook.rejected", 0)
    if rejected >= WEBHOOK_REJECTED_ALERT:
        findings.append(
            Finding(
                "webhook_rejected", WARN, "وب‌هوک‌هایِ ردشده زیاد است",
                f"{fa_number(rejected)} رویداد از شروعِ این پروسه به‌خاطرِ نامعتبربودن رد شده است.",
                "اگر اخیراً دامنه/توکن عوض شده، آدرسِ وب‌هوک و کلیدِ احراز را در تنظیماتِ "
                "سرور تطبیق بده؛ رد شدنِ همهٔ رویدادها یعنی ربات چیزی دریافت نمی‌کند.",
            )
        )
    rate_limited = counters.get("webhook.rate_limited", 0)
    if rate_limited >= WEBHOOK_RATE_LIMIT_ALERT:
        findings.append(
            Finding(
                "webhook_rate_limited", INFO, "سقفِ نرخِ وب‌هوک خورده شده",
                f"{fa_number(rate_limited)} رویداد به‌خاطرِ سقفِ نرخِ محافظتی رد شده است.",
                "یا ترافیکِ واقعی بالاست یا عددِ `webhook_rate_limit_per_minute` "
                "(پیش‌فرض ۶۰۰ در دقیقه) برایِ این حجم کم است.",
            )
        )
    denied = counters.get("wallet.deduct_denied", 0)
    if denied >= WALLET_DENIAL_ALERT:
        findings.append(
            Finding(
                "wallet_denied", INFO, "چند بار کیف‌پولِ فروشگاه‌ها کافی نبوده",
                f"{fa_number(denied)} برداشتِ ردشده از شروعِ این پروسه.",
                "به فروشگاه‌دارها یادآوریِ شارژ بفرست؛ این یعنی پاسخِ AI آن‌ها در همان لحظه "
                "ساخته نشده است.",
            )
        )
    return findings


async def inspect(session: AsyncSession) -> list[Finding]:
    """یکِ دورِ کاملِ بازرسی — فقط‌خواندنی، بی‌هیچ نوشتنِ جدیدی."""
    system = capacity_service.system_lines()
    db = capacity_service.db_pool_lines()
    ai = await capacity_service.ai_lines(session)
    counters = dict(capacity_service.counters_lines())
    log_counts = observability.recent_log_counts()
    rows = observability.recent_logs(view="warnings", limit=300)
    findings = _thresholds(system, db, ai)
    findings += _log_findings(
        _log_matches(rows, _AI_FAILURE_MARKERS), _log_matches(rows, _TELEGRAM_MARKERS), log_counts["errors"]
    )
    findings += _counter_findings(counters)
    return findings


def alert_text(findings: list[Finding], moment: datetime.datetime) -> str:
    from app.bots.main_bot import texts as main_texts

    return main_texts.doctor_alert_text(findings, moment)


def _ready_to_alert(findings: list[Finding]) -> list[Finding]:
    """یافته‌هایی که تازه‌اند (نه چیزی که همین‌الاخ هشدارش رفته است)."""
    now = time.monotonic()
    fresh = [finding for finding in findings if now - _last_alert_at.get(finding.key, 0.0) >= ALERT_COOLDOWN_SECONDS]
    for finding in fresh:
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
