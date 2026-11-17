"""پ۱۱۲ · درهایِ آپدیتِ بله: چه چیزی «امضا» را جایگزین می‌کند و چه چیزی را نمی‌کند.

چرا این تست هست: مستنداتِ بله هیچِ امضایِ HMAC رویِ بدنهٔ وبهوک را تأیید نمی‌کند و ما هرگز یکِ
وبهوکِ *واقعی* از بله نگرفته‌ایم (NOT VERIFIED). پس نمی‌توان ادعا کرد «امضا بررسی می‌شود». آنچه
می‌توان ثابت کرد این سه تا است:

۱. درِ آپدیتِ بله فقط با `BALE_UPDATES_MODE=webhook` باز است — و این گارد حالا رویِ **هر دو** مسیر
   برقرار است (پیش‌ازاین مسیرِ رازِ مسیری در polling هم قبول می‌کرد).
۲. پذیرش = دانستنِ راز؛ از هدرِ تلگرام‌مانند **یا** از مسیر. بی‌آن ⇒ ۴۰۳، بی‌توکن/بی‌حالتِ webhook ⇒ ۴۰۴.
۳. آنچه در آپدیتِ جعلی هرگز اتفاق نمی‌افتد: پول. اعتبارِ پرداخت از استعلامِ سمتِ سرور
   (`bale_service.inquire_transaction`) می‌آید، نه از بدنهٔ وبهوک ⇒ بدنهٔ ساختگی موجودی نمی‌سازد.

اجرا: python3 tests_manual/run_one.py test_p112_bale_webhook_guards.py
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
import types

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from sqlalchemy import select  # noqa: E402

from app import main as app_main  # noqa: E402
from app.config import settings  # noqa: E402
from app.database.session import engine, session_scope  # noqa: E402
from app.services import bale_credentials_service  # noqa: E402
from harness import reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

OWNER_TG_ID = 11_121_000_001
SHOP_BOT_TG_ID = 11_121_000_002
SECRET = "bale-webhook-secret-32-bytes-long"


class _Req:
    """جای‌نمایِ حداقلیِ `Request` برایِ دو مسیرِ بله (بدنه + هدرها)."""

    def __init__(self, headers: dict[str, str] | None = None, body: bytes = b"{}") -> None:
        self.headers = headers or {}
        self._body = body
        self.client = types.SimpleNamespace(host="127.0.0.1")
        self.url = types.SimpleNamespace(scheme="http")
        self.query_params = {}

    async def json(self) -> dict:
        import json

        return json.loads(self._body or b"{}")


def _saved() -> tuple:
    return (settings.bale_updates_mode, settings.bale_webhook_secret, settings.bale_bot_token)


def _restore(values: tuple) -> None:
    settings.bale_updates_mode, settings.bale_webhook_secret, settings.bale_bot_token = values


async def test_closed_in_polling_for_both_routes() -> None:
    saved = _saved()
    try:
        settings.bale_bot_token = "123456:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        settings.bale_webhook_secret = SECRET
        settings.bale_updates_mode = "polling"
        assert bale_credentials_service.webhook_secret() == SECRET
        assert app_main._bale_webhook_open() is False, "در polling هیچ دری باز نیست"
        assert (await app_main.webhook_bale(_Req({}))).status_code == 404
        assert (await app_main.webhook_bale_with_secret(SECRET, _Req({}))).status_code == 404, (
            "مسیرِ رازِ مسیری در polling باز ماند"
        )
        # بدونِ توکنِ ربات هم همان ۴۰۴
        settings.bale_bot_token = ""
        settings.bale_updates_mode = "webhook"
        assert (await app_main.webhook_bale(_Req({}))).status_code == 404
    finally:
        bale_credentials_service.reset_cache()
        _restore(saved)
    print("PASS test_closed_in_polling_for_both_routes")


async def test_secret_from_header_or_path_and_rejections() -> None:
    saved = _saved()
    try:
        settings.bale_bot_token = "123456:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        settings.bale_webhook_secret = SECRET
        settings.bale_updates_mode = "webhook"
        assert app_main._bale_webhook_open() is True

        # راز از هدر ⇒ پذیرش؛ راز از مسیر ⇒ پذیرش؛ هیچ‌کدام ⇒ ۴۰۳؛ غلط ⇒ ۴۰۳
        assert (await app_main.webhook_bale(_Req({"X-Telegram-Bot-Api-Secret-Token": SECRET}))).status_code == 200
        assert (await app_main.webhook_bale(_Req({}))).status_code == 403
        assert (await app_main.webhook_bale(_Req({"X-Telegram-Bot-Api-Secret-Token": "guess"}))).status_code == 403
        assert (await app_main.webhook_bale_with_secret(SECRET, _Req({}))).status_code == 200
        assert (await app_main.webhook_bale_with_secret("guess", _Req({}))).status_code == 403
        # راز از هدر برایِ مسیرِ مسیری هم کار می‌کند (تبدیلِ «ادعا» به «هر دو حالت» — پ۱۱۲)
        assert (await app_main.webhook_bale_with_secret(
            "", _Req({"X-Telegram-Bot-Api-Secret-Token": SECRET})
        )).status_code == 200

        # رازِ خالی ⇒ هیچ مقایسه‌ای با رشتهٔ تهی انجام نشود (وگرنه درخواستِ بی‌هدر قبول می‌شد)
        settings.bale_webhook_secret = ""
        assert app_main._bale_webhook_open() is False
        assert (await app_main.webhook_bale(_Req({}))).status_code == 404
        assert app_main._bale_webhook_authorized(_Req({}), "") is False, "رازِ خالی نباید خودش با خودش بخواند"
    finally:
        bale_credentials_service.reset_cache()
        _restore(saved)
    print("PASS test_secret_from_header_or_path_and_rejections")


async def test_forged_update_cannot_move_money_without_server_inquiry() -> None:
    """بدنهٔ وبهوک تنها منبع نیست: استعلامِ سمتِ سرور «موفق» نباشد، هیچ شارژی انجام نمی‌شود."""
    from app.database.models import Payment, PaymentPurpose, PaymentStatus, ShopOwner
    from app.services import payment_service

    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID, initial_balance_toman=10_000)
    async with session_scope() as session:
        owner = (await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == OWNER_TG_ID))).scalar_one()
        payment = await payment_service.create_bale_payment(
            session, owner, 100_000, None, f"payment-forged-{int(time.time() % 100_000)}", purpose=PaymentPurpose.WALLET_TOPUP
        )
        payment_id = payment.id
        payload = payment.bale_invoice_payload
        await session.commit()

    saved = _saved()
    calls: list[str] = []
    original = app_main.bale_service.inquire_transaction
    try:
        settings.bale_bot_token = "123456:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        settings.bale_webhook_secret = SECRET
        settings.bale_updates_mode = "webhook"

        async def _failing_inquire(token: str, ref: str) -> dict:
            calls.append(ref)
            return {"result": "failed", "transaction_id": ref, "card_pan": "6037"}

        app_main.bale_service.inquire_transaction = _failing_inquire  # type: ignore[assignment]

        body = json.dumps(
            {
                "message": {
                    "successful_payment": {
                        "invoice_payload": payload,
                        "telegram_payment_charge_id": "forged-ref",
                        "total_amount": 1_000_000,
                        "currency": "IRR",
                    }
                }
            }
        ).encode()
        status = (await app_main.webhook_bale(_Req({"X-Telegram-Bot-Api-Secret-Token": SECRET}, body))).status_code
        assert status == 200, "پاسخِ وبهوک باید ۲۰۰ باشد تا بله دوباره‌فرستانی نسازد"
        assert calls == ["forged-ref"], calls

        async with session_scope() as session:
            row = await session.get(Payment, payment_id)
            assert row.status == PaymentStatus.PENDING, f"پرداختِ جعلی تایید شد: {row.status}"
            balance = int(
                (
                    await session.execute(
                        select(ShopOwner.wallet_balance_toman).where(ShopOwner.telegram_id == OWNER_TG_ID)
                    )
                ).scalar_one()
            )
            assert balance == 10_000, balance
    finally:
        app_main.bale_service.inquire_transaction = original  # type: ignore[assignment]
        bale_credentials_service.reset_cache()
        _restore(saved)
        await engine.dispose()
    print("PASS test_forged_update_cannot_move_money_without_server_inquiry")


async def main() -> None:
    await test_closed_in_polling_for_both_routes()
    await test_secret_from_header_or_path_and_rejections()
    await test_forged_update_cannot_move_money_without_server_inquiry()


if __name__ == "__main__":
    asyncio.run(main())
