"""پ۱۰۹ · پنجرهٔ نوشتنیِ وب برایِ فروشگاه‌دار (مسیرهایِ `/web/*`).

چرا این فایل جدا از `/panel`ِ عملیاتی است: `/panel` (پ۹۱) با `METRICS_TOKEN` فقط *دیدن* می‌دهد و رویِ
اپِ سلامت هم سرویس می‌شود. اینجا درِ *تغییر دادن* است؛ پس احرازِ جدا (لینکِ یکبارمصرفِ صادرشده از
رباتِ مرکزی + کوکیِ امضاشده با `WEB_PANEL_SECRET`)، نشانهٔ CSRF در هر فرم، و فقط در اپِ اصلی باز
می‌شود — در `build_health_app()` هیچ `/web/*` وجود ندارد.

هیچ‌چیز اینجا پول را جابه‌جا نمی‌کند: نه پرداخت، نه استرداد، نه شارژِ کیف‌پول، نه پیام به مشتری.
چهار فعلِ مجاز (`web_panel_service.ACTIONS`) همان کارِ همان دکمهٔ ربات است و از همان سرویس‌ها
می‌گذرند (مالکیتِ ردیف، قفلِ سطری، گذارِ مجاز، ردیفِ ممیزی).

بدونِ `WEB_PANEL_SECRET` هر چهار مسیر ۴۰۴ند؛ یعنی با تنظیماتِ فعلیِ همین استقرار چیزی باز نمی‌شود.
"""
from __future__ import annotations

import html
import logging
import urllib.parse

from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select

from app.bots.main_bot import texts as panel_texts
from app.config import settings
from app.database.models import OrderConsultation, Product
from app.database.session import session_scope
from app.services import http_guard, order_state, web_panel_service

logger = logging.getLogger(__name__)

panel_router = APIRouter()

LOGIN_FAIL_LIMIT_PER_MINUTE = 20
PANEL_ROWS_LIMIT = 30
_MODE_LABELS = {"sales": "🛍 فروشِ محصول (فروشگاه)", "consultation": "💬 مشاوره و خدمات"}

_NOTES: dict[str, str] = {
    "active": "✅ نمایشِ این محصول در ربات روشن شد.",
    "inactive": "🙈 نمایشِ این محصول در ربات خاموش شد.",
    "stock": "✅ موجودیِ این محصول ثبت شد.",
    "price": "✅ قیمتِ این محصول ثبت شد.",
    "advanced": "✅ سفارش به قدمِ بعدی رفت.",
    "expired": "🚫 این لینک منقضی یا ابطال شده است. از رباتِ مرکزی لینکِ تازه بگیر.",
    "csrf": "🚫 نشانهٔ محافظتِ فرم درست نبود؛ صفحه را تازه کن و دوباره امتحان کن.",
    "not-found": "🚫 این ردیف در فروشگاهِ تو پیدا نشد.",
    "no-next-step": "🚫 این سفارش قدمِ بعدی ندارد (یا تکمیل/لغو شده است).",
    "value-range": "🚫 عددی که نوشتی مجاز نیست.",
    "value-required": "🚫 برایِ این کار باید عدد بنویسی.",
    "illegal": "🚫 این گذارِ وضعیت مجاز نیست.",
    "session-limit": "🚫 سقفِ نوشتنِ این نشست پر شد؛ از ربات لینکِ تازه بگیر.",
    "action-not-allowed": "🚫 این کار در پنلِ وب انجام نمی‌شود.",
}


def _note_key(result: tuple[bool, str]) -> str:
    ok, detail = result
    if ok:
        if detail in _NOTES:
            return detail
        return "advanced"
    if detail in _NOTES:
        return detail
    return "illegal" if detail.startswith("illegal") else "expired"


def _client_ip(request: Request) -> str:
    if settings.trust_proxy_headers:
        first = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
        if first:
            return first[:64]
    client = getattr(request, "client", None)
    return (getattr(client, "host", None) or "unknown")[:64]


