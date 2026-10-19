import asyncio
import os

from telegram import Bot


class TelegramIntegrationConfigError(RuntimeError):
    pass


async def _send_message(token: str, chat_id: str, text: str) -> None:
    async with Bot(token=token) as bot:
        await bot.send_message(chat_id=chat_id, text=text)


def notify_admin_new_registration(user) -> None:
    token = os.getenv("BOT_TOKEN", "").strip()
    admin_chat_id = os.getenv("ADMIN_TELEGRAM_ID", "").strip()
    if not token or not admin_chat_id:
        raise TelegramIntegrationConfigError(
            "BOT_TOKEN and ADMIN_TELEGRAM_ID must be configured to notify the admin."
        )

    text = (
        "🌐 Sayt orqali yangi o‘quvchi ro‘yxatdan o‘tdi!\n\n"
        f"👤 F.I.Sh: {user.full_name}\n"
        f"📞 Telefon: {user.phone}\n"
        f"🔑 Login: {user.username}"
    )
    asyncio.run(_send_message(token, admin_chat_id, text))


def notify_telegram_user(user, text: str) -> None:
    if not user.telegram_id:
        return

    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise TelegramIntegrationConfigError(
            "BOT_TOKEN must be configured to notify a Telegram user."
        )

    asyncio.run(_send_message(token, str(user.telegram_id), text))
