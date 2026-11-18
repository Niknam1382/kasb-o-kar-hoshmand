"""پ۱۲۲ · رفتارِ سقفِ حجمِ ویسِ مشتری بالاخره تست شد (قفلِ «NOT RUN»ِ پ۱۱۸).

پ۱۱۸ دو چیز ساخت: `MAX_VOICE_BYTES = ۴ مگابایت` در `customer_voice` و `texts.VOICE_TOO_BIG`، و در
`docs/changelog-p118.md` صادقانه نوشت که **بی‌تست** ماند (هندلرِ ویس برایِ صدا زدنِ مستقیم، Botِ
توکن‌مت لازم دارد). این فایل همان هندلر را با یکِ رباتِ جعلیِ کوچک صدا می‌زند و سه حالت را می‌بندد:

۱. `voice.file_size` اعلامی بزرگ ⇒ پیامِ «ویس خیلی بزرگ است» و **هیچ دانلودی انجام نمی‌شود**.
۲. `file_size` اعلامی کوچک ولی حجمِ واقعیِ دانلودشده بزرگ ⇒ همان پیام، و **بی‌AI و بی‌کسرِ کیف‌پول**
   (در همین فاز بازبینیِ دوم رویِ حجمِ واقعی افزوده شد، چون متادیتا می‌تواند دروغ باشد).
۳. ویسِ معمولی ⇒ رونویسی می‌شود، هزینهٔ صوت دقیقاً یک بار کم می‌شود و متنِ رونویسی‌شده به
   جریانِ پاسخِ AI می‌رود.

اجرا: python3 tests_manual/run_one.py test_p122_voice_size_cap.py
"""
from __future__ import annotations

import asyncio
import io
import sys
from types import SimpleNamespace

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from harness import reset_database  # noqa: E402
from phase4_helpers import owner_balance, wallet_transactions  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.shop_bot import texts as shop_texts  # noqa: E402
from app.bots.shop_bot.handlers import customer as customer_module  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import admin_settings_service, ai_pool_service, wallet_service  # noqa: E402

OWNER_TG = 12_200_001
SHOP_BOT_TG = 12_200_002
CUSTOMER_TG = 12_200_003
OVER_SIZE = customer_module.MAX_VOICE_BYTES + 1024
REASON = wallet_service.WalletTransactionReason.VOICE_TRANSCRIPTION


class _Transport:
    """جایِ `Bot`ِ رویِ پیام: `id` برایِ یافتنِ فروشگاه، `download` برایِ ویس، `send_message` برایِ اخطارها."""

    def __init__(self, *, payload: bytes, declared_size: int | None) -> None:
        self.id = SHOP_BOT_TG
        self.token = "12200002:" + "A" * 32
        self.payload = payload
        self.declared_size = declared_size
        self.downloads = 0
        self.sent: list[tuple[int, str]] = []

    async def download(self, file_id: str) -> io.BytesIO:
        self.downloads += 1
        return io.BytesIO(self.payload)

    async def send_message(self, chat_id: int, text: str, **kwargs):
        self.sent.append((int(chat_id), text))
        return SimpleNamespace(message_id=99)


class _Ai:
    def __init__(self, transcript: str = "یک کیلو چای می‌خوام") -> None:
        self.transcript = transcript
        self.calls = 0

    async def transcribe_audio(self, audio_bytes: bytes, filename: str = "voice.ogg") -> str:
        self.calls += 1
        return self.transcript


class _Message:
    def __init__(self, transport: _Transport) -> None:
        self.bot = transport
        self.voice = SimpleNamespace(file_id="voice-1", file_size=transport.declared_size, duration=42)
        self.from_user = SimpleNamespace(id=CUSTOMER_TG, first_name="مشتری", username="customer", last_name=None)
        self.message_id = 7
        self.chat = SimpleNamespace(id=CUSTOMER_TG)
        self.answers: list[str] = []

    async def answer(self, text: str, **kwargs):
        self.answers.append(text)
        return SimpleNamespace(message_id=1)