def _is_https(request: Request) -> bool:
    if settings.trust_proxy_headers and (request.headers.get("x-forwarded-proto") or "").startswith("https"):
        return True
    return request.url.scheme == "https"


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)


async def _dashboard(request: Request):
    """همهیِ پرس‌وجوها در یکِ scope (درسِ پ۱۰۴: صدا زدنِ سرویس رویِ سشنِ بسته‌شده اتصال نشتی می‌سازد).

    خروجی: `(row, shop_bot, products, orders)` و `(None, None, [], [])` وقتی نشست سالم نیست.
    """
    row_id = web_panel_service.parse_cookie(request.cookies.get(web_panel_service.COOKIE_NAME))
    if row_id is None:
        return None, None, [], []
    async with session_scope() as session:
        row = await web_panel_service.load_session(session, row_id)
        if row is None:
            return None, None, [], []
        shop = await web_panel_service.shop_for_owner(session, row.owner_telegram_id)
        if shop is None:
            return None, None, [], []
        products = list(
            (
                await session.execute(
                    select(Product)
                    .where(Product.shop_bot_id == shop.id)
                    .order_by(Product.id.desc())
                    .limit(PANEL_ROWS_LIMIT)
                )
            ).scalars().all()
        )
        orders = list(
            (
                await session.execute(
                    select(OrderConsultation)
                    .where(
                        OrderConsultation.shop_bot_id == shop.id,
                        OrderConsultation.status.in_(
                            [order_state.CONFIRMED, order_state.PAID, order_state.PROCESSING, order_state.SHIPPED]
                        ),
                    )
                    .order_by(OrderConsultation.id.desc())
                    .limit(PANEL_ROWS_LIMIT)
                )
            )
            .scalars()
            .all()
        )
        await web_panel_service.touch(session, row)
        return row, shop, products, orders


def _csrf_field(row_id: int) -> str:
    return f'<input type=hidden name=csrf value="{_esc(web_panel_service.csrf_token(row_id))}">'


def _form(row_id: int, action: str, target: int, *, label: str, number_min: int | None = None) -> str:
    fields = (
        f"{_csrf_field(row_id)}"
        f'<input type=hidden name=action value="{_esc(action)}">'
        f'<input type=hidden name=target value="{target}">'
    )
    number = "" if number_min is None else f'<input type=number name=value min={number_min} required>'
    return f"<form method=post action=/web/action class=inl>{fields}{number}<button>{_esc(label)}</button></form>"


def _products_table(row_id: int, products) -> str:
    if not products:
        return "<p class=muted>هنوز محصولی ثبت نکرده‌ای.</p>"
    lines = []
    for product in products:
        stock = "—" if product.stock_quantity is None else f"{product.stock_quantity:,}"
        retired = " 🗄 بایگانی‌شده" if getattr(product, "retired_at", None) else ""
        lines.append(
            "<tr>"
            f"<td>{_esc(product.name[:70])}{retired}</td>"
            f"<td>{f'{product.price_toman:,}'} تومان</td>"
            f"<td>{stock}</td>"
            f"<td>{'✅ فعال' if product.is_active else '⛔️ غیرفعال'}</td>"
            f"<td>{_form(row_id, 'product_toggle_active', product.id, label='تغییرِ وضعیت')}</td>"
            f"<td>{_form(row_id, 'product_set_stock', product.id, label='ثبتِ موجودی', number_min=0)}</td>"
            f"<td>{_form(row_id, 'product_set_price', product.id, label='ثبتِ قیمت', number_min=1)}</td>"
            "</tr>"
        )
    return (
        "<table><tr><th>نام</th><th>قیمت</th><th>موجودی</th><th>وضعیت</th><th>نمایش/پنهان</th>"
        "<th>موجودیِ تازه</th><th>قیمتِ تازه</th></tr>" + "".join(lines) + "</table>"
    )


