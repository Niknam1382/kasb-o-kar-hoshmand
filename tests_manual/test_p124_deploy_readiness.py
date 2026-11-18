"""پ۱۲۴ · گیت‌هایِ آمادگیِ دیپلوی رویِ کانفیگ (نامِ متغیرِ محیطی + تمیزیِ فایل‌هایِ نمونه).

چرا این تست نوشته شد: در بازرسیِ پیش ازِ استقرار روشن شد `WEB_PANEL_SECRET` در `.env.example`،
راهنمایِ ادمین، پلی‌بوک و هشت کامنتِ کد آمده بود، ولی `pydantic-settings` فیلدِ `panel_secret` را با
نامِ `PANEL_SECRET` می‌خواند ⇒ کسی که دقیقاً طبقِ مستندات عمل می‌کرد، پنجرهٔ وب را بی‌سروصدا ۴۰۴
می‌دید (بدونِ هیچ خطا یا لاگِ هشدار). رفع با `AliasChoices` انجام شد و این فایل همان را پین می‌کند تا
دیگر هیچ‌وقت «نامِ مستند ≠ نامی که کد می‌خواند» نشود.

سه چیزی که این فایل می‌بندد:
۱. هر دو نامِ `WEB_PANEL_SECRET` و `PANEL_SECRET` مقدارِ `settings.panel_secret` را پر می‌کنند و بی‌
   هیچ‌کدام، خالی می‌ماند (یعنی درِ `/web/*` بسته است).
۲. `scripts/check_env_coverage.py` (گیتِ هشتم) سبز است و در `check_gates.py` ثبت شده؛ یعنی هر فیلدِ
   تازهٔ `Settings` باید با همان نامی که کد می‌خواند در فایل‌هایِ نمونه مستند شود.
۳. فایل‌هایِ نمونه هیچ رازِ پرشده‌ای ندارند (جزِ پیش‌فرضِ توسعه‌یِ `POSTGRES_PASSWORD=postgres` و
   توکنِ بی‌خطرِ نمونه) — تا کسی مقدارِ واقعیِ `.env` را اشتباهاً داخلِ `.env.example` نریزد.
۴. یکِ alembic head (بی‌دست‌زدنِ دیتابیس؛ فقط خواندنِ پوشهٔ مایگریشن).

اجرا: python3 tests_manual/run_one.py test_p124_deploy_readiness.py
"""
from __future__ import annotations

import os
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from app.config import Settings  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
FAKE_TOKEN = "123456789:" + "A" * 35
REQUIRED_ENV = {
    "DATABASE_URL": "postgresql+asyncpg://u:p@127.0.0.1:5432/kasbokar_probe",
    "MAIN_BOT_TOKEN": FAKE_TOKEN,
    "ENCRYPTION_KEY": "probe-encryption-key-not-a-real-fernet",
}
ALLOWED_SAMPLE_VALUES = {"", "postgres", FAKE_TOKEN, "123456789:AAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"}


def _settings_with(**overrides) -> Settings:
    """`Settings` را با محیطِ مشخص می‌سازد (بی‌فایلِ .env) و محیطِ واقعیِ پروسه را دست نمی‌زند."""
    merged = {**REQUIRED_ENV, **{key: str(value) for key, value in overrides.items()}}
    saved = {key: os.environ.get(key) for key in merged}
    os.environ.update(merged)
    try:
        return Settings(_env_file=None)
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def test_both_documented_names_fill_panel_secret() -> None:
    assert _settings_with().panel_secret == "", "بی‌کلید باید خالی بماند (⇒ /web/* نبود دارد)"
    assert _settings_with(WEB_PANEL_SECRET="از-مستندات").panel_secret == "از-مستندات"
    assert _settings_with(PANEL_SECRET="نامِ-داخلی").panel_secret == "نامِ-داخلی"
    # هر دو با هم: alias‌ها به ترتیب به ترتیبِ اولویت عمل می‌کند (نامِ مستندِ اول برنده است)
    both = _settings_with(WEB_PANEL_SECRET="اول", PANEL_SECRET="دوم")
    assert both.panel_secret == "اول", both.panel_secret
    print("✅ test_both_documented_names_fill_panel_secret PASSED")


def test_env_coverage_gate_is_registered_and_green() -> None:
    script = ROOT / "scripts" / "check_env_coverage.py"
    assert script.is_file(), "گیتِ پوششِ کانفیگ وجود ندارد"
    gates = (ROOT / "scripts" / "check_gates.py").read_text(encoding="utf-8")
    assert "check_env_coverage.py" in gates, "گیتِ تازه در check_gates.py ثبت نشده (یکِ پاسِ کامل آن را رد می‌کند)"
    done = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, encoding="utf-8", cwd=str(ROOT))
    assert done.returncode == 0, done.stdout + done.stderr
    print("✅ test_env_coverage_gate_is_registered_and_green PASSED —", done.stdout.strip()[:90])


def test_example_env_files_have_no_filled_secrets() -> None:
    checked = 0
    for name in (".env.example", ".env.docker.example"):
        body = (ROOT / name).read_text(encoding="utf-8")
        for line in body.splitlines():
            if line.strip().startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            if not re.search(r"(TOKEN|KEY|SECRET|PASSWORD)$", key):
                continue
            checked += 1
            assert value.strip() in ALLOWED_SAMPLE_VALUES, f"{name}: `{key}` مقدارِ نمونه‌ایِ واقعی دارد؟"
    assert checked >= 4, f"انتظارِ دست‌کم چهار کلیدِ حساس در نمونه‌ها بود؛ دیده شد: {checked}"
    print(f"✅ test_example_env_files_have_no_filled_secrets PASSED ({checked} کلیدِ حساس بررسی شد)")


def test_single_alembic_head_without_touching_database() -> None:
    revisions, parents = set(), set()
    for path in sorted((ROOT / "migrations" / "versions").glob("*.py")):
        body = path.read_text(encoding="utf-8")
        rev = re.search(r"^revision(?:\s*:\s*str)?\s*=\s*[\"']([^\"']+)[\"']", body, re.M)
        assert rev, path.name
        revisions.add(rev.group(1))
        down = re.search(r"^down_revision[^=]*=\s*(.+)$", body, re.M)
        if down:
            parents.update(re.findall(r"[\"']([0-9a-f]{8,})[\"']", down.group(1)))
    heads = revisions - parents
    assert len(heads) == 1, f"قاعدهٔ پروژه یکِ head است؛ دیده شد: {sorted(heads)}"
    print(f"✅ test_single_alembic_head_without_touching_database PASSED ({len(revisions)} رِویشن، head={sorted(heads)[0]})")


def main() -> None:
    test_both_documented_names_fill_panel_secret()
    test_env_coverage_gate_is_registered_and_green()
    test_example_env_files_have_no_filled_secrets()
    test_single_alembic_head_without_touching_database()


if __name__ == "__main__":
    main()
