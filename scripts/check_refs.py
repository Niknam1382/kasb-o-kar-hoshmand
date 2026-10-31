"""
بررسیِ استاتیکِ ارجاع‌ها — جایگزینِ سبک برایِ وقتی که نمی‌شه کد رو اجرا کرد.

هر عبارتِ `alias.name` که alias یه ماژولِ داخلیِ پروژه‌ست (مثلاً `texts.SOME_NAME` بعد از
`from app.bots.shop_bot import texts`) باید واقعاً تویِ همون ماژول تعریف شده باشه. تایپوی
اسمِ ثابت/تابع، چیزیه که `py_compile` نمی‌گیرتش و فقط موقعِ اجرا می‌ترکه.

اجرا (از ریشه‌ی پروژه):  python3 scripts/check_refs.py
خروجی: لیستِ ارجاع‌هایِ شکسته (کدِ خروج ۱) یا یه خطِ OK (کدِ خروج ۰).

ارجاع‌هایی که با `hasattr(alias, "name")` محافظت شدن نادیده گرفته می‌شن.
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCAN_DIRS = ("app", "tests_manual")


def module_path(dotted: str) -> pathlib.Path | None:
    parts = dotted.split(".")
    as_file = ROOT.joinpath(*parts).with_suffix(".py")
    if as_file.exists():
        return as_file
    as_package = ROOT.joinpath(*parts, "__init__.py")
    return as_package if as_package.exists() else None


def top_level_names(path: pathlib.Path) -> set[str]:
    names: set[str] = set()
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(n.id for target in node.targets for n in ast.walk(target) if isinstance(n, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update((alias.asname or alias.name).split(".")[0] for alias in node.names)
    return names


def hasattr_guarded(tree: ast.AST) -> set[tuple[str, str]]:
    guarded: set[tuple[str, str]] = set()
    for node in ast.walk(tree):
        is_hasattr = isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "hasattr"
        if is_hasattr and len(node.args) == 2 and isinstance(node.args[0], ast.Name) and isinstance(node.args[1], ast.Constant):
            guarded.add((node.args[0].id, str(node.args[1].value)))
    return guarded


def main() -> int:
    cache: dict[pathlib.Path, set[str]] = {}
    problems: list[str] = []
    files = [path for directory in SCAN_DIRS for path in (ROOT / directory).rglob("*.py")]

    for file in files:
        tree = ast.parse(file.read_text(encoding="utf-8"))
        aliases: dict[str, pathlib.Path] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("app") and node.level == 0:
                for imported in node.names:
                    target = module_path(f"{node.module}.{imported.name}")
                    if target is not None:
                        aliases[imported.asname or imported.name] = target

        guarded = hasattr_guarded(tree)
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in aliases):
                continue
            if (node.value.id, node.attr) in guarded:
                continue
            target = aliases[node.value.id]
            if node.attr not in cache.setdefault(target, top_level_names(target)):
                where = f"{file.relative_to(ROOT)}:{node.lineno}"
                problems.append(f"{where}: {node.value.id}.{node.attr} در {target.relative_to(ROOT)} تعریف نشده")

    if problems:
        print("\n".join(problems))
        return 1
    print(f"OK — هیچ ارجاعِ شکسته‌ای پیدا نشد ({len(files)} فایل بررسی شد)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
