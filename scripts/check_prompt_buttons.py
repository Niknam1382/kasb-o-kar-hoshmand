#!/usr/bin/env python3
"""شمارندهٔ «دکمهٔ مرده در متن»: هر نقل‌قولِ «…» که شکلِ دکمه دارد (ایموجی دارد) باید در کدِ
همان مخزن به‌عنوانِ برچسبِ دکمهٔ واقعی وجود داشته باشد.

چرا: باگِ گزارش‌شده توسطِ مالک (پ۱۰۸) — رباتِ مشاوره‌ای می‌گفت «از دکمهٔ مشاوره استفاده کن» در حالی
که هیچ دکمه‌ای ساخته نشده بود؛ مقصّر پرامپتِ پیش‌فرضِ AI بود، نه کیبورد. گیت‌هایِ فعلی شکلِ
`callback_data` را می‌سنجند ولی *نامِ* دکمه‌ای که فقط در متن/پرامپت ذکر می‌شود را نه.

مفهومِ «دکمهٔ زنده»: رشته‌ای که در `keyboards.py` به‌عنوانِ `text=` یا در فهرستِ ردیف‌هایِ منو آمده،
یا مقدارِ یکِ ثابتِ `*_BUTTON` / `BTN_*` است، یا در هندلرها با `F.text == "…"` تطبیق داده می‌شود.
مقایسه با نرمال‌سازیِ cart_suggest_service (ی/ک، ZWNJ، ارقام) انجام می‌شود تا تفاوتِ ظاهری جعلی نسازد.

اجرا: python3 scripts/check_prompt_buttons.py [مدیریتِ متن‌ها]
خروجی: خط‌هایِ `مرده: <متن>  ←  فایل:خط` و در پایان جمع. کدِ خروجِ ۱ اگر چیزی پیدا شد.
"""
from __future__ import annotations

import ast
import pathlib
import re
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "app")

from app.services.cart_suggest_service import normalize_text  # noqa: E402

_SPAN = re.compile(r"«([^»\n]{2,44})»")
BUTTONISH = re.compile(r"^[\U0001F000-\U0001FAFF←-⯿]\S*")
# «🏷 کدهای تخفیف › ➕ افزودن کد جدید» یکِ مسیرِ ناوبری است، نه یکِ دکمه ⇒ هر قطعه جدا سنجیده می‌شود.
_SEGMENT = re.compile(r"\s*(?:›|→|←)\s*")
# «🔑 ثبت/ویرایش توکن ربات» یکِ دکمه است، دو دکمه نه ⇒ اسلش فقط وقتی جدا می‌کند که دورش فاصله باشد.
_SLASH = re.compile(r"\s+/\s+")
# نقل‌قول‌هایِ توضیحیِ مستندات/دوکاسترینگ که هرگز دکمه نبودند (نمونهٔ قالب و وضعیتِ کلی).
PROSE = re.compile(r"…|①|②|③|④|⑤|نامِ کاربری|@|\bX\b|<|\{|\}")
# برچسب‌هایِ حالت‌دار/پویا: دقیقاً همین رشته‌ها دکمه نمی‌شوند («✅ روشن‌کردنِ …»، «🔵 توکن…: <مخفی>»،
# خط‌هایِ گزارشِ ظرفیت). اینجا بودن یعنی «عمداً پویاست» — با دستی چک شده، نه با حدس.
APPROVED = {"🔧 فنی", "✅ روشن", "🗄 دیتابیس"}


def _literals(node: ast.AST) -> list[tuple[str, int]]:
    out = []
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            out.append((child.value, child.lineno))
    return out


def _live_labels(root: pathlib.Path) -> set[str]:
    live: set[str] = set()
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "attr", getattr(node.func, "id", "")).endswith("KeyboardButton"):
                for kw in node.keywords:
                    if kw.arg == "text" and isinstance(kw.value, ast.Constant):
                        _add(live, kw.value.value)
                        _add_strings(live, kw.value)
            elif isinstance(node, (ast.Assign, ast.AnnAssign)) and _is_button_const(node):
                _add_strings(live, node.value)
            elif isinstance(node, ast.Call) and getattr(node.func, "id", "") == "switch_label" and node.args:
                # سوییچ‌ها برچسبِ *ساخته‌شده* دارند: «✅ روشن‌کردنِ X» / «⏸ خاموش‌کردنِ X».
                first = node.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    live.add(normalize_text(f"✅ روشن‌کردنِ {first.value}"))
                    live.add(normalize_text(f"⏸ خاموش‌کردنِ {first.value}"))
            elif isinstance(node, ast.Compare):
                _add_strings(live, node.comparators[0])
            elif isinstance(node, (ast.Assign, ast.AnnAssign)) and isinstance(
                node.value, (ast.List, ast.Tuple, ast.Set, ast.Dict)
            ):
                # جدولِ برچسب (مثلِ `PAY_METHOD_LABELS`)؛ مقدارهایش دکمه‌هایِ واقعیاند.
                _add_strings(live, node.value)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.endswith("_label"):
                _add_strings(live, node)
        if path.name == "keyboards.py":
            # هر رشتهٔ این فایل یا برچسبِ دکمه است یا بخشی از آن (`_btn("💳 کیف‌پول", …)`).
            for value, _line in _literals(tree):
                _add(live, value)
    return live


def _is_button_const(node: ast.AST) -> bool:
    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    return any(
        isinstance(t, ast.Name) and ("BUTTON" in t.id.upper() or t.id.upper().startswith("BTN_")) for t in targets
    )


def _add_strings(live: set[str], node: ast.AST) -> None:
    for value, _line in _literals(node):
        _add(live, value)


def _add(live: set[str], value: object) -> None:
    if isinstance(value, str):
        live.add(normalize_text(value))


def _mentioned(root: pathlib.Path, live: set[str]) -> list[str]:
    dead = []
    seen = set()
    for path in sorted(root.rglob("*.py")):
        if path.name == "keyboards.py":
            continue  # اینها خودِ منبعِ «زنده»اند
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            for span in _SPAN.findall(node.value):
                for piece in _SPAN_pieces(span):
                    key = (path, piece, node.lineno)
                    if PROSE.search(piece) or not BUTTONISH.match(piece):
                        continue
                    if normalize_text(piece) in live or piece in APPROVED or key in seen:
                        continue
                    seen.add(key)
                    dead.append(f"مرده: «{piece}»  ←  {path.as_posix()}:{node.lineno}")
    return dead


def _SPAN_pieces(span: str) -> list[str]:
    parts = []
    for chunk in _SEGMENT.split(span):
        parts.extend(_SLASH.split(chunk))
    return parts


def main() -> int:
    root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "app")
    live = _live_labels(root)
    dead = _mentioned(root, live)
    print(f"برچسبِ دکمهٔ زنده: {len(live)} · نامِ دکمه‌مانند در متن‌ها: بررسی شد")
    for line in dead:
        print(line)
    if dead:
        return 1
    print("هیچ دکمهٔ مرده‌ای در متن/پرامپت‌ها نیست ✔")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
