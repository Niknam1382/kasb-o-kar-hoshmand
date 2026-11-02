"""گیتِ «دکمهٔ مرده»: هر callback_data که ساخته می‌شود باید مصرف‌کننده داشته باشد.

چرا این گیت متولد شد (P24): دکمهٔ «⬅️ بازگشت به پنل» (`callback_data="main_menu"`) در پنج کیبورد
ساخته می‌شد و *هیچ* هندلری برایش ثبت نشده بود؛ هر کاربری که رویِ صفحهٔ خالیِ «🧾 تاریخچهٔ پرداخت»
یا «🧩 سوال‌هایِ بی‌جواب» می‌زد، ساعتِ چرخانِ بی‌پاسخ می‌دید. این دقیقاً همان باگی بود که در گزارشِ
«دکمه‌ها کار نمی‌کنند» وجود داشت و هیچ‌یک از گیت‌هایِ موجود (ارجاع، صفت، نام) نمی‌توانستند بگیرندش،
چون بینِ دو فایلِ مستقل حرف می‌گذرد: کیبورد می‌سازد، هندلر مصرف نمی‌کند.

روش (ast، بدونِ اجرایِ کد):
۱) هر `callback_data=` در `app/` → یا رشتهٔ کامل است یا `f"prefix:{…}"` ⇒ پیشوندِ `prefix:` taken.
۲) هر فیلترِ ثبتِ هندلر: `F.data == "x"`، `F.data.startswith("p:")`، `F.data.in_({...})`،
   `Command("y")` و مصرفِ `data.split(":", 1)[1]` ⇒ الگوهایِ مصرف‌شده.
۳) هر رشتهٔ کاملِ ساخته‌شده که هیچ هندلری آن را مصرف نمی‌کند ⇒ خطا.
۴) اخطار (نه خطا): `int(<data>.split(...)[1])` بدونِ گارد — باید `parse_suffix_int` شود.

اجرا: python3 scripts/check_callbacks.py
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
APP = ROOT / "app"

# callback_dataهایی که عمداً در هندلرهایِ عمومی مصرف می‌شوند (پیشوند یا تطبیقِ جزئی):
# این‌ها با جست‌وجویِ ast رویِ رشته‌هایِ فیلتر شناسایی نمی‌شوند، چون با `in`/پسوندهایِ متغیر
# مصرف می‌شوند؛ هرکدام با یکِ کامنتِ مرجع در کدِ خودِ پروژه قابلِ ردیابی است.
# «main_menu» عمداً در این فهرست نیست: هندلرِ panel.cb_back_to_panel باید پیدایش کند؛ روزه‌یِ
# اولِ P24 همین رشته در پنج کیبورد ساخته می‌شد و هیچ هندلری نداشت (باگِ گزارش‌شدهٔ کاربر).
MANUAL_ALLOWLIST = {
    "noop",  # shop_bot.customer: دکمهٔ بی‌کارِ حذفِ کیبورد
}

# در main() پر می‌شود: NAME → مقدار، تا فیلترهایِ نوشته‌شده با ثابت هم دیده شوند
_CONSTANTS: dict[str, str] = {}


def _literal_or_prefix(node: ast.AST) -> tuple[str | None, str | None]:
    """از مقدارِ callback_data: (رشتهٔ کامل، پیشوندِ ثابت) — یکی از دو.

    قاعده: چیزی که **پیش ازِ اولین «:» متغیر دارد** (`f"pm_{method}:{key}"`) پیشوندِ ثابتی نیست؛
    آن را رد می‌کنیم، وگرنه گیت هر چیزِ پویا را «دکمهٔ مرده» گزارش می‌کند بی‌آنکه باشد.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value, None
    if isinstance(node, ast.JoinedStr):
        collected: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                collected.append(value.value)
                if ":" in value.value:
                    break  # پیشوندِ ثابت تا اولین «:» تعیین است
                continue
            head = "".join(collected)
            if ":" not in head:
                return None, None  # متغیر قبلِ «:» ⇒ پویا
            return None, head
        head = "".join(collected)
        if ":" in head:
            return None, head
        return (head or None), None
    return None, None


def _collected_producers() -> tuple[set[str], set[str], list[str]]:
    exact: set[str] = set()
    prefixes: set[str] = set()
    unguarded: list[str] = []
    for path in APP.rglob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.keyword) and node.arg == "callback_data":
                full, prefix = _literal_or_prefix(node.value)
                if full:
                    exact.add(full)
                elif prefix and len(prefix) >= 3:
                    prefixes.add(prefix)
            # int(x.split(":")[1]) بدونِ گارد — debt که با parse_suffix_int حل می‌شود
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "int":
                arg = node.args[0] if node.args else None
                if isinstance(arg, ast.Subscript) and isinstance(arg.value, ast.Call):
                    callee = arg.value.func
                    if isinstance(callee, ast.Attribute) and callee.attr == "split":
                        unguarded.append(f"{path.relative_to(ROOT)}:{node.lineno}")
    return exact | prefixes, prefixes, unguarded


def _strings(node: ast.AST) -> list[str]:
    """همهٔ رشته‌هایِ داخلِ یکِ نودِ فیلتر (constant، list/tuple/set، f-stringِ ساده)."""
    out: list[str] = []
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        out.append(node.value)
    elif isinstance(node, ast.JoinedStr):
        full, prefix = _literal_or_prefix(node)
        out.extend(x for x in (full, prefix) if x)
    elif isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        for element in node.elts:
            out.extend(_strings(element))
    return out


