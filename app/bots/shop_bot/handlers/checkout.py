"""چک‌اوتِ مرحله‌ایِ سبدِ خرید (W5 · C3 / 1.1).

مراحل: نامِ تحویل‌گیرنده ← موبایل ← (فقط کالایِ فیزیکی) آدرس از دفترچه/ورودِ تازه ← (اگر حتی یک روشِ ارسالِ فعال
وجود داشته باشد) روشِ ارسال ← سوال‌هایِ سفارشیِ فروشگاه‌دار ← توضیح ← پیش‌فاکتور (با هزینه‌یِ ارسال) ← «ثبتِ نهایی».

نگهبان‌هایِ قبلی حفظ شده‌اند: اثرانگشتِ سبد، `previewed_final_total` (مبلغی که می‌بینه = مبلغی که ثبت می‌شه)، قفلِ کمپین،
و `state.clear()` قبلِ هر I/O در «ثبتِ نهایی» (دابل‌تپ = یک سفارش). این روتر قبل از `customer.router` include می‌شه (F20).
"""

from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from typing import NamedTuple

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.main_bot import texts as main_texts
from app.bots.shop_bot import checkout_ui as ui
from app.bots.shop_bot import keyboards, texts
from app.bots.shop_bot.states import CheckoutStates
from app.config import settings
from app.database.models import OrderStatus, OrderType
from app.services import (
    address_book_service,
    bale_credentials_service,
    bale_service,
    campaign_service,
    cart_service,
    checkout_config_service,
    checkout_flow,
    customer_service,
    digital_service,
    order_payment_service,
    order_service,
    order_state,
    order_transition_service,
    payment_settings_service,
    shipping_service,
    shop_bot_service,
    shop_owner_service,
    shop_prefs_service,
)
from app.services.admin_settings_service import get_admin_settings
from app.utils import validators

logger = logging.getLogger(__name__)

router = Router(name="shop_checkout")

_POS_TO_STATE = {
    checkout_flow.POS_NAME: CheckoutStates.entering_name,
    checkout_flow.POS_PHONE: CheckoutStates.entering_phone,
    checkout_flow.POS_ADDR_PICK: CheckoutStates.choosing_address,
    checkout_flow.POS_PROV: CheckoutStates.entering_province,
    checkout_flow.POS_CITY: CheckoutStates.entering_city,
    checkout_flow.POS_ADDR_TEXT: CheckoutStates.entering_address,
    checkout_flow.POS_POSTAL: CheckoutStates.entering_postal,
    checkout_flow.POS_SHIP: CheckoutStates.choosing_shipping,
    checkout_flow.POS_QA: CheckoutStates.answering_questions,
    checkout_flow.POS_NOTE: CheckoutStates.entering_note,
    checkout_flow.POS_PREVIEW: CheckoutStates.confirming,
}
_ADDRESS_SUBSTEPS = (
    checkout_flow.POS_PROV,
    checkout_flow.POS_CITY,
    checkout_flow.POS_ADDR_TEXT,
    checkout_flow.POS_POSTAL,
)
# همه‌یِ stateهایِ مرحله‌ایِ قبل از پیش‌نمایش (برایِ «برگشت»/«انصراف»)
_STAGE_STATES = (
    CheckoutStates.entering_name,
    CheckoutStates.entering_phone,
    CheckoutStates.choosing_address,
    CheckoutStates.managing_addresses,
    CheckoutStates.entering_province,
    CheckoutStates.entering_city,
    CheckoutStates.entering_address,
    CheckoutStates.entering_postal,
    CheckoutStates.choosing_shipping,
    CheckoutStates.answering_questions,
    CheckoutStates.entering_note,
)


@dataclass
class _Ctx:
    message: Message
    state: FSMContext
    session: AsyncSession
    shop_bot: object
    customer: object
    items: list


class _CheckoutPreview(NamedTuple):
    text: str
    keyboard: InlineKeyboardMarkup
    offer: "campaign_service.Offer | None"
    final_total: int  # شاملِ هزینه‌یِ ارسال
    code: str | None
    code_dropped: bool


async def _safe_edit(callback: CallbackQuery, text: str, reply_markup=None) -> None:
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            raise


async def _load_ctx(event: Message | CallbackQuery, state: FSMContext, session: AsyncSession) -> _Ctx | None:
    """فروشگاه/مشتری/سبد رو می‌خونه. سبدِ خالی ⇒ state پاک + پیام ⇒ None."""
    message = event.message if isinstance(event, CallbackQuery) else event
    shop_bot = await shop_bot_service.get_by_bot_telegram_id(session, event.bot.id)
    if shop_bot is None or message is None:
        return None
    customer = await customer_service.get_by_shop_bot_and_telegram_id(session, shop_bot.id, event.from_user.id)
    cart = await cart_service.get_or_create_cart(session, shop_bot.id, customer.id) if customer else None
    items = await cart_service.get_items_with_products(session, cart.id) if cart else []
    if not items:
        await state.clear()
        await message.answer(texts.CART_EMPTY)
        return None
    return _Ctx(message, state, session, shop_bot, customer, items)


# =============================================================================
# حرکت بینِ مرحله‌ها
# =============================================================================
async def _resolve_shipping(session: AsyncSession, shop_bot, data: dict, items):
    """(روش|None, هزینه, لازمِ‌انتخاب). بدونِ کالایِ فیزیکی/بدونِ روشِ فعال ⇒ (None, 0, False)."""
    if not data.get("ck_physical"):
        return None, 0, False
    methods = await shipping_service.list_methods(session, shop_bot.id, only_active=True)
    if not methods:
        return None, 0, False
    chosen = next((m for m in methods if m.id == data.get("ck_ship_id")), None)
    if chosen is None:
        # B8: حتی با یک روشِ فعال هم انتخابِ خودکار نداریم — مشتری باید هزینه‌یِ ارسال را ببیند و تایید کند.
        return None, 0, True
    subtotal = checkout_flow.physical_subtotal(items, digital_service.is_digital)
    return chosen, checkout_flow.shipping_fee(chosen.fee_toman, chosen.free_over_toman, subtotal), False


def _ship_label(method, fee: int) -> str:
    return f"{method.name} · {'رایگان' if fee == 0 else validators.format_toman(fee)}"


