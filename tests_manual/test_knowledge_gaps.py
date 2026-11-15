"""
تست: تشخیصِ «سوالِ بی‌جواب» (فازِ ۴-الف) — از پرامپتِ ربات تا پنلِ فروشگاه‌دار.

پوشش:
۱. منطقِ خالص: حذفِ نشانه‌یِ [[GAP]] (هر شکلی)، یکسان‌سازیِ سوال (فاصله/رقمِ فارسی/ی-ک/علامت)، هش، کوتاه‌سازی.
۲. دستورِ تشخیصِ خلأ فقط وقتی کلیدِ سراسری روشنه به پرامپت اضافه می‌شه؛ بدونِ اون و بدونِ پرسش‌وپاسخ،
   پرامپت بایت‌به‌بایت مثلِ قبله.
۳. مسیرِ واقعیِ پاسخ به مشتری: نشانه *هیچ‌وقت* به مشتری نمی‌رسه و توی تاریخچه نمی‌ره؛ سوال ثبت و
   تجمیع می‌شه (سوالِ تکراری با فرمتِ متفاوت = همون ردیف). جوابِ فقط-نشانه → متنِ جایگزین.
۴. کلیدِ خاموش: نشانه حذف می‌شه ولی چیزی ثبت نمی‌شه و دستور توی پرامپت نیست.
۵. سقفِ سوال‌هایِ بازِ هر فروشگاه + تکراری‌ها همچنان شمرده می‌شن؛ ثبتِ هم‌زمانِ یه سوال = یه ردیف با شمارنده‌یِ درست.
۶. پنلِ فروشگاه‌دار: فهرست (بیشترین تکرار اول)، پاسخ ← پیش‌نمایش ← تایید، لغو، نادیده‌گرفتن، اعتبارسنجی،
   دکمه‌یِ کهنه، ایزوله‌بودنِ چندمستاجری، دکمه‌یِ منو وسطِ FSM.
۷. پیش‌نمایشِ ربات: نشانه حذف می‌شه ولی هیچ‌وقت ثبت نمی‌شه؛ هزینه‌ای نداره.
۸. گزارشِ شبانه: خطِ «سوالِ بی‌جوابِ جدید» فقط وقتی >۰؛ سوییچِ سراسریِ ادمین + ممیزی + محدودیتِ ادمینِ عملیاتی.

اجرا: python3 tests_manual/test_knowledge_gaps.py
"""
from __future__ import annotations

import asyncio
import datetime
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402
from sqlalchemy import select  # noqa: E402

from harness import FakeSession, build_test_dispatchers, reset_database  # noqa: E402
from phase4_helpers import Chat, FakeAi, callbacks, owner_balance, patched_ai, set_ai  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot import texts  # noqa: E402
from app.bots.shop_bot import texts as shop_texts  # noqa: E402
from app.bots.shop_bot.handlers import customer as customer_handlers  # noqa: E402
from app.database.models import (  # noqa: E402
    AuditEventType,
    AuditLogEntry,
    ConversationMessage,
    KnowledgeGap,
    KnowledgeGapStatus,
    LearnedAnswer,
)
from app.database.session import session_scope  # noqa: E402
from app.services import (  # noqa: E402
    admin_role_service,
    ai_context,
    knowledge_service,
    product_service,
    shop_bot_service,
    stats_service,
)
from app.services.admin_settings_service import get_admin_settings  # noqa: E402

ADMIN_TG_ID = 12345  # باید با ADMIN_TELEGRAM_IDS توی .env یکی باشه
OPERATOR_TG_ID = 991031
OWNER_TG_ID = 991001
SHOP_BOT_TG_ID = 991002
CUSTOMER_TG_ID = 991003
OTHER_OWNER_TG_ID = 991011
OTHER_SHOP_BOT_TG_ID = 991012
STRANGER_TG_ID = 991021

UTC = datetime.timezone.utc
MARKER = "[[GAP]]"


