"""
ممیزیِ «commit قبل از هر فراخوانیِ AI» (ظرفیت؛ تله‌یِ ۱۰-ب): هر `.get_reply/.analyze_image/.transcribe_audio` باید
در *همون تابع* یک `X.commit()` قبلش داشته باشه که X همون‌جا تعریف/پارامتر باشه (commit روی نامِ تعریف‌نشده = NameError).
توابعِ بدونِ session (سرویس‌هایی که فراخوان commit می‌کنه) در WAIVED فهرست شدن؛ فراخوانشون باید commit بزنه.
اجرا:  python3 scripts/audit_ai_commit.py        (کدِ خروج ۱ = فراخوانیِ ممیزی‌نشده)
"""
from __future__ import annotations

import ast
import pathlib
import sys

AI_METHODS = {"get_reply", "analyze_image", "transcribe_audio"}
# (فایل، تابع): این توابع session ندارن؛ commit در فراخوانشونه (پس از افزودنِ هر مورد، فراخوان رو دستی چک کن)
WAIVED = {
    ("app/services/ai_service.py", None),  # لایه‌یِ wrapper/failover؛ session نداره
    ("app/services/order_detection_service.py", "detect_order"),
    ("app/services/cart_edit_service.py", "classify"),
    ("app/services/crm_summary_service.py", "generate_summary"),
}


def _own_nodes(fn: ast.AST):
    stack = list(fn.body)
    while stack:
        node = stack.pop()
        yield node
        for child in ast.iter_child_nodes(node):
            if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
                stack.append(child)


def main() -> int:
    problems = 0
    for path in sorted(pathlib.Path("app").rglob("*.py")):
        rel = str(path).replace("\\", "/")
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for fn in (n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))):
            names = {a.arg for a in fn.args.args + fn.args.kwonlyargs}
            for n in _own_nodes(fn):
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
                    names.add(n.id)
                if isinstance(n, (ast.With, ast.AsyncWith)):
                    names.update(i.optional_vars.id for i in n.items if isinstance(i.optional_vars, ast.Name))
            ai_lines = [n.lineno for n in _own_nodes(fn) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in AI_METHODS]
            commits = [
                (n.lineno, n.func.value.id)
                for n in _own_nodes(fn)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "commit" and isinstance(n.func.value, ast.Name)
            ]
            for line in ai_lines:
                if any(c < line and obj in names for c, obj in commits):
                    continue
                if (rel, None) in WAIVED or (rel, fn.name) in WAIVED:
                    continue
                print(f"{rel}:{line} ({fn.name}): فراخوانیِ AI بدونِ commitِ معتبر قبلش")
                problems += 1
    print("audit_ai_commit:", "OK" if not problems else f"{problems} مورد")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