def _disabled(data: dict) -> frozenset[str]:
    """B9: گام‌هایِ خاموشِ همین فروشگاه (اسنپشاتِ همان لحظه‌یِ شروعِ چک‌اوت)."""
    return frozenset(data.get("ck_disabled") or ())


def _ask(data: dict, key: str, default: str) -> str:
    """B9: متنِ پرسشِ گام — تنظیمِ فروشگاه‌دار اگر باشد، وگرنه متنِ پیش‌فرض."""
    return (data.get("ck_questions") or {}).get(key) or default


def _qa_pairs(data: dict, method, fee: int) -> list[tuple[str, str]]:
    phone = data.get("ck_phone") or ""
    return checkout_flow.build_qa_pairs(
        name=data.get("ck_name") or "",
        phone_display=validators.format_phone_display(phone) or phone,
        address_text=data.get("ck_addr_text") if data.get("ck_physical") else None,
        ship_label=_ship_label(method, fee) if method is not None else None,
        questions=list(data.get("questions") or []),
        answers=list(data.get("answers") or []),
        note=data.get("ck_note"),
        disabled=_disabled(data),
    )


async def _go(ctx: _Ctx, pos: str, *, push: bool = True) -> None:
    data = await ctx.state.get_data()
    stack = list(data.get("ck_stack") or [])
    if push:
        stack = checkout_flow.push_history(stack, data.get("ck_pos"))
    update: dict = {"ck_pos": pos, "ck_stack": stack}
    if pos == checkout_flow.POS_QA:
        update.update(ck_qa_i=0, answers=[])
    await ctx.state.update_data(**update)
    await _render(ctx, pos)


async def _advance(ctx: _Ctx, pos: str) -> None:
    """بعد از تکمیلِ یه مرحله: اگه «ویرایش از پیش‌نمایش» بود برگرد به پیش‌نمایش؛ وگرنه مرحله‌یِ بعد."""
    data = await ctx.state.get_data()
    if pos in (checkout_flow.POS_ADDR_PICK, *_ADDRESS_SUBSTEPS):
        # آدرس کامل شد: زیرمرحله‌هایِ آدرس از تاریخچه حذف و «انتخابِ آدرس» جایگزین‌شون می‌شه
        stack = [p for p in (data.get("ck_stack") or []) if p not in _ADDRESS_SUBSTEPS and p != checkout_flow.POS_ADDR_PICK]
        stack.append(checkout_flow.POS_ADDR_PICK)
        await ctx.state.update_data(ck_stack=stack, ck_pos=checkout_flow.POS_ADDR_PICK, ck_addr_new=None)
        data = await ctx.state.get_data()
        pos = checkout_flow.POS_ADDR_PICK
        if data.get("ck_ret"):
            await ctx.state.update_data(ck_ret=False, ck_stack=stack[:-1])
            await _go(ctx, checkout_flow.POS_PREVIEW, push=False)
            return
        stack = stack[:-1]
        await ctx.state.update_data(ck_stack=stack)
        data = await ctx.state.get_data()
        await _go_next(ctx, data, pos)
        return
    if data.get("ck_ret"):
        await ctx.state.update_data(ck_ret=False)
        await _go(ctx, checkout_flow.POS_PREVIEW, push=False)
        return
    await _go_next(ctx, data, pos)


async def _go_next(ctx: _Ctx, data: dict, pos: str) -> None:
    nxt = checkout_flow.next_position(
        pos,
        physical=bool(data.get("ck_physical")),
        ship_choice=bool(data.get("ck_ship_choice")),
        has_questions=bool(data.get("questions")),
        disabled=_disabled(data),
    )
    await _go(ctx, nxt)


async def _back(ctx: _Ctx) -> None:
    data = await ctx.state.get_data()
    if data.get("ck_ret"):
        await ctx.state.update_data(ck_ret=False)
        await _go(ctx, checkout_flow.POS_PREVIEW, push=False)
        return
    pos = data.get("ck_pos")
    qa_i = int(data.get("ck_qa_i") or 0)
    if pos == checkout_flow.POS_QA and qa_i > 0:
        answers = list(data.get("answers") or [])[: qa_i - 1]
        await ctx.state.update_data(ck_qa_i=qa_i - 1, answers=answers)
        await _render(ctx, checkout_flow.POS_QA)
        return
    prev, stack = checkout_flow.pop_history(data.get("ck_stack") or [])
    if prev is None:
        await _render(ctx, pos or checkout_flow.POS_NAME)
        return
    update: dict = {"ck_stack": stack, "ck_pos": prev}
    if prev == checkout_flow.POS_QA:
        total = len(data.get("questions") or [])
        update.update(ck_qa_i=max(0, total - 1), answers=list(data.get("answers") or [])[: max(0, total - 1)])
    await ctx.state.update_data(**update)
    await _render(ctx, prev)