async def _seed() -> int:
    await reset_database()
    return await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)


async def _gaps(shop_bot_id: int | None = None) -> list[KnowledgeGap]:
    async with session_scope() as session:
        query = select(KnowledgeGap).order_by(KnowledgeGap.id)
        if shop_bot_id is not None:
            query = query.where(KnowledgeGap.shop_bot_id == shop_bot_id)
        return list((await session.execute(query)).scalars().all())


async def _learned() -> list[LearnedAnswer]:
    async with session_scope() as session:
        return list((await session.execute(select(LearnedAnswer).order_by(LearnedAnswer.id))).scalars().all())


async def _make_gap(shop_bot_id: int, text: str, times: int = 1) -> int:
    async with session_scope() as session:
        for _ in range(times):
            assert await knowledge_service.record_gap(session, shop_bot_id, text) is True
    return next(gap.id for gap in await _gaps(shop_bot_id) if gap.question_text == knowledge_service.truncate_text(text, 300))


async def _customer_says(shop_bot_id: int, bot: Bot, main_bot: Bot, text: str) -> None:
    async with session_scope() as session:
        await customer_handlers._generate_and_send_reply(session, shop_bot_id, CUSTOMER_TG_ID, text, bot, main_bot)
    await asyncio.sleep(0.2)  # تسکِ پس‌زمینه‌یِ تشخیصِ سفارش


async def _set_gap_switch(enabled: bool) -> None:
    async with session_scope() as session:
        (await get_admin_settings(session)).knowledge_gap_enabled = enabled


# =============================================================================
# ۱. منطقِ خالص
# =============================================================================
def test_pure_marker_and_normalization() -> None:
    strip = knowledge_service.strip_gap_marker
    assert strip("جواب [[GAP]]") == ("جواب", True)
    assert strip("جواب [[ gap ]]") == ("جواب", True), "فاصله‌یِ داخلِ کروشه و حروفِ کوچیک هم نشانه حساب می‌شه"
    assert strip("[[GAP]]") == ("", True)
    assert strip("الف [[GAP]] ب") == ("الف ب", True), "فاصله‌یِ دوبل‌شده‌یِ جایِ نشانه جمع می‌شه"
    assert strip("[[GAP]] یک [[gap]] دو") == ("یک دو", True), "همه‌یِ نشانه‌ها حذف می‌شن"
    assert strip("جواب\n[[GAP]]") == ("جواب", True)
    assert strip("بدون نشانه") == ("بدون نشانه", False)
    assert strip("[GAP] جواب") == ("جواب", True), "تک‌کروشه (انحرافِ رایجِ مدل‌ها) هم نشانه حساب می‌شه و به مشتری نمی‌رسه"
    assert strip("GAP بدونِ کروشه") == ("GAP بدونِ کروشه", False) and strip("[ماهیتِ GAP نیست]") == ("[ماهیتِ GAP نیست]", False)
    assert strip(None) == ("", False) and strip("") == ("", False)

    norm = knowledge_service.normalize_question
    assert norm("قیمتِ ارسال؟") == norm("قیمت ارسال") == "قیمتارسال"
    assert norm("قیمت ۱۲۳") == norm("قیمت 123") == norm("قیمت ١٢٣")
    assert norm("كتاب") == norm("کتاب") and norm("علي") == norm("علی")
    assert norm("چند؟!؟") == norm("چند")
    assert norm("   ") == "" and norm(None) == "" and norm("😀؟!") == ""

    key = knowledge_service.make_question_key
    assert key("قیمت ارسال؟") == key("قیمتِ ارسال") and len(key("x")) == 64
    assert key("قیمت ارسال") != key("قیمت ارسالی")
    assert key("؟؟") is None and key(None) is None and key("😀") is None

    trunc = knowledge_service.truncate_text
    assert trunc("  الف \n\n ب  ", 50) == "الف ب"
    long_text = "ا" * 50
    assert len(trunc(long_text, 10)) == 10 and trunc(long_text, 10).endswith("…")
    assert trunc("abc", 3) == "abc" and trunc(None, 5) == ""

    print("✅ test_pure_marker_and_normalization PASSED")


