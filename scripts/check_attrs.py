"""
بررسیِ استاتیکِ دومِ ارجاع‌ها (مکمّلِ check_refs.py) — برایِ وقتی که نمی‌شه کد رو اجرا کرد.

دو نوع خطا رو می‌گیره که `py_compile` و `check_refs.py` نمی‌گیرنشون و فقط موقعِ اجرا می‌ترکن:

۱. `from app.x import name` وقتی `name` توی ماژولِ مقصد تعریف نشده (تایپو/جابه‌جاشده).
۲. `obj.attr` وقتی `obj` یه *نمونه‌ی* سطحِ ماژوله (مثلاً `rate_limiter = InMemoryRateLimiter()`) و
   کلاسش همچین صفت/متدی نداره. نمونه‌ی واقعیِ این خطا: حالتِ محدودکننده توی متغیرِ سطحِ ماژوله
   (`_windows`)، نه روی نمونه — و `rate_limiter._windows` توی تست AttributeError داد.

اجرا (از ریشه‌ی پروژه):  python3 scripts/check_attrs.py
خروجی: لیستِ موردهایِ مشکوک (کدِ خروج ۱) یا یه خطِ OK (کدِ خروج ۰).

محدودیت‌ها (عمداً محافظه‌کار، تا هشدارِ الکی نده):
- کلاسی که از کلاسِ دیگه ارث می‌بره یا `__getattr__` داره بررسی نمی‌شه (صفت‌هایِ ارثی/پویا معلوم نیست).
- فقط نمونه‌هایی که *همون ماژول* با `name = ClassName(...)` می‌سازه دنبال می‌شن.
- ارجاع‌هایی که با `hasattr(alias, "name")` محافظت شدن نادیده گرفته می‌شن.
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCAN_DIRS = ("app", "tests_manual")
IMPORT_ROOTS = (ROOT, ROOT / "tests_manual")  # تست‌ها `from harness import ...` رو بدونِ پیشوند می‌نویسن


def module_path(dotted: str) -> pathlib.Path | None:
    parts = dotted.split(".")
    for base in IMPORT_ROOTS:
        as_file = base.joinpath(*parts).with_suffix(".py")
        if as_file.exists():
            return as_file
        as_package = base.joinpath(*parts) / "__init__.py"
        if as_package.exists():
            return as_package
    return None


class ModuleInfo:
    def __init__(self, path: pathlib.Path) -> None:
        self.names: set[str] = set()
        self.class_attrs: dict[str, set[str] | None] = {}  # None = بررسی‌نشدنی (ارث/__getattr__)
        self.instances: dict[str, str] = {}  # نامِ نمونه -> نامِ کلاس
        self._collect(ast.parse(path.read_text(encoding="utf-8")).body)

    def _collect(self, body: list[ast.stmt]) -> None:
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.names.add(node.name)
            elif isinstance(node, ast.ClassDef):
                self.names.add(node.name)
                self.class_attrs[node.name] = self._class_attrs(node)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        self.names.add(target.id)
                        if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name):
                            self.instances[target.id] = node.value.func.id
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                self.names.add(node.target.id)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    self.names.add((alias.asname or alias.name).split(".")[0])
            elif isinstance(node, (ast.If, ast.Try)):
                self._collect(node.body)
                self._collect(getattr(node, "orelse", []))
                for handler in getattr(node, "handlers", []):
                    self._collect(handler.body)

    @staticmethod
    def _class_attrs(node: ast.ClassDef) -> set[str] | None:
        if node.bases:  # ارث‌بری: صفت‌هایِ والد رو نمی‌دونیم
            return None
        attrs: set[str] = set()
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                attrs.add(item.name)
                if item.name == "__getattr__":
                    return None
                for sub in ast.walk(item):
                    if (
                        isinstance(sub, ast.Attribute)
                        and isinstance(sub.value, ast.Name)
                        and sub.value.id == "self"
                        and isinstance(sub.ctx, ast.Store)
                    ):
                        attrs.add(sub.attr)
            elif isinstance(item, ast.Assign):
                attrs.update(t.id for t in item.targets if isinstance(t, ast.Name))
            elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                attrs.add(item.target.id)
        return attrs


_cache: dict[pathlib.Path, ModuleInfo] = {}


def info(path: pathlib.Path) -> ModuleInfo:
    if path not in _cache:
        _cache[path] = ModuleInfo(path)
    return _cache[path]


def guarded_names(tree: ast.AST) -> set[str]:
    """نام‌هایی که فایل با hasattr(x, "name") امتحان می‌کنه — پس وجودشون اختیاریه."""
    guarded: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "hasattr"
            and len(node.args) == 2
            and isinstance(node.args[1], ast.Constant)
            and isinstance(node.args[1].value, str)
        ):
            guarded.add(node.args[1].value)
    return guarded


def main() -> int:
    problems: list[tuple[str, int, str]] = []
    files = [p for d in SCAN_DIRS for p in sorted((ROOT / d).rglob("*.py"))]
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        guarded = guarded_names(tree)
        rel = str(path.relative_to(ROOT))
        bound_instances: dict[str, tuple[ModuleInfo, str]] = {}

        for node in ast.walk(tree):
            if not (isinstance(node, ast.ImportFrom) and node.module and node.level == 0):
                continue
            source = module_path(node.module)
            for alias in node.names:
                local = alias.asname or alias.name
                if module_path(f"{node.module}.{alias.name}") is not None:
                    continue  # `from package import submodule`
                if source is None or alias.name == "*":
                    continue
                module_info = info(source)
                if alias.name not in module_info.names:
                    if alias.name not in guarded:
                        problems.append((rel, node.lineno, f"from {node.module} import {alias.name}: این نام توی ماژولِ مقصد تعریف نشده"))
                    continue
                class_name = module_info.instances.get(alias.name)
                if class_name and module_info.class_attrs.get(class_name) is not None:
                    bound_instances[local] = (module_info, class_name)

        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in bound_instances:
                module_info, class_name = bound_instances[node.value.id]
                attrs = module_info.class_attrs[class_name] or set()
                if node.attr not in attrs and node.attr not in guarded and not node.attr.startswith("__"):
                    problems.append(
                        (
                            rel,
                            node.lineno,
                            f"{node.value.id}.{node.attr}: {node.value.id} نمونه‌ی کلاسِ {class_name} ـه و "
                            f"{class_name} همچین صفت/متدی نداره (شاید توی ماژول تعریف شده، نه روی نمونه؟)",
                        )
                    )

    unique = sorted(set(problems))
    for rel, lineno, message in unique:
        print(f"{rel}:{lineno}: {message}")
    if unique:
        print(f"\n{len(unique)} مورد مشکوک پیدا شد.")
        return 1
    print(f"OK — مشکلی پیدا نشد ({len(files)} فایل بررسی شد)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
