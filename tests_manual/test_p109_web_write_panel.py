"""پ۱۰۹ · پنجرهٔ نوشتنیِ وب: احرازِ لینکِ یکبارمصرف، کوکیِ امضاشده، CSRF، دامنهٔ مالکیت و «بی‌پول».

ادعاها (همه در همین فایل سنجیده می‌شوند):
۱. بی‌`WEB_PANEL_SECRET` هر چهار مسیر `/web/*` وجود ندارند (۴۰۴) و اپِ سلامت هم هیچ `/web/*` ندارد.
۲. لینک **یک‌بار** مصرف می‌شود، مهلتِ ۱۵ دقیقه دارد، و کوکیِ نشست بدونِ امضایِ درست خوانده نمی‌شود.
۳. فرمِ بی‌نشانهٔ CSRF (یا با نشانهٔ نشستِ دیگر) هیچ چیزی را عوض نمی‌کند.
۴. شناسهٔ محصول/سفارشِ فروشگاهِ دیگر ⇒ «not-found» و همان ردیف دست‌نخورده می‌ماند.
۵. چهار فعلِ مجاز دقیقاً همان کارِ دکمهٔ ربات را می‌کنند و هر کدام **یکِ ردیفِ ممیزی** می‌گذارند.
۶. هیچ مسیرِ پولی از وب باز نیست: مجموعهٔ فعل‌ها ثابت است، کیف‌پول/پرداخت‌ها دست‌نخورده‌اند، و
   هیچ گذاری به `paid`/`refunded` از این در انجام نمی‌شود.
۷. دکمهٔ تازه در منو + `_KNOWN_MENU_BUTTONS` ثبت شده (قاعدهٔ ۶).

اجرا: python3 tests_manual/run_one.py test_p109_web_write_panel.py
"""
from __future__ import annotations

import asyncio
import sys
import urllib.parse

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from sqlalchemy import func, select  # noqa: E402

from app import main as app_main  # noqa: E402
from app.bots.main_bot import keyboards  # noqa: E402
from app.bots.main_bot import texts as main_texts  # noqa: E402
from app.bots.main_bot.router import _KNOWN_MENU_BUTTONS  # noqa: E402
from app.config import settings  # noqa: E402
from app.database.models import (  # noqa: E402
    AuditEventType,
    AuditLogEntry,
    OrderConsultation,
    OrderStatus,
    OrderType,
    Payment,
    Product,
    ShopBot,
    ShopOwner,
    WebPanelSession,
)
from app.database.session import engine, session_scope  # noqa: E402
from app.services import customer_service, web_panel_service  # noqa: E402
from app.web import panel as web_panel  # noqa: E402
from harness import reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

SECRET = "p109-panel-secret"
BASE = "https://panel.example.test"
OWNER_A = 10_900_000_001
BOT_A = 10_900_000_002
OWNER_B = 10_900_000_011
BOT_B = 10_900_000_012
CUSTOMER_TG = 10_900_000_021


# ============================================================================= ابزار
async def _call(app, method: str, path: str, headers: list[tuple[bytes, bytes]], body: bytes = b""):
    parts = urllib.parse.urlsplit(path)
    scope = {
        "type": "http", "asgi": {"version": "3.0", "spec_version": "2.3"}, "http_version": "1.1",
        "method": method, "scheme": "https", "path": parts.path, "raw_path": parts.path.encode(),
        "query_string": parts.query.encode(),
        "headers": [(b"host", b"panel.example.test")] + headers,
        "client": ("127.0.0.1", 5555), "server": ("panel.example.test", 443), "root_path": "",
    }

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    status: list[int] = []
    response_headers: list[tuple[bytes, bytes]] = []
    chunks = bytearray()

    async def send(message):
        if message["type"] == "http.response.start":
            status.append(message["status"])
            response_headers.extend(message.get("headers", []))
        elif message["type"] == "http.response.body":
            chunks.extend(message.get("body", b""))

    await app(scope, receive, send)
    return (status[0] if status else 0), response_headers, bytes(chunks)


def _cookie_from(headers: list[tuple[bytes, bytes]]) -> bytes:
    for key, value in headers:
        if key.lower() == b"set-cookie" and web_panel_service.COOKIE_NAME.encode() in value:
            return value.split(b";")[0].split(b"=", 1)[1]
    raise AssertionError(f"کوکی در پاسخ نیست: {headers}")


async def _login(app, owner_telegram_id: int) -> bytes:
    async with session_scope() as session:
        link = await web_panel_service.issue_link(session, owner_telegram_id, BASE)
    assert link, "لینک ساخته نشد"
    token = urllib.parse.urlsplit(link).query.split("t=", 1)[1]
    status, headers, body = await _call(app, "GET", f"/web/login?t={token}", [])
    assert status == 303, (status, body[:200])
    return _cookie_from(headers)


