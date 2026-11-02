"""قابلیتِ مشاهده (P20 · بلاکرِ B1): scrubber، correlation-id، شمارنده‌ها و خروجیِ /metrics.

سه چیز را یک‌جا می‌دهد، بدونِ هیچ سرویسِ تازه‌ای (نه Prometheus، نه Loki، نه Redis):

۱) **پاک‌سازیِ لاگ** — `SecretScrubbingFilter` رویِ root logger می‌نشیند و هرچه شبیهِ راز باشد را
   ماسک می‌کند: توکنِ ربات (`123:ABC…`)، کلیدهایِ `sk-…`/Fernet (`gAAAAA…`)، شمارهٔ موبایلِ ایران،
   کلیدِ `Authorization`، و هر مقدارِ `ENCRYPTION_KEY`/`MAIN_BOT_TOKEN` که از `.env` آمده.
   چرا فیلتر و نه «مراقبِ نوشتنِ لاگ‌ها»: استثنایی که aiohttp/aiogram از متنِ درخواست می‌سازد
   می‌تواند خودش آدرسِ وب‌هوک با راز را در پیامِ استثنا بگذارد — یعنی هر کدِ new می‌تواند این را
   دور بزند. فیلترِ لایهٔ آخر تنها جایِ مطمئن است.

۲) **شناسهٔ همبستگی** — `bind_correlation("…")` در ابتدایِ هر آپدیت/درخواستِ HTTP؛ `fmt()` آن را
   به هر خطِ لاگِ همانِ درخواست اضافه می‌کند ⇒ ردِ «یک پیامِ مشتری» بینِ وب‌هوک، AI، کسرِ کیف‌پول
   و پاسخِ تلگرام در یکِ جستجو.

۳) **شمارنده‌ها** — `count("webhook.rejected")` و… در حافظه؛ `/metrics` (با راز) متنِ سادهٔ
   Prometheus می‌دهد. عمداً histogram/summary نداریم: برایِ «چند کاربرِ فعال هم‌زمان» و هشدارِ
   غیرعادی، شمارنده + لاگِ ساختاریافته کافی است و وابستگیِ تازه لازم ندارد.

`JSON_LOGS=true` ⇒ هر خط یکِ شیءِ JSON (برایِ جمع‌آوریِ خودکارِ لوگ). پیش‌فرض false تا لاگِ `docker compose logs`
همان آدم‌خوانا بماند.
"""

from __future__ import annotations

import contextvars
import json
import logging
import re
import time

_CORRELATION: contextvars.ContextVar[str] = contextvars.ContextVar("correlation_id", default="")
_counters: dict[str, int] = {}
_started_at = time.time()

MAX_CORRELATION_LENGTH = 32

# توکنِ ربات: رقم:حروف/ارقام/[-_] (هم تلگرام هم بله همین شکل‌اند)
_PATTERNS: tuple[re.Pattern[str], ...] = (
    # توکنِ ربات: رقم:حروف/ارقام/[-_] (هم تلگرام هم بله همین شکل‌اند).
    # P21-F: \b اولِ الگو حذف شد — در آدرسِ واقعیِ API («/bot123456789:AA…/sendMessage») بینِ
    # «bot» و رقم‌ها مرزِ کلمه‌ای وجود ندارد، پس الگویِ قبلی دقیقاً در همان محتمل‌ترین جایِ نشت
    # توکن هیچی را ماسک نمی‌کرد.
    re.compile(r"\d{6,}:[A-Za-z0-9_\-]{20,}"),
    re.compile(r"\bsk-[A-Za-z0-9_\-]{10,}\b"),
    re.compile(r"\bgAAAAA[A-Za-z0-9_\-]{10,}"),  # رمزِ Fernet
    re.compile(r"\b(eyJ[A-Za-z0-9_\-]{5,}\.){2}[A-Za-z0-9_\-]{5,}\b"),  # JWT
    re.compile(r"(?<![\d+])(?:\+?98|0098|98|0)?9\d{9}(?!\d)"),  # موبایلِ ایران (0912…، +989…، 989…)
    # P24: شمارهٔ کارت (PAN) — ۱۵/۱۶ رقم، با فاصله یا خط‌تیره. هر logger.exception که مدلِ پرداخت
    # یا رشتهٔ رسید را چاپ کند، کارت را در لاگ می‌ریخت؛ الگوهایِ بالا کارت را نمی‌گرفتند.
    re.compile(r"(?<!\d)(?:\d[ \-]?){14,15}\d(?!\d)"),
    re.compile(r"(?i)\b(authorization|api[_-]?key|secret|token|password)\b\s*[=:]\s*\S+"),
)


