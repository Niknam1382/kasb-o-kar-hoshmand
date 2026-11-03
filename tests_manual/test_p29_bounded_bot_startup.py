"""
تست: P29-B — راه‌اندازیِ ۵۰۰ ربات نه «همه‌با‌هم» باشد نه «یکی‌یکی» (رفتار عوض نمی‌شود)

عددهایِ MEASURED با `scripts/scale_probe.py` رویِ ۵۰۰ فروشگاه، پیش‌ازاین رفع:
  · حالتِ polling: اوجِ هم‌زمانیِ `delete_webhook` = ۵۰۰ (هر ۵۰۰ ربات در یکِ لحظه به تلگرام زدند)
  · حالتِ webhook: ثبتِ ترتیبی — ۲۰ ربات = ۵٫۰ ثانیه ⇒ ۵۰۰ ربات ≈ ۱۲۵ ثانیه

رفع: یکِ درِ نیمه‌باز (`asyncio.Semaphore(BOT_REGISTER_CONCURRENCY)`) دورِ هر `register` و دورِ
`delete_webhook`ِ اوّلیهٔ هر تسکِ polling. سه چیزی که این فایل قفل می‌کند تا «بهینه‌سازی» به
«باگ» تبدیل نشود:
  ۱. هر فروشگاه همچنان ثبت می‌شود و یکِ تسکِ polling دارد (هیچ‌کس جا نمی‌افتد)
  ۲. همزمانیِ درخواست‌هایِ راه‌اندازی از سقفِ تنظیم‌شده بیشتر نمی‌شود — وگرنه همان گلهٔ
     ۵۰۰تاییِ یک‌لحظه‌ای برمی‌گردد (و Telegram به‌خاطرِ حجمِ درخواست از یکِ IP محدود می‌کند)
  ۳. خطایِ `delete_webhook`ِ یکِ ربات مثلِ قبل فقط لاگ می‌شود و همان ربات به پولینگ ادامه می‌دهد

اجرا: python3 tests_manual/run_one.py test_p29_bounded_bot_startup.py
"""
from __future__ import annotations

import asyncio
import pathlib
import sys
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests_manual"))

from aiogram.exceptions import TelegramAPIError  # noqa: E402

from harness import FakeSession  # noqa: E402

import app.services.bot_manager as bot_manager_module  # noqa: E402
from app.config import RunMode, settings  # noqa: E402
from app.services.bot_manager import ShopBotManager  # noqa: E402
from app.utils.encryption import encrypt_token  # noqa: E402

PARK_FOREVER = 3600.0  # get_updatesِ ساختگی همین‌جا بلوکه می‌شود؛ تسک نباید در تست دورِ خود بچرخد


class StartProbeSession(FakeSession):
    """FakeSession + شمارشِ همزمانیِ درخواست‌هایِ راه‌اندازی (delete/set webhook).

    get_updates شمارشِ همزمانی نمی‌شود، چون عمداً پارک می‌کند؛ چیزی که می‌سنجیم «رَشِ
    راه‌اندازی» است، نه پولینگِ عادیِ هر ربات.
    """

    delete_calls = 0
    set_calls = 0
    poll_calls = 0
    start_inflight = 0
    start_peak = 0
    fail_delete = False

    @classmethod
    def reset(cls) -> None:
        cls.delete_calls = 0
        cls.set_calls = 0
        cls.poll_calls = 0
        cls.start_inflight = 0
        cls.start_peak = 0
        cls.fail_delete = False

    async def make_request(self, bot, method, timeout=None):  # noqa: ANN001
        name = type(method).__name__
        if name == "GetUpdates":
            StartProbeSession.poll_calls += 1
            await asyncio.sleep(PARK_FOREVER)
            return []
        if name in ("DeleteWebhook", "SetWebhook"):
            StartProbeSession.start_inflight += 1
            StartProbeSession.start_peak = max(StartProbeSession.start_peak, StartProbeSession.start_inflight)
            await asyncio.sleep(0.02)  # تا همزمانیِ واقعی دیده شود
            try:
                if name == "DeleteWebhook" and StartProbeSession.fail_delete:
                    raise TelegramAPIError(method="deleteWebhook", message="probe: network down")
                return await super().make_request(bot, method, timeout)
            finally:
                if name == "DeleteWebhook":
                    StartProbeSession.delete_calls += 1
                else:
                    StartProbeSession.set_calls += 1
                StartProbeSession.start_inflight -= 1
        return await super().make_request(bot, method, timeout)