async def _render(ctx: _Ctx, pos: str) -> None:
    data = await ctx.state.get_data()
    message = ctx.message
    if pos == checkout_flow.POS_ADDR_PICK:
        addresses = await address_book_service.list_addresses(ctx.session, ctx.customer.id)
        if not addresses:
            await _go(ctx, checkout_flow.POS_PROV, push=False)
            return
        await ctx.state.set_state(_POS_TO_STATE[pos])
        await message.answer(ui.ASK_ADDRESS_PICK, reply_markup=ui.address_pick_keyboard(addresses))
        return
    if pos == checkout_flow.POS_PREVIEW:
        preview = await _prepare_checkout_preview(ctx.state, ctx.session, ctx.shop_bot, ctx.customer, ctx.items, data.get("discount_code"))
        if preview is None:
            await _go(ctx, checkout_flow.POS_SHIP, push=False)
            return
        await message.answer(preview.text, reply_markup=preview.keyboard)
        return

    await ctx.state.set_state(_POS_TO_STATE[pos])
    if pos == checkout_flow.POS_NAME:
        full = " ".join(p for p in (ctx.customer.first_name, getattr(ctx.customer, "last_name", None)) if p)
        suggest = data.get("ck_name") or validators.clean_person_name(full)
        await ctx.state.update_data(ck_name_suggest=suggest)
        prompt = ui.name_prompt(suggest) if suggest else _ask(data, "name", ui.ASK_NAME_PLAIN)
        await message.answer(prompt, reply_markup=ui.name_keyboard(suggest))
    elif pos == checkout_flow.POS_PHONE:
        saved = validators.format_phone_display(data.get("ck_phone") or ctx.customer.phone_number)
        await message.answer(_ask(data, "phone", ui.ASK_PHONE), reply_markup=ui.phone_keyboard(saved))
    elif pos == checkout_flow.POS_PROV:
        await message.answer(ui.ASK_PROVINCE, reply_markup=ui.nav_keyboard())
    elif pos == checkout_flow.POS_CITY:
        await message.answer(ui.ASK_CITY, reply_markup=ui.nav_keyboard())
    elif pos == checkout_flow.POS_ADDR_TEXT:
        await message.answer(_ask(data, "address", ui.ASK_ADDRESS_TEXT), reply_markup=ui.nav_keyboard())
    elif pos == checkout_flow.POS_POSTAL:
        await message.answer(ui.ASK_POSTAL, reply_markup=ui.nav_keyboard(skip=True))
    elif pos == checkout_flow.POS_SHIP:
        methods = await shipping_service.list_methods(ctx.session, ctx.shop_bot.id, only_active=True)
        if not methods:
            # روشِ ارسالِ فعالی نمانده (مثلاً فروشگاه‌دار وسطِ چک‌اوت همه را خاموش کرده) ⇒ مرحله رد می‌شود.
            await ctx.state.update_data(ck_ship_choice=False, ck_ship_id=None, ck_no_shipping=bool(data.get("ck_physical")))
            await _advance(ctx, checkout_flow.POS_SHIP)
            return
        subtotal = checkout_flow.physical_subtotal(ctx.items, digital_service.is_digital)
        options = [
            (m.id, ui.shipping_option_label(m, checkout_flow.shipping_fee(m.fee_toman, m.free_over_toman, subtotal))) for m in methods
        ]
        await message.answer(_ask(data, "shipping", ui.ASK_SHIPPING), reply_markup=ui.shipping_keyboard(options))
    elif pos == checkout_flow.POS_QA:
        questions = list(data.get("questions") or [])
        index = int(data.get("ck_qa_i") or 0)
        await message.answer(
            texts.checkout_question_prompt(questions[index], index + 1, len(questions)), reply_markup=ui.nav_keyboard()
        )
    elif pos == checkout_flow.POS_NOTE:
        await message.answer(_ask(data, "note", ui.ASK_NOTE), reply_markup=ui.nav_keyboard(skip=True))


async def _prepare_checkout_preview(
    state: FSMContext, session: AsyncSession, shop_bot, customer, items, code: str | None
) -> _CheckoutPreview | None:
    """پیش‌نمایشِ نهایی (اقلام، تخفیف، ارسال، جمع). None ⇒ روشِ ارسال باید انتخاب بشه.
    اثرانگشتِ سبد، کدِ نگه‌داشته‌شده و مبلغِ نمایش‌داده‌شده (با ارسال) توی data ذخیره می‌شن."""
    data = await state.get_data()
    method, fee, needs_choice = await _resolve_shipping(session, shop_bot, data, items)
    if needs_choice:
        return None
    list_total = sum(product.price_toman * item.quantity for item, product in items)
    quote = await campaign_service.find_best_offer(session, shop_bot.id, customer.id, list_total, code=code)
    kept_code = code if (code and quote.code_problem is None) else None
    show_code_button = kept_code is not None or await campaign_service.has_open_code_campaign(session, shop_bot.id)
    items_total = quote.offer.final_total_toman if quote.offer is not None else list_total
    grand_total = items_total + fee

    await state.update_data(
        cart_fingerprint=cart_service.cart_fingerprint(items),
        discount_code=kept_code,
        previewed_final_total=grand_total,
        ck_pos=checkout_flow.POS_PREVIEW,
    )
    await state.set_state(CheckoutStates.confirming)
    pairs = _qa_pairs(data, method, fee)
    return _CheckoutPreview(
        text=ui.preview_text(items, pairs, quote.offer, method.name if method is not None else None, fee, grand_total),
        keyboard=ui.preview_keyboard(
            show_code_button=show_code_button,
            code_applied=kept_code is not None,
            physical=bool(data.get("ck_physical")),
            ship_choice=bool(data.get("ck_ship_choice")),
        ),
        offer=quote.offer,
        final_total=grand_total,
        code=kept_code,
        code_dropped=bool(code) and kept_code is None,
    )


