from __future__ import annotations

import asyncio
import datetime
import io
import itertools
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests_manual"))

from aiogram import Bot  # noqa: E402
from aiogram.exceptions import TelegramBadRequest  # noqa: E402
from openpyxl import load_workbook  # noqa: E402
from sqlalchemy import func, select  # noqa: E402
from sqlalchemy.dialects import postgresql  # noqa: E402

from db_env import is_test_database  # noqa: E402
from harness import FakeSession, build_test_dispatchers, fake_user, make_callback_update, reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot import keyboards, texts  # noqa: E402
from app.bots.main_bot.handlers import panel  # noqa: E402
from app.database.models import ShopBot, ShopOwner, WalletCharge, WalletTransaction, WalletTransactionReason  # noqa: E402
from app.database.session import engine, session_scope  # noqa: E402
from app.services import excel_export_service, wallet_service  # noqa: E402
from app.utils.encryption import encrypt_token  # noqa: E402
from app.utils.jalali import format_jalali_datetime  # noqa: E402
from app.utils.validators import fa_number  # noqa: E402

OWNER_TG = 953001
OTHER_TG = 953002
EMPTY_TG = 953003
SMALL_TG = 953004
MAIN_TOKEN = "530000:FAKE_MAIN_TOKEN_FOR_P53_TESTS_ONLY_0000"
SHOP_TOKEN = "530001:FAKE_SHOP_TOKEN_FOR_P53_TESTS_ONLY_0000"
STAMP = datetime.datetime(2026, 3, 20, 21, 15, tzinfo=datetime.timezone.utc)
UPDATE_IDS = itertools.count(530000)


@dataclass
class HistoryData:
    owner_id: int
    other_id: int
    empty_id: int
    small_id: int
    rows: list[WalletTransaction]
    other_rows: list[WalletTransaction]
    small_rows: list[WalletTransaction]


def _transaction(owner_id: int, index: int, base: int = 10000) -> WalletTransaction:
    reasons = list(WalletTransactionReason)
    return WalletTransaction(
        shop_owner_id=owner_id,
        amount_toman=(base + index) * (-1 if index % 3 == 0 else 1),
        reason=reasons[index % len(reasons)],
        created_at=STAMP,
        reference=f"provider-private-p53-{owner_id}-{index}",
        idempotency_key=f"access-private-p53-{owner_id}-{index}",
    )


async def _seed() -> HistoryData:
    await reset_database()
    shop_ids = [
        await seed_usable_shop(tg, tg + 100, initial_balance_toman=0)
        for tg in (OWNER_TG, OTHER_TG, EMPTY_TG, SMALL_TG)
    ]
    async with session_scope() as session:
        owners = []
        for shop_id in shop_ids:
            shop = await session.get(ShopBot, shop_id)
            shop.encrypted_token = encrypt_token(SHOP_TOKEN)
            owners.append(await session.get(ShopOwner, shop.shop_owner_id))
        owner, other, empty, small = owners
        rows = []
        other_rows = [_transaction(other.id, 0, 8000000)]
        session.add(other_rows[0])
        for index in range(37):
            transaction = _transaction(owner.id, index)
            session.add(transaction)
            rows.append(transaction)
            if index % 3 == 0:
                foreign = _transaction(other.id, len(other_rows), 8000000)
                session.add(foreign)
                other_rows.append(foreign)
        small_rows = [_transaction(small.id, index, 9000000) for index in range(3)]
        session.add_all(small_rows)
        for account, transactions in ((owner, rows), (other, other_rows), (small, small_rows)):
            account.wallet_balance_toman = sum(t.amount_toman for t in transactions)
        await session.flush()
        return HistoryData(owner.id, other.id, empty.id, small.id, rows[::-1], other_rows[::-1], small_rows[::-1])


async def _snapshot():
    async with session_scope() as session:
        balances = (await session.execute(select(ShopOwner.id, ShopOwner.wallet_balance_toman).order_by(ShopOwner.id))).all()
        ledger = (await session.execute(select(
            WalletTransaction.id, WalletTransaction.shop_owner_id, WalletTransaction.amount_toman,
            WalletTransaction.reason, WalletTransaction.reference, WalletTransaction.idempotency_key,
        ).order_by(WalletTransaction.id))).all()
        count = await session.scalar(select(func.count()).select_from(WalletTransaction))
        charges = (await session.execute(select(
            WalletCharge.id, WalletCharge.remaining_toman, WalletCharge.expires_at,
        ).order_by(WalletCharge.id))).all()
        return balances, ledger, count, charges


