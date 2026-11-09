"""
تست: P18 · A4 — استخرِ AI با زنجیره‌یِ مدل برایِ هر کلید (چت/بینایی/صوت).

پوششِ داده‌شده:
* فهرستِ مدل‌هایِ پشتیبان: تجزیه، ترتیب، حذفِ تکراری، سقفِ ۵ مورد.
* اول مدل‌هایِ پشتیبانِ *همان کلید* امتحان می‌شوند، بعد کلیدِ بعدیِ استخر.
* سلامت/cooldown به‌ازایِ (کلید + مدل) است ⇒ مدلِ خراب، کلِ کلید را از روتیشن بیرون نمی‌کند.
* قابلیتِ `stt` فقط ورودی‌هایِ stt را برمی‌دارد و مسیرِ قدیمی همان whisper-1 می‌ماند.
* پنلِ ادمین: خطِ ششمِ افزودنِ کلید و دکمه‌یِ «🧵 مدل‌هایِ پشتیبان».

اجرا: python3 tests_manual/test_p18_ai_model_pool.py
"""
from __future__ import annotations

import asyncio
import pathlib
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402
from sqlalchemy import text  # noqa: E402

from harness import FakeSession, build_test_dispatchers, make_callback_update, make_message_update, reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot import texts as main_texts  # noqa: E402
from app.database.models import AiApiKeyPoolEntry, AiKeyCapability  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import ai_pool_service, ai_service  # noqa: E402
from app.services.admin_settings_service import get_admin_settings  # noqa: E402
from app.services.ai_service import AiCallResult, AiServiceError  # noqa: E402

ADMIN_TG_ID = 12345
MAIN_TOKEN = "000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS"


class _FakeClient:
    """جایِ OpenAiCompatibleAiService: هر فراخوانی را ضبط می‌کند و طبقِ self.fail_on خطا می‌دهد."""

    instances: list["_FakeClient"] = []
    fail_on: frozenset[str] = frozenset()

    def __init__(self, api_key: str, model: str, base_url: str = ai_service.DEFAULT_AI_BASE_URL) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.calls: list[str] = []
        _FakeClient.instances.append(self)

    def _check(self, method: str) -> None:
        self.calls.append(method)
        if self.model in _FakeClient.fail_on:
            raise AiServiceError(f"مدلِ {self.model} شکست خورد")

    async def get_reply(self, system_prompt, history, user_message) -> AiCallResult:
        self._check("get_reply")
        return AiCallResult(text=self.model, total_tokens=7)

    async def analyze_image(self, prompt, image_bytes, mime_type="image/jpeg") -> AiCallResult:
        self._check("analyze_image")
        return AiCallResult(text=self.model, total_tokens=7)

    async def transcribe_audio(self, audio_bytes, filename="voice.ogg") -> str:
        self._check("transcribe_audio")
        return self.model


def _entry(model: str, fallbacks: str = "", capability: str = "chat") -> AiApiKeyPoolEntry:
    # شیءِ transient (ذخیره‌نشده) — model_chain فقط مدل‌ها را می‌خواند.
    return AiApiKeyPoolEntry(label="l", api_key="k", model=model, fallback_models=fallbacks, base_url="u", capability=capability)


def _patch_clients():
    _FakeClient.instances = []
    original = ai_service.OpenAiCompatibleAiService
    ai_service.OpenAiCompatibleAiService = _FakeClient
    return original


# ============================================================================= ۱ — تجزیه و ترتیب
def test_parse_model_list_normalizes_and_caps() -> None:
    assert ai_pool_service.parse_model_list("a, b، c;d\ne") == ["a", "b", "c", "d", "e"], "جداکننده‌هایِ مخلوط و ویرگولِ فارسی"
    assert ai_pool_service.parse_model_list("a ,a,  a") == ["a"], "تکراری حذف می‌شود"
    assert ai_pool_service.parse_model_list(None) == [] and ai_pool_service.parse_model_list("   ") == []
    long = ", ".join(f"m{i}" for i in range(12))
    assert len(ai_pool_service.parse_model_list(long)) == ai_pool_service.MAX_FALLBACK_MODELS, "سقفِ هزینه/تأخیر"
    huge = ai_pool_service.parse_model_list("x" * 5000)
    assert huge == ["x" * ai_pool_service.MAX_MODEL_NAME_LENGTH], "نامِ مدل هم باید بریده شود (ورودیِ مخرب)"
    print("✅ test_parse_model_list_normalizes_and_caps PASSED")