# =============================================================================
# شروع
# =============================================================================
@router.callback_query(F.data == "cart_checkout_start")
async def cart_checkout_start(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    shop_bot = await shop_bot_service.get_by_bot_telegram_id(session, callback.bot.id)
    if shop_bot is None:
        await callback.answer()
        return
    customer = await customer_service.get_by_shop_bot_and_telegram_id(session, shop_bot.id, callback.from_user.id)
    cart = await cart_service.get_or_create_cart(session, shop_bot.id, customer.id) if customer else None
    items = await cart_service.get_items_with_products(session, cart.id) if cart else []
    if not items:
        await callback.answer(texts.CART_EMPTY, show_alert=True)
        return

    physical = checkout_flow.is_physical_cart(items, digital_service.is_digital)
    methods = await shipping_service.list_methods(session, shop_bot.id, only_active=True) if physical else []
    # B9: گام‌هایِ روشن/خاموش و متنِ پرسشِ همین فروشگاه یک‌بار خوانده و در state فریز می‌شوند ⇒
    # تغییرِ تنظیم وسطِ چک‌اوت، جریانِ نیمه‌کاره را نمی‌شکند.
    steps = checkout_config_service.parse(shop_bot.checkout_config)
    disabled = checkout_config_service.disabled_positions(steps)
    ship_choice = physical and bool(methods)
    # دیتایِ تلاشِ نیمه‌کاره‌یِ قبلی نباید به این چک‌اوت نشت کنه.
    await state.set_data(
        {
            "questions": checkout_flow.custom_questions(shop_bot.checkout_questions),
            "answers": [],
            "discount_code": None,
            "previewed_final_total": None,
            "ck_physical": physical,
            # B8: با حتی یک روشِ فعال هم مرحله‌یِ ارسال نشان داده می‌شود (قبلاً فقط ≥۲ روش).
            "ck_ship_choice": ship_choice,
            # B8: سبدِ فیزیکی بدونِ هیچ روشِ ارسالِ فعال ⇒ چک‌اوت بدونِ هزینه‌یِ ارسال ادامه می‌یابد
            # و فروشگاه‌دار در اعلانِ سفارش هشدار می‌گیرد.
            "ck_no_shipping": physical and not methods,
            "ck_stack": [],
            "ck_pos": None,
            "ck_ret": False,
            "ck_disabled": sorted(disabled),
            "ck_questions": checkout_config_service.questions(steps),
        }
    )
    await callback.answer()
    ctx = _Ctx(callback.message, state, session, shop_bot, customer, items)
    has_questions = bool(checkout_flow.custom_questions(shop_bot.checkout_questions))
    await _go(
        ctx,
        checkout_flow.first_position(physical=physical, ship_choice=ship_choice, has_questions=has_questions, disabled=disabled),
        push=False,
    )


# =============================================================================
# ناوبری و انصراف
# =============================================================================
@router.callback_query(StateFilter(*_STAGE_STATES), F.data == ui.BACK_CB)
async def checkout_back(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await callback.answer()
    ctx = await _load_ctx(callback, state, session)
    if ctx is not None:
        await _back(ctx)


@router.callback_query(StateFilter(*_STAGE_STATES, CheckoutStates.confirming), F.data == ui.CANCEL_CB)
async def cart_checkout_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await callback.message.edit_text(texts.CHECKOUT_CANCELLED)


# =============================================================================
# نام و موبایل
# =============================================================================
@router.callback_query(CheckoutStates.entering_name, F.data == "ck_name_ok")
async def checkout_name_ok(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    data = await state.get_data()
    suggest = validators.clean_person_name(data.get("ck_name_suggest"))
    if suggest is None:
        await callback.answer(ui.NAME_INVALID, show_alert=True)
        return
    await callback.answer()
    ctx = await _load_ctx(callback, state, session)
    if ctx is None:
        return
    await state.update_data(ck_name=suggest)
    await _advance(ctx, checkout_flow.POS_NAME)


@router.message(CheckoutStates.entering_name, F.text)
async def checkout_name_received(message: Message, session: AsyncSession, state: FSMContext) -> None:
    name = validators.clean_person_name(message.text)
    if name is None:
        await message.answer(ui.NAME_INVALID)
        return
    ctx = await _load_ctx(message, state, session)
    if ctx is None:
        return
    await state.update_data(ck_name=name)
    await _advance(ctx, checkout_flow.POS_NAME)


async def _save_phone(ctx: _Ctx, local_phone: str, via_contact: bool) -> None:
    await ctx.state.update_data(ck_phone=local_phone)
    ctx.customer.phone_number = validators.to_e164_iran(local_phone)
    if via_contact:
        ctx.customer.phone_via_contact = True
    await ctx.session.flush()
    await _advance(ctx, checkout_flow.POS_PHONE)


@router.callback_query(CheckoutStates.entering_phone, F.data == "ck_phone_saved")
async def checkout_phone_saved(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    ctx = await _load_ctx(callback, state, session)
    if ctx is None:
        await callback.answer()
        return
    data = await state.get_data()
    local = validators.normalize_iran_phone(data.get("ck_phone") or ctx.customer.phone_number or "")
    if local is None:
        await callback.answer(ui.PHONE_INVALID, show_alert=True)
        return
    await callback.answer()
    await _save_phone(ctx, local, False)


@router.message(CheckoutStates.entering_phone, F.contact)
async def checkout_phone_contact(message: Message, session: AsyncSession, state: FSMContext) -> None:
    contact = message.contact
    if contact.user_id is not None and contact.user_id != message.from_user.id:
        await message.answer(ui.CONTACT_NOT_YOURS)
        return
    local = validators.normalize_iran_phone(contact.phone_number or "")
    if local is None:
        await message.answer(ui.PHONE_INVALID)
        return
    ctx = await _load_ctx(message, state, session)
    if ctx is not None:
        await _save_phone(ctx, local, True)


@router.message(CheckoutStates.entering_phone, F.text)
async def checkout_phone_received(message: Message, session: AsyncSession, state: FSMContext) -> None:
    local = validators.normalize_iran_phone(message.text or "")
    if local is None:
        await message.answer(ui.PHONE_INVALID)
        return
    ctx = await _load_ctx(message, state, session)
    if ctx is not None:
        await _save_phone(ctx, local, False)


# =============================================================================
# آدرس (دفترچه‌آدرس + ورودِ تازه)
# =============================================================================
@router.callback_query(CheckoutStates.choosing_address, F.data.startswith("ck_addr_sel:"))
async def checkout_address_selected(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    raw = callback.data.split(":", 1)[1]
    ctx = await _load_ctx(callback, state, session)
    if ctx is None:
        await callback.answer()
        return
    row = await address_book_service.get_owned(session, int(raw), ctx.customer.id) if raw.isdecimal() and raw.isascii() else None
    if row is None:
        await callback.answer(ui.ADDRESS_GONE, show_alert=True)
        await _render(ctx, checkout_flow.POS_ADDR_PICK)
        return
    await callback.answer()
    await state.update_data(ck_addr_id=row.id, ck_addr_text=address_book_service.format_address(row))
    await _advance(ctx, checkout_flow.POS_ADDR_PICK)


@router.callback_query(CheckoutStates.choosing_address, F.data == "ck_addr_new")
async def checkout_address_new(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    ctx = await _load_ctx(callback, state, session)
    if ctx is None:
        await callback.answer()
        return
    if len(await address_book_service.list_addresses(session, ctx.customer.id)) >= address_book_service.MAX_ADDRESSES:
        await callback.answer(ui.ADDRESS_LIMIT_REACHED, show_alert=True)
        return
    await callback.answer()
    await state.update_data(ck_addr_new={})
    await _go(ctx, checkout_flow.POS_PROV)


@router.callback_query(CheckoutStates.choosing_address, F.data == "ck_addr_mng")
async def checkout_address_manage(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    ctx = await _load_ctx(callback, state, session)
    if ctx is None:
        await callback.answer()
        return
    await callback.answer()
    await state.set_state(CheckoutStates.managing_addresses)
    addresses = await address_book_service.list_addresses(session, ctx.customer.id)
    await ctx.message.answer(ui.address_manage_text(addresses), reply_markup=ui.address_manage_keyboard(addresses))


async def _manage_action(callback: CallbackQuery, session: AsyncSession, state: FSMContext, delete: bool) -> None:
    raw = callback.data.split(":", 1)[1]
    ctx = await _load_ctx(callback, state, session)
    if ctx is None:
        await callback.answer()
        return
    address_id = int(raw) if raw.isdecimal() and raw.isascii() else -1
    ok = (
        await address_book_service.delete_address(session, ctx.customer.id, address_id)
        if delete
        else await address_book_service.set_default(session, ctx.customer.id, address_id)
    )
    if not ok:
        await callback.answer(ui.ADDRESS_GONE, show_alert=True)
    else:
        await callback.answer(ui.ADDRESS_DELETED if delete else ui.ADDRESS_DEFAULTED)
        data = await state.get_data()
        if delete and data.get("ck_addr_id") == address_id:
            await state.update_data(ck_addr_id=None, ck_addr_text=None)
    addresses = await address_book_service.list_addresses(session, ctx.customer.id)
    await _safe_edit(callback, ui.address_manage_text(addresses), reply_markup=ui.address_manage_keyboard(addresses))


@router.callback_query(CheckoutStates.managing_addresses, F.data.startswith("ck_addr_def:"))
async def checkout_address_default(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await _manage_action(callback, session, state, delete=False)


@router.callback_query(CheckoutStates.managing_addresses, F.data.startswith("ck_addr_del:"))
async def checkout_address_delete(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await _manage_action(callback, session, state, delete=True)


@router.callback_query(CheckoutStates.managing_addresses, F.data == "ck_addr_pick")
async def checkout_address_back_to_pick(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await callback.answer()
    ctx = await _load_ctx(callback, state, session)
    if ctx is not None:
        await _render(ctx, checkout_flow.POS_ADDR_PICK)


async def _store_new_address_field(state: FSMContext, key: str, value: str) -> None:
    data = await state.get_data()
    fields = dict(data.get("ck_addr_new") or {})
    fields[key] = value
    await state.update_data(ck_addr_new=fields)


@router.message(CheckoutStates.entering_province, F.text)
async def checkout_province_received(message: Message, session: AsyncSession, state: FSMContext) -> None:
    value = validators.clean_place_name(message.text)
    if value is None:
        await message.answer(ui.PLACE_INVALID)
        return
    ctx = await _load_ctx(message, state, session)
    if ctx is None:
        return
    await _store_new_address_field(state, "province", value)
    await _go(ctx, checkout_flow.POS_CITY)


@router.message(CheckoutStates.entering_city, F.text)
async def checkout_city_received(message: Message, session: AsyncSession, state: FSMContext) -> None:
    value = validators.clean_place_name(message.text)
    if value is None:
        await message.answer(ui.PLACE_INVALID)
        return
    ctx = await _load_ctx(message, state, session)
    if ctx is None:
        return
    await _store_new_address_field(state, "city", value)
    await _go(ctx, checkout_flow.POS_ADDR_TEXT)


@router.message(CheckoutStates.entering_address, F.text)
async def checkout_address_text_received(message: Message, session: AsyncSession, state: FSMContext) -> None:
    value = validators.clean_address_text(message.text)
    if value is None:
        await message.answer(ui.ADDRESS_INVALID)
        return
    ctx = await _load_ctx(message, state, session)
    if ctx is None:
        return
    await _store_new_address_field(state, "address", value)
    await _go(ctx, checkout_flow.POS_POSTAL)


async def _finish_new_address(ctx: _Ctx, postal: str | None) -> None:
    data = await ctx.state.get_data()
    fields = data.get("ck_addr_new")
    if not fields or not all(fields.get(k) for k in ("province", "city", "address")):
        # دابل‌تپ/آپدیتِ کهنه: آدرسِ در-حالِ-ساخت دیگه نیست ⇒ اثرِ دوم نداریم.
        await ctx.message.answer(ui.STALE_STEP)
        return
    # قبلِ هر I/O برداشته می‌شه تا دو آپدیتِ هم‌زمان دو آدرس نسازن
    await ctx.state.update_data(ck_addr_new=None)
    row = await address_book_service.add_address(
        ctx.session,
        ctx.customer.id,
        province=fields["province"],
        city=fields["city"],
        address=fields["address"],
        postal_code=postal,
    )
    if row is None:
        await ctx.message.answer(ui.ADDRESS_LIMIT_REACHED)
        await _go(ctx, checkout_flow.POS_ADDR_PICK, push=False)
        return
    await ctx.state.update_data(ck_addr_id=row.id, ck_addr_text=address_book_service.format_address(row))
    await _advance(ctx, checkout_flow.POS_POSTAL)


@router.message(CheckoutStates.entering_postal, F.text)
async def checkout_postal_received(message: Message, session: AsyncSession, state: FSMContext) -> None:
    postal = validators.is_valid_postal_code(message.text)
    if postal is None:
        await message.answer(ui.POSTAL_INVALID, reply_markup=ui.nav_keyboard(skip=True))
        return
    ctx = await _load_ctx(message, state, session)
    if ctx is not None:
        await _finish_new_address(ctx, postal)


@router.callback_query(CheckoutStates.entering_postal, F.data == ui.SKIP_CB)
async def checkout_postal_skipped(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await callback.answer()
    ctx = await _load_ctx(callback, state, session)
    if ctx is not None:
        await _finish_new_address(ctx, None)


# =============================================================================
# روشِ ارسال، سوال‌هایِ فروشگاه‌دار، توضیح
# =============================================================================
@router.callback_query(CheckoutStates.choosing_shipping, F.data.startswith("ck_ship:"))
async def checkout_shipping_selected(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    raw = callback.data.split(":", 1)[1]
    ctx = await _load_ctx(callback, state, session)
    if ctx is None:
        await callback.answer()
        return
    method = await shipping_service.get_owned(session, int(raw), ctx.shop_bot.id) if raw.isdecimal() and raw.isascii() else None
    if method is None or not method.is_active:
        await callback.answer(ui.SHIPPING_GONE, show_alert=True)
        await _render(ctx, checkout_flow.POS_SHIP)
        return
    await callback.answer()
    await state.update_data(ck_ship_id=method.id)
    await _advance(ctx, checkout_flow.POS_SHIP)


@router.message(CheckoutStates.answering_questions, F.text)
async def checkout_answer_received(message: Message, session: AsyncSession, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text or len(text) > checkout_flow.MAX_ANSWER_LENGTH:
        await message.answer(ui.ANSWER_TOO_LONG)
        return
    data = await state.get_data()
    questions = list(data.get("questions") or [])
    answers = list(data.get("answers") or [])
    if not questions:
        await message.answer(ui.STALE_STEP)
        return
    ctx = await _load_ctx(message, state, session)
    if ctx is None:
        return
    answers.append(text)
    if len(answers) < len(questions):
        await state.update_data(answers=answers, ck_qa_i=len(answers))
        await _render(ctx, checkout_flow.POS_QA)
        return
    await state.update_data(answers=answers)
    await _advance(ctx, checkout_flow.POS_QA)


@router.message(CheckoutStates.entering_note, F.text)
async def checkout_note_received(message: Message, session: AsyncSession, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text or len(text) > checkout_flow.MAX_NOTE_LENGTH:
        await message.answer(ui.NOTE_TOO_LONG)
        return
    ctx = await _load_ctx(message, state, session)
    if ctx is None:
        return
    await state.update_data(ck_note=text)
    await _advance(ctx, checkout_flow.POS_NOTE)


@router.callback_query(CheckoutStates.entering_note, F.data == ui.SKIP_CB)
async def checkout_note_skipped(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await callback.answer()
    ctx = await _load_ctx(callback, state, session)
    if ctx is None:
        return
    await state.update_data(ck_note=None)
    await _advance(ctx, checkout_flow.POS_NOTE)


# مرحله‌هایی که فقط با دکمه جواب می‌گیرن: متنِ آزاد نباید به‌عنوانِ چتِ AI تفسیر بشه.
@router.message(
    StateFilter(CheckoutStates.choosing_address, CheckoutStates.managing_addresses, CheckoutStates.choosing_shipping), F.text
)
async def checkout_button_only_hint(message: Message) -> None:
    await message.answer("لطفاً از دکمه‌هایِ همین مرحله استفاده کن 🙏 (یا «❌ انصراف»).")


# =============================================================================
# پیش‌نمایش: ویرایش
# =============================================================================
@router.callback_query(CheckoutStates.confirming, F.data.startswith("ck_edit:"))
async def checkout_edit_from_preview(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    field = callback.data.split(":", 1)[1]
    target = {
        "name": checkout_flow.POS_NAME,
        "phone": checkout_flow.POS_PHONE,
        "addr": checkout_flow.POS_ADDR_PICK,
        "ship": checkout_flow.POS_SHIP,
    }.get(field)
    data = await state.get_data()
    if target is None or (target in (checkout_flow.POS_ADDR_PICK, checkout_flow.POS_SHIP) and not data.get("ck_physical")):
        await callback.answer(ui.STALE_STEP, show_alert=True)
        return
    if target == checkout_flow.POS_SHIP and not data.get("ck_ship_choice"):
        await callback.answer(ui.STALE_STEP, show_alert=True)
        return
    ctx = await _load_ctx(callback, state, session)
    if ctx is None:
        await callback.answer()
        return
    await callback.answer()
    await state.update_data(ck_ret=True)
    await _go(ctx, target)


# =============================================================================
# کدِ تخفیف
# =============================================================================
@router.callback_query(CheckoutStates.confirming, F.data == "cart_discount_code")
async def cart_discount_code_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(CheckoutStates.entering_discount_code)
    await callback.answer()
    # پیش‌نمایش با دکمه‌هایش جایگزینِ پیامِ راهنما می‌شه (دکمه‌یِ کهنه‌ای نمی‌مونه)؛ بعدِ
    # واردکردنِ کد، پیش‌نمایشِ تازه به‌عنوانِ پیامِ جدید فرستاده می‌شه.
    await _safe_edit(callback, texts.CHECKOUT_ASK_DISCOUNT_CODE)


@router.message(CheckoutStates.entering_discount_code, F.text)
async def checkout_discount_code_received(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    code: str | None = data.get("discount_code")
    raw = (message.text or "").strip()

    ctx = await _load_ctx(message, state, session)
    if ctx is None:
        return
    shop_bot, customer, items = ctx.shop_bot, ctx.customer, ctx.items

    notice: str | None = None
    if raw == "حذف":
        code = None
        notice = texts.DISCOUNT_CODE_REMOVED
    elif raw != "برگشت":
        if not campaign_service.register_code_attempt(shop_bot.id, message.from_user.id):
            await message.answer(texts.DISCOUNT_CODE_TOO_MANY_ATTEMPTS)
            return
        candidate = campaign_service.normalize_code(raw)
        if not campaign_service.is_valid_code(candidate):
            await message.answer(texts.discount_code_problem("not_found") + texts.DISCOUNT_CODE_RETRY_HINT)
            return
        list_total = sum(product.price_toman * item.quantity for item, product in items)
        quote = await campaign_service.find_best_offer(session, shop_bot.id, customer.id, list_total, code=candidate)
        if quote.code_problem is not None:
            problem_text = texts.discount_code_problem(quote.code_problem.value, quote.code_min_cart_toman)
            await message.answer(problem_text + texts.DISCOUNT_CODE_RETRY_HINT)
            return
        code = candidate
        notice = texts.discount_code_outranked(quote.offer) if quote.code_outranked else texts.DISCOUNT_CODE_APPLIED

    preview = await _prepare_checkout_preview(state, session, shop_bot, customer, items, code)
    if preview is None:
        await _go(ctx, checkout_flow.POS_SHIP, push=False)
        return
    if preview.code_dropped:
        notice = texts.DISCOUNT_CODE_NO_LONGER_VALID
    text = f"{notice}\n\n{preview.text}" if notice else preview.text
    await message.answer(text, reply_markup=preview.keyboard)


# =============================================================================
# ثبتِ نهایی
# =============================================================================
@router.callback_query(CheckoutStates.confirming, F.data == "cart_checkout_confirm")
async def cart_checkout_confirm(callback: CallbackQuery, state: FSMContext, session: AsyncSession, main_bot: Bot) -> None:
    data = await state.get_data()
    previewed_cart_fingerprint: str | None = data.get("cart_fingerprint")
    discount_code: str | None = data.get("discount_code")
    previewed_final_total: int | None = data.get("previewed_final_total")
    # state.clear() عمداً همین اولِ کاره و قبلِ هر I/O ای: دابل‌تپِ «ثبتِ نهایی» دومین
    # آپدیت رو با فیلترِ CheckoutStates.confirming رد می‌کنه و سفارشِ تکراری ساخته نمی‌شه.
    await state.clear()

    shop_bot = await shop_bot_service.get_by_bot_telegram_id(session, callback.bot.id)
    if shop_bot is None:
        await callback.answer()
        return
    customer = await customer_service.get_by_shop_bot_and_telegram_id(session, shop_bot.id, callback.from_user.id)
    cart = await cart_service.get_or_create_cart(session, shop_bot.id, customer.id) if customer else None
    items = await cart_service.get_items_with_products(session, cart.id) if cart else []
    if not items:
        await callback.answer()
        await callback.message.edit_text(texts.CART_EMPTY)
        return

    if previewed_cart_fingerprint is not None and previewed_cart_fingerprint != cart_service.cart_fingerprint(items):
        # سبد بعد از نمایشِ پیش‌نمایش عوض شده؛ چیزی که مشتری دیده با چیزی که ثبت می‌شد یکی نیست.
        await callback.answer()
        await callback.message.edit_text(texts.CHECKOUT_CART_CHANGED)
        return

    physical = bool(data.get("ck_physical"))
    disabled = _disabled(data)
    name, phone_local = data.get("ck_name"), data.get("ck_phone")
    address_text = data.get("ck_addr_text") if physical else None
    # B9: فقط گام‌هایِ روشن الزامی‌اند؛ گامِ خاموش هیچ‌وقت پرسیده نشده پس نبودش اشکالی ندارد.
    missing = (
        (checkout_flow.POS_NAME not in disabled and not name)
        or (checkout_flow.POS_PHONE not in disabled and not phone_local)
        or (physical and checkout_flow.POS_ADDR_PICK not in disabled and not address_text)
    )
    if missing:
        await callback.answer()
        await callback.message.edit_text(ui.STALE_STEP)
        return

    ctx = _Ctx(callback.message, state, session, shop_bot, customer, items)
    method, ship_fee, needs_choice = await _resolve_shipping(session, shop_bot, data, items)
    if needs_choice:
        # روشِ انتخاب‌شده دیگه فعال نیست: برگرد به انتخابِ ارسال (دیتا بازیابی می‌شه).
        await state.set_data({**data, "ck_ship_id": None})
        await callback.answer()
        await callback.message.answer(ui.SHIPPING_GONE)
        await _go(ctx, checkout_flow.POS_SHIP, push=False)
        return

    # کمپین/تخفیف: اعتبارسنجیِ دوباره *با قفل* (ردیفِ کمپین‌ها FOR UPDATE) — تا دو مشتریِ
    # هم‌زمان نتونن هر دو آخرین ظرفیت رو بگیرن. قفل تا commit می‌مونه (پایین‌تر زود commit می‌شه).
    list_total = sum(product.price_toman * item.quantity for item, product in items)
    quote = await campaign_service.find_best_offer(session, shop_bot.id, customer.id, list_total, code=discount_code, lock=True)
    offer = quote.offer
    items_total = offer.final_total_toman if offer is not None else list_total
    final_total = items_total + ship_fee
    if previewed_final_total is not None and previewed_final_total != final_total:
        # کمپین/قیمت/هزینه‌یِ ارسال عوض شده: ثبت نمی‌کنیم و پیش‌نمایشِ تازه رو نشون می‌دیم.
        await state.set_data(data)
        preview = await _prepare_checkout_preview(state, session, shop_bot, customer, items, discount_code)
        assert preview is not None  # needs_choice بالا بررسی شد
        text = f"{texts.CHECKOUT_PRICE_CHANGED}\n\n{preview.text}"
        if preview.code_dropped:
            text = f"{texts.DISCOUNT_CODE_NO_LONGER_VALID}\n\n{text}"
        await callback.answer()
        await _safe_edit(callback, text, reply_markup=preview.keyboard)
        return

    qa_pairs = _qa_pairs(data, method, ship_fee)
    qa_text = "\n".join(f"{q}: {a}" for q, a in qa_pairs)
    phone_e164 = validators.to_e164_iran(phone_local) if phone_local else None
    group_id = secrets.token_hex(12)
    line_totals = [product.price_toman * item.quantity for item, product in items]
    # تخفیفِ سبد متناسب با مبلغِ هر ردیف پخش می‌شه؛ جمعِ سهم‌ها دقیقاً برابرِ تخفیفِ کله.
    shares = campaign_service.distribute_discount(line_totals, offer.discount_toman) if offer is not None else [0] * len(items)
    orders = []
    for (item, product), line_total, share in zip(items, line_totals, shares):
        order = await order_service.create_order(
            session,
            shop_bot.id,
            customer.id,
            OrderType.ORDER,
            f"{product.name} × {item.quantity} (از سبدِ خرید)",
            # قانونِ طلایی: مبلغِ ذخیره‌شده از اول *بعد از تخفیف* ـه؛ هزینه‌یِ ارسال جدا روی shipping_fee_toman.
            line_total - share,
            product_id=product.id,
            quantity=item.quantity,
        )
        order.cart_checkout_group_id = group_id
        order.checkout_answers = qa_text
        order.customer_phone = phone_e164
        if address_text:  # همه‌یِ ردیف‌هایِ گروه (فاکتور از ردیفِ اول می‌خونه)
            order.customer_address = address_text
        if method is not None:
            order.shipping_fee_toman = ship_fee
            order.shipping_method_name = method.name[:64]
        if offer is not None:
            order.campaign_id = offer.campaign_id
            order.discount_toman = share
        orders.append(order)
    await session.flush()

    # W3: اگه فروشگاه روشِ آنلاین/کارتی فعال کرده، سفارش‌ها منتظرِ پرداخت می‌شن (نه تاییدِ دستی)
    pay_settings = await payment_settings_service.get(session, shop_bot.id)
    pay_methods = await bale_credentials_service.methods(session, shop_bot, pay_settings)
    if pay_methods:
        for order in orders:
            order.status = OrderStatus.AWAITING_PAYMENT
        # A5: مهلتِ پرداختِ گروه per-shop است؛ NULL یعنی همان پیش‌فرضِ سراسری.
        order_payment_service.set_group_deadline(
            orders,
            shop_prefs_service.resolve(
                shop_prefs_service.ORDER_RESERVATION, shop_bot, await get_admin_settings(session)
            ),
        )
        await order_transition_service.record_event(
            session, orders[0], None, OrderStatus.AWAITING_PAYMENT, actor_type="customer", actor_ref=str(customer.id)
        )
        # PHASE 5D: همین‌جا جریانِ پرداخت شروع می‌شود ⇒ کمیسیونِ موردانتظار رزرو می‌شود
        # (گذّار وضعیت اینجا اجرا نمی‌شود، پس رزرو صریح صدا زده می‌شود).
        await order_transition_service.apply_commission(session, orders, order_state.AWAITING_PAYMENT)
        await session.flush()

    total_toman = order_transition_service.group_total_toman(orders)  # اقلام (بعد از تخفیف) + ارسال
    # متنِ اطلاع‌رسانیِ فروشگاه‌دار رو همین‌جا، قبل از خالی‌کردنِ سبد می‌سازیم.
    owner_notification_text = main_texts.cart_order_notification(customer, items, qa_pairs, total_toman, offer=offer)
    if data.get("ck_no_shipping"):
        owner_notification_text = f"{owner_notification_text}\n\n{main_texts.OWNER_NO_SHIPPING_METHOD_WARNING}"
    await cart_service.clear_cart(session, cart.id)
    if offer is not None or quote.locked:
        # قفلِ ردیفِ کمپین‌ها تا commit می‌مونه؛ بقیه‌ی هندلر تماسِ شبکه‌ست ⇒ همین‌جا commit (سفارش‌ها قطعی‌ان).
        await session.commit()

    ack_text = texts.checkout_completed_ack_with_discount(offer) if offer is not None else texts.CHECKOUT_COMPLETED_ACK
    try:
        await callback.answer()
        if pay_methods:
            ack_text = f"{ack_text}\n\n{texts.pay_choose_method_text(total_toman)}"
        await callback.message.edit_text(
            ack_text, reply_markup=keyboards.payment_methods_keyboard(group_id, pay_methods) if pay_methods else None
        )
    except TelegramAPIError:
        logger.exception("ویرایشِ پیامِ تاییدِ چک‌اوت برایِ مشتری %s ناموفق بود.", callback.from_user.id)

    owner = await shop_owner_service.get_by_id(session, shop_bot.shop_owner_id)
    if owner is not None:
        from app.bots.main_bot import keyboards as main_keyboards

        try:
            await main_bot.send_message(
                owner.telegram_id,
                owner_notification_text,
                reply_markup=(
                    main_keyboards.order_group_actions_keyboard(group_id, OrderStatus.AWAITING_PAYMENT)
                    if pay_methods
                    else main_keyboards.cart_group_notification_keyboard(group_id)
                ),
            )
        except TelegramAPIError:
            logger.exception("اطلاع‌رسانیِ سفارشِ سبد به فروشگاه‌دار %s ناموفق بود.", owner.telegram_id)

    if not pay_methods:
        await _maybe_offer_cart_online_payment(
            callback.bot, session, shop_bot, pay_settings, group_id, total_toman, customer.telegram_id
        )


async def _maybe_offer_cart_online_payment(
    shop_bot_instance: Bot, session: AsyncSession, shop_bot, pay_settings, group_id: str, total_toman: int, customer_telegram_id: int
) -> None:
    """مثلِ _maybe_offer_online_payment (customer.py) ولی برایِ مجموعِ کلِ سبد (شاملِ ارسال). payload با پیشوندِ
    'cartgroup-'؛ main.py موقعِ وب‌هوک group_id رو از payload جدا می‌کنه.

    B11: با همان ملاکِ واحدِ `bale_credentials_service.shop_status` که دکمه‌یِ بله‌پی هم با آن ساخته می‌شود؛
    پیکربندیِ ناقص ⇒ هیچ پیامِ اضافه‌ای به مشتری نمی‌رود."""
    if total_toman <= 0:
        return
    status = await bale_credentials_service.shop_status(session, shop_bot, pay_settings)
    if not status.available:
        return

    invoice_payload = f"cartgroup-{group_id}-{secrets.token_hex(8)}"
    try:
        pay_url = await bale_service.create_invoice_link(
            status.bot_token,
            status.provider_token,
            title="پرداختِ سبدِ خرید",
            description="پرداختِ سبدِ خرید",
            payload=invoice_payload,
            amount_rial=bale_service.toman_to_rial(total_toman),
        )
    except bale_service.BaleError:
        logger.exception("درخواستِ ساختِ لینکِ بله‌پی برایِ سبدِ %s ناموفق بود؛ گزینه‌ی پرداختِ آنلاین نشون داده نمی‌شه.", group_id)
        return

    try:
        await shop_bot_instance.send_message(
            customer_telegram_id, texts.online_payment_offer(total_toman), reply_markup=keyboards.online_payment_keyboard(pay_url)
        )
    except TelegramAPIError:
        logger.exception("ارسالِ پیشنهادِ پرداختِ آنلاینِ سبد به مشتری %s ناموفق بود.", customer_telegram_id)


# دکمه‌یِ کهنه‌یِ مرحله‌ایِ چک‌اوت (ری‌استارتِ ربات/state ازبین‌رفته): پیامِ مودبانه، نه سکوت. باید *آخرین* هندلرِ این روتر باشه.
@router.callback_query(F.data.startswith("ck_"))
async def checkout_stale_button(callback: CallbackQuery) -> None:
    await callback.answer(ui.STALE_STEP, show_alert=True)
