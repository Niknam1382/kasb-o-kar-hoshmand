"""حذفِ حسابِ *خودِ* فروشگاه‌دار (پ۶۵ · نیمهٔ دومِ موردِ ۲۷/۴۱).

چرا این فایل کنارِ `shop_purge_service` است و آن را صدا نمی‌زند: آن سرویس «حذفِ قطعیِ داده»
از پنلِ ادمین است و *همه‌چیز* را از جمله دفترِ مالی می‌بُرد. خواستهٔ اینجا چیزِ دیگری است —
«خودم می‌خواهم حسابم را ببندم» — و دو نیاز با هم در تضادند:

۱) اسنادِ مالیِ پلتفرم و سندِ حقوقیِ فروشگاه نباید محو شوند: `payments`، `wallet_transactions`،
   `wallet_charges`، `commission_receivables`، `invoices`، `orders_consultations` و
   `audit_log_entries` (که زنجیرهٔ هش دارد) دست‌نخورده می‌مانند. با هر ردیفِ ممیزیِ پاک‌شده
   `scripts/verify_audit_chain.py` می‌شکند و دفتری که روزی شاهدِ بیرونی است بی‌ارزش می‌شود.
۲) داده‌هایِ *شخصی* باید بروند: هویتِ خودِ فروشگاه‌دار، هویتِ مشتریانی که با رباتِ او حرف زده‌اند،
   متنِ گفتگوها، دفترچهٔ آدرس، کدهایِ OTP، و همهٔ رازهایِ اتصال (توکنِ تلگرام/بله، رازِ وبهوک،
   مرچنت، توکنِ دسترسیِ اینستاگرام).

پس این مسیر «بستنِ حساب + بی‌نام‌سازیِ هویت» است، نه «پاک‌کردنِ هر چیز». سه نکته که اگر بعداً
«تمیزکاری» خوانده شوند، خراب می‌شوند:

• `telegram_id` خودِ فروشگاه‌دار و `referral_code`اش می‌مانند: اولی برایِ این‌که همان نفر دوباره
  با همان هویتِ تلگرامی ثبت‌نامِ تازه نسازد (میدل‌ورِ هویت حسابِ بسته‌شده را می‌شناسد)، دومی برایِ
  این‌که تاریخچهٔ حسابِ کسانی که با کدِ او آمده‌اند نشکند. نام/موبایل/ایمیل/یوزرنیم می‌روند.
• مشتری هم *ردیفش* می‌ماند و *هویتش* می‌رود: `telegram_id` به `-id` تبدیل می‌شود (شناسه‌هایِ
  تلگرام همیشه مثبت‌اند، پس هرگز با شناسهٔ واقعیِ کسی نمی‌جنگد و یکتاییِ
  (فروشگاه، شناسه، بستر) حفظ می‌شود). این‌طور ارجاعِ سفارش‌ها و دفترِ کیف‌پول سالم می‌ماند و
  «پولِ این سفارش از کدامِ مشتری بود» بی‌نام باقی می‌ماند، نه گم.
• موجودیِ کیف‌پولِ صفرنشده مانعِ حذف است: هیچ‌کس با زدنِ یکِ دکمه نباید اعتبارِ خریداری‌شده‌اش را
  از دست بدهد. در همان حالت *هیچ* ردیفی عوض نمی‌شود (بی‌اثر، نه نصفه).

ترتیبِ حذف *دستی* است، نه `ON DELETE CASCADE` (همان قراردادِ `shop_purge_service`: اسکیمای این
پروژه عمداً cascade ندارد). تراکنشِ تکپارچه و مسئولیتِ `commit()` با فراخواننده است تا پیش از
خاموش‌کردنِ رباتِ زنده (که کارِ شبکه است) عدد قطعی شود (قاعدهٔ ۷).
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    AuditEventType,
    Cart,
    CartAiProposal,
    CartItem,
    ConversationMessage,
    Customer,
    CustomerAddress,
    DirectMessage,
    InstagramAccount,
    Notification,
    OtpCode,
    OrderConsultation,
    ScheduledBroadcast,
    ShopBot,
    ShopOwner,
)
from app.services import audit_log_service, order_state, owner_activity_service

# مقدارِ نگهبانِ ستون‌هایِ NOT NULL که راز داشتند: نه توکنِ واقعیِ کسی، نه چیزی که بتوان با آن
# رباتی را اجرا کرد. `webhook_secret_token` رویِ `EncryptedToken` است و رشتهٔ خالی را به NULL
# می‌بَرد ⇒ باید غیرخالی باشد.
SECRET_WIPED = "حذف‌شده"

BLOCK_WALLET = "wallet"
BLOCK_RESERVED = "reserved"

# صف‌هایِ خروجیِ باز: بعد ازِ بسته‌شدنِ حساب هرگز ارسال‌شدنی نیستند و اگر بمانند، جابِ اعلان‌ها
# تا سقفِ تلاشِ خودشان بیهوده دوباره‌دستی می‌کند.
_BROADCAST_OPEN_STATUSES = ("pending", "queued")


@dataclass(slots=True)
class DeletionPreview:
    """آنچه کاربر *پیش از* تایید باید ببیند، و آنچه مانعِ حذف است."""

    owner_id: int
    bot_count: int = 0
    customers: int = 0
    messages: int = 0
    addresses: int = 0
    orders: int = 0
    open_orders: int = 0
    pending_notifications: int = 0
    pending_broadcasts: int = 0
    instagram_accounts: int = 0
    bale_bots: int = 0
    wallet_toman: int = 0
    reserved_toman: int = 0
    blockers: tuple[str, ...] = ()

    @property
    def blocked(self) -> bool:
        return bool(self.blockers)


async def _bots_of(session: AsyncSession, owner_id: int) -> list[ShopBot]:
    query = select(ShopBot).where(ShopBot.shop_owner_id == owner_id).order_by(ShopBot.id)
    return list((await session.execute(query)).scalars().all())


async def _count(session: AsyncSession, model, *conditions) -> int:
    return int((await session.execute(select(func.count()).select_from(model).where(*conditions))).scalar_one())


async def preview(session: AsyncSession, owner: ShopOwner) -> DeletionPreview:
    """شمارشِ چیزی که می‌رود و چیزی که می‌ماند + تشخیصِ مانع‌ها (هیچ چیزی را عوض نمی‌کند)."""
    bots = await _bots_of(session, owner.id)
    bot_ids = [bot.id for bot in bots]
    data = DeletionPreview(
        owner_id=owner.id,
        bot_count=len(bots),
        wallet_toman=int(owner.wallet_balance_toman or 0),
        reserved_toman=int(owner.commission_reserved_toman or 0),
        bale_bots=sum(1 for bot in bots if bot.bale_bot_id is not None),
    )
    if bot_ids:
        customer_ids = select(Customer.id).where(Customer.shop_bot_id.in_(bot_ids))
        data.customers = await _count(session, Customer, Customer.shop_bot_id.in_(bot_ids))
        data.messages = await _count(session, ConversationMessage, ConversationMessage.customer_id.in_(customer_ids))
        data.addresses = await _count(session, CustomerAddress, CustomerAddress.customer_id.in_(customer_ids))
        data.orders = await _count(session, OrderConsultation, OrderConsultation.shop_bot_id.in_(bot_ids))
        data.open_orders = await _count(
            session, OrderConsultation, OrderConsultation.shop_bot_id.in_(bot_ids), OrderConsultation.status.in_(order_state.OPEN)
        )
        data.instagram_accounts = await _count(session, InstagramAccount, InstagramAccount.shop_bot_id.in_(bot_ids))
        data.pending_notifications = await _count(
            session, Notification, Notification.shop_bot_id.in_(bot_ids), Notification.status == "pending"
        )
        data.pending_broadcasts = await _count(
            session, ScheduledBroadcast, ScheduledBroadcast.shop_bot_id.in_(bot_ids), ScheduledBroadcast.status.in_(_BROADCAST_OPEN_STATUSES)
        )
    data.blockers = _blockers(data)
    return data


def _blockers(data: DeletionPreview) -> tuple[str, ...]:
    """فقط پولِ مانده مانع است؛ سفارشِ باز هشدار است، نه مانع (تصمیم با صاحبِ حساب است)."""
    out: list[str] = []
    if data.wallet_toman > 0:
        out.append(BLOCK_WALLET)
    if data.reserved_toman > 0:
        out.append(BLOCK_RESERVED)
    return tuple(out)


async def delete_account(
    session: AsyncSession, owner: ShopOwner, *, actor_telegram_id: int | None = None, now: datetime.datetime | None = None
) -> dict:
    """حساب را می‌بندد، هویت را بی‌نام می‌کند و رازها را پاک می‌کند؛ اسنادِ مالی و ممیزی می‌مانند.

    خروجی: `{"blocked": [...], "bot_ids": [...], "erased": {...}, "preview": DeletionPreview}`
    اگر `blocked` خالی نبود *هیچ* چیزی عوض نشده و فراخواننده باید شرطِ پول را دوباره توضیح بدهد.
    این تابع `commit()` نمی‌زند.
    """
    data = await preview(session, owner)
    if data.blocked:
        return {"blocked": list(data.blockers), "bot_ids": [], "erased": {}, "preview": data}

    bots = await _bots_of(session, owner.id)
    bot_ids = [bot.id for bot in bots]
    erased: dict[str, int] = {}
    moment = now or datetime.datetime.now(datetime.timezone.utc)

    if bot_ids:
        customer_ids = select(Customer.id).where(Customer.shop_bot_id.in_(bot_ids))
        cart_ids = select(Cart.id).where(Cart.shop_bot_id.in_(bot_ids))

        # ۱) محتوایِ گفتگو، پیامِ مستقیم، آدرس و سبد — هیچ ارزشِ حسابداری ندارند ⇒ می‌روند.
        for table, model, column, conditions in (
            ("cart_items", CartItem, CartItem.cart_id, cart_ids),
            ("cart_ai_proposals", CartAiProposal, CartAiProposal.cart_id, cart_ids),
            ("carts", Cart, Cart.shop_bot_id, bot_ids),
            ("conversation_messages", ConversationMessage, ConversationMessage.customer_id, customer_ids),
            ("direct_messages", DirectMessage, DirectMessage.customer_id, customer_ids),
            ("customer_addresses", CustomerAddress, CustomerAddress.customer_id, customer_ids),
            ("instagram_accounts", InstagramAccount, InstagramAccount.shop_bot_id, bot_ids),
        ):
            result = await session.execute(delete(model).where(column.in_(conditions)))
            erased[table] = int(result.rowcount or 0)

        # ۲) فقط صفِ *باز* می‌رود؛ اعلانِ رفته/شکست‌خورده تاریخچه است و بی‌هویت می‌ماند.
        result = await session.execute(
            delete(Notification).where(Notification.shop_bot_id.in_(bot_ids), Notification.status == "pending")
        )
        erased["notifications"] = int(result.rowcount or 0)
        result = await session.execute(
            delete(ScheduledBroadcast).where(
                ScheduledBroadcast.shop_bot_id.in_(bot_ids), ScheduledBroadcast.status.in_(_BROADCAST_OPEN_STATUSES)
            )
        )
        erased["scheduled_broadcasts"] = int(result.rowcount or 0)

        # ۳) بی‌نام‌سازیِ مشتری: ردیف می‌ماند (تا سفارش/دفترِ کیف‌پول به جایی بند بماند)، هویت می‌رود.
        result = await session.execute(
            update(Customer)
            .where(Customer.shop_bot_id.in_(bot_ids))
            .values(
                telegram_id=-Customer.id,
                first_name=None,
                last_name=None,
                username=None,
                phone_number=None,
                phone_via_contact=False,
                crm_notes=None,
                crm_tags=None,
                is_blocked=False,
            )
        )
        erased["customers_anonymized"] = int(result.rowcount or 0)

        # ۴) خاموش‌کردنِ ربات و برداشتنِ هر رازِ اتصال.
        result = await session.execute(
            update(ShopBot)
            .where(ShopBot.id.in_(bot_ids))
            .values(
                is_active=False,
                disabled_reason="حذفِ حسابِ فروشگاه‌دار",
                encrypted_token=SECRET_WIPED,
                webhook_secret_token=SECRET_WIPED,
                bale_encrypted_token=None,
                bale_bot_id=None,
                bale_bot_username=None,
                bale_bot_enabled=False,
                bale_provider_token=None,
                zarinpal_merchant_id=None,
                support_enabled=False,
                support_contact_username=None,
                support_contact_phone=None,
                knowledge_channel_id=None,
                knowledge_channel_bot=None,
                branding_applied_bio=None,
                branding_next_check_at=moment,
            )
        )
        erased["shop_bots_closed"] = int(result.rowcount or 0)

    # ۵) شماره‌هایِ خامِ کدِ موقتِ خودِ حساب و اعلانِ صف‌مانده‌اش (بی‌ربات هم ممکن است، پس صفرِ اولیه).
    erased.setdefault("notifications", 0)
    result = await session.execute(delete(OtpCode).where(OtpCode.shop_owner_id == owner.id))
    erased["otp_codes"] = int(result.rowcount or 0)
    result = await session.execute(delete(Notification).where(Notification.owner_id == owner.id, Notification.status == "pending"))
    erased["notifications"] += int(result.rowcount or 0)

    # ۶) هویتِ خودِ فروشگاه‌دار.
    result = await session.execute(
        update(ShopOwner)
        .where(ShopOwner.id == owner.id)
        .values(
            first_name=None, last_name=None, phone_number=None, email=None, username=None, phone_verified=False, email_verified=False
        )
    )
    erased["owner_anonymized"] = int(result.rowcount or 0)

    # ۷) دروازهٔ ورود: از این لحظه هر پیامی با «حساب غیرفعال است» جواب داده می‌شود (میدل‌ورِ هویت).
    await owner_activity_service.soft_delete(session, owner, now=moment)

    removed_rows = sum(erased.values())
    await audit_log_service.log(
        session,
        AuditEventType.OWNER_SELF_DELETED,
        actor_telegram_id=actor_telegram_id,
        details=(
            f"owner={owner.id} · ربات‌ها={len(bot_ids)} · ردیف‌هایِ پاک‌شده={removed_rows} · "
            f"مشتری‌هایِ بی‌نام={erased.get('customers_anonymized', 0)} · سفارش‌هایِ ماندنی={data.orders} · "
            "اسنادِ مالی و ممیزی نگه داشته شد"
        ),
    )
    return {"blocked": [], "bot_ids": bot_ids, "erased": erased, "preview": data}
