"""
تست: P22 — چینشِ دکمه‌هایِ رباتِ کاربر (دونادونه)

قاعدهٔ محصول: هیچ‌کدام از منوهایِ مشتری ستونی/ردیف‌تکی نباشند، به‌جز:
۱) دکمهٔ «❌ …» که سفارش را بی‌تاییدیهٔ دوم لغو می‌کند ⇒ همیشه تمام‌عرض و تنها؛
۲) برچسبِ بلند که در نصفِ عرض با «…» بریده می‌شود ⇒ تنها می‌ماند.
ترتیبِ خطیِ دکمه‌ها عوض نمی‌شود (هندلرها و تست‌هایِ موجود با همان ترتیب کار می‌کنند).

اجرا: python3 tests_manual/test_customer_keyboard_layout.py
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from app.bots.main_bot import keyboards as main_keyboards  # noqa: E402
from app.bots.shop_bot import keyboards  # noqa: E402
from app.bots.shop_bot import texts as shop_texts  # noqa: E402
from app.database.models import TenantMode  # noqa: E402


def rows(markup) -> list[list[str]]:
    source = markup.keyboard if hasattr(markup, "keyboard") else markup.inline_keyboard
    return [[button.text for button in row] for row in source]


def flat(markup) -> list[str]:
    return [label for row in rows(markup) for label in row]


# ============================================================================= ۱ — منویِ اصلی
def test_main_menu_is_paired() -> None:
    assert rows(keyboards.customer_main_keyboard(TenantMode.SALES, False)) == [
        [shop_texts.BTN_PRODUCTS, shop_texts.BTN_CART],
        [shop_texts.BTN_MY_ORDERS],
    ]
    assert rows(keyboards.customer_main_keyboard(TenantMode.SALES, True)) == [
        [shop_texts.BTN_PRODUCTS, shop_texts.BTN_CART],
        [shop_texts.BTN_MY_ORDERS, shop_texts.BTN_SUPPORT],
    ]
    # P24: در مودِ مشاوره دو دکمهٔ مرده حذف شد؛ تنها ردیفِ ممکن، ردیفِ پشتیبانی است و
    # بی‌پشتیبانی هیچ کیبوردی فرستاده نمی‌شود (ReplyKeyboardRemove).
    assert getattr(keyboards.customer_main_keyboard(TenantMode.CONSULTATION, False), "remove_keyboard", None) is True
    assert rows(keyboards.customer_main_keyboard(TenantMode.CONSULTATION, True)) == [
        [shop_texts.BTN_SUPPORT]
    ]
    print("✅ test_main_menu_is_paired PASSED")


# ============================================================================= ۲ — ترتیب خطی حفظ می‌شود
def test_pairing_never_reorders_buttons() -> None:
    assert flat(keyboards.customer_main_keyboard("sales", True)) == [
        shop_texts.BTN_PRODUCTS,
        shop_texts.BTN_CART,
        shop_texts.BTN_MY_ORDERS,
        shop_texts.BTN_SUPPORT,
    ]
    assert flat(keyboards.my_orders_list_keyboard(["a", "b", "c", "d", "e"], 0, 9)) == [
        "🔎 سفارشِ 1",
        "🔎 سفارشِ 2",
        "🔎 سفارشِ 3",
        "🔎 سفارشِ 4",
        "🔎 سفارشِ 5",
        "بعدی ➡️",
    ]
    assert flat(keyboards.payment_methods_keyboard("k", ["card", "bale", "zarinpal", "manual"])) == [
        shop_texts.PAY_METHOD_LABELS["card"],
        shop_texts.PAY_METHOD_LABELS["bale"],
        shop_texts.PAY_METHOD_LABELS["zarinpal"],
        shop_texts.PAY_METHOD_LABELS["manual"],
        "❌ لغوِ سفارش",
    ]
    print("✅ test_pairing_never_reorders_buttons PASSED")


# ============================================================================= ۳ — لغو همیشه تنها
def test_cancel_buttons_stay_full_width() -> None:
    assert rows(keyboards.checkout_confirm_keyboard()) == [["✅ ثبتِ نهایی"], ["❌ انصراف"]]
    assert rows(keyboards.checkout_confirm_keyboard(show_code_button=True)) == [
        ["✅ ثبتِ نهایی", "🎟 کد تخفیف دارم"],
        ["❌ انصراف"],
    ]
    assert rows(keyboards.receipt_keyboard("k")) == [["📎 ارسالِ رسید", "⬅️ روشِ دیگه"], ["❌ لغوِ سفارش"]]
    assert rows(keyboards.payment_methods_keyboard("k", ["card", "bale"])) == [
        [shop_texts.PAY_METHOD_LABELS["card"], shop_texts.PAY_METHOD_LABELS["bale"]],
        ["❌ لغوِ سفارش"],
    ]
    card = keyboards.my_order_card_keyboard("k", can_invoice=True, can_cancel=True, digital_order_ids=[], page=0, can_pay=True)
    assert rows(card) == [["💳 پرداخت", "📄 فاکتور"], ["⬅️ برگشت به فهرست"], ["❌ لغوِ سفارش"]], rows(card)
    print("✅ test_cancel_buttons_stay_full_width PASSED")


# ============================================================================= ۴ — برچسبِ بلند تنگ نمی‌شود
def test_long_labels_are_not_squeezed() -> None:
    manual = shop_texts.PAY_METHOD_LABELS["manual"]
    assert len(manual) > 26, "این تست عمداً رویِ بلندترین برچسب نوشته شده"
    assert rows(keyboards.payment_methods_keyboard("k", ["manual"])) == [[manual], ["❌ لغوِ سفارش"]]
    assert rows(keyboards.payment_methods_keyboard("k", ["bale", "manual", "card"])) == [
        [shop_texts.PAY_METHOD_LABELS["bale"]],
        [manual],
        [shop_texts.PAY_METHOD_LABELS["card"]],
        ["❌ لغوِ سفارش"],
    ], "بلند تنها می‌ماند و جایِ خودش را هم به هم نمی‌زند"
    print("✅ test_long_labels_are_not_squeezed PASSED")


# ============================================================================= ۵ — نگارستان و کارتِ محصول
def test_gallery_and_product_card_are_paired() -> None:
    class _P:
        def __init__(self, pk: int, name: str, active: bool = True) -> None:
            self.id, self.name, self.is_active = pk, name, active

    gallery = _which([_P(i, f"محصول {i}") for i in range(1, 6)])
    assert [len(r) for r in gallery] == [2, 2, 1], gallery
    card = _card(_P(1, "x"))
    assert card == [["➕ افزودن به سبد", "🛒 دیدنِ سبدِ خرید"]]
    assert _card(_P(1, "x", active=False)) == [["🛒 دیدنِ سبدِ خرید"]]
    print("✅ test_gallery_and_product_card_are_paired PASSED")


def _which(products):
    from app.bots.shop_bot.handlers import product_photos

    return rows(product_photos.which_keyboard(products))


def _card(product):
    from app.bots.shop_bot.handlers import product_photos

    return rows(product_photos.card_keyboard(product))


# ============================================================================= ۶ — پنل‌هایِ ادمین و فروشگاه‌دار
def test_panel_menus_are_paired() -> None:
    """مشکلِ ۲ کاربر: منویِ فروشگاه‌دار «سه ردیفِ تک، بعد دونفره، بعد یکِ ردیفِ سه‌تایی» بود.
    قاعده: هیچ ردیفی بیشتر از دو دکمه ندارد و تا ردیفِ آخر، همه دونفره‌اند."""
    # P42 · موردِ ۱ و ۳۵: دکمهٔ سبز از منو رفته و سوئیچِ «سوال‌هایِ بی‌جواب» هم ردیفش را برداشته؛
    # در هر دو حالت چینشِ دونفره باید سالم بماند.
    for knowledge_gap in (False, True):
        for mode in ("sales", "consultation"):
            rows_of_menu = rows(main_keyboards.shop_owner_panel_keyboard(mode, knowledge_gap=knowledge_gap))
            widths = [len(row) for row in rows_of_menu]
            assert max(widths) <= 2, (mode, knowledge_gap, widths)
            assert all(width == 2 for width in widths[:-1]), (mode, knowledge_gap, widths)

    for is_super in (True, False):
        widths = [len(row) for row in rows(main_keyboards.admin_panel_keyboard(is_super))]
        assert max(widths) <= 2 and all(width == 2 for width in widths[:-1]), (is_super, widths)

    flat_super = flat(main_keyboards.admin_panel_keyboard(True))
    assert flat_super[:4] == ["📢 مدیریت کانال‌های اجباری", "🧾 صف تایید پرداخت‌ها", "💰 تنظیمات قیمت و تخفیف", "🔑 تنظیمات کلیدها"], flat_super
    assert "📜 گزارشِ ممیزی" in flat_super and "👑 مدیریتِ ادمین‌ها" in flat_super
    assert flat(main_keyboards.admin_panel_keyboard(False)) == [
        "📢 مدیریت کانال‌های اجباری",
        "🧾 صف تایید پرداخت‌ها",
        "📊 آمار سراسری",
        "📈 وضعیتِ همزمانی و عملکرد",  # P30-D
        "📣 پیام همگانی",
        "👥 مدیریت فروشگاه‌دارها",
        "🧹 کاربرانِ غیرفعال",
        "🛡 نگهبانِ محتوا",
        "⏱ اعتبار و زمان",
        "📜 گزارشِ ممیزی",
    ], "ردیف‌ها عوض شد، ترتیبِ دکمه‌ها نه"
    print("✅ test_panel_menus_are_paired PASSED")


def test_panel_inline_screens_are_paired() -> None:
    class _Bot:
        message_batch_seconds = 8
        bale_encrypted_token = None
        bale_bot_enabled = False
        low_stock_alert_threshold = 3
        # پ۵۸ · موردِ ۲۴-الف: کیبوردِ تنظیمات مود را می‌خواند تا «📦 اخطارِ موجودی» را در مشاوره
        # نشان ندهد؛ این فیکِ هم‌شکلِ `ShopBot` باید همان صفت را داشته باشد (رشته هم پذیرفته است،
        # مثلِ خودِ `shop_owner_panel_keyboard`).
        tenant_mode = "sales"

    class _Row:
        card_enabled = bale_enabled = zarinpal_enabled = manual_enabled = auto_accept_online = True

    widths = [len(row) for row in rows(main_keyboards.shop_settings_keyboard(_Bot()))]
    assert max(widths) <= 2, widths
    widths = [len(row) for row in rows(main_keyboards.payments_menu_keyboard(_Row(), _Bot()))]
    assert max(widths) <= 2, widths
    widths = [len(row) for row in rows(main_keyboards.profile_keyboard())]
    # پ۶۵ · قاعدهٔ ۸: تغییرِ عمدیِ انتظار — «🗑 حذفِ حسابِ من» ردیفِ *تنهایِ آخر* است (چهارم)،
    # تا خطرناک‌ترین فعلِ صفحه کنارِ ویرایش‌هایِ بی‌خطر دونفره نشود. بقیهٔ چینش دست‌نخورده است.
    assert widths == [2, 2, 2, 1], widths
    widths = [len(row) for row in rows(main_keyboards.audit_filter_keyboard("money", "24"))]
    assert max(widths) <= 2, widths
    print("✅ test_panel_inline_screens_are_paired PASSED")


def main() -> None:
    test_main_menu_is_paired()
    test_pairing_never_reorders_buttons()
    test_cancel_buttons_stay_full_width()
    test_long_labels_are_not_squeezed()
    test_gallery_and_product_card_are_paired()
    test_panel_menus_are_paired()
    test_panel_inline_screens_are_paired()


if __name__ == "__main__":
    main()
