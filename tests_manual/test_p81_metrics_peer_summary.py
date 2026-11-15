"""پ۸۱ · لایهٔ اولِ فقط‌خواندنیِ «پنلِ عملیاتی»: `/metrics` حالا می‌گوید چند پروسه در جمعِ شمارنده‌ها هست.

چرا همین‌قدر؟ خواستهٔ اصلی (پنلِ وبِ چندکاناله و همزمانیِ هزاران چت) یکِ فازِ بزرگِ مستقل است و
نیمه‌کاره گذاشتنش رویِ مسیرِ HTTP خطرناک‌تر از عقب انداختنش است. این فایل فقط چیزی را اضافه می‌کند که
بی‌صدا کم‌گوییِ عملیاتی را دیدنی می‌کند: دو خطِ gauge در متنِ Prometheus که از ضربانِ شمارنده‌ها
(`capacity_service.publish_counters`) تغذیه می‌شوند — بدونِ کوئری در مسیرِ HTTP، بدونِ رازِ تازه،
بدونِ تغییرِ درِ احرازِ موجود (`METRICS_TOKEN`).

پوششِ داده‌شده:
۱. پیش ازِ اولین ضربان، خروجیِ `render_prometheus()` دقیقاً شکلِ دیروز است (هیچ خطِ تازه‌ای نیست).
۲. بعد ازِ ضربان، `kasbokar_runtime_processes ≥ 1` و `kasbokar_runtime_stale_processes` نمایش داده می‌شود.
۳. عددِ خط‌ها با `aggregate_counters` یکی است (دو منبعِ حقیقت نداریم) و پروسهٔ بی‌ضربان در `stale` می‌آید.

اجرا: python3 tests_manual/run_one.py test_p81_metrics_peer_summary.py
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from app import observability  # noqa: E402
from app.services import capacity_service  # noqa: E402
from app.database.models import RuntimeCounterSnapshot  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from harness import reset_database  # noqa: E402

UTC = dt.timezone.utc


def test_no_lines_before_first_beat() -> None:
    observability._peer_summary.clear()
    body = observability.render_prometheus()
    assert "kasbokar_runtime_processes" not in body, "بدونِ ضربان، خطِ تازه ساخته نمی‌شود (شکلِ دیروز)"
    assert "kasbokar_uptime_seconds" in body
    print("PASS test_no_lines_before_first_beat")


async def test_beat_publishes_gauges() -> None:
    await reset_database()
    observability.reset_counters()
    observability._peer_summary.clear()
    observability.count("webhook.shop", 5)
    async with session_scope() as session:
        summary = await capacity_service.publish_counters(session)
        await session.commit()
    assert summary["processes"] == 1 and summary["stale"] == 0, summary
    body = observability.render_prometheus()
    assert "kasbokar_runtime_processes 1" in body, body
    assert "kasbokar_runtime_stale_processes 0" in body, body
    assert "# TYPE kasbokar_runtime_processes gauge" in body, body
    print("PASS test_beat_publishes_gauges")


async def test_metrics_agree_with_aggregate_counters() -> None:
    async with session_scope() as session:
        session.add(
            RuntimeCounterSnapshot(
                process_key="dead-worker:7", hostname="dead", counters=json.dumps({"webhook.main": 4}),
                updated_at=dt.datetime.now(UTC) - dt.timedelta(hours=3),
            )
        )
        session.add(
            RuntimeCounterSnapshot(
                process_key="live-worker:8", hostname="live", counters=json.dumps({"webhook.main": 6}),
                updated_at=dt.datetime.now(UTC),
            )
        )
        await session.commit()
    async with session_scope() as session:
        totals, processes, stale = await capacity_service.aggregate_counters(session)
        summary = await capacity_service.publish_counters(session)
        await session.commit()
    # خودِ اینِ پروسه (ردیفِ خودش + سهمِ زندهٔ حافظه) + live-worker ⇒ ۲ ؛ dead-worker بی‌اعتبار ⇒ stale=1
    assert (processes, stale) == (2, 1), (processes, stale)
    assert totals["webhook.main"] == 6, totals  # سهمِ مرده در جمع نیست، سهمِ زنده هست
    assert summary["processes"] == processes and summary["stale"] == stale, "دو منبعِ حقیقت یکی‌اند"
    body = observability.render_prometheus()
    assert f"kasbokar_runtime_processes {processes}" in body, body[-400:]
    assert "kasbokar_runtime_stale_processes 1" in body, body[-400:]
    observability.reset_counters()
    observability._peer_summary.clear()
    print("PASS test_metrics_agree_with_aggregate_counters")


async def main() -> None:
    test_no_lines_before_first_beat()
    await test_beat_publishes_gauges()
    await test_metrics_agree_with_aggregate_counters()


if __name__ == "__main__":
    asyncio.run(main())
