"""پ۷۰ · خواستهٔ مالکِ محصول: پر‌مصرف‌ترین‌هایِ AI و مدیریتشان در پنلِ خودِ فروشگاه‌دار.

چرا این فایل جدا از `admin_ai_usage.py` است: آن صفحه به سوپرادمین می‌دهد که *بینِ همهِٔ فروشگاه‌ها*
ببیند کدامِ کاربر زیاد مصرف می‌کند. این صفحه همان رتبه‌بندی و همان سه اهرم است، ولی فقط رویِ
مشتریانِ همون فروشگاه — و نگهبانِ مالکیت (`crm_service.get_owned_customer`) پشتِ هر فعل، چون
`customer_id` از `callback_data` می‌آید و دست‌کاری‌شدنی است.

ورودی از دو مود می‌آید و هر دو به همین صفحه می‌رسند:
* «👥 مشتری‌ها › 📈 پرمصرف‌هایِ AI» (مودِ فروشگاهی)
* «💬 گفتگوها و کاربران › 📈 پرمصرف‌هایِ AI» (مودِ مشاوره‌ای)

چه چیزی عوض می‌شود و چه چیزی نمی‌شود: سه ستونِ تنظیماتیِ رویِ ردیفِ مشتری (سقفِ ۲۴ ساعت،
توقفِ پاسخِ خودکار، بلاک) + ردیفِ ممیزی. هیچ مبلغی جابه‌جا نمی‌شود و مسیرِ پولِ کیف‌پول
دست‌نخورده است؛ ریاضِ هزینه همان `ai_usage_service` و همان دفترِ تراکنش‌هاست.

صراحتِ لازم: شمارش از نسخه‌ای شروع می‌شود که کسرِ AI شناسهٔ مشتری را می‌داند (پ۵۵) ⇒ مصرفِ
کامنتِ اینستاگرام، خلاصهٔ CRM و دستیارِ مدیریتی در این فهرست نیست و عددِ این صفحه با «جمعِ
پرداخت‌شده به پلتفرم» یکی نمی‌شود و نباید یکی باشد.
"""
from __future__ import annotations

import datetime
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.main_bot import keyboards, texts
from app.bots.main_bot.handlers.owner_common import (
    require_shop_bot,
    require_shop_bot_cb,
    safe_edit,
)
from app.bots.main_bot.states import OwnerAiUsageStates
from app.database.models import AuditEventType, Customer
from app.services import ai_usage_service, audit_log_service, crm_service
from app.services.identity_service import display_user
from app.utils.validators import parse_price_toman

logger = logging.getLogger(__name__)

router = Router(name="owner_ai_usage")

WINDOW_HOURS = {"24h": 24, "7d": 24 * 7, "30d": 24 * 30}
WINDOW_LABELS = dict(texts.AI_USAGE_WINDOWS)
NO_LIMIT_WORDS = ("بدونِ سقف", "بی‌سقف", "خالی", "همه")
CANCEL_WORDS = ("انصراف", "لغو", "/cancel")
_MAX_ID = 2_147_483_647
_MAX_PAGE = 10_000


def _window(key: str) -> str:
    return key if key in WINDOW_HOURS else "24h"


def _strict_window(key: str) -> str | None:
    return key if key in WINDOW_HOURS else None


def _decimal(raw: str, *, maximum: int) -> int | None:
    if not raw.isascii() or not raw.isdecimal():
        return None
    value = int(raw)
    return value if value <= maximum else None


def _parts(data: str, count: int) -> list[str] | None:
    pieces = (data or "").split(":")
    return pieces if len(pieces) == count else None


def _paused(customer: Customer, moment: datetime.datetime) -> bool:
    until = customer.ai_paused_until
    if until is None:
        return False
    if until.tzinfo is None:
        until = until.replace(tzinfo=datetime.timezone.utc)
    return until > moment


async def _range(window: str) -> tuple[datetime.datetime, datetime.datetime]:
    until = datetime.datetime.now(datetime.timezone.utc)
    return until - datetime.timedelta(hours=WINDOW_HOURS[_window(window)]), until


