"""
تست: P39 · باگِ ۱ — هیچ متنِ رباتی نباید نشانه‌یِ Markdown («**bold**») داشته باشد

پوشش:
۱. پویشِ ASTِ هر دو فایلِ متن (رباتِ اصلی + رباتِ فروشگاه): هیچ رشتهٔ غیرِ داکیومنتی نباید
   `**`, `__` یا `~~` داشته باشد (مالکِ محصول همین را در صفحهٔ «زیرمجموعه» دید).
۲. `strip_markdown`: جفت‌ها را می‌زداید، فهرستِ ستاره‌ای را به • تبدیل می‌کند، تیترِ # را
   برمی‌دارد، جفتِ بسته‌نشده را هم پاک می‌کند — و شناسه‌ها (`callback_data`) و ضربِ عددی
   (`۳*۴`) دست‌نخورده می‌مانند.
۳. مسیرِ واقعیِ چتِ مشتری: پاسخِ هوشِ مصنوعی که با `**` می‌آید، تمیز به دستِ مشتری می‌رسد و
   همان متنِ تمیز در تاریخچه می‌نشیند (وگرنه مدلِ دورِ بعد تقلیدش می‌کند).
۴. خروجی‌هایِ AIِ ارباب‌رجوع: clamp_replyِ دستیارِ مدیریتی و خلاصهٔ CRM، و دستورِ تازهٔ
   پرامپت که به مدل می‌گوید قالب‌بندی ننویسد.

اجرا: python3 tests_manual/run_one.py test_p39_no_markdown_markers.py
"""
from __future__ import annotations

import ast
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402
from sqlalchemy import select  # noqa: E402

from harness import FakeSession, build_test_dispatchers, make_message_update, reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.database.models import Customer, TenantMode  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import ai_context, ai_service, conversation_service, crm_summary_service, owner_assistant_service  # noqa: E402
from app.services.ai_service import AiCallResult  # noqa: E402
from app.services.order_detection_service import _CLASSIFIER_USER_PROMPT  # noqa: E402
from app.utils.text_limits import strip_markdown  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TEXT_FILES = (
    ROOT / "app" / "bots" / "main_bot" / "texts.py",
    ROOT / "app" / "bots" / "shop_bot" / "texts.py",
)
MARKERS = ("**", "__", "~~")
OWNER_TG_ID = 7_390_000_011
SHOP_BOT_TG_ID = 7_390_000_012
CUSTOMER_TG_ID = 7_390_000_013
FAKE_BOT_TOKEN = f"{SHOP_BOT_TG_ID}:NOMARKDOWNTOKENFAKEFORTESTS"


