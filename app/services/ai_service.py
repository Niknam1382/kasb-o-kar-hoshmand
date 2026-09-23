from __future__ import annotations

import abc
import asyncio
import base64
import dataclasses
import logging
import random
import time

import aiohttp

logger = logging.getLogger(__name__)

DEFAULT_AI_BASE_URL = "https://api.x.ai/v1/chat/completions"

# تلاشِ مجددِ خودکار برای خطاهای موقتیِ سرویسِ هوش مصنوعی (شبکه/تایم‌اوت/۵xx/۴۲۹) —
# قبل از اینکه کلِ مکالمه fail بشه و به مشتری خطا نشون داده بشه.
_MAX_RETRIES = 2
_RETRY_BACKOFF_SECONDS = (1.0, 2.0)

# جلسه‌ی HTTP مشترک که بین همه‌ی فراخوانی‌های هوش مصنوعی بازاستفاده می‌شه، به‌جای
# اینکه هر بار یه aiohttp.ClientSession تازه ساخته بشه (این یکی از دلایل اصلیِ
# مصرف بالای پهنای‌باند/منابع بود).
_http_session: aiohttp.ClientSession | None = None


def _get_http_session() -> aiohttp.ClientSession:
    global _http_session
    if _http_session is None or _http_session.closed:
        _http_session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60))
    return _http_session


async def close_http_session() -> None:
    global _http_session
    if _http_session is not None and not _http_session.closed:
        await _http_session.close()
    _http_session = None


def _derive_audio_url(chat_completions_url: str) -> str:
    """
    از روی آدرس‌ِ chat/completions، آدرسِ audio/transcriptions رو می‌سازه.
    مثلاً https://api.x.ai/v1/chat/completions -> https://api.x.ai/v1/audio/transcriptions
    """
    if "/chat/completions" in chat_completions_url:
        return chat_completions_url.replace("/chat/completions", "/audio/transcriptions")
    base = chat_completions_url.rsplit("/", 1)[0]
    return f"{base}/audio/transcriptions"


class AiServiceError(Exception):
    pass


@dataclasses.dataclass
class AiCallResult:
    """
    نتیجه‌ی یه فراخوانیِ هوش مصنوعی، همراه با مصرفِ توکن (اگه ارائه‌دهنده گزارشش
    کرده باشه) — این توکن‌ها همون چیزیه که سیستمِ کیف‌پول برای کسرِ دقیق و
    وزن‌دار استفاده می‌کنه. اگه ارائه‌دهنده usage برنگردونه، total_tokens برابرِ
    None می‌مونه و لایه‌ی کیف‌پول یه تخمینِ محافظه‌کارانه جایگزینش می‌کنه.
    """

    text: str
    total_tokens: int | None = None


class BaseAiService(abc.ABC):
    @abc.abstractmethod
    async def get_reply(self, system_prompt: str, history: list[dict[str, str]], user_message: str) -> AiCallResult: ...

    @abc.abstractmethod
    async def analyze_image(self, prompt: str, image_bytes: bytes, mime_type: str = "image/jpeg") -> AiCallResult: ...

    @abc.abstractmethod
    async def transcribe_audio(self, audio_bytes: bytes, filename: str = "voice.ogg") -> str: ...


