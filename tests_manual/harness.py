from __future__ import annotations

import datetime
from typing import Any

from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiogram.methods import TelegramMethod
from aiogram.methods.base import TelegramType
from aiogram.types import (
    CallbackQuery,
    Chat,
    ChatInviteLink,
    ChatMemberAdministrator,
    ChatMemberBanned,
    ChatMemberLeft,
    ChatMemberMember,
    ChatMemberOwner,
    Contact,
    Message,
    File,
    PhotoSize,
    Update,
    User,
    Voice,
)

_STATUS_TO_MODEL = {
    "creator": ChatMemberOwner,
    "administrator": ChatMemberAdministrator,
    "member": ChatMemberMember,
    "left": ChatMemberLeft,
    "kicked": ChatMemberBanned,
}


def _as_chat_id(identifier: Any) -> int:
    try:
        return int(identifier)
    except (TypeError, ValueError):
        return abs(hash(str(identifier))) % (10**9)


def fake_user(user_id: int, first_name: str = "Test", is_bot: bool = False, username: str | None = None) -> User:
    return User.model_construct(id=user_id, is_bot=is_bot, first_name=first_name, username=username)


class FakeSession(BaseSession):
    """
    Session ی جعلی که به‌جای زدنِ درخواستِ واقعی به تلگرام، خروجیِ ازپیش‌پیکربندی‌شده
    برمی‌گردونه و همه‌ی درخواست‌های خروجی رو برای assertion توی تست‌ها ذخیره می‌کنه.
    """

    def __init__(self) -> None:
        super().__init__()
        self.sent_messages: list[dict[str, Any]] = []
        self.sent_photos: list[dict[str, Any]] = []
        self.sent_documents: list[dict[str, Any]] = []
        self.answered_callbacks: list[dict[str, Any]] = []
        self.deleted_messages: list[dict[str, Any]] = []
        self.chat_member_status: dict[tuple[str, int], str] = {}
        self.chat_info: dict[str, Chat] = {}
        self.bot_identities: dict[str, User] = {}
        self.downloaded_files: dict[str, bytes] = {}
        self._next_message_id = 10_000

    # --- پیکربندیِ رفتار جعلی از داخل تست ---
    def set_chat_member_status(self, chat_id: Any, user_id: int, status: str) -> None:
        self.chat_member_status[(str(chat_id), user_id)] = status

    def set_chat_info(self, identifier: Any, chat: Chat) -> None:
        self.chat_info[str(identifier)] = chat

    def set_bot_identity(self, token: str, user: User) -> None:
        self.bot_identities[token] = user

    def set_downloaded_file(self, file_id: str, content: bytes) -> None:
        self.downloaded_files[file_id] = content

    async def close(self) -> None:
        return None

    def _next_id(self) -> int:
        self._next_message_id += 1
        return self._next_message_id

    def _build_message(self, chat_id: Any, **extra: Any) -> Message:
        chat = self.chat_info.get(str(chat_id)) or Chat.model_construct(id=_as_chat_id(chat_id), type="private")
        return Message.model_construct(
            message_id=self._next_id(),
            date=datetime.datetime.now(datetime.timezone.utc),
            chat=chat,
            **extra,
        )

    async def make_request(self, bot: Bot, method: TelegramMethod[TelegramType], timeout: int | None = None) -> Any:
        name = type(method).__name__

        if name == "GetMe":
            return self.bot_identities.get(bot.token) or fake_user(bot.id, "TestBot", is_bot=True, username="test_bot")

        if name == "SendMessage":
            self.sent_messages.append(
                {"chat_id": method.chat_id, "text": method.text, "reply_markup": getattr(method, "reply_markup", None)}
            )
            return self._build_message(method.chat_id, text=method.text, reply_markup=getattr(method, "reply_markup", None))

        if name == "SendPhoto":
            self.sent_photos.append(
                {"chat_id": method.chat_id, "caption": getattr(method, "caption", None), "photo": method.photo}
            )
            photo = [PhotoSize.model_construct(file_id="fake_photo_id", file_unique_id="fake_photo_uid", width=100, height=100)]
            return self._build_message(
                method.chat_id, photo=photo, caption=getattr(method, "caption", None), reply_markup=getattr(method, "reply_markup", None)
            )

        if name == "SendDocument":
            self.sent_documents.append(
                {"chat_id": method.chat_id, "caption": getattr(method, "caption", None), "document": method.document}
            )
            return self._build_message(method.chat_id, caption=getattr(method, "caption", None))

        if name == "EditMessageText":
            return self._build_message(method.chat_id, text=method.text, reply_markup=getattr(method, "reply_markup", None))

        if name == "EditMessageCaption":
            return self._build_message(
                method.chat_id, caption=getattr(method, "caption", None), reply_markup=getattr(method, "reply_markup", None)
            )

        if name == "EditMessageReplyMarkup":
            return self._build_message(method.chat_id, reply_markup=getattr(method, "reply_markup", None))

        if name == "DeleteMessage":
            self.deleted_messages.append({"chat_id": method.chat_id, "message_id": method.message_id})
            return True

        if name == "AnswerCallbackQuery":
            self.answered_callbacks.append(
                {"callback_query_id": method.callback_query_id, "text": getattr(method, "text", None), "show_alert": getattr(method, "show_alert", None)}
            )
            return True

        if name == "GetFile":
            # file_path رو عمداً برابرِ خودِ file_id می‌ذاریم؛ چون فقط داخلِ همین
            # هارنسِ تست استفاده می‌شه و stream_content زیر همون رو برای پیدا
            # کردنِ محتوای جعلی می‌خونه.
            return File.model_construct(file_id=method.file_id, file_unique_id=f"{method.file_id}_uid", file_size=len(self.downloaded_files.get(method.file_id, b"")), file_path=method.file_id)

        if name == "GetChatMember":
            status = self.chat_member_status.get((str(method.chat_id), method.user_id), "left")
            model = _STATUS_TO_MODEL.get(status, ChatMemberLeft)
            return model.model_construct(status=status, user=fake_user(method.user_id))

        if name == "GetChat":
            chat = self.chat_info.get(str(method.chat_id))
            if chat is None:
                chat = Chat.model_construct(id=_as_chat_id(method.chat_id), type="channel", title=str(method.chat_id), username=str(method.chat_id).lstrip("@"))
            return chat

        if name == "CreateChatInviteLink":
            return ChatInviteLink.model_construct(
                invite_link=f"https://t.me/joinchat/fake_{_as_chat_id(method.chat_id)}",
                creator=fake_user(0, is_bot=True),
                creates_join_request=False,
                is_primary=True,
                is_revoked=False,
            )

        if name in ("DeleteWebhook", "SetWebhook", "AnswerPreCheckoutQuery"):
            return True

        if name == "GetUpdates":
            return []

        raise NotImplementedError(f"FakeSession: متد «{name}» هنوز توی هارنسِ تست پشتیبانی نمی‌شه.")

    async def stream_content(self, url, headers=None, timeout=30, chunk_size=65536, raise_for_status=True):
        file_id = str(url).rsplit("/", 1)[-1]
        content = self.downloaded_files.get(file_id, b"fake-binary-content")
        yield content


