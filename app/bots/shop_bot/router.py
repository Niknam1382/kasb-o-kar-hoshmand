from __future__ import annotations

from aiogram import Router

from app.bots.shop_bot.handlers import customer


def build_shop_router() -> Router:
    router = Router(name="shop_bot")
    router.include_router(customer.router)
    return router