# =============================================================================
# ۲. پرامپت
# =============================================================================
async def test_prompt_instruction_only_when_enabled_and_baseline_unchanged() -> None:
    shop_bot_id = await _seed()
    async with session_scope() as session:
        shop_bot = await shop_bot_service.get_by_id(session, shop_bot_id)
        products = await product_service.get_active_by_shop_bot(session, shop_bot_id)
        baseline = ai_context.build_system_prompt(shop_bot, products, [], None)
        same = ai_context.build_system_prompt(shop_bot, products, [], None, learned_answers=[], gap_detection=False)
        with_gap = ai_context.build_system_prompt(shop_bot, products, [], None, gap_detection=True)

    assert baseline == same, "بدونِ پرسش‌وپاسخ و با کلیدِ خاموش، پرامپت باید دقیقاً مثلِ قبل باشه"
    assert MARKER not in baseline
    assert with_gap.startswith(baseline) and with_gap.endswith(ai_context.GAP_DETECTION_INSTRUCTION)
    assert MARKER in ai_context.GAP_DETECTION_INSTRUCTION
    assert "حدس نزن" in ai_context.GAP_DETECTION_INSTRUCTION

    print("✅ test_prompt_instruction_only_when_enabled_and_baseline_unchanged PASSED")


# =============================================================================
# ۳. مسیرِ واقعیِ پاسخ به مشتری
# =============================================================================
async def test_gap_recorded_and_marker_never_reaches_customer(main_bot) -> None:
    shop_bot_id = await _seed()
    fake = set_ai(FakeAi(chat_reply=f"متاسفانه جوابش رو نمی‌دونم، به فروشگاه‌دار می‌سپارم. {MARKER}"))
    bot = Bot(token=f"{SHOP_BOT_TG_ID}:FAKE", session=FakeSession())

    await _customer_says(shop_bot_id, bot, main_bot, "ساعت کاری شما چیه؟")

    assert len(bot.session.sent_messages) == 1
    assert bot.session.sent_messages[0]["text"] == "متاسفانه جوابش رو نمی‌دونم، به فروشگاه‌دار می‌سپارم."
    assert MARKER not in bot.session.sent_messages[0]["text"], "نشانه هیچ‌وقت نباید به مشتری برسه"
    assert MARKER in fake.chat_calls[0][0], "دستورِ تشخیصِ خلأ باید توی پرامپتِ این فراخوانی باشه"

    async with session_scope() as session:
        stored = list((await session.execute(select(ConversationMessage))).scalars().all())
    assert len(stored) == 2 and all(MARKER not in m.content for m in stored), "نشانه نباید توی تاریخچه ذخیره بشه"

    gaps = await _gaps(shop_bot_id)
    assert len(gaps) == 1
    assert gaps[0].question_text == "ساعت کاری شما چیه؟" and gaps[0].occurrences == 1
    assert gaps[0].status == KnowledgeGapStatus.OPEN

    # همون سوال با فرمتِ متفاوت (بدونِ علامت، فاصله‌یِ اضافه) = همون ردیف، شمارنده بالا می‌ره
    await _customer_says(shop_bot_id, bot, main_bot, "  ساعتِ  کاری شما چیه  ")
    gaps = await _gaps(shop_bot_id)
    assert len(gaps) == 1 and gaps[0].occurrences == 2, "سوالِ تکراری باید تجمیع بشه، نه ردیفِ تازه"
    assert all(MARKER not in m["text"] for m in bot.session.sent_messages)

    # در تاریخچه‌یِ دفعه‌یِ دوم، AI نشانه‌ای ندیده که تقلیدش کنه
    assert all(MARKER not in item["content"] for item in fake.chat_calls[1][1])

    print("✅ test_gap_recorded_and_marker_never_reaches_customer PASSED")