def make_message_update(
    update_id: int,
    text: str | None = None,
    user_id: int = 111111,
    chat_id: int | None = None,
    first_name: str = "تست",
    username: str | None = None,
    contact_phone: str | None = None,
    photo: bool = False,
    voice: bool = False,
    caption: str | None = None,
    forward_from_chat: Chat | None = None,
    message_id: int | None = None,
) -> Update:
    resolved_chat_id = chat_id if chat_id is not None else user_id
    kwargs: dict[str, Any] = {
        "message_id": message_id or 1,
        "date": datetime.datetime.now(datetime.timezone.utc),
        "chat": Chat.model_construct(id=resolved_chat_id, type="private"),
        "from_user": fake_user(user_id, first_name, username=username),
        "text": text,
        "caption": caption,
    }

    if contact_phone is not None:
        kwargs["contact"] = Contact.model_construct(phone_number=contact_phone, first_name=first_name, user_id=user_id)

    if photo:
        kwargs["photo"] = [PhotoSize.model_construct(file_id="incoming_photo_id", file_unique_id="incoming_photo_uid", width=200, height=200)]

    if voice:
        kwargs["voice"] = Voice.model_construct(file_id="incoming_voice_id", file_unique_id="incoming_voice_uid", duration=3)

    if forward_from_chat is not None:
        kwargs["forward_from_chat"] = forward_from_chat

    message = Message.model_construct(**kwargs)
    return Update.model_construct(update_id=update_id, message=message)