def test_model_chain_puts_primary_first() -> None:
    assert ai_pool_service.model_chain(_entry("deepseek-chat", "glm-4-flash, qwen-plus")) == ["deepseek-chat", "glm-4-flash", "qwen-plus"]
    assert ai_pool_service.model_chain(_entry("deepseek-chat", "deepseek-chat, x")) == ["deepseek-chat", "x"], "تکرارِ مدلِ اصلی حذف"
    assert ai_pool_service.model_chain(_entry("m1", "")) == ["m1"], "بدونِ پشتیبان ⇒ همان رفتارِ قبل"
    print("✅ test_model_chain_puts_primary_first PASSED")


# ============================================================================= ۲ — fallback داخلِ همان کلید
async def test_fallback_models_of_same_key_are_tried_first() -> None:
    ai_service.reset_all_circuits_for_tests()
    original = _patch_clients()
    _FakeClient.fail_on = frozenset({"m1"})
    try:
        chain = ai_service.ModelChainAiService(11, "k", "u", ai_pool_service.model_chain(_entry("m1", "m2, m3")))
        result = await chain.get_reply("s", [], "hi")
    finally:
        ai_service.OpenAiCompatibleAiService = original
        _FakeClient.fail_on = frozenset()

    assert result.text == "m2", "باید اولین مدلِ سالمِ همان کلید برگردد"
    order = [c.model for c in _FakeClient.instances if c.calls]
    assert order[:2] == ["m1", "m2"], f"ترتیبِ امتحان: {order}"
    assert not any(c.calls and c.model == "m3" for c in _FakeClient.instances), "بعد از موفقیت نباید ادامه دهد"
    assert ai_service._circuit_is_open(11, "m1") is False, "یک شکست مدار را باز نمی‌کند"
    print("✅ test_fallback_models_of_same_key_are_tried_first PASSED")


async def test_circuit_is_per_key_and_model() -> None:
    """پنج شکستِ پیاپی فقط همان (کلید، مدل) را خاموش می‌کند، نه کلِ کلید را."""
    ai_service.reset_all_circuits_for_tests()
    original = _patch_clients()
    _FakeClient.fail_on = frozenset({"bad"})
    try:
        chain = ai_service.ModelChainAiService(21, "k", "u", ["bad", "good"])
        for _ in range(ai_service._CIRCUIT_FAILURE_THRESHOLD):
            await chain.get_reply("s", [], "hi")
        assert ai_service._circuit_is_open(21, "bad"), "مدلِ خراب باید در cooldown برود"
        assert not ai_service._circuit_is_open(21, "good"), "مدلِ سالمِ همان کلید نباید تحت‌تأثیر باشد"
        assert not ai_service._circuit_is_open(21), "خودِ کلید نباید از روتیشن خارج شود"
        assert chain.is_available() is True

        _FakeClient.instances = []
        result = await chain.get_reply("s", [], "hi")
        assert result.text == "good", "بعد از cooldown، فقط مدلِ سالمِ همان کلید صدا زده می‌شود"
        assert all(not c.calls for c in _FakeClient.instances if c.model == "bad"), "مدلِ در cooldown نباید دوباره صدا زده شود"
    finally:
        ai_service.OpenAiCompatibleAiService = original
        _FakeClient.fail_on = frozenset()
        ai_service.reset_all_circuits_for_tests()
    print("✅ test_circuit_is_per_key_and_model PASSED")


