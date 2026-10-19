from telegram import Update
from telegram.ext import ContextTypes
from asgiref.sync import sync_to_async

from asosiy.models import Group


@sync_to_async
def get_groups_text() -> str:
	groups = Group.objects.all()[:10]
	if not groups:
		return 'Hozircha guruhlar mavjud emas.'

	return 'Guruhlar:\n' + '\n'.join(
		f'- {group.name} ({group.subject})' for group in groups
	)


async def guruhlar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	text = await get_groups_text()
	await update.message.reply_text(text)
