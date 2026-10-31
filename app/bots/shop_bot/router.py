from __future__ import annotations

from aiogram import Router

from app.bots.common.middlewares import MenuButtonEscapeMiddleware
from app.bots.shop_bot import texts
from app.bots.shop_bot.handlers import cart_proposals, checkout, customer, orders, payments, product_photos
from app.bots.shop_bot.middlewares import BlockedCustomerMiddleware


def build_shop_router() -> Router:
    router = Router(name="shop_bot")
    # B4: مشتریِ بلاک‌شده پیش از هر چیز دیگری متوقف می‌شود (outermost، برایِ متن و کالبک)
    router.message.outer_middleware(BlockedCustomerMiddleware())
    router.callback_query.outer_middleware(BlockedCustomerMiddleware())
    # C1: زدنِ دکمه‌یِ منو وسطِ چک‌اوت، state رو پاک می‌کنه و به هندلرِ درست می‌رسه (outer، قبلِ فیلترِ state)
    router.message.outer_middleware(MenuButtonEscapeMiddleware(texts.CUSTOMER_MENU_BUTTONS))
    router.include_router(orders.router)
    router.include_router(payments.router)
    router.include_router(cart_proposals.router)
    router.include_router(product_photos.router)
    router.include_router(checkout.router)  # F20: قبل از customer.router (catch-all)
    router.include_router(customer.router)
    return router