async def test_pool_moves_to_next_key_after_whole_chain_fails() -> None:
    """وقتی همه‌یِ مدل‌هایِ کلیدِ اول می‌افتند، کلیدِ دوم امتحان می‌شود؛ و کلیدی که همه‌یِ مدل‌هایش
    در cooldown اند، بدونِ ثبتِ شکست رد می‌شود.

    P47: نقطهٔ شروعِ پیمایش دیگر «تصادفی» نیست؛ کم‌بارترینِ کلید با نشانگرِ چرخشی انتخاب می‌شود.
    پس به‌جایِ قفلِ کردنِ انتخابِ تصادفی، state استخر را صفر می‌کنیم تا اولینِ درخواست
    از کلیدِ اول شروع شود (چرخشِ واقعی در `test_p47_ai_key_load_balance.py` سنجیده می‌شود).
    """
    ai_service.reset_all_circuits_for_tests()
    original = _patch_clients()
    _FakeClient.fail_on = frozenset({"a1", "a2"})
    try:
        key_a = ai_service.ModelChainAiService(1, "ka", "u", ["a1", "a2"])
        key_b = ai_service.ModelChainAiService(2, "kb", "u", ["b1"])
        pooled = ai_service.PooledAiService([(1, key_a), (2, key_b)])
        ai_service.reset_pool_state_for_tests()  # شروعِ قطعی از کلیدِ خراب
        result = await pooled.get_reply("s", [], "hi")
        assert result.text == "b1", "بعد از آخرین مدلِ کلیدِ اول باید به کلیدِ دوم برود"
        tried = [c.model for c in _FakeClient.instances if c.calls]
        assert tried == ["a1", "a2", "b1"], tried

        # حالا مدلِ تنهایِ کلیدِ دوم هم می‌افتد ⇒ شکست‌ها رویِ (کلید، مدل) شمرده می‌شوند
        _FakeClient.fail_on = frozenset({"a1", "a2", "b1"})
        for _ in range(ai_service._CIRCUIT_FAILURE_THRESHOLD):
            try:
                await pooled.get_reply("s", [], "hi")
            except AiServiceError:
                pass
        assert ai_service._circuit_is_open(1, "a1") and ai_service._circuit_is_open(1, "a2"), (
            "هر دو مدلِ کلیدِ اول باید بعد از ۵ شکستِ پیاپی خاموش شده باشند"
        )
        assert not key_a.is_available(), "هیچ مدلِ سالمی از کلیدِ اول نمانده"
        assert not key_b.is_available(), "کلیدِ دوم هم همه‌یِ مدل‌هایش را از دست داد"

        # وقتی همه در cooldown اند، استخر پیامِ روشن می‌دهد (نه KeyError/None)
        try:
            await pooled.get_reply("s", [], "hi")
        except AiServiceError as exc:
            assert "مدارشون بازه" in str(exc), str(exc)
        else:
            raise AssertionError("استخرِ کاملاً سرد باید AiServiceError بدهد")
    finally:
        ai_service.OpenAiCompatibleAiService = original
        _FakeClient.fail_on = frozenset()
        ai_service.reset_all_circuits_for_tests()
        ai_service.reset_pool_state_for_tests()
    print("✅ test_pool_moves_to_next_key_after_whole_chain_fails PASSED")


# ============================================================================= ۳ — استخرِ صوت
async def test_stt_pool_ignores_chat_and_both_entries() -> None:
    await reset_database()
    await seed_usable_shop(999_901, 999_902)
    async with session_scope() as session:
        await ai_pool_service.add_entry(session, "chat key", "sk-1", "glm-4-flash", "https://x/v1/chat/completions", "chat")
        await ai_pool_service.add_entry(session, "both key", "sk-2", "glm-4v", "https://x/v1/chat/completions", "both")
        stt = await ai_pool_service.add_entry(session, "voice key", "sk-3", " whisper-1 ", "https://x/v1/chat/completions", "stt", "va, vb")
        assert (await ai_pool_service.get_active_entries_for_capability(session, "stt")) == [stt], "only stt entries"
        got = await ai_pool_service.build_ai_service(session, await get_admin_settings(session), "stt")
        assert isinstance(got, ai_service.ModelChainAiService), type(got)
        assert got.models == ["whisper-1", "va", "vb"], got.models
        assert got.key_id == stt.id
    print("✅ test_stt_pool_ignores_chat_and_both_entries PASSED")