async def _run_voice(transport: _Transport, ai: _Ai) -> tuple[list[str], list[str], int]:
    """هندلر را مستقیم اجرا می‌کند؛ استخرِ AI و زمان‌بندِ پاسخِ AI جعلی‌اند تا تست قطعی بماند."""
    scheduled: list[str] = []

    async def fake_build(*args, **kwargs):
        return ai

    def fake_schedule(shop_bot_id, customer_tg_id, text, *args, **kwargs):
        scheduled.append(text)

    original_build = ai_pool_service.build_ai_service
    original_schedule = customer_module._schedule_debounced_processing
    ai_pool_service.build_ai_service = fake_build
    customer_module._schedule_debounced_processing = fake_schedule
    message = _Message(transport)
    try:
        async with session_scope() as session:
            await customer_module.customer_voice(message, session, transport)
            await session.commit()
    finally:
        ai_pool_service.build_ai_service = original_build
        customer_module._schedule_debounced_processing = original_schedule
    return message.answers, scheduled, ai.calls


async def _fresh_shop() -> int:
    await reset_database()
    admin_settings_service.reset_read_cache()
    customer_module._pending_buffers.clear()
    customer_module._pending_tasks.clear()
    return await seed_usable_shop(OWNER_TG, SHOP_BOT_TG)


# ============================================================================= ۱ — اعلامِ دروغِ بزرگ
async def test_declared_oversize_voice_is_never_downloaded() -> None:
    await _fresh_shop()
    transport = _Transport(payload=b"x" * 128, declared_size=OVER_SIZE)
    before = await owner_balance(OWNER_TG)

    answers, scheduled, calls = await _run_voice(transport, _Ai())
    assert answers == [shop_texts.VOICE_TOO_BIG], answers
    assert transport.downloads == 0, "ویسِ بزرگ‌تر ازِ سقف نباید اصلاً دانلود شود"
    assert calls == 0 and scheduled == []
    assert await owner_balance(OWNER_TG) == before
    assert not await wallet_transactions(REASON)
    print("✅ test_declared_oversize_voice_is_never_downloaded PASSED")


# ============================================================================= ۲ — اعلامِ کوچک، بدنهٔ بزرگ
async def test_real_oversize_voice_stops_before_ai_and_billing() -> None:
    await _fresh_shop()
    transport = _Transport(payload=b"y" * OVER_SIZE, declared_size=1024)
    before = await owner_balance(OWNER_TG)

    answers, scheduled, calls = await _run_voice(transport, _Ai())
    assert answers == [shop_texts.VOICE_TOO_BIG], answers
    assert transport.downloads == 1
    assert calls == 0, "فایلِ ردشده نباید به سرویسِ تبدیلِ صوت برود"
    assert scheduled == []
    assert await owner_balance(OWNER_TG) == before, "ویسِ ردشده نباید هزینه داشته باشد"
    assert not await wallet_transactions(REASON)
    print("✅ test_real_oversize_voice_stops_before_ai_and_billing PASSED")


# ============================================================================= ۳ — مسیرِ عادی
async def test_normal_voice_is_transcribed_billed_once_and_forwarded() -> None:
    await _fresh_shop()
    transport = _Transport(payload=b"z" * 4096, declared_size=4096)
    ai = _Ai()
    before = await owner_balance(OWNER_TG)

    answers, scheduled, calls = await _run_voice(transport, ai)
    assert calls == 1, "رونویسی باید دقیقاً یک بار صدا زده شود"
    assert scheduled == [ai.transcript], f"متنِ رونویسی‌شده به جریانِ پاسخ نرفت: {scheduled}"
    rows = await wallet_transactions(REASON)
    assert len(rows) == 1, [r.idempotency_key for r in rows]
    assert await owner_balance(OWNER_TG) < before, "هزینهٔ صوت کم نشد"
    print("✅ test_normal_voice_is_transcribed_billed_once_and_forwarded PASSED")


async def main() -> None:
    await test_declared_oversize_voice_is_never_downloaded()
    await test_real_oversize_voice_stops_before_ai_and_billing()
    await test_normal_voice_is_transcribed_billed_once_and_forwarded()
    await asyncio.sleep(0)


if __name__ == "__main__":
    asyncio.run(main())
