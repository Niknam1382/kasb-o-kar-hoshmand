"""منطقِ خالصِ چک‌اوتِ مرحله‌ایِ سبد (W5 · C3). بدونِ I/O و بدونِ aiogram/SQLAlchemy ⇒ در sandbox قابلِ اجراست.

موقعیت‌ها (position) رشته‌اند: name، phone، addr_pick، prov، city، addr_text، postal، ship، qa، note، preview."""

from __future__ import annotations

from typing import Callable, Iterable

POS_NAME = "name"
POS_PHONE = "phone"
POS_ADDR_PICK = "addr_pick"
POS_PROV = "prov"
POS_CITY = "city"
POS_ADDR_TEXT = "addr_text"
POS_POSTAL = "postal"
POS_SHIP = "ship"
POS_QA = "qa"
POS_NOTE = "note"
POS_PREVIEW = "preview"

_ADDRESS_POSITIONS = {POS_ADDR_PICK, POS_PROV, POS_CITY, POS_ADDR_TEXT, POS_POSTAL}

MAX_CUSTOM_QUESTIONS = 10
MAX_NOTE_LENGTH = 300
MAX_ANSWER_LENGTH = 300


def custom_questions(raw: str | None) -> list[str]:
    """سوال‌هایِ سفارشیِ فروشگاه‌دار (هر خط یکی). بدونِ پیش‌فرض: نام/موبایل/آدرس مرحله‌یِ جدا دارن."""
    if not raw or not raw.strip():
        return []
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    return lines[:MAX_CUSTOM_QUESTIONS]


def is_physical_cart(items, is_digital: Callable) -> bool:
    """items: [(CartItem, Product)] — اگه حتی یک کالایِ غیرِدیجیتال باشه، آدرس/ارسال لازمه."""
    return any(not is_digital(product) for _item, product in items)


def physical_subtotal(items, is_digital: Callable) -> int:
    """جمعِ قیمتِ کالاهایِ فیزیکیِ سبد (قبل از تخفیف) — مبنای «ارسالِ رایگان بالایِ X»."""
    return sum(product.price_toman * item.quantity for item, product in items if not is_digital(product))


def shipping_fee(fee_toman: int, free_over_toman: int | None, subtotal_toman: int) -> int:
    """هزینه‌یِ ارسال؛ بالاتر/برابرِ آستانه رایگان. (همان قاعده‌یِ shipping_service.fee_for_subtotal)."""
    if free_over_toman is not None and subtotal_toman >= free_over_toman:
        return 0
    return max(0, fee_toman)


def step_order(*, physical: bool, ship_choice: bool = False, has_questions: bool = False, disabled: frozenset[str] = frozenset()) -> list[str]:
    """ترتیبِ گام‌هایِ روشنِ همین سبد (ماکرو؛ «addr» و «ship» هم ممکن است حذف شوند). پیش‌نمایش همیشه هست."""
    order: list[str] = []
    if POS_NAME not in disabled:
        order.append(POS_NAME)
    if POS_PHONE not in disabled:
        order.append(POS_PHONE)
    if physical and "addr" not in disabled:
        order.append("addr")
    if physical and ship_choice and POS_SHIP not in disabled:
        order.append(POS_SHIP)
    if has_questions:
        order.append(POS_QA)
    if POS_NOTE not in disabled:
        order.append(POS_NOTE)
    return order


def next_position(
    pos: str, *, physical: bool, ship_choice: bool, has_questions: bool, disabled: frozenset[str] = frozenset()
) -> str:
    """موقعیتِ بعدی (ماکرو). زیرمرحله‌هایِ آدرس همه به «addr» نگاشت می‌شن ⇒ بعدش ship/qa/note.

    B9: `disabled` کلیدهایِ گامِ خاموشِ همان فروشگاه است. خالی ⇒ دقیقاً رفتارِ قبلی.
    """
    order = step_order(physical=physical, ship_choice=ship_choice, has_questions=has_questions, disabled=disabled)
    order.append(POS_PREVIEW)
    key = "addr" if pos in _ADDRESS_POSITIONS else pos
    if key not in order:
        return POS_PREVIEW
    idx = order.index(key)
    nxt = order[idx + 1] if idx + 1 < len(order) else POS_PREVIEW
    return POS_ADDR_PICK if nxt == "addr" else nxt


def first_position(*, physical: bool = False, ship_choice: bool = False, has_questions: bool = False, disabled: frozenset[str] = frozenset()) -> str:
    """اولین گامِ روشن؛ اگر همه خاموش باشند مستقیم پیش‌نمایش."""
    order = step_order(physical=physical, ship_choice=ship_choice, has_questions=has_questions, disabled=disabled)
    if not order:
        return POS_PREVIEW
    nxt = order[0]
    return POS_ADDR_PICK if nxt == "addr" else nxt


def push_history(stack: Iterable[str], pos: str | None) -> list[str]:
    """pos (موقعیتِ فعلی) رو به تاریخچه اضافه می‌کنه؛ تکرارِ پشتِ‌هم‌ِ یکسان ثبت نمی‌شه."""
    out = list(stack)
    if pos and (not out or out[-1] != pos):
        out.append(pos)
    return out


def pop_history(stack: Iterable[str]) -> tuple[str | None, list[str]]:
    """(موقعیتِ قبلی یا None, تاریخچه‌یِ جدید)."""
    out = list(stack)
    if not out:
        return None, out
    return out.pop(), out


def build_qa_pairs(
    *,
    name: str,
    phone_display: str,
    address_text: str | None,
    ship_label: str | None,
    questions: list[str],
    answers: list[str],
    note: str | None,
    disabled: frozenset[str] = frozenset(),
) -> list[tuple[str, str]]:
    """جفت‌هایِ «پرسش ← پاسخ» که در پیش‌نمایش، اعلانِ فروشگاه‌دار و checkout_answers می‌آیند.

    B9: گامِ خاموش در جفت‌ها ظاهر نمی‌شود (برچسب‌ها ثابت‌اند؛ چیزی که فروشگاه‌دار ویرایش می‌کند
    *متنِ پرسش از مشتری* است، نه این برچسب‌هایِ داخلیِ سفارش).
    """
    pairs: list[tuple[str, str]] = []
    if POS_NAME not in disabled:
        pairs.append(("نامِ تحویل‌گیرنده", name))
    if POS_PHONE not in disabled:
        pairs.append(("شماره‌یِ تماس", phone_display))
    if address_text and "addr" not in disabled:
        pairs.append(("آدرسِ تحویل", address_text))
    if ship_label and POS_SHIP not in disabled:
        pairs.append(("روشِ ارسال", ship_label))
    pairs.extend(zip(questions, answers))
    if note and POS_NOTE not in disabled:
        pairs.append(("توضیحِ سفارش", note))
    return pairs