def _shop_bot(index: int) -> SimpleNamespace:
    """ فقط سه چیزی که `register()` از ردیفِ ShopBot می‌خواند (بدونِ دیتابیس)."""
    return SimpleNamespace(
        id=index,
        encrypted_token=encrypt_token(f"{900000000 + index}:" + "A" * 35),
        webhook_secret_token=f"secret-{index}",
    )


def _manager_with_probe(shop_dispatcher) -> ShopBotManager:  # noqa: ANN001
    StartProbeSession.reset()
    bot_manager_module.Bot = lambda token, **kwargs: bot_manager_module.Bot_original(token, session=StartProbeSession())
    return ShopBotManager(shop_dispatcher)


async def _drain(manager: ShopBotManager) -> None:
    tasks = list(manager._polling_tasks.values())
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


async def _wait_deletes(target: int, timeout: float = 8.0) -> None:
    """تسک‌هایِ polling درِ semaphore را بعد از load_all می‌گیرند ⇒ باید تا completion صبر کرد."""
    deadline = asyncio.get_running_loop().time() + timeout
    while StartProbeSession.delete_calls < target:
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError(f"فقط {StartProbeSession.delete_calls} از {target} delete_webhook انجام شد")
        await asyncio.sleep(0.01)


async def test_registration_is_bounded_and_complete(shop_dispatcher) -> None:
    limit = settings.bot_register_concurrency
    rows = [_shop_bot(i + 1) for i in range(limit * 3)]
    manager = _manager_with_probe(shop_dispatcher)
    original_class = bot_manager_module.Bot_original
    try:
        await manager.load_all(rows)
        await _wait_deletes(len(rows))
        assert len(manager.registered_shop_bot_ids()) == len(rows), "هیچ رباتی نباید جا بیفتد"
        assert len(manager._polling_tasks) == len(rows), "هر فروشگاه یک تسکِ polling دارد"
        assert StartProbeSession.delete_calls == len(rows), "هر ربات دقیقاً یک delete_webhook می‌زند"
        assert StartProbeSession.start_peak <= limit, f"همزمانی از سقف ({limit}) گذشت: {StartProbeSession.start_peak}"
        assert StartProbeSession.start_peak > 1, "ثبت نباید دوباره ترتیبی شود (سرعتِ بوتِ ۵۰۰ فروشگاه)"
        assert manager.get_secret(1) == "secret-1"
    finally:
        await _drain(manager)
        bot_manager_module.Bot = original_class
    print("✅ test_registration_is_bounded_and_complete PASSED")


async def test_webhook_mode_is_bounded_too(shop_dispatcher) -> None:
    limit = settings.bot_register_concurrency
    rows = [_shop_bot(i + 1) for i in range(limit * 2)]
    manager = _manager_with_probe(shop_dispatcher)
    original_class = bot_manager_module.Bot_original
    mode_before = settings.run_mode
    settings.run_mode = RunMode.WEBHOOK
    try:
        await manager.load_all(rows)
        assert StartProbeSession.set_calls == len(rows), "در حالتِ webhook برایِ هر ربات یک set_webhook"
        assert len(manager.registered_shop_bot_ids()) == len(rows)
        assert not manager._polling_tasks, "در حالتِ webhook تسکِ polling ساخته نمی‌شود"
        assert StartProbeSession.start_peak <= limit
        assert StartProbeSession.start_peak > 1, "set_webhook ها نباید ترتیبی شوند (۵۰۰×RTT)"
    finally:
        settings.run_mode = mode_before
        await _drain(manager)
        bot_manager_module.Bot = original_class
    print("✅ test_webhook_mode_is_bounded_too PASSED")