async def test_marker_only_reply_uses_fallback_and_still_records(main_bot) -> None:
    shop_bot_id = await _seed()
    set_ai(FakeAi(chat_reply=MARKER))
    bot = Bot(token=f"{SHOP_BOT_TG_ID}:FAKE", session=FakeSession())

    await _customer_says(shop_bot_id, bot, main_bot, "آدرس دقیقِ مغازه کجاست؟")

    assert bot.session.sent_messages[-1]["text"] == shop_texts.GAP_FALLBACK_REPLY
    assert len(await _gaps(shop_bot_id)) == 1
    async with session_scope() as session:
        stored = list((await session.execute(select(ConversationMessage).order_by(ConversationMessage.id))).scalars().all())
    assert stored[-1].content == shop_texts.GAP_FALLBACK_REPLY, "متنِ جایگزین ذخیره می‌شه، نه یه پیامِ خالی"

    print("✅ test_marker_only_reply_uses_fallback_and_still_records PASSED")


async def test_switch_off_strips_marker_but_records_nothing(main_bot) -> None:
    shop_bot_id = await _seed()
    await _set_gap_switch(False)
    fake = set_ai(FakeAi(chat_reply=f"ببخشید نمی‌دونم {MARKER.lower()}"))
    bot = Bot(token=f"{SHOP_BOT_TG_ID}:FAKE", session=FakeSession())

    await _customer_says(shop_bot_id, bot, main_bot, "سوالِ بی‌جوابِ من")

    assert bot.session.sent_messages[-1]["text"] == "ببخشید نمی‌دونم", "با کلیدِ خاموش هم نشانه حتماً حذف می‌شه"
    assert await _gaps(shop_bot_id) == [], "با کلیدِ خاموش چیزی ثبت نمی‌شه"
    assert MARKER not in fake.chat_calls[0][0], "با کلیدِ خاموش دستورِ تشخیص توی پرامپت نیست"

    # روشن‌کردنِ دوباره: دستور برمی‌گرده و ثبت انجام می‌شه
    await _set_gap_switch(True)
    await _customer_says(shop_bot_id, bot, main_bot, "یه سوالِ دیگه")
    assert MARKER in fake.chat_calls[1][0] and len(await _gaps(shop_bot_id)) == 1

    # جوابِ عادی بدونِ نشانه: چیزی ثبت نمی‌شه
    set_ai(FakeAi(chat_reply="جوابِ کاملِ عادی"))
    await _customer_says(shop_bot_id, bot, main_bot, "قیمتِ چایِ ممتاز؟")
    assert len(await _gaps(shop_bot_id)) == 1
    assert bot.session.sent_messages[-1]["text"] == "جوابِ کاملِ عادی"

    print("✅ test_switch_off_strips_marker_but_records_nothing PASSED")


# =============================================================================
# ۵. سقف و هم‌زمانی
# =============================================================================
async def test_open_gap_cap_blocks_new_questions_but_counts_repeats() -> None:
    shop_bot_id = await _seed()
    original_cap = knowledge_service.MAX_OPEN_GAPS_PER_SHOP
    knowledge_service.MAX_OPEN_GAPS_PER_SHOP = 3
    try:
        async with session_scope() as session:
            for index in range(3):
                assert await knowledge_service.record_gap(session, shop_bot_id, f"سوالِ شماره {index}") is True
            assert await knowledge_service.record_gap(session, shop_bot_id, "سوالِ کاملاً جدید") is False, (
                "بعد از رسیدن به سقف، سوالِ تازه ثبت نمی‌شه"
            )
            assert await knowledge_service.record_gap(session, shop_bot_id, "سوالِ شماره 1") is True, "تکراری همچنان شمرده می‌شه"
            assert await knowledge_service.record_gap(session, shop_bot_id, "؟؟") is False, "متنِ بی‌معنی ثبت نمی‌شه"
            assert await knowledge_service.count_open_gaps(session, shop_bot_id) == 3

        gaps = await _gaps(shop_bot_id)
        assert len(gaps) == 3
        repeated = next(gap for gap in gaps if gap.question_text == "سوالِ شماره 1")
        assert repeated.occurrences == 2

        # فروشگاهِ دیگه سقفِ خودش رو داره
        other_shop_bot_id = await seed_usable_shop(OTHER_OWNER_TG_ID, OTHER_SHOP_BOT_TG_ID)
        async with session_scope() as session:
            assert await knowledge_service.record_gap(session, other_shop_bot_id, "سوالِ فروشگاهِ دوم") is True
    finally:
        knowledge_service.MAX_OPEN_GAPS_PER_SHOP = original_cap

    print("✅ test_open_gap_cap_blocks_new_questions_but_counts_repeats PASSED")