def _orders_table(row_id: int, orders) -> str:
    if not orders:
        return "<p class=muted>سفارشِ در جریانی نیست.</p>"
    lines = []
    for order in orders:
        next_label = panel_texts.order_next_status_button_label(order.status)
        action = _form(row_id, "order_next_step", order.id, label=next_label) if next_label else "—"
        lines.append(
            "<tr>"
            f"<td>{_esc(panel_texts.order_status_label(order.status))}</td>"
            f"<td>{_esc((order.summary or '')[:80])}</td>"
            f"<td>{f'{(order.estimated_value_toman or 0):,}'} تومان</td>"
            f"<td>{action}</td>"
            "</tr>"
        )
    return (
        "<table><tr><th>وضعیت</th><th>خلاصه</th><th>ارزشِ تخمینی</th><th>قدمِ بعدی</th></tr>"
        + "".join(lines)
        + "</table>"
    )


def _panel_html(row, shop, products, orders, note: str) -> str:
    mode_key = shop.tenant_mode.value if hasattr(shop.tenant_mode, "value") else shop.tenant_mode
    return (
        "<!doctype html><html lang=fa dir=rtl><head><meta charset=utf-8>"
        "<meta name=viewport content='width=device-width,initial-scale=1'>"
        f"<title>پنلِ {_esc(shop.bot_username or 'فروشگاه')}</title><style>"
        "body{font-family:system-ui,Tahoma;margin:1.2rem;background:#f6f7f9;color:#1f2933;max-width:72rem}"
        "h1{font-size:1.2rem}h2{font-size:1rem;margin-top:1.4rem;border-bottom:1px solid #d7dbe0;padding-bottom:.2rem}"
        "table{border-collapse:collapse;width:100%;background:#fff;font-size:.9rem}"
        "th,td{border:1px solid #d7dbe0;padding:.35rem .5rem;text-align:right}th{background:#eef1f4}"
        "form.inl{display:inline}button{font:inherit;padding:.15rem .5rem}"
        ".note{background:#fff;border:1px solid #d7dbe0;padding:.5rem .7rem;border-radius:.4rem}"
        ".muted{color:#5a6572;font-size:.85rem}"
        "</style></head><body>"
        f"<h1>🌐 پنلِ «{_esc(shop.bot_username or 'فروشگاه')}» — {_esc(_MODE_LABELS.get(mode_key, mode_key))}</h1>"
        + (f"<p class=note>{_esc(note)}</p>" if note else "")
        + "<p class=muted>این صفحه از لینکِ یکبارمصرفِ رباتِ مرکزی باز می‌شود؛ "
        + f"{row.actions_count} نوشتن در این نشست انجام شده است. هر تغییر در دفترِ ممیزی ثبت می‌شود "
        "و هیچ پولی جابه‌جا نمی‌شود.</p>"
        + f"<h2>محصولات ({len(products)})</h2>" + _products_table(row.id, products)
        + f"<h2>سفارش‌هایِ در جریان ({len(orders)})</h2>" + _orders_table(row.id, orders)
        + "<h2>خروج</h2><form method=post action=/web/logout><button>بستنِ این نشست</button></form>"
        + "</body></html>"
    )


def _unauthorized() -> Response:
    return HTMLResponse(
        "<!doctype html><html lang=fa dir=rtl><meta charset=utf-8><body style='font-family:Tahoma;margin:2rem'>"
        "<p>🚫 این لینک منقضی یا ابطال شده است، یا کوکیِ این مرورگر معتبر نیست.</p>"
        "<p>در رباتِ مرکزی دکمهٔ «🌐 پنلِ وب» را دوباره بزن تا لینکِ تازه بگیری.</p></body></html>",
        status_code=401,
        media_type="text/html; charset=utf-8",
    )