def _docstring_nodes(tree: ast.Module) -> set[int]:
    """آی‌دیِ نودهایِ رشته‌ای که داکیومنت‌اند (نه متنِ ارسالی) تا از پویش خارج بمانند."""
    nodes: set[int] = set()
    for item in ast.walk(tree):
        if not isinstance(item, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        body = getattr(item, "body", None)
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
            nodes.add(id(body[0].value))
    return nodes


# ============================================================================= ۱ — متن‌هایِ ثابت
def test_ui_text_files_have_no_markdown_markers() -> None:
    offenders: list[str] = []
    for path in TEXT_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        hidden = _docstring_nodes(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            if id(node) in hidden:
                continue
            if any(marker in node.value for marker in MARKERS):
                offenders.append(f"{path.name}:{node.lineno}: {node.value[:60]!r}")
    assert not offenders, "متن‌هایِ زیر هنوز نشانه‌یِ Markdown دارند:\n" + "\n".join(offenders)
    print("✅ test_ui_text_files_have_no_markdown_markers PASSED")


# ============================================================================= ۲ — پاک‌ساز
def test_strip_markdown_keeps_content_and_identifiers() -> None:
    assert strip_markdown("قیمتِ **مداد** ۱۲٬۰۰۰ تومان است") == "قیمتِ مداد ۱۲٬۰۰۰ تومان است"
    assert strip_markdown("**محصولات:**\n* مداد\n* پاک‌کن") == "محصولات:\n• مداد\n• پاک‌کن"
    assert strip_markdown("### عنوانِ بخش") == "عنوانِ بخش"
    assert strip_markdown("این **جفتِ بسته‌نشده است") == "این جفتِ بسته‌نشده است"
    assert strip_markdown("دکمهٔ `start` با callback_data=x:1 کار می‌کند") == "دکمهٔ start با callback_data=x:1 کار می‌کند"
    assert strip_markdown("مساحت = ۳*۴ متر") == "مساحت = ۳*۴ متر"
    assert strip_markdown("~~حذف‌شده~~ و __مهم__") == "حذف‌شده و مهم"
    assert strip_markdown(None) == "" and strip_markdown("متنِ ساده") == "متنِ ساده"
    print("✅ test_strip_markdown_keeps_content_and_identifiers PASSED")


# ============================================================================= ۳ — چتِ واقعیِ مشتری
class _MarkdownAi:
    async def get_reply(self, system_prompt: str, history, user_message: str) -> AiCallResult:
        if user_message == _CLASSIFIER_USER_PROMPT:
            return AiCallResult(text='{"status": "none"}', total_tokens=9)
        return AiCallResult(text="**قیمتِ مداد** ۱۲٬۰۰۰ تومان است.\n* ارسالِ رایگان\n* گارانتی دارد", total_tokens=30)

    async def analyze_image(self, prompt: str, image_bytes: bytes, mime_type: str = "image/jpeg") -> AiCallResult:
        return AiCallResult(text="تحلیل", total_tokens=1)

    async def transcribe_audio(self, audio_bytes: bytes, filename: str = "voice.ogg") -> str:
        return "رونویسی"


async def test_customer_chat_reply_reaches_without_markers(shop_dp) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    original = ai_service.get_ai_service
    ai_service.get_ai_service = lambda *a, **k: _MarkdownAi()
    try:
        bot = Bot(token=FAKE_BOT_TOKEN, session=FakeSession())
        session_obj: FakeSession = bot.session  # type: ignore[assignment]
        await shop_dp.feed_update(bot, make_message_update(1, text="قیمتِ مداد چنده؟", user_id=CUSTOMER_TG_ID))
        await asyncio.sleep(4.5)
        body = "\n".join(m["text"] for m in session_obj.sent_messages)
        assert body, "هیچ پاسخی به مشتری نرفت"
        assert "**" not in body and "*" not in body, body
        assert "قیمتِ مداد ۱۲٬۰۰۰ تومان است." in body, body
        assert "• ارسالِ رایگان" in body, body
        async with session_scope() as session:
            customer_id = (
                await session.execute(select(Customer.id).where(Customer.telegram_id == CUSTOMER_TG_ID))
            ).scalar_one()
            history = await conversation_service.get_recent_history(session, customer_id, 10)
        assert history and "**" not in history[-1]["content"], history
    finally:
        ai_service.get_ai_service = original
    print("✅ test_customer_chat_reply_reaches_without_markers PASSED")


# ============================================================================= ۴ — سایرِ خروجی‌هایِ AI
def test_owner_facing_ai_replies_are_clamped_clean() -> None:
    assert owner_assistant_service.clamp_reply("**فروشِ** امروز خوب بود") == "فروشِ امروز خوب بود"
    assert crm_summary_service.clamp_reply("**مشتری راضی است**") == "مشتری راضی است"
    assert owner_assistant_service.clamp_reply(None) == "" and owner_assistant_service.clamp_reply("  متن  ") == "متن"
    print("✅ test_owner_facing_ai_replies_are_clamped_clean PASSED")


def test_system_prompt_tells_the_model_not_to_use_markdown() -> None:
    shop_bot = SimpleNamespace(tenant_mode=TenantMode.SALES, ai_instructions=None)
    prompt = ai_context.build_system_prompt(shop_bot, [], None, "دستورِ تست")
    assert "Markdown" in prompt and "•" in prompt, prompt[:400]
    consultation = ai_context.build_system_prompt(
        SimpleNamespace(tenant_mode=TenantMode.CONSULTATION, ai_instructions=None), [], None, "دستورِ تست"
    )
    assert "Markdown" in consultation, consultation[:400]
    print("✅ test_system_prompt_tells_the_model_not_to_use_markdown PASSED")


async def main() -> None:
    _main_dp, shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    test_ui_text_files_have_no_markdown_markers()
    test_strip_markdown_keeps_content_and_identifiers()
    await test_customer_chat_reply_reaches_without_markers(shop_dp)
    test_owner_facing_ai_replies_are_clamped_clean()
    test_system_prompt_tells_the_model_not_to_use_markdown()


if __name__ == "__main__":
    asyncio.run(main())