class OpenAiCompatibleAiService(BaseAiService):
    """
    کلاینتی برای هر ارائه‌دهنده‌ای که API سازگار با فرمت OpenAI (chat completions،
    vision، و whisper) بده — از جمله Grok/xAI و ارائه‌دهنده‌های ارزان‌تر مثل GapGPT
    که آدرس‌شون از طریق admin_settings.ai_base_url قابل‌تنظیمه.
    """

    def __init__(self, api_key: str, model: str, base_url: str = DEFAULT_AI_BASE_URL) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    async def get_reply(self, system_prompt: str, history: list[dict[str, str]], user_message: str) -> AiCallResult:
        messages = [{"role": "system", "content": system_prompt}, *history]
        if user_message:
            messages.append({"role": "user", "content": user_message})

        payload = {"model": self.model, "messages": messages}
        data = await self._post_chat(payload)
        return AiCallResult(text=self._extract_text(data), total_tokens=self._extract_usage(data))

    async def analyze_image(self, prompt: str, image_bytes: bytes, mime_type: str = "image/jpeg") -> AiCallResult:
        b64_image = base64.b64encode(image_bytes).decode("ascii")
        data_url = f"data:{mime_type};base64,{b64_image}"

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
        }
        data = await self._post_chat(payload)
        return AiCallResult(text=self._extract_text(data), total_tokens=self._extract_usage(data))

    async def transcribe_audio(self, audio_bytes: bytes, filename: str = "voice.ogg") -> str:
        url = _derive_audio_url(self.base_url)

        last_exc: Exception | None = None
        data: dict | None = None
        for attempt in range(_MAX_RETRIES + 1):
            form = aiohttp.FormData()
            form.add_field("file", audio_bytes, filename=filename, content_type="application/octet-stream")
            form.add_field("model", "whisper-1")
            try:
                session = _get_http_session()
                async with session.post(url, headers=self._headers(), data=form) as resp:
                    if resp.status == 429 or resp.status >= 500:
                        text = await resp.text()
                        last_exc = AiServiceError(f"خطای موقتیِ رونویسی صوتی {resp.status}: {text[:300]}")
                    elif resp.status != 200:
                        text = await resp.text()
                        raise AiServiceError(f"خطای رونویسی صوتی {resp.status}: {text[:300]}")
                    else:
                        data = await resp.json()
                        break
            except AiServiceError:
                raise
            except Exception as exc:
                last_exc = AiServiceError(f"فراخوانی رونویسی صوتی ناموفق بود: {exc}")

            if attempt < _MAX_RETRIES:
                logger.warning("رونویسیِ صوتی ناموفق بود (تلاشِ %s)، دوباره امتحان می‌شه...", attempt + 1)
                await asyncio.sleep(_RETRY_BACKOFF_SECONDS[attempt])

        if data is None:
            raise last_exc

        text = data.get("text")
        if not isinstance(text, str):
            raise AiServiceError(f"پاسخ غیرمنتظره از سرویسِ رونویسی: {data}")
        return text

    async def _post_chat(self, payload: dict) -> dict:
        headers = {**self._headers(), "Content-Type": "application/json"}
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                session = _get_http_session()
                async with session.post(self.base_url, headers=headers, json=payload) as resp:
                    if resp.status == 429 or resp.status >= 500:
                        # خطای موقتی (محدودیتِ نرخ یا مشکلِ سمتِ سرور) — ارزشِ تلاشِ مجدد رو داره
                        text = await resp.text()
                        last_exc = AiServiceError(f"خطای موقتیِ سرویس هوش مصنوعی {resp.status}: {text[:300]}")
                    elif resp.status != 200:
                        # خطای غیرموقتی (مثلاً کلیدِ نامعتبر) — تلاشِ مجدد کمکی نمی‌کنه
                        text = await resp.text()
                        raise AiServiceError(f"خطای سرویس هوش مصنوعی {resp.status}: {text[:300]}")
                    else:
                        return await resp.json()
            except AiServiceError:
                raise
            except Exception as exc:
                last_exc = AiServiceError(f"فراخوانی هوش مصنوعی ناموفق بود: {exc}")

            if attempt < _MAX_RETRIES:
                logger.warning("فراخوانیِ هوش مصنوعی ناموفق بود (تلاشِ %s)، دوباره امتحان می‌شه...", attempt + 1)
                await asyncio.sleep(_RETRY_BACKOFF_SECONDS[attempt])

        raise last_exc

    @staticmethod
    def _extract_text(data: dict) -> str:
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise AiServiceError(f"پاسخ غیرمنتظره از سرویس هوش مصنوعی: {data}") from exc

    @staticmethod
    def _extract_usage(data: dict) -> int | None:
        # نه همه‌ی ارائه‌دهنده‌های سازگار با OpenAI حتماً usage برمی‌گردونن؛ اگه
        # نبود، None برمی‌گردونیم و لایه‌ی کیف‌پول خودش یه تخمینِ محافظه‌کارانه
        # (بر اساسِ طولِ متن) جایگزین می‌کنه، به‌جای اینکه کل فراخوانی fail بشه.
        usage = data.get("usage")
        if not isinstance(usage, dict):
            return None
        total = usage.get("total_tokens")
        return int(total) if isinstance(total, (int, float)) else None


