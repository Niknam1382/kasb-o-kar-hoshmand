"""متن/کیبوردِ «پیشنهادِ ویرایشِ سبد با AI» (W5 · C2). callback_data: cart_ai_apply:<id>، cart_ai_reject:<id>."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.utils.validators import fa_number

PROPOSAL_INTRO = "می‌خوای این تغییرها رو توی سبدت انجام بدم؟"
PROPOSAL_FOOTER = "⏱ این پیشنهاد تا ۱۰ دقیقه معتبره."
PROPOSAL_REJECTED = "باشه، سبدت دست‌نخورده موند 🙂"
PROPOSAL_STALE = "سبدت از لحظه‌یِ این پیشنهاد عوض شده؛ چیزی تغییر نکرد. دوباره بگو چی می‌خوای."
PROPOSAL_EXPIRED = "این پیشنهاد منقضی شده؛ چیزی تغییر نکرد. دوباره بگو چی می‌خوای."
PROPOSAL_ALREADY = "این پیشنهاد قبلاً بررسی شده."
PROPOSAL_GONE = "این پیشنهاد دیگه وجود نداره."


def proposal_text(lines: list[str], rejected_count: int = 0) -> str:
    parts = [PROPOSAL_INTRO, ""] + lines
    if rejected_count:
        parts.append(f"\n⚠️ {fa_number(rejected_count)} مورد از درخواستت رو متوجه نشدم؛ اگه لازمه دوباره و واضح‌تر بگو.")
    parts.append(f"\n{PROPOSAL_FOOTER}")
    return "\n".join(parts)


def proposal_keyboard(proposal_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ اعمال", callback_data=f"cart_ai_apply:{proposal_id}"),
                InlineKeyboardButton(text="❌ نه", callback_data=f"cart_ai_reject:{proposal_id}"),
            ]
        ]
    )