async def _seed_two_shops() -> dict:
    await reset_database()
    shop_a = await seed_usable_shop(OWNER_A, BOT_A, initial_balance_toman=100_000)
    shop_b = await seed_usable_shop(OWNER_B, BOT_B, initial_balance_toman=100_000)
    async with session_scope() as session:
        product_a = Product(shop_bot_id=shop_a, name="کیکِ A", price_toman=120_000, stock_quantity=7, is_active=True)
        product_b = Product(shop_bot_id=shop_b, name="کیکِ B", price_toman=90_000, stock_quantity=3, is_active=True)
        session.add_all([product_a, product_b])
        customer = await customer_service.get_or_create_customer(session, shop_a, CUSTOMER_TG, "مشتریِ تست", None)
        order = OrderConsultation(
            shop_bot_id=shop_a,
            customer_id=customer.id,
            type=OrderType.ORDER,
            summary="یکِ کیک",
            status=OrderStatus.CONFIRMED,
            confirmed=True,
            estimated_value_toman=120_000,
        )
        session.add(order)
        await session.flush()
        ids = {"shop_a": shop_a, "shop_b": shop_b, "product_a": product_a.id, "product_b": product_b.id, "order_a": order.id}
        await session.commit()
    return ids


async def _form(app, cookie: bytes, **fields) -> tuple[int, list, bytes]:
    payload = {**fields, "csrf": web_panel_service.csrf_token(int(cookie.split(b".")[0]))}
    body = urllib.parse.urlencode(payload).encode()
    return await _call(
        app,
        "POST",
        "/web/action",
        [(b"cookie", f"{web_panel_service.COOKIE_NAME}={cookie.decode()}".encode()), (b"content-type", b"application/x-www-form-urlencoded")],
        body,
    )


def _location(headers: list) -> str:
    for key, value in headers:
        if key.lower() == b"location":
            return value.decode()
    return ""


# ============================================================================= ۱
def test_routes_are_hidden_without_secret_and_absent_from_health_app() -> None:
    from test_p87_ops_endpoint import _paths_of  # noqa: PLC0415

    previous = settings.panel_secret
    try:
        settings.panel_secret = ""
        assert web_panel_service.enabled() is False
        assert web_panel_service.parse_cookie("1.abc") is None, "بی‌کلید هیچ کوکی‌ای پذیرفته نمی‌شود"
        assert web_panel_service.csrf_ok(1, "anything") is False
    finally:
        settings.panel_secret = previous

    health = _paths_of(app_main.build_health_app().routes)
    assert health == {"/health", "/metrics", "/ops/status", "/panel", "/ws/ops"}, sorted(health)
    main_paths = _paths_of(app_main.app.routes)
    for path in ("/web/login", "/web/panel", "/web/action", "/web/logout"):
        assert path in main_paths, sorted(main_paths)
    print("PASS test_routes_are_hidden_without_secret_and_absent_from_health_app")


# ============================================================================= ۲
async def test_disabled_secret_returns_404() -> None:
    app = app_main.app
    previous = settings.panel_secret
    try:
        settings.panel_secret = ""
        for method, path in (
            ("GET", "/web/login?t=x"),
            ("GET", "/web/panel"),
            ("POST", "/web/logout"),
            ("POST", "/web/action"),
        ):
            assert (await _call(app, method, path, [], b""))[0] == 404, f"{method} {path}"
    finally:
        settings.panel_secret = previous
    print("PASS test_disabled_secret_returns_404")


async def test_link_is_single_use_and_expiry_stops_the_session() -> None:
    import datetime

    await _seed_two_shops()
    app = app_main.app
    previous = settings.panel_secret
    settings.panel_secret = SECRET
    try:
        async with session_scope() as session:
            link = await web_panel_service.issue_link(session, OWNER_A, BASE)
        token = urllib.parse.urlsplit(link).query.split("t=", 1)[1]
        status, headers, body = await _call(app, "GET", f"/web/login?t={token}", [])
        assert status == 303, (status, body[:200])
        cookie = _cookie_from(headers)
        assert token not in cookie.decode() and len(cookie) >= 32, "کوکی باید امضا داشته باشد نه خودِ توکن"

        status2, _h2, _b2 = await _call(app, "GET", f"/web/login?t={token}", [])
        assert status2 == 401, "لینکِ سوخته دوباره کار می‌کند"

        async with session_scope() as session:
            rows = (await session.execute(select(func.count()).select_from(WebPanelSession))).scalar_one()
            assert rows == 1, rows
            row = (await session.execute(select(WebPanelSession).limit(1))).scalar_one()
            assert row.used_at is not None and row.token_hash != token, "هشِ توکن ذخیره نمی‌شود"
            assert token not in row.token_hash
            row.expires_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=1)
            await session.commit()

        status3, _h3, _b3 = await _call(
            app, "GET", "/web/panel", [(b"cookie", f"{web_panel_service.COOKIE_NAME}={cookie.decode()}".encode())]
        )
        assert status3 == 401, "نشستِ منقضی شده هنوز کار می‌کند"
    finally:
        settings.panel_secret = previous
    print("PASS test_link_is_single_use_and_expiry_stops_the_session")


