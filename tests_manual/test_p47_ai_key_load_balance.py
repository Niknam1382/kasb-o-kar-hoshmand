"""
تست: P47 · استخرِ ۱۰ کلیدِ AI با سقفِ همزمانیِ هرِ کلید و توزیعِ مساویِ بار.

پوششِ داده‌شده:
* سهمِ مساوی: کلیدهایی که عددی ننوشته‌اند، سقفِ پلتفرم را مساوی بینِ خودشان تقسیم می‌کنند.
* توزیع: با N کلیدِ هم‌سقف، هیچ کلیدی بیش ازِ یکِ درخواستِ هم‌زمان ندارد و همه‌ی کلیدها کار می‌کنند.
* سقفِ هرِ کلید: حتی زیرِ هجومِ درخواست، جایگاهِ کارِ همان کلید از عددِ خودش عبور نمی‌کند.
* صفِ شلوغ: وقتی همه پر باشند، بعد ازِ AI_QUEUE_TIMEOUT_SECONDS خطای «شلوغ» داده می‌شود (نه بی‌نهایت انتظار).
* مدارِ قطع مثلِ قبل کار می‌کند: کلیدِ خراب بعد ازِ پنج شکست کنار گذاشته می‌شود.
* پنل: «کلید ۱ … کلید ۱۰»، سقفِ همزمانی از همان صفحه (نه .env)، سقفِ ۱۰ کلید، انتقالِ کلیدِ قدیمی
  و گاردِ ضدSSRF رویِ آدرسِ هرِ کلید.

اجرا: python3 tests_manual/test_p47_ai_key_load_balance.py
"""
from __future__ import annotations

import asyncio
import pathlib
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402

from harness import FakeSession, build_test_dispatchers, make_callback_update, make_message_update, reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot import texts as main_texts  # noqa: E402
from app.config import settings  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import ai_pool_service, ai_service  # noqa: E402
from app.services.admin_settings_service import get_admin_settings  # noqa: E402
from app.services.ai_service import AiCallResult, AiServiceError  # noqa: E402

ADMIN_TG_ID = 12345
MAIN_TOKEN = "000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS"
PUBLIC_URL = "https://api.example-provider.test/v1/chat/completions"


class _TrackingService:
    """جایِ یکِ کلیدِ AI: جایگاه‌هایِ در حالِ اجرا را می‌شمارد و سقفِ واقعیِ همان کلید را ضبط می‌کند."""

    def __init__(self, key_id: int, tracker: dict[int, dict[str, int]], *, hold: float = 0.01, always_fails: bool = False) -> None:
        self.key_id = key_id
        self.tracker = tracker
        self.hold = hold
        self.always_fails = always_fails

    def _state(self) -> dict[str, int]:
        return self.tracker.setdefault(self.key_id, {"inflight": 0, "peak": 0, "served": 0, "failed": 0})

    async def get_reply(self, system_prompt: str, history: list[dict[str, str]], user_message: str) -> AiCallResult:
        state = self._state()
        state["inflight"] += 1
        state["peak"] = max(state["peak"], state["inflight"])
        try:
            if self.always_fails:
                state["failed"] += 1
                raise AiServiceError(f"کلیدِ {self.key_id} رد شد")
            await asyncio.sleep(self.hold)
            state["served"] += 1
            return AiCallResult(text=f"k{self.key_id}", total_tokens=5)
        finally:
            state["inflight"] -= 1

    async def analyze_image(self, prompt: str, image_bytes: bytes, mime_type: str = "image/jpeg") -> AiCallResult:
        return await self.get_reply(prompt, [], "")

    async def transcribe_audio(self, audio_bytes: bytes, filename: str = "voice.ogg") -> str:
        await self.get_reply("", [], "")
        return f"k{self.key_id}"


def _pool(
    key_ids: list[int], tracker: dict, caps: dict[int, int] | None = None, failing: set[int] | None = None, hold: float = 0.01
) -> ai_service.PooledAiService:
    services = [
        (key_id, _TrackingService(key_id, tracker, hold=hold, always_fails=key_id in (failing or set()))) for key_id in key_ids
    ]
    return ai_service.PooledAiService(services, caps)


async def _fire(pool: ai_service.PooledAiService, count: int) -> list[object]:
    return await asyncio.gather(*[pool.get_reply("s", [], f"m{i}") for i in range(count)], return_exceptions=True)