async def test_legacy_voice_keeps_whisper_default() -> None:
    """استخرِ خالی ⇒ همان مسیرِ قدیمی، با مدلِ whisper-1 (رفتارِ قبل از A4 دست‌نخورده)."""
    await reset_database()
    await seed_usable_shop(999_911, 999_912)
    seen: list[tuple] = []
    original = ai_service.get_ai_service

    def _spy(api_key, model, base_url=None, fallback_api_key=None, fallback_model=None, fallback_base_url=None):
        seen.append((model, fallback_model))
        return _FakeClient("k", model, base_url or ai_service.DEFAULT_AI_BASE_URL)

    ai_service.get_ai_service = _spy
    original_client = ai_service.OpenAiCompatibleAiService
    ai_service.OpenAiCompatibleAiService = _FakeClient
    try:
        async with session_scope() as session:
            admin_settings = await get_admin_settings(session)
            admin_settings.ai_api_key = "sk-legacy"
            await session.commit()
        async with session_scope() as session:
            got = await ai_pool_service.build_ai_service(session, await get_admin_settings(session), "stt")
            assert got is not None
            assert seen == [(ai_service.DEFAULT_STT_MODEL, None)], seen
            assert ai_service.DEFAULT_STT_MODEL == "whisper-1"
    finally:
        ai_service.get_ai_service = original
        ai_service.OpenAiCompatibleAiService = original_client
    print("✅ test_legacy_voice_keeps_whisper_default PASSED")


def test_hardcoded_whisper_is_gone_from_the_client() -> None:
    source = pathlib.Path("app/services/ai_service.py").read_text(encoding="utf-8")
    assert 'form.add_field("model", self.model)' in source, "رونویسی باید مدلِ همون ورودیِ استخر را بفرستد"
    assert 'form.add_field("model", "whisper-1")' not in source
    print("✅ test_hardcoded_whisper_is_gone_from_the_client PASSED")