class FallbackAiService(BaseAiService):
    """
    اگه سرویسِ اصلی (حتی بعد از تلاشِ مجددِ خودش) شکست بخوره، یه‌بار با
    سرویسِ پشتیبان (کلید/مدل/آدرسِ جداگانه که ادمین در تنظیمات مشخص کرده)
    امتحان می‌کنه — تا یه قطعیِ گذرای ارائه‌دهنده‌ی اصلی، کلِ مکالمه‌ی مشتری
    رو از کار نندازه. اگه پشتیبان تنظیم نشده باشه، اصلاً ساخته نمی‌شه.
    """

    def __init__(self, primary: BaseAiService, fallback: BaseAiService) -> None:
        self._primary = primary
        self._fallback = fallback

    async def get_reply(self, system_prompt: str, history: list[dict[str, str]], user_message: str) -> AiCallResult:
        try:
            return await self._primary.get_reply(system_prompt, history, user_message)
        except AiServiceError:
            logger.warning("سرویسِ اصلیِ هوش مصنوعی شکست خورد؛ تلاش با سرویسِ پشتیبان...")
            return await self._fallback.get_reply(system_prompt, history, user_message)

    async def analyze_image(self, prompt: str, image_bytes: bytes, mime_type: str = "image/jpeg") -> AiCallResult:
        try:
            return await self._primary.analyze_image(prompt, image_bytes, mime_type)
        except AiServiceError:
            logger.warning("سرویسِ اصلیِ تحلیلِ عکس شکست خورد؛ تلاش با سرویسِ پشتیبان...")
            return await self._fallback.analyze_image(prompt, image_bytes, mime_type)

    async def transcribe_audio(self, audio_bytes: bytes, filename: str = "voice.ogg") -> str:
        try:
            return await self._primary.transcribe_audio(audio_bytes, filename)
        except AiServiceError:
            logger.warning("سرویسِ اصلیِ رونویسیِ صوتی شکست خورد؛ تلاش با سرویسِ پشتیبان...")
            return await self._fallback.transcribe_audio(audio_bytes, filename)


def get_ai_service(
    api_key: str,
    model: str,
    base_url: str = DEFAULT_AI_BASE_URL,
    fallback_api_key: str | None = None,
    fallback_model: str | None = None,
    fallback_base_url: str | None = None,
) -> BaseAiService:
    primary = OpenAiCompatibleAiService(api_key, model, base_url)
    if fallback_api_key and fallback_model:
        fallback = OpenAiCompatibleAiService(fallback_api_key, fallback_model, fallback_base_url or DEFAULT_AI_BASE_URL)
        return FallbackAiService(primary, fallback)
    return primary


# =============================================================================
# استخرِ چند کلید + مدارِ قطعِ هوشمند (Circuit Breaker)
# =============================================================================
#
# حالتِ مدارِ قطع، عمداً in-memory و سطحِ پردازه‌ست (نه توی دیتابیس) — چون
# هدفش محافظت از خودِ این پردازه در برابرِ کوبیدنِ مداومِ یه کلیدِ خراب به
# سرویسِ AIه، نه یه رکوردِ دائمی. با ری‌استارتِ اپ، مدارها دوباره بسته
# می‌شن (که درسته: شاید مشکلِ کلید موقتی بوده).

_CIRCUIT_FAILURE_THRESHOLD = 5  # این‌قدر شکستِ پیاپی لازمه تا مدار باز بشه
_CIRCUIT_COOLDOWN_SECONDS = 60.0  # مدت‌زمانی که یه مدارِ بازشده، بازمی‌مونه