def _ids(rows):
    return [row.id for row in rows]


def _buttons(markup):
    return [button.callback_data for row in markup.inline_keyboard for button in row]


def _workbook(raw):
    return load_workbook(io.BytesIO(raw))


def _amounts(raw):
    return [row[3] for row in _workbook(raw).worksheets[0].iter_rows(min_row=2, values_only=True)]


def _notes(raw):
    return "\n".join(str(cell.value) for row in _workbook(raw)["توضیحات"] for cell in row if cell.value is not None)


def _expected_body(rows):
    return "\n".join([texts.WALLET_HISTORY_INTRO, "", *(texts.wallet_transaction_line(t) for t in rows)])


async def _feed(dispatcher, bot, data: str, user_id: int = OWNER_TG):
    update = make_callback_update(next(UPDATE_IDS), data=data, user_id=user_id)
    callback = update.callback_query
    message = callback.message.model_copy(update={"from_user": fake_user(OTHER_TG if user_id == OWNER_TG else OWNER_TG)})
    update = update.model_copy(update={"callback_query": callback.model_copy(update={"message": message})})
    assert update.callback_query.from_user.id != update.callback_query.message.from_user.id
    await dispatcher.feed_update(bot, update)


def test_reason_labels_and_cursor_validation() -> None:
    for reason in WalletTransactionReason:
        label = texts.wallet_reason_label(reason)
        assert label == texts.wallet_reason_label(reason.value)
        assert label != "سایر تراکنش‌ها" and not re.search(r"[A-Za-z0-9]", label)
    unknown = "private_unknown_reason"
    assert texts.wallet_reason_label(unknown) == "سایر تراکنش‌ها"
    line = texts.wallet_transaction_line(SimpleNamespace(reason=unknown, amount_toman=-1250, created_at=STAMP))
    assert unknown not in line and "-۱٬۲۵۰" in line
    assert "۱۵" not in texts.WALLET_HISTORY_INTRO
    for raw in ("", "0", "-1", "+1", " 1", "1 ", "۱", "١", "²", "1.0", "2147483648", "9" * 100):
        assert panel._wallet_history_cursor(raw) is None
    assert panel._wallet_history_cursor("1") == 1
    assert panel._wallet_history_cursor("2147483647") == 2147483647
    print("PASS test_reason_labels_and_cursor_validation")


def test_history_keyboard_navigation_and_callback_bounds() -> None:
    base = _buttons(keyboards.wallet_history_keyboard())
    assert set(base) == {"wallet_history", "wallet_history_export", "main_menu"}
    markup = keyboards.wallet_history_keyboard(newer_cursor=2147483647, older_cursor=1, next_cursor=2147483647)
    callbacks = _buttons(markup)
    assert "wallet_history_page:newer:2147483647" in callbacks
    assert "wallet_history_page:older:1" in callbacks
    assert "wallet_history_export:2147483647" in callbacks
    assert all(len(data.encode("utf-8")) <= 64 for data in callbacks)
    assert all(not re.search(r"[A-Za-z0-9]", button.text) for row in markup.inline_keyboard for button in row)
    assert not any(data.startswith("wallet_history_export:") for data in base)
    print("PASS test_history_keyboard_navigation_and_callback_bounds")