# ============================================================================= ۱ — سهمِ مساوی
def test_equal_share_math() -> None:
    assert ai_service.equal_share_cap(20, 3) == 7, "سقفِ ۲۰ بینِ ۳ کلید ⇒ ۷ (سقفِ پایینِ همان عدد)"
    assert ai_service.equal_share_cap(20, 1) == 20 and ai_service.equal_share_cap(20, 0) == 20
    assert ai_service.equal_share_cap(3, 10) == 1, "هیچ کلیدی زیرِ یکِ درخواستِ هم‌زمان نمی‌افتد"
    original = settings.ai_max_concurrent_calls
    try:
        settings.ai_max_concurrent_calls = 20
        pool = _pool([1, 2, 3], {})
        assert pool.cap_of(1) == 7, "کلیدی که سقف ننوشته، سهمِ مساوی از سقفِ پلتفرم می‌گیرد"
        assert ai_service.PooledAiService([(1, _TrackingService(1, {}))], {1: 250}).cap_of(1) == 250, "عددِ خودش حرفِ اول را می‌زند"
    finally:
        settings.ai_max_concurrent_calls = original
    print("✅ test_equal_share_math PASSED")


# ============================================================================= ۲ — توزیعِ مساوی و هم‌زمان
async def test_load_spreads_evenly_across_keys() -> None:
    ai_service.reset_all_circuits_for_tests()
    ai_service.reset_pool_state_for_tests()
    tracker: dict[int, dict[str, int]] = {}
    pool = _pool([11, 12, 13, 14], tracker, caps={11: 1, 12: 1, 13: 1, 14: 1})
    results = await _fire(pool, 8)
    assert all(isinstance(r, AiCallResult) for r in results), f"همه باید پاسخ بگیرن: {results}"

    served = [tracker[k]["served"] for k in (11, 12, 13, 14)]
    peaks = [tracker[k]["peak"] for k in (11, 12, 13, 14)]
    assert sum(served) == 8, served
    assert max(peaks) == 1, f"سقفِ هرِ کلید ۱ بود؛ جایگاهِ کارِ اضافه ساخته شد: {peaks}"
    assert all(count >= 1 for count in served), f"هیچ کلیدی بیکار نماند: {served}"
    assert max(served) - min(served) <= 2, f"توزیع باید تقریباً مساوی باشد: {served}"
    print("✅ test_load_spreads_evenly_across_keys PASSED")


async def test_per_key_cap_is_never_exceeded() -> None:
    ai_service.reset_all_circuits_for_tests()
    ai_service.reset_pool_state_for_tests()
    tracker: dict[int, dict[str, int]] = {}
    pool = _pool([21, 22], tracker, caps={21: 3, 22: 1})
    results = await _fire(pool, 20)
    assert all(isinstance(r, AiCallResult) for r in results), f"۲۰ درخواست باید همه جواب بگیرن: {results}"
    assert tracker[21]["peak"] <= 3, f"سقفِ کلید ۲۱ سه است: {tracker[21]}"
    assert tracker[22]["peak"] <= 1, f"سقفِ کلید ۲۲ یک است: {tracker[22]}"
    assert tracker[21]["served"] + tracker[22]["served"] == 20
    print("✅ test_per_key_cap_is_never_exceeded PASSED")


async def test_saturated_pool_gives_up_after_the_queue_timeout() -> None:
    """صفِ شلوغ بی‌نهایت نگه‌داشتنی نیست: بعد ازِ AI_QUEUE_TIMEOUT_SECONDS خطای «شلوغ» می‌دهد."""
    ai_service.reset_all_circuits_for_tests()
    ai_service.reset_pool_state_for_tests()
    tracker: dict[int, dict[str, int]] = {}
    pool = _pool([31], tracker, caps={31: 1}, hold=2.0)
    original = settings.ai_queue_timeout_seconds
    settings.ai_queue_timeout_seconds = 1
    try:
        blocker = asyncio.create_task(pool.get_reply("s", [], "اولی"))
        await asyncio.sleep(0.05)  # جایگاهِ تنهاِ کلید پر می‌شود
        started = asyncio.get_running_loop().time()
        second = await _fire(pool, 1)
        waited = asyncio.get_running_loop().time() - started
        assert isinstance(second[0], AiServiceError), f"کلیدِ پر باید خطای صف بدهد: {second}"
        assert "شلوغ" in str(second[0]), second[0]
        assert waited < 1.9, f"باید حدودِ یکِ ثانیه صبر کند، نه تا بی‌نهایت: {waited:.2f}s"
        assert ai_service.slots_for(31).inflight == 1, "درخواستِ دوم باید جایگاهِ کلید را رفته‌رفته نبسته باشد"
        blocker.cancel()
        try:
            await blocker
        except BaseException:
            pass
        assert ai_service.slots_for(31).inflight == 0, "لغوشدنِ تسک نباید جایگاهِ کارِ کلید را برایِ همیشه پر بگذارد"
    finally:
        settings.ai_queue_timeout_seconds = original
    print("✅ test_saturated_pool_gives_up_after_the_queue_timeout PASSED")


