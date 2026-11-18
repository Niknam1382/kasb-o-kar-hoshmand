"""پ۱۱۴ · دیدنی‌بودنِ دکمهٔ «🌐 پنلِ وب» (خواستهٔ مالک: محو‌کردنِ دکمه پیش ازِ روشن‌کردنِ قابلیت).

ادعاها (همه در همین فایل سنجیده می‌شوند):
۱. ستونِ سراسریِ `admin_settings.web_panel_enabled` وجود دارد، پیش‌فرضِ سرور `true` است و
   مایگریشنِ پ۱۱۴ افزودنی و برگشتنی است (یکِ alembic head).
۲. کیبوردِ پنلِ فروشگاه‌دار دکمه را فقط با `web_panel=True` می‌سازد (هر دو مود) — یعنی «پنهان»
   یعنی نبودِ دکمه، نه دکمه‌ای که بعد ازِ زدن «خاموش است» می‌گوید.
۳. `panel_keyboard` دو شرط را با هم می‌پاید: سوئیچِ ادمین و تنظیم‌شدنِ `WEB_PANEL_SECRET`.
۴. سوئیچِ ادمین مقدار را عوض می‌کند و یکِ ردیفِ ممیزی می‌گذارد.
۵. وقتی سوئیچ خاموش است `/web/login` بی‌مصرفِ لینک ۴۰۴ می‌دهد (ورودِ نو بسته)، ولی نشستِ
   صادرشده‌یِ پیش ازِ خاموش‌کردن با ۴۰۴ مواجه نمی‌شود (بی‌قطعِ وسطِ کار).

اجرا: python3 tests_manual/run_one.py test_p114_web_panel_visibility.py
"""
from __future__ import annotations

import asyncio
import re
import sys
import types
import urllib.parse
from pathlib import Path

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from sqlalchemy import select, text  # noqa: E402

from app import main as app_main  # noqa: E402
from app.bots.main_bot import keyboards  # noqa: E402
from app.bots.main_bot import texts as main_texts  # noqa: E402
from app.bots.main_bot.handlers import admin as admin_handlers  # noqa: E402
from app.bots.main_bot.handlers import owner_common  # noqa: E402
from app.config import settings  # noqa: E402
from app.database.models import AuditEventType, AuditLogEntry, TenantMode  # noqa: E402
from app.database.session import engine, session_scope  # noqa: E402
from app.services import admin_settings_service, web_panel_service  # noqa: E402
from harness import reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

SECRET = "p114-panel-secret"
BASE = "https://panel.example.test"
OWNER = 11_400_000_001
BOT = 11_400_000_002


def _labels(markup) -> list[str]:
    return [str(button.text) for row in markup.keyboard for button in row]


async def _call(app, method: str, path: str, headers: list[tuple[bytes, bytes]], body: bytes = b"", *, want_headers: bool = False):
    parts = urllib.parse.urlsplit(path)
    scope = {
        "type": "http", "asgi": {"version": "3.0", "spec_version": "2.3"}, "http_version": "1.1",
        "method": method, "scheme": "https", "path": parts.path, "raw_path": parts.path.encode(),
        "query_string": parts.query.encode(),
        "headers": [(b"host", b"panel.example.test")] + headers,
        "client": ("127.0.0.1", 5577), "server": ("panel.example.test", 443), "root_path": "",
    }

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    status: list[int] = []
    response_headers: list[tuple[bytes, bytes]] = []

    async def send(message):
        if message["type"] == "http.response.start":
            status.append(message["status"])
            response_headers.extend(message.get("headers", []))

    await app(scope, receive, send)
    code = status[0] if status else 0
    return (code, response_headers) if want_headers else code


def _cookie_from(headers: list[tuple[bytes, bytes]]) -> bytes:
    for key, value in headers:
        if key.lower() == b"set-cookie" and web_panel_service.COOKIE_NAME.encode() in value:
            return value.split(b";")[0].split(b"=", 1)[1]
    raise AssertionError("کوکیِ نشست در پاسخِ ۳۰۳ نیست")


async def _set_switch(value: bool) -> None:
    async with session_scope() as session:
        row = await admin_settings_service.get_admin_settings(session)
        row.web_panel_enabled = value
        await session.commit()