async def test_history_concurrent_insert_preserves_nearest_page(data: HistoryData) -> None:
    before = await _snapshot()
    async with session_scope() as session:
        first, _, _ = await wallet_service.get_owner_history_page(session, data.owner_id)
        second, _, _ = await wallet_service.get_owner_history_page(session, data.owner_id, cursor_id=first[-1].id)
        assert await _snapshot() == before
        async with session_scope() as writer:
            inserted = _transaction(data.owner_id, 99)
            writer.add(inserted)
            owner = await writer.get(ShopOwner, data.owner_id)
            owner.wallet_balance_toman += inserted.amount_toman
            await writer.flush()
        after_insert = await _snapshot()
        back, has_newer, has_older = await wallet_service.get_owner_history_page(
            session, data.owner_id, direction="newer", cursor_id=second[0].id,
        )
        assert _ids(back) == _ids(first) and has_newer and has_older
        newest, has_newer, has_older = await wallet_service.get_owner_history_page(
            session, data.owner_id, direction="newer", cursor_id=first[0].id,
        )
        assert _ids(newest) == [inserted.id] and not has_newer and has_older
        fresh, _, _ = await wallet_service.get_owner_history_page(session, data.owner_id)
        assert _ids(fresh) == [inserted.id, *_ids(first[:14])]
    assert await _snapshot() == after_insert
    data.rows.insert(0, inserted)
    print("PASS test_history_concurrent_insert_preserves_nearest_page")


async def test_history_pages_round_trip(data: HistoryData) -> None:
    async with session_scope() as session:
        first, newer, older = await wallet_service.get_owner_history_page(session, data.owner_id)
        assert len(first) == 15 and not newer and older
        second, newer, older = await wallet_service.get_owner_history_page(session, data.owner_id, cursor_id=first[-1].id)
        assert len(second) == 15 and newer and older
        third, newer, older = await wallet_service.get_owner_history_page(session, data.owner_id, cursor_id=second[-1].id)
        assert len(third) == len(data.rows) - 30 and newer and not older
        assert _ids(first + second + third) == _ids(data.rows)
        back, _, _ = await wallet_service.get_owner_history_page(session, data.owner_id, direction="newer", cursor_id=third[0].id)
        assert _ids(back) == _ids(second)
        back, newer, older = await wallet_service.get_owner_history_page(session, data.owner_id, direction="newer", cursor_id=back[0].id)
        assert _ids(back) == _ids(first) and not newer and older
        recent = await wallet_service.get_recent_transactions(session, data.owner_id, limit=19)
        assert _ids(recent) == _ids(data.rows[:19])
    print("PASS test_history_pages_round_trip")