async def test_concurrent_same_question_stays_one_row() -> None:
    shop_bot_id = await _seed()

    async def record() -> bool:
        async with session_scope() as session:
            return await knowledge_service.record_gap(session, shop_bot_id, "قیمتِ ارسال به شیراز؟")

    results = await asyncio.gather(*[record() for _ in range(8)])
    assert all(results)
    gaps = await _gaps(shop_bot_id)
    assert len(gaps) == 1 and gaps[0].occurrences == 8, "۸ ثبتِ هم‌زمان باید یه ردیف با شمارنده‌یِ ۸ بسازه"

    print("✅ test_concurrent_same_question_stays_one_row PASSED")


# =============================================================================
# ۶. پنلِ فروشگاه‌دار
# =============================================================================
async def test_owner_flow_answer_dismiss_and_validation(main_dp) -> None:
    shop_bot_id = await _seed()
    popular = await _make_gap(shop_bot_id, "قیمت ارسال به شیراز چقدره؟", times=3)
    rare = await _make_gap(shop_bot_id, "آیا گارانتی دارید؟")
    owner = Chat(main_dp, OWNER_TG_ID)

    await owner.say("🧩 سوال‌هایِ بی‌جواب")
    assert "قیمت ارسال به شیراز چقدره؟" in owner.last_text and "۳ بار" in owner.last_text
    assert owner.last_text.index("قیمت ارسال") < owner.last_text.index("گارانتی"), "بیشترین تکرار اول"
    assert callbacks(owner.last_markup) == [
        f"gap_answer:{popular}",
        f"gap_dismiss:{popular}",
        f"gap_answer:{rare}",
        f"gap_dismiss:{rare}",
        # پ۷۵: ردیفِ تازهٔ «🧠 سوال‌هایِ مشابه» (ادعایِ کهنه عمداً گسترش یافت، نه ضعیف).
        "gap_clusters",
    ]

    # --- پاسخ: اعتبارسنجی، پیش‌نمایش، تایید ---
    await owner.tap(f"gap_answer:{popular}")
    assert owner.last_text == texts.gap_answer_prompt("قیمت ارسال به شیراز چقدره؟")
    await owner.say("   ")
    assert owner.last_text == texts.GAP_ANSWER_EMPTY
    await owner.say("ی" * 501)
    assert owner.last_text == texts.GAP_ANSWER_TOO_LONG
    answer = "ارسال به شیراز ۶۰ هزار تومانه."
    await owner.say(answer)
    assert owner.last_text == texts.gap_answer_preview("قیمت ارسال به شیراز چقدره؟", answer)
    assert callbacks(owner.last_markup) == ["gap_save_confirm", "gap_save_cancel"]
    assert await _learned() == [], "تا تاییدِ نهایی چیزی ذخیره نمی‌شه"

    await owner.tap("gap_save_confirm")
    learned = await _learned()
    assert len(learned) == 1
    assert learned[0].answer == answer and learned[0].question == "قیمت ارسال به شیراز چقدره؟"
    assert learned[0].source_gap_id == popular and learned[0].is_active
    assert next(g for g in await _gaps(shop_bot_id) if g.id == popular).status == KnowledgeGapStatus.ANSWERED

    await owner.tap("gap_save_confirm")  # دابل‌تپ
    assert owner.last_toast["text"] == texts.KNOWLEDGE_STALE_BUTTON and owner.last_toast["show_alert"]
    assert len(await _learned()) == 1, "دابل‌تپ نباید پرسش‌وپاسخِ تکراری بسازه"

    # --- لغو: چیزی ذخیره نمی‌شه و سوال باز می‌مونه ---
    await owner.tap(f"gap_answer:{rare}")
    await owner.say("ضمانتِ ۱۸ ماهه داره")
    await owner.tap("gap_save_cancel")
    assert len(await _learned()) == 1
    assert next(g for g in await _gaps(shop_bot_id) if g.id == rare).status == KnowledgeGapStatus.OPEN

    # --- پاسخ‌دادن به سوالی که وسطِ راه بسته شده ---
    await owner.tap(f"gap_answer:{rare}")
    async with session_scope() as session:
        gap = await knowledge_service.get_owned_gap(session, rare, shop_bot_id)
        await knowledge_service.dismiss_gap(session, gap)
    await owner.say("جوابی که دیر رسید")
    assert owner.last_text == texts.GAP_NOT_OPEN, "سوالِ بسته‌شده دیگه جواب نمی‌گیره"
    assert len(await _learned()) == 1

    # --- نادیده‌گرفتن ---
    fresh = await _make_gap(shop_bot_id, "سوالِ تازه برایِ نادیده‌گرفتن")
    await owner.tap(f"gap_dismiss:{fresh}")
    assert owner.last_toast["text"] == texts.GAP_DISMISSED
    assert next(g for g in await _gaps(shop_bot_id) if g.id == fresh).status == KnowledgeGapStatus.DISMISSED
    await owner.tap(f"gap_dismiss:{fresh}")
    assert owner.last_toast["text"] == texts.GAP_NOT_OPEN and owner.last_toast["show_alert"]

    await owner.say("🧩 سوال‌هایِ بی‌جواب")
    assert owner.last_text == texts.GAPS_EMPTY

    print("✅ test_owner_flow_answer_dismiss_and_validation PASSED")


