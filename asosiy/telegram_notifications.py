import logging

from telegram.error import TelegramError

from foydalanuvchilar.telegram_integration import (
    TelegramIntegrationConfigError,
    notify_telegram_user,
)


logger = logging.getLogger(__name__)


def notify_users(users, text: str) -> None:
    notified_ids = set()
    for user in users:
        telegram_id = user.telegram_id
        if not telegram_id or telegram_id in notified_ids:
            continue
        notified_ids.add(telegram_id)
        try:
            notify_telegram_user(user, text)
        except (TelegramError, OSError, TelegramIntegrationConfigError):
            logger.exception(
                "Telegram notification failed for user %s.",
                user.pk,
            )