async def test_history_empty_small_and_foreign_cursors(data: HistoryData) -> None:
    async with session_scope() as session:
        assert await wallet_service.get_owner_history_page(session, data.empty_id) == ([], False, False)
        rows, newer, older = await wallet_service.get_owner_history_page(session, data.small_id)
        assert _ids(rows) == _ids(data.small_rows) and not newer and not older
        for cursor in (1, 2147483647, data.other_rows[0].id, data.other_rows[len(data.other_rows) // 2].id):
            for direction in ("older", "newer"):
                rows, newer, older = await wallet_service.get_owner_history_page(
                    session, data.owner_id, direction=direction, cursor_id=cursor,
                )
                candidates = [t for t in data.rows if (t.id < cursor if direction == "older" else t.id > cursor)]
                expected = candidates[:15] if direction == "older" else candidates[-15:]
                assert _ids(rows) == _ids(expected)
                assert all(row.shop_owner_id == data.owner_id for row in rows)
                assert newer == bool(rows and any(t.id > rows[0].id for t in data.rows))
                assert older == bool(rows and any(t.id < rows[-1].id for t in data.rows))
                assert await wallet_service.get_owner_history_page(
                    session, data.empty_id, direction=direction, cursor_id=cursor,
                ) == ([], False, False)
        foreign_rows, newer, older = await wallet_service.get_owner_history_page(session, data.other_id)
        assert _ids(foreign_rows) == _ids(data.other_rows) and not newer and not older
    print("PASS test_history_empty_small_and_foreign_cursors")


async def test_history_queries_are_bounded_and_owner_scoped(data: HistoryData) -> None:
    async with session_scope() as session:
        with patch.object(session, "execute", wraps=session.execute) as execute:
            await wallet_service.get_owner_history_page(session, data.owner_id, direction="newer", cursor_id=data.rows[-1].id)
        assert execute.await_count == 2
        page_query, flag_query = [call.args[0] for call in execute.await_args_list]
        assert page_query._limit_clause.value == 15 and page_query._offset_clause is None
        page_sql = str(page_query.compile(dialect=postgresql.dialect()))
        flag_sql = str(flag_query.compile(dialect=postgresql.dialect()))
        assert "wallet_transactions.id ASC" in page_sql and "wallet_transactions.shop_owner_id =" in page_sql
        assert flag_sql.count("EXISTS") == 2 and flag_sql.count("wallet_transactions.shop_owner_id =") == 2
        assert all(value == data.owner_id for key, value in flag_query.compile().params.items() if key.startswith("shop_owner_id"))
        with patch.object(session, "execute", new_callable=AsyncMock) as execute:
            for kwargs in ({"direction": "invalid"}, {"cursor_id": 0}, {"cursor_id": 2147483648}):
                try:
                    await wallet_service.get_owner_history_page(session, data.owner_id, **kwargs)
                except ValueError:
                    pass
                else:
                    raise AssertionError("invalid history arguments accepted")
            execute.assert_not_awaited()
    print("PASS test_history_queries_are_bounded_and_owner_scoped")


async def test_owner_workbook_is_localized_signed_and_private(data: HistoryData) -> None:
    async with session_scope() as session:
        raw, count, next_cursor = await excel_export_service.build_owner_wallet_workbook(session, data.owner_id)
    assert count == len(data.rows) and next_cursor is None
    wb = _workbook(raw)
    ws = wb.worksheets[0]
    assert ws.max_column == 4 and ws.max_row == count + 1
    assert [cell.value for cell in ws[1]][:3] == ["ردیف", "تاریخ (تهران)", "دلیل"]
    assert "تومان" in ws.cell(1, 4).value
    assert all(sheet.sheet_view.rightToLeft for sheet in wb.worksheets)
    assert ws.freeze_panes == "A2" and ws.auto_filter.ref == f"A1:D{count + 1}"
    assert str(ws["A1"].fill.start_color.rgb).endswith("0F5E5C")
    for index, transaction in enumerate(data.rows, start=1):
        cells = list(ws[index + 1])
        assert cells[0].value == fa_number(index)
        assert cells[1].value == format_jalali_datetime(STAMP) == "۱ فروردین ۱۴۰۵، ساعت ۰۰:۴۵"
        assert cells[2].value == texts.wallet_reason_label(transaction.reason)
        assert cells[3].value == transaction.amount_toman and cells[3].data_type == "n"
        assert cells[3].number_format == "+#,##0;[Red]-#,##0;0"
    for sheet in wb.worksheets:
        for row in sheet:
            for cell in row:
                assert cell.data_type != "f"
                if isinstance(cell.value, str):
                    assert not re.search(r"[A-Za-z0-9]", cell.value)
                    assert "شناسه" not in cell.value and "ارجاع" not in cell.value
    assert any(t.amount_toman > 0 for t in data.rows) and any(t.amount_toman < 0 for t in data.rows)
    assert _amounts(raw) == [t.amount_toman for t in data.rows]
    assert "همهٔ تراکنش‌های موجود هنگام تهیه" in _notes(raw)
    print("PASS test_owner_workbook_is_localized_signed_and_private")


async def test_export_chunks_cover_owner_exactly_once(data: HistoryData) -> None:
    before_id = None
    collected = []
    async with session_scope() as session:
        for offset in range(0, len(data.rows), 7):
            raw, count, next_cursor = await excel_export_service.build_owner_wallet_workbook(
                session, data.owner_id, before_id=before_id, limit=7,
            )
            expected = data.rows[offset:offset + 7]
            assert count == len(expected)
            collected.extend(_amounts(raw))
            assert _amounts(raw) == [t.amount_toman for t in expected]
            assert fa_number(count) in _notes(raw)
            if offset + count < len(data.rows):
                assert next_cursor == expected[-1].id
                assert "همهٔ تاریخچه نیست" in _notes(raw) and "دریافت ادامهٔ فایل" in _notes(raw)
            else:
                assert next_cursor is None and "پایانِ تاریخچه" in _notes(raw)
            if before_id is not None:
                assert "ردیف‌های فایل‌های قبلی در این فایل نیستند" in _notes(raw)
                assert "همهٔ تراکنش‌های موجود هنگام تهیه" not in _notes(raw)
            before_id = next_cursor
    assert collected == [t.amount_toman for t in data.rows] and len(set(collected)) == len(data.rows)
    print("PASS test_export_chunks_cover_owner_exactly_once")


async def test_export_empty_small_and_foreign_cursors(data: HistoryData) -> None:
    async with session_scope() as session:
        raw, count, cursor = await excel_export_service.build_owner_wallet_workbook(session, data.empty_id)
        assert count == 0 and cursor is None and _workbook(raw).worksheets[0].max_row == 1
        assert "تراکنشی وجود ندارد" in _notes(raw)
        raw, count, cursor = await excel_export_service.build_owner_wallet_workbook(session, data.small_id, limit=3)
        assert count == 3 and cursor is None and _amounts(raw) == [t.amount_toman for t in data.small_rows]
        for before_id in (data.other_rows[0].id, data.other_rows[-1].id, 2147483647, 1):
            raw, count, cursor = await excel_export_service.build_owner_wallet_workbook(session, data.owner_id, before_id=before_id)
            expected = [t.amount_toman for t in data.rows if t.id < before_id]
            assert count == len(expected) and cursor is None and _amounts(raw) == expected
        raw, count, cursor = await excel_export_service.build_owner_wallet_workbook(session, data.other_id)
        assert count == len(data.other_rows) and cursor is None and _amounts(raw) == [t.amount_toman for t in data.other_rows]
    print("PASS test_export_empty_small_and_foreign_cursors")


async def test_export_query_cap_and_formula_neutralization(data: HistoryData) -> None:
    async with session_scope() as session:
        with patch.object(session, "execute", wraps=session.execute) as execute:
            await excel_export_service.build_owner_wallet_workbook(session, data.owner_id, limit=99999)
        execute.assert_awaited_once()
        query = execute.await_args.args[0]
        assert query._limit_clause.value == 5001 and query._offset_clause is None
        assert list(query.selected_columns.keys()) == ["id", "created_at", "reason", "amount_toman"]
        sql = str(query.compile(dialect=postgresql.dialect()))
        assert "wallet_transactions.shop_owner_id =" in sql and "wallet_transactions.id DESC" in sql
        with patch.object(texts, "wallet_reason_label", return_value="=1+1"):
            raw, count, cursor = await excel_export_service.build_owner_wallet_workbook(session, data.owner_id, limit=1)
        assert count == 1 and cursor == data.rows[0].id
        cell = _workbook(raw).worksheets[0]["C2"]
        assert cell.value == "=1+1" and cell.data_type == "s"
        with patch.object(session, "execute", new_callable=AsyncMock) as execute:
            for kwargs in ({"limit": 0}, {"limit": -1}, {"before_id": 0}, {"before_id": 2147483648}):
                try:
                    await excel_export_service.build_owner_wallet_workbook(session, data.owner_id, **kwargs)
                except ValueError:
                    pass
                else:
                    raise AssertionError("invalid export arguments accepted")
            execute.assert_not_awaited()
    print("PASS test_export_query_cap_and_formula_neutralization")


async def test_dispatcher_history_uses_callback_sender(dispatcher, data: HistoryData) -> None:
    fake = FakeSession()
    async with Bot(token=MAIN_TOKEN, session=fake).context() as bot:
        await _feed(dispatcher, bot, "wallet_history")
        first = fake.sent_messages[-1]
        assert first["text"] == _expected_body(data.rows[:15]) and first["chat_id"] == OWNER_TG
        older = next(c for c in _buttons(first["reply_markup"]) if c.startswith("wallet_history_page:older:"))
        await _feed(dispatcher, bot, older)
        second = fake.edited_texts[-1]
        assert second["text"] == _expected_body(data.rows[15:30])
        older = next(c for c in _buttons(second["reply_markup"]) if c.startswith("wallet_history_page:older:"))
        await _feed(dispatcher, bot, older)
        third = fake.edited_texts[-1]
        assert third["text"] == _expected_body(data.rows[30:])
        newer = next(c for c in _buttons(third["reply_markup"]) if c.startswith("wallet_history_page:newer:"))
        await _feed(dispatcher, bot, newer)
        assert fake.edited_texts[-1]["text"] == second["text"]
        newer = next(c for c in _buttons(second["reply_markup"]) if c.startswith("wallet_history_page:newer:"))
        await _feed(dispatcher, bot, newer)
        assert fake.edited_texts[-1]["text"] == first["text"]
        assert len(fake.answered_callbacks) == 5
    print("PASS test_dispatcher_history_uses_callback_sender")


async def test_dispatcher_repeated_page_is_safe(dispatcher, data: HistoryData) -> None:
    fake = FakeSession()
    real_request = fake.make_request
    edits = 0

    async def request(bot, method, timeout=None):
        nonlocal edits
        if type(method).__name__ == "EditMessageText":
            edits += 1
            if edits > 1:
                raise TelegramBadRequest(method=method, message="Bad Request: message is not modified")
        return await real_request(bot, method, timeout)

    async with Bot(token=MAIN_TOKEN, session=fake).context() as bot:
        with patch.object(fake, "make_request", side_effect=request):
            callback = f"wallet_history_page:older:{data.rows[14].id}"
            await _feed(dispatcher, bot, callback)
            await _feed(dispatcher, bot, callback)
    assert edits == 2 and len(fake.answered_callbacks) == 2
    assert fake.edited_texts[-1]["text"] == _expected_body(data.rows[15:30])
    print("PASS test_dispatcher_repeated_page_is_safe")


async def test_dispatcher_export_continuation_commits_reads(dispatcher, data: HistoryData) -> None:
    fake = FakeSession()
    real_build = excel_export_service.build_owner_wallet_workbook
    read_sessions = []
    sent_keyboards = []
    real_request = fake.make_request

    async def bounded_build(session, owner_id, *, before_id=None):
        assert owner_id == data.owner_id
        read_sessions.append(session)
        return await real_build(session, owner_id, before_id=before_id, limit=7)

    async def request(bot, method, timeout=None):
        if type(method).__name__ == "SendDocument":
            assert not read_sessions[-1].in_transaction(), "read session must commit before document upload"
            sent_keyboards.append(method.reply_markup)
        return await real_request(bot, method, timeout)

    collected = []
    async with Bot(token=MAIN_TOKEN, session=fake).context() as bot:
        with patch.object(excel_export_service, "build_owner_wallet_workbook", side_effect=bounded_build), patch.object(fake, "make_request", side_effect=request):
            callback = "wallet_history_export"
            for offset in range(0, len(data.rows), 7):
                await _feed(dispatcher, bot, callback)
                document = fake.sent_documents[-1]
                assert document["chat_id"] == OWNER_TG
                raw = document["document"].data
                collected.extend(_amounts(raw))
                expected = data.rows[offset:offset + 7]
                assert _amounts(raw) == [t.amount_toman for t in expected]
                continuation = [c for c in _buttons(sent_keyboards[-1]) if c.startswith("wallet_history_export:")]
                if offset + len(expected) < len(data.rows):
                    assert continuation == [f"wallet_history_export:{expected[-1].id}"]
                    assert "همهٔ تاریخچه نیست" in document["caption"]
                    callback = continuation[0]
                else:
                    assert not continuation and "پایانِ تاریخچه" in document["caption"]
    assert collected == [t.amount_toman for t in data.rows]
    assert len(fake.sent_documents) == (len(data.rows) + 6) // 7
    print("PASS test_dispatcher_export_continuation_commits_reads")


async def test_dispatcher_invalid_callbacks_never_query_history(dispatcher) -> None:
    malformed = [
        "wallet_history_page", "wallet_history_page:older", "wallet_history_page:bad:1",
        "wallet_history_page:older:1:2", "wallet_history_export:1:2", "wallet_history_export:",
    ]
    for raw in ("0", "-1", "+1", " 1", "1 ", "۱", "١", "1.0", "2147483648", "99999999999"):
        malformed.extend((f"wallet_history_page:older:{raw}", f"wallet_history_page:newer:{raw}", f"wallet_history_export:{raw}"))
    fake = FakeSession()
    async with Bot(token=MAIN_TOKEN, session=fake).context() as bot:
        with patch.object(panel, "_current_owner", new_callable=AsyncMock) as owner_lookup, patch.object(wallet_service, "get_owner_history_page", new_callable=AsyncMock) as history, patch.object(excel_export_service, "build_owner_wallet_workbook", new_callable=AsyncMock) as export:
            for callback in malformed:
                before = len(fake.answered_callbacks)
                await _feed(dispatcher, bot, callback)
                assert len(fake.answered_callbacks) == before + 1
                assert fake.answered_callbacks[-1]["text"] == texts.WALLET_HISTORY_INVALID
                assert fake.answered_callbacks[-1]["show_alert"] is True
            owner_lookup.assert_not_awaited()
            history.assert_not_awaited()
            export.assert_not_awaited()
    assert not fake.sent_documents and not fake.sent_messages and not fake.edited_texts
    print("PASS test_dispatcher_invalid_callbacks_never_query_history")


async def test_dispatcher_empty_missing_owner_and_foreign_cursors(dispatcher, data: HistoryData) -> None:
    fake = FakeSession()
    async with Bot(token=MAIN_TOKEN, session=fake).context() as bot:
        for callback in ("wallet_history", "wallet_history_export"):
            await _feed(dispatcher, bot, callback, EMPTY_TG)
            assert fake.sent_messages[-1]["text"] == texts.WALLET_HISTORY_EMPTY
            assert "main_menu" in _buttons(fake.sent_messages[-1]["reply_markup"])
            await _feed(dispatcher, bot, callback, 953999)
            assert fake.answered_callbacks[-1]["text"] == texts.WALLET_HISTORY_UNAVAILABLE
        assert not fake.sent_documents
        await _feed(dispatcher, bot, "wallet_history_page:newer:2147483647")
        assert fake.edited_texts[-1]["text"] == texts.WALLET_HISTORY_PAGE_EMPTY
        await _feed(dispatcher, bot, "wallet_history_export:1")
        assert fake.sent_messages[-1]["text"] == texts.WALLET_HISTORY_PAGE_EMPTY and not fake.sent_documents
        foreign_cursor = data.other_rows[len(data.other_rows) // 2].id
        expected = [t for t in data.rows if t.id < foreign_cursor]
        await _feed(dispatcher, bot, f"wallet_history_page:older:{foreign_cursor}")
        assert fake.edited_texts[-1]["text"] == _expected_body(expected[:15])
        await _feed(dispatcher, bot, f"wallet_history_export:{foreign_cursor}")
        assert _amounts(fake.sent_documents[-1]["document"].data) == [t.amount_toman for t in expected]
        await _feed(dispatcher, bot, "wallet_history_export", OTHER_TG)
        assert fake.sent_documents[-1]["chat_id"] == OTHER_TG
        assert _amounts(fake.sent_documents[-1]["document"].data) == [t.amount_toman for t in data.other_rows]
    print("PASS test_dispatcher_empty_missing_owner_and_foreign_cursors")


async def test_reads_preserve_balances_and_transaction_count(before) -> None:
    assert await _snapshot() == before
    print("PASS test_reads_preserve_balances_and_transaction_count")


async def main() -> None:
    if not is_test_database(str(engine.url)):
        raise SystemExit("این تست فقط با اجراکنندهٔ تست و دیتابیسِ جدا اجرا می‌شود.")
    dispatcher, _shop_dispatcher, _manager, main_bot = build_test_dispatchers()
    try:
        test_reason_labels_and_cursor_validation()
        test_history_keyboard_navigation_and_callback_bounds()
        data = await _seed()
        await test_history_concurrent_insert_preserves_nearest_page(data)
        before = await _snapshot()
        await test_history_pages_round_trip(data)
        await test_history_empty_small_and_foreign_cursors(data)
        await test_history_queries_are_bounded_and_owner_scoped(data)
        await test_owner_workbook_is_localized_signed_and_private(data)
        await test_export_chunks_cover_owner_exactly_once(data)
        await test_export_empty_small_and_foreign_cursors(data)
        await test_export_query_cap_and_formula_neutralization(data)
        await test_dispatcher_history_uses_callback_sender(dispatcher, data)
        await test_dispatcher_repeated_page_is_safe(dispatcher, data)
        await test_dispatcher_export_continuation_commits_reads(dispatcher, data)
        await test_dispatcher_invalid_callbacks_never_query_history(dispatcher)
        await test_dispatcher_empty_missing_owner_and_foreign_cursors(dispatcher, data)
        await test_reads_preserve_balances_and_transaction_count(before)
    finally:
        await main_bot.session.close()
        await dispatcher.storage.close()
        await _shop_dispatcher.storage.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