@panel_router.get("/web/login")
async def web_login(request: Request) -> Response:
    if not web_panel_service.enabled():
        return Response(status_code=404)
    if not http_guard.allow((_client_ip(request), "web-login"), LOGIN_FAIL_LIMIT_PER_MINUTE):
        logger.warning("سقفِ تلاشِ لینکِ پنلِ وب از IP=%s رد شد.", _client_ip(request))
        return Response(status_code=429, headers={"Retry-After": "60"}, media_type="text/plain; charset=utf-8")
    token = (request.query_params.get("t") or "")[:128]
    async with session_scope() as session:
        row = await web_panel_service.redeem(session, token, user_agent=request.headers.get("user-agent") or "")
        row_id = row.id if row is not None else None
        max_age = web_panel_service.SESSION_TTL_SECONDS
    if row_id is None:
        return _unauthorized()
    response = RedirectResponse("/web/panel", status_code=303)
    response.set_cookie(
        web_panel_service.COOKIE_NAME,
        web_panel_service.cookie_value(row_id),
        max_age=max_age,
        httponly=True,
        samesite="strict",
        secure=_is_https(request),
        path="/",
    )
    return response


@panel_router.get("/web/panel")
async def web_panel(request: Request) -> Response:
    if not web_panel_service.enabled():
        return Response(status_code=404)
    row, shop, products, orders = await _dashboard(request)
    if row is None:
        return _unauthorized()
    note = _NOTES.get((request.query_params.get("note") or "")[:32], "")
    return HTMLResponse(_panel_html(row, shop, products, orders, note), media_type="text/html; charset=utf-8")


async def _read_form(request: Request) -> dict[str, str]:
    """فرمِ x-www-form-urlencoded بدونِ وابستگیِ تازه (python-multipart نصب نیست و اضافه نمی‌شود)."""
    raw = (await request.body())[:8192].decode("utf-8", errors="replace")
    parsed = urllib.parse.parse_qs(raw, keep_blank_values=True)
    return {key: values[0] for key, values in parsed.items() if values}


@panel_router.post("/web/action")
async def web_action(request: Request) -> Response:
    if not web_panel_service.enabled():
        return Response(status_code=404)
    row_id = web_panel_service.parse_cookie(request.cookies.get(web_panel_service.COOKIE_NAME))
    if row_id is None:
        return _unauthorized()
    form = await _read_form(request)
    if not web_panel_service.csrf_ok(row_id, form.get("csrf")):
        logger.warning("فرمِ پنلِ وب بی‌نشانهٔ CSRF درست از IP=%s رد شد.", _client_ip(request))
        return RedirectResponse("/web/panel?note=csrf", status_code=303)
    action = (form.get("action") or "")[:40]
    target = (form.get("target") or "").strip()
    if not target.isdigit():
        return RedirectResponse("/web/panel?note=not-found", status_code=303)
    raw_value = (form.get("value") or "").strip()
    value: int | None = None
    if raw_value:
        if not raw_value.isdigit():
            return RedirectResponse("/web/panel?note=value-range", status_code=303)
        value = int(raw_value)

    async with session_scope() as session:
        row = await web_panel_service.load_session(session, row_id)
        if row is None:
            return RedirectResponse("/web/panel?note=expired", status_code=303)
        shop = await web_panel_service.shop_for_owner(session, row.owner_telegram_id)
        if shop is None:
            return RedirectResponse("/web/panel?note=not-found", status_code=303)
        result = await web_panel_service.apply_action(
            session, row=row, shop_bot=shop, action=action, target_id=int(target), value=value
        )
        if not result[0]:
            await session.rollback()
    return RedirectResponse(f"/web/panel?note={_note_key(result)}", status_code=303)


@panel_router.post("/web/logout")
async def web_logout() -> Response:
    if not web_panel_service.enabled():
        return Response(status_code=404)
    response = RedirectResponse("/web/panel", status_code=303)
    response.delete_cookie(web_panel_service.COOKIE_NAME, path="/")
    return response
