"""
گیت‌هایِ ایمنیِ پیش ازِ commit (P20 · پیشنهادِ «چیزی که باید در CI باشد»).

پنج اسکریپتِ این پوشه (check_refs، check_attrs، lint_names، check_callbacks، check_text_hygiene)
دقیقاً برایِ گرفتنِ همان خطاهایی نوشته شده‌اند که در P18/P19 دو باگِ واقعی بودند (ارجاعِ
`module.missing_symbol` که فقط در زمانِ اجرا می‌ترکید) و دکمه‌هایِ مردهٔ P24. ولی هیچ‌چیز آنها را
خودکار اجرا نمی‌کرد. این اسکریپت همه را با هم اجرا می‌کند تا بتوان در CI یا pre-commit یک دستور داشت:

    python3 scripts/check_gates.py            # + compileall روی app/tests_manual/migrations

کدِ خروجِ ۰ یعنی همه‌چیز تمیز است. رویِ ویندوز هم اجرا می‌شود (کدِ صفحهٔ فرزندها utf-8 است).
"""
from __future__ import annotations

import ast
import os
import pathlib
import subprocess
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower().replace("-", "") != "utf8":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

ROOT = pathlib.Path(__file__).resolve().parents[1]
GATES = (
    "scripts/check_refs.py",
    "scripts/check_attrs.py",
    "scripts/lint_names.py",
    "scripts/check_callbacks.py",
    "scripts/check_text_hygiene.py",
    "scripts/check_prompt_buttons.py",
    "scripts/check_env_coverage.py",  # پ۱۲۴: هر فیلدِ کانفیگ با همان نامی که کد می‌خواند در .env.example  # پ۱۰۸: «از دکمهٔ مشاوره استفاده کن» برایِ دکمه‌ای که وجود ندارد
)
TESTS_DIR = ROOT / "tests_manual"
REGISTRY = TESTS_DIR / "run_all_tests.py"


def registered_test_files() -> set[str]:
    tree = ast.parse(REGISTRY.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.endswith(".py"):
            names.add(node.value)
    return names


def check_registry() -> list[str]:
    """هر فایلِ تست باید در `run_all_tests.py` باشد، وگرنه هرگز اجرا نمی‌شود (تستِ خاموش = بدونِ تست)."""
    if not REGISTRY.exists():
        return [f"فایلِ {REGISTRY.name} پیدا نشد"]
    registered = registered_test_files()
    problems = [
        f"{path.name} در run_all_tests.py ثبت نشده ⇒ هرگز اجرا نمی‌شود"
        for path in sorted(TESTS_DIR.glob("test_*.py"))
        if path.name not in registered
    ]
    problems += [
        f"run_all_tests.py به {name} ارجاع می‌دهد که چنین فایلی وجود ندارد"
        for name in sorted(registered)
        if name.startswith("test_") and not (TESTS_DIR / name).exists()
    ]
    return problems


def main() -> int:
    failures: list[str] = []

    compile_result = subprocess.run(
        [sys.executable, "-m", "compileall", "-q", "app", "tests_manual", "migrations", "scripts"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if compile_result.returncode != 0:
        failures.append("compileall:\n" + (compile_result.stdout + compile_result.stderr)[-2000:])

    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    for gate in GATES:
        result = subprocess.run(
            [sys.executable, gate], cwd=ROOT, capture_output=True, text=True,
            encoding="utf-8", errors="replace", env=env,
        )
        tail = (result.stdout + result.stderr).strip().splitlines()
        print(f"· {gate}: {'OK' if result.returncode == 0 else 'FAIL'}" + (f" — {tail[-1]}" if tail else ""))
        if result.returncode != 0:
            failures.append(f"{gate}:\n" + "\n".join(tail[-40:]))

    registry_problems = check_registry()
    print(f"· ثبتِ فایل‌هایِ تست در run_all_tests.py: {'OK' if not registry_problems else 'FAIL'}")
    failures.extend(registry_problems)

    if failures:
        print("\n❌ گیت‌ها رد شدند:")
        for line in failures:
            print("\n" + line)
        return 1
    print("✅ همهٔ گیت‌ها تمیزند")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
