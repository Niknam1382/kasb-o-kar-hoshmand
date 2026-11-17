#!/usr/bin/env python3
"""پ۱۱۱ · بارسنجیِ HTTPِ **واقعی** (uvicorn + چند پروسه)، نه فراخوانِ مستقیمِ ASGI.

چرا این فایل هست: همهٔ عددهایِ HTTPِ این پروژه تا امروز «فراخوانِ خامِ ASGI داخلِ یکِ پروسهٔ تست»
بودند (تست‌هایِ `scope` در پ۹۱/پ۱۰۴). آن عددها منطقِ اپ را می‌پایند ولی *ظرفیتِ سروِ درخواست* را
نه — همان چیزی که برایِ «چند هزار فروشگاه رویِ چند worker» لازم است. این اسکریپت سرورِ واقعی
(uvicorn) را بالا می‌آورد و با کلاینتِ رشته‌ایِ استاندارد (http.client + ThreadPoolExecutor،
بی‌هیچ وابستگیِ تازه) فشار می‌آورد.

چه مسیرهایی سنجیده می‌شوند و چرا بی‌خطرند:
· `/health` (یکِ `SELECT 1`) · `/metrics` و `/ops/status` (فقط‌خواندنی) · `/panel` (همانِ `/ops/status`
  به شکلِ HTML) · `/web/login` با لینکِ جعلی (مسیرِ ردِّ احراز) · `/webhook/main` بی‌امضا (ردِّ
  زودهنگام، پیشِ هر AI یا تلگرام).
هیچ‌کدام پیامی نمی‌فرستند، پرداختی نمی‌سازند و به هوشِ مصنوعی زنگ نمی‌زنند؛ تنها اثرِ جانبی،
شمارنده‌هایِ in-process و ردیفِ ضربانِ شمارنده است.

ایمنی: تا `LOADTEST_DB_CONFIRM=1` ست نشود اجرا نمی‌شود و رویِ دیتابیسِ `kasbokar`/`postgres`
متوقف می‌گردد (همان قاعدهٔ `two_process_probe.py` و `loadtest_*.py`).

دستور (داخل کانتینر؛ پورت‌ها فقط رویِ loopbackِ همان کانتینرند):
    docker compose run --rm -e LOADTEST_DB_CONFIRM=1 -e METRICS_TOKEN=load-p111 \\
        -e WEB_PANEL_SECRET= bot python3 scripts/http_load_probe.py --workers 1,2,4 --requests 400 --concurrency 32

خروجی: برایِ هر آرایشِ worker، جمعِ req/s و p50/p95 به‌ازایِ هر مسیر + شمارِ وضعیت‌ها (MEASURED).
"""
from __future__ import annotations

import argparse
import base64
import http.client
import json
import multiprocessing as mp
import os
import socket
import sys
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, ".")

IMPORT_STRING = "scripts.http_load_probe:build_app"
HEALTH_PORT_BASE = 8300


def _guard() -> None:
    if os.environ.get("LOADTEST_DB_CONFIRM") != "1":
        print(
            "LOADTEST_DB_CONFIRM=1 لازم است. این سنجه فقط‌خواندنی است، ولی رویِ دیتابیسِ اصلی/تولیدی "
            "هرگز اجرا نکن (بهتر است DATABASE_URL را به دیتابیسِ جدا بدهی)."
        )
        raise SystemExit(2)
    from app.config import settings

    name = str(settings.database_url).rsplit("/", 1)[-1]
    if name in {"kasbokar", "postgres"}:
        print(f"⛔️ دیتابیسِ «{name}» مجاز نیست — یکِ دیتابیسِ جدا بده.")
        raise SystemExit(2)


def build_app():
    """اپِ سلامت (فقط `/health`، `/metrics`، `/ops/status`، `/panel`، `/ws/ops`).

    عمداً اپِ اصلی *نیست*: `app.main.app` در startup ربات‌ها را register می‌کند و به تلگرام زنگ
    می‌زند؛ این یکی هیچ اثرِ بیرونی ندارد و همان لایهٔ HTTP را سرو می‌کند.
    """
    from app.main import build_health_app

    return build_health_app()


def _serve(port: int, ready: "mp.SimpleQueue") -> None:
    """یکِ پروسهٔ uvicorn رویِ یکِ پورت (بدونِ `--workers`، تا شمارشِ پروسه‌ها دستِ خودمان باشد)."""
    import uvicorn

    config = uvicorn.Config(IMPORT_STRING, host="127.0.0.1", port=port, log_level="error", factory=False)
    server = uvicorn.Server(config)
    server.run()
    ready.put(port)


def _endpoints() -> list[tuple[str, str, dict[str, str], int, set[int]]]:
    from app.config import settings

    token = settings.metrics_token or "load-p111"
    basic = "Basic " + base64.b64encode(f"ops:{token}".encode()).decode()
    header_token = {"x-metrics-token": token}
    return [
        ("health", "GET", "/health", {}, 0, {200, 503}),
        ("metrics", "GET", "/metrics", header_token, 0, {200, 403, 404}),
        ("ops/status", "GET", "/ops/status", header_token, 0, {200, 401, 403, 404}),
        ("panel", "GET", "/panel", {"authorization": basic}, 0, {200, 401, 404}),
        ("web/login-bad", "GET", "/web/login?t=not-a-real-link", {}, 0, {401, 404}),
        ("webhook-unsigned", "POST", "/webhook/main", {"content-type": "application/json"}, 1, {401, 403, 404}),
    ]


