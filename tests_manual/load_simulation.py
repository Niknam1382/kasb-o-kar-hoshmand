"""
شبیه‌ساز بار (فازِ ۶-الف) — «رباتِ ما چه تعداد فروشگاه/مشتریِ هم‌زمان رو تحمل می‌کنه؟»

⚠️ این فایل جزوِ run_all_tests نیست (تستِ پاس/فیل نیست؛ اندازه‌گیریه) و **دیتابیسِ پروژه رو پاک می‌کنه** (مثلِ تست‌ها).

چی رو شبیه‌سازی می‌کنه: N فروشگاه، هرکدوم M مشتری که هم‌زمان K پیامِ پشتِ‌هم می‌فرستن؛ AI یه تأخیرِ ثابت داره (--ai-delay) و
هیچ پول/اینترنتی خرج نمی‌شه. مسیرِ واقعی (dispatcher، میدل‌ورها، دیتابیسِ واقعیِ Postgres، debounce، کسرِ کیف‌پول، ثبتِ مکالمه)
اجرا می‌شه؛ فقط تلگرام و AI جعلی‌ان. پس عددها «سقفِ نرم‌افزار و دیتابیس روی همین سخت‌افزار» رو نشون می‌دن (نه شبکه‌یِ واقعیِ تلگرام).

اجرا (داخلِ Docker؛ از ساده به سنگین):
  docker compose run --rm bot python3 tests_manual/load_simulation.py
  docker compose run --rm bot python3 tests_manual/load_simulation.py --shops 20 --customers 25 --messages 3 --ai-delay 3
  docker compose run --rm bot python3 tests_manual/load_simulation.py --shops 50 --customers 20 --ai-delay 5 --window 1

خروجی: زمانِ کل، تعدادِ جواب‌ها، بیشینه‌یِ فراخوانی‌هایِ هم‌زمانِ AI، بیشینه‌یِ اتصالِ دیتابیسِ درگیر، خطاها، و یه «نتیجه‌گیری».
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import statistics
import sys
import time

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402

from harness import FakeSession, build_test_dispatchers, make_message_update, reset_database  # noqa: E402
from phase4_helpers import FakeAi, patched_ai, set_ai  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.shop_bot.handlers import customer as customer_handlers  # noqa: E402
from app.config import settings  # noqa: E402
from app.database.session import engine  # noqa: E402
from app.services.order_detection_service import _CLASSIFIER_USER_PROMPT  # noqa: E402


class _CountingAi(FakeAi):
    def __init__(self, delay: float) -> None:
        super().__init__(chat_reply="پاسخِ آزمایشی", delay=delay)
        self.active = 0
        self.max_active = 0
        self.total = 0

    async def get_reply(self, system_prompt, history, user_message):
        if user_message == _CLASSIFIER_USER_PROMPT:
            return await super().get_reply(system_prompt, history, user_message)
        self.active += 1
        self.total += 1
        self.max_active = max(self.max_active, self.active)
        try:
            return await super().get_reply(system_prompt, history, user_message)
        finally:
            self.active -= 1


class _ErrorCounter(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.ERROR)
        self.records: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record.getMessage()[:140])


async def main() -> int:
    parser = argparse.ArgumentParser(description="شبیه‌ساز بارِ رباتِ فروشگاهی")
    parser.add_argument("--shops", type=int, default=10, help="تعدادِ فروشگاه (پیش‌فرض ۱۰)")
    parser.add_argument("--customers", type=int, default=20, help="مشتریِ هم‌زمان به‌ازایِ هر فروشگاه (پیش‌فرض ۲۰)")
    parser.add_argument("--messages", type=int, default=3, help="پیامِ پشتِ‌همِ هر مشتری (پیش‌فرض ۳؛ حداکثر ۱۰ به‌خاطرِ محدودیتِ نرخ)")
    parser.add_argument("--ai-delay", type=float, default=2.0, help="تأخیرِ هر فراخوانیِ AI به ثانیه (پیش‌فرض ۲)")
    parser.add_argument("--window", type=float, default=0.5, help="مدتِ تجمیعِ پیام‌ها به ثانیه (پیش‌فرض ۰٫۵ برایِ سرعتِ تست)")
    parser.add_argument("--timeout", type=float, default=300.0, help="سقفِ انتظار برایِ اتمام (ثانیه)")
    args = parser.parse_args()
    args.messages = max(1, min(args.messages, 10))

    counter = _ErrorCounter()
    logging.getLogger().addHandler(counter)

    print(f"⏳ آماده‌سازی: {args.shops} فروشگاه × {args.customers} مشتری × {args.messages} پیام (AI: {args.ai_delay}s)...")
    await reset_database()
    shops: list[tuple[Bot, FakeSession]] = []
    for index in range(args.shops):
        owner_tg, bot_tg = 7_000_000 + index, 7_500_000 + index
        await seed_usable_shop(owner_tg, bot_tg)
        bot = Bot(token=f"{bot_tg}:FAKE", session=FakeSession())
        shops.append((bot, bot.session))  # type: ignore[arg-type]

    _main_dp, shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    fake = set_ai(_CountingAi(args.ai_delay))
    customer_handlers.DEBOUNCE_SECONDS = args.window

    max_checked_out = 0
    stop_sampling = False

    async def sample_pool() -> None:
        nonlocal max_checked_out
        while not stop_sampling:
            max_checked_out = max(max_checked_out, engine.pool.checkedout())
            await asyncio.sleep(0.05)

    update_id = 0
    send_latencies: list[float] = []

    async def customer(shop_index: int, customer_index: int) -> None:
        nonlocal update_id
        bot, _session = shops[shop_index]
        customer_tg = 100_000_000 + shop_index * 10_000 + customer_index
        for message_number in range(args.messages):
            update_id += 1
            started = time.perf_counter()
            await shop_dp.feed_update(bot, make_message_update(update_id, text=f"سلام پیامِ {message_number + 1}", user_id=customer_tg))
            send_latencies.append(time.perf_counter() - started)
            await asyncio.sleep(0.1)

    expected_replies = args.shops * args.customers
    sampler = asyncio.create_task(sample_pool())
    started_at = time.perf_counter()
    with patched_ai():
        await asyncio.gather(*[customer(s, c) for s in range(args.shops) for c in range(args.customers)])
        sending_done = time.perf_counter() - started_at

        def replies() -> int:
            return sum(len(session.sent_messages) for _bot, session in shops)

        while replies() < expected_replies and time.perf_counter() - started_at < args.timeout:
            await asyncio.sleep(0.2)
        await asyncio.sleep(1.0)  # جوابِ اضافی/تسک‌هایِ پس‌زمینه
    elapsed = time.perf_counter() - started_at
    stop_sampling = True
    await sampler

    got = replies()
    errors = counter.records
    print("\n" + "=" * 62)
    print(f"فروشگاه‌ها: {args.shops} | مشتریِ هم‌زمان: {args.shops * args.customers} | پیام‌ها: {args.shops * args.customers * args.messages}")
    p95 = sorted(send_latencies)[max(0, int(len(send_latencies) * 0.95) - 1)] * 1000
    print(f"زمانِ ارسالِ همه‌یِ پیام‌ها : {sending_done:6.1f} ثانیه (میانگینِ پذیرشِ هر پیام {statistics.mean(send_latencies) * 1000:.0f}ms، p95 {p95:.0f}ms)")
    print(f"زمانِ کل تا آخرین جواب   : {elapsed:6.1f} ثانیه")
    print(f"جواب‌هایِ تحویل‌شده      : {got} از {expected_replies} مورد انتظار")
    print(f"فراخوانیِ AI (چت)        : {fake.total} (بیشینه‌یِ هم‌زمان: {fake.max_active}، سقفِ تنظیم‌شده: {settings.ai_max_concurrent_calls})")
    print(f"اتصالِ دیتابیسِ درگیر    : بیشینه {max_checked_out} از {settings.db_pool_size}+{settings.db_max_overflow}")
    print(f"توان (جواب بر ثانیه)    : {got / elapsed:6.1f}")
    print(f"خطاهایِ لاگ‌شده          : {len(errors)}")
    for line in errors[:5]:
        print(f"   - {line}")
    print("=" * 62)

    problems = []
    if got < expected_replies:
        problems.append(f"{expected_replies - got} جواب تحویل داده نشد (timeout یا خطا)")
    if got > expected_replies:
        problems.append(f"{got - expected_replies} جوابِ اضافه (پیام‌هایِ یه مشتری یکی نشدن؛ پنجره‌یِ --window رو بزرگ‌تر کن یا بررسی کن)")
    if errors:
        problems.append(f"{len(errors)} خطا توی لاگ (احتمالاً pool timeout / 429 / خطایِ دیتابیس)")
    if max_checked_out >= settings.db_pool_size + settings.db_max_overflow:
        problems.append(
            "استخرِ دیتابیس کاملاً پر شد → DB_POOL_SIZE را زیاد کن (P20-F اندازه گرفت که "
            "اتصال‌هایِ DB_MAX_OVERFLOW در اوج، توان را تا ۲٫۸ برابر کم می‌کنند؛ پس استخرِ ثابت "
            "بهتر از سرریزِ موقت است) و max_connections پستگرس را چک کن"
        )
    if fake.max_active >= settings.ai_max_concurrent_calls:
        print(
            "ℹ️ سقفِ فراخوانیِ هم‌زمانِ AI پر شد؛ فراخوانی‌هایِ اضافه صف کشیدن (طبیعیه؛ اگه جواب‌ها خیلی دیر شد، "
            "AI_MAX_CONCURRENT_CALLS رو با توجه به سقفِ ارائه‌دهنده بالا ببر)."
        )
    if problems:
        print("❌ مشکل‌ها:")
        for problem in problems:
            print("  •", problem)
        return 1
    print("✅ این بار با همین سخت‌افزار بدونِ خطا و بدونِ جوابِ گم‌شده یا اضافه تحمل شد.")
    print("   (برایِ پیدا کردنِ سقف، --shops/--customers رو مرحله‌به‌مرحله زیاد کن تا اولین ❌ ظاهر بشه.)")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