@dataclasses.dataclass
class _CircuitState:
    consecutive_failures: int = 0
    open_until: float = 0.0  # time.monotonic() — ۰ یعنی مدار بسته‌ست


_circuit_states: dict[int, _CircuitState] = {}


def _circuit_is_open(key_id: int) -> bool:
    state = _circuit_states.get(key_id)
    if state is None:
        return False
    return time.monotonic() < state.open_until


def _record_circuit_success(key_id: int) -> None:
    _circuit_states.pop(key_id, None)


def _record_circuit_failure(key_id: int) -> None:
    state = _circuit_states.setdefault(key_id, _CircuitState())
    state.consecutive_failures += 1
    if state.consecutive_failures >= _CIRCUIT_FAILURE_THRESHOLD:
        newly_opened = state.open_until == 0.0
        state.open_until = time.monotonic() + _CIRCUIT_COOLDOWN_SECONDS
        if newly_opened:
            logger.error(
                "مدارِ قطع برای یه کلیدِ AI باز شد (پس از %d شکستِ پیاپی) — تا %d ثانیه دیگه امتحان نمی‌شه.",
                state.consecutive_failures,
                int(_CIRCUIT_COOLDOWN_SECONDS),
            )


def reset_all_circuits_for_tests() -> None:
    """فقط برای تست: بینِ تست‌های مختلف حالتِ مدارِ قطع رو ریست می‌کنه."""
    _circuit_states.clear()


class PooledAiService(BaseAiService):
    """
    یه استخر از N سرویسِ AI (هرکدوم با کلید/مدل/آدرسِ خودش). هر فراخوانی از
    یه نقطه‌ی تصادفی توی استخر شروع می‌کنه (برای پخشِ یکنواختِ بار بینِ
    کلیدها) و کلیدهایی که مدارشون باز باشه رو رد می‌کنه. اگه یه کلید شکست
    بخوره، بلافاصله کلیدِ بعدی امتحان می‌شه؛ فقط اگه *همه* شکست بخورن یا
    مدارشون باز باشه، خطای آخر رو بالا می‌ده.
    """

    def __init__(self, entries: list[tuple[int, BaseAiService]]) -> None:
        if not entries:
            raise ValueError("PooledAiService به حداقل یه کلید نیاز داره")
        self._entries = entries

    def _ordered_entries(self) -> list[tuple[int, BaseAiService]]:
        start = random.randrange(len(self._entries))
        return self._entries[start:] + self._entries[:start]

    async def _run(self, method_name: str, *args) -> object:
        last_exc: Exception | None = None
        tried_any = False
        for key_id, service in self._ordered_entries():
            if _circuit_is_open(key_id):
                continue
            tried_any = True
            try:
                result = await getattr(service, method_name)(*args)
                _record_circuit_success(key_id)
                return result
            except AiServiceError as exc:
                _record_circuit_failure(key_id)
                last_exc = exc
                logger.warning("یه کلیدِ AI در استخر شکست خورد (%s)، امتحانِ کلیدِ بعدی...", method_name)

        if not tried_any:
            raise AiServiceError("همه‌ی کلیدهای AI در استخر موقتاً مدارشون بازه (شکست‌های پیاپیِ اخیر).")
        raise last_exc or AiServiceError("همه‌ی کلیدهای استخرِ AI شکست خوردن.")

    async def get_reply(self, system_prompt: str, history: list[dict[str, str]], user_message: str) -> AiCallResult:
        return await self._run("get_reply", system_prompt, history, user_message)

    async def analyze_image(self, prompt: str, image_bytes: bytes, mime_type: str = "image/jpeg") -> AiCallResult:
        return await self._run("analyze_image", prompt, image_bytes, mime_type)

    async def transcribe_audio(self, audio_bytes: bytes, filename: str = "voice.ogg") -> str:
        return await self._run("transcribe_audio", audio_bytes, filename)
