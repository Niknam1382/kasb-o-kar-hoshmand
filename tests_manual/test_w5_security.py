"""
تست: سخت‌سازیِ امنیتیِ W5 — مقایسه‌یِ زمان‌ثابتِ رازها، غیرفعال‌بودنِ مستنداتِ API، خنثی‌سازیِ تزریقِ فرمولِ اکسل،
و بسته‌بودنِ پورتِ دیتابیس به بیرون (فقط لوکال).

اجرا: python3 tests_manual/test_w5_security.py
"""
from __future__ import annotations

import asyncio
import io
import re
import sys
from pathlib import Path

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from openpyxl import load_workbook  # noqa: E402

from harness import reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app import main as app_main  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import customer_service, excel_export_service, order_service  # noqa: E402
from app.database.models import OrderType  # noqa: E402


async def test_secret_comparison_is_safe() -> None:
    eq = app_main._secrets_equal
    assert eq("abc", "abc") and not eq("abc", "abd") and not eq("abc", "abcd") and not eq("", "x")
    assert eq("یه-رمز-تصادفیِ-بلند", "یه-رمز-تصادفیِ-بلند"), "رازِ غیرِ ASCII هم بدونِ خطا مقایسه می‌شه"
    assert not eq(None, "x") and not eq("x", None)
    assert eq(None, None), "رفتارِ قبلی: دو None برابرند (فراخوان‌ها قبلاً None را رد می‌کنند)"
    print("✅ test_secret_comparison_is_safe PASSED")


def _route_paths(routes) -> set[str]:
    """مسیرها را از درختِ router جمع می‌کند. starlette 1.x موقعِ `include_router` یکِ
    `_IncludedRouter` تنبل می‌گذارد (route‌های واقعی زیرِ `original_router`‌اند)؛ از P21-B اپِ
    اصلی هم `observability_router` را include می‌کند، پس خواندنِ مستقیمِ `route.path` اینجا
    می‌شکست (همان کمکی که `test_p21_ops.py` دارد)."""
    found: set[str] = set()
    for route in routes:
        path = getattr(route, "path", None)
        if path:
            found.add(path)
        for attr in ("routes", "original_router", "router"):
            nested = getattr(route, attr, None)
            if nested is not None and hasattr(nested, "routes"):
                found |= _route_paths(nested.routes)
    return found


async def test_api_docs_are_disabled() -> None:
    assert app_main.app.docs_url is None and app_main.app.redoc_url is None and app_main.app.openapi_url is None
    paths = _route_paths(app_main.app.routes)
    assert not ({"/docs", "/redoc", "/openapi.json"} & paths)
    print("✅ test_api_docs_are_disabled PASSED")


async def test_database_port_is_local_only() -> None:
    compose = Path("docker-compose.yml").read_text(encoding="utf-8")
    ports = re.findall(r'-\s*"([^"]*5432[^"]*)"', compose)
    assert ports and all(p.startswith("127.0.0.1:") for p in ports), ports
    print("✅ test_database_port_is_local_only PASSED")


async def test_excel_export_neutralizes_formulas() -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(999901, 999902)
    evil = '=HYPERLINK("http://evil.example","click")'
    async with session_scope() as session:
        customer = await customer_service.get_or_create_customer(session, shop_bot_id, 999903, evil, None)
        order = await order_service.create_order(session, shop_bot_id, customer.id, OrderType.ORDER, "=1+1 کالا", 10_000)
        order.customer_address = "=cmd|' /C calc'!A0"
        order.checkout_answers = "@SUM(1+1)"
    async with session_scope() as session:
        customers_bytes = await excel_export_service.build_customers_workbook(session, shop_bot_id)
        orders_bytes = await excel_export_service.build_orders_workbook(session, shop_bot_id)
    seen_evil = 0
    for blob in (customers_bytes, orders_bytes):
        wb = load_workbook(io.BytesIO(blob))
        for ws in wb.worksheets:
            for row in ws.iter_rows():
                for cell in row:
                    assert cell.data_type != "f", f"فرمولِ اجراشدنی در {ws.title}!{cell.coordinate}: {cell.value!r}"
                    if isinstance(cell.value, str) and cell.value.startswith("="):
                        seen_evil += 1
    assert seen_evil >= 2, "متنِ مخرب باید به‌صورتِ متنِ ساده (نه حذف‌شده) در فایل بماند"
    print("✅ test_excel_export_neutralizes_formulas PASSED")


async def main() -> None:
    await test_secret_comparison_is_safe()
    await test_api_docs_are_disabled()
    await test_database_port_is_local_only()
    await test_excel_export_neutralizes_formulas()


if __name__ == "__main__":
    asyncio.run(main())