async def test_forged_cookie_is_not_read() -> None:
    previous = settings.panel_secret
    settings.panel_secret = SECRET
    try:
        good = web_panel_service.cookie_value(7)
        assert web_panel_service.parse_cookie(good) == 7
        assert web_panel_service.parse_cookie("7." + good.split(".")[1][:-1] + "0") is None
        assert web_panel_service.parse_cookie("8." + good.split(".")[1]) is None
        assert web_panel_service.parse_cookie("not-a-cookie") is None
        assert web_panel_service.parse_cookie(None) is None
        assert web_panel_service.csrf_ok(7, web_panel_service.csrf_token(7)) is True
        assert web_panel_service.csrf_ok(7, web_panel_service.csrf_token(8)) is False
        assert web_panel_service.csrf_ok(7, None) is False
    finally:
        settings.panel_secret = previous
    print("PASS test_forged_cookie_is_not_read")


# ============================================================================= ۳
async def test_form_without_valid_csrf_changes_nothing() -> None:
    ids = await _seed_two_shops()
    app = app_main.app
    previous = settings.panel_secret
    settings.panel_secret = SECRET
    try:
        cookie = await _login(app, OWNER_A)
        body = urllib.parse.urlencode(
            {"action": "product_set_stock", "target": str(ids["product_a"]), "value": "999", "csrf": "guess"}
        ).encode()
        headers = [(b"cookie", f"{web_panel_service.COOKIE_NAME}={cookie.decode()}".encode()), (b"content-type", b"application/x-www-form-urlencoded")]
        status, resp_headers, _raw = await _call(app, "POST", "/web/action", headers, body)
        assert status == 303 and "note=csrf" in _location(resp_headers), _location(resp_headers)
        async with session_scope() as session:
            product = await session.get(Product, ids["product_a"])
            assert product.stock_quantity == 7, "فرمِ بی‌CSRF موجودی را عوض کرد"
    finally:
        settings.panel_secret = previous
    print("PASS test_form_without_valid_csrf_changes_nothing")


# ============================================================================= ۴ و ۵
async def test_actions_are_scoped_and_audited() -> None:
    ids = await _seed_two_shops()
    app = app_main.app
    previous = settings.panel_secret
    settings.panel_secret = SECRET
    try:
        cookie = await _login(app, OWNER_A)
        before = await _audit_count()

        # ردیفِ فروشگاهِ دیگر ⇒ نه‌یافت (و دست‌نخورده)
        _s, h, _b = await _form(app, cookie, action="product_set_price", target=str(ids["product_b"]), value="1")
        assert "note=not-found" in _location(h), _location(h)
        async with session_scope() as session:
            other = await session.get(Product, ids["product_b"])
            assert other.price_toman == 90_000, "قیمتِ فروشگاهِ دیگر عوض شد"

        _s, h, _b = await _form(app, cookie, action="product_toggle_active", target=str(ids["product_a"]))
        assert "note=inactive" in _location(h), _location(h)
        _s, h, _b = await _form(app, cookie, action="product_set_stock", target=str(ids["product_a"]), value="12")
        assert "note=stock" in _location(h), _location(h)
        _s, h, _b = await _form(app, cookie, action="product_set_price", target=str(ids["product_a"]), value="135000")
        assert "note=price" in _location(h), _location(h)
        _s, h, _b = await _form(app, cookie, action="order_next_step", target=str(ids["order_a"]))
        assert "note=advanced" in _location(h), _location(h)
        # عددِ نامجاز و فعلِ ناشناخته
        _s, h, _b = await _form(app, cookie, action="product_set_price", target=str(ids["product_a"]), value="x")
        assert "note=value-range" in _location(h), _location(h)
        _s, h, _b = await _form(app, cookie, action="wallet_topup", target=str(ids["product_a"]), value="1")
        assert "note=action-not-allowed" in _location(h), _location(h)

        async with session_scope() as session:
            product = await session.get(Product, ids["product_a"])
            order = await session.get(OrderConsultation, ids["order_a"])
            assert product.is_active is False and product.stock_quantity == 12 and product.price_toman == 135_000, (
                product.is_active,
                product.stock_quantity,
                product.price_toman,
            )
            assert order.status == OrderStatus.PROCESSING, order.status
            row = (await session.execute(select(WebPanelSession).limit(1))).scalar_one()
            assert row.actions_count == 4, row.actions_count
        after = await _audit_count()
        assert after - before == 4, f"هر نوشتن باید یکِ ردیفِ ممیزی بگذارد: {after - before}"
        status, _h, raw = await _call(
            app, "GET", "/web/panel", [(b"cookie", f"{web_panel_service.COOKIE_NAME}={cookie.decode()}".encode())]
        )
        text = raw.decode("utf-8", errors="replace")
        assert status == 200 and "کیکِ A" in text and "کیکِ B" not in text, text[:300]
        assert SECRET not in text and "type=hidden name=csrf" in text
    finally:
        settings.panel_secret = previous
    print("PASS test_actions_are_scoped_and_audited")