async def test_column_exists_with_safe_default() -> None:
    async with session_scope() as session:
        default = (
            await session.execute(
                text(
                    "select column_default, is_nullable from information_schema.columns "
                    "where table_name = 'admin_settings' and column_name = 'web_panel_enabled'"
                )
            )
        ).first()
    assert default is not None, "ستونِ پ۱۱۴ در دیتابیس نیست (ایمیج قدیمی است؟)"
    assert "true" in (default[0] or "").lower(), default
    assert default[1] == "NO", "ستون باید خالی‌ناپذیر باشد"

    revisions, parents = set(), set()
    files = sorted(Path("migrations/versions").glob("*.py"))
    for path in files:
        body = path.read_text(encoding="utf-8")
        rev = re.search(r"^revision(?:\s*:\s*str)?\s*=\s*[\"']([^\"']+)[\"']", body, re.M)
        assert rev, path.name
        revisions.add(rev.group(1))
        down = re.search(r"^down_revision[^=]*=\s*(.+)$", body, re.M)
        if down:
            parents.update(re.findall(r"[\"']([0-9a-f]{8,})[\"']", down.group(1)))
    heads = revisions - parents
    # پ۱۲۰: چیزی که قاعدهٔ پروژه می‌گوید «همیشه یکِ head» است، نه «هد همین عدد باشد» — با هر
    # مایگریشنِ افزودنیِ تازه، پینِ عددِ هدِ خودِ پ۱۱۴ می‌شکست (و تستِ پ۱۱۴ عملاً بی‌معنی).
    assert len(heads) == 1, f"همیشه فقط یکِ alembic head لازم است؛ دیده شد: {sorted(heads)}"
    assert "c9e2f4a7b135" in revisions, "رِویشنِ پ۱۴ از تاریخچهٔ مایگریشن‌ها بیرون افتاده است"
    p114 = [path for path in files if "p114_web_panel_switch" in path.name]
    assert len(p114) == 1, p114
    body = p114[0].read_text(encoding="utf-8")
    assert "def downgrade() -> None:" in body and "drop_column" in body, "رِویشنِ پ۱۱۴ باید بازگشت داشته باشد"
    print("✅ test_column_exists_with_safe_default PASSED")


async def test_keyboard_hides_button_when_switch_off() -> None:
    for mode in (TenantMode.SALES, TenantMode.CONSULTATION):
        shown = _labels(keyboards.shop_owner_panel_keyboard(mode, web_panel=True))
        assert main_texts.WEB_PANEL_BUTTON in shown, mode
        hidden = _labels(keyboards.shop_owner_panel_keyboard(mode, web_panel=False))
        assert main_texts.WEB_PANEL_BUTTON not in hidden, mode
        # پنهان‌کردنِ این دکمه نباید بقیهٔ منو را عوض کند (چینشِ دونفره و تعدادِ فعل‌ها).
        assert len(shown) == len(hidden) + 1, (mode, shown, hidden)
    print("✅ test_keyboard_hides_button_when_switch_off PASSED")


async def test_panel_keyboard_needs_both_switch_and_secret() -> None:
    saved = settings.panel_secret
    try:
        settings.panel_secret = SECRET
        await _set_switch(True)
        async with session_scope() as session:
            with_button = await owner_common.panel_keyboard(session, TenantMode.SALES)
        assert main_texts.WEB_PANEL_BUTTON in _labels(with_button), "با سوئیچِ روشن + راز، دکمه باید باشد"

        await _set_switch(False)
        async with session_scope() as session:
            without_button = await owner_common.panel_keyboard(session, TenantMode.SALES)
        assert main_texts.WEB_PANEL_BUTTON not in _labels(without_button), "سوئیچِ خاموش ⇒ دکمه محو"

        await _set_switch(True)
        settings.panel_secret = ""
        async with session_scope() as session:
            no_secret = await owner_common.panel_keyboard(session, TenantMode.SALES)
        assert main_texts.WEB_PANEL_BUTTON not in _labels(no_secret), "بی‌راز ⇒ دکمه محو (auto-hide)"
    finally:
        settings.panel_secret = saved
    print("✅ test_panel_keyboard_needs_both_switch_and_secret PASSED")