# ============================================================================= ۴ — پنلِ ادمین
async def test_admin_add_entry_with_sixth_line_and_stt(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(999_921, 999_922)
    main_bot = Bot(token=MAIN_TOKEN, session=FakeSession())

    await main_dp.feed_update(main_bot, make_callback_update(1, data="ai_pool_add", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(
        main_bot,
        make_message_update(
            2,
            text="voice key\nsk-3\nwhisper-1\nhttps://x/v1/chat/completions\nstt\nscribe-v2, faster-whisper",
            user_id=ADMIN_TG_ID,
        ),
    )

    async with session_scope() as session:
        entry = (await ai_pool_service.get_all_entries(session))[0]
        cap = entry.capability.value if hasattr(entry.capability, "value") else entry.capability
        assert cap == AiKeyCapability.STT.value
        assert entry.fallback_models == "scribe-v2, faster-whisper", entry.fallback_models
        assert entry.api_key == "sk-3", "رمزنگاری باید شفاف باشد و مقدارِ اصلی برگردد"
        assert ai_pool_service.model_chain(entry) == ["whisper-1", "scribe-v2", "faster-whisper"]
    print("✅ test_admin_add_entry_with_sixth_line_and_stt PASSED")


async def test_admin_rejects_unknown_capability(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(999_931, 999_932)
    main_bot = Bot(token=MAIN_TOKEN, session=FakeSession())
    session_obj: FakeSession = main_bot.session  # type: ignore[assignment]

    await main_dp.feed_update(main_bot, make_callback_update(1, data="ai_pool_add", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(
        main_bot, make_message_update(2, text="l\nsk-1\nm\nhttps://x/v1\naudio", user_id=ADMIN_TG_ID)
    )
    assert session_obj.sent_messages[-1]["text"] == main_texts.AI_POOL_ENTRY_INVALID_CAPABILITY, session_obj.sent_messages[-1]
    async with session_scope() as session:
        assert await ai_pool_service.get_all_entries(session) == []
    # «stt» پذیرفته می‌شود ولی «audio» نه ⇒ فهرستِ پذیرفته‌شده از خودِ Enum خوانده می‌شود
    assert {item.value for item in AiKeyCapability} == {"chat", "vision", "both", "stt"}
    print("✅ test_admin_rejects_unknown_capability PASSED")


async def test_admin_edits_fallback_models_and_can_clear_them(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(999_941, 999_942)
    main_bot = Bot(token=MAIN_TOKEN, session=FakeSession())
    session_obj: FakeSession = main_bot.session  # type: ignore[assignment]

    async with session_scope() as session:
        entry = await ai_pool_service.add_entry(session, "k", "sk-9", "m-main", "https://x/v1/chat/completions", "chat")
        entry_id = entry.id

    n = 0
    await main_dp.feed_update(main_bot, make_callback_update((n := n + 1), data=f"ai_pool_models:{entry_id}", user_id=ADMIN_TG_ID))
    assert "مدل‌هایِ پشتیبان" in session_obj.sent_messages[-1]["text"]
    await main_dp.feed_update(main_bot, make_message_update((n := n + 1), text="m-second, m-third", user_id=ADMIN_TG_ID))
    async with session_scope() as session:
        stored = await ai_pool_service.get_by_id(session, entry_id)
        assert stored.fallback_models == "m-second, m-third", stored.fallback_models

    await main_dp.feed_update(main_bot, make_callback_update((n := n + 1), data=f"ai_pool_models:{entry_id}", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(main_bot, make_message_update((n := n + 1), text="خالی", user_id=ADMIN_TG_ID))
    async with session_scope() as session:
        stored = await ai_pool_service.get_by_id(session, entry_id)
        assert stored.fallback_models == "", repr(stored.fallback_models)

    # کلیدِ نامعتبر ⇒ هیچ اثری، و state هم آزاد می‌شود
    await main_dp.feed_update(main_bot, make_callback_update((n := n + 1), data="ai_pool_models:999999", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(main_bot, make_message_update((n := n + 1), text="m-x", user_id=ADMIN_TG_ID))
    async with session_scope() as session:
        assert (await ai_pool_service.get_by_id(session, entry_id)).fallback_models == ""
    print("✅ test_admin_edits_fallback_models_and_can_clear_them PASSED")


async def test_pool_api_key_is_encrypted_at_rest() -> None:
    """د(ب): کلیدِ AI هم مثلِ بقیه‌یِ رازها باید در دیتابیس رمزنگاری‌شده بخوابد."""
    await reset_database()
    await seed_usable_shop(999_951, 999_952)
    secret = "sk-super-secret-1234567890"
    async with session_scope() as session:
        entry = await ai_pool_service.add_entry(session, "k", secret, "m1", "https://x/v1/chat/completions", "chat", "m2")
        entry_id = entry.id
        assert entry.api_key == secret, "خواندن باید شفاف باشد"
    async with session_scope() as session:
        raw = (await session.execute(text("SELECT api_key, fallback_models FROM ai_api_key_pool WHERE id = :i"), {"i": entry_id})).one()
    assert secret not in raw[0], "کلیدِ خام نباید در ستون پیدا شود"
    assert raw[0].startswith("gAAAAA"), f"قالبِ Fernet انتظار می‌رفت: {raw[0][:16]}"
    assert raw[1] == "m2", "fallback_models رشته‌یِ معمولی است و رمزنگاری نمی‌خواهد"
    print("✅ test_pool_api_key_is_encrypted_at_rest PASSED")


async def main() -> None:
    test_parse_model_list_normalizes_and_caps()
    test_model_chain_puts_primary_first()
    await test_fallback_models_of_same_key_are_tried_first()
    await test_circuit_is_per_key_and_model()
    await test_pool_moves_to_next_key_after_whole_chain_fails()
    await test_stt_pool_ignores_chat_and_both_entries()
    await test_pool_api_key_is_encrypted_at_rest()
    await test_legacy_voice_keeps_whisper_default()
    test_hardcoded_whisper_is_gone_from_the_client()

    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    await test_admin_add_entry_with_sixth_line_and_stt(main_dp)
    await test_admin_rejects_unknown_capability(main_dp)
    await test_admin_edits_fallback_models_and_can_clear_them(main_dp)


if __name__ == "__main__":
    asyncio.run(main())