async def test_broken_key_is_still_isolated_by_the_circuit() -> None:
    ai_service.reset_all_circuits_for_tests()
    ai_service.reset_pool_state_for_tests()
    tracker: dict[int, dict[str, int]] = {}
    pool = _pool([41, 42], tracker, caps={41: 10, 42: 10}, failing={41})
    results = await _fire(pool, 6)
    assert all(isinstance(r, AiCallResult) for r in results), "کلیدِ خراب نباید پاسخِ مشتری را از کار بیندازد"
    assert tracker[42]["served"] == 6, tracker
    assert ai_service.circuit_health()["open_keys"] == 1, "پنج شکستِ پیاپی ⇒ مدارِ آنِ کلید باز"
    results = await _fire(pool, 2)
    assert all(isinstance(r, AiCallResult) for r in results)
    assert tracker[41]["failed"] == 5, f"بعد ازِ بازشدنِ مدار نباید به آن کلید زده شود: {tracker[41]}"
    print("✅ test_broken_key_is_still_isolated_by_the_circuit PASSED")


_held_loops: list[object] = []


def _slot_identity_in_new_loop() -> tuple[int, int]:
    """یکِ loopِ تازه (داخلِ رشتهٔ جدا) می‌سازد و شناسهٔ جایگاهِ کارِ کلید را برمی‌گرداند.

    خودِ شیءِ loop هم نگه داشته می‌شود: `id()` یکِ loopِ بسته و زباله‌بردایی‌شده می‌تواند به
    loopِ بعدیِ همان رشته برگردد، و آن‌وقت دو loopِ واقعاً مستقل «یکی» به‌نظر می‌رسیدند
    (این ادعا در سوئیتِ کامل، دو بار پشتِ هم، رویِ ماشینِ تحتِ بار می‌شکست).
    """

    async def _read() -> tuple[int, int]:
        loop = asyncio.get_running_loop()
        _held_loops.append(loop)
        slots = ai_service.slots_for(99_977)
        slots.inflight = 4
        return id(loop), id(slots)

    return asyncio.run(_read())


async def test_pool_state_is_loop_scoped() -> None:
    """`slots_for` برایِ هر event loop یکِ شمارندهٔ مستقل می‌سازد (تست‌ها loopهایِ جدا دارند)."""
    ai_service.reset_pool_state_for_tests()
    _held_loops.clear()
    (loop_a, slots_a), (loop_b, slots_b) = await asyncio.gather(
        asyncio.to_thread(_slot_identity_in_new_loop), asyncio.to_thread(_slot_identity_in_new_loop)
    )
    assert loop_a != loop_b, "دو loopِ مستقل ساخته نشد"
    assert slots_a != slots_b, "جایگاهِ کارِ یکِ کلید نباید بینِ دو loop مشترک بماند"
    registered = {key[0] for key in ai_service._key_slots}
    assert {loop_a, loop_b} <= registered, f"ثبتِ per-loop کامل نیست: {sorted(registered)}"
    print("✅ test_pool_state_is_loop_scoped PASSED")


