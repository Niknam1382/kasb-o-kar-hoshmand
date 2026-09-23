from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    waiting_first_name = State()
    waiting_last_name = State()
    waiting_phone = State()
    waiting_phone_otp = State()
    waiting_email = State()
    waiting_email_otp = State()


class ShopBotTokenStates(StatesGroup):
    waiting_token = State()


class ProductStates(StatesGroup):
    waiting_name = State()
    waiting_description = State()
    waiting_price = State()
    waiting_photo = State()
    waiting_stock = State()
    waiting_edit_field_value = State()


class ProductImportStates(StatesGroup):
    waiting_file = State()
    waiting_confirmation = State()


class AiInstructionsStates(StatesGroup):
    waiting_instructions = State()


class PreviewStates(StatesGroup):
    active = State()


class ChannelKnowledgeStates(StatesGroup):
    waiting_channel_proof = State()


class PaymentStates(StatesGroup):
    waiting_discount_code = State()
    waiting_receipt = State()
    waiting_topup_amount = State()


class BroadcastStates(StatesGroup):
    waiting_message = State()
    waiting_confirmation = State()


class AdminChannelStates(StatesGroup):
    waiting_name = State()
    waiting_channel_proof = State()
    waiting_is_primary = State()


class AdminPricingStates(StatesGroup):
    waiting_plan_duration = State()
    waiting_plan_price = State()
    waiting_discount_code = State()
    waiting_discount_type = State()
    waiting_discount_value = State()
    waiting_discount_max_uses = State()


class AdminSettingsStates(StatesGroup):
    waiting_value = State()
    waiting_referral_amount = State()
    waiting_rate_limit_max = State()
    waiting_rate_limit_window = State()


class AdminGiftStates(StatesGroup):
    waiting_amount = State()


class AdminWalletCorrectionStates(StatesGroup):
    waiting_amount = State()
    waiting_reason = State()


class ModerationStates(StatesGroup):
    waiting_pattern = State()


class AiPoolStates(StatesGroup):
    waiting_entry_details = State()


class AdminRoleStates(StatesGroup):
    waiting_telegram_id = State()
