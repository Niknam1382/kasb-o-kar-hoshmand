#!/usr/bin/env python3
"""پ۱۱۰ · سنجهٔ دست‌دهیِ واقعیِ WebSocket (`/ws/ops`) رویِ uvicorn.

چرا این اسکریپت هست: تستِ سوئیت اپِ ASGI را مستقیم صدا می‌زند، یعنی مسیرِ *سِرور* (uvicorn +
ارتقای HTTP به WS + تنظیمِ `proxy_http_version`/`Upgrade` در nginx) را نمی‌پاید. این اسکریپت با
socketِ خام (بی‌هیچ وابستگیِ تازه) سه چیز را ثابت می‌کند:

۱. دست‌دهیِ بی‌نشانه ⇒ اتصال پذیرفته نمی‌شود (بسته‌شدن/کدِ خطا، نه ۱۰۱).
۲. دست‌دهیِ با کوکیِ نشانه ⇒ `101 Switching Protocols` + `Sec-WebSocket-Accept` درست.
۳. چند فریمِ متنی پشتِ سرهم در بازهٔ خواسته‌شده می‌رسد (پخشِ زنده کار می‌کند).

اجرا (داخل کانتینر، جایی که سرویسِ HTTP بالا است):
    python3 scripts/ws_handshake_probe.py --url ws://127.0.0.1:8000/ws/ops --frames 3 --seconds 20
نکتهٔ استقرار: اگر پشتِ reverse-proxy همین اسکریپت رویِ آدرسِ عمومی ۱۰۱ نداد، مشکل از
پیکربندیِ ارتقا (nginx/Caddy) است، نه از کد.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import os
import socket
import struct
import sys
import time

sys.path.insert(0, ".")

from app import main as app_main  # noqa: E402
from app.config import settings  # noqa: E402

GUID = b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
OP_CLOSE, OP_PING, OP_PONG, OP_TEXT = 0x8, 0x9, 0xA, 0x1


def _split(url: str) -> tuple[str, str, int, str]:
    scheme, _, rest = url.partition("://")
    host, _, path = rest.partition("/")
    port = 443 if scheme == "wss" else 80
    if ":" in host:
        host, _, raw_port = host.partition(":")
        port = int(raw_port) if raw_port.isdigit() else port
    return scheme, host, port, "/" + path


def _connect(scheme: str, host: str, port: int, path: str, cookie: str | None, timeout: float):
    sock: socket.socket = socket.create_connection((host, port), timeout=timeout)
    if scheme == "wss":
        import ssl

        sock = ssl.create_default_context().wrap_socket(sock, server_hostname=host)
    key = base64.b64encode(os.urandom(16)).decode()
    lines = [
        f"GET {path} HTTP/1.1",
        f"Host: {host}",
        "Upgrade: websocket",
        "Connection: Upgrade",
        f"Sec-WebSocket-Key: {key}",
        "Sec-WebSocket-Version: 13",
    ]
    if cookie:
        lines.append(f"Cookie: {cookie}")
    sock.sendall(("\r\n".join(lines) + "\r\n\r\n").encode())
    return sock, key


def _handshake(sock: socket.socket) -> tuple[bytes, bytes]:
    """سرِ دست‌دهی + هر بایتی که *همراهش* رسیده (فریمِ اول معمولاً همین‌جا است)."""
    buffer = b""
    while b"\r\n\r\n" not in buffer:
        chunk = sock.recv(4096)
        if not chunk:
            break
        buffer += chunk
    head, _, rest = buffer.partition(b"\r\n\r\n")
    return head, rest


class _Reader:
    def __init__(self, sock: socket.socket, pending: bytes) -> None:
        self.sock = sock
        self.buffer = bytearray(pending)

    def _need(self, count: int) -> bytes:
        while len(self.buffer) < count:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise EOFError
            self.buffer += chunk
        return bytes(self.buffer[:count])

    def frame(self) -> tuple[int, bytes]:
        first = self._need(2)
        opcode = first[0] & 0x0F
        length = first[1] & 0x7F
        header_size = 2
        if length == 126:
            length = struct.unpack("!H", self._need(4)[2:])[0]
            header_size = 4
        elif length == 127:
            length = struct.unpack("!Q", self._need(10)[2:])[0]
            header_size = 10
        payload = self._need(header_size + length)[header_size:]
        del self.buffer[: header_size + length]
        return opcode, payload


def _send_frame(sock: socket.socket, opcode: int, payload: bytes = b"") -> None:
    """فریمِ کلاینت همیشه باید ماسک‌شده باشد (RFC 6455) — وگرنه سرور اتصال را می‌بندد."""
    mask = os.urandom(4)
    masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
    header = struct.pack("!BB", 0x80 | opcode, 0x80 | len(payload)) if len(payload) < 126 else struct.pack(
        "!BBH", 0x80 | opcode, 0x80 | 126, len(payload)
    )
    sock.sendall(header + mask + masked)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="ws://127.0.0.1:8000/ws/ops")
    parser.add_argument("--frames", type=int, default=2)
    parser.add_argument("--seconds", type=float, default=20.0)
    args = parser.parse_args()

    if not settings.metrics_token:
        print("METRICS_TOKEN خالی است ⇒ سرور هر اتصالِ WS را رد می‌کند (رفتارِ درست، ولی سنجه نیست).")
        return 2

    scheme, host, port, path = _split(args.url)

    sock, _ = _connect(scheme, host, port, path, None, timeout=5.0)
    head = _handshake(sock)[0]
    status_line = head.split(b"\r\n", 1)[0].decode("latin-1")
    print(f"بی‌نشانه: {status_line or '(بسته‌شدنِ بی‌پاسخ)'}")
    sock.close()

    cookie = f"{app_main.OPS_WS_COOKIE}={app_main._ops_ws_ticket()}"
    sock, key = _connect(scheme, host, port, path, cookie, timeout=args.seconds + 10)
    head, pending = _handshake(sock)
    status_line = head.split(b"\r\n", 1)[0].decode("latin-1")
    expected = base64.b64encode(hashlib.sha1(key.encode() + GUID).digest()).decode()
    accepted = expected.lower() in head.decode("latin-1").lower()
    print(f"با نشانه: {status_line or '(بسته‌شدنِ بی‌پاسخ)'} · Sec-WebSocket-Accept درست: {accepted}")
    if " 101" not in status_line or not accepted:
        sock.close()
        return 1

    reader = _Reader(sock, pending)
    started = time.monotonic()
    sizes: list[int] = []
    while len(sizes) < args.frames and time.monotonic() - started < args.seconds:
        try:
            opcode, payload = reader.frame()
        except (EOFError, OSError):
            break
        if opcode == OP_CLOSE:
            print("سرور اتصال را بست (۴۴۰۱ یعنی نشانه خوانده نشد).")
            break
        if opcode == OP_PING:
            _send_frame(sock, OP_PONG, payload)
            continue
        if opcode in (OP_TEXT, 0x2):
            sizes.append(len(payload))
    sock.close()
    elapsed = time.monotonic() - started
    if len(sizes) < args.frames:
        print(f"MEASURED فریم‌ها: {sizes} · کمتر از {args.frames} در {elapsed:.1f}s")
        return 1
    print(f"MEASURED {len(sizes)} فریم در {elapsed:.1f}s · اندازه‌ها: {sizes} بایت")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