# ============================================================================= ۳ — عددهایِ ظرفیت و برچسب‌ها
def test_capacity_report_finds_the_bottleneck() -> None:
    entry = ai_pool_service.AiApiKeyPoolEntry
    original = settings.ai_max_concurrent_calls
    try:
        settings.ai_max_concurrent_calls = 40
        small = [entry(label="a", api_key="k", model="m", base_url="u", capability="chat", is_active=True, max_concurrent=5),
                 entry(label="b", api_key="k", model="m", base_url="u", capability="chat", is_active=True, max_concurrent=5)]
        report = ai_pool_service.capacity_report(small)
        assert report == {"keys": 2, "ceiling": 40, "sum_caps": 10, "bottleneck": "keys"}, report
        big = [entry(label="x", api_key="k", model="m", base_url="u", capability="chat", is_active=True, max_concurrent=50) for _ in range(10)]
        assert ai_pool_service.capacity_report(big)["bottleneck"] == "platform"
        assert ai_pool_service.capacity_report([])["sum_caps"] == 0
        assert ai_pool_service.capacity_report(small + [entry(label="off", api_key="k", model="m", base_url="u", capability="chat", is_active=False, max_concurrent=99)])["keys"] == 2
        # سهمِ مساوی وقتی عددی نوشته نشده: ۴۰ بینِ ۳ کلید ⇒ ۱۴ هرکدام ⇒ جمعِ ۴۲ ⇒ گلوگاه پلتفرم
        shares = [entry(label=str(i), api_key="k", model="m", base_url="u", capability="chat", is_active=True, max_concurrent=None) for i in range(3)]
        assert ai_pool_service.capacity_report(shares) == {"keys": 3, "ceiling": 40, "sum_caps": 42, "bottleneck": "platform"}
    finally:
        settings.ai_max_concurrent_calls = original

    assert ai_pool_service.key_cap_label(entry(max_concurrent=25)) == "۲۵ درخواستِ هم‌زمان"
    assert ai_pool_service.key_cap_label(entry(max_concurrent=None)) == "سهمِ مساوی از سقفِ پلتفرم"
    line = main_texts.ai_pool_capacity_line({"keys": 3, "ceiling": 40, "sum_caps": 42, "bottleneck": "platform"})
    assert "گلوگاه" in line and "۴۰" in line, line
    assert main_texts.ai_pool_capacity_line({"keys": 0, "ceiling": 40, "sum_caps": 0, "bottleneck": "keys"}) == ""
    print("✅ test_capacity_report_finds_the_bottleneck PASSED")


def test_key_cap_parsing_accepts_persian_digits_and_rejects_junk() -> None:
    assert ai_pool_service.parse_key_cap("۲۵") == (25, None), "ارقام جلالی هم پذیرفته شود"
    assert ai_pool_service.parse_key_cap("25") == (25, None)
    assert ai_pool_service.parse_key_cap("خالی") == (None, None), "خالی ⇒ سهمِ مساوی، بدونِ خطا"
    assert ai_pool_service.parse_key_cap(None) == (None, None), "خطِ هفتمِ ننوشته ⇒ نه عدد، نه خطا"
    assert ai_pool_service.parse_key_cap("   ") == (None, None), "فضایِ خالی هم «ننوشته» است"
    assert ai_pool_service.parse_key_cap("abc")[1] is not None
    assert ai_pool_service.parse_key_cap("0")[1] is not None
    assert ai_pool_service.parse_key_cap("501")[1] is not None
    assert ai_pool_service.parse_key_cap("۵۰۰") == (500, None)
    assert ai_pool_service.MAX_KEYS == 10 and ai_pool_service.MIN_KEY_CAP == 1 and ai_pool_service.MAX_KEY_CAP == 500
    print("✅ test_key_cap_parsing_accepts_persian_digits_and_rejects_junk PASSED")