def scrub(text: str) -> str:
    """همهٔ شکل‌هایِ راز را به `●…` تبدیل می‌کند. بی‌خطر برایِ متنِ فارسیِ معمولی."""
    out = text
    for pattern in _PATTERNS:
        out = pattern.sub(lambda m: m.group(0)[:3] + "●●●●", out)
    return out


class SecretScrubbingFilter(logging.Filter):
    """فیلترِ root handler — آخرینِ سدِ پیش ازِ بیرون‌رفتنِ متنِ لاگ (و هم‌زمانِ تزریقِ correlation-id)."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.msg = scrub(str(record.msg))
            args = record.args
            if isinstance(args, tuple):
                record.args = tuple(scrub(a) if isinstance(a, str) else a for a in args)
            elif isinstance(args, str):
                record.args = scrub(args)
            correlation = current_correlation()
            record.corr = f" [{correlation}]" if correlation else ""
        except Exception:  # noqa: BLE001 — هیچ‌وقت نباید لاگ‌گیری را بشکند
            record.corr = getattr(record, "corr", "")
        return True


class JsonFormatter(logging.Formatter):
    """یک شیءِ JSON در هر خط (زمان/سطح/لاگر/پیام/correlation/استثنا)."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": scrub(record.getMessage()),
        }
        correlation = current_correlation()
        if correlation:
            payload["corr"] = correlation
        if record.exc_info:
            payload["exc"] = scrub(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False)


class ScrubbingFormatter(logging.Formatter):
    """فیلترِ ساده فقط `msg`/`args` را می‌شَوَرد؛ متنِ استثنا (traceback) بعد ازِ آن به خروجی
    اضافه می‌شود و از فیلتر رد نمی‌شود. P21-F: اینجا کلِ خطِ نهایی دوباره scrub می‌شود، چون
    خطاهایِ شبکه/aiogram می‌توانند آدرسِ کاملِ `bot<token>/sendMessage` را در خودِ متن داشته باشند."""

    def format(self, record: logging.LogRecord) -> str:
        return scrub(super().format(record))


def install(level: str = "INFO", as_json: bool = False) -> None:
    """رویِ root logger بنشین (از main.py فراخوانده می‌شود)."""
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO))
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    for handler in root.handlers:
        if not any(isinstance(f, SecretScrubbingFilter) for f in handler.filters):
            handler.addFilter(SecretScrubbingFilter())
        if as_json:
            handler.setFormatter(JsonFormatter())
        else:
            handler.setFormatter(ScrubbingFormatter(CORRELATION_PLAIN_FORMAT))


CORRELATION_PLAIN_FORMAT = "%(asctime)s %(levelname)s %(name)s%(corr)s: %(message)s"


def bind_correlation(value: str) -> str:
    token = scrub((value or "").strip())[:MAX_CORRELATION_LENGTH]
    _CORRELATION.set(token)
    return token


def current_correlation() -> str:
    return _CORRELATION.get()


def correlate(prefix: str, *parts: object) -> str:
    """`wh:main:8f3a…` — کوتاه، بدونِ راز، قابلِ جستجو."""
    joined = ":".join(str(p) for p in parts if p not in (None, ""))
    return f"{prefix}:{joined}" if joined else prefix


def count(name: str, amount: int = 1) -> None:
    _counters[name] = _counters.get(name, 0) + amount


def snapshot() -> dict[str, int]:
    return dict(sorted(_counters.items()))


def reset_counters() -> None:
    """فقط برایِ تست."""
    _counters.clear()


def render_prometheus() -> str:
    """متنِ سادهٔ /metrics — بدونِ وابستگیِ client-library."""
    lines = [
        "# HELP kasbokar_uptime_seconds عمرِ همینِ نسخهٔ برنامه به ثانیه",
        "# TYPE kasbokar_uptime_seconds gauge",
        f"kasbokar_uptime_seconds {time.time() - _started_at:.1f}",
    ]
    for name, value in sorted(_counters.items()):
        metric = "kasbokar_" + re.sub(r"[^a-zA-Z0-9_]", "_", name)
        lines.append(f"# TYPE {metric} counter")
        lines.append(f"{metric} {value}")
    return "\n".join(lines) + "\n"