async def _audit_count() -> int:
    async with session_scope() as session:
        return int(
            (
                await session.execute(
                    select(func.count()).select_from(AuditLogEntry).where(AuditLogEntry.event_type == AuditEventType.WEB_PANEL_ACTION)
                )
            ).scalar_one()
        )


# ============================================================================= ۶
async def test_no_money_path_is_reachable_from_the_web() -> None:
    assert web_panel_service.ACTIONS == {
        "product_toggle_active",
        "product_set_stock",
        "product_set_price",
        "order_next_step",
    }, "فعل‌هایِ وب باید همان چهار کارِ بی‌پول بمانند"
    ids = await _seed_two_shops()
    app = app_main.app
    previous = settings.panel_secret
    settings.panel_secret = SECRET
    try:
        cookie = await _login(app, OWNER_A)
        async with session_scope() as session:
            wallet_before = (await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == OWNER_A))).scalar_one().wallet_balance_toman
        for action, target, value in (
            ("order_next_step", ids["order_a"], ""),
            ("order_next_step", ids["order_a"], ""),
            ("order_next_step", ids["order_a"], ""),
        ):
            await _form(app, cookie, action=action, target=str(target), value=value)
        async with session_scope() as session:
            owner = (await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == OWNER_A))).scalar_one()
            order = await session.get(OrderConsultation, ids["order_a"])
            payments = (await session.execute(select(func.count()).select_from(Payment))).scalar_one()
            assert owner.wallet_balance_toman == wallet_before, "کیف‌پول از وب عوض شد"
            assert order.status in (OrderStatus.PROCESSING, OrderStatus.SHIPPED, OrderStatus.COMPLETED), order.status
            assert order.status not in (OrderStatus.PAID, OrderStatus.REFUNDED, OrderStatus.REFUND_PENDING)
            assert payments == 0, payments
    finally:
        settings.panel_secret = previous
    print("PASS test_no_money_path_is_reachable_from_the_web")


# ============================================================================= ۷
async def test_revoke_and_menu_registration() -> None:
    ids = await _seed_two_shops()
    del ids
    app = app_main.app
    previous = settings.panel_secret
    settings.panel_secret = SECRET
    try:
        cookie = await _login(app, OWNER_A)
        async with session_scope() as session:
            await web_panel_service.issue_link(session, OWNER_A, BASE)
        async with session_scope() as session:
            count = await web_panel_service.revoke_for_owner(session, OWNER_A)
        assert count == 2, count  # نشستِ همین مرورگر + لینکِ سوخته‌نشدهٔ دوم
        status, _h, _b = await _call(
            app, "GET", "/web/panel", [(b"cookie", f"{web_panel_service.COOKIE_NAME}={cookie.decode()}".encode())]
        )
        assert status == 401, "لینکِ ابطال‌شده باید نشست را هم ببندد"

        assert main_texts.WEB_PANEL_BUTTON in _KNOWN_MENU_BUTTONS, "دکمهٔ تازه ثبت نشده (قاعدهٔ ۶)"
        for mode in ("sales", "consultation"):
            labels = {button.text for row in keyboards.shop_owner_panel_keyboard(mode).keyboard for button in row}
            assert main_texts.WEB_PANEL_BUTTON in labels, mode
        cbs = [
            button.callback_data
            for row in keyboards.web_panel_keyboard().inline_keyboard
            for button in row
            if button.callback_data
        ]
        assert "web_panel_revoke" in cbs and all(len(item.encode("utf-8")) <= 64 for item in cbs), cbs
    finally:
        settings.panel_secret = previous
    print("PASS test_revoke_and_menu_registration")


async def main() -> None:
    test_routes_are_hidden_without_secret_and_absent_from_health_app()
    await test_disabled_secret_returns_404()
    await test_link_is_single_use_and_expiry_stops_the_session()
    await test_forged_cookie_is_not_read()
    await test_form_without_valid_csrf_changes_nothing()
    await test_actions_are_scoped_and_audited()
    await test_no_money_path_is_reachable_from_the_web()
    await test_revoke_and_menu_registration()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