async def test_gap_list_paginates_and_notes_disabled_detection(main_dp) -> None:
    shop_bot_id = await _seed()
    for index in range(7):
        await _make_gap(shop_bot_id, f"سوالِ صفحه‌بندی شماره {index}")
    owner = Chat(main_dp, OWNER_TG_ID)

    await owner.say("🧩 سوال‌هایِ بی‌جواب")
    markup_callbacks = callbacks(owner.last_markup)
    assert "gap_list:1" in markup_callbacks and "noop" in markup_callbacks, "۷ سوال با اندازه‌یِ صفحه‌یِ ۵ = دو صفحه"
    assert sum(1 for data in markup_callbacks if data.startswith("gap_answer:")) == 5

    # خاموش‌بودنِ تشخیص توی فهرست یادآوری می‌شه (فروشگاه‌دار گیج نشه)
    await _set_gap_switch(False)
    await owner.say("🧩 سوال‌هایِ بی‌جواب")
    assert texts.GAPS_DETECTION_OFF_NOTE in owner.last_text

    print("✅ test_gap_list_paginates_and_notes_disabled_detection PASSED")


async def test_other_owner_and_strangers_cannot_touch_gaps(main_dp) -> None:
    shop_bot_id = await _seed()
    other_shop_bot_id = await seed_usable_shop(OTHER_OWNER_TG_ID, OTHER_SHOP_BOT_TG_ID)
    gap_id = await _make_gap(shop_bot_id, "سوالِ فروشگاهِ اول")

    intruder = Chat(main_dp, OTHER_OWNER_TG_ID)
    for action in ("gap_answer", "gap_dismiss"):
        await intruder.tap(f"{action}:{gap_id}")
        assert intruder.last_toast["text"] == texts.GAP_NOT_FOUND and intruder.last_toast["show_alert"], action
    await intruder.tap("gap_dismiss:abc")
    assert intruder.last_toast["text"] == texts.GAP_NOT_FOUND, "شناسه‌یِ نامعتبر هم بی‌خطر رد می‌شه"
    await intruder.say("🧩 سوال‌هایِ بی‌جواب")
    assert intruder.last_text == texts.GAPS_EMPTY, "فروشگاه‌دارِ دیگه نباید سوال‌هایِ این فروشگاه رو ببینه"

    stranger = Chat(main_dp, STRANGER_TG_ID)
    await stranger.tap(f"gap_dismiss:{gap_id}")
    assert stranger.last_toast["show_alert"]
    await stranger.say("🧩 سوال‌هایِ بی‌جواب")
    assert stranger.last_text == texts.SHOP_BOT_NOT_SET_UP

    gaps = await _gaps()
    assert len(gaps) == 1 and gaps[0].status == KnowledgeGapStatus.OPEN and gaps[0].shop_bot_id == shop_bot_id
    assert await _gaps(other_shop_bot_id) == [] and await _learned() == []

    print("✅ test_other_owner_and_strangers_cannot_touch_gaps PASSED")