def make_callback_update(
    update_id: int,
    data: str,
    user_id: int = 111111,
    chat_id: int | None = None,
    message_id: int = 1,
    message_text: str | None = "پیام قبلی",
    message_caption: str | None = None,
    first_name: str = "تست",
) -> Update:
    resolved_chat_id = chat_id if chat_id is not None else user_id
    message = Message.model_construct(
        message_id=message_id,
        date=datetime.datetime.now(datetime.timezone.utc),
        chat=Chat.model_construct(id=resolved_chat_id, type="private"),
        text=message_text,
        caption=message_caption,
    )
    callback = CallbackQuery.model_construct(
        id=str(update_id),
        from_user=fake_user(user_id, first_name),
        chat_instance="fake_chat_instance",
        data=data,
        message=message,
    )
    return Update.model_construct(update_id=update_id, callback_query=callback)


# =============================================================================
# کمک‌کننده‌های مشترکِ همه‌ی فایل‌های تست: ریست دیتابیس + ساختِ دیسپچرها
# =============================================================================
async def reset_database() -> None:
    """
    همه‌ی جدول‌ها رو خالی می‌کنه (نه drop) تا اسکیمای alembic دست‌نخورده بمونه.

    لیستِ جدول‌ها دیگه دستی نگه‌داشته نمی‌شه — مستقیم از pg_tables خونده
    می‌شه. چرا: فراموش‌کردنِ اضافه‌کردنِ یه جدولِ جدید به یه لیستِ ثابت، دقیقاً
    همون باگی بود که دوبار توی همین پروژه اتفاق افتاد (اول moderation_rules/
    audit_log_entries، بعد ai_api_key_pool — که باعث شد کلیدهای باقی‌مونده از
    یه اجرای تستِ قبلی، توی اجرای بعدی هم بمونن و باعثِ چند تا fail بشن).
    این‌جوری، هر جدولِ جدیدی که بعداً اضافه بشه، خودکار پاک می‌شه — نیازی به
    یادآوریِ دستی نیست.
    """
    from sqlalchemy import text

    from app.database.session import session_scope

    async with session_scope() as session:
        result = await session.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename != 'alembic_version'")
        )
        tables = [row[0] for row in result.fetchall()]
        if tables:
            quoted = ", ".join(f'"{t}"' for t in tables)
            await session.execute(text(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE"))


def build_test_dispatchers() -> tuple[Dispatcher, Dispatcher, Any, Bot]:
    """
    یه جفت دیسپچرِ (اصلی/فروشگاهی) دقیقاً مثلِ چیزی که app.main در استارتاپِ واقعی
    می‌سازه، برمی‌گردونه. bot_manager برگشتی رو می‌شه به دیسپچرِ اصلی به‌عنوانِ
    dispatcher["bot_manager"] تزریق کرد (خودِ create_main_dispatcher این کارو می‌کنه).
    main_bot ای که برگردونده می‌شه همونیه که create_shop_dispatcher به‌صورتِ داخلی
    زیرِ dispatcher["main_bot"] ست کرده — یعنی برای چک‌کردنِ پیام‌هایی که هندلرهای
    شاپ‌بات (مثلاً فوروارد عکس یا اطلاع‌رسانیِ سفارش) به فروشگاه‌دار می‌فرستن، باید
    دقیقاً همینو استفاده کرد، نه یه Bot جدا.
    """
    from app.main import create_main_dispatcher, create_shop_dispatcher
    from app.services.bot_manager import ShopBotManager

    main_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())
    shop_dispatcher = create_shop_dispatcher(main_bot)
    bot_manager = ShopBotManager(shop_dispatcher)
    main_dispatcher = create_main_dispatcher(bot_manager)
    main_dispatcher["bot_manager"] = bot_manager
    return main_dispatcher, shop_dispatcher, bot_manager, main_bot


def make_shop_bot(token: str = "111111:SHOP_BOT_FAKE_TOKEN") -> Bot:
    return Bot(token=token, session=FakeSession())
