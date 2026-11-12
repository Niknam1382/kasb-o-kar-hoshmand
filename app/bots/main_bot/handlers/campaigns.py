"""
پنلِ فروشگاه‌دار — «🎯 کمپین‌ها» (فازِ ۳): ساختِ تخفیفِ مخصوصِ مشتری‌هایِ خودش
(ویزاردِ FSM)، فهرست با آمارِ مصرف، توقف/ادامه، حذفِ امن، و اعلام به مشتری‌ها.

منطقِ پول/محدودیت‌ها کلاً توی app/services/campaign_service.py ـه؛ اینجا فقط
گفتگو با فروشگاه‌دار است. «اعلام به مشتری‌ها» از خودِ سیستمِ «📣 پیام به مشتری‌ها»
(panel.py، CustomerBroadcastStates) استفاده می‌کنه: متنِ پیش‌فرض رو توی همون FSM
می‌ذاریم و تاییدِ/لغوِ ارسال رو هندلرهایِ همون سیستم انجام می‌دن.
"""
from __future__ import annotations

import datetime
import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.main_bot import keyboards, texts
from app.bots.main_bot.handlers.owner_common import require_sales_mode, require_sales_mode_cb
from app.bots.main_bot.states import CampaignWizardStates, CustomerBroadcastStates
from app.database.models import Campaign, CampaignDiscountType, ShopBot
from app.services import campaign_service, customer_service, shop_bot_service, shop_owner_service
from app.utils.validators import fa_text, parse_price_toman

logger = logging.getLogger(__name__)

router = Router(name="campaigns")


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _parse_positive_int(raw: str) -> int | None:
    """عددِ صحیحِ مثبت از متنِ فروشگاه‌دار (رقمِ فارسی/انگلیسی، جداکننده‌ی هزارگان کاما/«،»/«٬»)."""
    return parse_price_toman((raw or "").replace("\u066c", ""))


async def _require_shop_bot(message: Message, session: AsyncSession) -> ShopBot | None:
    owner = await shop_owner_service.get_by_telegram_id(session, message.from_user.id)
    shop_bot = await shop_bot_service.get_by_owner(session, owner) if owner else None
    if shop_bot is None:
        await message.answer(texts.SHOP_BOT_NOT_SET_UP)
        return None
    return shop_bot


async def _require_shop_bot_cb(callback: CallbackQuery, session: AsyncSession) -> ShopBot | None:
    owner = await shop_owner_service.get_by_telegram_id(session, callback.from_user.id)
    shop_bot = await shop_bot_service.get_by_owner(session, owner) if owner else None
    if shop_bot is None:
        await callback.answer(texts.SHOP_BOT_NOT_SET_UP, show_alert=True)
        return None
    return shop_bot


async def _safe_edit(callback: CallbackQuery, text: str, reply_markup=None) -> None:
    """edit_text ـی که «message is not modified» رو بی‌صدا نادیده می‌گیره (دابل‌تپ)."""
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            raise


async def _owned_campaign_or_alert(
    callback: CallbackQuery, session: AsyncSession, shop_bot: ShopBot, prefix: str
) -> Campaign | None:
    """شناسه‌ی کمپین از callback_data میاد (قابلِ دستکاری)، پس مالکیت حتماً چک می‌شه —
    یه فروشگاه‌دار با حدس‌زدنِ شناسه نمی‌تونه کمپینِ فروشگاهِ دیگه‌ای رو ببینه/عوض کنه."""
    try:
        campaign_id = int(callback.data[len(prefix) :])
    except ValueError:
        campaign_id = None
    campaign = await campaign_service.get_owned(session, campaign_id, shop_bot.id) if campaign_id is not None else None
    if campaign is None:
        await callback.answer(texts.CAMPAIGN_NOT_FOUND, show_alert=True)
        return None
    return campaign


async def _list_payload(session: AsyncSession, shop_bot: ShopBot):
    campaigns = await campaign_service.list_for_shop(session, shop_bot.id)
    if not campaigns:
        return texts.CAMPAIGNS_EMPTY, keyboards.campaigns_list_keyboard([])
    now = _now()
    items = [(c, campaign_service.campaign_status(c, now)) for c in campaigns]
    intro = texts.CAMPAIGNS_LIST_INTRO
    if len(campaigns) >= campaign_service.LIST_LIMIT:
        intro += "\n" + fa_text(texts.CAMPAIGNS_LIST_TRUNCATED, limit=campaign_service.LIST_LIMIT)
    return intro, keyboards.campaigns_list_keyboard(items)


