"""گیتِ «پوششِ تنظیمات»: هر فیلدِ `Settings` باید در `.env.example` (یا نسخهٔ داکرش) نوشته باشد.

چرا این گیت لازم شد (پ۱۲۴، آماده‌سازیِ دیپلوی): بازرسیِ دستی نشان داد چند فیلدِ واقعیِ کانفیگ
(استخرِ DB، سقفِ همزمانیِ AI، نقشِ پروسه و شارد، `BACKUP_DIR`، …) در هیچ‌کدام از دو فایلِ نمونه
نیستند — یعنی کسی که از صفر مستقر می‌کند *نمی‌دانست* این اهرم‌ها وجود دارند؛ دقیقاً همان چیزهایی
که برایِ ۵۰۰ فروشگاه لازم‌اند.

بازدیدِ دوم (مهم‌تر): **نامِ متغیرِ محیطی باید همان چیزی باشد که مستندات قول می‌دهند.**
`pydantic-settings` فیلدِ `panel_secret` را با `PANEL_SECRET` می‌خواند، ولی `.env.example`،
راهنمایِ ادمین، پلی‌بوک و کامنتِ خودِ کد همه `WEB_PANEL_SECRET` را نوشته بودند ⇒ استقرارِ طبقِ
دستورالعمل، پنجرهٔ وب را بی‌سروصدا ۴۰۴ می‌کرد (باگِ واقعی؛ با `AliasChoices` رفع شد). برایِ همین
این اسکریپت نام‌هایِ نمونه را با نامی که فیلد *واقعاً* می‌خواند مقایسه می‌کند، نه با نامِ فیلد.

روش (regex، بدونِ اجرایِ کدِ کانفیگ):
۱) فیلدهایِ `app/config.py` ⇒ نام + `validation_alias` (AliasChoices) اگر دارد.
۲) نام‌هایِ پذیرفته‌شدهٔ هر فیلد = آن aliasها، وگرنه NAME بزرگِ خودِ فیلد.
۳) کلیدهایِ `.env.example` و `.env.docker.example` (با `#` یا بی‌`#`، چون رسمِ این فایل‌ها
   کامنت‌کردنِ کلیدِ «خالی‌بگذار=پیش‌فرض» است) ⇒ هر فیلد باید دست‌کم در یکی از دو فایل با یکی از
   نام‌هایِ خودش آمده باشد.
۴) برعکس: کلیدی که در نمونه هست ولی *هیچ‌جایِ* `app/` خوانده نمی‌شود ⇒ کلیدِ مرده یا نامِ اشتباه.

اجرا: python3 scripts/check_env_coverage.py
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONFIG = ROOT / "app" / "config.py"
EXAMPLES = (ROOT / ".env.example", ROOT / ".env.docker.example")

# فیلدهایی که عمداً بی‌مستند می‌مانند (اگر روزی لازم شد، با دلیل این‌جا فهرست شود).
ALLOW_UNDOCUMENTED: frozenset[str] = frozenset()
# کلیدهایی که pydantic نمی‌خواند ولی داکر/سیستم/کانتینر مصرف می‌کنند.
INFRA_KEYS = frozenset({"TZ", "ENV", "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB"})

FIELD_RE = re.compile(r"^    ([a-z][a-z0-9_]*): [^=\n]+(?:=[^\n]*)?$", re.M)
KEY_RE = re.compile(r"^#?\s*([A-Za-z][A-Z0-9_]*)\s*=")
# فقط نام‌هایِ داخلِ `alias=` / `validation_alias=` را برمی‌دارد؛ اگر هر رشتهٔ بزرگِ دیگری
# (مثلِ مقدارِ پیش‌فرض `INFO`) به‌اشتباه alias حساب شود، خودِ همین گیت گمراه می‌شود (پ۱۲۴).
ALIAS_DECL_RE = re.compile(r"(?:validation_alias|alias)\s*=\s*(.+)$")
NAME_IN_RE = re.compile(r"\"([A-Z][A-Z0-9_]*)\"")


def settings_fields() -> list[tuple[str, list[str]]]:
    body = CONFIG.read_text(encoding="utf-8")
    out: list[tuple[str, list[str]]] = []
    for match in FIELD_RE.finditer(body):
        name, declaration = match.group(1), match.group(0)
        if name.startswith("_") or name == "model_config":
            continue
        aliases = [found.group(1) for part in ALIAS_DECL_RE.findall(declaration) for found in NAME_IN_RE.finditer(part)]
        out.append((name, aliases or [name.upper()]))
    return out


def example_keys() -> set[str]:
    keys: set[str] = set()
    for path in EXAMPLES:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            found = KEY_RE.match(line.strip())
            if found:
                keys.add(found.group(1).upper())
    return keys


def readable_sources():
    """همه‌جایی که یکِ کلیدِ محیطی می‌تواند خوانده شود: کدِ اپ، فایلِ compose، اسکریپت‌هایِ عملیاتی."""
    paths = list((ROOT / "app").rglob("*.py")) + [ROOT / "docker-compose.yml"]
    paths += list((ROOT / "scripts").glob("*"))
    paths += [ROOT / "entrypoint.sh"]
    return [path for path in paths if path.is_file()]


def app_source() -> str:
    return chr(10).join(path.read_text(encoding="utf-8", errors="ignore") for path in readable_sources())


def main() -> int:
    fields = settings_fields()
    if len(fields) < 20:
        print(f"check_env_coverage: خطا — فقط {len(fields)} فیلد از {CONFIG.name} خوانده شد (regex شکسته؟)")
        return 1
    keys = example_keys()
    if not keys:
        print("check_env_coverage: خطا — هیچ کلیدی در فایل‌هایِ نمونه پیدا نشد")
        return 1

    undocumented = [name for name, names in fields if name not in ALLOW_UNDOCUMENTED and not set(names) & keys]
    documented_names = {name for _n, names in fields for name in names}
    source = app_source()
    dead_keys = sorted(
        key
        for key in keys - documented_names - INFRA_KEYS
        if f'"{key}"' not in source and key not in source
    )
    for name in undocumented:
        print(f"check_env_coverage: ✗ `{name}` در `Settings` هست ولی در فایل‌هایِ نمونه نیست")
    for key in dead_keys:
        print(f"check_env_coverage: ✗ `{key}` در نمونه هست ولی هیچ‌جایِ `app/`، `docker-compose.yml` یا `scripts/` خوانده نمی‌شود")
    if undocumented or dead_keys:
        return 1
    print(
        f"check_env_coverage: OK — {len(fields)} فیلدِ کانفیگ همگی با همان نامی که کد می‌خواند در "
        f"{', '.join(path.name for path in EXAMPLES if path.is_file())} مستند شده‌اند"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