async def test_menu_button_escapes_knowledge_states(main_dp) -> None:
    shop_bot_id = await _seed()
    gap_id = await _make_gap(shop_bot_id, "سوالی که وسطش پشیمون می‌شیم")
    owner = Chat(main_dp, OWNER_TG_ID)

    await owner.tap(f"gap_answer:{gap_id}")
    await owner.say("🧩 سوال‌هایِ بی‌جواب")  # دکمه‌یِ منو وسطِ FSM
    assert "سوالی که وسطش پشیمون می‌شیم" in owner.last_text, "دکمه‌یِ منو باید فهرست رو باز کنه، نه اینکه به‌عنوانِ جواب ذخیره بشه"
    await owner.say("جوابِ واقعی")  # state پاک شده؛ این متن دیگه جوابِ سوال حساب نمی‌شه
    assert texts.gap_answer_preview("سوالی که وسطش پشیمون می‌شیم", "جوابِ واقعی") not in [m["text"] for m in owner.sent]
    assert await _learned() == []

    print("✅ test_menu_button_escapes_knowledge_states PASSED")


# =============================================================================
# ۷. پیش‌نمایش
# =============================================================================
async def test_preview_strips_marker_but_never_records(main_dp) -> None:
    shop_bot_id = await _seed()
    fake = set_ai(FakeAi(chat_reply=f"نمی‌دونم {MARKER}"))
    owner = Chat(main_dp, OWNER_TG_ID)
    balance_before = await owner_balance(OWNER_TG_ID)

    await owner.say("👀 پیش‌نمایش ربات")
    assert owner.last_text == texts.PREVIEW_START_INTRO
    await owner.say("سوالِ تستیِ من")
    assert MARKER not in owner.last_text
    assert owner.last_text == f"نمی‌دونم\n\n{texts.PREVIEW_GAP_NOTE}"
    assert MARKER in fake.chat_calls[0][0], "پیش‌نمایش هم باید رفتارِ واقعی رو نشون بده (دستور توی پرامپته)"
    assert await _gaps(shop_bot_id) == [], "سوالِ تستیِ فروشگاه‌دار نباید ثبت بشه"
    assert await owner_balance(OWNER_TG_ID) == balance_before, "پیش‌نمایش هزینه‌ای نداره"

    await owner.say("🔚 پایان پیش‌نمایش")
    assert owner.last_text == texts.PREVIEW_END_TEXT

    print("✅ test_preview_strips_marker_but_never_records PASSED")