async def _detail_payload(session: AsyncSession, campaign: Campaign):
    uses, discount_total = await campaign_service.usage_stats(session, campaign.id)
    status = campaign_service.campaign_status(campaign, _now())
    return texts.campaign_detail_text(campaign, status, uses, discount_total), keyboards.campaign_detail_keyboard(campaign, status)


# =============================================================================
# فهرست / جزئیات / توقف / حذف / اعلام
# =============================================================================
@router.message(F.text == "🎯 کمپین‌ها")
async def open_campaigns(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    shop_bot = await _require_shop_bot(message, session)
    if shop_bot is None:
        return
    if not await require_sales_mode(message, shop_bot):
        return
    text, keyboard = await _list_payload(session, shop_bot)
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data == "campaign_list")
async def campaign_back_to_list(callback: CallbackQuery, session: AsyncSession) -> None:
    shop_bot = await _require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    text, keyboard = await _list_payload(session, shop_bot)
    await callback.answer()
    await _safe_edit(callback, text, keyboard)


@router.callback_query(F.data.startswith("campaign_view:"))
async def campaign_view(callback: CallbackQuery, session: AsyncSession) -> None:
    shop_bot = await _require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    campaign = await _owned_campaign_or_alert(callback, session, shop_bot, "campaign_view:")
    if campaign is None:
        return
    text, keyboard = await _detail_payload(session, campaign)
    await callback.answer()
    await _safe_edit(callback, text, keyboard)


@router.callback_query(F.data.startswith("campaign_toggle:"))
async def campaign_toggle(callback: CallbackQuery, session: AsyncSession) -> None:
    shop_bot = await _require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    campaign = await _owned_campaign_or_alert(callback, session, shop_bot, "campaign_toggle:")
    if campaign is None:
        return
    if campaign_service.campaign_status(campaign, _now()) == "ended":
        await callback.answer(texts.CAMPAIGN_ALREADY_ENDED, show_alert=True)
        return

    await campaign_service.set_active(session, campaign, not campaign.is_active)
    text, keyboard = await _detail_payload(session, campaign)
    await callback.answer(texts.CAMPAIGN_RESUMED_TOAST if campaign.is_active else texts.CAMPAIGN_PAUSED_TOAST)
    await _safe_edit(callback, text, keyboard)


@router.callback_query(F.data.startswith("campaign_delete:"))
async def campaign_delete(callback: CallbackQuery, session: AsyncSession) -> None:
    shop_bot = await _require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    campaign = await _owned_campaign_or_alert(callback, session, shop_bot, "campaign_delete:")
    if campaign is None:
        return
    if not await campaign_service.delete_if_unused(session, campaign):
        await callback.answer(texts.CAMPAIGN_CANNOT_DELETE_USED, show_alert=True)
        return

    text, keyboard = await _list_payload(session, shop_bot)
    await callback.answer(texts.CAMPAIGN_DELETED_TOAST)
    await _safe_edit(callback, text, keyboard)


