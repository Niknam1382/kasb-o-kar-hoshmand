"""
تست: P43 · نگهبانِ محتوا — دقت، گزارشِ قابلِ فهم و بلاکِ واقعی (مواردِ ۳۰، ۳۱، ۱۰)

۱. دقت (۳۰): قانونِ «خر» دیگر «آخرین/خرید/خبر» را نمی‌گیرد، ولی «خر»ِ تنها و عبارتِ دوکلمه‌ای
   (با ی/ك عربی و فاصله‌هایِ اضافه) را می‌گیرد — همان تطبیقِ غلط که گزارشِ بی‌دلیل می‌ساخت.
۲. دامنه (۳۰): قانونِ خودِ فروشگاه فقط در همان فروشگاه اجرا می‌شود؛ قانونِ سراسری همه‌جا.
۳. end-to-end: WARN ⇒ AI جواب می‌دهد + یکِ ردیفِ `moderation_reports` (کلمه، اکشن، دامنه،
   بریدهٔ پیام، مشتری) + ممیزی؛ BLOCK ⇒ بدونِ AI و با `Customer.is_blocked = True` (موردِ ۳۱).
۴. صفحه‌ها (۱۰): «🛡 نگهبانِ محتوا» در *هر دو* پنل و چینشِ دونفرهٔ منو نشکستن؛ کارتِ گزارش
   دکمه‌هایِ «گفتگو» (همان صفحهٔ CRM)، «مشخصاتِ کاربر»، «بلاک/رفعِ بلاک» و «بررسی شد» را دارد؛
   گزارشِ بسته‌شده از فهرستِ «باز» می‌رود؛ بیرونِ دامنه باز نمی‌شود؛ فهرستِ ادمین برایِ کاربرِ
   عادی کار نمی‌کند.

اجرا: python3 tests_manual/run_one.py test_p43_moderation_reports.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402
from sqlalchemy import select  # noqa: E402

from harness import FakeSession, build_test_dispatchers, make_message_update, reset_database  # noqa: E402
from phase4_helpers import Chat  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot import keyboards, texts as main_texts  # noqa: E402
from app.config import settings  # noqa: E402
from app.database.models import AuditEventType, Customer, ModerationReport, ModerationRule  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import ai_service, moderation_service  # noqa: E402
from app.services.ai_service import AiCallResult  # noqa: E402

OWNER_TG_ID = 7_443_000_001
OTHER_OWNER_TG_ID = 7_443_000_002
SHOP_BOT_TG_ID = 7_443_000_003
OTHER_SHOP_BOT_TG_ID = 7_443_000_004
CUSTOMER_TG_ID = 7_443_000_005
DEBOUNCE_WAIT = 4.5  # پنجره‌یِ debounceِ پیش‌فرض ۳٫۰ ثانیه است


class _FakeAi:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def get_reply(self, system_prompt, history, user_message) -> AiCallResult:
        # «تحلیلِ گفتگو» (دعوتِ دومِ همان پیام، برایِ یادگیریِ سؤال/پاسخ) شمارش نمی‌شود؛ وگرنه
        # هر تستِ end-to-end دو تماس برایِ یکِ پیامِ مشتری می‌بیند.
        if not user_message.startswith("بر اساس مکالمه"):
            self.calls.append(user_message)
        return AiCallResult(text="سلام، چطور می‌تونم کمکتون کنم؟", total_tokens=50)


def _install(fake: _FakeAi):
    original = ai_service.get_ai_service
    ai_service.get_ai_service = lambda *a, **k: fake
    return original


async def _add_rule(pattern: str, action: str, *, shop_bot_id: int | None = None) -> int:
    async with session_scope() as session:
        rule = ModerationRule(pattern=pattern, is_regex=False, action=action)
        rule.shop_bot_id = shop_bot_id
        session.add(rule)
        await session.flush()
        rule_id = rule.id
        await session.commit()
    return rule_id


async def _reports(shop_bot_id: int) -> list[ModerationReport]:
    async with session_scope() as session:
        return list((await session.execute(select(ModerationReport).where(ModerationReport.shop_bot_id == shop_bot_id))).scalars().all())


# ============================================================================= ۱ — دقت (۳۰)
def test_matcher_is_word_bounded() -> None:
    for harmless in ("این آخرین خریدِ من است", "خریدِ دوم را هم اضافه کن", "خبر داری؟ قیمت چند؟"):
        assert not moderation_service._phrase_matches(moderation_service.tokenize("خر"), moderation_service.tokenize(harmless)), harmless
    assert moderation_service._phrase_matches(moderation_service.tokenize("خر"), moderation_service.tokenize("این خر را می‌خرم"))
    assert moderation_service._phrase_matches(moderation_service.tokenize("تقلب کردن"), moderation_service.tokenize("او   تقلب کردن را یاد بگیر"))
    assert not moderation_service._phrase_matches(moderation_service.tokenize("تقلب کردن"), moderation_service.tokenize("من تقلب کردم"))
    assert moderation_service._phrase_matches(moderation_service.tokenize("كذب"), moderation_service.tokenize("این رجل كذب"))
    assert not moderation_service._phrase_matches(moderation_service.tokenize(""), moderation_service.tokenize("هر چیزی"))
    print("✅ test_matcher_is_word_bounded PASSED")


# ============================================================================= ۲ — دامنه (۳۰)
async def test_rule_scope_is_per_shop() -> None:
    await reset_database()
    shop_a = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    shop_b = await seed_usable_shop(OTHER_OWNER_TG_ID, OTHER_SHOP_BOT_TG_ID)
    async with session_scope() as session:
        await moderation_service.check_text(session, "بی‌ربط", shop_bot_id=shop_a)
        rows = await moderation_service.get_rules(session, shop_a)
        assert [r.shop_bot_id for r in rows] == [], "با هیچِ قانونِ فروشگاه، فقط سراسری‌ها"

    await _add_rule("ممنوعه", "warn", shop_bot_id=shop_a)
    async with session_scope() as session:
        hit_a = await moderation_service.check_text(session, "این ممنوعه است", shop_bot_id=shop_a)
        hit_b = await moderation_service.check_text(session, "این ممنوعه است", shop_bot_id=shop_b)
        assert hit_a is not None and hit_a.shop_bot_id == shop_a, "قانونِ خودِ فروشگاه اجرا می‌شود"
        assert hit_b is None, "قانونِ فروشگاهِ دیگر نباید اینجا اجرا شود (موردِ ۳۰)"
        assert moderation_service.scope_of(hit_a) == "shop"
    print("✅ test_rule_scope_is_per_shop PASSED")


# ============================================================================= ۳ — end-to-end (۱۰، ۳۱)
async def test_warn_and_block_end_to_end(shop_dp) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    await _add_rule("خر", "warn")
    fake = _FakeAi()
    original = _install(fake)
    shop_bot_instance = Bot(token=f"{SHOP_BOT_TG_ID}:FAKE", session=FakeSession())
    try:
        # ۱) همان جمله‌ای که قبلاً گزارشِ بی‌دلیل می‌ساخت
        await shop_dp.feed_update(shop_bot_instance, make_message_update(1, text="این آخرین خریدِ من است", user_id=CUSTOMER_TG_ID))
        await asyncio.sleep(DEBOUNCE_WAIT)
        assert fake.calls == ["این آخرین خریدِ من است"], fake.calls
        async with session_scope() as session:
            from app.services import shop_bot_service

            shop_bot = await shop_bot_service.get_by_bot_telegram_id(session, SHOP_BOT_TG_ID)
            shop_id = shop_bot.id
        assert await _reports(shop_id) == [], "تطبیقِ غلط نباید گزارش بسازد (موردِ ۳۰)"

        # ۲) WARNِ واقعی: پاسخِ AI می‌رود، چیزی به مشتری گفته نمی‌شود، گزارش ثبت می‌شود
        await shop_dp.feed_update(shop_bot_instance, make_message_update(2, text="این خر را می‌خرم", user_id=CUSTOMER_TG_ID))
        await asyncio.sleep(DEBOUNCE_WAIT)
        assert fake.calls == ["این آخرین خریدِ من است", "این خر را می‌خرم"], fake.calls
        reports = await _reports(shop_id)
        assert len(reports) == 1, reports
        report = reports[0]
        assert report.pattern == "خر" and report.action == "warn" and report.scope == "platform"
        assert report.customer_id is not None and "خر" in report.excerpt, report.excerpt
        async with session_scope() as session:
            entries = list((await session.execute(select(ModerationReport.id).where(ModerationReport.id == report.id))).scalars().all())
            assert entries == [report.id]
    finally:
        ai_service.get_ai_service = original
        await shop_bot_instance.session.close()

    # ۳) BLOCK ⇒ بدونِ AI و با ستونِ بلاک (موردِ ۳۱)
    await _add_rule("كذب", "block")
    fake2 = _FakeAi()
    original2 = _install(fake2)
    second = Bot(token=f"{SHOP_BOT_TG_ID}:FAKE", session=FakeSession())
    try:
        await shop_dp.feed_update(second, make_message_update(3, text="این رجل كذب است", user_id=CUSTOMER_TG_ID))
        await asyncio.sleep(DEBOUNCE_WAIT)
        assert fake2.calls == [], f"BLOCK نباید AI صدا بزند: {fake2.calls}"
        async with session_scope() as session:
            customer = (await session.execute(select(Customer).where(Customer.telegram_id == CUSTOMER_TG_ID))).scalar_one()
            assert customer.is_blocked is True, "«مسدود» باید Customer.is_blocked را بنویسد"
        # پیامِ بعدیِ همان مشتری: میدل‌ورِ بلاک جلویش را می‌گیرد
        third = Bot(token=f"{SHOP_BOT_TG_ID}:FAKE", session=FakeSession())
        await shop_dp.feed_update(third, make_message_update(4, text="دوباره سلام", user_id=CUSTOMER_TG_ID))
        await asyncio.sleep(1.0)
        assert fake2.calls == [], "پس ازِ بلاک هم AI صدا زده نمی‌شود"
        await third.session.close()
    finally:
        ai_service.get_ai_service = original2
        await second.session.close()
    print("✅ test_warn_and_block_end_to_end PASSED")


# ============================================================================= ۴ — صفحه‌ها (۱۰)
async def test_guard_pages_and_buttons(main_dp) -> None:
    await reset_database()
    shop_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    other_shop_id = await seed_usable_shop(OTHER_OWNER_TG_ID, OTHER_SHOP_BOT_TG_ID)
    for mode in ("sales", "consultation"):
        kb = keyboards.shop_owner_panel_keyboard(mode)
        labels = {b.text for row in kb.keyboard for b in row}
        assert main_texts.MODERATION_GUARD_BUTTON in labels, (mode, labels)
        assert max(len(row) for row in kb.keyboard) <= 2, (mode, [len(r) for r in kb.keyboard])

    async with session_scope() as session:
        customer = Customer(shop_bot_id=shop_id, telegram_id=CUSTOMER_TG_ID, platform="telegram")
        session.add(customer)
        await session.flush()
        mine = ModerationReport(shop_bot_id=shop_id, customer_id=customer.id, rule_id=None, pattern="خر",
                                action="warn", scope="platform", excerpt="این خر را می‌خرم")
        theirs = ModerationReport(shop_bot_id=other_shop_id, customer_id=None, rule_id=None, pattern="خصوصی",
                                  action="review", scope="shop", excerpt="پیامِ فروشگاهِ دیگر")
        session.add_all([mine, theirs])
        await session.flush()
        report_id, other_id, customer_id = mine.id, theirs.id, customer.id
        await session.commit()

    owner = Chat(main_dp, OWNER_TG_ID)
    await owner.say(main_texts.MODERATION_GUARD_BUTTON)
    datas = [b.callback_data for row in owner.last_markup.inline_keyboard for b in row if b.callback_data]
    assert f"mod_open:{report_id}" in datas, datas
    assert f"mod_open:{other_id}" not in datas, "فهرستِ هر فروشگاه فقط گزارش‌هایِ خودش است"

    await owner.tap(f"mod_open:{report_id}")
    # کارت با edit_text نشانه‌گذاری می‌شود ⇒ از `edits` خوانده می‌شود (نه فهرستِ پیام‌هایِ فرستاده‌شده)
    card = owner.last_edit_text
    assert "این خر را می‌خرم" in card and "«خر»" in card, card
    datas = [b.callback_data for row in owner.edits[-1]["reply_markup"].inline_keyboard for b in row if b.callback_data]
    assert f"crm_conv:{customer_id}:0" in datas, f"«گفتگو» همان صفحهٔ CRM را باز می‌کند: {datas}"
    assert f"crm_card:{customer_id}" in datas, datas
    assert f"mod_block:{report_id}" in datas and f"mod_done:{report_id}" in datas, datas

    await owner.tap(f"mod_block:{report_id}")
    async with session_scope() as session:
        assert (await session.get(Customer, customer_id)).is_blocked is True
    await owner.tap(f"mod_unblock:{report_id}")
    async with session_scope() as session:
        assert (await session.get(Customer, customer_id)).is_blocked is False

    await owner.tap(f"mod_done:{report_id}")
    async with session_scope() as session:
        row = await session.get(ModerationReport, report_id)
        assert row.reviewed is True and row.reviewed_at is not None
    await owner.say(main_texts.MODERATION_GUARD_BUTTON)
    datas = [b.callback_data for row in owner.last_markup.inline_keyboard for b in row if b.callback_data]
    assert f"mod_open:{report_id}" not in datas, "گزارشِ بسته‌شده از فهرستِ «باز» می‌رود"

    stranger = Chat(main_dp, 7_443_999_999)
    await stranger.tap("mod_admin_list:0")
    assert stranger.last_toast["text"] == main_texts.ADMIN_ONLY_COMMAND, stranger.last_toast
    print("✅ test_guard_pages_and_buttons PASSED")


async def main() -> None:
    assert settings.admin_ids, "این تست به ADMIN_TELEGRAM_IDSِ محیطِ تست نیاز دارد"
    main_dp, shop_dp, bot_manager, main_bot = build_test_dispatchers()
    test_matcher_is_word_bounded()
    await test_rule_scope_is_per_shop()
    await test_warn_and_block_end_to_end(shop_dp)
    await test_guard_pages_and_buttons(main_dp)


if __name__ == "__main__":
    asyncio.run(main())