async def test_delete_webhook_failure_keeps_the_bot_polling(shop_dispatcher) -> None:
    """همان رفتاری که پیش‌تر داشت: خطایِ حذفِ وب‌هوک فقط لاگ است و polling ادامه می‌یابد."""
    rows = [_shop_bot(i + 1) for i in range(4)]
    manager = _manager_with_probe(shop_dispatcher)
    StartProbeSession.fail_delete = True
    original_class = bot_manager_module.Bot_original
    try:
        await manager.load_all(rows)
        await _wait_deletes(len(rows))
        await asyncio.sleep(0.05)  # تسک‌ها بعد از آزادکردنِ در، وارد get_updates می‌شوند
        assert len(manager.registered_shop_bot_ids()) == len(rows), "خطایِ شبکه نباید ربات را حذف کند"
        assert StartProbeSession.poll_calls == len(rows), "با وجودِ خطا، هر ربات به get_updates می‌رسد"
        assert StartProbeSession.delete_calls == len(rows)
    finally:
        StartProbeSession.fail_delete = False
        await _drain(manager)
        bot_manager_module.Bot = original_class
    print("✅ test_delete_webhook_failure_keeps_the_bot_polling PASSED")


async def test_empty_and_bad_limit_are_safe(shop_dispatcher) -> None:
    """load_all([]) بی‌اثر است و سقفِ نامعتبر (صفر/منفی) به بن‌بست نمی‌انجامد."""
    manager = _manager_with_probe(shop_dispatcher)
    original_class = bot_manager_module.Bot_original
    limit_before = settings.bot_register_concurrency
    try:
        await manager.load_all([])
        assert not manager.registered_shop_bot_ids()
        settings.bot_register_concurrency = 0
        manager2 = ShopBotManager(shop_dispatcher)
        rows = [_shop_bot(i + 1) for i in range(3)]
        await manager2.load_all(rows)
        await _wait_deletes(len(rows))
        assert len(manager2.registered_shop_bot_ids()) == len(rows), "سقفِ صفر یعنی یکی‌یکی، نه هیچی"
        assert StartProbeSession.start_peak == 1
        await _drain(manager2)
    finally:
        settings.bot_register_concurrency = limit_before
        bot_manager_module.Bot = original_class
    print("✅ test_empty_and_bad_limit_are_safe PASSED")


async def test_shutdown_closes_every_bot_bounded(shop_dispatcher) -> None:
    """`shutdown()` باید همهٔ ربات‌ها را ببندد، نه ترتیبی (۵۰۰×RTT = SIGKILL داکر) و نه نصفه."""
    limit = settings.bot_register_concurrency
    rows = [_shop_bot(i + 1) for i in range(limit + 6)]
    manager = _manager_with_probe(shop_dispatcher)
    original_class = bot_manager_module.Bot_original
    try:
        await manager.load_all(rows)
        await _wait_deletes(len(rows))
        StartProbeSession.start_peak = 0  # از اینجا فقط خاموش‌شدن را می‌سنجیم
        StartProbeSession.delete_calls = 0
        await manager.shutdown()
        assert manager.registered_shop_bot_ids() == [], "هیچ اتصالی نباید باز بماند"
        assert manager.registered_bale_bot_ids() == []
        assert StartProbeSession.delete_calls == len(rows), "برایِ هر ربات دقیقاً یک delete_webhookِ بستن"
        assert 1 < StartProbeSession.start_peak <= limit, f"بستن نباید ترتیبی شود: peak={StartProbeSession.start_peak}"
    finally:
        await _drain(manager)
        bot_manager_module.Bot = original_class
    print("✅ test_shutdown_closes_every_bot_bounded PASSED")


async def main() -> None:
    from harness import build_test_dispatchers

    assert not hasattr(bot_manager_module, "Bot_original"), "پچ دوبار اعمال نشود"
    bot_manager_module.Bot_original = bot_manager_module.Bot
    assert isinstance(settings.bot_register_concurrency, int) and settings.bot_register_concurrency >= 1
    _main_dp, shop_dispatcher, _manager, _bot = build_test_dispatchers()
    await test_registration_is_bounded_and_complete(shop_dispatcher)
    await test_webhook_mode_is_bounded_too(shop_dispatcher)
    await test_delete_webhook_failure_keeps_the_bot_polling(shop_dispatcher)
    await test_empty_and_bad_limit_are_safe(shop_dispatcher)
    await test_shutdown_closes_every_bot_bounded(shop_dispatcher)
    print("\n✅ همهٔ تست‌هایِ P29ِ «راه‌اندازیِ کرید‌شده» پاس شدند")


if __name__ == "__main__":
    asyncio.run(main())