# =============================================================================
# ۸. گزارشِ شبانه و سوییچِ ادمین
# =============================================================================
async def test_nightly_report_mentions_new_gaps_only_when_any() -> None:
    shop_bot_id = await _seed()
    now = datetime.datetime.now(UTC)

    async def stats() -> dict:
        async with session_scope() as session:
            return await stats_service.get_shop_daily_stats(
                session, shop_bot_id, now - datetime.timedelta(hours=1), now + datetime.timedelta(minutes=1)
            )

    before = await stats()
    assert before["new_knowledge_gaps"] == 0
    assert "بی‌جواب" not in texts.nightly_report_text(before), "بدونِ سوالِ تازه خطی اضافه نمی‌شه"

    gap_id = await _make_gap(shop_bot_id, "سوالِ تازه‌یِ امشب", times=2)
    after = await stats()
    assert after["new_knowledge_gaps"] == 1, "یه سوالِ متمایز یه بار شمرده می‌شه، نه به‌تعدادِ تکرارش"
    assert "🧩 ۱ سوالِ بی‌جوابِ جدید" in texts.nightly_report_text(after)

    async with session_scope() as session:
        await knowledge_service.dismiss_gap(session, await knowledge_service.get_owned_gap(session, gap_id, shop_bot_id))
    assert (await stats())["new_knowledge_gaps"] == 0, "سوالِ نادیده‌گرفته‌شده دیگه جزو «تازه‌هایِ باز» نیست"

    print("✅ test_nightly_report_mentions_new_gaps_only_when_any PASSED")


async def test_admin_toggle_knowledge_gap_switch(main_dp) -> None:
    await _seed()
    admin = Chat(main_dp, ADMIN_TG_ID)

    async with session_scope() as session:
        assert (await get_admin_settings(session)).knowledge_gap_enabled is True, "پیش‌فرض باید روشن باشه"

    await admin.tap("admin_toggle_knowledge_gap")
    async with session_scope() as session:
        assert (await get_admin_settings(session)).knowledge_gap_enabled is False
        entries = list(
            (await session.execute(select(AuditLogEntry).where(AuditLogEntry.event_type == AuditEventType.KILL_SWITCH_TOGGLED)))
            .scalars()
            .all()
        )
    assert any("knowledge_gap_enabled -> False" in (entry.details or "") for entry in entries), "تغییرِ سوییچ باید توی ممیزی ثبت بشه"

    await admin.tap("admin_toggle_knowledge_gap")
    async with session_scope() as session:
        assert (await get_admin_settings(session)).knowledge_gap_enabled is True
        await admin_role_service.grant_operator(session, OPERATOR_TG_ID, granted_by_telegram_id=ADMIN_TG_ID)

    operator = Chat(main_dp, OPERATOR_TG_ID)
    await operator.tap("admin_toggle_knowledge_gap")
    async with session_scope() as session:
        assert (await get_admin_settings(session)).knowledge_gap_enabled is True, "ادمینِ عملیاتی نباید بتونه این سوییچ رو بزنه"

    print("✅ test_admin_toggle_knowledge_gap_switch PASSED")


async def main() -> None:
    test_pure_marker_and_normalization()
    main_dp, _shop_dp, _bot_manager, main_bot = build_test_dispatchers()
    with patched_ai():
        await test_prompt_instruction_only_when_enabled_and_baseline_unchanged()
        await test_gap_recorded_and_marker_never_reaches_customer(main_bot)
        await test_marker_only_reply_uses_fallback_and_still_records(main_bot)
        await test_switch_off_strips_marker_but_records_nothing(main_bot)
        await test_open_gap_cap_blocks_new_questions_but_counts_repeats()
        await test_concurrent_same_question_stays_one_row()
        await test_owner_flow_answer_dismiss_and_validation(main_dp)
        await test_gap_list_paginates_and_notes_disabled_detection(main_dp)
        await test_other_owner_and_strangers_cannot_touch_gaps(main_dp)
        await test_menu_button_escapes_knowledge_states(main_dp)
        await test_preview_strips_marker_but_never_records(main_dp)
        await test_nightly_report_mentions_new_gaps_only_when_any()
        await test_admin_toggle_knowledge_gap_switch(main_dp)


if __name__ == "__main__":
    asyncio.run(main())