def _is_f_data(node: ast.AST) -> bool:
    """آیا این نود `F.data` است؟"""
    return isinstance(node, ast.Attribute) and node.attr == "data" and isinstance(node.value, ast.Name) and node.value.id == "F"


def _const_table(tree: ast.Module) -> dict[str, str]:
    """NAME = "رشته" — تا فیلترهایی که با ثابتِ ماژول نوشته شده‌اند (F.data == CANCEL_CB) دیده شوند."""
    table: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            value = node.value
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        table[target.id] = value.value
    return table


def _resolve(node: ast.AST, table: dict[str, str]) -> list[str]:
    """رشته‌هایِ یکِ نود، با بازکردنِ نامِ ثابتِ ماژول (`ui.CANCEL_CB` هم)."""
    texts = _strings(node)
    if isinstance(node, ast.Name):
        texts.append(table[node.id]) if node.id in table else None
    if isinstance(node, ast.Attribute) and node.attr in table:
        texts.append(table[node.attr])
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"_chunk", "f"}:
        texts.extend(_strings(node.args[0]) if node.args else [])
    return texts


def _global_constants() -> dict[str, str]:
    """همهٔ `NAME = "…"`. برایِ فیلترهایی که با ثابت نوشته شده‌اند (`F.data == ui.CANCEL_CB`)."""
    table: dict[str, str] = {}
    for path in APP.rglob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        table.update(_const_table(tree))
    return table


def _receiver_is_data(node: ast.AST) -> bool:
    """آیا گیرنده‌یِ `.startswith(…)` یکی از متغیرهایِ callback_data است؟"""
    src = ast.dump(node)
    return '"data"' in src or "'data'" in src or "attr='data'" in src


def _collected_consumers() -> tuple[set[str], set[str]]:
    """(رشته‌هایِ دقیق، پیشوندها) از فیلترها و از پارسِ دستیِ `callback.data`."""
    exact: set[str] = set()
    prefixes: set[str] = set()
    for path in APP.rglob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        table = {**_CONSTANTS, **_const_table(tree)}
        for node in ast.walk(tree):
            if isinstance(node, ast.Compare) and _is_f_data(node.left):
                for comparator in node.comparators:
                    exact.update(_resolve(comparator, table))
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                attr = node.func.attr
                # F.data.startswith("p:") / F.data.in_([...])
                if isinstance(node.func.value, ast.Attribute) and node.func.value.attr == "data":
                    if attr in {"startswith", "endswith", "find", "contains"}:
                        for arg in node.args:
                            prefixes.update(_resolve(arg, table))
                    elif attr == "in_":
                        for arg in node.args:
                            exact.update(_resolve(arg, table))
                # پارسِ دستی: if callback.data.startswith("crm_") — catch-allهایِ پروژه
                elif attr in {"startswith", "__eq__"} and _receiver_is_data(node.func.value):
                    for arg in node.args:
                        texts = _resolve(arg, table)
                        if attr == "startswith":
                            prefixes.update(texts)
                        else:
                            exact.update(texts)
            # `data == "x"` / `raw == "x"` رویِ متغیرِ حاویِ callback_data
            if isinstance(node, ast.Compare) and isinstance(node.left, ast.Name) and node.left.id in {"data", "raw", "text_data"}:
                for comparator in node.comparators:
                    exact.update(_resolve(comparator, table))
    return exact, prefixes


def _is_consumed(token: str, consumed_exact: set[str], consumed_prefixes: set[str]) -> bool:
    if token in consumed_exact or token in consumed_prefixes:
        return True
    # «sched_cancel:12» یا پیشوندِ «sched_cancel:» با startswith("sched_cancel:") مصرف می‌شود
    for pattern in consumed_prefixes | consumed_exact:
        if pattern.endswith(":") and (token.startswith(pattern) or token == pattern[:-1]):
            return True
    # `F.data == "audit_filter:all"` در برابرِ تولیدِ «audit_filter:…»
    for pattern in consumed_exact:
        if token.endswith(":") and pattern.startswith(token):
            return True
    return False


def main() -> int:
    _CONSTANTS.update(_global_constants())
    produced_all, _produced_prefixes, unguarded = _collected_producers()
    consumed_exact, consumed_prefixes = _collected_consumers()

    problems = [
        f"callback_data بدونِ هندلر: {token!r}"
        for token in sorted(produced_all)
        if token not in MANUAL_ALLOWLIST and not _is_consumed(token, consumed_exact, consumed_prefixes)
    ]
    for line in problems:
        print(f"scripts/check_callbacks.py: {line}")

    if unguarded:
        print(f"⚠️  {len(unguarded)} جایِ `int(data.split(…)[1])` بدونِ گارد (الگویِ خودِ پروژه: parse_suffix_int):")
        for item in unguarded[:6]:
            print(f"   · {item}")

    if problems:
        print(f"❌ {len(problems)} دکمهٔ مرده")
        return 1
    print(f"OK — {len(produced_all)} شکلِ callback_data همگی مصرف‌کننده دارند")
    return 0


if __name__ == "__main__":
    sys.exit(main())