@router.callback_query(F.data.startswith("campaign_announce:"))
async def campaign_announce(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    shop_bot = await _require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    campaign = await _owned_campaign_or_alert(callback, session, shop_bot, "campaign_announce:")
    if campaign is None:
        return
    if campaign_service.campaign_status(campaign, _now()) != "active":
        await callback.answer(texts.CAMPAIGN_ANNOUNCE_ONLY_ACTIVE, show_alert=True)
        return
    customer_count = await customer_service.count_by_shop_bot(session, shop_bot.id)
    if customer_count == 0:
        await callback.answer(texts.CUSTOMER_BROADCAST_NO_CUSTOMERS, show_alert=True)
        return

    # متنِ آماده رو توی FSMِ «پیام به مشتری‌ها» می‌ذاریم؛ دکمه‌هایِ تایید/لغوِ همون سیستم
    # (panel.py) ارسال رو انجام می‌دن. فروشگاه‌دار می‌تونه با /cancel لغو کنه و متنِ
    # دلخواهش رو از «📣 پیام به مشتری‌ها» بفرسته.
    announcement = texts.campaign_announcement_text(campaign)
    await state.set_state(CustomerBroadcastStates.waiting_confirmation)
    await state.update_data(broadcast_text=announcement)
    await callback.answer()
    await callback.message.answer(
        texts.customer_broadcast_preview(announcement, customer_count),
        reply_markup=keyboards.confirm_customer_broadcast_keyboard(),
    )


# =============================================================================
# ویزاردِ ساختِ کمپین
# =============================================================================
@router.callback_query(F.data == "campaign_new")
async def campaign_new(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    shop_bot = await _require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    if not await require_sales_mode_cb(callback, shop_bot):
        return
    await state.clear()
    await state.set_state(CampaignWizardStates.waiting_name)
    await callback.answer()
    await callback.message.answer(texts.CAMPAIGN_ASK_NAME)


@router.message(CampaignWizardStates.waiting_name, F.text)
async def wizard_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if not name or len(name) > campaign_service.MAX_NAME_LENGTH:
        await message.answer(texts.CAMPAIGN_NAME_INVALID)
        return
    await state.update_data(name=name)
    await state.set_state(CampaignWizardStates.waiting_type)
    await message.answer(texts.CAMPAIGN_ASK_TYPE, reply_markup=keyboards.campaign_type_keyboard())


@router.callback_query(CampaignWizardStates.waiting_type, F.data.startswith("campaign_type:"))
async def wizard_type(callback: CallbackQuery, state: FSMContext) -> None:
    kind = callback.data.split(":", 1)[1]
    if kind not in (CampaignDiscountType.PERCENT.value, CampaignDiscountType.FIXED.value):
        await callback.answer()
        return
    await state.update_data(discount_type=kind)
    await state.set_state(CampaignWizardStates.waiting_value)
    await callback.answer()
    prompt = texts.CAMPAIGN_ASK_PERCENT if kind == CampaignDiscountType.PERCENT.value else texts.CAMPAIGN_ASK_FIXED
    await callback.message.answer(prompt)


@router.message(CampaignWizardStates.waiting_value, F.text)
async def wizard_value(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    kind = data["discount_type"]
    value = _parse_positive_int(message.text or "")
    if kind == CampaignDiscountType.PERCENT.value:
        if value is None or not (1 <= value <= 100):
            await message.answer(texts.CAMPAIGN_PERCENT_INVALID)
            return
    elif value is None or value > campaign_service.MAX_TOMAN_VALUE:
        await message.answer(texts.CAMPAIGN_AMOUNT_INVALID)
        return

    await state.update_data(discount_value=value)
    if kind == CampaignDiscountType.PERCENT.value:
        await state.set_state(CampaignWizardStates.waiting_max_discount)
        await message.answer(
            texts.CAMPAIGN_ASK_MAX_DISCOUNT, reply_markup=keyboards.campaign_skip_keyboard("♾ بدونِ سقف", "campaign_skip_max")
        )
    else:
        await _ask_code_choice(message, state)


async def _ask_code_choice(message: Message, state: FSMContext) -> None:
    await state.set_state(CampaignWizardStates.waiting_code_choice)
    await message.answer(texts.CAMPAIGN_ASK_CODE_CHOICE, reply_markup=keyboards.campaign_code_choice_keyboard())


@router.message(CampaignWizardStates.waiting_max_discount, F.text)
async def wizard_max_discount(message: Message, state: FSMContext) -> None:
    value = _parse_positive_int(message.text or "")
    if value is None or value > campaign_service.MAX_TOMAN_VALUE:
        await message.answer(texts.CAMPAIGN_AMOUNT_INVALID)
        return
    await state.update_data(max_discount_toman=value)
    await _ask_code_choice(message, state)


@router.callback_query(CampaignWizardStates.waiting_max_discount, F.data == "campaign_skip_max")
async def wizard_skip_max_discount(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(max_discount_toman=None)
    await callback.answer()
    await _ask_code_choice(callback.message, state)


@router.callback_query(CampaignWizardStates.waiting_code_choice, F.data.startswith("campaign_code_choice:"))
async def wizard_code_choice(callback: CallbackQuery, state: FSMContext) -> None:
    choice = callback.data.split(":", 1)[1]
    await callback.answer()
    if choice == "code":
        await state.set_state(CampaignWizardStates.waiting_code)
        await callback.message.answer(texts.CAMPAIGN_ASK_CODE)
    elif choice == "auto":
        await state.update_data(code=None)
        await _ask_min_cart(callback.message, state)


@router.message(CampaignWizardStates.waiting_code, F.text)
async def wizard_code(message: Message, state: FSMContext, session: AsyncSession) -> None:
    shop_bot = await _require_shop_bot(message, session)
    if shop_bot is None:
        await state.clear()
        return
    code = campaign_service.normalize_code(message.text)
    if not campaign_service.is_valid_code(code):
        await message.answer(texts.CAMPAIGN_CODE_INVALID)
        return
    if await campaign_service.get_by_code(session, shop_bot.id, code) is not None:
        await message.answer(texts.CAMPAIGN_CODE_TAKEN)
        return
    await state.update_data(code=code)
    await _ask_min_cart(message, state)


async def _ask_min_cart(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await state.set_state(CampaignWizardStates.waiting_min_cart)
    if data["discount_type"] == CampaignDiscountType.FIXED.value:
        # مبلغ‌ثابت: حداقلِ سبد اجباریه (دکمه‌ی «ندارد» نداره).
        await message.answer(texts.campaign_ask_min_cart_fixed(data["discount_value"]))
    else:
        await message.answer(
            texts.CAMPAIGN_ASK_MIN_CART, reply_markup=keyboards.campaign_skip_keyboard("ندارد", "campaign_skip_min_cart")
        )


@router.message(CampaignWizardStates.waiting_min_cart, F.text)
async def wizard_min_cart(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    value = _parse_positive_int(message.text or "")
    if value is None or value > campaign_service.MAX_TOMAN_VALUE:
        await message.answer(texts.CAMPAIGN_AMOUNT_INVALID)
        return
    if data["discount_type"] == CampaignDiscountType.FIXED.value and value <= data["discount_value"]:
        await message.answer(texts.campaign_min_cart_too_low(data["discount_value"]))
        return
    await state.update_data(min_cart_total_toman=value)
    await _ask_duration(message, state)


@router.callback_query(CampaignWizardStates.waiting_min_cart, F.data == "campaign_skip_min_cart")
async def wizard_skip_min_cart(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    if data.get("discount_type") == CampaignDiscountType.FIXED.value:
        # دکمه برایِ مبلغ‌ثابت نشون داده نمی‌شه؛ این فقط دفاعِ دومه (callback دستکاری‌شده).
        await callback.answer(texts.campaign_ask_min_cart_fixed(data["discount_value"]), show_alert=True)
        return
    await state.update_data(min_cart_total_toman=None)
    await callback.answer()
    await _ask_duration(callback.message, state)


async def _ask_duration(message: Message, state: FSMContext) -> None:
    await state.set_state(CampaignWizardStates.waiting_duration)
    await message.answer(texts.CAMPAIGN_ASK_DURATION, reply_markup=keyboards.campaign_duration_keyboard())


async def _set_duration_and_continue(message: Message, state: FSMContext, days: int) -> None:
    await state.update_data(duration_days=days)
    await state.set_state(CampaignWizardStates.waiting_total_limit)
    await message.answer(
        texts.CAMPAIGN_ASK_TOTAL_LIMIT, reply_markup=keyboards.campaign_skip_keyboard("♾ نامحدود", "campaign_skip_total_limit")
    )


@router.callback_query(CampaignWizardStates.waiting_duration, F.data.startswith("campaign_duration:"))
async def wizard_duration_button(callback: CallbackQuery, state: FSMContext) -> None:
    try:
        days = int(callback.data.split(":", 1)[1])
    except ValueError:
        days = 0
    if not (1 <= days <= campaign_service.MAX_DURATION_DAYS):
        await callback.answer()
        return
    await callback.answer()
    await _set_duration_and_continue(callback.message, state, days)


@router.message(CampaignWizardStates.waiting_duration, F.text)
async def wizard_duration_text(message: Message, state: FSMContext) -> None:
    days = _parse_positive_int(message.text or "")
    if days is None or not (1 <= days <= campaign_service.MAX_DURATION_DAYS):
        await message.answer(texts.CAMPAIGN_DURATION_INVALID)
        return
    await _set_duration_and_continue(message, state, days)


async def _ask_per_customer(message: Message, state: FSMContext) -> None:
    await state.set_state(CampaignWizardStates.waiting_per_customer_limit)
    await message.answer(texts.CAMPAIGN_ASK_PER_CUSTOMER, reply_markup=keyboards.campaign_per_customer_keyboard())


@router.message(CampaignWizardStates.waiting_total_limit, F.text)
async def wizard_total_limit(message: Message, state: FSMContext) -> None:
    value = _parse_positive_int(message.text or "")
    if value is None or value > campaign_service.MAX_LIMIT_VALUE:
        await message.answer(texts.CAMPAIGN_LIMIT_INVALID)
        return
    await state.update_data(total_usage_limit=value)
    await _ask_per_customer(message, state)


@router.callback_query(CampaignWizardStates.waiting_total_limit, F.data == "campaign_skip_total_limit")
async def wizard_skip_total_limit(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(total_usage_limit=None)
    await callback.answer()
    await _ask_per_customer(callback.message, state)


@router.callback_query(CampaignWizardStates.waiting_per_customer_limit, F.data.startswith("campaign_percustomer:"))
async def wizard_per_customer(callback: CallbackQuery, state: FSMContext) -> None:
    try:
        count = int(callback.data.split(":", 1)[1])
    except ValueError:
        count = -1
    if count not in (0, 1, 2, 3):
        await callback.answer()
        return
    await state.update_data(per_customer_limit=count or None)  # ۰ = نامحدود
    await state.set_state(CampaignWizardStates.waiting_confirmation)
    data = await state.get_data()
    await callback.answer()
    await callback.message.answer(texts.campaign_wizard_summary(data, _now()), reply_markup=keyboards.campaign_confirm_keyboard())


@router.callback_query(CampaignWizardStates.waiting_confirmation, F.data == "campaign_create_confirm")
async def wizard_confirm(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    # clear عمداً همین اولِ کاره (قبلِ هر I/O): دابل‌تپ، آپدیتِ دوم رو با فیلترِ state رد می‌کنه
    # و دو کمپینِ تکراری ساخته نمی‌شه.
    await state.clear()
    shop_bot = await _require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return

    try:
        campaign = await campaign_service.create_campaign(
            session,
            shop_bot.id,
            name=data["name"],
            discount_type=CampaignDiscountType(data["discount_type"]),
            discount_value=data["discount_value"],
            duration_days=data["duration_days"],
            max_discount_toman=data.get("max_discount_toman"),
            min_cart_total_toman=data.get("min_cart_total_toman"),
            code=data.get("code"),
            total_usage_limit=data.get("total_usage_limit"),
            per_customer_limit=data.get("per_customer_limit"),
        )
    except campaign_service.CampaignError as exc:
        await callback.answer()
        await _safe_edit(callback, texts.campaign_create_error(exc.code))
        return

    await callback.answer()
    await _safe_edit(callback, texts.campaign_created(campaign, _now()), keyboards.campaign_created_keyboard(campaign.id))


@router.callback_query(CampaignWizardStates.waiting_confirmation, F.data == "campaign_create_cancel")
async def wizard_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await _safe_edit(callback, texts.CAMPAIGN_CREATE_CANCELLED)


@router.message(
    StateFilter(
        CampaignWizardStates.waiting_type,
        CampaignWizardStates.waiting_code_choice,
        CampaignWizardStates.waiting_per_customer_limit,
        CampaignWizardStates.waiting_confirmation,
    ),
    F.text,
)
async def wizard_use_buttons(message: Message) -> None:
    await message.answer(texts.CAMPAIGN_USE_BUTTONS)


# دکمه‌هایِ ویزاردِ کهنه (state عوض شده/پاک شده): بدونِ این هندلر دکمه فقط بی‌صدا می‌چرخه.
# این هندلر *آخر* ثبت می‌شه تا هندلرهایِ state-دارِ بالا همیشه اولویت داشته باشن.
@router.callback_query(
    F.data.startswith(
        (
            "campaign_type:",
            "campaign_code_choice:",
            "campaign_duration:",
            "campaign_percustomer:",
            "campaign_skip_",
            "campaign_create_",
        )
    )
)
async def wizard_stale_button(callback: CallbackQuery) -> None:
    await callback.answer(texts.CAMPAIGN_WIZARD_STALE, show_alert=True)
