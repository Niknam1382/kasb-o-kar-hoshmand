"""
بررسیِ استاتیکِ سبک (pyflakes-lite، بدونِ وابستگی): دو خطایِ زمانِ‌اجرا که compileall نمی‌گیره:
  1) نامِ تعریف‌نشده (NameError)           2) استفاده از متغیرِ محلی قبل از انتساب (UnboundLocalError)
اجرا:  python3 scripts/lint_names.py app tests_manual migrations scripts      (خروجیِ ۰ = تمیز؛ کدِ خروج ۱ = مشکل)
"""
from __future__ import annotations

import ast
import builtins
import pathlib
import sys


_SCOPE_NODES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)


def _bound_names(scope: ast.AST) -> set[str]:
    """نام‌هایِ تعریف‌شده در *همین* scope (بدونِ ورود به scopeهایِ تو-در-تو؛ نامِ خودِ def/class جزوِ scopeِ بیرونیه)."""
    names: set[str] = set()
    if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
        a = scope.args
        names.update(x.arg for x in a.args + a.kwonlyargs + a.posonlyargs)
        names.update(x.arg for x in (a.vararg, a.kwarg) if x)
    stack = list(scope.body) if not isinstance(scope, ast.Lambda) else [scope.body]
    while stack:
        n = stack.pop()
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(n.name)
            stack.extend(n.decorator_list)
            continue
        if isinstance(n, ast.Lambda):
            continue
        if isinstance(n, ast.Import):
            names.update((x.asname or x.name).split(".")[0] for x in n.names)
        elif isinstance(n, ast.ImportFrom):
            names.update(x.asname or x.name for x in n.names)
        elif isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            names.add(n.id)
        elif isinstance(n, ast.ExceptHandler) and n.name:
            names.add(n.name)
        elif isinstance(n, (ast.Global, ast.Nonlocal)):
            names.update(n.names)
        stack.extend(ast.iter_child_nodes(n))
    return names


def _undefined_names(tree: ast.Module) -> list[tuple[int, str]]:
    builtin_names = set(dir(builtins)) | {"__file__", "__name__", "__doc__"}
    findings: list[tuple[int, str]] = []

    def visit(scope: ast.AST, chain: list[set[str]]) -> None:
        here = _bound_names(scope)
        visible = chain + [here]
        # بدنه‌یِ scope رو بگرد؛ scopeهایِ تو-در-تو بازگشتی
        stack = list(scope.body) if not isinstance(scope, ast.Lambda) else [scope.body]
        if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            stack.extend(d for d in scope.args.defaults + [d for d in scope.args.kw_defaults if d])
        while stack:
            n = stack.pop()
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                stack.extend(n.decorator_list)
                stack.extend(a for a in (n.args.defaults + [d for d in n.args.kw_defaults if d]))
                visit(n, visible if not isinstance(scope, ast.ClassDef) else chain)
                continue
            if isinstance(n, ast.ClassDef):
                stack.extend(n.decorator_list + n.bases)
                visit(n, visible)
                continue
            if isinstance(n, ast.Lambda):
                visit(n, visible)
                continue
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
                if n.id not in builtin_names and not any(n.id in s for s in visible):
                    findings.append((n.lineno, f"نامِ تعریف‌نشده: {n.id}"))
            stack.extend(ast.iter_child_nodes(n))

    visit(tree, [])
    return findings


def _comprehension_targets(fn: ast.AST) -> set[str]:
    out: set[str] = set()
    for n in ast.walk(fn):
        if isinstance(n, ast.comprehension):
            out.update(t.id for t in ast.walk(n.target) if isinstance(t, ast.Name))
    return out


def check_file(path: pathlib.Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    findings: list[tuple[int, str]] = list(_undefined_names(tree))

    for fn in (n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))):
        params = {a.arg for a in fn.args.args + fn.args.kwonlyargs + fn.args.posonlyargs}
        params.update(a.arg for a in (fn.args.vararg, fn.args.kwarg) if a)
        declared = {name for n in ast.walk(fn) if isinstance(n, (ast.Global, ast.Nonlocal)) for name in n.names}
        comp = _comprehension_targets(fn)
        stores: dict[str, int] = {}
        loads: list[tuple[str, int]] = []

        def walk(node: ast.AST) -> None:
            for c in ast.iter_child_nodes(node):
                if isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
                    continue
                if isinstance(c, ast.Name):
                    if isinstance(c.ctx, ast.Store):
                        stores.setdefault(c.id, c.lineno)
                    elif isinstance(c.ctx, ast.Load):
                        loads.append((c.id, c.lineno))
                elif isinstance(c, ast.ExceptHandler) and c.name:
                    stores.setdefault(c.name, c.lineno)
                elif isinstance(c, (ast.Import, ast.ImportFrom)):
                    for a in c.names:
                        stores.setdefault((a.asname or a.name).split(".")[0], c.lineno)
                walk(c)

        walk(fn)
        for name, line in loads:
            if name in stores and name not in params and name not in declared and name not in comp and line < stores[name]:
                findings.append((line, f"استفاده قبل از انتساب: {name} در {fn.name} (اولین انتساب: خطِ {stores[name]})"))
    return sorted(set(findings))


def main(argv: list[str]) -> int:
    roots = argv or ["app", "tests_manual", "migrations", "scripts"]
    bad = 0
    for root in roots:
        for path in sorted(pathlib.Path(root).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            for line, message in check_file(path):
                print(f"{path}:{line}: {message}")
                bad += 1
    print("lint_names:", "OK — مشکلی نیست" if not bad else f"{bad} مورد")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
