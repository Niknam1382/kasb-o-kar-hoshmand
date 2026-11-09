"""P45 · ظرفیت: نقشِ هر پروسه و شاردِ آن.

چرا لازم شد: سقفِ واقعیِ «چند فروشگاه رویِ یکِ پروسه» رم و تعدادِ socket است، نه دیتابیس
(MEASURED: ~۰٫۴–۰٫۷ مگابایت و یکِ سوکتِ ۲۰ ثانیه‌ای به‌ازایِ هر ربات). راهِ رسیدن به ۱٬۵۰۰ فروشگاه
و ~۱٬۰۰۰ مشتریِ هم‌زمان، تقسیمِ *کار* بینِ پروسه‌هاست، نه سرورِ قوی‌ترِ تنها.

سه نقش (متغیرِ محیطی `APP_ROLE`؛ پیش‌فرض `all` = رفتارِ کاملِ امروز در یکِ پروسه):
· `core`  → رباتِ مرکزی (پنلِ صاحبِ کسب‌وکار)، جاب‌ها، صفِ اعلان، pollingِ بله‌پی، `/health`.
· `poller`→ فقط ربات‌هایِ فروشگاهیِ شاردِ خودش (`shop_bot_id % SHARD_COUNT == SHARD_INDEX`).
· `web`   → فقط دریافتِ webhook (هیچ socketِ بازِ بلندمدتی ندارد؛ برایِ وقتی که HTTPS داری).
· `all`   → همهٔ بالا در یکِ پروسه.

دو قانونِ ایمنی که این ماژود نگه می‌دارد:
۱) هر فروشگاه فقط و فقط در یکِ پروسه polling می‌شود (تقسیمِ شارد + قفلِ advisoryِ *به‌ازایِ هر
   شارد*). اگر دو پروسه با یکِ شارد بالا بیایند، دومی هیچ getUpdates‌ای شروع نمی‌کند.
۲) کارهایِ «یک‌بار در کلِ سرویس» (جاب‌ها، اعلان‌ها، بله‌پیِ مرکزی، پنلِ مرکزی) رویِ یکِ پروسه
   می‌مانند؛ تقسیمِ آن‌ها بینِ پروسه‌ها یعنی گزارش/یادآوریِ دوباره.
"""

from __future__ import annotations

from app.config import RunMode, settings

CORE = "core"
POLLER = "poller"
WEB = "web"
ALL = "all"
ROLES: frozenset[str] = frozenset({CORE, POLLER, WEB, ALL})


def role() -> str:
    raw = (settings.app_role or ALL).strip().lower()
    return raw if raw in ROLES else ALL


def is_core() -> bool:
    """پنلِ مرکزی + جاب‌ها + اعلان‌ها + pollingِ بله‌پیِ مرکزی."""
    return role() in (CORE, ALL)


def is_poller() -> bool:
    """ربات‌هایِ فروشگاهیِ این شارد (در حالتِ polling)."""
    return role() in (POLLER, ALL)


def is_web() -> bool:
    """پروسهٔ «فقط HTTP» (بدونِ هیچ pollingِ فروشگاه). در لایهٔ ۳-وب چندتا از این بالا می‌آید."""
    return role() == WEB


def serves_http() -> bool:
    """این پروسه اپِ HTTP (وب‌هوک‌ها + `/health`) را سرو می‌کند؟

    در حالتِ polling جز نقشِ `web` چیزی سرو نمی‌کند (هر پروسه یکِ اپِ سلامتِ کوچکِ جدا دارد)؛
    در حالتِ webhook همهٔ پروسه‌هایی که وب‌هوک می‌گیرند این مسیر می‌روند."""
    return settings.run_mode == RunMode.WEBHOOK or is_web()


def shard_index() -> int:
    count = max(1, int(settings.shard_count or 1))
    return int(settings.shard_index or 0) % count


def shard_count() -> int:
    return max(1, int(settings.shard_count or 1))


def owns_shard(shop_bot_id: int) -> bool:
    return shop_bot_id % shard_count() == shard_index()


def lock_key(base: int) -> int:
    """کلیدِ قفلِ advisory برایِ این پروسه. با `SHARD_COUNT=1` عدد عوض نمی‌شود ⇒ قفل‌هایِ امروز
    (۲۰۲۶۱۱۰۳ و ۲۰۲۶۱۱۰۴) دقیقاً همان‌ها می‌مانند. با شارد، هر شارد قفلِ خودش را دارد و دو
    پروسهٔ هم‌شارد باز هم همدیگر را مهار می‌کنند."""
    count = shard_count()
    if count <= 1:
        return base
    return base * 100 + shard_index()


def describe() -> str:
    return f"role={role()} shard={shard_index()}/{shard_count()}"
