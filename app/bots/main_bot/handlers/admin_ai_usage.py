"""پ۵۵ · موردِ ۲۳: رتبه‌بندیِ مصرفِ هوشِ مصنوعیِ هر کاربر + سه اهرمِ مدیریتی.

چرا این صفحه: تا پیشِ این ادمین فقط می‌توانست بگوید «این فروشگاه چقدر خرج کرد»؛ نمی‌توانست
بگوید کدامِ مشتریِ آن فروشگاه پشتِ آن خرج است، و هیچ اهرمی جز بلاکِ خودِ فروشگاه‌دار نداشت.
این صفحه از همینِ نسخه مصرف را به‌ازایِ کاربر می‌شمارد (پاسِ واقعیِ «چه کسی زیاد مصرف می‌کند»)
و سه کارِ ساده از همان‌جا ممکن می‌کند: سقفِ مصرف در ۲۴ ساعت، توقفِ موقتِ پاسخِ خودکار، و
بلاک/رفعِ بلاکِ همان کاربر.

صراحتِ لازم:
- ردیف‌هایِ قدیمیِ دفترِ کیف‌پول مشتریِ خود را نمی‌دانستند ⇒ رتبه‌بندی از همینِ نسخه شروع
  می‌شود و گذشته را حدس نمی‌زند (همین نکته رویِ صفحه هم نوشته می‌شود).
- کامنتِ اینستاگرام، خلاصهٔ CRM و دستیارِ مدیریتی بی‌مشتریِ شناخته‌شده هزینه می‌کنند ⇒ در
  این فهرست نیستند؛ عددِ این صفحه با «آمار سراسری» یکی نمی‌شود و یکی هم نباید باشد.
- این صفحه هیچ مبلغی جابه‌جا نمی‌کند: فقط سه ستونِ تنظیماتیِ رویِ ردیفِ کاربر را عوض می‌کند
  و هر سه در دفترِ ممیزی نوشته می‌شوند. مسیرِ پولیِ کیف‌پول دست‌نخورده است.

دسترسی: فقط سوپرادمین (اهرم‌هایِ تنبیهیِ به‌ازایِ هر کاربر، مثلِ مدیریتِ ادمین‌ها).
"""

from __future__ import annotations

import datetime
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.main_bot import keyboards, texts
from app.bots.main_bot.filters import IsSuperAdmin
from app.bots.main_bot.handlers.owner_common import safe_edit
from app.bots.main_bot.states import AiUsageStates
from app.database.models import AuditEventType, Customer, ShopBot
from app.services import ai_usage_service, audit_log_service, crm_service
from app.services.identity_service import display_user
from app.utils.validators import parse_price_toman

logger = logging.getLogger(__name__)

router = Router(name="admin_ai_usage")
router.message.filter(IsSuperAdmin())
router.callback_query.filter(IsSuperAdmin())

WINDOW_HOURS = {"24h": 24, "7d": 24 * 7, "30d": 24 * 30}
WINDOW_LABELS = dict(texts.AI_USAGE_WINDOWS)
NO_LIMIT_WORDS = ("بدونِ سقف", "بی‌سقف", "خالی", "همه")
CANCEL_WORDS = ("انصراف", "لغو", "/cancel")
_MAX_ID = 2_147_483_647
_MAX_PAGE = 10_000


def _window(key: str) -> str:
    return key if key in WINDOW_HOURS else "24h"


def _strict_window(key: str) -> str | None:
    """پنجره از دادهٔ دکمه می‌آید ⇒ پنجرهٔ ناشناخته «۲۴ ساعت» تفسیر نمی‌شود، رد می‌شود."""
    return key if key in WINDOW_HOURS else None


def _range(key: str) -> tuple[datetime.datetime, datetime.datetime]:
    until = datetime.datetime.now(datetime.timezone.utc)
    return until - datetime.timedelta(hours=WINDOW_HOURS[_window(key)]), until


def _decimal(raw: str, *, maximum: int) -> int | None:
    if not raw.isascii() or not raw.isdecimal():
        return None
    value = int(raw)
    return value if value <= maximum else None


def _paused(customer: Customer, moment: datetime.datetime) -> bool:
    until = customer.ai_paused_until
    if until is None:
        return False
    if until.tzinfo is None:
        until = until.replace(tzinfo=datetime.timezone.utc)
    return until > moment


def _parts(data: str, count: int) -> list[str] | None:
    parts = (data or "").split(":")
    return parts if len(parts) == count else None


async def _filter_of(state: FSMContext) -> int | None:
    """پ۷۰: فیلترِ «فقطِ این فروشگاه» رویِ چتِ ادمین می‌ماند و هر ناوبری آن را نگه می‌دارد."""
    value = (await state.get_data()).get("ai_usage_shop")
    return int(value) if value else None