async def _list_screen(session: AsyncSession, shop_bot, window: str, page: int) -> tuple[str, object]:
    since, until = await _range(window)
    ranked, total = await ai_usage_service.rank_page(session, since=since, until=until, page=page, shop_bot_id=shop_bot.id)
    if not ranked and page > 0:
        pages = max(1, (total + ai_usage_service.RANK_PAGE_SIZE - 1) // ai_usage_service.RANK_PAGE_SIZE)
        page = max(0, pages - 1)
        ranked, total = await ai_usage_service.rank_page(session, since=since, until=until, page=page, shop_bot_id=shop_bot.id)
    if not ranked:
        return (
            f"{texts.OWNER_AI_USAGE_TITLE}\n\n{texts.OWNER_AI_USAGE_EMPTY}\n\n{texts.OWNER_AI_USAGE_NOTE}",
            keyboards.owner_ai_usage_keyboard([], _window(window), page, 1),
        )
    customers = {
        customer.id: customer
        for customer in (
            await session.execute(
                select(Customer)
                .where(Customer.shop_bot_id == shop_bot.id, Customer.id.in_([cid for cid, _s, _c in ranked]))
            )
        ).scalars().all()
    }
    items, lines = [], []
    for index, (customer_id, spent, calls) in enumerate(ranked, start=1):
        customer = customers.get(customer_id)
        if customer is None:
            continue
        name = display_user(customer, "short")
        lines.append(texts.owner_ai_usage_line(index, name, spent, calls))
        items.append((customer_id, index, name))
    if not lines:
        return (
            f"{texts.OWNER_AI_USAGE_TITLE}\n\n{texts.OWNER_AI_USAGE_EMPTY}\n\n{texts.OWNER_AI_USAGE_NOTE}",
            keyboards.owner_ai_usage_keyboard([], _window(window), page, 1),
        )
    total_pages = max(1, (total + ai_usage_service.RANK_PAGE_SIZE - 1) // ai_usage_service.RANK_PAGE_SIZE)
    body = "\n".join(
        [
            texts.owner_ai_usage_intro(WINDOW_LABELS[_window(window)], page, total_pages),
            texts.OWNER_AI_USAGE_NOTE,
            "",
            *lines,
        ]
    )
    return body, keyboards.owner_ai_usage_keyboard(items, _window(window), page, total_pages)


async def _detail_screen(session: AsyncSession, shop_bot, customer_id: int, window: str, page: int):
    customer = await crm_service.get_owned_customer(session, customer_id, shop_bot.id)
    if customer is None:
        return None
    since, until = await _range(window)
    spent, calls = await ai_usage_service.spend_and_calls(session, customer.id, since, until)
    body = texts.ai_usage_detail_text(
        customer,
        str(shop_bot.bot_username or ""),
        spent_toman=spent,
        calls=calls,
        window_label=WINDOW_LABELS[_window(window)],
        page=page,
    )
    keyboard = keyboards.owner_ai_usage_detail_keyboard(
        customer.id, _window(window), page, paused=_paused(customer, until), blocked=bool(customer.is_blocked)
    )
    return body, keyboard


@router.callback_query(F.data == "ouai_open")
async def cb_open(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    await state.clear()
    body, keyboard = await _list_screen(session, shop_bot, "24h", 0)
    await session.commit()
    await callback.answer()
    await safe_edit(callback, body, keyboard)


@router.callback_query(F.data.startswith("ouai:"))
async def cb_list(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    parts = _parts(callback.data, 3)
    window = _strict_window(parts[1]) if parts is not None else None
    if parts is None or window is None or _decimal(parts[2], maximum=_MAX_PAGE) is None:
        await callback.answer(texts.OWNER_AI_USAGE_INVALID, show_alert=True)
        return
    await state.clear()
    body, keyboard = await _list_screen(session, shop_bot, window, int(parts[2]))
    await session.commit()
    await callback.answer()
    await safe_edit(callback, body, keyboard)


@router.callback_query(F.data.startswith("ouai_view:"))
async def cb_view(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    parts = _parts(callback.data, 4)
    if parts is None or _strict_window(parts[1]) is None or _decimal(parts[2], maximum=_MAX_PAGE) is None or _decimal(
        parts[3], maximum=_MAX_ID
    ) is None:
        await callback.answer(texts.OWNER_AI_USAGE_INVALID, show_alert=True)
        return
    await state.clear()
    screen = await _detail_screen(session, shop_bot, int(parts[3]), parts[1], int(parts[2]))
    if screen is None:
        await callback.answer(texts.OWNER_AI_USAGE_INVALID, show_alert=True)
        return
    await session.commit()
    await callback.answer()
    await safe_edit(callback, screen[0], screen[1])


async def _audit(session: AsyncSession, shop_bot, details: str, actor_id: int) -> None:
    await audit_log_service.log(
        session, AuditEventType.AI_USAGE_CONTROL_CHANGED, shop_bot_id=shop_bot.id, actor_telegram_id=actor_id, details=details
    )


@router.callback_query(F.data.startswith("ouai_pause:"))
async def cb_pause(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    parts = _parts(callback.data, 5)
    if parts is None or _decimal(parts[1], maximum=_MAX_ID) is None or _strict_window(parts[3]) is None or _decimal(
        parts[4], maximum=_MAX_PAGE
    ) is None:
        await callback.answer(texts.OWNER_AI_USAGE_INVALID, show_alert=True)
        return
    hours = _decimal(parts[2], maximum=24 * 30)
    if hours is None:
        await callback.answer(texts.OWNER_AI_USAGE_INVALID, show_alert=True)
        return
    customer = await crm_service.get_owned_customer(session, int(parts[1]), shop_bot.id)
    if customer is None:
        await callback.answer(texts.OWNER_AI_USAGE_INVALID, show_alert=True)
        return
    until = await ai_usage_service.set_paused(session, customer, hours or None)
    await _audit(
        session,
        shop_bot,
        f"پاسخِ خودکارِ مشتریِ شناسهٔ داخلی {customer.id} "
        f"{'متوقف شد تا ' + until.isoformat() if until else 'آزاد شد'} (پنلِ فروشگاه‌دار)",
        callback.from_user.id,
    )
    await session.commit()
    await state.clear()
    screen = await _detail_screen(session, shop_bot, customer.id, parts[3], int(parts[4]))
    if screen is None:
        await callback.answer(texts.OWNER_AI_USAGE_INVALID)
        return
    await callback.answer(texts.ai_usage_pause_saved(hours or None))
    await safe_edit(callback, screen[0], screen[1])


@router.callback_query(F.data.startswith("ouai_limit:"))
async def cb_limit(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    parts = _parts(callback.data, 4)
    if parts is None or _decimal(parts[1], maximum=_MAX_ID) is None or _strict_window(parts[2]) is None or _decimal(
        parts[3], maximum=_MAX_PAGE
    ) is None:
        await callback.answer(texts.OWNER_AI_USAGE_INVALID, show_alert=True)
        return
    customer = await crm_service.get_owned_customer(session, int(parts[1]), shop_bot.id)
    if customer is None:
        await callback.answer(texts.OWNER_AI_USAGE_INVALID, show_alert=True)
        return
    await state.set_data(
        {
            "ouai_customer_id": customer.id,
            "ouai_shop_bot_id": shop_bot.id,
            "ouai_window": parts[2],
            "ouai_page": int(parts[3]),
        }
    )
    await state.set_state(OwnerAiUsageStates.waiting_limit)
    await callback.answer()
    await callback.message.answer(texts.AI_USAGE_LIMIT_ASK)


@router.message(OwnerAiUsageStates.waiting_limit, F.text)
async def limit_received(message: Message, state: FSMContext, session: AsyncSession) -> None:
    raw = (message.text or "").strip()
    data = await state.get_data()
    if raw in CANCEL_WORDS:
        await state.clear()
        await message.answer(texts.AI_USAGE_CANCELLED)
        return
    shop_bot = await require_shop_bot(message, session)
    customer = None
    if shop_bot is not None and int(data.get("ouai_shop_bot_id") or 0) == shop_bot.id:
        customer = await crm_service.get_owned_customer(session, data.get("ouai_customer_id"), shop_bot.id)
    if customer is None:
        await state.clear()
        await message.answer(texts.OWNER_AI_USAGE_INVALID)
        return

    amount = None if raw in NO_LIMIT_WORDS else parse_price_toman(raw)
    if amount is None and raw not in NO_LIMIT_WORDS:
        await message.answer(texts.AI_USAGE_LIMIT_INVALID)
        return

    saved = await ai_usage_service.set_daily_limit(session, customer, amount)
    await _audit(
        session,
        shop_bot,
        f"سقفِ مصرفِ ۲۴ ساعتهٔ مشتریِ شناسهٔ داخلی {customer.id}: "
        f"{saved if saved is not None else 'برداشته شد'} (پنلِ فروشگاه‌دار)",
        message.from_user.id,
    )
    await session.commit()
    await state.clear()
    screen = await _detail_screen(
        session, shop_bot, customer.id, _window(str(data.get("ouai_window") or "24h")), int(data.get("ouai_page") or 0)
    )
    confirmation = texts.ai_usage_limit_saved(saved)
    if screen is None:
        await message.answer(confirmation)
        return
    await message.answer(f"{confirmation}\n\n{screen[0]}", reply_markup=screen[1])


@router.callback_query(F.data.startswith("ouai_block:"))
async def cb_block(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    parts = _parts(callback.data, 5)
    if parts is None or _decimal(parts[1], maximum=_MAX_ID) is None or parts[2] not in {"0", "1"} or _strict_window(
        parts[3]
    ) is None or _decimal(parts[4], maximum=_MAX_PAGE) is None:
        await callback.answer(texts.OWNER_AI_USAGE_INVALID, show_alert=True)
        return
    customer = await crm_service.get_owned_customer(session, int(parts[1]), shop_bot.id)
    if customer is None:
        await callback.answer(texts.OWNER_AI_USAGE_INVALID, show_alert=True)
        return
    blocked = parts[2] == "1"
    await crm_service.set_blocked(session, customer, blocked)
    await audit_log_service.log(
        session,
        AuditEventType.CUSTOMER_BLOCK_CHANGED,
        shop_bot_id=shop_bot.id,
        actor_telegram_id=callback.from_user.id,
        details=f"customer={customer.id} blocked={blocked} (از صفحهٔ پرمصرف‌هایِ AI)",
    )
    await session.commit()
    await state.clear()
    screen = await _detail_screen(session, shop_bot, customer.id, parts[3], int(parts[4]))
    if screen is None:
        await callback.answer(texts.OWNER_AI_USAGE_INVALID)
        return
    await callback.answer(texts.CRM_BLOCK_DONE if blocked else texts.CRM_UNBLOCK_DONE)
    await safe_edit(callback, screen[0], screen[1])
