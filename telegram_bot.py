import asyncio
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sozlamalar.settings')

import django
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler

load_dotenv()
django.setup()

from handlers.guruhlar import guruhlar
from handlers.menu import menu_callback
from handlers.registration import registration_conv_handler
from handlers.start import start
from handlers.status import status

BOT_TOKEN = os.getenv('BOT_TOKEN', '')
ADMIN_TELEGRAM_ID = os.getenv('ADMIN_TELEGRAM_ID', '')

def main() -> None:
    if not BOT_TOKEN:
        print('BOT_TOKEN topilmadi. .env faylida BOT_TOKEN ni kiriting.')
        return

    if not ADMIN_TELEGRAM_ID:
        print('ADMIN_TELEGRAM_ID topilmadi. .env faylida ADMIN_TELEGRAM_ID ni kiriting.')
        return

    asyncio.set_event_loop(asyncio.new_event_loop())

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(registration_conv_handler)
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('status', status))
    app.add_handler(CommandHandler('guruhlar', guruhlar))
    app.add_handler(CallbackQueryHandler(menu_callback))


    print('Telegram bot ishga tushdi...')
    app.run_polling()


if __name__ == '__main__':
    main()