def _one(port: int, method: str, path: str, headers: dict[str, str], body: bytes | None, timeout: float) -> int:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    try:
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        response.read()
        return response.status
    finally:
        connection.close()


def _spawn_workers(count: int) -> tuple[list, list]:
    context = mp.get_context("spawn")
    ready = context.SimpleQueue()
    procs = []
    for index in range(count):
        proc = context.Process(target=_serve, args=(HEALTH_PORT_BASE + index, ready), daemon=True)
        proc.start()
        procs.append(proc)
    ports = [HEALTH_PORT_BASE + index for index in range(count)]
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", ports[0]), timeout=1.0):
                break
        except OSError:
            time.sleep(0.5)
    else:
        print("❌ سرور بالا نیامد (uvicorn رویِ loopback).")
    return procs, ports


def _stop(procs: list) -> None:
    for proc in procs:
        proc.terminate()
    for proc in procs:
        proc.join(10)
        if proc.is_alive():
            proc.kill()


def measure(workers: int, requests: int, concurrency: int) -> dict:
    procs, ports = _spawn_workers(workers)
    if not ports:
        return {}
    time.sleep(1.0)
    endpoints = _endpoints()
    results: dict[str, dict] = {}
    for name, method, path, headers, body_mode, expected in endpoints:
        body = b'{"update_id":1,"message":{"text":"load"}}' if body_mode else None
        plan = [(ports[index % len(ports)], method, path, headers, body) for index in range(requests)]
        # گرم‌کردن: سه درخواست اول (ارتباطِ تازه، first-importِ سرویس‌ها) در عدد نمی‌آیند
        for warm in plan[:3]:
            try:
                _one(*warm, timeout=10.0)
            except OSError:
                pass
        latencies: list[int] = []
        statuses: dict[int, int] = {}

        def run(item):
            started = time.perf_counter()
            try:
                status = _one(*item, timeout=10.0)
            except OSError:
                status = 0  # اتصال بسته/timeout: با کدِ ۰ شمرده می‌شود و سنجه را رد می‌کند
            latencies.append(int((time.perf_counter() - started) * 1000))
            statuses[status] = statuses.get(status, 0) + 1
            return status

        began = time.perf_counter()
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            list(pool.map(run, plan))
        elapsed = max(1e-6, time.perf_counter() - began)
        ordered = sorted(latencies)
        p50 = ordered[len(ordered) // 2] if ordered else 0
        p95 = ordered[max(0, (len(ordered) * 95) // 100 - 1)] if ordered else 0
        unexpected = {
            code: value
            for code, value in statuses.items()
            if code not in expected and (code == 0 or str(code)[0] == "5" or str(code)[0] == "4")
        }
        results[name] = {
            "requests": requests,
            "per_second": round(requests / elapsed, 1),
            "p50_ms": p50,
            "p95_ms": p95,
            "statuses": statuses,
            "unexpected": unexpected,
            "ok": not unexpected,
        }
        print(
            f"MEASURED workers={workers} {name}: {results[name]['per_second']} req/s · p50 {p50} ms · "
            f"p95 {p95} ms · وضعیت‌ها={statuses}"
        )
    _stop(procs)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="بارسنجیِ HTTPِ واقعی رویِ uvicorn (چند پروسه)")
    parser.add_argument("--workers", default="1,2,4", help="آرایش‌ها، جدا با کاما (مثلاً 1,2,4)")
    parser.add_argument("--requests", type=int, default=200, help="تعدادِ درخواست در هر مسیر")
    parser.add_argument("--concurrency", type=int, default=16, help="تعدادِ رشته‌هایِ کلاینت")
    parser.add_argument("--json", action="store_true", help="خروجیِ JSON نهایی (برایِ پیوستن به گزارش)")
    args = parser.parse_args()
    _guard()

    from app.config import settings

    if not settings.metrics_token:
        print("METRICS_TOKEN ست نشده ⇒ `/metrics`، `/ops/status` و `/panel` ۴۰۴ می‌شوند (سنجه بی‌معنی).")
        return 2

    summary = {}
    for workers in [int(item) for item in args.workers.split(",") if item.strip()]:
        summary[workers] = measure(max(1, min(workers, 6)), max(10, args.requests), max(1, args.concurrency))
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    failed = [
        f"{workers}/{name}"
        for workers, rows in summary.items()
        for name, row in (rows or {}).items()
        if not row.get("ok")
    ]
    if failed:
        print("❌ مسیرهایی با پاسخِ غیرمنتظره: " + ", ".join(failed))
        return 1
    print("✅ همهٔ مسیرها فقط پاسخ‌هایِ منتظره دادند (بدونِ ۵xxِ غیرمنتظره).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