# ============================================================================= ۴ — پنلِ ادمین
async def test_admin_adds_key_with_seventh_line_and_edits_cap(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(999_871, 999_872)
    main_bot = Bot(token=MAIN_TOKEN, session=FakeSession())
    session_obj: FakeSession = main_bot.session  # type: ignore[assignment]

    await main_dp.feed_update(main_bot, make_callback_update(1, data="ai_pool_add", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(
        main_bot, make_message_update(2, text=f"کلید دوم\nsk-2\nglm-4-flash\n{PUBLIC_URL}\nchat\n-\n۲۵", user_id=ADMIN_TG_ID)
    )
    async with session_scope() as session:
        entries = await ai_pool_service.get_all_entries(session)
        assert len(entries) == 1, entries
        entry = entries[0]
        assert entry.max_concurrent == 25, entry.max_concurrent
        assert entry.fallback_models == "", "«-» یعنی بدونِ پشتیبان (نباید نامِ مدل شود)"
        entry_id = entry.id

    await main_dp.feed_update(main_bot, make_callback_update(3, data=f"ai_pool_cap:{entry_id}", user_id=ADMIN_TG_ID))
    ask_text = session_obj.sent_messages[-1]["text"]
    assert "سقفِ همزمانی" in ask_text and "۴۰" in ask_text, ask_text
    await main_dp.feed_update(main_bot, make_message_update(4, text="99999", user_id=ADMIN_TG_ID))
    assert "بینِ" in session_obj.sent_messages[-1]["text"], session_obj.sent_messages[-1]["text"]
    async with session_scope() as session:
        assert (await ai_pool_service.get_by_id(session, entry_id)).max_concurrent == 25, "ورودیِ نامعتبر نباید ذخیره شود"

    await main_dp.feed_update(main_bot, make_message_update(5, text="۶۰", user_id=ADMIN_TG_ID))
    async with session_scope() as session:
        assert (await ai_pool_service.get_by_id(session, entry_id)).max_concurrent == 60
    assert session_obj.sent_messages[-2]["text"] == main_texts.AI_POOL_CAP_SAVED

    await main_dp.feed_update(main_bot, make_callback_update(6, data=f"ai_pool_cap:{entry_id}", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(main_bot, make_message_update(7, text="خالی", user_id=ADMIN_TG_ID))
    async with session_scope() as session:
        stored = await ai_pool_service.get_by_id(session, entry_id)
        assert stored.max_concurrent is None, stored.max_concurrent
        assert "سهمِ مساوی" in main_texts.ai_pool_entry_detail_text(stored)
    print("✅ test_admin_adds_key_with_seventh_line_and_edits_cap PASSED")


async def test_admin_panel_lists_keys_with_numbers_and_refuses_an_eleventh(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(999_881, 999_882)
    main_bot = Bot(token=MAIN_TOKEN, session=FakeSession())
    session_obj: FakeSession = main_bot.session  # type: ignore[assignment]

    async with session_scope() as session:
        for index in range(10):
            await ai_pool_service.add_entry(
                session, f"کلید {index}", f"sk-{index}", "m", PUBLIC_URL, "chat", None, 10 + index
            )

    await main_dp.feed_update(main_bot, make_callback_update(1, data="ai_pool_list", user_id=ADMIN_TG_ID))
    edited = session_obj.edited_texts[-1]
    buttons = [b.text for row in edited["reply_markup"].inline_keyboard for b in row]
    assert any(b.startswith("🟢 کلید ۱ ·") for b in buttons), buttons
    assert any(b.startswith("🟢 کلید ۱۰ ·") for b in buttons), buttons
    assert any("همزمان: ۱۰" in b for b in buttons) and any("همزمان: ۱۹" in b for b in buttons), buttons
    text = edited["text"]
    assert "گلوگاه" in text and "۱۰ کلیدِ فعال" in text, text
    assert "۱۴۵" in text, f"جمعِ سقفهایِ ۱۰ تا ۱۹ می‌شود ۱۴۵: {text}"

    await main_dp.feed_update(main_bot, make_callback_update(2, data="ai_pool_add", user_id=ADMIN_TG_ID))
    assert session_obj.answered_callbacks[-1]["text"] == main_texts.AI_POOL_MAX_KEYS_REACHED
    async with session_scope() as session:
        assert len(await ai_pool_service.get_all_entries(session)) == 10
    print("✅ test_admin_panel_lists_keys_with_numbers_and_refuses_an_eleventh PASSED")


async def test_legacy_key_moves_into_the_numbered_pool(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(999_891, 999_892)
    main_bot = Bot(token=MAIN_TOKEN, session=FakeSession())

    async with session_scope() as session:
        admin_settings = await get_admin_settings(session)
        assert admin_settings.ai_api_key, "سیدِ تست یکِ کلیدِ قدیمی ست کرده است"
        legacy_key = admin_settings.ai_api_key

    await main_dp.feed_update(main_bot, make_callback_update(1, data="ai_pool_import", user_id=ADMIN_TG_ID))
    async with session_scope() as session:
        entries = await ai_pool_service.get_all_entries(session)
        assert len(entries) == 1 and entries[0].api_key == legacy_key, entries
        assert (await get_admin_settings(session)).ai_api_key is None, "کلیدِ قدیمی نباید دو بار در گردش بیفتد"
    print("✅ test_legacy_key_moves_into_the_numbered_pool PASSED")


async def test_pool_base_url_keeps_the_ssrf_guard(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(999_901, 999_902)
    main_bot = Bot(token=MAIN_TOKEN, session=FakeSession())
    session_obj: FakeSession = main_bot.session  # type: ignore[assignment]

    for bad_url in ("http://api.example.test/v1/chat/completions", "https://127.0.0.1:8000/v1/chat/completions", "https://192.168.1.20/v1"):
        await main_dp.feed_update(main_bot, make_callback_update(1, data="ai_pool_add", user_id=ADMIN_TG_ID))
        await main_dp.feed_update(main_bot, make_message_update(2, text=f"بد\nsk-x\nm\n{bad_url}\nchat", user_id=ADMIN_TG_ID))
        assert session_obj.sent_messages[-1]["text"] == main_texts.ADMIN_INVALID_AI_URL, bad_url

    async with session_scope() as session:
        assert await ai_pool_service.get_all_entries(session) == [], "هیچ آدرسِ داخلیِ ردشده‌ای نباید ذخیره شود"
    print("✅ test_pool_base_url_keeps_the_ssrf_guard PASSED")


async def test_build_ai_service_uses_per_key_caps(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(999_911, 999_912)
    async with session_scope() as session:
        await ai_pool_service.add_entry(session, "کپی", "sk-pool", "m1", PUBLIC_URL, "chat", None, 77)
        admin_settings = await get_admin_settings(session)
        admin_settings.ai_api_key = None
        service = await ai_pool_service.build_ai_service(session, admin_settings, "chat")
    assert isinstance(service, ai_service.ModelChainAiService), f"تک‌کلید ⇒ استخر نمی‌سازد: {type(service)}"

    async with session_scope() as session:
        await ai_pool_service.add_entry(session, "دومی", "sk-pool-2", "m2", PUBLIC_URL, "chat", None, 130)
        service = await ai_pool_service.build_ai_service(session, await get_admin_settings(session), "chat")
    assert isinstance(service, ai_service.PooledAiService)
    caps = {row["key_id"]: row["cap"] for row in service.load_snapshot()}
    assert 77 in caps.values() and 130 in caps.values(), caps
    print("✅ test_build_ai_service_uses_per_key_caps PASSED")


def test_http_session_is_not_capped_at_the_aiohttp_default() -> None:
    source = pathlib.Path("app/services/ai_service.py").read_text(encoding="utf-8")
    assert "aiohttp.TCPConnector(limit=" in source, "سقفِ سوکتِ پیش‌فرضِ aiohttp (۱۰۰) گلوگاهِ ۲٬۰۰۰ درخواست است"
    assert "ttl_dns_cache" in source
    print("✅ test_http_session_is_not_capped_at_the_aiohttp_default PASSED")


async def main() -> None:
    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    test_equal_share_math()
    await test_load_spreads_evenly_across_keys()
    await test_per_key_cap_is_never_exceeded()
    await test_saturated_pool_gives_up_after_the_queue_timeout()
    await test_broken_key_is_still_isolated_by_the_circuit()
    await test_pool_state_is_loop_scoped()
    test_capacity_report_finds_the_bottleneck()
    test_key_cap_parsing_accepts_persian_digits_and_rejects_junk()
    await test_admin_adds_key_with_seventh_line_and_edits_cap(main_dp)
    await test_admin_panel_lists_keys_with_numbers_and_refuses_an_eleventh(main_dp)
    await test_legacy_key_moves_into_the_numbered_pool(main_dp)
    await test_pool_base_url_keeps_the_ssrf_guard(main_dp)
    await test_build_ai_service_uses_per_key_caps(main_dp)
    test_http_session_is_not_capped_at_the_aiohttp_default()
    print("📊 نتیجه: ۱۴ تستِ P47 (سهمِ مساوی، توزیع، سقفِ هرِ کلید، مدارِ قطع، پنل) PASS")


if __name__ == "__main__":
    asyncio.run(main())