async def _clear_state_keep_filter(state: FSMContext, shop_bot_id: int | None) -> None:
    # پ۶۴ · قاعدهٔ پنل‌ها: هر ناوبری حالتِ «در انتظارِ ورودی» را پاک می‌کند؛ فیلترِ فروشگاه ورودی نیست.
    await state.clear()
    if shop_bot_id:
        await state.update_data(ai_usage_shop=shop_bot_id)


async def _list_screen(
    session: AsyncSession, window: str, page: int, shop_bot_id: int | None = None
) -> tuple[str, object]:
    since, until = _range(window)
    ranked, total = await ai_usage_service.rank_page(
        session, since=since, until=until, page=page, shop_bot_id=shop_bot_id
    )
    if not ranked and page > 0:
        page = max(0, (total + ai_usage_service.RANK_PAGE_SIZE - 1) // ai_usage_service.RANK_PAGE_SIZE - 1)
        ranked, total = await ai_usage_service.rank_page(
            session, since=since, until=until, page=page, shop_bot_id=shop_bot_id
        )
    filter_line = await _shop_line(session, shop_bot_id)
    if not ranked:
        return (
            "\n\n".join(part for part in (texts.AI_USAGE_EMPTY, texts.AI_USAGE_HISTORY_NOTE, filter_line) if part),
            _windows_keyboard(window, shop_bot_id),
        )

    customers = {
        customer.id: customer
        for customer in (
            await session.execute(select(Customer).where(Customer.id.in_([customer_id for customer_id, _spent, _calls in ranked])))
        ).scalars().all()
    }
    usernames: dict[int, str] = {}
    shop_ids = sorted({customer.shop_bot_id for customer in customers.values()})
    if shop_ids:
        for shop_id, username in (
            await session.execute(select(ShopBot.id, ShopBot.bot_username).where(ShopBot.id.in_(shop_ids)))
        ).all():
            usernames[int(shop_id)] = str(username or "")

    items = []
    lines = []
    for index, (customer_id, spent, calls) in enumerate(ranked, start=1):
        customer = customers.get(customer_id)
        if customer is None:
            # ردیفِ مصرف مانده ولی کاربر پاک شده ⇒ خط را نشان نمی‌دهیم، ولی شمارِ کل را دست نمی‌زنیم.
            continue
        name = display_user(customer, "short")
        shop = usernames.get(customer.shop_bot_id, "")
        lines.append(texts.ai_usage_line(index, name, shop, spent, calls))
        items.append((customer_id, index, name))
    if not lines:
        return (
            "\n\n".join(part for part in (texts.AI_USAGE_EMPTY, texts.AI_USAGE_HISTORY_NOTE, filter_line) if part),
            _windows_keyboard(window, shop_bot_id),
        )

    total_pages = max(1, (total + ai_usage_service.RANK_PAGE_SIZE - 1) // ai_usage_service.RANK_PAGE_SIZE)
    body = "\n".join(
        [
            texts.ai_usage_intro(total, WINDOW_LABELS[_window(window)], page, total_pages),
            texts.AI_USAGE_HISTORY_NOTE,
            *([filter_line] if filter_line else []),
            "",
            *lines,
        ]
    )
    return body, keyboards.ai_usage_keyboard(items, _window(window), page, total_pages, shop_bot_id)


async def _shop_line(session: AsyncSession, shop_bot_id: int | None) -> str:
    if not shop_bot_id:
        return ""
    shop_bot = await session.get(ShopBot, shop_bot_id)
    if shop_bot is None:
        return ""
    return texts.AI_USAGE_SHOP_FILTER_LINE.format(shop=str(shop_bot.bot_username or shop_bot_id))


def _windows_keyboard(window: str, shop_bot_id: int | None):
    """نمایِ خالی: اگر فیلتری هست، دکمهٔ «همهٔ فروشگاه‌ها» هم باید باشد تا ادمین گیر نکند."""
    base = keyboards.ai_usage_windows_keyboard(window)
    if shop_bot_id:
        base.inline_keyboard.insert(
            1,
            [InlineKeyboardButton(text=texts.AI_USAGE_SHOP_ALL_BUTTON, callback_data="ai_usage_shop:0")],
        )
    return base


async def _detail_screen(session: AsyncSession, customer_id: int, window: str, page: int) -> tuple[str, object] | None:
    customer = await session.get(Customer, customer_id)
    if customer is None:
        return None
    since, until = _range(window)
    spent, calls = await ai_usage_service.spend_and_calls(session, customer_id, since, until)
    shop_bot = await session.get(ShopBot, customer.shop_bot_id)
    body = texts.ai_usage_detail_text(
        customer,
        str(shop_bot.bot_username or "") if shop_bot is not None else "",
        spent_toman=spent,
        calls=calls,
        window_label=WINDOW_LABELS[_window(window)],
        page=page,
    )
    keyboard = keyboards.ai_usage_detail_keyboard(
        customer_id,
        _window(window),
        page,
        paused=_paused(customer, until),
        blocked=bool(customer.is_blocked),
        shop_bot_id=customer.shop_bot_id,
    )
    return body, keyboard


async def _audit(session: AsyncSession, actor_id: int, details: str) -> None:
    await audit_log_service.log(session, AuditEventType.ADMIN_SETTING_CHANGED, actor_telegram_id=actor_id, details=details)


@router.message(F.text == texts.AI_USAGE_BUTTON)
async def open_ai_usage(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    body, keyboard = await _list_screen(session, "24h", 0)
    await session.commit()
    await message.answer(body, reply_markup=keyboard)


@router.callback_query(F.data.startswith("ai_usage:"))
async def cb_ai_usage(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    parts = _parts(callback.data, 3)
    window = _strict_window(parts[1]) if parts is not None else None
    if parts is None or window is None or _decimal(parts[2], maximum=_MAX_PAGE) is None:
        await callback.answer(texts.AI_USAGE_INVALID, show_alert=True)
        return
    # پ۶۴ · قاعدهٔ پنل‌ها: هرِ ناوبریِ داخلِ صفحه حالتِ «در انتظارِ ورودی» را پاک می‌کند، وگرنه
    # اگر ادمین وسطِ پرسشِ سقف این دکمه‌ها را بزند، متنِ بعدی‌اش ورودیِ قدیمی ذخیره می‌شود.
    shop_bot_id = await _filter_of(state)
    await _clear_state_keep_filter(state, shop_bot_id)
    page = int(parts[2])
    body, keyboard = await _list_screen(session, window, page, shop_bot_id)
    await session.commit()
    await callback.answer()
    await safe_edit(callback, body, keyboard)


@router.callback_query(F.data.startswith("ai_usage_shop:"))
async def cb_ai_usage_shop(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """پ۷۰: «فقطِ مشتریانِ این فروشگاه» (و `ai_usage_shop:0` ⇒ برداشتنِ فیلتر)."""
    raw = (callback.data or "").split(":", 1)[1]
    shop_bot_id = _decimal(raw, maximum=_MAX_ID)
    if shop_bot_id is None:
        await callback.answer(texts.AI_USAGE_INVALID, show_alert=True)
        return
    if shop_bot_id and await session.get(ShopBot, shop_bot_id) is None:
        await callback.answer(texts.AI_USAGE_SHOP_INVALID, show_alert=True)
        return
    await _clear_state_keep_filter(state, shop_bot_id or None)
    body, keyboard = await _list_screen(session, "24h", 0, shop_bot_id or None)
    await session.commit()
    await callback.answer()
    await safe_edit(callback, body, keyboard)


@router.callback_query(F.data.startswith("ai_usage_view:"))
async def cb_ai_usage_view(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    parts = _parts(callback.data, 4)
    if parts is None or _decimal(parts[3], maximum=_MAX_ID) is None or _decimal(parts[2], maximum=_MAX_PAGE) is None:
        await callback.answer(texts.AI_USAGE_INVALID, show_alert=True)
        return
    if _strict_window(parts[1]) is None:
        await callback.answer(texts.AI_USAGE_INVALID, show_alert=True)
        return
    screen = await _detail_screen(session, int(parts[3]), parts[1], int(parts[2]))
    if screen is None:
        await callback.answer(texts.AI_USAGE_INVALID, show_alert=True)
        return
    await state.clear()
    body, keyboard = screen
    await session.commit()
    await callback.answer()
    await safe_edit(callback, body, keyboard)


@router.callback_query(F.data.startswith("ai_usage_pause:"))
async def cb_ai_usage_pause(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    parts = _parts(callback.data, 5)
    if parts is None or _decimal(parts[1], maximum=_MAX_ID) is None or _decimal(parts[4], maximum=_MAX_PAGE) is None:
        await callback.answer(texts.AI_USAGE_INVALID, show_alert=True)
        return
    if _strict_window(parts[3]) is None:
        await callback.answer(texts.AI_USAGE_INVALID, show_alert=True)
        return
    hours = _decimal(parts[2], maximum=24 * 30)
    if hours is None:
        await callback.answer(texts.AI_USAGE_INVALID, show_alert=True)
        return
    customer = await session.get(Customer, int(parts[1]))
    if customer is None:
        await callback.answer(texts.AI_USAGE_INVALID, show_alert=True)
        return

    until = await ai_usage_service.set_paused(session, customer, hours or None)
    await _audit(
        session,
        callback.from_user.id,
        f"توقفِ پاسخِ خودکارِ کاربرِ شناسهٔ داخلی {customer.id} در فروشگاهِ {customer.shop_bot_id} "
        f"تا {until.isoformat() if until else 'همین حالا (آزاد)'}",
    )
    await session.commit()
    await state.clear()
    screen = await _detail_screen(session, customer.id, parts[3], int(parts[4]))
    if screen is None:
        await callback.answer(texts.AI_USAGE_INVALID)
        return
    await callback.answer(texts.ai_usage_pause_saved(hours or None))
    await safe_edit(callback, screen[0], screen[1])


@router.callback_query(F.data.startswith("ai_usage_limit:"))
async def cb_ai_usage_limit(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    parts = _parts(callback.data, 4)
    if parts is None or _decimal(parts[1], maximum=_MAX_ID) is None or _decimal(parts[3], maximum=_MAX_PAGE) is None:
        await callback.answer(texts.AI_USAGE_INVALID, show_alert=True)
        return
    customer = await session.get(Customer, int(parts[1]))
    if customer is None:
        await callback.answer(texts.AI_USAGE_INVALID, show_alert=True)
        return
    if _strict_window(parts[2]) is None:
        await callback.answer(texts.AI_USAGE_INVALID, show_alert=True)
        return
    await state.set_data(
        {"ai_usage_customer_id": customer.id, "ai_usage_window": parts[2], "ai_usage_page": int(parts[3])}
    )
    await state.set_state(AiUsageStates.waiting_limit)
    await callback.answer()
    await callback.message.answer(texts.AI_USAGE_LIMIT_ASK)


@router.message(AiUsageStates.waiting_limit, F.text)
async def ai_usage_limit_received(message: Message, state: FSMContext, session: AsyncSession) -> None:
    raw = (message.text or "").strip()
    data = await state.get_data()
    if raw in CANCEL_WORDS:
        await state.clear()
        await message.answer(texts.AI_USAGE_CANCELLED)
        return
    customer = await session.get(Customer, int(data.get("ai_usage_customer_id") or 0))
    if customer is None:
        await state.clear()
        await message.answer(texts.AI_USAGE_INVALID)
        return

    amount = None if raw in NO_LIMIT_WORDS else parse_price_toman(raw)
    if amount is None and raw not in NO_LIMIT_WORDS:
        await message.answer(texts.AI_USAGE_LIMIT_INVALID)
        return

    saved = await ai_usage_service.set_daily_limit(session, customer, amount)
    await _audit(
        session,
        message.from_user.id,
        f"سقفِ مصرفِ ۲۴ ساعتهٔ کاربرِ شناسهٔ داخلی {customer.id} در فروشگاهِ {customer.shop_bot_id}: "
        f"{saved if saved is not None else 'برداشته شد'}",
    )
    await session.commit()
    await state.clear()
    window = _window(str(data.get("ai_usage_window") or "24h"))
    page = int(data.get("ai_usage_page") or 0)
    screen = await _detail_screen(session, customer.id, window, page)
    confirmation = texts.ai_usage_limit_saved(saved)
    if screen is None:
        await message.answer(confirmation)
        return
    await message.answer(f"{confirmation}\n\n{screen[0]}", reply_markup=screen[1])


@router.callback_query(F.data.startswith("ai_usage_block:"))
async def cb_ai_usage_block(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    parts = _parts(callback.data, 5)
    if parts is None or _decimal(parts[1], maximum=_MAX_ID) is None or _decimal(parts[4], maximum=_MAX_PAGE) is None:
        await callback.answer(texts.AI_USAGE_INVALID, show_alert=True)
        return
    if parts[2] not in {"0", "1"} or _strict_window(parts[3]) is None:
        await callback.answer(texts.AI_USAGE_INVALID, show_alert=True)
        return
    customer = await session.get(Customer, int(parts[1]))
    if customer is None:
        await callback.answer(texts.AI_USAGE_INVALID, show_alert=True)
        return

    blocked = parts[2] == "1"
    await crm_service.set_blocked(session, customer, blocked)
    await audit_log_service.log(
        session,
        AuditEventType.CUSTOMER_BLOCK_CHANGED,
        shop_bot_id=customer.shop_bot_id,
        actor_telegram_id=callback.from_user.id,
        details=f"بلاکِ کاربرِ شناسهٔ داخلی {customer.id} از پنلِ ادمینِ پلتفرم: {'فعال' if blocked else 'خاموش'}",
    )
    await session.commit()
    await state.clear()
    screen = await _detail_screen(session, customer.id, parts[3], int(parts[4]))
    if screen is None:
        await callback.answer(texts.AI_USAGE_INVALID)
        return
    await callback.answer()
    await safe_edit(callback, screen[0], screen[1])