async def test_admin_toggle_flips_value_and_audits() -> None:
    before = None
    async with session_scope() as session:
        before = (await admin_settings_service.get_admin_settings(session)).web_panel_enabled

    answers: list[str] = []
    edits: list[object] = []

    async def _answer(text: str = "") -> None:
        answers.append(text)

    async def _edit(reply_markup=None) -> None:
        edits.append(reply_markup)

    callback = types.SimpleNamespace(
        from_user=types.SimpleNamespace(id=777),
        message=types.SimpleNamespace(edit_reply_markup=_edit),
        answer=_answer,
    )
    async with session_scope() as session:
        await admin_handlers.cb_toggle_web_panel(callback, session)
        await session.commit()

    async with session_scope() as session:
        after = (await admin_settings_service.get_admin_settings(session)).web_panel_enabled
        entries = (
            await session.execute(
                select(AuditLogEntry).where(
                    AuditLogEntry.event_type == AuditEventType.KILL_SWITCH_TOGGLED,
                    AuditLogEntry.details.like("%web_panel_enabled%"),
                )
            )
        ).scalars().all()
    assert after != before, "سوئیچ مقدار را عوض نکرد"
    assert entries, "ردیفِ ممیزی گذاشته نشد"
    assert answers and (main_texts.WEB_PANEL_TOGGLED_ON if after else main_texts.WEB_PANEL_TOGGLED_OFF) == answers[0]
    assert edits, "کیبوردِ صفحهٔ تنظیمات تازه نشد"

    async with session_scope() as session:
        await admin_handlers.cb_toggle_web_panel(callback, session)
        await session.commit()
    async with session_scope() as session:
        back = (await admin_settings_service.get_admin_settings(session)).web_panel_enabled
    assert back == before, "دوباره زدنِ سوئیچ باید به حالتِ اول برگردد"
    print("✅ test_admin_toggle_flips_value_and_audits PASSED")


async def test_new_login_blocked_while_hidden_but_live_session_survives() -> None:
    saved = settings.panel_secret
    app = app_main.app
    try:
        settings.panel_secret = SECRET
        await seed_usable_shop(OWNER, BOT)
        async with session_scope() as session:
            link = await web_panel_service.issue_link(session, OWNER, BASE)
        token = urllib.parse.urlsplit(link).query.split("t=", 1)[1]

        await _set_switch(False)
        status = await _call(app, "GET", f"/web/login?t={token}", [])
        assert status == 404, f"سوئیچِ خاموش ⇒ ورودِ نو باید ۴۰۴ دهد؛ دیده شد {status}"

        # لینک هنوز مصرف نشده است (۴۰۴ پیش ازِ redeem) ⇒ با روشن‌کردنِ دوباره همان لینک کار می‌کند.
        await _set_switch(True)
        status, resp_headers = await _call(app, "GET", f"/web/login?t={token}", [], want_headers=True)
        assert status == 303, f"سوئیچِ روشن ⇒ همان لینک باید قبول شود؛ دیده شد {status}"
        cookie = _cookie_from(resp_headers)

        # نشستِ زنده با خاموش‌کردنِ سوئیچ هم نمی‌شکند (فقط ورودِ نو بسته است).
        await _set_switch(False)
        status = await _call(
            app, "GET", "/web/panel", [(b"cookie", web_panel_service.COOKIE_NAME.encode() + b"=" + cookie)]
        )
        assert status == 200, f"نشستِ صادرشده نباید با پنهان‌کردنِ دکمه بپرد؛ دیده شد {status}"
    finally:
        settings.panel_secret = saved
        await _set_switch(True)
    print("✅ test_new_login_blocked_while_hidden_but_live_session_survives PASSED")


async def main() -> None:
    await reset_database()
    await test_column_exists_with_safe_default()
    await test_keyboard_hides_button_when_switch_off()
    await test_panel_keyboard_needs_both_switch_and_secret()
    await test_admin_toggle_flips_value_and_audits()
    await test_new_login_blocked_while_hidden_but_live_session_survives()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
