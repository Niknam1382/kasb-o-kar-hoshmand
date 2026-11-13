"""پیکربندیِ گام‌هایِ پیش‌فرضِ چک‌اوت (P18 · B9) — per-shop، منطقِ خالصِ JSON بدونِ I/O.

هفت گامِ چک‌اوت — پنج گامِ اصلی (نام، موبایل، آدرس، ارسال، توضیح) و دو زیرگامِ «آدرس»
(استان، شهر) — روشن/خاموش و متنِ پرسششان قابلِ ویرایش است.
سوالاتِ سفارشیِ فروشگاه‌دار (`ShopBot.checkout_questions`) مسیرِ جداگانه‌یِ خودش را دارد و دست‌نخورده
مانده. همه‌چیز در یک ستونِ متنیِ `ShopBot.checkout_config` ذخیره می‌شود:

* `None`/خالی ⇒ پیش‌فرض‌هایِ همین فایل ⇒ پنج گامِ اصلی روشن، استان و شهر خاموش.
* پ۶۸: `province` و `city` دو زیرگامِ «آدرس»‌اند؛ پیش‌فرض «نپرس» است و فروشگاه‌دار از همان
  صفحه روشنشان می‌کند. پیش‌فرضِ خاموش با ستونِ خالی یکی است ⇒ `dump` همان `None` را می‌نویسد
  و هیچ مهاجرتِ داده‌ای لازم نیست.
* JSON خراب، کلیدِ ناشناخته، یا متنِ بلند ⇒ بی‌صدا به پیش‌فرضِ همان گام برمی‌گردد (هرگز کرش نمی‌کند).

قاعده‌یِ ایمنی: «آدرس» و «موبایل» هیچ‌وقت با هم خاموش نمی‌شوند؛ سفارشِ فیزیکی باید راهی برایِ تحویل داشته باشد.
"""
from __future__ import annotations

import dataclasses
import json

from app.bots.shop_bot import checkout_ui

STEP_KEYS = ("name", "phone", "address", "province", "city", "shipping", "note")
# پ۶۸ (موردِ ۱۹): «استان» و «شهر» پیش‌فرض خاموش‌اند ⇒ ستونِ خالی یعنی «نپرس»، نه «بپرس».
DEFAULT_ENABLED = dict.fromkeys(STEP_KEYS, True) | {"province": False, "city": False}
MAX_QUESTION_LENGTH = 150
# گامِ «آدرس» در چک‌اوت ماکرو است و چند زیرمرحله دارد؛ در `checkout_flow` با کلیدِ «addr» شناخته می‌شود.
STEP_TO_POSITION = {"name": "name", "phone": "phone", "address": "addr", "province": "prov", "city": "city",
                    "shipping": "ship", "note": "note"}
# متنِ پرسشی که متنِ فروشگاه‌دار جایگزینش می‌شود (بقیه‌یِ متن‌ها — از جمله پیام‌هایِ خطا — ثابت می‌مانند).
DEFAULT_QUESTIONS = {
    "name": checkout_ui.ASK_NAME_PLAIN,
    "phone": checkout_ui.ASK_PHONE,
    "address": checkout_ui.ASK_ADDRESS_TEXT,
    "province": checkout_ui.ASK_PROVINCE,
    "city": checkout_ui.ASK_CITY,
    "shipping": checkout_ui.ASK_SHIPPING,
    "note": checkout_ui.ASK_NOTE,
}


@dataclasses.dataclass(frozen=True)
class CheckoutStep:
    key: str
    enabled: bool
    question: str


def parse(raw: str | None) -> dict[str, CheckoutStep]:
    """`ShopBot.checkout_config` ⇒ نگاشتِ کاملِ هفت گام. مقدارِ نامعتبر ⇒ پیش‌فرض، بدونِ استثناء."""
    steps = {key: CheckoutStep(key, DEFAULT_ENABLED[key], DEFAULT_QUESTIONS[key]) for key in STEP_KEYS}
    if not raw:
        return steps
    try:
        loaded = json.loads(raw)
    except (ValueError, TypeError):
        return steps
    if not isinstance(loaded, dict):
        return steps
    for key in STEP_KEYS:
        entry = loaded.get(key)
        if not isinstance(entry, dict):
            continue
        question = str(entry.get("q") or "").strip()[:MAX_QUESTION_LENGTH]
        steps[key] = CheckoutStep(
            key, bool(entry.get("on", DEFAULT_ENABLED[key])), question or DEFAULT_QUESTIONS[key]
        )
    return steps


def dump(steps: dict[str, CheckoutStep]) -> str | None:
    """همه‌چیز پیش‌فرض ⇒ None (ستونِ خالی). وگرنه JSONِ فشرده با کلیدهایِ کوتاه."""
    if all(
        step.enabled == DEFAULT_ENABLED[step.key] and step.question == DEFAULT_QUESTIONS[step.key]
        for step in steps.values()
    ):
        return None
    return json.dumps(
        {key: {"on": step.enabled, "q": step.question} for key, step in steps.items()},
        ensure_ascii=False,
        separators=(",", ":"),
    )


def disabled_positions(steps: dict[str, CheckoutStep]) -> frozenset[str]:
    return frozenset(STEP_TO_POSITION[key] for key, step in steps.items() if not step.enabled)


def questions(steps: dict[str, CheckoutStep]) -> dict[str, str]:
    return {key: step.question for key, step in steps.items()}


def set_enabled(steps: dict[str, CheckoutStep], key: str, enabled: bool) -> dict[str, CheckoutStep] | None:
    """None وقتی کلید مجهول است یا خاموش‌کردنِ همزمانِ آدرس و موبایل نتیجه می‌دهد (قاعده‌یِ ایمنی)."""
    step = steps.get(key)
    if step is None:
        return None
    candidate = {**steps, key: dataclasses.replace(step, enabled=enabled)}
    if not candidate["address"].enabled and not candidate["phone"].enabled:
        return None
    return candidate


def set_question(steps: dict[str, CheckoutStep], key: str, text: str | None) -> dict[str, CheckoutStep] | None:
    """متنِ خالی/«خالی» ⇒ برگشت به متنِ پیش‌فرض. بلندتر از ۱۵۰ نویسه ⇒ None (فروشگاه‌دار باید کوتاه‌تر کند)."""
    if key not in steps:
        return None
    raw = (text or "").strip()
    if not raw or raw in {"خالی", "بدونِ متن", "پیش‌فرض"}:
        return {**steps, key: dataclasses.replace(steps[key], question=DEFAULT_QUESTIONS[key])}
    if len(raw) > MAX_QUESTION_LENGTH:
        return None
    return {**steps, key: dataclasses.replace(steps[key], question=raw)}


def summary(steps: dict[str, CheckoutStep]) -> list[str]:
    """خط‌هایِ «وضعیتِ فعلی» برایِ صفحه‌یِ تنظیمات."""
    lines = []
    for key in STEP_KEYS:
        step = steps[key]
        state = "روشن" if step.enabled else "خاموش"
        custom = "" if step.question == DEFAULT_QUESTIONS[key] else " — متنِ خودت"
        lines.append(f"• {key}: {state}{custom}")
    return lines
